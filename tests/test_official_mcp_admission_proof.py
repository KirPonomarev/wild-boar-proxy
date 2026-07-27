# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import mcp_delegate
from wild_boar_proxy import official_mcp_admission_proof as proof
from wild_boar_proxy.core import packets
from wild_boar_proxy.process_runner import BoundedProcessResult, PROCESS_OK


MCP_GET_STDOUT = """\
wbp
  enabled: true
  transport: stdio
  command: python3
  args: -m wild_boar_proxy.mcp_delegate
  cwd: -
  env: WBP_PROFILE_DIR=*****
  remove: codex mcp remove wbp
"""


def _process_result(*, stdout: str, exit_code: int = 0) -> BoundedProcessResult:
    return BoundedProcessResult(
        status="ok" if exit_code == 0 else "error",
        machine_error_code=PROCESS_OK if exit_code == 0 else "PROCESS_FAILED",
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=False,
        duration_seconds=0.01,
    )


def _jsonl_for_prompt_bound_tool_call(
    variant: proof.OfficialMcpAdmissionVariant,
    *,
    status: str = "completed",
    arguments: dict[str, str] | None = None,
) -> str:
    if arguments is None:
        arguments = {
            "task": variant.expected_task or variant.prompt,
            "expected_alias": variant.expected_alias,
        }
    return "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "thread-proof"}),
            json.dumps({"type": "turn.started"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item-delegate",
                        "type": "mcp_tool_call",
                        "server_name": "wbp",
                        "tool_name": "delegate_to_dip",
                        "status": status,
                        "arguments": arguments,
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps({"type": "turn.completed"}),
        ]
    )


def _profile_path_from_overrides(config_overrides: list[str]) -> Path:
    encoded = "\n".join(config_overrides)
    match = re.search(r'WBP_PROFILE_DIR="([^"]+)"', encoded)
    assert match is not None
    return Path(match.group(1))


def _evidence_path_from_overrides(config_overrides: list[str]) -> Path:
    encoded = "\n".join(config_overrides)
    match = re.search(r'WBP_ENTRY_HOOK_EVIDENCE_PATH="([^"]+)"', encoded)
    assert match is not None
    return Path(match.group(1))


def _positive_case_packet(alias: str) -> dict[str, object]:
    variant = proof.OfficialMcpAdmissionVariant(
        name=f"positive_{alias.replace(' ', '_').casefold()}",
        prompt=f"{alias}, проверь WBP MCP admission.",
        expected_alias=alias,
        coding_aliases=("DIP", "Agent 2", "Worker"),
        expect_positive_proof=True,
        expected_task=f"WBP_TEST_{alias.replace(' ', '_').upper()}",
    )
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        profile_dir = root / "profile"
        proof.write_runtime_context(profile_dir, variant)
        delegate_packet = mcp_delegate.build_delegate_to_dip_packet(
            {"task": variant.expected_task, "expected_alias": alias},
            env={"WBP_PROFILE_DIR": str(profile_dir)},
            mcp_tool_called=True,
        )
        evidence = mcp_delegate._entry_hook_evidence_packet(delegate_packet)
    config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
        "",
        MCP_GET_STDOUT,
        list_exit_code=0,
        get_exit_code=0,
    )
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        variant.prompt,
        source="codex_exec_json",
        expected_delegate_arguments={
            "task": variant.expected_task,
            "expected_alias": alias,
        },
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        _jsonl_for_prompt_bound_tool_call(variant),
        prompt_packet=prompt_packet,
    )
    return proof.build_official_mcp_admission_case_packet(
        variant=variant,
        config_packet=config_packet,
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        entry_hook_evidence=evidence,
        codex_exec_exit_code=0,
        codex_exec_machine_error_code="OK",
        codex_mcp_get_exit_code=0,
        uses_danger_full_access=False,
        uses_dangerously_bypass=False,
    )


def _natural_variant(alias: str, prompt: str) -> proof.OfficialMcpAdmissionVariant:
    return proof.OfficialMcpAdmissionVariant(
        name=f"strict_natural_{alias.replace(' ', '_').casefold()}",
        prompt=prompt,
        expected_alias=alias,
        coding_aliases=("DIP", "Agent 2", "Worker"),
        expect_positive_proof=True,
        intent_kind=proof.INTENT_STRICT_NATURAL,
        bind_expected_delegate_arguments=False,
    )


def _natural_case_packet(
    alias: str,
    prompt: str,
    *,
    tool_arguments: dict[str, str] | None = None,
) -> dict[str, object]:
    variant = _natural_variant(alias, prompt)
    arguments = (
        tool_arguments
        if tool_arguments is not None
        else {
            "task": proof._strict_natural_delegated_task(prompt, alias),
            "expected_alias": alias,
        }
    )
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        profile_dir = root / "profile"
        proof.write_runtime_context(profile_dir, variant)
        delegate_packet = mcp_delegate.build_delegate_to_dip_packet(
            arguments,
            env={"WBP_PROFILE_DIR": str(profile_dir)},
            mcp_tool_called=True,
        )
        evidence = mcp_delegate._entry_hook_evidence_packet(delegate_packet)
    config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
        "",
        MCP_GET_STDOUT,
        list_exit_code=0,
        get_exit_code=0,
    )
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        variant.prompt,
        source="codex_exec_json",
        expected_delegate_arguments=proof._expected_delegate_arguments(variant),
        intent_claim=proof.build_natural_intent_claim_packet(variant),
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        _jsonl_for_prompt_bound_tool_call(variant, arguments=arguments),
        prompt_packet=prompt_packet,
    )
    return proof.build_official_mcp_admission_case_packet(
        variant=variant,
        config_packet=config_packet,
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        entry_hook_evidence=evidence,
        codex_exec_exit_code=0,
        codex_exec_machine_error_code="OK",
        codex_mcp_get_exit_code=0,
        uses_danger_full_access=False,
        uses_dangerously_bypass=False,
    )


def _natural_negative_case_packet(name: str) -> dict[str, object]:
    variant = proof.OfficialMcpAdmissionVariant(
        name=name,
        prompt="Сделай короткий план проверки.",
        expected_alias="",
        coding_aliases=("DIP", "Agent 2", "Worker"),
        expect_positive_proof=False,
        intent_kind=proof.INTENT_NO_ALIAS_NEGATIVE,
        bind_expected_delegate_arguments=False,
    )
    config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
        "",
        MCP_GET_STDOUT,
        list_exit_code=0,
        get_exit_code=0,
    )
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        variant.prompt,
        source="codex_exec_json",
        expected_delegate_arguments=proof._expected_delegate_arguments(variant),
        intent_claim=proof.build_natural_intent_claim_packet(variant),
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        "",
        prompt_packet=prompt_packet,
    )
    return proof.build_official_mcp_admission_case_packet(
        variant=variant,
        config_packet=config_packet,
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        entry_hook_evidence={},
        codex_exec_exit_code=0,
        codex_exec_machine_error_code="OK",
        codex_mcp_get_exit_code=0,
        uses_danger_full_access=False,
        uses_dangerously_bypass=False,
    )


def _ambiguous_natural_case_packet() -> dict[str, object]:
    variant = proof.OfficialMcpAdmissionVariant(
        name="ambiguous_loose_semantic",
        prompt="Пусть второй агент посмотрит это.",
        expected_alias="Agent 2",
        coding_aliases=("DIP", "Agent 2", "Worker"),
        expect_positive_proof=True,
        intent_kind=proof.INTENT_AMBIGUOUS_NATURAL,
        required_for_natural_matrix=False,
        bind_expected_delegate_arguments=False,
    )
    config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
        "",
        MCP_GET_STDOUT,
        list_exit_code=0,
        get_exit_code=0,
    )
    prompt_packet = mcp_delegate.build_prompt_observation_packet(
        variant.prompt,
        source="codex_exec_json",
        expected_delegate_arguments=proof._expected_delegate_arguments(variant),
        intent_claim=proof.build_natural_intent_claim_packet(variant),
    )
    codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
        "",
        prompt_packet=prompt_packet,
    )
    return proof.build_official_mcp_admission_case_packet(
        variant=variant,
        config_packet=config_packet,
        prompt_packet=prompt_packet,
        codex_tool_call_packet=codex_packet,
        entry_hook_evidence={},
        codex_exec_exit_code=0,
        codex_exec_machine_error_code="OK",
        codex_mcp_get_exit_code=0,
        uses_danger_full_access=False,
        uses_dangerously_bypass=False,
    )


class OfficialMcpAdmissionProofTests(unittest.TestCase):
    def test_codex_mcp_config_overrides_are_per_tool_and_bounded(self) -> None:
        overrides = proof.codex_mcp_config_overrides(
            profile_dir=Path("/tmp/wbp-profile"),
            evidence_path=Path("/tmp/wbp-evidence.json"),
            per_tool_approval=True,
            approval_policy="never",
            repo_root=Path("/repo"),
        )
        joined = "\n".join(overrides)

        self.assertIn('mcp_servers.wbp.command="python3"', joined)
        self.assertIn('mcp_servers.wbp.args=["-m","wild_boar_proxy.mcp_delegate"]', joined)
        self.assertIn('mcp_servers.wbp.enabled_tools=["delegate_to_dip"]', joined)
        self.assertIn(
            'mcp_servers.wbp.tools.delegate_to_dip.approval_mode="approve"',
            joined,
        )
        self.assertIn('approval_policy="never"', joined)
        self.assertIn('PYTHONPATH="/repo"', joined)
        self.assertIn('WBP_PROFILE_DIR="/tmp/wbp-profile"', joined)
        self.assertIn(
            'WBP_ENTRY_HOOK_EVIDENCE_PATH="/tmp/wbp-evidence.json"',
            joined,
        )
        self.assertNotIn("default_tools_approval_mode", joined)
        self.assertNotIn("danger-full-access", joined)
        self.assertNotIn("dangerously-bypass", joined)

    def test_natural_prompt_classifier_marks_explicit_tool_instructions(self) -> None:
        self.assertFalse(
            proof.explicit_tool_instruction_used(
                "Codex, дай задачу DIP: верни короткий план."
            )
        )
        self.assertTrue(
            proof.explicit_tool_instruction_used(
                "Call the WBP MCP tool delegate_to_dip exactly once."
            )
        )
        self.assertTrue(
            proof.prompt_has_expected_alias(
                "Agent 2, проверь контракт допуска WBP.",
                "Agent 2",
            )
        )

    def test_natural_intent_claim_classifies_loose_semantic_as_blocked(self) -> None:
        variant = proof.OfficialMcpAdmissionVariant(
            name="ambiguous_loose_semantic",
            prompt="Пусть второй агент посмотрит это.",
            expected_alias="Agent 2",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
            intent_kind=proof.INTENT_AMBIGUOUS_NATURAL,
            bind_expected_delegate_arguments=False,
        )

        packet = proof.build_natural_intent_claim_packet(variant)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], proof.NATURAL_INTENT_AMBIGUOUS)
        self.assertEqual(packet["natural_command_shape"], proof.NATURAL_SHAPE_LOOSE_SEMANTIC_TASK)
        self.assertEqual(packet["binding_status"], proof.NATURAL_REQUIRES_HOOK_INTERCEPTOR)
        self.assertEqual(packet["canonicalization_rule_id"], proof.CANON_RULE_UNSUPPORTED)
        self.assertFalse(packet["canonicalization_supported"])
        self.assertFalse(packet["intent_claim_digest_present"])
        self.assertFalse(packet["delegated_task_digest_present"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_task_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_case_requires_codex_tool_call_and_entry_hook_evidence(self) -> None:
        packet = _positive_case_packet("DIP")

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.OFFICIAL_MCP_ADMISSION_CASE_PACKET_KIND,
        )
        self.assertTrue(packet["expectation_met"])
        self.assertTrue(packet["positive_proof"])
        self.assertTrue(packet["codex_mcp_tool_called"])
        self.assertTrue(packet["delegate_to_dip_called"])
        self.assertTrue(packet["alias_context_read"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertTrue(packet["selected_alias_matches_expected"])
        self.assertEqual(packet["selected_alias_lane"], "api_route")
        self.assertTrue(packet["allowed_api_route_ids_enforced"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["uses_danger_full_access"])
        self.assertFalse(packet["uses_dangerously_bypass"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_natural_case_routes_without_explicit_tool_instruction(self) -> None:
        packet = _natural_case_packet(
            "Worker",
            "Worker, сделай короткий план проверки.",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["natural_prompt_used"])
        self.assertTrue(packet["strict_natural_prompt"])
        self.assertFalse(packet["explicit_tool_instruction_used"])
        self.assertTrue(packet["expected_alias_present_in_prompt"])
        self.assertTrue(packet["natural_alias_intent_routed"])
        self.assertEqual(packet["natural_alias_intent_result"], "routed")
        self.assertTrue(packet["prompt_to_mcp_call_bound"])
        self.assertEqual(packet["prompt_binding_mode"], "natural_intent_claim")
        self.assertTrue(packet["intent_claim_digest_present"])
        self.assertTrue(packet["intent_claim_digest_bound"])
        self.assertTrue(packet["delegated_task_digest_present"])
        self.assertEqual(packet["delegated_task_source"], "natural_prompt_parser")
        self.assertEqual(packet["natural_command_shape"], proof.NATURAL_SHAPE_COLON_DELIMITED_TASK)
        self.assertEqual(packet["binding_status"], proof.NATURAL_BINDING_SUPPORTED)
        self.assertEqual(
            packet["canonicalization_rule_id"],
            proof.CANON_RULE_COLON_DELIMITED_EXACT,
        )
        self.assertTrue(packet["canonicalization_supported"])
        self.assertTrue(packet["canonicalization_input_digest_present"])
        self.assertTrue(packet["canonicalization_output_digest_present"])
        self.assertTrue(packet["tool_call_task_matches_intent"])
        self.assertFalse(packet["prompt_task_digest_matched"])
        self.assertEqual(packet["selected_alias"], "Worker")
        self.assertTrue(packet["selected_alias_matches_expected"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_task_recorded"])
        self.assertFalse(packet["raw_jsonl_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_natural_quoted_payload_binds_after_unwrap(self) -> None:
        marker = "WBP_QUOTED_PAYLOAD_TEST"
        prompt = f'Codex, дай задачу DIP: "{marker}"'
        packet = _natural_case_packet(
            "DIP",
            prompt,
            tool_arguments={"task": marker, "expected_alias": "DIP"},
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["positive_proof"])
        self.assertEqual(packet["natural_command_shape"], proof.NATURAL_SHAPE_QUOTED_PAYLOAD)
        self.assertEqual(packet["binding_status"], proof.NATURAL_BINDING_SUPPORTED)
        self.assertEqual(
            packet["canonicalization_rule_id"],
            proof.CANON_RULE_QUOTED_PAYLOAD_UNWRAP,
        )
        self.assertTrue(packet["canonicalization_supported"])
        self.assertTrue(packet["intent_claim_digest_bound"])
        self.assertTrue(packet["tool_call_task_matches_intent"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_task_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertNotIn(marker, json.dumps(packet, ensure_ascii=False))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_natural_full_prompt_echo_does_not_bypass_intent_binding(self) -> None:
        prompt = "Worker, сделай короткий план проверки."
        packet = _natural_case_packet(
            "Worker",
            prompt,
            tool_arguments={"task": prompt, "expected_alias": "Worker"},
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.NATURAL_MCP_TOOL_CALL_NOT_BOUND,
        )
        self.assertFalse(packet["positive_proof"])
        self.assertFalse(packet["natural_alias_intent_routed"])
        self.assertEqual(packet["prompt_binding_mode"], "natural_intent_claim")
        self.assertFalse(packet["prompt_to_mcp_call_bound"])
        self.assertTrue(packet["intent_claim_digest_present"])
        self.assertFalse(packet["intent_claim_digest_bound"])
        self.assertTrue(packet["delegated_task_digest_present"])
        self.assertFalse(packet["tool_call_task_matches_intent"])
        self.assertTrue(packet["prompt_task_digest_matched"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["raw_task_recorded"])
        self.assertIn("intent_claim_digest_not_bound", packet["proof_blocking_reasons"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_strict_natural_exact_task_binds_to_intent_digest(self) -> None:
        marker = "WBP_NATURAL_BINDING_CORE_PROOF_TEST"
        prompt = f"Codex, дай задачу DIP: Ответь ровно строкой: {marker}"
        packet = _natural_case_packet(
            "DIP",
            prompt,
            tool_arguments={
                "task": f"Ответь ровно строкой: {marker}",
                "expected_alias": "DIP",
            },
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["positive_proof"])
        self.assertTrue(packet["natural_alias_intent_routed"])
        self.assertEqual(packet["natural_command_shape"], proof.NATURAL_SHAPE_EXACT_STABLE_TASK)
        self.assertEqual(packet["binding_status"], proof.NATURAL_BINDING_SUPPORTED)
        self.assertEqual(
            packet["canonicalization_rule_id"],
            proof.CANON_RULE_EXACT_STABLE_TASK,
        )
        self.assertEqual(packet["prompt_binding_mode"], "natural_intent_claim")
        self.assertTrue(packet["prompt_to_mcp_call_bound"])
        self.assertTrue(packet["intent_claim_digest_bound"])
        self.assertTrue(packet["tool_call_task_matches_intent"])
        self.assertFalse(packet["prompt_task_digest_matched"])
        self.assertEqual(packet["delegated_task_candidate_digest_count"], 1)
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_task_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertNotIn(marker, json.dumps(packet, ensure_ascii=False))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_natural_tool_call_without_prompt_binding_is_specific_red(self) -> None:
        prompt = "Codex, дай задачу DIP: верни короткий план."
        packet = _natural_case_packet(
            "DIP",
            prompt,
            tool_arguments={
                "task": "DIP: верни короткий план.",
                "expected_alias": "DIP",
            },
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.NATURAL_MCP_TOOL_CALL_NOT_BOUND,
        )
        self.assertEqual(
            packet["proof_machine_error_code"],
            proof.NATURAL_MCP_TOOL_CALL_NOT_BOUND,
        )
        self.assertFalse(packet["positive_proof"])
        self.assertTrue(packet["natural_prompt_used"])
        self.assertTrue(packet["strict_natural_prompt"])
        self.assertFalse(packet["explicit_tool_instruction_used"])
        self.assertTrue(packet["codex_mcp_tool_called"])
        self.assertTrue(packet["delegate_to_dip_tool_call_completed"])
        self.assertFalse(packet["prompt_to_mcp_call_bound"])
        self.assertTrue(packet["tool_call_completed_but_prompt_not_bound"])
        self.assertTrue(packet["natural_mcp_tool_call_unbound"])
        self.assertEqual(packet["prompt_binding_mode"], "natural_intent_claim")
        self.assertTrue(packet["intent_claim_digest_present"])
        self.assertFalse(packet["intent_claim_digest_bound"])
        self.assertTrue(packet["delegated_task_digest_present"])
        self.assertFalse(packet["tool_call_task_matches_intent"])
        self.assertTrue(packet["tool_call_digest_present"])
        self.assertFalse(packet["expected_delegate_tool_call_digest_present"])
        self.assertFalse(packet["prompt_task_digest_matched"])
        self.assertTrue(packet["prompt_digest_present"])
        self.assertTrue(packet["codex_tool_call_claim_digest_present"])
        self.assertTrue(packet["alias_context_read"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertTrue(packet["selected_alias_matches_expected"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["raw_task_recorded"])
        self.assertFalse(packet["raw_jsonl_recorded"])
        self.assertFalse(packet["product_ready"])
        self.assertIn(
            "prompt_not_bound_to_codex_mcp_tool_call",
            packet["proof_blocking_reasons"],
        )
        self.assertNotIn(prompt, json.dumps(packet, ensure_ascii=False))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_natural_case_blocks_alias_collapse_to_dip(self) -> None:
        packet = _natural_case_packet(
            "Worker",
            "Worker, сделай короткий план проверки.",
            tool_arguments={
                "task": "Worker, сделай короткий план проверки.",
                "expected_alias": "DIP",
            },
        )

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.OFFICIAL_MCP_ALIAS_MISMATCH,
        )
        self.assertFalse(packet["positive_proof"])
        self.assertFalse(packet["natural_alias_intent_routed"])
        self.assertEqual(packet["selected_alias"], "DIP")
        self.assertFalse(packet["selected_alias_matches_expected"])
        self.assertIn(
            "selected_alias_did_not_match_expected_alias",
            packet["proof_blocking_reasons"],
        )
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_negative_case_without_approval_fails_closed_not_positive(self) -> None:
        variant = proof.OfficialMcpAdmissionVariant(
            name="negative_no_approval_policy_never",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=False,
            per_tool_approval=False,
            approval_policy="never",
        )
        config_packet = mcp_delegate.build_codex_mcp_config_probe_packet(
            "",
            MCP_GET_STDOUT,
            list_exit_code=0,
            get_exit_code=0,
        )
        prompt_packet = mcp_delegate.build_prompt_observation_packet(
            variant.prompt,
            source="codex_exec_json",
            expected_delegate_arguments={"task": variant.prompt, "expected_alias": "DIP"},
        )
        codex_packet = mcp_delegate.build_codex_exec_tool_call_observation_packet(
            "",
            prompt_packet=prompt_packet,
        )

        packet = proof.build_official_mcp_admission_case_packet(
            variant=variant,
            config_packet=config_packet,
            prompt_packet=prompt_packet,
            codex_tool_call_packet=codex_packet,
            entry_hook_evidence={},
            codex_exec_exit_code=0,
            codex_exec_machine_error_code="OK",
            codex_mcp_get_exit_code=0,
            uses_danger_full_access=False,
            uses_dangerously_bypass=False,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["expectation_met"])
        self.assertFalse(packet["positive_proof"])
        self.assertTrue(packet["fail_closed"])
        self.assertFalse(packet["codex_mcp_tool_called"])
        self.assertIn(
            "codex_delegate_to_dip_tool_call_not_observed",
            packet["proof_blocking_reasons"],
        )
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["uses_danger_full_access"])
        self.assertFalse(packet["uses_dangerously_bypass"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_matrix_requires_three_alias_positives_and_three_fail_closed_negatives(self) -> None:
        positives = [_positive_case_packet(alias) for alias in ("DIP", "Agent 2", "Worker")]
        negatives = []
        for index in range(3):
            negative = dict(positives[0])
            negative.update(
                {
                    "variant": f"negative_{index}",
                    "expect_positive_proof": False,
                    "expectation_met": True,
                    "positive_proof": False,
                    "fail_closed": True,
                    "codex_mcp_tool_called": False,
                    "delegate_to_dip_called": False,
                    "api_lane_called": False,
                    "route_bound_dispatch_proven": False,
                }
            )
            negatives.append(negative)

        packet = proof.build_official_mcp_admission_matrix_packet(positives + negatives)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["final_status"], "FEATURE_CORE_PROOF_POSITIVE")
        self.assertTrue(packet["required_aliases_proven"])
        self.assertEqual(packet["negative_fail_closed_count"], 3)
        self.assertTrue(packet["no_dangerous_modes"])
        self.assertTrue(packet["no_raw_recording"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_natural_matrix_reports_green_for_strict_aliases_and_fail_closed_negatives(self) -> None:
        positives = [
            _natural_case_packet("DIP", "Codex, дай задачу DIP: верни короткий план."),
            _natural_case_packet("Agent 2", "Agent 2, проверь контракт допуска WBP."),
            _natural_case_packet("Worker", "Worker, сделай короткий план проверки."),
        ]
        negatives = [
            _natural_negative_case_packet("negative_no_approval"),
            _natural_negative_case_packet("negative_missing_context"),
            _natural_negative_case_packet("negative_route_outside_allowlist"),
            _natural_negative_case_packet("negative_no_alias_prompt"),
        ]

        packet = proof.build_natural_alias_intent_matrix_packet(positives + negatives)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(
            packet["final_status"],
            "NATURAL_ALIAS_INTENT_CORE_PROOF_POSITIVE",
        )
        self.assertEqual(packet["natural_alias_intent_result"], "green")
        self.assertEqual(packet["strict_success_count"], 3)
        self.assertEqual(packet["negative_fail_closed_count"], 4)
        self.assertTrue(packet["required_aliases_proven"])
        self.assertEqual(packet["alias_mismatch_count"], 0)
        self.assertTrue(packet["explicit_tool_instruction_absent_in_strict"])
        self.assertTrue(packet["no_dangerous_modes"])
        self.assertTrue(packet["no_raw_recording"])
        self.assertFalse(packet["product_ready"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_natural_matrix_reports_command_class_breakdown(self) -> None:
        exact = _natural_case_packet(
            "DIP",
            "Codex, дай задачу DIP: Ответь ровно строкой: WBP_MATRIX_EXACT_TEST",
            tool_arguments={
                "task": "Ответь ровно строкой: WBP_MATRIX_EXACT_TEST",
                "expected_alias": "DIP",
            },
        )
        quoted = _natural_case_packet(
            "DIP",
            'Codex, дай задачу DIP: "WBP_MATRIX_QUOTED_TEST"',
            tool_arguments={"task": "WBP_MATRIX_QUOTED_TEST", "expected_alias": "DIP"},
        )
        colon = _natural_case_packet(
            "Worker",
            "Worker, сделай короткий план проверки.",
        )
        loose = _ambiguous_natural_case_packet()
        negative = _natural_negative_case_packet("negative_no_alias_prompt")

        packet = proof.build_natural_alias_intent_matrix_packet(
            [exact, quoted, colon, loose, negative]
        )
        summaries = {
            summary["class_name"]: summary
            for summary in packet["natural_command_class_summaries"]
        }

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["natural_command_class_count"], 5)
        self.assertEqual(
            summaries[proof.NATURAL_SHAPE_EXACT_STABLE_TASK]["proof_status"],
            "binding_supported",
        )
        self.assertEqual(
            summaries[proof.NATURAL_SHAPE_QUOTED_PAYLOAD]["proof_status"],
            "binding_supported",
        )
        self.assertEqual(
            summaries[proof.NATURAL_SHAPE_COLON_DELIMITED_TASK]["proof_status"],
            "binding_supported",
        )
        self.assertEqual(
            summaries[proof.NATURAL_SHAPE_LOOSE_SEMANTIC_TASK]["proof_status"],
            "binding_blocked",
        )
        self.assertIn(
            proof.NATURAL_REQUIRES_HOOK_INTERCEPTOR,
            summaries[proof.NATURAL_SHAPE_LOOSE_SEMANTIC_TASK]["binding_statuses"],
        )
        self.assertEqual(
            summaries[proof.NATURAL_SHAPE_AMBIGUOUS_UNSAFE_TASK]["proof_status"],
            "binding_blocked",
        )
        self.assertIn(
            proof.NATURAL_AMBIGUOUS_FAIL_CLOSED,
            summaries[proof.NATURAL_SHAPE_AMBIGUOUS_UNSAFE_TASK]["binding_statuses"],
        )
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_natural_matrix_reports_partial_for_some_strict_routing(self) -> None:
        routed = _natural_case_packet(
            "DIP",
            "Codex, дай задачу DIP: верни короткий план.",
        )
        failed_worker = dict(
            _natural_negative_case_packet("strict_worker_not_routed")
        )
        failed_worker.update(
            {
                "intent_kind": proof.INTENT_STRICT_NATURAL,
                "strict_natural_prompt": True,
                "no_alias_negative_prompt": False,
                "expect_positive_proof": True,
                "expected_alias": "Worker",
                "required_for_natural_matrix": True,
            }
        )
        failed_agent = dict(failed_worker)
        failed_agent.update({"variant": "strict_agent_2_not_routed", "expected_alias": "Agent 2"})
        negatives = [_natural_negative_case_packet("negative_no_alias_prompt")]

        packet = proof.build_natural_alias_intent_matrix_packet(
            [routed, failed_worker, failed_agent, *negatives]
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["final_status"], "NATURAL_ALIAS_INTENT_PARTIAL")
        self.assertEqual(packet["natural_alias_intent_result"], "partial")
        self.assertEqual(packet["strict_success_count"], 1)
        self.assertFalse(packet["required_aliases_proven"])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_natural_matrix_reports_red_when_no_strict_prompt_routes(self) -> None:
        failed_cases = []
        for alias in ("DIP", "Agent 2", "Worker"):
            failed = dict(_natural_negative_case_packet(f"strict_{alias}_not_routed"))
            failed.update(
                {
                    "intent_kind": proof.INTENT_STRICT_NATURAL,
                    "strict_natural_prompt": True,
                    "no_alias_negative_prompt": False,
                    "expect_positive_proof": True,
                    "expected_alias": alias,
                    "required_for_natural_matrix": True,
                }
            )
            failed_cases.append(failed)

        packet = proof.build_natural_alias_intent_matrix_packet(failed_cases)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["final_status"], "NATURAL_ALIAS_INTENT_NOT_PROVEN")
        self.assertEqual(packet["natural_alias_intent_result"], "red")
        self.assertEqual(packet["strict_success_count"], 0)
        self.assertEqual(packet["natural_tool_call_count"], 0)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_run_case_uses_per_tool_approval_and_sanitized_entry_hook_evidence(self) -> None:
        variant = proof.OfficialMcpAdmissionVariant(
            name="positive_dip_per_tool_approve",
            prompt="Codex, дай задачу DIP: верни короткий план.",
            expected_alias="DIP",
            coding_aliases=("DIP", "Agent 2", "Worker"),
            expect_positive_proof=True,
        )
        commands: list[list[str]] = []

        def fake_mcp_get(
            *,
            codex_bin: Path,
            env: dict[str, str],
            config_overrides: list[str],
            timeout_seconds: int,
        ) -> BoundedProcessResult:
            commands.append([str(codex_bin), "mcp", *config_overrides])
            self.assertEqual(env["CODEX_HOME"], str(codex_home))
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("CODEX_API_KEY", env)
            self.assertIn(
                'mcp_servers.wbp.tools.delegate_to_dip.approval_mode="approve"',
                "\n".join(config_overrides),
            )
            self.assertNotIn("default_tools_approval_mode", "\n".join(config_overrides))
            return _process_result(stdout=MCP_GET_STDOUT)

        def fake_codex_exec(
            *,
            codex_bin: Path,
            env: dict[str, str],
            config_overrides: list[str],
            model_id: str,
            prompt: str,
            workdir: Path,
            timeout_seconds: int,
        ) -> BoundedProcessResult:
            commands.append([str(codex_bin), "exec", "-m", model_id, *config_overrides])
            self.assertEqual(model_id, proof.DEFAULT_CODEX_MODEL_ID)
            profile_dir = _profile_path_from_overrides(config_overrides)
            evidence_path = _evidence_path_from_overrides(config_overrides)
            mcp_delegate.handle_jsonrpc_message(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "delegate_to_dip",
                        "arguments": {
                            "task": variant.expected_task or prompt,
                            "expected_alias": variant.expected_alias,
                        },
                    },
                },
                env={
                    "WBP_PROFILE_DIR": str(profile_dir),
                    mcp_delegate.ENTRY_HOOK_EVIDENCE_ENV_PATH: str(evidence_path),
                },
            )
            return _process_result(stdout=_jsonl_for_prompt_bound_tool_call(variant))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = root / "codex-home"
            proof_root = root / "proof"
            codex_home.mkdir()
            with (
                mock.patch(
                    "wild_boar_proxy.official_mcp_admission_proof._run_codex_mcp_get",
                    side_effect=fake_mcp_get,
                ),
                mock.patch(
                    "wild_boar_proxy.official_mcp_admission_proof._run_codex_exec",
                    side_effect=fake_codex_exec,
                ),
            ):
                packet = proof.run_official_mcp_admission_case(
                    variant=variant,
                    codex_home=codex_home,
                    proof_root=proof_root,
                    codex_bin=Path("/usr/local/bin/codex"),
                    model_id=proof.DEFAULT_CODEX_MODEL_ID,
                    timeout_seconds=3,
                )

            case_packet_path = proof_root / variant.name / "case-packet.json"
            evidence_path = proof_root / variant.name / "entry-hook-evidence.json"
            case_packet_exists = case_packet_path.exists()
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

        self.assertTrue(commands)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["positive_proof"])
        self.assertTrue(packet["codex_mcp_tool_called"])
        self.assertTrue(packet["api_lane_called"])
        self.assertFalse(packet["raw_jsonl_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertTrue(case_packet_exists)
        self.assertEqual(evidence["packet_kind"], "wbp_entry_hook_tool_call_evidence")
        self.assertNotIn(variant.prompt, json.dumps(evidence, ensure_ascii=False))
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
