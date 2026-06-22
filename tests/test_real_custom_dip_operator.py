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
from wild_boar_proxy.command_effects import EFFECT_MUTATE, EFFECT_PROBE, EFFECT_READ
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


def _runner_work_packet(
    *,
    ok: bool = True,
    changed_files: list[str] | None = None,
    **overrides: object,
) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_repeatable_real_custom_dip_proof_runner",
        "status": "ok" if ok else "error",
        "machine_error_code": "OK" if ok else "WBP_REAL_CUSTOM_DIP_PROOF_RUNNER_WBP_DIP_FAILED",
        "effect": "mutate",
        "changed_files": changed_files
        or ["/tmp/wbp/operator/real-custom-dip-proof-runner.packet.json"],
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
    packet.update(overrides)
    return packet


def _preflight_ready_packet() -> dict[str, object]:
    return {
        "packet_kind": operator.REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "effect": "probe",
        "changed_files": [],
        "preflight_ready": True,
        "selected_alias": "DIP",
        "selected_alias_present": True,
        "blocking_reasons": [],
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "product_ready": False,
    }


def _preflight_blocked_packet() -> dict[str, object]:
    packet = _preflight_ready_packet()
    packet.update(
        {
            "status": "error",
            "machine_error_code": operator.REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED,
            "preflight_ready": False,
            "blocking_reasons": ["user_prompt_submit_hook_not_ready"],
        }
    )
    return packet


def _operator_work_packet(
    root: Path,
    run_index: int,
    *,
    ok: bool = True,
    evidence_root: Path | None = None,
    **overrides: object,
) -> dict[str, object]:
    evidence_dir = evidence_root or root / f"run-{run_index:02d}"
    evidence_file = evidence_dir / "real-custom-dip-proof-runner.packet.json"
    _write_json(evidence_file, {"ok": ok, "run_index": run_index})
    return _runner_work_packet(
        ok=ok,
        changed_files=[str(evidence_file)],
        packet_kind=operator.REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND,
        **overrides,
    )


def _acceptance_packet(root: Path, *, run_count: int = 5) -> dict[str, object]:
    return operator.build_real_custom_dip_operator_acceptance_packet(
        prompt_text=PROMPT,
        requested_runs=run_count,
        preflight_packet=_preflight_ready_packet(),
        work_packets=[
            _operator_work_packet(root / "acceptance-evidence", run_index)
            for run_index in range(1, run_count + 1)
        ],
        secret_values=[PROMPT, ROUTE_ID],
    )


def _write_acceptance_packet_file(path: Path, packet: dict[str, object]) -> Path:
    _write_json(path, packet)
    return path


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

    def test_acceptance_passes_five_mocked_runs_with_distinct_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            work_packets = [
                _operator_work_packet(root / "evidence", run_index)
                for run_index in range(1, 6)
            ]
            with mock.patch.object(
                operator,
                "build_real_custom_dip_operator_preflight_packet",
                return_value=_preflight_ready_packet(),
            ) as preflight_mock, mock.patch.object(
                operator,
                "run_real_custom_dip_operator_work_command",
                side_effect=work_packets,
            ) as work_mock:
                packet = operator.run_real_custom_dip_operator_acceptance_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    runs=5,
                    proof_dir=str(root / "acceptance-proof"),
                    codex_cwd=str(Path(__file__).resolve().parents[1]),
                )

            self.assertTrue(preflight_mock.called)
            self.assertEqual(work_mock.call_count, 5)
            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(
                packet["packet_kind"],
                operator.REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_PACKET_KIND,
            )
            self.assertTrue(packet["acceptance_passed"])
            self.assertEqual(packet["acceptance_run_count_requested"], 5)
            self.assertEqual(packet["acceptance_run_count_completed"], 5)
            self.assertTrue(packet["all_runs_work_mode_proven"])
            self.assertTrue(packet["all_runs_api_lane_called"])
            self.assertTrue(packet["all_runs_delivery_proven"])
            self.assertTrue(packet["all_runs_no_fallback"])
            self.assertTrue(packet["all_runs_no_local_imitation"])
            self.assertTrue(packet["all_runs_no_native_codex_subagent_as_dip"])
            self.assertTrue(packet["all_runs_no_admission_mint"])
            self.assertTrue(packet["evidence_roots_distinct"])
            self.assertFalse(packet["proof_mode_admission_proven"])
            self.assertFalse(packet["repeatable_real_custom_dip_proof_proven"])
            self.assertFalse(packet["real_custom_codex_hook_origin_dip_proof_proven"])
            self.assertFalse(packet["product_ready"])
            self.assertFalse(packet["custom_codex_ui_visibility_proven"])
            self.assertFalse(packet["fallback_used"])
            self.assertFalse(packet["local_imitation_used"])
            self.assertFalse(packet["native_codex_subagent_used_as_dip"])
            self.assertTrue(packet["acceptance_is_not_dip_work_prerequisite"])
            self.assertTrue(packet["acceptance_packet_file_written"])
            acceptance_packet_file = (
                root
                / "acceptance-proof"
                / "real-custom-dip-operator-acceptance.packet.json"
            )
            self.assertTrue(acceptance_packet_file.is_file())
            self.assertIn(str(acceptance_packet_file), packet["changed_files"])
            self.assertEqual(len(packet["evidence_root_digests"]), 5)
            self.assertEqual(len(packet["run_summaries"]), 5)
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(PROMPT, serialized)
            self.assertNotIn(ROUTE_ID, serialized)
            self.assertFalse(packet["evidence_root_paths_recorded"])
            for summary in packet["run_summaries"]:
                self.assertFalse(summary["evidence_root_path_recorded"])
            self.assertEqual(
                packets.inspect_command_packet_semantics(
                    packet,
                    secret_values=[PROMPT, ROUTE_ID],
                ),
                [],
            )

    def test_acceptance_rejects_out_of_range_runs_without_preflight_or_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            with mock.patch.object(
                operator,
                "build_real_custom_dip_operator_preflight_packet",
            ) as preflight_mock, mock.patch.object(
                operator,
                "run_real_custom_dip_operator_work_command",
            ) as work_mock:
                packet = operator.run_real_custom_dip_operator_acceptance_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    runs=1,
                )

            self.assertFalse(preflight_mock.called)
            self.assertFalse(work_mock.called)
            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_BLOCKED,
            )
            self.assertFalse(packet["acceptance_passed"])
            self.assertFalse(packet["acceptance_run_count_valid"])
            self.assertIn("acceptance_run_count_out_of_range", packet["blocking_reasons"])
            self.assertEqual(packet["acceptance_run_count_completed"], 0)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_acceptance_preflight_blocked_skips_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            with mock.patch.object(
                operator,
                "build_real_custom_dip_operator_preflight_packet",
                return_value=_preflight_blocked_packet(),
            ) as preflight_mock, mock.patch.object(
                operator,
                "run_real_custom_dip_operator_work_command",
            ) as work_mock:
                packet = operator.run_real_custom_dip_operator_acceptance_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    runs=2,
                )

            self.assertTrue(preflight_mock.called)
            self.assertFalse(work_mock.called)
            self.assertEqual(packet["status"], "error")
            self.assertFalse(packet["acceptance_passed"])
            self.assertFalse(packet["preflight_ready"])
            self.assertIn("preflight_not_ready", packet["blocking_reasons"])
            self.assertEqual(packet["acceptance_run_count_completed"], 0)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_acceptance_stops_on_first_failed_work_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            work_packets = [
                _operator_work_packet(root / "evidence", 1),
                _operator_work_packet(root / "evidence", 2),
                _operator_work_packet(root / "evidence", 3, ok=False),
                _operator_work_packet(root / "evidence", 4),
            ]
            with mock.patch.object(
                operator,
                "build_real_custom_dip_operator_preflight_packet",
                return_value=_preflight_ready_packet(),
            ), mock.patch.object(
                operator,
                "run_real_custom_dip_operator_work_command",
                side_effect=work_packets,
            ) as work_mock:
                packet = operator.run_real_custom_dip_operator_acceptance_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    runs=5,
                )

            self.assertEqual(work_mock.call_count, 3)
            self.assertEqual(packet["status"], "error")
            self.assertFalse(packet["acceptance_passed"])
            self.assertEqual(packet["acceptance_run_count_completed"], 3)
            self.assertEqual(packet["acceptance_stopped_on_run"], 3)
            self.assertIn("acceptance_run_count_not_completed", packet["blocking_reasons"])
            self.assertIn("run_3_api_lane_not_called", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_acceptance_blocks_admission_mint_overclaim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            work_packet = _operator_work_packet(
                root / "evidence",
                1,
                proof_mode_admission_proven=True,
            )
            with mock.patch.object(
                operator,
                "build_real_custom_dip_operator_preflight_packet",
                return_value=_preflight_ready_packet(),
            ), mock.patch.object(
                operator,
                "run_real_custom_dip_operator_work_command",
                return_value=work_packet,
            ) as work_mock:
                packet = operator.run_real_custom_dip_operator_acceptance_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    runs=2,
                )

            self.assertEqual(work_mock.call_count, 1)
            self.assertEqual(packet["status"], "error")
            self.assertFalse(packet["acceptance_passed"])
            self.assertFalse(packet["all_runs_no_admission_mint"])
            self.assertFalse(packet["proof_mode_admission_proven"])
            self.assertIn(
                "run_1_proof_mode_admission_minted",
                packet["blocking_reasons"],
            )
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_acceptance_blocks_duplicate_evidence_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shared_root = root / "shared-evidence"
            packet = operator.build_real_custom_dip_operator_acceptance_packet(
                prompt_text=PROMPT,
                requested_runs=2,
                preflight_packet=_preflight_ready_packet(),
                work_packets=[
                    _operator_work_packet(root / "unused", 1, evidence_root=shared_root),
                    _operator_work_packet(root / "unused", 2, evidence_root=shared_root),
                ],
                secret_values=[PROMPT, ROUTE_ID],
            )

            self.assertEqual(packet["status"], "error")
            self.assertFalse(packet["acceptance_passed"])
            self.assertFalse(packet["evidence_roots_distinct"])
            self.assertIn("evidence_roots_not_distinct", packet["blocking_reasons"])
            self.assertFalse(packet["evidence_root_paths_recorded"])
            for summary in packet["run_summaries"]:
                self.assertFalse(summary["evidence_root_path_recorded"])
            self.assertEqual(
                packets.inspect_command_packet_semantics(
                    packet,
                    secret_values=[PROMPT, ROUTE_ID],
                ),
                [],
            )

    def test_acceptance_blocks_prompt_or_route_secret_in_nested_work_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = operator.build_real_custom_dip_operator_acceptance_packet(
                prompt_text=PROMPT,
                requested_runs=2,
                preflight_packet=_preflight_ready_packet(),
                work_packets=[
                    _operator_work_packet(root / "evidence", 1, leaked_prompt=PROMPT),
                    _operator_work_packet(root / "evidence", 2, leaked_route=ROUTE_ID),
                ],
                secret_values=[PROMPT, ROUTE_ID],
            )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET,
            )
            self.assertFalse(packet["acceptance_passed"])
            self.assertIn("operator_acceptance_packet_secret_leak", packet["blocking_reasons"])
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(PROMPT, serialized)
            self.assertNotIn(ROUTE_ID, serialized)
            self.assertEqual(
                packets.inspect_command_packet_semantics(
                    packet,
                    secret_values=[PROMPT, ROUTE_ID],
                ),
                [],
            )

    def test_status_reads_acceptance_proof_file_as_ready_without_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            proof_file = _write_acceptance_packet_file(
                root / "real-custom-dip-operator-acceptance.packet.json",
                _acceptance_packet(root),
            )
            with mock.patch.object(
                operator,
                "run_real_custom_dip_operator_work_command",
            ) as work_mock, mock.patch.object(
                operator,
                "run_real_custom_dip_operator_acceptance_command",
            ) as acceptance_mock:
                packet = operator.run_dip_operator_status_command(
                    paths=paths,
                    proof_file=str(proof_file),
                    max_age_seconds=3600,
                )

            self.assertFalse(work_mock.called)
            self.assertFalse(acceptance_mock.called)
            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(
                packet["packet_kind"],
                operator.DIP_OPERATOR_READINESS_PACKET_KIND,
            )
            self.assertTrue(packet["dip_operator_ready"])
            self.assertEqual(packet["operator_status"], "ready")
            self.assertTrue(packet["last_acceptance_packet_found"])
            self.assertTrue(packet["last_acceptance_packet_valid"])
            self.assertTrue(packet["last_acceptance_passed"])
            self.assertEqual(packet["last_acceptance_run_count"], 5)
            self.assertEqual(packet["required_acceptance_run_count"], 5)
            self.assertTrue(packet["last_acceptance_api_lane_called"])
            self.assertTrue(packet["last_acceptance_delivery_proven"])
            self.assertTrue(packet["last_acceptance_evidence_roots_distinct"])
            self.assertTrue(packet["last_acceptance_evidence_files_present"])
            self.assertTrue(packet["last_acceptance_fresh"])
            self.assertFalse(packet["status_command_dispatches"])
            self.assertFalse(packet["status_command_runs_acceptance"])
            self.assertFalse(packet["status_command_reads_audit_history"])
            self.assertFalse(packet["product_ready"])
            self.assertFalse(packet["custom_codex_ui_visibility_proven"])
            self.assertFalse(packet["fallback_used"])
            self.assertFalse(packet["local_imitation_used"])
            self.assertFalse(packet["native_codex_subagent_used_as_dip"])
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(PROMPT, serialized)
            self.assertNotIn(ROUTE_ID, serialized)
            self.assertNotIn(str(proof_file), serialized)
            self.assertEqual(
                packets.inspect_command_packet_semantics(
                    packet,
                    secret_values=[PROMPT, ROUTE_ID],
                ),
                [],
            )

    def test_status_finds_latest_managed_acceptance_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            old_packet = _acceptance_packet(root / "old")
            new_packet = _acceptance_packet(root / "new")
            old_file = _write_acceptance_packet_file(
                paths.managed_dir
                / "direct-provider-positive-proof"
                / "operator-dip-acceptance-old"
                / "real-custom-dip-operator-acceptance.packet.json",
                old_packet,
            )
            new_file = _write_acceptance_packet_file(
                paths.managed_dir
                / "direct-provider-positive-proof"
                / "operator-dip-acceptance-new"
                / "real-custom-dip-operator-acceptance.packet.json",
                new_packet,
            )
            os.utime(old_file, (old_file.stat().st_atime - 100, old_file.stat().st_mtime - 100))

            packet = operator.run_dip_operator_status_command(
                paths=paths,
                max_age_seconds=3600,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["dip_operator_ready"])
            self.assertEqual(
                packet["last_acceptance_packet_path_digest"],
                operator._sha256_text(str(new_file.expanduser().resolve(strict=False))),
            )

    def test_status_missing_acceptance_packet_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            packet = operator.run_dip_operator_status_command(paths=paths)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.DIP_OPERATOR_READINESS_PROOF_MISSING,
            )
            self.assertFalse(packet["dip_operator_ready"])
            self.assertEqual(packet["operator_status"], "proof_missing")
            self.assertIn("acceptance_packet_missing", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_status_latest_search_ignores_disappearing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            proof_file = _write_acceptance_packet_file(
                paths.managed_dir
                / "direct-provider-positive-proof"
                / "operator-dip-acceptance-vanishing"
                / "real-custom-dip-operator-acceptance.packet.json",
                _acceptance_packet(root),
            )
            real_stat = Path.stat

            def fake_stat(path: Path, *args: object, **kwargs: object) -> os.stat_result:
                if path == proof_file:
                    raise FileNotFoundError(str(path))
                return real_stat(path, *args, **kwargs)

            with mock.patch.object(Path, "stat", fake_stat):
                packet = operator.run_dip_operator_status_command(paths=paths)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                operator.DIP_OPERATOR_READINESS_PROOF_MISSING,
            )
            self.assertFalse(packet["dip_operator_ready"])
            self.assertIn("acceptance_packet_missing", packet["blocking_reasons"])

    def test_status_invalid_json_and_wrong_kind_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            invalid_file = root / "invalid.json"
            invalid_file.write_text("{not-json\n", encoding="utf-8")

            invalid_packet = operator.run_dip_operator_status_command(
                paths=paths,
                proof_file=str(invalid_file),
            )

            self.assertEqual(invalid_packet["status"], "error")
            self.assertFalse(invalid_packet["dip_operator_ready"])
            self.assertIn(
                "acceptance_packet_invalid_json",
                invalid_packet["blocking_reasons"],
            )

            wrong_kind_file = _write_acceptance_packet_file(
                root / "wrong-kind.json",
                {
                    "status": "ok",
                    "exit_code": 0,
                    "human_message": "wrong kind",
                    "machine_error_code": "OK",
                    "changed_files": [],
                    "next_action": "none",
                    "liveness": "not_applicable",
                    "severity": "recoverable",
                    "operator_action": "none",
                    "effect": "read",
                    "packet_kind": "wrong_kind",
                },
            )
            wrong_kind_packet = operator.run_dip_operator_status_command(
                paths=paths,
                proof_file=str(wrong_kind_file),
            )

            self.assertEqual(wrong_kind_packet["status"], "error")
            self.assertFalse(wrong_kind_packet["dip_operator_ready"])
            self.assertIn(
                "acceptance_packet_wrong_kind",
                wrong_kind_packet["blocking_reasons"],
            )

    def test_status_stale_acceptance_is_historical_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            proof_file = _write_acceptance_packet_file(
                root / "stale.json",
                _acceptance_packet(root),
            )
            old_time = proof_file.stat().st_mtime - 100
            os.utime(proof_file, (old_time, old_time))

            packet = operator.run_dip_operator_status_command(
                paths=paths,
                proof_file=str(proof_file),
                max_age_seconds=1,
            )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], operator.DIP_OPERATOR_READINESS_STALE)
            self.assertFalse(packet["dip_operator_ready"])
            self.assertEqual(packet["operator_status"], "stale")
            self.assertTrue(packet["historical_acceptance_passed"])
            self.assertFalse(packet["last_acceptance_fresh"])
            self.assertIn("acceptance_packet_stale", packet["blocking_reasons"])

    def test_status_blocks_missing_evidence_and_unsafe_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            missing_evidence_packet = _acceptance_packet(root / "missing")
            first_changed_file = Path(missing_evidence_packet["changed_files"][0])
            first_changed_file.unlink()
            missing_file = _write_acceptance_packet_file(
                root / "missing-evidence.json",
                missing_evidence_packet,
            )

            packet = operator.run_dip_operator_status_command(
                paths=paths,
                proof_file=str(missing_file),
            )

            self.assertEqual(packet["status"], "error")
            self.assertFalse(packet["dip_operator_ready"])
            self.assertIn(
                "acceptance_evidence_files_missing",
                packet["blocking_reasons"],
            )

            unsafe_packet = _acceptance_packet(root / "unsafe")
            unsafe_packet["product_ready"] = True
            unsafe_packet["raw_prompt_recorded"] = True
            unsafe_packet["leaked_prompt"] = PROMPT
            unsafe_file = _write_acceptance_packet_file(root / "unsafe.json", unsafe_packet)

            unsafe_status = operator.run_dip_operator_status_command(
                paths=paths,
                proof_file=str(unsafe_file),
            )

            self.assertEqual(unsafe_status["status"], "error")
            self.assertEqual(
                unsafe_status["machine_error_code"],
                operator.DIP_OPERATOR_READINESS_UNSAFE,
            )
            self.assertFalse(unsafe_status["dip_operator_ready"])
            self.assertEqual(unsafe_status["operator_status"], "unsafe")
            self.assertIn("product_ready_claimed", unsafe_status["blocking_reasons"])
            self.assertIn(
                "unsafe_secret_or_raw_backend_claim",
                unsafe_status["blocking_reasons"],
            )

    def test_cli_effect_and_dispatch_for_dip_commands(self) -> None:
        parser = cli_mod.build_parser()
        preflight_args = parser.parse_args(
            ["dip", "preflight", "--prompt", PROMPT, "--json"]
        )
        work_args = parser.parse_args(["dip", "work", "--prompt", PROMPT, "--json"])
        acceptance_args = parser.parse_args(
            ["dip", "acceptance", "--runs", "2", "--prompt", PROMPT, "--json"]
        )
        acceptance_default_args = parser.parse_args(
            ["dip", "acceptance", "--prompt", PROMPT, "--json"]
        )
        status_args = parser.parse_args(["dip", "status", "--json"])
        self.assertEqual(cli_mod.command_effect_from_args(preflight_args), EFFECT_PROBE)
        self.assertEqual(cli_mod.command_effect_from_args(work_args), EFFECT_MUTATE)
        self.assertEqual(cli_mod.command_effect_from_args(acceptance_args), EFFECT_MUTATE)
        self.assertEqual(cli_mod.command_effect_from_args(status_args), EFFECT_READ)
        self.assertEqual(
            acceptance_default_args.runs,
            operator.ACCEPTANCE_RUNS_DEFAULT,
        )

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

        with mock.patch.object(
            cli_mod,
            "run_real_custom_dip_operator_acceptance_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as acceptance_mock:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(
                    [
                        "dip",
                        "acceptance",
                        "--runs",
                        "2",
                        "--prompt",
                        PROMPT,
                        "--json",
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertTrue(acceptance_mock.called)
        self.assertEqual(acceptance_mock.call_args.kwargs["prompt_text"], PROMPT)
        self.assertEqual(acceptance_mock.call_args.kwargs["runs"], 2)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ok")

        with mock.patch.object(
            cli_mod,
            "run_dip_operator_status_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as status_mock:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(
                    [
                        "dip",
                        "status",
                        "--proof-file",
                        "/tmp/proof.json",
                        "--max-age-seconds",
                        "42",
                        "--json",
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertTrue(status_mock.called)
        self.assertEqual(status_mock.call_args.kwargs["proof_file"], "/tmp/proof.json")
        self.assertEqual(status_mock.call_args.kwargs["max_age_seconds"], 42)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "ok")


if __name__ == "__main__":
    unittest.main()
