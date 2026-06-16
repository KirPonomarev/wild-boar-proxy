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
) -> str:
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
