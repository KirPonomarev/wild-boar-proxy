# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "original_codex_via_wbp_bounded_live_reversibility_probe.py"


def _load_tool_module():
    spec = importlib.util.spec_from_file_location("original_live_reversibility_probe", TOOL_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class OriginalLiveReversibilityProbeTests(unittest.TestCase):
    def test_preserving_wbp_config_keeps_existing_sections(self) -> None:
        tool = _load_tool_module()
        config = (
            'model = "gpt-5.4"\n'
            'model_reasoning_effort = "high"\n\n'
            '[projects."/Volumes/Work/wild-boar-proxy"]\n'
            'trust_level = "trusted"\n'
        )

        candidate = tool._build_preserving_wbp_config(
            existing_text=config,
            endpoint="http://127.0.0.1:12345/v1",
            model="gpt-5.4",
            auth_command_path="/repo/wbp_codex_auth_command.py",
        )

        self.assertIn('[projects."/Volumes/Work/wild-boar-proxy"]', candidate)
        self.assertIn('model_provider = "wbp"', candidate)
        self.assertIn('[model_providers.wbp]', candidate)
        self.assertIn('[model_providers.wbp.auth]', candidate)

    def test_preserving_wbp_config_removes_old_wbp_blocks(self) -> None:
        tool = _load_tool_module()
        config = (
            'model = "old"\n'
            'model_provider = "old_provider"\n\n'
            '[model_providers.wbp]\n'
            'base_url = "http://old.invalid/v1"\n\n'
            '[model_providers.wbp.auth]\n'
            'command = "/old"\n\n'
            '[desktop]\n'
            'preventSleepWhileRunning = true\n'
        )

        candidate = tool._build_preserving_wbp_config(
            existing_text=config,
            endpoint="http://127.0.0.1:12345/v1",
            model="gpt-5.4",
            auth_command_path="/repo/wbp_codex_auth_command.py",
        )

        self.assertNotIn("http://old.invalid", candidate)
        self.assertNotIn('command = "/old"', candidate)
        self.assertEqual(candidate.count("[model_providers.wbp]"), 1)
        self.assertEqual(candidate.count("[model_providers.wbp.auth]"), 1)
        self.assertIn("[desktop]", candidate)

    def test_preserving_wbp_config_does_not_emit_bearer_token(self) -> None:
        tool = _load_tool_module()

        candidate = tool._build_preserving_wbp_config(
            existing_text='model = "gpt-5.4"\n',
            endpoint="http://127.0.0.1:12345/v1",
            model="gpt-5.4",
            auth_command_path="/repo/wbp_codex_auth_command.py",
        )

        self.assertNotIn("experimental_bearer_token", candidate)
        self.assertNotIn("sk-", candidate)

    def test_direct_launch_packet_accepts_pid_and_records_proxy_sanitized(self) -> None:
        tool = _load_tool_module()

        packet = tool._native_original_launch_execution_packet(
            launch_attempted=True,
            launch_returncode=None,
            launch_command=["/Applications/Codex.app/Contents/MacOS/Codex"],
            launch_pid=123,
            proxy_env_sanitized=True,
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["launch_pid"], 123)
        self.assertTrue(packet["proxy_env_sanitized"])

    def test_trace_wait_requires_response_not_only_request(self) -> None:
        request_only = {
            "request_observed": True,
            "path": "/v1/responses",
            "response_observed": False,
        }
        request_and_response = {
            "request_observed": True,
            "path": "/v1/responses",
            "response_observed": True,
        }

        self.assertFalse(
            request_only["request_observed"]
            and request_only["path"] == "/v1/responses"
            and request_only["response_observed"]
        )
        self.assertTrue(
            request_and_response["request_observed"]
            and request_and_response["path"] == "/v1/responses"
            and request_and_response["response_observed"]
        )


if __name__ == "__main__":
    unittest.main()
