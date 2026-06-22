# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.wbp_dip_tool import (
    DEFAULT_SANDBOX,
    WBP_DIP_TOOL_DRY_RUN,
    WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE,
    WBP_DIP_TOOL_OK,
    build_codex_exec_argv,
    build_delegate_prompt,
    build_wbp_dip_tool_packet,
    request_live_result,
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


def _live_result(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "status": "ok",
        "machine_error_code": "OK",
        "provider_called": True,
        "result_available": True,
        "source": "external_models_direct",
        "route_allowed": True,
        "route_status": "ok",
        "route_id_sha256": "0" * 64,
        "route_id_recorded": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "result_text": "DIP checked: dispatch is bounded; next step is operator smoke.",
        "provider_recorded": True,
        "provider": "deepseek",
        "effective_model_sha256": "1" * 64,
        "effective_model_recorded": False,
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
                live_result=_live_result(),
            )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertTrue(packet["api_lane_called"])
        self.assertTrue(packet["route_bound_dispatch_proven"])
        self.assertFalse(packet["fallback_used"])
        self.assertFalse(packet["local_imitation_used"])
        self.assertFalse(packet["product_ready"])
        self.assertTrue(packet["live_result_required"])
        self.assertTrue(packet["live_result_available"])
        self.assertTrue(packet["live_result_provider_called"])
        self.assertEqual(
            packet["live_result_text"],
            "DIP checked: dispatch is bounded; next step is operator smoke.",
        )
        self.assertFalse(packet["live_result_route_id_recorded"])
        self.assertFalse(packet["live_result_effective_model_recorded"])
        self.assertFalse(packet["raw_prompt_recorded"])
        self.assertFalse(packet["prompt_text_recorded"])
        self.assertFalse(packet_contains_text(packet, TASK))

    def test_packet_rejects_proof_only_dispatch_when_live_result_is_required(self) -> None:
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

        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], WBP_DIP_TOOL_LIVE_RESULT_UNAVAILABLE)
        self.assertTrue(packet["delegate_to_dip_proven"])
        self.assertFalse(packet["live_result_available"])
        self.assertIn("live_result_unavailable", packet["blocking_reasons"])

    def test_packet_rejects_and_redacts_unsafe_live_result_text(self) -> None:
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
                live_result=_live_result(result_text=TASK),
            )

        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["live_result_available"])
        self.assertEqual(packet["live_result_text"], "")
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
                        live_result=_live_result(),
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

    @mock.patch("wild_boar_proxy.wbp_dip_tool._provider_headers", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.load_routes_file", return_value={})
    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_uses_runtime_allowed_route(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
        _load_routes_file_mock: mock.Mock,
        _provider_headers_mock: mock.Mock,
    ) -> None:
        route = {
            "route_id": "route-ok",
            "base_url": "https://example.invalid",
            "endpoint_path": "/chat/completions",
            "upstream_model": "deepseek-chat",
            "provider": "deepseek",
            "auth": {"type": "none"},
            "cost_class": "paid_or_free_limited",
            "enabled": True,
        }
        find_route_mock.return_value = route
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=12,
            payload={
                "choices": [
                    {
                        "message": {
                            "content": "DIP result: bounded answer from provider."
                        }
                    }
                ]
            },
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], WBP_DIP_TOOL_OK)
        self.assertTrue(result["result_available"])
        self.assertTrue(result["provider_called"])
        self.assertEqual(result["result_text"], "DIP result: bounded answer from provider.")
        self.assertFalse(result["route_id_recorded"])
        request_json_mock.assert_called_once()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.find_route")
    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_prefers_runtime_http_bridge(
        self,
        request_json_mock: mock.Mock,
        find_route_mock: mock.Mock,
    ) -> None:
        request_json_mock.return_value = SimpleNamespace(
            status_code=200,
            latency_ms=5,
            payload={"output_text": "Bridge result from WBP."},
        )
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "allowed_api_route_ids": ["route-ok"],
                        "deepseek_live_format_check_bridge": {
                            "enabled": True,
                            "method": "POST",
                            "model": "route-ok",
                            "response_text_field": "output_text",
                            "url_candidates": ["http://127.0.0.1:50555/v1/responses"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["source"], "runtime_context_http_bridge")
        self.assertTrue(result["bridge_attempted"])
        self.assertEqual(result["result_text"], "Bridge result from WBP.")
        find_route_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_rejects_route_outside_allowlist(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"DIP": "dip"},
                        "agent_id_to_route": {"dip": "route-outside"},
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["route_allowed"])
        self.assertEqual(result["route_status"], "route_not_allowed")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()

    @mock.patch("wild_boar_proxy.wbp_dip_tool.request_json")
    def test_request_live_result_rejects_alias_outside_context(
        self,
        request_json_mock: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            profile = Path(raw_root)
            (profile / "wbp-agent-runtime-context.json").write_text(
                json.dumps(
                    {
                        "alias_to_agent_id": {"Agent 2": "dip"},
                        "agent_id_to_route": {"dip": "route-ok"},
                        "api_model_id": "route-ok",
                        "allowed_api_route_ids": ["route-ok"],
                    }
                ),
                encoding="utf-8",
            )

            result = request_live_result(
                task=TASK,
                expected_alias="DIP",
                profile_dir=profile,
                timeout_seconds=0.01,
            )

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["route_allowed"])
        self.assertEqual(result["route_status"], "alias_not_in_context")
        self.assertFalse(result["provider_called"])
        request_json_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
