# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from wild_boar_proxy import external_models as external_models_mod
from wild_boar_proxy.core import packets
from wild_boar_proxy.external_models import (
    contracts,
    errors,
    routes,
    run_external_models_command,
    state as state_mod,
)
from wild_boar_proxy.external_models import lifecycle
from wild_boar_proxy.external_models import transforms
from wild_boar_proxy.external_models import validate as validate_mod
from wild_boar_proxy.external_models.integration import ensure_installed_layout
from wild_boar_proxy.external_models.paths import ExternalModelsPaths
from wild_boar_proxy.external_models.state import capture_local_evidence, load_state_file
from wild_boar_proxy.runtime import RuntimeErrorInfo


def sample_route() -> dict[str, object]:
    return {
        "schema_version": 1,
        "route_id": "wbp-deepseek-v3",
        "display_name": "DeepSeek V3",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": "deepseek/deepseek-chat",
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
        "cost_class": "paid_or_free_limited",
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": True,
    }


def sample_evidence_payload(*, network_dependent: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": contracts.EVIDENCE_SCHEMA_VERSION,
        "captured_at_utc": "2026-06-27T00:00:00Z",
        "route_id": "wbp-deepseek-v3",
        "command_context": (
            "external-models check"
            if network_dependent
            else "external-models evidence capture"
        ),
        "network_dependent_evidence": network_dependent,
        "result": {
            "status": "ok",
            "machine_error_code": errors.OK,
            "requested_model": "wbp-deepseek-v3",
            "effective_model": "deepseek/deepseek-chat" if network_dependent else None,
            "provider": "openrouter",
            "fallback_used": False,
            "fallback_chain": ["wbp-deepseek-v3"],
            "cost_class": "paid_or_free_limited",
            "latency_ms": 42 if network_dependent else None,
        },
    }
    if network_dependent:
        payload["verification_scope"] = "route_provider_only"
        result = payload["result"]
        assert isinstance(result, dict)
        result["verification_scope"] = "route_provider_only"
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    return payload


class ExternalModelContractTests(unittest.TestCase):
    def test_default_state_payload_keeps_policy_separate(self) -> None:
        payload = contracts.default_state_payload()
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(
            payload["policy"],
            {
                "paid_routes_enabled": False,
                "paid_route_allowlist": [],
                "paid_route_default": "blocked",
            },
        )
        self.assertEqual(payload["adapter"]["state"], "stopped")
        self.assertFalse(payload["local_auth"]["token_present"])
        self.assertEqual(payload["routes"], {})

    def test_validate_route_schema_rejects_observed_state_field(self) -> None:
        route = sample_route() | {"last_check": "2026-05-12T00:00:00Z"}
        with self.assertRaises(RuntimeErrorInfo) as ctx:
            routes.validate_route_schema(route)
        self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")

    def test_validate_route_schema_accepts_canonical_route_ids(self) -> None:
        valid_ids = [
            "wbp-a",
            "wbp-AZ09",
            "wbp-a_b.c-d",
            "wbp-" + "a" * 128,
        ]
        for route_id in valid_ids:
            with self.subTest(route_id=route_id):
                validated = routes.validate_route_schema(
                    sample_route() | {"route_id": route_id}
                )
                self.assertEqual(validated["route_id"], route_id)

    def test_validate_route_schema_rejects_unsafe_route_ids(self) -> None:
        invalid_ids = [
            "foo-a",
            "wbp-",
            "wbp-/../../escape",
            "wbp-a/../b",
            "wbp-a\\b",
            "wbp-a\nb",
            "wbp-a..b",
            "wbp-é",
            "ｗbp-a",
            "wbp-" + "a" * 129,
        ]
        for route_id in invalid_ids:
            with self.subTest(route_id=route_id):
                with self.assertRaises(RuntimeErrorInfo) as ctx:
                    routes.validate_route_schema(sample_route() | {"route_id": route_id})
                self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")

    def test_validate_route_schema_rejects_unknown_transform_profile(self) -> None:
        route = sample_route() | {"transform_profile": "python_eval"}
        with self.assertRaises(RuntimeErrorInfo) as ctx:
            routes.validate_route_schema(route)
        self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")

    def test_validate_route_schema_accepts_allowlisted_transform_profiles(self) -> None:
        route = sample_route() | {
            "transform_profile": "openai_chat_input_text",
            "response_profile": "top_level_output_text",
        }
        validated = routes.validate_route_schema(route)
        self.assertEqual(validated["transform_profile"], "openai_chat_input_text")
        self.assertEqual(validated["response_profile"], "top_level_output_text")

        developer_to_system = routes.validate_route_schema(
            sample_route() | {"transform_profile": "openai_chat_developer_to_system"}
        )
        self.assertEqual(
            developer_to_system["transform_profile"],
            "openai_chat_developer_to_system",
        )

    def test_validate_route_schema_accepts_bounded_check_max_tokens(self) -> None:
        validated = routes.validate_route_schema(sample_route() | {"check_max_tokens": 256})
        self.assertEqual(validated["check_max_tokens"], 256)

        for invalid_value in (0, -1, 32769, True, "256"):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(RuntimeErrorInfo) as ctx:
                    routes.validate_route_schema(
                        sample_route() | {"check_max_tokens": invalid_value}
                    )
                self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")

    def test_validate_route_schema_accepts_deepseek_thinking_policy_only_for_deepseek(self) -> None:
        deepseek = sample_route() | {
            "provider": "deepseek",
            "upstream_model": "deepseek-v4-pro",
            "thinking": {"type": "enabled", "reasoning_effort": "max"},
        }
        validated = routes.validate_route_schema(deepseek)
        self.assertEqual(validated["thinking"]["reasoning_effort"], "max")

        disabled = routes.validate_route_schema(
            deepseek | {"thinking": {"type": "disabled"}}
        )
        self.assertEqual(disabled["thinking"]["type"], "disabled")

        with self.assertRaises(RuntimeErrorInfo):
            routes.validate_route_schema(
                sample_route() | {"thinking": {"type": "enabled", "reasoning_effort": "max"}}
            )
        with self.assertRaises(RuntimeErrorInfo):
            routes.validate_route_schema(
                deepseek | {"thinking": {"type": "enabled", "reasoning_effort": "medium"}}
            )
        with self.assertRaises(RuntimeErrorInfo):
            routes.validate_route_schema(
                deepseek | {"thinking": {"type": "disabled", "reasoning_effort": "max"}}
            )

    def test_build_check_request_uses_shared_completion_budget_across_profiles(self) -> None:
        request_payload, _metadata = transforms.build_check_request(
            sample_route(),
            user_prompt="ping",
        )
        self.assertEqual(
            request_payload["max_tokens"], transforms.CHECK_REQUEST_COMPLETION_BUDGET
        )

        override_payload, _metadata = transforms.build_check_request(
            sample_route() | {"check_max_tokens": 256},
            user_prompt="ping",
        )
        self.assertEqual(override_payload["max_tokens"], 256)

        developer_payload, _metadata = transforms.build_check_request(
            sample_route() | {"transform_profile": "openai_chat_system_to_developer"},
            user_prompt="ping",
        )
        self.assertEqual(
            developer_payload["max_tokens"], transforms.CHECK_REQUEST_COMPLETION_BUDGET
        )

        developer_to_system_payload, _metadata = transforms.build_check_request(
            sample_route() | {"transform_profile": "openai_chat_developer_to_system"},
            user_prompt="ping",
        )
        self.assertEqual(
            developer_to_system_payload["max_tokens"],
            transforms.CHECK_REQUEST_COMPLETION_BUDGET,
        )

        input_text_payload, _metadata = transforms.build_check_request(
            sample_route() | {"transform_profile": "openai_chat_input_text"},
            user_prompt="ping",
        )
        self.assertEqual(
            input_text_payload["max_output_tokens"],
            transforms.CHECK_REQUEST_COMPLETION_BUDGET,
        )

        deepseek_payload, _metadata = transforms.build_check_request(
            sample_route()
            | {
                "provider": "deepseek",
                "upstream_model": "deepseek-v4-pro",
                "thinking": {"type": "enabled", "reasoning_effort": "max"},
            },
            user_prompt="ping",
        )
        self.assertEqual(
            deepseek_payload["thinking"],
            {"type": "enabled", "reasoning_effort": "max"},
        )
        self.assertEqual(
            deepseek_payload["max_tokens"],
            transforms.THINKING_CHECK_REQUEST_COMPLETION_BUDGET,
        )
        deepseek_developer_payload, _metadata = transforms.build_check_request(
            sample_route()
            | {
                "provider": "deepseek",
                "upstream_model": "deepseek-v4-pro",
                "transform_profile": "openai_chat_developer_to_system",
                "thinking": {"type": "enabled", "reasoning_effort": "high"},
            },
            user_prompt="ping",
        )
        self.assertEqual(
            deepseek_developer_payload["max_tokens"],
            transforms.THINKING_CHECK_REQUEST_COMPLETION_BUDGET,
        )
        deepseek_disabled_payload, disabled_metadata = transforms.build_check_request(
            sample_route()
            | {
                "provider": "deepseek",
                "upstream_model": "deepseek-v4-flash",
                "thinking": {"type": "disabled"},
            },
            user_prompt="ping",
        )
        self.assertEqual(deepseek_disabled_payload["thinking"], {"type": "disabled"})
        self.assertEqual(
            deepseek_disabled_payload["max_tokens"],
            transforms.CHECK_REQUEST_COMPLETION_BUDGET,
        )
        self.assertTrue(disabled_metadata["api_parameter_sent"])

    def test_extract_check_response_rejects_null_chat_message_content(self) -> None:
        payload = {"choices": [{"message": {"content": None}}]}
        with self.assertRaises(RuntimeErrorInfo) as ctx:
            transforms.extract_check_response(sample_route(), payload)
        self.assertEqual(ctx.exception.machine_error_code, "invalid_upstream_response")

    def test_paths_from_env_uses_isolated_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "external-models"
            old = dict(os.environ)
            try:
                os.environ["WBP_EXTERNAL_MODELS_DIR"] = str(root)
                os.environ["WBP_EXTERNAL_MODELS_SECRETS"] = str(root / "custom-secrets.env")
                os.environ["WBP_EXTERNAL_MODELS_EVIDENCE"] = str(root / "artifacts")
                os.environ["WBP_EXTERNAL_MODELS_ROUTES_LOCK"] = str(root / "custom-routes.lock")
                os.environ["WBP_EXTERNAL_MODELS_STATE_LOCK"] = str(root / "custom-state.lock")
                paths = ExternalModelsPaths.from_env()
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(paths.root_dir, root.resolve())
            self.assertEqual(paths.routes_file, (root / "routes.json").resolve())
            self.assertEqual(paths.state_file, (root / "state.json").resolve())
            self.assertEqual(paths.secrets_file, (root / "custom-secrets.env").resolve())
            self.assertEqual(paths.evidence_dir, (root / "artifacts").resolve())
            self.assertEqual(paths.routes_lock, (root / "custom-routes.lock").resolve())
            self.assertEqual(paths.state_lock, (root / "custom-state.lock").resolve())

    def test_paths_from_env_falls_back_to_managed_dir_external_models(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed_dir = Path(temp_dir) / "managed"
            expected_root = (managed_dir / "external-models").resolve()
            old = dict(os.environ)
            try:
                os.environ.pop("WBP_EXTERNAL_MODELS_DIR", None)
                os.environ["WBP_MANAGED_DIR"] = str(managed_dir)
                paths = ExternalModelsPaths.from_env()
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(paths.root_dir, expected_root)
            self.assertEqual(paths.routes_file, (expected_root / "routes.json").resolve())
            self.assertEqual(paths.state_file, (expected_root / "state.json").resolve())
            self.assertEqual(paths.secrets_file, (expected_root / "secrets.env").resolve())

    def test_ensure_installed_layout_creates_neutral_files_and_secrets_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = ExternalModelsPaths.from_root(Path(temp_dir) / "external-models")
            ensure_installed_layout(paths)
            self.assertTrue(paths.root_dir.is_dir())
            self.assertTrue(paths.evidence_dir.is_dir())
            self.assertEqual(
                json.loads(paths.routes_file.read_text(encoding="utf-8"))["routes"], []
            )
            state = json.loads(paths.state_file.read_text(encoding="utf-8"))
            self.assertEqual(state["adapter"]["state"], "stopped")
            self.assertFalse(state["local_auth"]["token_present"])
            self.assertEqual(paths.secrets_file.read_text(encoding="utf-8"), "")
            self.assertEqual(paths.secrets_file.stat().st_mode & 0o777, 0o600)

    def test_atomic_write_json_uses_unique_state_store_temp_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "state.json"
            temp_names: list[str] = []
            real_mkstemp = state_mod.state_store.tempfile.mkstemp

            def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
                fd, name = real_mkstemp(*args, **kwargs)
                temp_names.append(Path(name).name)
                return fd, name

            with mock.patch.object(
                state_mod.state_store.tempfile, "mkstemp", recording_mkstemp
            ):
                state_mod.atomic_write_json(target, {"schema_version": 2, "value": "a"})
                state_mod.atomic_write_json(target, {"schema_version": 2, "value": "b"})

            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8"))["value"], "b"
            )
            self.assertEqual(len(temp_names), 2)
            self.assertEqual(len(set(temp_names)), 2)
            self.assertTrue(all(name.startswith(".wbp-tmp-") for name in temp_names))
            self.assertTrue(all(name.endswith(".state.json.tmp") for name in temp_names))
            self.assertNotIn(".state.json", temp_names)
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_atomic_write_json_fsyncs_file_and_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "routes.json"
            real_open = state_mod.state_store.os.open
            real_fsync = state_mod.state_store.os.fsync
            fsync_paths: list[str] = []
            fsync_kinds: list[str] = []

            def recording_open(
                path: object, flags: int, *args: object, **kwargs: object
            ) -> int:
                fd = real_open(path, flags, *args, **kwargs)
                if Path(path) == root:
                    fsync_paths.append(str(path))
                return fd

            def recording_fsync(fd: int) -> None:
                mode = os.fstat(fd).st_mode & 0o170000
                fsync_kinds.append("directory" if mode == 0o040000 else "file")
                real_fsync(fd)

            with (
                mock.patch.object(state_mod.state_store.os, "open", recording_open),
                mock.patch.object(state_mod.state_store.os, "fsync", recording_fsync),
            ):
                state_mod.atomic_write_json(target, {"schema_version": 1, "routes": []})

            self.assertIn(str(root), fsync_paths)
            self.assertIn("file", fsync_kinds)
            self.assertIn("directory", fsync_kinds)

    def test_write_state_file_rejects_incomplete_payload_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "state.json"
            target.write_text(
                json.dumps(contracts.default_state_payload(), ensure_ascii=True, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            before = target.read_text(encoding="utf-8")

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                state_mod.write_state_file(
                    target,
                    {
                        "schema_version": contracts.STATE_SCHEMA_VERSION,
                        "policy": {},
                    },
                )

            self.assertEqual(ctx.exception.machine_error_code, errors.SCHEMA_INVALID)
            self.assertEqual(target.read_text(encoding="utf-8"), before)
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_write_state_file_rejects_invalid_observed_route_patch_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "state.json"
            target.write_text(
                json.dumps(contracts.default_state_payload(), ensure_ascii=True, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            before = target.read_text(encoding="utf-8")
            payload = contracts.default_state_payload()
            payload["routes"] = {"wbp-deepseek-v3": {"unexpected": "value"}}

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                state_mod.write_state_file(target, payload)

            self.assertEqual(ctx.exception.machine_error_code, errors.SCHEMA_INVALID)
            self.assertEqual(target.read_text(encoding="utf-8"), before)
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_write_routes_file_rejects_invalid_route_payload_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "routes.json"
            target.write_text(
                json.dumps(contracts.default_routes_payload(), ensure_ascii=True, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            before = target.read_text(encoding="utf-8")
            payload = contracts.default_routes_payload()
            payload["routes"] = [sample_route() | {"auth": {}}]

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                routes.write_routes_file(target, payload)

            self.assertEqual(ctx.exception.machine_error_code, errors.SCHEMA_INVALID)
            self.assertEqual(target.read_text(encoding="utf-8"), before)
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_write_evidence_file_rejects_hash_drift_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "evidence.json"
            payload = sample_evidence_payload(network_dependent=False)
            payload["artifact_sha256"] = "0" * 64

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                state_mod.write_evidence_file(target, payload)

            self.assertEqual(ctx.exception.machine_error_code, errors.SCHEMA_INVALID)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_write_evidence_file_rejects_missing_network_scope_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "evidence.json"
            payload = sample_evidence_payload(network_dependent=True)
            del payload["verification_scope"]

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                state_mod.write_evidence_file(target, payload)

            self.assertEqual(ctx.exception.machine_error_code, errors.SCHEMA_INVALID)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_write_evidence_file_rejects_invalid_fallback_chain_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "evidence.json"
            payload = sample_evidence_payload(network_dependent=True)
            result = payload["result"]
            assert isinstance(result, dict)
            result["fallback_chain"] = ["wbp-deepseek-v3", 7]
            canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
            payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                state_mod.write_evidence_file(target, payload)

            self.assertEqual(ctx.exception.machine_error_code, errors.SCHEMA_INVALID)
            self.assertFalse(target.exists())
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_check_command_fails_closed_when_evidence_write_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            managed_dir = root / "managed"
            paths = ExternalModelsPaths.from_root(managed_dir / "external-models")
            ensure_installed_layout(paths)
            routes.write_routes_file(
                paths.routes_file,
                contracts.default_routes_payload() | {"routes": [sample_route()]},
            )
            state_mod.write_secrets_file_text(
                paths.secrets_file,
                "OPENROUTER_API_KEY=test-key\n",
            )
            args = mock.Mock(external_models_command="check", route="wbp-deepseek-v3")
            response = mock.Mock(
                status_code=200,
                payload={
                    "choices": [
                        {"message": {"role": "assistant", "content": "pong"}}
                    ]
                },
                latency_ms=12,
            )
            evidence_error = RuntimeErrorInfo(
                "Evidence validator rejected payload.",
                machine_error_code=errors.SCHEMA_INVALID,
                operator_action="stop",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(paths.root_dir),
                },
                clear=False,
            ), mock.patch.object(
                validate_mod,
                "request_json",
                return_value=response,
            ), mock.patch.object(
                validate_mod,
                "write_evidence_file",
                side_effect=evidence_error,
            ):
                packet = run_external_models_command(args)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], errors.SCHEMA_INVALID)
            self.assertEqual(packet["effect"], "mutate")
            self.assertEqual(
                [str(Path(item).resolve()) for item in packet["changed_files"]],
                [str(paths.state_file.resolve())],
            )
            self.assertEqual(packet["data"]["verification_scope"], "route_provider_only")
            self.assertEqual(packet["data"]["route_state"], "limited")
            self.assertFalse(packet["data"]["bridge_or_file_bridge_used"])
            self.assertEqual(
                json.loads(paths.state_file.read_text(encoding="utf-8"))["routes"][
                    "wbp-deepseek-v3"
                ]["availability_state"],
                "limited",
            )
            self.assertEqual(list(paths.evidence_dir.glob("*")), [])

    def test_routes_validate_command_fails_closed_when_evidence_write_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            managed_dir = root / "managed"
            paths = ExternalModelsPaths.from_root(managed_dir / "external-models")
            ensure_installed_layout(paths)
            routes.write_routes_file(
                paths.routes_file,
                contracts.default_routes_payload() | {"routes": [sample_route()]},
            )
            state_mod.write_secrets_file_text(
                paths.secrets_file,
                "OPENROUTER_API_KEY=test-key\n",
            )
            args = mock.Mock(
                external_models_command="routes",
                routes_command="validate",
                route="wbp-deepseek-v3",
            )
            evidence_error = RuntimeErrorInfo(
                "Evidence validator rejected payload.",
                machine_error_code=errors.SCHEMA_INVALID,
                operator_action="stop",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(paths.root_dir),
                },
                clear=False,
            ), mock.patch.object(
                validate_mod,
                "_handle_models_probe",
                return_value=({"available_models_count": 1, "latency_ms": 7}, 1),
            ), mock.patch.object(
                validate_mod,
                "write_evidence_file",
                side_effect=evidence_error,
            ):
                packet = run_external_models_command(args)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], errors.SCHEMA_INVALID)
            self.assertEqual(packet["effect"], "mutate")
            self.assertEqual(
                [str(Path(item).resolve()) for item in packet["changed_files"]],
                [str(paths.state_file.resolve())],
            )
            self.assertEqual(packet["data"]["verification_scope"], "route_provider_only")
            self.assertEqual(packet["data"]["route_state"], "limited")
            self.assertEqual(
                json.loads(paths.state_file.read_text(encoding="utf-8"))["routes"][
                    "wbp-deepseek-v3"
                ]["availability_state"],
                "limited",
            )
            self.assertEqual(list(paths.evidence_dir.glob("*")), [])

    def test_secret_write_sets_mode_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "secrets.env"
            real_replace = state_mod.state_store.os.replace
            published_modes: list[int] = []

            def recording_replace(src: object, dst: object) -> None:
                published_modes.append(Path(src).stat().st_mode & 0o777)
                real_replace(src, dst)

            with mock.patch.object(
                state_mod.state_store.os, "replace", recording_replace
            ):
                state_mod.write_secrets_file_text(
                    target, "OPENROUTER_API_KEY=test-key\n"
                )

            self.assertEqual(published_modes, [0o600])
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                target.read_text(encoding="utf-8"), "OPENROUTER_API_KEY=test-key\n"
            )

    def test_failed_secret_write_cleans_temp_and_keeps_original(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "secrets.env"
            target.write_text("OPENROUTER_API_KEY=old\n", encoding="utf-8")
            os.chmod(target, 0o600)
            created_temp: list[Path] = []
            real_mkstemp = state_mod.state_store.tempfile.mkstemp

            def recording_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
                fd, name = real_mkstemp(*args, **kwargs)
                created_temp.append(Path(name))
                return fd, name

            def failing_replace(src: object, dst: object) -> None:
                raise OSError("replace failed")

            with (
                mock.patch.object(
                    state_mod.state_store.tempfile, "mkstemp", recording_mkstemp
                ),
                mock.patch.object(state_mod.state_store.os, "replace", failing_replace),
            ):
                with self.assertRaises(RuntimeErrorInfo) as ctx:
                    state_mod.write_secrets_file_text(
                        target, "OPENROUTER_API_KEY=new\n"
                    )

            self.assertEqual(ctx.exception.machine_error_code, errors.STATE_WRITE_FAILED)
            self.assertEqual(
                target.read_text(encoding="utf-8"), "OPENROUTER_API_KEY=old\n"
            )
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertTrue(created_temp)
            self.assertTrue(all(not path.exists() for path in created_temp))
            self.assertEqual(list(root.glob(".wbp-tmp-*")), [])

    def test_build_external_models_payload_keeps_domain_next_action_generic_operator(
        self,
    ) -> None:
        packet = contracts.build_external_models_payload(
            ok=False,
            human_message="owner action required",
            machine_error_code="credential_source_missing",
            data={"route_id": "wbp-deepseek-v3"},
            next_action="api_route_connect",
            severity="critical",
            liveness="warming_up",
        )

        self.assertEqual(packet["operator_action"], "user_action")
        self.assertEqual(packet["next_action"], "api_route_connect")
        self.assertEqual(packet["severity"], "critical")
        self.assertEqual(packet["liveness"], "warming_up")
        self.assertEqual(
            packets.classify_command_operator_action(packet["operator_action"]),
            "core",
        )
        self.assertEqual(
            packets.classify_command_next_action(packet["next_action"]),
            "legacy",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_credential_admit_packets_declare_mutate_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed_dir = Path(temp_dir) / "managed"
            root = managed_dir / "external-models"
            args = mock.Mock(
                external_models_command="credentials",
                credentials_command="admit",
                provider="deepseek",
                source="owner-env",
            )
            with mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(root),
                    "DEEPSEEK_API_KEY": "",
                },
                clear=False,
            ):
                missing = run_external_models_command(args)
            self.assertEqual(missing["status"], "error")
            self.assertEqual(
                missing["machine_error_code"],
                errors.EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING,
            )
            self.assertEqual(missing["effect"], "mutate")
            self.assertEqual(missing["changed_files"], [])

            fixture_value = "fixture-deepseek-value"
            with mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(root),
                    "DEEPSEEK_API_KEY": fixture_value,
                },
                clear=False,
            ):
                admitted = run_external_models_command(args)
            self.assertEqual(admitted["status"], "ok")
            self.assertEqual(admitted["machine_error_code"], "OK")
            self.assertEqual(admitted["effect"], "mutate")
            self.assertNotIn(fixture_value, json.dumps(admitted, ensure_ascii=True))

    def test_external_models_effect_classifier_covers_documented_commands(self) -> None:
        cases = [
            (mock.Mock(external_models_command="start"), "mutate"),
            (mock.Mock(external_models_command="stop"), "mutate"),
            (mock.Mock(external_models_command="status"), "read"),
            (mock.Mock(external_models_command="models"), "read"),
            (mock.Mock(external_models_command="check"), "mutate"),
            (mock.Mock(external_models_command="live-format-check"), "probe"),
            (mock.Mock(external_models_command="routes", routes_command="list"), "read"),
            (
                mock.Mock(external_models_command="routes", routes_command="validate"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="routes", routes_command="add"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="routes", routes_command="update"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="routes", routes_command="remove"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="routes", routes_command="enable"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="routes", routes_command="disable"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="credentials", credentials_command="admit"),
                "mutate",
            ),
            (
                mock.Mock(external_models_command="credentials", credentials_command="status"),
                "read",
            ),
            (
                mock.Mock(external_models_command="profile", profile_command="codex-desktop"),
                "read",
            ),
            (
                mock.Mock(external_models_command="evidence", evidence_command="capture"),
                "mutate",
            ),
        ]
        for args, expected_effect in cases:
            with self.subTest(command=args.external_models_command):
                self.assertEqual(
                    external_models_mod._command_effect_for_args(args),
                    expected_effect,
                )

    def test_external_models_runtime_errors_preserve_documented_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            managed_dir = Path(temp_dir) / "managed"
            root = managed_dir / "external-models"
            cases = [
                (
                    mock.Mock(external_models_command="check", route="missing-route"),
                    "mutate",
                ),
                (
                    mock.Mock(
                        external_models_command="routes",
                        routes_command="validate",
                        route="missing-route",
                    ),
                    "mutate",
                ),
                (
                    mock.Mock(
                        external_models_command="live-format-check",
                        route="missing-route",
                        prompt="ping",
                        expected_text="pong",
                    ),
                    "probe",
                ),
                (
                    mock.Mock(
                        external_models_command="evidence",
                        evidence_command="capture",
                        route="missing-route",
                    ),
                    "mutate",
                ),
            ]
            with mock.patch.dict(
                os.environ,
                {
                    "WBP_MANAGED_DIR": str(managed_dir),
                    "WBP_EXTERNAL_MODELS_DIR": str(root),
                },
                clear=False,
            ):
                for args, expected_effect in cases:
                    with self.subTest(command=args.external_models_command):
                        packet = run_external_models_command(args)
                        self.assertEqual(packet["status"], "error")
                        self.assertEqual(packet["machine_error_code"], errors.ROUTE_NOT_FOUND)
                        self.assertEqual(packet["effect"], expected_effect)
                        self.assertEqual(packet["changed_files"], [])

    def test_capture_local_evidence_writes_non_self_referential_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence_dir = Path(temp_dir) / "evidence"
            route = sample_route()
            packet = contracts.build_external_models_payload(
                ok=True,
                human_message="ok",
                machine_error_code="OK",
                data={"route_id": route["route_id"]},
            )
            path = capture_local_evidence(
                evidence_dir=evidence_dir,
                route=route,
                packet=packet,
            )
            self.assertTrue(path.resolve().is_relative_to(evidence_dir.resolve()))
            self.assertTrue(path.name.startswith("wbp-deepseek-v3-"))
            payload = json.loads(path.read_text(encoding="utf-8"))
            artifact_sha = payload.pop("artifact_sha256")
            canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode(
                "utf-8"
            )
            self.assertEqual(artifact_sha, hashlib.sha256(canonical).hexdigest())

    def test_capture_local_evidence_blocks_unvalidated_traversal_route_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence_dir = root / "evidence"
            route = sample_route() | {"route_id": "wbp-/../../escape"}
            packet = contracts.build_external_models_payload(
                ok=False,
                human_message="blocked",
                machine_error_code="schema_invalid",
            )

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                capture_local_evidence(
                    evidence_dir=evidence_dir,
                    route=route,
                    packet=packet,
                )

            self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")
            self.assertFalse((root / "escape").exists())
            self.assertEqual(list(evidence_dir.glob("*")) if evidence_dir.exists() else [], [])

    def test_network_evidence_blocks_unvalidated_traversal_route_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = ExternalModelsPaths.from_root(root / "external-models")
            route = sample_route() | {"route_id": "wbp-/../../escape"}
            result = {
                "status": "error",
                "machine_error_code": "schema_invalid",
            }

            with self.assertRaises(RuntimeErrorInfo) as ctx:
                validate_mod._write_network_evidence(
                    paths=paths,
                    route=route,
                    command_context="external-models check",
                    result=result,
                )

            self.assertEqual(ctx.exception.machine_error_code, "schema_invalid")
            self.assertFalse((paths.root_dir / "escape").exists())
            self.assertEqual(
                list(paths.evidence_dir.glob("*")) if paths.evidence_dir.exists() else [],
                [],
            )

    def test_load_state_file_returns_default_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = load_state_file(Path(temp_dir) / "missing.json")
            self.assertEqual(state["policy"]["paid_route_default"], "blocked")

    def test_load_state_file_migrates_v1_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "policy": {
                            "paid_routes_enabled": True,
                            "paid_route_allowlist": ["wbp-paid"],
                            "paid_route_default": "allow",
                        },
                        "routes": {"wbp-a": {"availability_state": "unverified"}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            state = load_state_file(state_path)
            self.assertEqual(state["schema_version"], 2)
            self.assertEqual(state["adapter"]["state"], "stopped")
            self.assertTrue(state["policy"]["paid_routes_enabled"])
            self.assertIn("wbp-a", state["routes"])

    def test_allocate_synthetic_port_skips_reserved_ports(self) -> None:
        ports = [8318, 8320, 45678]

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def bind(self, addr):
                return None

            def getsockname(self):
                return ("127.0.0.1", ports.pop(0))

        with mock.patch("wild_boar_proxy.external_models.lifecycle.socket.socket", return_value=FakeSocket()):
            self.assertEqual(lifecycle.allocate_synthetic_port(), 45678)


class ZeroTestSelectionGuardTests(unittest.TestCase):
    def test_module_contains_real_tests(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            ExternalModelContractTests
        )
        self.assertGreaterEqual(suite.countTestCases(), 7)
