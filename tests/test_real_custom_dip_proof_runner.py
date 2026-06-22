# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_custom_dip_proof_runner as runner
from wild_boar_proxy import real_user_prompt_submit_ledger_proof as ledger_proof
from wild_boar_proxy import wbp_dip_hook_origin_proof
from wild_boar_proxy.codex_working_flow_delivery_proof import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
    WBP_DIP_HOOK_ORIGIN_LIVE_PROVIDER_DELIVERY_SOURCE_PACKET_KIND,
)
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.runtime import RuntimePaths
from wild_boar_proxy.user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    HOOK_READINESS_PACKET_KIND,
    hook_ledger_path,
)
from wild_boar_proxy.wbp_dip_tool import WBP_DIP_TOOL_OK, WBP_DIP_TOOL_PACKET_KIND


PROMPT = "Codex, дай задачу DIP: repeatable hook-origin dispatch proof."
ROUTE_ID = "wbp-deepseek-chat-secret-route"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    profile.mkdir(parents=True, exist_ok=True)
    managed.mkdir(parents=True, exist_ok=True)
    context = {
        "allowed_api_route_ids": [ROUTE_ID],
        "slots": [{"slot": "agent_2", "alias": "DIP", "route_id": ROUTE_ID}],
    }
    _write_json(profile / "wbp-agent-runtime-context.json", context)
    with mock.patch.dict(
        "os.environ",
        {
            "WBP_PROFILE_DIR": str(profile),
            "WBP_MANAGED_DIR": str(managed),
            "WBP_CONFIG_TOML": str(profile / "config.toml"),
        },
    ):
        return RuntimePaths.from_env()


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
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "product_ready": False,
        "blocking_reasons": [] if ok else ["hook_not_trusted"],
    }


def _ledger_packet(prompt: str) -> dict[str, object]:
    digest = _sha256(prompt)
    return {
        "packet_kind": ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_PROOF_PACKET_KIND,
        "status": "ok",
        "machine_error_code": ledger_proof.REAL_USER_PROMPT_SUBMIT_LEDGER_OK,
        "effect": "probe",
        "changed_files": [],
        "real_user_prompt_submit_ledger_proven": True,
        "custom_codex_flow_proven": True,
        "custom_codex_origin_proven": True,
        "user_prompt_submit_hook_ran": True,
        "hook_ledger_written": True,
        "hook_prompt_digest_bound": True,
        "hook_runtime_context_digest_bound": True,
        "thread_or_turn_digest_bound": True,
        "hook_config_digest_bound": True,
        "hook_event_transport_stdin": True,
        "prompt_digest": digest,
        "hook_prompt_digest": digest,
        "blocking_reasons": [],
        "custom_codex_ui_visibility_proven": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }


def _wbp_dip_packet(prompt: str, *, ok: bool = True) -> dict[str, object]:
    live_text = "live provider result"
    return {
        "packet_kind": WBP_DIP_TOOL_PACKET_KIND,
        "status": "ok" if ok else "error",
        "machine_error_code": WBP_DIP_TOOL_OK if ok else "WBP_DIP_TOOL_FAILED",
        "effect": "mutate",
        "changed_files": ["proof/wbp-dip-tool.packet.json"],
        "expected_alias": "DIP",
        "task_sha256": _sha256(prompt),
        "delegate_to_dip_proven": ok,
        "api_lane_called": ok,
        "route_bound_dispatch_proven": ok,
        "live_result_required": True,
        "live_result_available": ok,
        "live_result_provider_called": ok,
        "live_result_route_allowed": ok,
        "live_result_text_sha256": _sha256(live_text) if ok else "",
        "live_result_text_length": len(live_text) if ok else 0,
        "live_result_text_recorded": ok,
        "live_result_route_id_recorded": False,
        "live_result_bridge_or_file_bridge_used": False,
        "live_result_runtime_context_bridge_used": False,
        "live_result_runtime_context_file_bridge_used": False,
        "direct_provider_auth_proven": ok,
        "direct_provider_response_observed": ok,
        "provider_auth_ok": ok,
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": ok,
        "blocking_reasons": [] if ok else ["delegate_to_dip_not_proven"],
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "live_result_raw_backend_details_exposed": False,
        "live_result_secret_value_exposed": False,
        "command_argv_recorded": False,
        "codex_stdout_recorded": False,
        "codex_stderr_recorded": False,
    }


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["fake"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _working_flow_source_packet(prompt: str) -> dict[str, object]:
    return {
        "packet_kind": WBP_DIP_HOOK_ORIGIN_LIVE_PROVIDER_DELIVERY_SOURCE_PACKET_KIND,
        "status": "ok",
        "machine_error_code": "OK",
        "effect": "probe",
        "changed_files": [],
        "prompt_digest": _sha256(prompt),
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "codex_working_flow_delivery_proven": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
    }


def _working_flow_delivery_packet(*, ok: bool = True) -> dict[str, object]:
    return {
        "packet_kind": CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        "status": "ok" if ok else "error",
        "machine_error_code": "OK" if ok else "WBP_CODEX_WORKING_FLOW_DELIVERY_NOT_BOUND",
        "effect": "probe",
        "changed_files": [],
        "codex_working_flow_delivery_proven": ok,
        "approved_delivery_surface_proven": ok,
        "assistant_response_bound_to_handoff_digest": ok,
        "working_flow_delivery_surface_kind": "mcp_tool_response",
        "working_flow_handoff_payload_digest": _sha256("working-flow-handoff"),
        "blocking_reasons": [] if ok else ["assistant_response_bound_to_handoff_digest_not_true"],
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
    }


class RealCustomDipProofRunnerTests(unittest.TestCase):
    def _run(
        self,
        root: Path,
        *,
        readiness_ok: bool = True,
        stale_ledger: bool = False,
        wbp_dip_ok: bool = True,
        wbp_dip_bridge_backed: bool = False,
        delivery_ok: bool = True,
        join_patch: object = None,
        probe_codex_app_server: bool = False,
    ) -> dict[str, object]:
        paths = _paths(root)
        codex_bin = root / "codex"
        codex_bin.write_text("#!/bin/sh\n", encoding="utf-8")
        codex_bin.chmod(0o755)
        (root / "tools").mkdir(exist_ok=True)
        wbp_dip = root / "tools" / "wbp_dip"
        wbp_dip.write_text("#!/bin/sh\n", encoding="utf-8")
        wbp_dip.chmod(0o755)
        ledger_file = hook_ledger_path(paths)
        counter = {"codex": 0}
        captured_readiness_kwargs: list[dict[str, object]] = []
        captured_ledger_kwargs: list[dict[str, object]] = []
        self._last_readiness_kwargs = captured_readiness_kwargs
        self._last_ledger_kwargs = captured_ledger_kwargs

        def fake_readiness(**kwargs: object) -> dict[str, object]:
            captured_readiness_kwargs.append(dict(kwargs))
            return _readiness(readiness_ok)

        def fake_custom_codex_prompt(*, prompt_text: str, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            counter["codex"] += 1
            if not stale_ledger:
                _write_json(
                    ledger_file,
                    {
                        "kind": "ledger",
                        "counter": counter["codex"],
                        "prompt_digest": _sha256(prompt_text),
                    },
                )
            completed = _completed(stdout="")
            completed.wbp_terminal_output_sha256 = _sha256("terminal")  # type: ignore[attr-defined]
            completed.wbp_terminal_output_bytes = 8  # type: ignore[attr-defined]
            completed.wbp_elapsed_ms = 10  # type: ignore[attr-defined]
            return completed

        def fake_subprocess_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            if argv and Path(argv[0]).resolve() == wbp_dip.resolve():
                env = _kwargs.get("env")
                self.assertIsInstance(env, dict)
                self.assertEqual(
                    env.get("WBP_EXTERNAL_MODELS_DIR"),
                    str(paths.managed_dir / "external-models"),
                )
                proof_dir = Path(argv[argv.index("--proof-dir") + 1])
                packet = _wbp_dip_packet(str(argv[-1]), ok=wbp_dip_ok)
                if wbp_dip_bridge_backed:
                    packet.update(
                        {
                            "live_result_bridge_or_file_bridge_used": True,
                            "live_result_runtime_context_file_bridge_used": True,
                            "direct_provider_auth_proven": False,
                            "direct_provider_response_observed": False,
                            "provider_auth_ok": False,
                            "positive_provider_proof_gate_satisfied": False,
                        }
                    )
                if wbp_dip_ok:
                    _write_json(proof_dir / "wbp-dip-tool.packet.json", packet)
                return _completed(
                    stdout=json.dumps(packet, ensure_ascii=True),
                    returncode=0 if wbp_dip_ok else 1,
                )
            raise AssertionError(f"unexpected subprocess argv: {argv}")

        def fake_ledger_proof(*, prompt_text: object, **_kwargs: object) -> dict[str, object]:
            captured_ledger_kwargs.append(dict(_kwargs))
            return _ledger_packet(str(prompt_text))

        def fake_delivery(**kwargs: object) -> dict[str, object]:
            run_dir = kwargs["run_dir"]
            prompt_text = str(kwargs["prompt_text"])
            self.assertIsInstance(run_dir, Path)
            source_file = run_dir / runner.WORKING_FLOW_SOURCE_FILE_NAME
            delivery_file = run_dir / runner.WORKING_FLOW_DELIVERY_FILE_NAME
            source = _working_flow_source_packet(prompt_text)
            delivery = _working_flow_delivery_packet(ok=delivery_ok)
            _write_json(source_file, source)
            _write_json(delivery_file, delivery)
            return {
                "working_flow_source_packet": source,
                "working_flow_delivery_packet": delivery,
                "working_flow_delivery_process": {},
                "artifacts": [
                    runner._packet_file_summary(  # noqa: SLF001
                        runner.WORKING_FLOW_SOURCE_FILE_NAME,
                        source_file,
                        source,
                    ),
                    runner._packet_file_summary(  # noqa: SLF001
                        runner.WORKING_FLOW_DELIVERY_FILE_NAME,
                        delivery_file,
                        delivery,
                    ),
                ],
                "run_blocking_reasons": []
                if delivery_ok
                else ["assistant_response_bound_to_handoff_digest_not_true"],
            }

        patches = [
            mock.patch.object(runner, "build_user_prompt_submit_readiness_packet", side_effect=fake_readiness),
            mock.patch.object(runner, "run_real_user_prompt_submit_ledger_proof_command", side_effect=fake_ledger_proof),
            mock.patch.object(runner, "_run_custom_codex_prompt", side_effect=fake_custom_codex_prompt),
            mock.patch.object(runner.subprocess, "run", side_effect=fake_subprocess_run),
            mock.patch.object(runner, "_run_working_flow_delivery", side_effect=fake_delivery),
        ]
        if join_patch is not None:
            patches.append(
                mock.patch.object(
                    runner,
                    "run_wbp_dip_hook_origin_proof_command",
                    side_effect=join_patch,
                )
            )
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            if len(patches) == 5:
                return runner.run_real_custom_dip_proof_runner_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    codex_bin=str(codex_bin),
                    codex_cwd=str(root),
                    proof_dir=str(root / "proof"),
                    timeout_seconds=3,
                    probe_codex_app_server=probe_codex_app_server,
                )
            if len(patches) == 6:
                with patches[5]:
                    return runner.run_real_custom_dip_proof_runner_command(
                        paths=paths,
                        prompt_text=PROMPT,
                        codex_bin=str(codex_bin),
                        codex_cwd=str(root),
                        proof_dir=str(root / "proof"),
                        timeout_seconds=3,
                        probe_codex_app_server=probe_codex_app_server,
                    )
            return runner.run_real_custom_dip_proof_runner_command(
                paths=paths,
                prompt_text=PROMPT,
                codex_bin=str(codex_bin),
                codex_cwd=str(root),
                proof_dir=str(root / "proof"),
                timeout_seconds=3,
                probe_codex_app_server=probe_codex_app_server,
            )

    def test_positive_requires_two_fresh_runs_and_file_backed_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packet = self._run(root)

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(packet["packet_kind"], runner.REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND)
            self.assertTrue(packet["repeatable_real_custom_dip_proof_proven"])
            self.assertTrue(packet["real_custom_codex_hook_origin_dip_proof_proven"])
            self.assertTrue(packet["two_runs_proven"])
            self.assertEqual(packet["run_count"], 2)
            self.assertTrue(packet["fresh_hook_ledgers_proven"])
            self.assertTrue(packet["prompt_digests_distinct"])
            self.assertTrue(packet["source_packet_hashes_present"])
            self.assertTrue(packet["custom_codex_flow_proven"])
            self.assertTrue(packet["user_prompt_submit_hook_ran"])
            self.assertTrue(packet["hook_prompt_digest_bound"])
            self.assertTrue(packet["hook_runtime_context_digest_bound"])
            self.assertTrue(packet["delegate_to_dip_proven"])
            self.assertTrue(packet["api_lane_called"])
            self.assertTrue(packet["route_bound_dispatch_proven"])
            self.assertTrue(packet["live_result_available"])
            self.assertTrue(packet["direct_provider_auth_proven"])
            self.assertTrue(packet["direct_provider_response_observed"])
            self.assertTrue(packet["positive_provider_proof_gate_satisfied"])
            self.assertTrue(packet["codex_working_flow_delivery_proven"])
            self.assertTrue(packet["approved_delivery_surface_proven"])
            self.assertTrue(packet["assistant_response_bound_to_handoff_digest"])
            self.assertFalse(packet["live_result_bridge_or_file_bridge_used"])
            self.assertTrue(packet["first_run_custom_codex_flow_proven"])
            self.assertTrue(packet["first_run_user_prompt_submit_hook_ran"])
            self.assertTrue(packet["first_run_api_lane_called"])
            self.assertTrue(packet["first_run_route_bound_dispatch_proven"])
            self.assertTrue(packet["first_run_live_result_available"])
            self.assertTrue(packet["first_run_direct_provider_auth_proven"])
            self.assertTrue(packet["first_run_direct_provider_response_observed"])
            self.assertTrue(packet["first_run_positive_provider_proof_gate_satisfied"])
            self.assertTrue(packet["first_run_codex_working_flow_delivery_proven"])
            self.assertTrue(packet["first_run_approved_delivery_surface_proven"])
            self.assertTrue(packet["first_run_assistant_response_bound_to_handoff_digest"])
            self.assertFalse(packet["first_run_live_result_bridge_or_file_bridge_used"])
            self.assertEqual(packet["first_run_wbp_dip_machine_error_code"], "OK")
            self.assertTrue(packet["partial_first_run_diagnostics_recorded"])
            self.assertTrue(packet["partial_first_run_diagnostics_are_not_product_ready"])
            self.assertFalse(packet["custom_codex_ui_visibility_proven"])
            self.assertFalse(packet["product_ready"])
            self.assertFalse(packet["fallback_used"])
            self.assertFalse(packet["local_imitation_used"])
            self.assertFalse(packet["native_codex_subagent_used_as_dip"])
            self.assertTrue((root / "proof" / runner.REAL_CUSTOM_DIP_PROOF_RUNNER_MANIFEST_FILE_NAME).is_file())
            self.assertTrue((root / "proof" / runner.REAL_CUSTOM_DIP_PROOF_RUNNER_FILE_NAME).is_file())
            serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
            self.assertNotIn(PROMPT, serialized)
            self.assertNotIn(ROUTE_ID, serialized)
            self.assertFalse(packet_contains_text(packet, PROMPT))
            self.assertFalse(packet_contains_text(packet, ROUTE_ID))
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_delivery_failure_blocks_full_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), delivery_ok=False)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                runner.REAL_CUSTOM_DIP_PROOF_RUNNER_DELIVERY_FAILED,
            )
            self.assertIn(
                "run_1_assistant_response_bound_to_handoff_digest_not_true",
                packet["blocking_reasons"],
            )
            self.assertFalse(packet["repeatable_real_custom_dip_proof_proven"])
            self.assertFalse(packet["codex_working_flow_delivery_proven"])
            self.assertTrue(packet["first_run_api_lane_called"])
            self.assertFalse(packet["first_run_codex_working_flow_delivery_proven"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_bridge_backed_result_blocks_repeatable_direct_provider_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), wbp_dip_bridge_backed=True)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                runner.REAL_CUSTOM_DIP_PROOF_RUNNER_JOIN_FAILED,
            )
            self.assertIn(
                "run_1_direct_provider_auth_proven_not_true",
                packet["blocking_reasons"],
            )
            self.assertIn(
                "run_1_positive_provider_proof_gate_satisfied_not_true",
                packet["blocking_reasons"],
            )
            self.assertFalse(packet["repeatable_real_custom_dip_proof_proven"])
            self.assertFalse(packet["positive_provider_proof_gate_satisfied"])
            self.assertTrue(packet["first_run_live_result_bridge_or_file_bridge_used"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_readiness_failure_blocks_before_runtime_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), readiness_ok=False)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                runner.REAL_CUSTOM_DIP_PROOF_RUNNER_READINESS_FAILED,
            )
            self.assertIn("hook_readiness_not_ok", packet["blocking_reasons"])
            self.assertEqual(packet["run_count"], 0)
            self.assertFalse(packet["api_lane_called"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_repeated_same_base_prompt_still_proves_fresh_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = self._run(root)
            second = self._run(root)

            self.assertEqual(first["status"], "ok")
            self.assertEqual(second["status"], "ok")
            self.assertTrue(first["fresh_hook_ledgers_proven"])
            self.assertTrue(second["fresh_hook_ledgers_proven"])
            self.assertNotEqual(
                first["effective_prompt_digests"],
                second["effective_prompt_digests"],
            )
            self.assertEqual(packets.inspect_command_packet_semantics(second), [])

    def test_probe_mode_does_not_substitute_local_hook_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), probe_codex_app_server=True)

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(self._last_readiness_kwargs)
            self.assertEqual(self._last_readiness_kwargs[0]["codex_hook_current_hash"], "")
            self.assertIs(self._last_readiness_kwargs[0]["probe_codex_app_server"], True)
            self.assertTrue(self._last_ledger_kwargs)
            self.assertEqual(self._last_ledger_kwargs[0]["codex_hook_current_hash"], "")
            self.assertIs(self._last_ledger_kwargs[0]["probe_codex_app_server"], True)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_stale_hook_ledger_blocks_false_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), stale_ledger=True)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                runner.REAL_CUSTOM_DIP_PROOF_RUNNER_HOOK_LEDGER_NOT_FRESH,
            )
            self.assertIn("run_1_hook_ledger_not_fresh", packet["blocking_reasons"])
            self.assertFalse(packet["api_lane_called"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_wbp_dip_failure_blocks_dispatch_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), wbp_dip_ok=False)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                runner.REAL_CUSTOM_DIP_PROOF_RUNNER_WBP_DIP_FAILED,
            )
            self.assertIn("run_1_wbp_dip_process_failed", packet["blocking_reasons"])
            self.assertFalse(packet["api_lane_called"])
            self.assertTrue(packet["first_run_custom_codex_flow_proven"])
            self.assertTrue(packet["first_run_user_prompt_submit_hook_ran"])
            self.assertFalse(packet["first_run_api_lane_called"])
            self.assertEqual(
                packet["first_run_wbp_dip_machine_error_code"],
                "WBP_DIP_TOOL_FAILED",
            )
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_join_unsafe_source_blocks(self) -> None:
        def unsafe_join(**_kwargs: object) -> dict[str, object]:
            packet = wbp_dip_hook_origin_proof.build_wbp_dip_hook_origin_proof_packet(
                prompt_text=PROMPT,
                ledger_proof_packet=_ledger_packet(PROMPT),
                wbp_dip_packet=_wbp_dip_packet(PROMPT),
            )
            packet["status"] = "error"
            packet["machine_error_code"] = wbp_dip_hook_origin_proof.WBP_DIP_HOOK_ORIGIN_UNSAFE_SOURCE
            packet["blocking_reasons"] = ["source_file_secret_leak"]
            return packet

        with tempfile.TemporaryDirectory() as temp_dir:
            packet = self._run(Path(temp_dir), join_patch=unsafe_join)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                runner.REAL_CUSTOM_DIP_PROOF_RUNNER_JOIN_FAILED,
            )
            self.assertIn("run_1_source_file_secret_leak", packet["blocking_reasons"])
            self.assertFalse(packet["api_lane_called"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_wires_real_custom_dip_runner(self) -> None:
        with mock.patch.object(
            cli_mod,
            "run_real_custom_dip_proof_runner_command",
            return_value={"status": "ok", "exit_code": 0},
        ) as mocked:
            stdout = io.StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = cli_mod.main(
                    [
                        "codex-runner",
                        "real-custom-dip-proof",
                        "--prompt",
                        PROMPT,
                        "--json",
                    ]
                )

        self.assertEqual(rc, 0)
        self.assertTrue(mocked.called)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "ok")


if __name__ == "__main__":
    unittest.main()
