# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from wild_boar_proxy.core import packets
from wild_boar_proxy.external_models import contracts, errors, routes, run_external_models_command
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
        self.assertTrue(disabled_metadata["api_parameter_sent"])

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

    def test_build_external_models_payload_keeps_domain_actions_passthrough(self) -> None:
        packet = contracts.build_external_models_payload(
            ok=False,
            human_message="owner action required",
            machine_error_code="credential_source_missing",
            data={"route_id": "wbp-deepseek-v3"},
            next_action="api_route_connect",
            severity="critical",
            liveness="warming_up",
        )

        self.assertEqual(packet["operator_action"], "api_route_connect")
        self.assertEqual(packet["next_action"], "api_route_connect")
        self.assertEqual(packet["severity"], "critical")
        self.assertEqual(packet["liveness"], "warming_up")
        self.assertEqual(
            packets.classify_command_operator_action(packet["operator_action"]),
            "legacy",
        )
        self.assertEqual(
            packets.classify_command_next_action(packet["next_action"]),
            "legacy",
        )

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
            import hashlib

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
