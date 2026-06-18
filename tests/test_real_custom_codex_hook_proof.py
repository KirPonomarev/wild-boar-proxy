# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import real_custom_codex_hook_proof as proof
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни доказанный API ответ."


def _runtime_context(*, allowed_routes: list[str] | None = None) -> dict[str, object]:
    allowed_routes = [ROUTE_ID] if allowed_routes is None else allowed_routes
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
                "route_id": ROUTE_ID,
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
        "agent_id_to_route": {"dip": ROUTE_ID},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": allowed_routes,
        "deepseek_live_format_check_cli_command": [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            "--route",
            ROUTE_ID,
            "--json",
        ],
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _prompt_digest(prompt: str, context: dict[str, object]) -> str:
    packet = hook_entry.build_router_hook_entry_packet(
        prompt_text=prompt,
        runtime_context=context,
        hook_surface_kind=hook_entry.HOOK_SURFACE_USER_PROMPT_SUBMIT,
    )
    return str(packet["prompt_digest"])


def _ledger(
    *,
    prompt: str = PROMPT,
    context: dict[str, object] | None = None,
    **overrides: object,
) -> dict[str, object]:
    context = _runtime_context() if context is None else context
    hook_hash = _sha256("wbp-user-prompt-submit-hook-v1")
    ledger = proof.build_user_prompt_submit_hook_ledger(
        prompt_digest=_prompt_digest(prompt, context),
        runtime_context_digest_value=proof.runtime_context_digest(context),
        thread_digest=_sha256("custom-codex-thread"),
        turn_digest=_sha256("custom-codex-turn"),
        trusted_hook_config_sha256=hook_hash,
        loaded_hook_config_sha256=hook_hash,
        hook_producer_state="HOOK_RAN_CUSTOM_CODEX_PROVEN",
        hook_event_digest=_sha256("custom-codex-user-prompt-submit-event"),
        session_digest=_sha256("custom-codex-session"),
        cwd_digest=_sha256(str(ROOT)),
        hook_trust_source="codex_non_managed_hook_execution",
    )
    ledger.update(overrides)
    return ledger


def _write_context_and_ledger(
    root: Path,
    *,
    prompt: str = PROMPT,
    context: dict[str, object] | None = None,
    ledger_overrides: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    context = _runtime_context() if context is None else context
    profile_dir = root / "profile"
    profile_dir.mkdir()
    context_path = profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME
    context_path.write_text(json.dumps(context) + "\n", encoding="utf-8")
    ledger_path = root / "user-prompt-submit-ledger.json"
    ledger = _ledger(prompt=prompt, context=context, **(ledger_overrides or {}))
    ledger_path.write_text(json.dumps(ledger) + "\n", encoding="utf-8")
    return profile_dir, ledger_path


def _live_provider_packet(
    *,
    route_id: str = ROUTE_ID,
    expected_text: str = "WBP_DIP_DISPATCH_OK",
    expected_text_observed: bool = True,
    response_preview_bounded: str | None = None,
    fallback_used: bool = False,
    raw_provider_response_recorded: bool = False,
) -> dict[str, object]:
    response_preview = (
        expected_text if response_preview_bounded is None else response_preview_bounded
    )
    return packets.build_command_packet(
        ok=True,
        human_message="External-models route live format check captured one provider response without writing state or evidence.",
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect="probe",
        extra={
            "data": {
                "check_kind": "api_only_live_route_format",
                "network_dependent": True,
                "verification_scope": "route_provider_only_no_write",
                "route_state": "live_response_observed_no_write",
                "requested_model": route_id,
                "effective_model": "deepseek-test",
                "provider": "deepseek",
                "fallback_used": fallback_used,
                "fallback_chain": [route_id],
                "cost_class": "free_or_limited",
                "latency_ms": 12,
                "request_count": 1,
                "retry_count": 0,
                "parallel_fanout_attempted": False,
                "expected_text": expected_text,
                "expected_text_observed": expected_text_observed,
                "response_preview_bounded": response_preview,
                "response_text_length": len(response_preview),
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
            "raw_provider_response_recorded": raw_provider_response_recorded,
        },
    )


def _write_live_provider_packet(
    root: Path,
    *,
    packet: dict[str, object] | None = None,
) -> Path:
    path = root / "live-provider-proof.json"
    path.write_text(json.dumps(packet or _live_provider_packet()) + "\n", encoding="utf-8")
    return path


def _assert_no_secret_or_raw_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    *,
    prompt: str = PROMPT,
    expected_text: str = "",
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(prompt, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    if expected_text:
        testcase.assertNotIn(expected_text, serialized)
    testcase.assertFalse(packet_contains_text(packet, prompt))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["route_candidate_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class RealCustomCodexHookProofTests(unittest.TestCase):
    def test_positive_file_backed_user_prompt_submit_hook_proves_dispatch_and_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
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
        self.assertEqual(result.stdout.strip(), json.dumps(packet, ensure_ascii=True))
        self.assertEqual(
            packet["packet_kind"],
            proof.REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND,
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertTrue(packet["runtime_context_file_read"])
        self.assertTrue(packet["hook_ledger_file_read"])
        self.assertTrue(packet["hook_ledger_packet_valid"])
        self.assertTrue(packet["hook_config_present"])
        self.assertTrue(packet["hook_enabled"])
        self.assertTrue(packet["hook_trusted"])
        self.assertTrue(packet["hook_hash_current"])
        self.assertTrue(packet["hook_config_digest_bound"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["hook_ledger_written"])
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["thread_or_turn_digest_bound"])
        self.assertTrue(packet["hook_producer_ledger_proven"])
        self.assertEqual(packet["hook_producer_state"], "HOOK_RAN_CUSTOM_CODEX_PROVEN")
        self.assertTrue(packet["hook_event_digest"])
        self.assertEqual(
            packet["hook_trust_source"],
            "codex_non_managed_hook_execution",
        )
        self.assertFalse(packet["custom_codex_flow_proven"])
        self.assertEqual(packet["command_origin_surface"], "")
        self.assertFalse(packet["command_origin_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["native_custom_codex_flow_proven"])
        self.assertFalse(packet["native_router_hook_observed"])
        self.assertTrue(packet["natural_alias_command_detected"])
        self.assertTrue(packet["natural_api_alias_command_detected"])
        self.assertTrue(packet["router_preflight_admitted"])
        self.assertTrue(packet["router_dispatch_admitted"])
        self.assertTrue(packet["router_owned_dispatch_decision_bound"])
        self.assertEqual(
            packet["router_dispatch_decision_truth_source"],
            "wbp_owned_router_hook_entry_to_api_lane_adapter",
        )
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["api_lane_dispatch_admitted"])
        self.assertTrue(packet["api_response_received"])
        self.assertTrue(packet["response_bound_to_proof"])
        self.assertEqual(packet["dispatch_status"], "proven")
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertEqual(
            packet["dispatch_truth_source"],
            "server_owned_controlled_provider_no_live_network",
        )
        self.assertTrue(packet["provider_like_response_only"])
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["route_id_allowed"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertTrue(packet["approved_handoff_payload_sanitized"])
        self.assertTrue(packet["machine_response_envelope_observed"])
        self.assertTrue(packet["machine_response_structured_content_present"])
        self.assertTrue(packet["handoff_delivered"])
        self.assertTrue(packet["delivery_observed"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["live_provider_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_custom_codex_origin"])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_file_backed_hook_dispatch_and_live_provider_join(self) -> None:
        expected_text = "WBP_DIP_DISPATCH_OK"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            live_path = _write_live_provider_packet(
                root,
                packet=_live_provider_packet(expected_text=expected_text),
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--live-provider-proof-file",
                    str(live_path),
                    "--live-provider-expected-text",
                    expected_text,
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
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["dispatch_proven"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertTrue(packet["live_provider_requested"])
        self.assertTrue(packet["live_provider_attempted"])
        self.assertEqual(
            packet["live_provider_source_kind"],
            "file_backed_external_models_live_format_check",
        )
        self.assertTrue(packet["live_provider_proof_file_read"])
        self.assertTrue(packet["live_provider_cli_command_declared"])
        self.assertTrue(packet["live_provider_cli_command_route_bound"])
        self.assertTrue(packet["live_provider_route_bound_to_context"])
        self.assertTrue(packet["live_provider_network_dependent"])
        self.assertEqual(packet["live_provider_request_count"], 1)
        self.assertTrue(packet["expected_text_observed"])
        self.assertFalse(packet["expected_text_recorded"])
        self.assertFalse(packet["raw_expected_text_recorded"])
        self.assertFalse(packet["provider_route_fallback_used"])
        self.assertTrue(packet["live_provider_response_bound_to_expected_text"])
        self.assertTrue(packet["live_provider_response_bound_to_route"])
        self.assertTrue(packet["live_provider_response_proven"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["does_not_prove_live_provider"])
        self.assertTrue(packet["approved_handoff_ready"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        _assert_no_secret_or_raw_text(self, packet, expected_text=expected_text)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_join_blocks_route_mismatch_or_missing_expected_text(self) -> None:
        cases = [
            (
                _live_provider_packet(route_id="wbp-other-route"),
                "live_provider_route_mismatch",
            ),
            (
                _live_provider_packet(expected_text_observed=False),
                "live_provider_expected_text_not_observed",
            ),
            (
                _live_provider_packet(response_preview_bounded="SOMETHING_ELSE"),
                "live_provider_response_preview_mismatch",
            ),
        ]
        for live_packet, reason in cases:
            with self.subTest(reason=reason):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(root)
                    live_path = _write_live_provider_packet(root, packet=live_packet)
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--live-provider-proof-file",
                            str(live_path),
                            "--live-provider-expected-text",
                            "WBP_DIP_DISPATCH_OK",
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN,
                )
                self.assertTrue(packet["dispatch_proven"])
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["live_provider_response_proven"])
                self.assertFalse(packet["external_live_provider_response_proven"])
                self.assertFalse(packet["approved_handoff_ready"])
                _assert_no_secret_or_raw_text(
                    self,
                    packet,
                    expected_text="WBP_DIP_DISPATCH_OK",
                )
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_join_blocks_unsafe_provider_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            live_path = _write_live_provider_packet(
                root,
                packet=_live_provider_packet(raw_provider_response_recorded=True),
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--live-provider-proof-file",
                    str(live_path),
                    "--live-provider-expected-text",
                    "WBP_DIP_DISPATCH_OK",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            proof.USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN,
        )
        self.assertIn("live_provider_raw_response_recorded", packet["blocking_reasons"])
        self.assertFalse(packet["live_provider_response_proven"])
        self.assertFalse(packet["external_live_provider_response_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_secret_or_raw_text(
            self,
            packet,
            expected_text="WBP_DIP_DISPATCH_OK",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_join_requires_cli_route_argument_binding(self) -> None:
        context = _runtime_context()
        context["deepseek_live_format_check_cli_command"] = [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "external-models",
            "live-format-check",
            ROUTE_ID,
            "--route",
            "wbp-other-route",
            "--json",
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root, context=context)
            live_path = _write_live_provider_packet(root)
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--live-provider-proof-file",
                    str(live_path),
                    "--live-provider-expected-text",
                    "WBP_DIP_DISPATCH_OK",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            proof.USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN,
        )
        self.assertTrue(packet["live_provider_cli_command_declared"])
        self.assertFalse(packet["live_provider_cli_command_route_bound"])
        self.assertIn(
            "live_provider_cli_command_not_route_bound",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["live_provider_response_proven"])
        _assert_no_secret_or_raw_text(
            self,
            packet,
            expected_text="WBP_DIP_DISPATCH_OK",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_live_provider_auto_run_blocks_unsafe_expected_marker_before_provider_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--live-provider-expected-text",
                    "not a safe marker",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            proof.USER_PROMPT_SUBMIT_LIVE_PROVIDER_NOT_PROVEN,
        )
        self.assertEqual(
            packet["live_provider_source_kind"],
            "live_provider_expected_text_not_safe_marker",
        )
        self.assertFalse(packet["live_provider_attempted"])
        self.assertIn(
            "live_provider_expected_text_not_safe_marker",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["live_provider_response_proven"])
        _assert_no_secret_or_raw_text(
            self,
            packet,
            expected_text="not a safe marker",
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_builder_rejects_in_memory_evidence_without_file_backed_metadata(self) -> None:
        context = _runtime_context()
        packet = proof.build_real_custom_codex_hook_proof_packet(
            prompt_text=PROMPT,
            runtime_context=context,
            hook_ledger=_ledger(context=context),
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN,
        )
        self.assertIn("hook_ledger_file_not_read", packet["blocking_reasons"])
        self.assertIn("runtime_context_file_not_read", packet["blocking_reasons"])
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_missing_or_invalid_ledger_before_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            ledger_path.unlink()
            invalid_json_path = root / "invalid-ledger.json"
            invalid_json_path.write_text("{", encoding="utf-8")
            non_mapping_path = root / "non-mapping-ledger.json"
            non_mapping_path.write_text("[]\n", encoding="utf-8")

            cases = [
                (
                    ledger_path,
                    proof.USER_PROMPT_SUBMIT_LEDGER_MISSING,
                    "hook_ledger_file_not_read",
                ),
                (
                    invalid_json_path,
                    proof.USER_PROMPT_SUBMIT_LEDGER_INVALID,
                    "hook_ledger_file_json_not_valid",
                ),
                (
                    non_mapping_path,
                    proof.USER_PROMPT_SUBMIT_LEDGER_INVALID,
                    "hook_ledger_file_not_mapping",
                ),
            ]
            for path, machine_code, reason in cases:
                with self.subTest(reason=reason):
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                    packet = json.loads(result.stdout)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(packet["machine_error_code"], machine_code)
                    self.assertIn(reason, packet["blocking_reasons"])
                    self.assertFalse(packet["dispatch_attempted"])
                    self.assertFalse(packet["api_lane_called"])
                    self.assertFalse(packet["custom_codex_origin_proven"])
                    self.assertFalse(packet["native_free_chat_router_proven"])
                    self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_blocks_missing_or_invalid_runtime_context_before_dispatch(self) -> None:
        cases = [
            ("missing", None, "runtime_context_file_not_read"),
            ("invalid-json", "{", "runtime_context_file_json_not_valid"),
            ("not-object", "[]\n", "runtime_context_file_not_mapping"),
        ]
        for label, file_text, reason in cases:
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(root)
                    context_path = profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME
                    if file_text is None:
                        context_path.unlink()
                    else:
                        context_path.write_text(file_text, encoding="utf-8")

                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["dispatch_attempted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["custom_codex_origin_proven"])
                self.assertFalse(packet["native_free_chat_router_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_disabled_untrusted_or_hash_mismatched_hook_before_dispatch(self) -> None:
        cases = [
            ({"hook_enabled": False}, "hook_disabled"),
            ({"hook_trusted": False}, "hook_untrusted"),
            ({"loaded_hook_config_sha256": _sha256("changed")}, "hook_config_digest_mismatch"),
        ]
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(
                        root,
                        ledger_overrides=overrides,
                    )
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["dispatch_attempted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["custom_codex_origin_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_non_custom_origin_even_if_hook_ran(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(
                root,
                ledger_overrides={
                    "origin_state": proof.ORIGIN_STATE_APP_SERVER_CHILD_FLOW,
                    "command_origin_surface": "custom_codex_flow",
                },
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            proof.USER_PROMPT_SUBMIT_UNSAFE_CLAIM,
        )
        self.assertIn(
            "origin_state_not_custom_codex_flow_proven",
            packet["blocking_reasons"],
        )
        self.assertIn(
            "custom_origin_surface_claim_without_custom_origin",
            packet["blocking_reasons"],
        )
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_each_non_custom_origin_state_before_dispatch(self) -> None:
        cases = [
            proof.ORIGIN_STATE_CONTROLLED_CODEX_EXEC_FLOW,
            proof.ORIGIN_STATE_APP_SERVER_CHILD_FLOW,
            proof.ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
            proof.ORIGIN_STATE_BLOCKED_ORIGIN_UNPROVEN,
        ]
        for origin_state in cases:
            with self.subTest(origin_state=origin_state):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(
                        root,
                        ledger_overrides={"origin_state": origin_state},
                    )
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_ORIGIN_NOT_CUSTOM_CODEX,
                )
                self.assertIn(
                    "origin_state_not_custom_codex_flow_proven",
                    packet["blocking_reasons"],
                )
                self.assertFalse(packet["dispatch_attempted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["custom_codex_origin_proven"])
                self.assertFalse(packet["native_free_chat_router_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_prompt_or_context_digest_mismatch_before_dispatch(self) -> None:
        cases = [
            ({"prompt_digest": _sha256("different-prompt")}, "hook_prompt_digest_mismatch"),
            (
                {"runtime_context_digest": _sha256("different-context")},
                "hook_runtime_context_digest_mismatch",
            ),
        ]
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(
                        root,
                        ledger_overrides=overrides,
                    )
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["dispatch_attempted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["dispatch_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_missing_thread_and_turn_digest_before_dispatch(self) -> None:
        cases = [
            ({"thread_digest": ""}, "thread_or_turn_digest_missing"),
            ({"turn_digest": ""}, "thread_or_turn_digest_missing"),
        ]
        for overrides, reason in cases:
            with self.subTest(overrides=overrides):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(
                        root,
                        ledger_overrides=overrides,
                    )
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )

                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_HOOK_NOT_PROVEN,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["dispatch_attempted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["custom_codex_origin_proven"])
                self.assertFalse(packet["native_free_chat_router_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_raw_prompt_route_or_provider_claims_from_ledger(self) -> None:
        cases = [
            ("raw_prompt_recorded", "raw_prompt_recorded"),
            ("raw_route_id_recorded", "raw_route_id_recorded"),
            ("provider_response_text_recorded", "provider_response_text_recorded"),
            ("local_imitation_used", "local_imitation_used"),
            ("native_codex_subagent_used_as_dip", "native_codex_subagent_used_as_dip"),
            ("product_ready", "product_ready_must_not_be_claimed"),
        ]
        for field, reason in cases:
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    profile_dir, ledger_path = _write_context_and_ledger(
                        root,
                        ledger_overrides={field: True},
                    )
                    env = os.environ.copy()
                    env["WBP_PROFILE_DIR"] = str(profile_dir)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "wild_boar_proxy",
                            "router-hook",
                            "user-prompt-submit-proof",
                            "--prompt",
                            PROMPT,
                            "--hook-ledger-file",
                            str(ledger_path),
                            "--json",
                        ],
                        cwd=ROOT,
                        env=env,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                packet = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(
                    packet["machine_error_code"],
                    proof.USER_PROMPT_SUBMIT_UNSAFE_CLAIM,
                )
                self.assertIn(reason, packet["blocking_reasons"])
                self.assertFalse(packet["dispatch_attempted"])
                self.assertFalse(packet["api_lane_called"])
                self.assertFalse(packet["custom_codex_origin_proven"])
                self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_blocks_route_outside_allowlist_after_hook_origin_before_dispatch_success(self) -> None:
        context = _runtime_context(allowed_routes=["wbp-other-route"])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(
                root,
                context=context,
            )
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(profile_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        packet = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            packet["machine_error_code"],
            proof.USER_PROMPT_SUBMIT_DISPATCH_NOT_PROVEN,
        )
        self.assertTrue(packet["hook_prompt_digest_bound"])
        self.assertTrue(packet["hook_runtime_context_digest_bound"])
        self.assertTrue(packet["dispatch_attempted"])
        self.assertIn("dispatch_packet_not_ok", packet["blocking_reasons"])
        self.assertFalse(packet["api_lane_called"])
        self.assertFalse(packet["dispatch_proven"])
        self.assertFalse(packet["custom_codex_origin_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        _assert_no_secret_or_raw_text(self, packet)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_user_prompt_submit_proof_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "user-prompt-submit-proof",
                "--prompt",
                PROMPT,
                "--hook-ledger-file",
                "/tmp/wbp-hook-ledger.json",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
