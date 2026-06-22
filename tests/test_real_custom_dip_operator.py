# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_custom_dip_operator as operator
from wild_boar_proxy.command_effects import EFFECT_MUTATE, EFFECT_PROBE
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.runtime import RuntimePaths
from wild_boar_proxy.user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    HOOK_READINESS_PACKET_KIND,
)


PROMPT = "Codex, дай задачу DIP: operator command surface smoke."
AGENT_2_PROMPT = "Codex, дай задачу Agent 2: operator command surface smoke."
ROUTE_ID = "wbp-deepseek-secret-route"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _paths(root: Path, *, context: dict[str, object] | None = None) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    profile.mkdir(parents=True, exist_ok=True)
    managed.mkdir(parents=True, exist_ok=True)
    _write_json(
        profile / "wbp-agent-runtime-context.json",
        _runtime_context() if context is None else context,
    )
    with mock.patch.dict(
        os.environ,
        {
            "WBP_PROFILE_DIR": str(profile),
            "WBP_MANAGED_DIR": str(managed),
            "WBP_CONFIG_TOML": str(profile / "config.toml"),
        },
    ):
        return RuntimePaths.from_env()


def _runtime_context(*, allowed_routes: list[str] | None = None) -> dict[str, object]:
    allowed_routes = [ROUTE_ID] if allowed_routes is None else allowed_routes
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "context_truth_source": "server_current_agent_bindings_state",
        "agent_bindings_status": "ok",
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "aliases": ["Codex", "Agent 1"],
                "lane": "primary_chatgpt",
                "enabled": True,
                "model_id": "gpt-5.4",
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "aliases": ["DIP", "Agent 2", "Worker"],
                "lane": "api_route",
                "enabled": True,
                "route_id": ROUTE_ID,
            },
        ],
        "alias_to_agent_id": {
            "Codex": "codex",
            "Agent 1": "codex",
            "DIP": "dip",
            "Agent 2": "dip",
            "Worker": "dip",
        },
        "agent_id_to_route": {"dip": ROUTE_ID},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": allowed_routes,
        "forbidden_stale_route_ids": ["wbp-stale-route"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _codex_bin(root: Path) -> Path:
    path = root / "bin" / "codex"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _readiness(ok: bool = True) -> dict[str, object]:
    return {
        "packet_kind": HOOK_READINESS_PACKET_KIND,
        "status": "ok" if ok else "error",
        "machine_error_code": HOOK_CONFIG_OK if ok else "HOOK_CONFIG_NOT_READY",
        "effect": "probe",
        "changed_files": [],
        "hook_enabled": ok,
        "hook_trusted": ok,
        "hook_config_digest_bound": ok,
        "blocking_reasons": [] if ok else ["hook_not_trusted"],
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "product_ready": False,
    }


def _runner_work_packet(*, ok: bool = True) -> dict[str, object]:
    return {
        "packet_kind": "wbp_repeatable_real_custom_dip_proof_runner",
        "status": "ok" if ok else "error",
        "machine_error_code": "OK" if ok else "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_WBP_DIP_FAILED",
        "effect": "mutate",
        "changed_files": ["/tmp/wbp/operator/real-custom-dip-proof-runner.packet.json"],
        "operator_command_mode": "work",
        "work_mode_proven": ok,
        "single_work_run_proven": ok,
        "work_mode_cannot_mint_admission_proof": True,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "real_custom_codex_hook_origin_dip_proof_proven": False,
        "two_runs_proven": False,
        "required_run_count": 1,
        "run_count": 1 if ok else 0,
        "custom_codex_flow_proven": ok,
        "user_prompt_submit_hook_ran": ok,
        "hook_prompt_digest_bound": ok,
        "hook_runtime_context_digest_bound": ok,
        "delegate_to_dip_proven": ok,
        "api_lane_called": ok,
        "route_bound_dispatch_proven": ok,
        "live_result_available": ok,
        "direct_provider_auth_proven": ok,
        "codex_working_flow_delivery_proven": ok,
        "approved_delivery_surface_proven": ok,
        "assistant_response_bound_to_handoff_digest": ok,
        "custom_codex_ui_visibility_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "blocking_reasons": [] if ok else ["run_1_wbp_dip_process_failed"],
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
    }


class RealCustomDipOperatorTests(unittest.TestCase):
    def test_preflight_ready_is_probe_only_and_leak_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            codex_bin = _codex_bin(root)
            with mock.patch.object(
                operator,
                "build_user_prompt_submit_readiness_packet",
                return_value=_readiness(),
            ):
                packet = operator.run_real_custom_dip_operator_preflight_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(codex_bin),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(Path(__file__).resolve().parents[1]),
                )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(
                packet["packet_kind"],
                operator.REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
            )
            self.assertTrue(packet["preflight_ready"])
            self.assertTrue(packet["natural_intent_passed"])
            self.assertEqual(packet["selected_alias"], "DIP")
            self.assertTrue(packet["route_id_allowed"])
            self.assertTrue(packet["user_prompt_submit_hook_ready"])
            self.assertFalse(packet["work_runner_called"])
            self.assertFalse(packet["api_lane_called"])
            self.assertFalse(packet["dispatch_proven"])
            self.assertFalse(packet["work_mode_proven"])
            self.assertFalse(packet["proof_mode_admission_proven"])
            self.assertFalse(packet["product_ready"])
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(PROMPT, serialized)
            self.assertNotIn(ROUTE_ID, serialized)
            self.assertFalse(packet_contains_text(packet, PROMPT))
            self.assertFalse(packet_contains_text(packet, ROUTE_ID))
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_preflight_blocks_route_outside_allowlist_without_dispatch_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root, context=_runtime_context(allowed_routes=["wbp-other-route"]))
            codex_bin = _codex_bin(root)
            with mock.patch.object(
                operator,
                "build_user_prompt_submit_readiness_packet",
                return_value=_readiness(),
            ):
                packet = operator.run_real_custom_dip_operator_preflight_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(codex_bin),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(Path(__file__).resolve().parents[1]),
                )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED,
            )
            self.assertFalse(packet["preflight_ready"])
            self.assertFalse(packet["route_id_allowed"])
            self.assertIn("route_not_allowed_by_runtime_context", packet["blocking_reasons"])
            self.assertFalse(packet["api_lane_called"])
            self.assertFalse(packet["work_mode_proven"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_preflight_blocks_existing_unwritable_proof_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            codex_bin = _codex_bin(root)
            proof_dir = root / "proof"
            proof_dir.mkdir()
            real_access = operator.os.access

            def fake_access(path: object, mode: int) -> bool:
                if Path(path) == proof_dir and mode == (operator.os.W_OK | operator.os.X_OK):
                    return False
                return real_access(path, mode)

            with mock.patch.object(
                operator,
                "build_user_prompt_submit_readiness_packet",
                return_value=_readiness(),
            ), mock.patch.object(operator.os, "access", side_effect=fake_access):
                packet = operator.run_real_custom_dip_operator_preflight_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(codex_bin),
                    proof_dir=str(proof_dir),
                    codex_cwd=str(Path(__file__).resolve().parents[1]),
                )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED,
            )
            self.assertFalse(packet["preflight_ready"])
            self.assertFalse(packet["proof_output_writable"])
            self.assertIn("proof_output_not_writable", packet["blocking_reasons"])
            self.assertFalse(packet["api_lane_called"])
            self.assertFalse(packet["work_runner_called"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_work_blocks_before_runner_when_preflight_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root, context={})
            codex_bin = _codex_bin(root)
            with mock.patch.object(
                operator,
                "build_user_prompt_submit_readiness_packet",
                return_value=_readiness(),
            ), mock.patch.object(
                operator,
                "run_real_custom_dip_proof_runner_command",
            ) as runner_mock:
                packet = operator.run_real_custom_dip_operator_work_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(codex_bin),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(Path(__file__).resolve().parents[1]),
                )

            self.assertFalse(runner_mock.called)
            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED,
            )
            self.assertTrue(packet["preflight_checked"])
            self.assertFalse(packet["preflight_ready"])
            self.assertFalse(packet["runner_called"])
            self.assertFalse(packet["api_lane_called"])
            self.assertFalse(packet["work_mode_proven"])
            self.assertIn("preflight_not_ready", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_work_calls_runner_with_parser_selected_alias_and_wraps_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            codex_bin = _codex_bin(root)
            with mock.patch.object(
                operator,
                "build_user_prompt_submit_readiness_packet",
                return_value=_readiness(),
            ), mock.patch.object(
                operator,
                "run_real_custom_dip_proof_runner_command",
                return_value=_runner_work_packet(),
            ) as runner_mock:
                packet = operator.run_real_custom_dip_operator_work_command(
                    paths=paths,
                    prompt_text=AGENT_2_PROMPT,
                    codex_bin=str(codex_bin),
                    proof_dir=str(root / "proof"),
                    codex_cwd=str(Path(__file__).resolve().parents[1]),
                    timeout_seconds=7,
                )

            self.assertTrue(runner_mock.called)
            self.assertEqual(runner_mock.call_args.kwargs["run_mode"], "work")
            self.assertEqual(runner_mock.call_args.kwargs["expected_alias"], "Agent 2")
            self.assertEqual(runner_mock.call_args.kwargs["timeout_seconds"], 7)
            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertTrue(packet["work_ready"])
            self.assertTrue(packet["runner_called"])
            self.assertTrue(packet["work_mode_proven"])
            self.assertTrue(packet["single_work_run_proven"])
            self.assertTrue(packet["api_lane_called"])
            self.assertEqual(packet["selected_alias"], "Agent 2")
            self.assertEqual(packet["runner_changed_files_count"], 1)
            self.assertFalse(packet["proof_mode_admission_proven"])
            self.assertFalse(packet["repeatable_real_custom_dip_proof_proven"])
            self.assertFalse(packet["product_ready"])
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(AGENT_2_PROMPT, serialized)
            self.assertNotIn(ROUTE_ID, serialized)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_work_wrapper_does_not_accept_proof_mode_runner_packet_as_work(self) -> None:
        runner_packet = _runner_work_packet()
        runner_packet["operator_command_mode"] = "proof"
        runner_packet["proof_mode_admission_proven"] = True
        preflight = {
            "packet_kind": operator.REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
            "status": "ok",
            "machine_error_code": "OK",
            "preflight_ready": True,
            "selected_alias": "DIP",
            "selected_alias_present": True,
            "blocking_reasons": [],
        }

        packet = operator.build_real_custom_dip_operator_work_packet(
            prompt_text=PROMPT,
            preflight_packet=preflight,
            runner_packet=runner_packet,
            secret_values=[PROMPT, ROUTE_ID],
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            operator.REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED,
        )
        self.assertTrue(packet["runner_called"])
        self.assertFalse(packet["work_mode_proven"])
        self.assertFalse(packet["proof_mode_admission_proven"])
        self.assertFalse(packet["repeatable_real_custom_dip_proof_proven"])
        self.assertIn("runner_work_not_proven", packet["blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_and_dispatch_for_dip_commands(self) -> None:
        parser = cli_mod.build_parser()
        preflight_args = parser.parse_args(
            ["dip", "preflight", "--prompt", PROMPT, "--json"]
        )
        work_args = parser.parse_args(["dip", "work", "--prompt", PROMPT, "--json"])
        self.assertEqual(cli_mod.command_effect_from_args(preflight_args), EFFECT_PROBE)
        self.assertEqual(cli_mod.command_effect_from_args(work_args), EFFECT_MUTATE)

        with mock.patch.object(
            cli_mod,
            "run_real_custom_dip_operator_work_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as mocked:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(["dip", "work", "--prompt", PROMPT, "--json"])

        self.assertEqual(rc, 0)
        self.assertTrue(mocked.called)
        self.assertEqual(mocked.call_args.kwargs["prompt_text"], PROMPT)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ok")

        with mock.patch.object(
            cli_mod,
            "run_real_custom_dip_operator_preflight_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as preflight_mock:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(["dip", "preflight", "--prompt", PROMPT, "--json"])

        self.assertEqual(rc, 0)
        self.assertTrue(preflight_mock.called)
        self.assertEqual(preflight_mock.call_args.kwargs["prompt_text"], PROMPT)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ok")


if __name__ == "__main__":
    unittest.main()
