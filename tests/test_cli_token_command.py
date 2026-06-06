# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.core import packets


ROOT = Path(__file__).resolve().parents[1]
AUTH_COMMAND_HELPER = ROOT / "wbp_codex_auth_command.py"


class TokenCommandCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.profile_dir.mkdir(parents=True)
        self.managed_dir.mkdir(parents=True)
        self.generated_config = self.managed_dir / "stable-runtime-config.generated.yaml"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        return env

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def run_helper(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(AUTH_COMMAND_HELPER)],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_token_plain_outputs_exact_local_listener_token(self) -> None:
        self.generated_config.write_text(
            'secret-key: ""\napi-keys:\n  - "local-runtime-token-123"\n',
            encoding="utf-8",
        )

        result = self.run_cli("token")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "local-runtime-token-123")
        self.assertEqual(result.stderr, "")

    def test_token_json_reports_contract_without_secret_leak(self) -> None:
        self.generated_config.write_text(
            'secret-key: ""\napi-keys:\n  - "local-runtime-token-123"\n',
            encoding="utf-8",
        )

        result = self.run_cli("token", "--json")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertNotIn("local-runtime-token-123", result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["next_action"], "none")
        self.assertEqual(
            payload["data"]["token_source_kind"],
            "stable_runtime_generated_config",
        )
        self.assertEqual(payload["data"]["token_output_shape"], "plain_token_stdout")
        self.assertTrue(payload["data"]["token_present"])
        self.assertFalse(payload["data"]["token_emitted"])
        self.assertFalse(payload["data"]["secret_value_exposed"])
        self.assertTrue(payload["data"]["local_only"])
        self.assertNotIn("config_path", payload["data"])
        self.assertFalse(
            packets.command_packet_has_secret_leak(
                payload,
                secret_values=["local-runtime-token-123"],
            )
        )

    def test_token_plain_falls_back_to_secret_key_shape(self) -> None:
        self.generated_config.write_text(
            'secret-key: "fallback-runtime-token-456"\n',
            encoding="utf-8",
        )

        result = self.run_cli("token")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "fallback-runtime-token-456")
        self.assertEqual(result.stderr, "")

    def test_token_json_fails_cleanly_when_generated_config_missing(self) -> None:
        result = self.run_cli("token", "--json")

        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "WBP_TOKEN_SOURCE_UNAVAILABLE")
        self.assertEqual(payload["operator_action"], "user_action")
        self.assertEqual(payload["next_action"], "repair_runtime")

    def test_token_plain_fails_without_json_when_generated_config_missing(self) -> None:
        result = self.run_cli("token")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Stable runtime generated config is missing", result.stderr)

    def test_token_plain_writes_audit_stamp_when_requested(self) -> None:
        self.generated_config.write_text(
            'secret-key: ""\napi-keys:\n  - "local-runtime-token-123"\n',
            encoding="utf-8",
        )
        stamp = self.root / "stamp.txt"
        env = self.env()
        env["WBP_TOKEN_COMMAND_AUDIT_STAMP_PATH"] = str(stamp)

        result = subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", "token"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertTrue(stamp.exists())
        self.assertEqual(stamp.read_text(encoding="utf-8"), "invoked\n")

    def test_repo_owned_auth_command_helper_outputs_exact_local_listener_token(self) -> None:
        self.generated_config.write_text(
            'secret-key: ""\napi-keys:\n  - "local-runtime-token-123"\n',
            encoding="utf-8",
        )

        result = self.run_helper()

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "local-runtime-token-123")
        self.assertEqual(result.stderr, "")

    def test_repo_owned_auth_command_helper_writes_audit_stamp_when_requested(self) -> None:
        self.generated_config.write_text(
            'secret-key: ""\napi-keys:\n  - "local-runtime-token-123"\n',
            encoding="utf-8",
        )
        stamp = self.root / "helper-stamp.txt"
        env = self.env()
        env["WBP_TOKEN_COMMAND_AUDIT_STAMP_PATH"] = str(stamp)

        result = subprocess.run(
            [str(AUTH_COMMAND_HELPER)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "local-runtime-token-123")
        self.assertEqual(result.stderr, "")
        self.assertTrue(stamp.exists())
        self.assertEqual(stamp.read_text(encoding="utf-8"), "invoked\n")

    def test_repo_owned_auth_command_helper_fails_without_secret_leak(self) -> None:
        result = self.run_helper()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Stable runtime generated config is missing", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
