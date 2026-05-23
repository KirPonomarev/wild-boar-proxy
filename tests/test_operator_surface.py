# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy.operator_surface import (
    OperatorSurfaceConfig,
    OperatorSurfaceSession,
    build_codex_config,
    forbidden_browser_fields,
    select_server_issued_model,
)


class OperatorSurfaceTests(unittest.TestCase):
    def test_build_codex_config_targets_cliproxy_responses_wire(self) -> None:
        config = build_codex_config(
            endpoint="http://127.0.0.1:8318/v1",
            model_id="gpt-5.3-codex",
        )

        self.assertIn('model = "gpt-5.3-codex"', config)
        self.assertIn('model_provider = "cliproxy"', config)
        self.assertIn('base_url = "http://127.0.0.1:8318/v1"', config)
        self.assertIn('wire_api = "responses"', config)
        self.assertNotIn("api_key", config)
        self.assertNotIn("secret", config)

    def test_forbidden_browser_fields_detect_nested_secret_path_and_ids(self) -> None:
        findings = forbidden_browser_fields(
            {
                "prompt": "ok",
                "model_id": "gpt-5.3-codex",
                "nested": {"api_key": "sk-hidden", "route_id": "route"},
                "items": [{"backend_id": "backend"}, {"path": "/tmp/secret"}],
            }
        )

        self.assertEqual(findings, ["nested.api_key", "nested.route_id", "items[0].backend_id", "items[1].path"])

    def test_select_server_issued_model_rejects_free_form_model(self) -> None:
        with self.assertRaises(ValueError):
            select_server_issued_model("gpt-free-form", ["gpt-5.3-codex"])

    def test_run_prompt_uses_stdin_dash_and_redacted_transcript(self) -> None:
        session = OperatorSurfaceSession(
            OperatorSurfaceConfig(
                codex_bin=Path("/bin/echo"),
                runtime_config=Path("/tmp/nonexistent-runtime-config.yaml"),
                timeout_seconds=5,
            )
        )
        session.probe_models = lambda: {  # type: ignore[method-assign]
            "ok": True,
            "model_ids": ["gpt-5.3-codex"],
            "server_issued": True,
        }
        session.status_payload = lambda: {  # type: ignore[method-assign]
            "status": {"status": "ok", "machine_error_code": "OK"},
            "models": {"model_ids": ["gpt-5.3-codex"], "server_issued": True},
        }
        session.local_api_key = lambda: "sk-test-secret-value"  # type: ignore[method-assign]

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            self.assertEqual(command[-1], "-")
            self.assertEqual(kwargs.get("input"), "Reply with exactly MAIN_WEB_OK.")
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            self.assertEqual(env.get("OPENAI_API_KEY"), "sk-test-secret-value")  # type: ignore[union-attr]
            last_message = Path(command[command.index("-o") + 1])
            last_message.write_text("MAIN_WEB_OK\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"type": "done"}), stderr="")

        with mock.patch("wild_boar_proxy.operator_surface.subprocess.run", side_effect=fake_run):
            result = session.run_prompt(
                {
                    "prompt": "Reply with exactly MAIN_WEB_OK.",
                    "model_id": "gpt-5.3-codex",
                }
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["final_message"], "MAIN_WEB_OK")
        self.assertTrue(result["stdin_prompt_used"])
        self.assertTrue(result["temp_root_removed"])
        self.assertNotIn("sk-test-secret-value", json.dumps(result))

    def test_run_prompt_rejects_browser_supplied_route_id(self) -> None:
        session = OperatorSurfaceSession()
        session.status_payload = lambda: {"status": {"status": "ok"}}  # type: ignore[method-assign]

        result = session.run_prompt(
            {
                "prompt": "Reply OK.",
                "model_id": "gpt-5.3-codex",
                "route_id": "browser-forged",
            }
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["machine_error_code"], "FORBIDDEN_BROWSER_FIELD")
        self.assertEqual(result["forbidden_fields"], ["route_id"])


if __name__ == "__main__":
    unittest.main()
