# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from wild_boar_proxy import interactive_custom_codex_proof as interactive
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.real_custom_codex_hook_proof import (
    ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
)
from wild_boar_proxy.runtime import RuntimePaths


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни доказанный API ответ."
EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"


def _runtime_context(*, route_id: str = ROUTE_ID) -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "context_truth_source": "server_launch_selection_packet",
        "agent_bindings_status": "ok",
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1"],
                "lane": "primary_chatgpt",
                "enabled": True,
                "model_id": "gpt-5.4",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": ["DIP", "Agent 2", "Worker"],
                "lane": "api_route",
                "enabled": True,
                "route_id": route_id,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "alias_to_agent_id": {
            "Codex": "codex",
            "Agent 1": "codex",
            "DIP": "dip",
            "Agent 2": "dip",
            "Worker": "dip",
        },
        "agent_id_to_route": {"dip": route_id},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": [route_id],
        "deepseek_live_format_check_cli_command": [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            "--route",
            route_id,
            "--json",
        ],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=root / "stable-config.yaml",
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=managed / "stable-runtime-launcher.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=root / "bin" / "codex-accounts",
        onboard_bin=root / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed / "stable-runtime-config.generated.yaml",
    )


def _write_profile(paths: RuntimePaths) -> None:
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    paths.managed_dir.mkdir(parents=True, exist_ok=True)
    paths.config_toml.write_text('model = "gpt-5.4"\n', encoding="utf-8")
    paths.runtime_effective_mode_file.write_text("stable\n", encoding="utf-8")
    paths.managed_config_file.write_text("mode: stable\n", encoding="utf-8")
    (paths.profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME).write_text(
        json.dumps(_runtime_context()) + "\n",
        encoding="utf-8",
    )
    external_models_dir = paths.managed_dir / "external-models"
    external_models_dir.mkdir(parents=True, exist_ok=True)
    (external_models_dir / "routes.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "routes": [
                    {
                        "route_id": ROUTE_ID,
                        "provider": "deepseek",
                        "enabled": True,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    install = producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
    assert install["status"] == "ok"


def _write_fresh_custom_ledger(paths: RuntimePaths, prompt: str = PROMPT) -> None:
    digest = producer.hook_definition_digest(producer.hook_command_for_paths(paths))
    packet = producer.build_user_prompt_submit_run_packet(
        event={
            "session_id": "interactive-session",
            "turn_id": "interactive-turn",
            "cwd": str(ROOT),
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-5.4",
            "permission_mode": "never",
            "prompt": prompt,
        },
        paths=paths,
        trusted_hook_config_sha256=digest,
        loaded_hook_config_sha256=digest,
        origin_state=ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
    )
    assert packet["status"] == "ok"


def _live_provider_packet(*, expected_text: str = EXPECTED_TEXT) -> dict[str, object]:
    return {
        "status": "ok",
        "exit_code": 0,
        "human_message": "External-models route live format check captured one provider response without writing state or evidence.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "probe",
        "data": {
            "check_kind": "api_only_live_route_format",
            "network_dependent": True,
            "verification_scope": "route_provider_only_no_write",
            "route_state": "live_response_observed_no_write",
            "requested_model": ROUTE_ID,
            "effective_model": "deepseek-test",
            "provider": "deepseek",
            "fallback_used": False,
            "fallback_chain": [ROUTE_ID],
            "latency_ms": 12,
            "request_count": 1,
            "retry_count": 0,
            "parallel_fanout_attempted": False,
            "expected_text": expected_text,
            "expected_text_observed": True,
            "response_preview_bounded": expected_text,
            "response_text_length": len(expected_text),
            "changed_files": [],
            "state_written": False,
            "evidence_written": False,
            "file_mutation_attempted": False,
            "commands_started_by_provider": False,
            "codex_history_sent": False,
            "repo_context_sent": False,
            "request_shape": "openai_chat_messages",
            "response_shape": "choices_message",
        },
        "raw_provider_response_recorded": False,
    }


def _write_live_provider_packet(path: Path, *, expected_text: str = EXPECTED_TEXT) -> None:
    path.write_text(json.dumps(_live_provider_packet(expected_text=expected_text)) + "\n")


def _assert_no_raw_sensitive_text(testcase: unittest.TestCase, packet: dict[str, object]) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["product_ready"])


class InteractiveCustomCodexProofTests(unittest.TestCase):
    def test_preflight_clears_stale_ledger_without_claiming_product(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            _write_fresh_custom_ledger(paths)
            packet = interactive.run_interactive_custom_codex_preflight_command(
                paths=paths,
                prompt_text=PROMPT,
                proof_dir=str(root / "proof"),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["preflight_ready_for_operator_prompt"])
        self.assertTrue(packet["ledger_before_present"])
        self.assertTrue(packet["ledger_cleared_before_prompt"])
        self.assertTrue(packet["hook_config_digest_bound"])
        self.assertTrue(packet["hook_trust_must_be_confirmed_by_fresh_ledger"])
        self.assertFalse(packet["interactive_custom_codex_flow_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_preflight_does_not_report_absent_ledger_as_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            ledger_path = producer.hook_ledger_path(paths)
            self.assertFalse(ledger_path.exists())
            packet = interactive.run_interactive_custom_codex_preflight_command(
                paths=paths,
                prompt_text=PROMPT,
                proof_dir=str(root / "proof"),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["ledger_before_present"])
        self.assertTrue(packet["ledger_cleared_before_prompt"])
        self.assertNotIn(str(ledger_path), packet["changed_files"])

    def test_preflight_blocks_when_selected_registry_does_not_contain_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            (paths.managed_dir / "external-models" / "routes.json").write_text(
                json.dumps({"schema_version": 1, "routes": []}) + "\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {"WBP_EXTERNAL_MODELS_DIR": str(paths.managed_dir / "external-models")},
                clear=False,
            ):
                packet = interactive.run_interactive_custom_codex_preflight_command(
                    paths=paths,
                    prompt_text=PROMPT,
                    proof_dir=str(root / "proof"),
                )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            interactive.INTERACTIVE_PREFLIGHT_NOT_READY,
        )
        self.assertFalse(packet["preflight_ready_for_operator_prompt"])
        self.assertFalse(packet["external_models_dir_route_registry_selected"])
        self.assertIn(
            "external_models_route_registry_not_selected",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["product_ready"])

    def test_collect_proves_interactive_hook_flow_with_approved_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            proof_dir = root / "proof"
            preflight = interactive.run_interactive_custom_codex_preflight_command(
                paths=paths,
                prompt_text=PROMPT,
                proof_dir=str(proof_dir),
            )
            time.sleep(0.001)
            _write_fresh_custom_ledger(paths)
            live_file = root / "live-provider.packet.json"
            _write_live_provider_packet(live_file)
            packet = interactive.run_interactive_custom_codex_collect_command(
                paths=paths,
                prompt_text=PROMPT,
                preflight_packet_file=str(proof_dir / "interactive-preflight.packet.json"),
                proof_dir=str(proof_dir),
                expected_text=EXPECTED_TEXT,
                live_provider_proof_file=str(live_file),
            )

        self.assertEqual(preflight["status"], "ok")
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["interactive_custom_codex_flow_proven"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_ledger_fresh"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["runtime_context_bound"])
        self.assertTrue(packet["alias_context_read"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertTrue(packet["strict_sealed_evidence"])
        self.assertTrue(packet["proof_seal_verified"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_collect_blocks_stale_missing_ledger_before_live_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            proof_dir = root / "proof"
            interactive.run_interactive_custom_codex_preflight_command(
                paths=paths,
                prompt_text=PROMPT,
                proof_dir=str(proof_dir),
            )
            live_file = root / "live-provider.packet.json"
            _write_live_provider_packet(live_file)
            packet = interactive.run_interactive_custom_codex_collect_command(
                paths=paths,
                prompt_text=PROMPT,
                preflight_packet_file=str(proof_dir / "interactive-preflight.packet.json"),
                proof_dir=str(proof_dir),
                expected_text=EXPECTED_TEXT,
                live_provider_proof_file=str(live_file),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            interactive.INTERACTIVE_HOOK_LEDGER_NOT_FRESH,
        )
        self.assertFalse(packet["interactive_custom_codex_flow_proven"])
        self.assertFalse(packet["hook_ledger_fresh"])
        self.assertFalse(packet["api_lane_called"])
        self.assertEqual(
            packet["live_provider_source_kind"],
            "suppressed_before_live_provider_call",
        )
        self.assertFalse(packet["live_provider_proof_file_present"])
        self.assertFalse(packet["live_provider_proof_file_read"])
        self.assertFalse(packet["live_provider_proof_file_valid_json"])
        self.assertFalse(packet["live_provider_proof_file_mapping"])
        self.assertTrue(packet["live_provider_suppressed_packet_written"])
        self.assertIn("hook_ledger_missing", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)

    def test_collect_blocks_preflight_prompt_digest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            proof_dir = root / "proof"
            interactive.run_interactive_custom_codex_preflight_command(
                paths=paths,
                prompt_text=PROMPT,
                proof_dir=str(proof_dir),
            )
            time.sleep(0.001)
            _write_fresh_custom_ledger(paths)
            packet = interactive.run_interactive_custom_codex_collect_command(
                paths=paths,
                prompt_text=PROMPT + " другая команда",
                preflight_packet_file=str(proof_dir / "interactive-preflight.packet.json"),
                proof_dir=str(proof_dir),
                expected_text=EXPECTED_TEXT,
                live_provider_proof_file=str(root / "missing-live.packet.json"),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            interactive.INTERACTIVE_PREFLIGHT_INVALID,
        )
        self.assertFalse(packet["interactive_custom_codex_flow_proven"])
        self.assertFalse(packet["api_lane_called"])
        self.assertIn("preflight_prompt_digest_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])

    def test_cli_interactive_collect_emits_strict_json_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_profile(paths)
            proof_dir = root / "proof"
            env = {
                **os.environ.copy(),
                "PYTHONPATH": str(ROOT),
                "WBP_PROFILE_DIR": str(paths.profile_dir),
                "WBP_MANAGED_DIR": str(paths.managed_dir),
                "WBP_CONFIG_TOML": str(paths.config_toml),
                "WBP_RUNTIME_EFFECTIVE_MODE_FILE": str(
                    paths.runtime_effective_mode_file
                ),
                "WBP_MANAGED_CONFIG_FILE": str(paths.managed_config_file),
                "WBP_STATE_FILE": str(paths.state_file),
            }
            preflight_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "interactive-preflight",
                    "--prompt",
                    PROMPT,
                    "--proof-dir",
                    str(proof_dir),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(preflight_result.returncode, 0, preflight_result.stderr)
            time.sleep(0.001)
            _write_fresh_custom_ledger(paths)
            live_file = root / "live-provider.packet.json"
            _write_live_provider_packet(live_file)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "interactive-collect",
                    "--prompt",
                    PROMPT,
                    "--preflight-packet-file",
                    str(proof_dir / "interactive-preflight.packet.json"),
                    "--proof-dir",
                    str(proof_dir),
                    "--expected-text",
                    EXPECTED_TEXT,
                    "--live-provider-proof-file",
                    str(live_file),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["packet_kind"], interactive.INTERACTIVE_COLLECT_PACKET_KIND)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["interactive_custom_codex_flow_proven"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_raw_sensitive_text(self, packet)
