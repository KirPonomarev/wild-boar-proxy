# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy import cli as cli_mod
from wild_boar_proxy import native_free_chat_router_handoff_working_flow_join as join
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


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> Path:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    return path


def _codex_exec_events(
    handoff: dict[str, object],
    *,
    assistant_digest: str | None = None,
    include_subagent_dip: bool = False,
    tool_name: str = "delegate_to_dip",
    server_name: str = "wbp",
) -> list[dict[str, object]]:
    digest = str(handoff["handoff_evidence_digest"] if assistant_digest is None else assistant_digest)
    events: list[dict[str, object]] = [
        {
            "type": "turn.started",
            "item": {"type": "turn", "turn_digest": "safe-turn-digest"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_result",
                "server_name": server_name,
                "tool_name": tool_name,
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
        },
    ]
    if include_subagent_dip:
        events.append(
            {
                "type": "subagent.start",
                "name": "DIP",
                "item": {"type": "subagent", "name": "DIP"},
            }
        )
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


def _positive_admission(root: Path) -> tuple[Path, Path, dict[str, object], dict[str, object]]:
    profile_dir, ledger_path = _write_context_and_ledger(root)
    handoff_path = root / "dispatch-handoff.json"
    result = _run_dispatch_admission(
        prompt=PROMPT,
        profile_dir=profile_dir,
        ledger_path=ledger_path,
        handoff_path=handoff_path,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    admission_packet = json.loads(result.stdout)
    admission_path = _write_json(root / "dispatch-admission.json", admission_packet)
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    return admission_path, handoff_path, admission_packet, handoff


def _run_join(
    *,
    admission_path: Path,
    handoff_path: Path,
    jsonl_path: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "wild_boar_proxy",
            "router-hook",
            "handoff-working-flow-join",
            "--dispatch-admission-file",
            str(admission_path),
            "--dispatch-handoff-file",
            str(handoff_path),
            "--codex-exec-jsonl-file",
            str(jsonl_path),
            "--json",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class NativeFreeChatRouterHandoffWorkingFlowJoinTests(unittest.TestCase):
    def test_positive_cli_joins_dispatch_handoff_to_assistant_continuation_without_product_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            admission_path, handoff_path, _admission_packet, handoff = _positive_admission(
                root
            )
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _codex_exec_events(handoff),
            )
            result = _run_join(
                admission_path=admission_path,
                handoff_path=handoff_path,
                jsonl_path=jsonl_path,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], "OK")
        self.assertEqual(packet["effect"], "probe")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(
            packet["packet_kind"],
            join.HANDOFF_WORKING_FLOW_JOIN_PACKET_KIND,
        )
        self.assertTrue(packet["handoff_to_working_flow_join_proven"])
        self.assertTrue(packet["dispatch_admission_packet_read"])
        self.assertTrue(packet["dispatch_handoff_file_read"])
        self.assertTrue(packet["dispatch_admission_proven"])
        self.assertTrue(packet["dispatch_result_digest_bound"])
        self.assertTrue(packet["handoff_evidence_digest_bound"])
        self.assertTrue(packet["handoff_file_sha256_bound"])
        self.assertTrue(packet["approved_handoff_source_used"])
        self.assertTrue(packet["codex_exec_json_events_observed"])
        self.assertTrue(packet["dispatch_handoff_tool_result_observed"])
        self.assertTrue(packet["dispatch_handoff_tool_result_bound"])
        self.assertEqual(packet["mcp_server_name_observed"], "wbp")
        self.assertEqual(packet["mcp_tool_name_observed"], "delegate_to_dip")
        self.assertTrue(packet["assistant_response_after_handoff"])
        self.assertTrue(packet["assistant_continuation_bound_to_handoff"])
        self.assertTrue(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["custom_codex_ui_visibility_proven"])
        self.assertFalse(packet["delivery_counts_as_custom_codex_ui"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        self.assertFalse(packet["native_free_chat_router_product_ready"])
        self.assertFalse(packet["native_free_chat_router_delivery_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["does_not_prove_custom_codex_ui"])
        self.assertTrue(packet["does_not_prove_native_free_chat_router"])
        self.assertTrue(packet["does_not_prove_product_ready"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertFalse(packet["codex_native_subagent_used_as_dip"])
        self.assertEqual(packet["blocking_reasons"], [])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_tampered_handoff_file_blocks_join(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            admission_path, handoff_path, _admission_packet, handoff = _positive_admission(
                root
            )
            handoff["dispatch_result_digest"] = "0" * 64
            _write_json(handoff_path, handoff)
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _codex_exec_events(handoff),
            )
            result = _run_join(
                admission_path=admission_path,
                handoff_path=handoff_path,
                jsonl_path=jsonl_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["handoff_to_working_flow_join_proven"])
        self.assertFalse(packet["dispatch_result_digest_bound"])
        self.assertFalse(packet["handoff_evidence_digest_bound"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertIn("dispatch_result_digest_mismatch", packet["blocking_reasons"])
        self.assertIn("handoff_evidence_digest_mismatch", packet["blocking_reasons"])
        self.assertIn("handoff_file_sha256_mismatch", packet["blocking_reasons"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["native_free_chat_router_proven"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_assistant_digest_mismatch_blocks_working_flow_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            admission_path, handoff_path, _admission_packet, handoff = _positive_admission(
                root
            )
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _codex_exec_events(handoff, assistant_digest="1" * 64),
            )
            result = _run_join(
                admission_path=admission_path,
                handoff_path=handoff_path,
                jsonl_path=jsonl_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(packet["machine_error_code"], join.HANDOFF_WORKING_FLOW_JOIN_NOT_BOUND)
        self.assertFalse(packet["assistant_continuation_bound_to_handoff"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertTrue(packet["assistant_marker_digest_mismatch"])
        self.assertIn(
            "assistant_response_handoff_digest_mismatch",
            packet["blocking_reasons"],
        )
        self.assertIn("assistant_response_not_bound_to_handoff", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_subagent_named_dip_blocks_as_unsafe_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            admission_path, handoff_path, _admission_packet, handoff = _positive_admission(
                root
            )
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _codex_exec_events(handoff, include_subagent_dip=True),
            )
            result = _run_join(
                admission_path=admission_path,
                handoff_path=handoff_path,
                jsonl_path=jsonl_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(
            packet["machine_error_code"],
            join.HANDOFF_WORKING_FLOW_JOIN_PAYLOAD_UNSAFE,
        )
        self.assertFalse(packet["handoff_to_working_flow_join_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["native_codex_subagent_used_as_dip"])
        self.assertIn("native_codex_subagent_used_as_dip", packet["blocking_reasons"])
        self.assertIn(
            "native_codex_subagent_used_as_dip",
            packet["transcript_unsafe_failures"],
        )
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_source_overclaim_blocks_join_before_false_green(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            admission_path, handoff_path, admission_packet, handoff = _positive_admission(
                root
            )
            admission_packet["product_ready"] = True
            _write_json(admission_path, admission_packet)
            jsonl_path = _write_jsonl(
                root / "codex-exec.jsonl",
                _codex_exec_events(handoff),
            )
            result = _run_join(
                admission_path=admission_path,
                handoff_path=handoff_path,
                jsonl_path=jsonl_path,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            packet = json.loads(result.stdout)

        self.assertEqual(
            packet["machine_error_code"],
            join.HANDOFF_WORKING_FLOW_JOIN_DISPATCH_ADMISSION_INVALID,
        )
        self.assertFalse(packet["dispatch_admission_proven"])
        self.assertFalse(packet["handoff_to_working_flow_join_proven"])
        self.assertFalse(packet["codex_working_flow_delivery_proven"])
        self.assertFalse(packet["product_ready"])
        self.assertIn("product_ready_must_not_be_claimed", packet["blocking_reasons"])
        _assert_no_prompt_route_or_secret(self, packet, prompt=PROMPT)
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_effect_classifier_marks_join_as_probe(self) -> None:
        parser = cli_mod.build_parser()
        args = parser.parse_args(
            [
                "router-hook",
                "handoff-working-flow-join",
                "--dispatch-admission-file",
                "/tmp/wbp-dispatch-admission.json",
                "--dispatch-handoff-file",
                "/tmp/wbp-dispatch-handoff.json",
                "--codex-exec-jsonl-file",
                "/tmp/wbp-codex-exec.jsonl",
                "--json",
            ]
        )

        self.assertEqual(cli_mod.command_effect_from_args(args), "probe")


if __name__ == "__main__":
    unittest.main()
