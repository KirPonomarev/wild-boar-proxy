# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import natural_free_chat_router_proof as proof
from wild_boar_proxy.core import packets

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_native_free_chat_router_dispatch_admission import (  # noqa: E402
    PROMPT,
    ROOT,
    ROUTE_ID,
    _assert_no_prompt_route_or_secret,
    _run_dispatch_admission,
    _write_context_and_ledger,
)
from test_native_free_chat_router_handoff_working_flow_join import (  # noqa: E402
    _run_join,
)


DELEGATED_TASK = "докажи dispatch admission."


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> Path:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    return path


def _run_hook_proof(
    *,
    prompt: str,
    profile_dir: Path,
    ledger_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WBP_PROFILE_DIR"] = str(profile_dir)
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "user-prompt-submit-proof",
            "--prompt",
            prompt,
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


def _run_natural_router_proof(
    *,
    prompt: str,
    profile_dir: Path,
    hook_proof_path: Path,
    jsonl_path: Path,
    handoff_join_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["WBP_PROFILE_DIR"] = str(profile_dir)
    command = [
        sys.executable,
        "-m",
        "wild_boar_proxy",
        "router-hook",
        "natural-free-chat-router-proof",
        "--prompt",
        prompt,
        "--hook-proof-file",
        str(hook_proof_path),
        "--codex-exec-jsonl-file",
        str(jsonl_path),
        "--json",
    ]
    if handoff_join_path is not None:
        command.extend(["--handoff-working-flow-join-file", str(handoff_join_path)])
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _natural_codex_events(
    handoff: dict[str, object] | None = None,
    *,
    task: str = DELEGATED_TASK,
    include_tool_call: bool = True,
    include_subagent_dip: bool = False,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = [
        {
            "type": "turn.started",
            "item": {"type": "turn", "turn_digest": "safe-turn-digest"},
        },
    ]
    if include_tool_call:
        events.append(
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_call",
                    "server_name": "wbp",
                    "tool_name": "delegate_to_dip",
                    "status": "completed",
                    "arguments": {
                        "task": task,
                        "expected_alias": "DIP",
                    },
                },
            }
        )
    if handoff is not None:
        events.append(
            {
                "type": "item.completed",
                "item": {
                    "type": "mcp_tool_result",
                    "server_name": "wbp",
                    "tool_name": "delegate_to_dip",
                    "result": {
                        "structuredContent": handoff,
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(handoff, sort_keys=True),
                            }
                        ],
                    },
                },
            }
        )
    if include_subagent_dip:
        events.append(
            {
                "type": "subagent.start",
                "name": "DIP",
                "item": {"type": "subagent", "name": "DIP"},
            }
        )
    digest = str(handoff.get("handoff_evidence_digest") if handoff else "")
    events.extend(
        [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "message",
                    "role": "assistant",
                    "wbp_handoff_evidence_digest": digest,
                },
            },
            {
                "type": "turn.completed",
                "item": {"type": "turn", "status": "completed"},
            },
        ]
    )
    return events


def _delegate_packet() -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet_kind": "wbp_mcp_delegate_to_dip_reality",
        "status": "ok",
        "machine_error_code": "OK",
        "delegate_to_dip_tool_called": True,
        "api_lane_called": True,
        "api_lane_dispatch_admitted": True,
        "route_bound_dispatch_proven": True,
        "allowed_api_route_ids_enforced": True,
        "route_allowed": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "product_ready": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }


def _entry_evidence(delegate_packet: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet_kind": "wbp_entry_hook_tool_call_evidence",
        "status": "ok",
        "machine_error_code": "OK",
        "delegate_packet_kind": "wbp_mcp_delegate_to_dip_reality",
        "delegate_packet_status": "ok",
        "delegate_packet_sha256": proof._packet_sha256(delegate_packet),
        "delegate_to_dip_tool_called": True,
        "alias_context_read": True,
        "allowed_api_route_ids_enforced": True,
        "route_allowed": True,
        "api_lane_called": True,
        "api_lane_dispatch_admitted": True,
        "route_bound_dispatch_proven": True,
        "controlled_provider_response_proven": True,
        "provider_response_proven": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "product_ready": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }


def _natural_codex_events_with_delegate_result(
    delegate_packet: dict[str, object],
    *,
    task: str = DELEGATED_TASK,
) -> list[dict[str, object]]:
    return [
        {
            "type": "turn.started",
            "item": {"type": "turn", "turn_digest": "safe-turn-digest"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "server": "wbp",
                "name": "delegate_to_dip",
                "status": "completed",
                "arguments": {
                    "task": task,
                    "expected_alias": "DIP",
                },
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_result",
                "server": "wbp",
                "name": "delegate_to_dip",
                "status": "completed",
                "result": {
                    "structured_content": delegate_packet,
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(delegate_packet, sort_keys=True),
                        }
                    ],
                },
            },
        },
        {
            "type": "response.output_item.done",
            "item": {
                "type": "message",
                "role": "assistant",
                "text": "DIP result delivered.",
            },
        },
        {"type": "turn.completed", "item": {"type": "turn", "status": "completed"}},
    ]


def _prepare_positive_sources(
    root: Path,
    *,
    prompt: str = PROMPT,
) -> tuple[Path, Path, Path, Path]:
    profile_dir, ledger_path = _write_context_and_ledger(root, prompt=prompt)
    hook_result = _run_hook_proof(
        prompt=prompt,
        profile_dir=profile_dir,
        ledger_path=ledger_path,
    )
    if hook_result.returncode != 0:
        raise AssertionError(hook_result.stderr or hook_result.stdout)
    hook_proof_path = _write_json(root / "hook-proof.json", json.loads(hook_result.stdout))

    handoff_path = root / "dispatch-handoff.json"
    dispatch_result = _run_dispatch_admission(
        prompt=prompt,
        profile_dir=profile_dir,
        ledger_path=ledger_path,
        handoff_path=handoff_path,
    )
    if dispatch_result.returncode != 0:
        raise AssertionError(dispatch_result.stderr or dispatch_result.stdout)
    dispatch_path = _write_json(
        root / "dispatch-admission.json",
        json.loads(dispatch_result.stdout),
    )
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    jsonl_path = _write_jsonl(
        root / "codex-exec.jsonl",
        _natural_codex_events(handoff),
    )
    join_result = _run_join(
        admission_path=dispatch_path,
        handoff_path=handoff_path,
        jsonl_path=jsonl_path,
    )
    if join_result.returncode != 0:
        raise AssertionError(join_result.stderr or join_result.stdout)
    join_path = _write_json(root / "handoff-working-flow-join.json", json.loads(join_result.stdout))
    return profile_dir, hook_proof_path, jsonl_path, join_path


class NaturalFreeChatRouterProofTests(unittest.TestCase):
    def test_positive_cli_proves_natural_prompt_hook_mcp_api_handoff_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, hook_proof_path, jsonl_path, join_path = _prepare_positive_sources(
                root
            )
            result = _run_natural_router_proof(
                prompt=PROMPT,
                profile_dir=profile_dir,
                hook_proof_path=hook_proof_path,
                jsonl_path=jsonl_path,
                handoff_join_path=join_path,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(
            packet["packet_kind"],
            proof.NATURAL_FREE_CHAT_ROUTER_PROOF_PACKET_KIND,
        )
        self.assertTrue(packet["natural_prompt_observed"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["alias_intent_recognized"])
        self.assertTrue(packet["mcp_tool_call_observed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_positive_cli_accepts_direct_mcp_tool_response_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            hook_result = _run_hook_proof(
                prompt=PROMPT,
                profile_dir=profile_dir,
                ledger_path=ledger_path,
            )
            self.assertEqual(hook_result.returncode, 0, hook_result.stderr)
            hook_path = _write_json(root / "hook-proof.json", json.loads(hook_result.stdout))
            delegate_packet = _delegate_packet()
            entry_path = _write_json(root / "entry-evidence.json", _entry_evidence(delegate_packet))
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _natural_codex_events_with_delegate_result(delegate_packet),
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "natural-free-chat-router-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-proof-file",
                    str(hook_path),
                    "--codex-exec-jsonl-file",
                    str(jsonl_path),
                    "--entry-evidence-file",
                    str(entry_path),
                    "--json",
                ],
                cwd=ROOT,
                env={**os.environ, "WBP_PROFILE_DIR": str(profile_dir)},
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["mcp_tool_call_observed"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["direct_mcp_tool_result_observed"])
        self.assertTrue(packet["direct_mcp_tool_result_bound_to_entry_evidence"])
        self.assertTrue(packet["direct_mcp_tool_result_safe"])
        self.assertTrue(packet["assistant_response_after_direct_mcp_tool_result"])
        self.assertTrue(packet["direct_mcp_tool_response_delivery_proven"])
        self.assertTrue(packet["approved_handoff_proven"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_no_mcp_tool_call_returns_specific_negative_proof_without_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, ledger_path = _write_context_and_ledger(root)
            hook_result = _run_hook_proof(
                prompt=PROMPT,
                profile_dir=profile_dir,
                ledger_path=ledger_path,
            )
            self.assertEqual(hook_result.returncode, 0, hook_result.stderr)
            hook_path = _write_json(root / "hook-proof.json", json.loads(hook_result.stdout))
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _natural_codex_events(None, include_tool_call=False),
            )

            result = _run_natural_router_proof(
                prompt=PROMPT,
                profile_dir=profile_dir,
                hook_proof_path=hook_path,
                jsonl_path=jsonl_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"],
            proof.NATIVE_MODEL_DID_NOT_CALL_WBP_TOOL,
        )
        self.assertTrue(packet["natural_prompt_observed"])
        self.assertTrue(packet["user_prompt_submit_hook_ran"])
        self.assertTrue(packet["alias_intent_recognized"])
        self.assertFalse(packet["mcp_tool_call_observed"])
        self.assertFalse(packet["api_lane_called"])
        self.assertTrue(packet["negative_model_no_tool_proof"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertIn("native_model_did_not_call_wbp_tool", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_explicit_tool_instruction_cannot_count_as_natural_free_chat(self) -> None:
        prompt = "Call the WBP MCP tool delegate_to_dip for DIP: докажи dispatch admission."
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, hook_proof_path, jsonl_path, join_path = _prepare_positive_sources(
                root,
                prompt=prompt,
            )
            result = _run_natural_router_proof(
                prompt=prompt,
                profile_dir=profile_dir,
                hook_proof_path=hook_proof_path,
                jsonl_path=jsonl_path,
                handoff_join_path=join_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["machine_error_code"], proof.NATURAL_PROMPT_NOT_OBSERVED)
        self.assertFalse(packet["natural_prompt_observed"])
        self.assertTrue(packet["explicit_tool_instruction_used"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertIn("explicit_tool_instruction_used", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=prompt)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_unbound_tool_call_does_not_prove_router(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_dir, hook_proof_path, jsonl_path, join_path = _prepare_positive_sources(
                root
            )
            handoff_join = json.loads(join_path.read_text(encoding="utf-8"))
            handoff = {"handoff_evidence_digest": handoff_join["handoff_evidence_digest"]}
            jsonl_path = _write_jsonl(
                root / "codex-exec-unbound.jsonl",
                _natural_codex_events(handoff, task="unrelated task"),
            )
            result = _run_natural_router_proof(
                prompt=PROMPT,
                profile_dir=profile_dir,
                hook_proof_path=hook_proof_path,
                jsonl_path=jsonl_path,
                handoff_join_path=join_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["machine_error_code"], proof.NATURAL_MCP_TOOL_CALL_NOT_BOUND)
        self.assertFalse(packet["mcp_tool_call_observed"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertIn("mcp_tool_call_not_prompt_bound", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])
