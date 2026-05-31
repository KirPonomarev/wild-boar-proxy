# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = REPO_ROOT / "tools" / "operator_control_surface_harness.py"
SPEC = importlib.util.spec_from_file_location("operator_control_surface_harness", HARNESS_PATH)
assert SPEC is not None
assert SPEC.loader is not None
operator_harness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = operator_harness
SPEC.loader.exec_module(operator_harness)


class OperatorControlSurfaceHarnessTests(unittest.TestCase):
    def test_forbidden_browser_fields_finds_nested_secret_surfaces(self) -> None:
        payload = {
            "prompt": "hello",
            "model_id": "gpt-5.3-codex",
            "nested": {"auth": "x", "items": [{"backend_id": "free-form"}]},
        }

        self.assertEqual(
            operator_harness.forbidden_browser_fields(payload),
            ["nested.auth", "nested.items[0].backend_id"],
        )

    def test_select_server_issued_model_rejects_free_form_model(self) -> None:
        with self.assertRaises(ValueError):
            operator_harness.select_server_issued_model(
                "invented-model",
                ["gpt-5.3-codex"],
            )

    def test_select_server_issued_model_accepts_listed_model(self) -> None:
        self.assertEqual(
            operator_harness.select_server_issued_model(
                "gpt-5.3-codex",
                ["gpt-5.3-codex"],
            ),
            "gpt-5.3-codex",
        )

    def test_build_codex_config_uses_wbp_responses_provider(self) -> None:
        config = operator_harness.build_codex_config(
            endpoint="http://127.0.0.1:8318/v1",
            model_id="gpt-5.3-codex",
        )

        self.assertIn('model = "gpt-5.3-codex"', config)
        self.assertIn('model_provider = "cliproxy"', config)
        self.assertIn('base_url = "http://127.0.0.1:8318/v1"', config)
        self.assertIn('env_key = "OPENAI_API_KEY"', config)
        self.assertIn('wire_api = "responses"', config)

    def test_extract_local_api_key_prefers_api_keys_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yaml"
            config.write_text(
                'secret-key: ""\napi-keys:\n  - "local-runtime-key-123"\n',
                encoding="utf-8",
            )

            self.assertEqual(
                operator_harness.extract_local_api_key(config),
                "local-runtime-key-123",
            )

    def test_redact_text_masks_secret_shapes_and_explicit_values(self) -> None:
        text = "OPENAI_API_KEY=secret-value-123 Bearer abcdefghijklmnop"

        redacted = operator_harness.redact_text(text, ["secret-value-123"])

        self.assertNotIn("secret-value-123", redacted)
        self.assertNotIn("Bearer abcdefghijklmnop", redacted)
        self.assertIn("<redacted-secret>", redacted)


if __name__ == "__main__":
    unittest.main()
