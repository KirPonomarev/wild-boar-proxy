# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.wbp_dip_tool import (
    DEFAULT_SANDBOX,
    WBP_DIP_TOOL_DRY_RUN,
    WBP_DIP_TOOL_OK,
    build_codex_exec_argv,
    build_delegate_prompt,
    build_wbp_dip_tool_packet,
)


TASK = "Codex, дай задачу DIP: проверь рабочий инструмент."


def _write_jsonl(path: Path, events: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=True) for event in events) + "\n",
        encoding="utf-8",
    )


def _delegate_packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "packet_kind": "wbp_mcp_delegate_to_dip_reality",
        "status": "ok",
        "machine_error_code": "OK",
        "delegate_to_dip_tool_called": True,
        "api_lane_called": True,
        "route_bound_dispatch_proven": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    packet.update(overrides)
    return packet


class WbpDipToolTests(unittest.TestCase):
    def test_build_codex_exec_argv_uses_custom_codex_mcp_delegate_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            prompt = build_delegate_prompt(task=TASK, expected_alias="DIP")
            argv = build_codex_exec_argv(
                codex_bin=root / "codex",
                repo_root=Path("/repo"),
                model="gpt-5.4",
                sandbox=DEFAULT_SANDBOX,
                prompt=prompt,
                output_jsonl=root / "codex.jsonl",
                output_last_message=root / "last.txt",
                profile_dir=root / "profile",
                entry_evidence_file=root / "entry.json",
            )

        self.assertIn("exec", argv)
        self.assertIn("--json", argv)
        self.assertIn("--sandbox", argv)
        self.assertIn(DEFAULT_SANDBOX, argv)
        self.assertIn("-m", argv)
        self.assertIn("gpt-5.4", argv)
        joined = "\n".join(argv)
        self.assertIn('mcp_servers.wbp.command="python3"', joined)
        self.assertIn("wild_boar_proxy.mcp_delegate", joined)
        self.assertIn("delegate_to_dip", joined)
        self.assertIn('approval_mode="approve"', joined)
        self.assertIn("WBP_PROFILE_DIR", joined)

    def test_packet_accepts_only_observed_delegate_api_lane(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            jsonl = root / "codex.jsonl"
            last = root / "last.txt"
            entry = root / "entry.json"
            _write_jsonl(
                jsonl,
                [
                    {
                        "type": "mcp_tool_result",
                        "result": {"structuredContent": _delegate_packet()},
                    },
                    {"type": "assistant_message", "role": "assistant", "text": "ok"},
                ],
            )
            last.write_text("ok\n", encoding="utf-8")
            entry.write_text("{}", encoding="utf-8")

            packet = build_wbp_dip_tool_packet(
                task=TASK,
                expected_alias="DIP",
                codex_exit_code=0,
                codex_exec_jsonl_file=jsonl,
                output_last_message_file=last,
                entry_evidence_file=entry,
                proof_dir=root,
                changed_files=[str(jsonl), str(last), str(entry)],
                secret_values=[TASK],
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_packet_rejects_fallback_or_local_imitation(self) -> None:
        for unsafe_field in ("fallback_used", "local_imitation_used"):
            with self.subTest(unsafe_field=unsafe_field):
                with tempfile.TemporaryDirectory() as raw_root:
                    root = Path(raw_root)
                    jsonl = root / "codex.jsonl"
                    last = root / "last.txt"
                    entry = root / "entry.json"
                    _write_jsonl(
                        jsonl,
                        [
                            {
                                "type": "mcp_tool_result",
                                "result": {
                                    "structuredContent": _delegate_packet(
                                        **{unsafe_field: True}
                                    )
                                },
                            }
                        ],
                    )
                    last.write_text("ok\n", encoding="utf-8")
                    entry.write_text("{}", encoding="utf-8")

                    packet = build_wbp_dip_tool_packet(
                        task=TASK,
                        expected_alias="DIP",
                        codex_exit_code=0,
                        codex_exec_jsonl_file=jsonl,
                        output_last_message_file=last,
                        entry_evidence_file=entry,
                        proof_dir=root,
                        changed_files=[str(jsonl), str(last), str(entry)],
                        secret_values=[TASK],
                    )

                self.assertEqual(packet["status"], "error")
                self.assertFalse(packet["delegate_to_dip_proven"])
                self.assertIn("delegate_to_dip_not_proven", packet["blocking_reasons"])

    def test_tool_dry_run_json_is_single_redacted_packet(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "tools/wbp_dip",
                "--dry-run",
                "--json",
                "--codex-bin",
                "/bin/echo",
                TASK,
            ],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)
        packet = json.loads(completed.stdout)
        self.assertEqual(packet["packet_kind"], "wbp_dip_working_tool_run")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_DRY_RUN)
        self.assertEqual(packet["effect"], "probe")
        self.assertTrue(packet["planned_codex_exec"])
        self.assertEqual(packet["planned_sandbox"], DEFAULT_SANDBOX)
        self.assertFalse(packet_contains_text(packet, TASK))


if __name__ == "__main__":
    unittest.main()
