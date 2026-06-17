# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import codex_working_flow_delivery_proof as working_flow
from wild_boar_proxy import interactive_codex_working_flow_delivery as join
from wild_boar_proxy import interactive_custom_codex_proof as interactive
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.proof_seal import read_json_mapping_file, sha256_file, verify_proof_seal
from wild_boar_proxy.real_custom_codex_hook_proof import (
    ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
)
from wild_boar_proxy.runtime import RuntimePaths


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: верни результат в working flow."
EXPECTED_TEXT = "WBP_DIP_DISPATCH_OK"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_digest(value: dict[str, object]) -> str:
    return _sha256_text(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


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


def _write_live_provider_packet(path: Path) -> None:
    path.write_text(json.dumps(_live_provider_packet()) + "\n", encoding="utf-8")


def _tool_result_event(structured_content: dict[str, object]) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-delegate-result",
            "type": "mcp_tool_result",
            "server_name": "wbp",
            "tool_name": "delegate_to_dip",
            "status": "completed",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            structured_content,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        ),
                    }
                ],
                "structuredContent": structured_content,
                "isError": False,
            },
        },
    }


def _assistant_event(digest: str) -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-assistant-continuation",
            "type": "assistant_message",
            "role": "assistant",
            "status": "completed",
            "text": "WBP working-flow receipt.",
            "metadata": {"wbp_handoff_digest": digest},
        },
    }


def _subagent_event() -> dict[str, object]:
    return {
        "type": "item.completed",
        "item": {
            "id": "item-subagent",
            "type": "codex_subagent",
            "name": "DIP",
            "status": "completed",
            "text": "Local sub-agent DIP produced a response.",
        },
    }


def _events_for_source(
    source: dict[str, object],
    *,
    assistant: bool = True,
    subagent: bool = False,
) -> list[dict[str, object]]:
    structured = working_flow._safe_working_flow_delivery_payload(source)
    events = [
        {"type": "thread.started", "thread_id": "thread-working-flow"},
        {"type": "turn.started"},
        _tool_result_event(structured),
    ]
    if subagent:
        events.append(_subagent_event())
    if assistant:
        events.append(_assistant_event(str(structured["handoff_payload_sha256"])))
    events.append({"type": "turn.completed"})
    return events


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=True) for event in events) + "\n",
        encoding="utf-8",
    )


def _prepare_interactive_proof(root: Path) -> tuple[RuntimePaths, Path, Path]:
    paths = _paths(root)
    _write_profile(paths)
    proof_dir = root / "proof"
    preflight = interactive.run_interactive_custom_codex_preflight_command(
        paths=paths,
        prompt_text=PROMPT,
        proof_dir=str(proof_dir),
    )
    assert preflight["status"] == "ok"
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
    assert packet["status"] == "ok"
    return paths, proof_dir / "interactive-custom-codex-proof.packet.json", proof_dir


def _assert_no_product_or_ui_claim(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    testcase.assertFalse(packet["custom_codex_ui_visibility_proven"])
    testcase.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
    testcase.assertFalse(packet["native_free_chat_router_proven"])
    testcase.assertFalse(packet["product_ready"])
    testcase.assertTrue(packet["does_not_prove_custom_codex_ui"])
    testcase.assertTrue(packet["does_not_prove_native_free_chat_router"])
    testcase.assertTrue(packet["does_not_prove_product_ready"])


def _assert_no_raw_sensitive_text(
    testcase: unittest.TestCase,
    packet: dict[str, object],
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    for forbidden in (PROMPT, ROUTE_ID, EXPECTED_TEXT):
        testcase.assertNotIn(forbidden, serialized)
        testcase.assertFalse(packet_contains_text(packet, forbidden))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["natural_phrase_recorded"])
    testcase.assertFalse(packet["raw_jsonl_recorded"])
    testcase.assertFalse(packet["tool_call_arguments_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["selected_api_route_id_recorded"])
    testcase.assertFalse(packet["raw_provider_response_recorded"])
    testcase.assertFalse(packet["provider_response_text_recorded"])
    testcase.assertFalse(packet["provider_response_preview_recorded"])
    testcase.assertFalse(packet["raw_backend_details_exposed"])
    testcase.assertFalse(packet["secret_value_exposed"])


class InteractiveCodexWorkingFlowDeliveryTests(unittest.TestCase):
    def test_positive_joins_interactive_proof_to_file_backed_codex_working_flow(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _paths_obj, interactive_file, proof_dir = _prepare_interactive_proof(root)
            source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
            source = json.loads(source_file.read_text(encoding="utf-8"))
            jsonl_file = root / "codex-exec.jsonl"
            _write_jsonl(jsonl_file, _events_for_source(source))

            packet = join.run_interactive_codex_working_flow_delivery_command(
                interactive_proof_file=str(interactive_file),
                integrated_live_provider_proof_file=str(source_file),
                codex_exec_jsonl_file=str(jsonl_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            join.INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        )
        self.assertEqual(packet["effect"], "mutate")
        self.assertEqual(packet["delivery_source_kind"], join.DELIVERY_SOURCE_CODEX_EXEC_JSONL)
        self.assertTrue(packet["delivery_source_file_backed"])
        self.assertTrue(packet["delivery_source_digest"])
        self.assertTrue(packet["interactive_custom_codex_flow_proven"])
        self.assertTrue(packet["hook_ledger_fresh"])
        self.assertTrue(packet["source_proof_sha256_bound_to_interactive_proof"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["external_live_provider_response_proven"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertTrue(packet["approved_delivery_surface_proven"])
        self.assertTrue(packet["assistant_continuation_bound"])
        self.assertTrue(packet["handoff_digest_bound"])
        self.assertTrue(packet["codex_exec_assistant_continuation_proven"])
        self.assertTrue(packet["codex_exec_working_flow_delivery_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["strict_sealed_evidence"])
        self.assertTrue(packet["working_flow_seal_input_hashes_bound"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertEqual(packet["blocking_reasons"], [])
        changed_names = {Path(path).name for path in packet["changed_files"]}
        self.assertIn(join.WORKING_FLOW_PACKET_FILENAME, changed_names)
        self.assertIn(join.WORKING_FLOW_SEAL_FILENAME, changed_names)
        self.assertIn(join.WORKING_FLOW_SEAL_VERIFY_FILENAME, changed_names)
        self.assertIn(join.FINAL_PACKET_FILENAME, changed_names)
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)
        self.assertEqual(
            packets.inspect_command_packet_semantics(
                packet,
                secret_values=[PROMPT, ROUTE_ID, EXPECTED_TEXT],
            ),
            [],
        )

    def test_forged_self_consistent_seal_input_hashes_block_strict_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _paths_obj, interactive_file, proof_dir = _prepare_interactive_proof(root)
            source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
            source = json.loads(source_file.read_text(encoding="utf-8"))
            jsonl_file = root / "codex-exec.jsonl"
            _write_jsonl(jsonl_file, _events_for_source(source))
            positive = join.run_interactive_codex_working_flow_delivery_command(
                interactive_proof_file=str(interactive_file),
                integrated_live_provider_proof_file=str(source_file),
                codex_exec_jsonl_file=str(jsonl_file),
                proof_dir=str(proof_dir),
            )
            self.assertEqual(positive["status"], "ok")

            seal_file = proof_dir / join.WORKING_FLOW_SEAL_FILENAME
            seal = json.loads(seal_file.read_text(encoding="utf-8"))
            source_kind = str(source["packet_kind"])
            seal["input_packet_hashes"][source_kind] = "f" * 64
            seal["producer_inputs_digest"] = _canonical_digest(
                {"input_packet_hashes": seal["input_packet_hashes"]}
            )
            seal_file.write_text(json.dumps(seal) + "\n", encoding="utf-8")

            expected_input_hashes = {
                interactive.INTERACTIVE_COLLECT_PACKET_KIND: sha256_file(interactive_file),
                str(source["packet_kind"]): sha256_file(source_file),
            }
            seal_verify_packet, _seal = verify_proof_seal(
                packet_file=str(proof_dir / join.WORKING_FLOW_PACKET_FILENAME),
                seal_file=str(seal_file),
                expected_packet_kind=working_flow.CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
                expected_input_packet_hashes=expected_input_hashes,
            )
            self.assertEqual(seal_verify_packet["status"], "error")
            self.assertIn(
                f"input_packet_hash_mismatch:{source_kind}",
                seal_verify_packet["blocking_reasons"],
            )
            interactive_packet, interactive_metadata = read_json_mapping_file(
                interactive_file,
                prefix="interactive_proof",
            )
            source_packet, source_metadata = read_json_mapping_file(
                source_file,
                prefix="source_proof",
            )
            working_flow_packet, working_flow_metadata = read_json_mapping_file(
                proof_dir / join.WORKING_FLOW_PACKET_FILENAME,
                prefix="working_flow_proof",
            )
            expected_digest = _canonical_digest(expected_input_hashes)
            final = join.build_interactive_codex_working_flow_delivery_packet(
                interactive_packet=interactive_packet,
                source_packet=source_packet,
                working_flow_packet=working_flow_packet,
                seal_create_packet={"status": "ok", "machine_error_code": "OK"},
                seal_verify_packet=seal_verify_packet,
                delivery_source_kind=join.DELIVERY_SOURCE_CODEX_EXEC_JSONL,
                file_metadata={
                    **interactive_metadata,
                    **source_metadata,
                    **working_flow_metadata,
                },
                changed_files=[],
                expected_seal_input_hashes_digest=expected_digest,
            )

        self.assertEqual(final["status"], "error")
        self.assertEqual(
            final["machine_error_code"],
            join.INTERACTIVE_WORKING_FLOW_SEAL_FAILED,
        )
        self.assertFalse(final["strict_sealed_evidence"])
        self.assertFalse(final["working_flow_seal_input_hashes_bound"])
        self.assertIn(
            "working_flow_seal_input_hashes_not_bound",
            final["blocking_reasons"],
        )
        self.assertFalse(final["codex_working_flow_delivery_proven"])
        _assert_no_product_or_ui_claim(self, final)

    def test_source_digest_mismatch_blocks_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _paths_obj, interactive_file, proof_dir = _prepare_interactive_proof(root)
            interactive_packet = json.loads(interactive_file.read_text(encoding="utf-8"))
            interactive_packet["source_proof_sha256"] = "0" * 64
            bad_interactive_file = root / "bad-interactive.packet.json"
            bad_interactive_file.write_text(
                json.dumps(interactive_packet) + "\n",
                encoding="utf-8",
            )
            source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
            source = json.loads(source_file.read_text(encoding="utf-8"))
            jsonl_file = root / "codex-exec.jsonl"
            _write_jsonl(jsonl_file, _events_for_source(source))

            packet = join.run_interactive_codex_working_flow_delivery_command(
                interactive_proof_file=str(bad_interactive_file),
                integrated_live_provider_proof_file=str(source_file),
                codex_exec_jsonl_file=str(jsonl_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            join.INTERACTIVE_WORKING_FLOW_SOURCE_PROOF_INVALID,
        )
        self.assertFalse(packet["source_proof_sha256_bound_to_interactive_proof"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertIn(
            "source_proof_sha256_not_bound_to_interactive_proof",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)

    def test_missing_assistant_continuation_blocks_working_flow_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _paths_obj, interactive_file, proof_dir = _prepare_interactive_proof(root)
            source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
            source = json.loads(source_file.read_text(encoding="utf-8"))
            jsonl_file = root / "codex-exec.jsonl"
            _write_jsonl(jsonl_file, _events_for_source(source, assistant=False))

            packet = join.run_interactive_codex_working_flow_delivery_command(
                interactive_proof_file=str(interactive_file),
                integrated_live_provider_proof_file=str(source_file),
                codex_exec_jsonl_file=str(jsonl_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            join.INTERACTIVE_WORKING_FLOW_DELIVERY_NOT_PROVEN,
        )
        self.assertFalse(packet["assistant_continuation_bound"])
        self.assertFalse(packet["codex_exec_working_flow_delivery_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertIn("working_flow_proof_packet_not_ok", packet["blocking_reasons"])
        self.assertIn("assistant_continuation_not_proven", packet["blocking_reasons"])
        _assert_no_product_or_ui_claim(self, packet)
        _assert_no_raw_sensitive_text(self, packet)

    def test_local_codex_subagent_as_dip_blocks_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _paths_obj, interactive_file, proof_dir = _prepare_interactive_proof(root)
            source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
            source = json.loads(source_file.read_text(encoding="utf-8"))
            jsonl_file = root / "codex-exec.jsonl"
            _write_jsonl(jsonl_file, _events_for_source(source, subagent=True))

            packet = join.run_interactive_codex_working_flow_delivery_command(
                interactive_proof_file=str(interactive_file),
                integrated_live_provider_proof_file=str(source_file),
                codex_exec_jsonl_file=str(jsonl_file),
                proof_dir=str(proof_dir),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["local_imitation_used"])
        self.assertTrue(packet["native_codex_subagent_used_as_dip"])
        self.assertIn("working_flow_proof_packet_not_ok", packet["blocking_reasons"])
        self.assertIn(
            "working_flow_native_codex_subagent_used_as_dip",
            packet["blocking_reasons"],
        )
        _assert_no_product_or_ui_claim(self, packet)

    def test_cli_interactive_working_flow_delivery_emits_strict_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _paths_obj, interactive_file, proof_dir = _prepare_interactive_proof(root)
            source_file = proof_dir / "interactive-user-prompt-submit-proof.packet.json"
            source = json.loads(source_file.read_text(encoding="utf-8"))
            jsonl_file = root / "codex-exec.jsonl"
            _write_jsonl(jsonl_file, _events_for_source(source))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "codex-runner",
                    "interactive-working-flow-delivery",
                    "--interactive-proof-file",
                    str(interactive_file),
                    "--integrated-live-provider-proof-file",
                    str(source_file),
                    "--codex-exec-jsonl-file",
                    str(jsonl_file),
                    "--proof-dir",
                    str(proof_dir),
                    "--json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["packet_kind"],
            join.INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        )
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])


if __name__ == "__main__":
    unittest.main()
