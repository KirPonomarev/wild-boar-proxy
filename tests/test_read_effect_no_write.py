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
from typing import Any

from tools.truth_tree_harness import assert_no_truth_mutation, snapshot_truth_tree


ROOT = Path(__file__).resolve().parents[1]


RUNTIME_TRUTH_FILES = (
    "backend-registry.json",
    "supervisor-state.json",
    "managed-config.yaml",
    "runtime-mode.txt",
    "runtime-effective-mode.txt",
    "config.toml",
)

EXTERNAL_MODELS_TRUTH_FILES = (
    "state.json",
    "routes.json",
    "secrets.env",
)


def _decode_single_json_object(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


class ReadEffectNoWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.external_dir = self.managed_dir / "external-models"
        self.profile_dir.mkdir(parents=True)
        self.managed_dir.mkdir(parents=True)
        self.stable_dir.mkdir(parents=True)
        self.external_dir.mkdir(parents=True)

        (self.profile_dir / "config.toml").write_text(
            'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:9999/v1"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n",
            encoding="utf-8",
        )
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "updated_at": "2026-06-01T00:00:00+00:00",
                    "stable_default_backend_id": "default-backend",
                    "pool_policy": {
                        "active_min": 1,
                        "active_target": 2,
                        "reserve_target": 0,
                    },
                    "backends": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "status": "healthy",
                            "manual_hold": False,
                            "auth_ref": "/tmp/a.json",
                            "fail_count": 0,
                            "success_count": 1,
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "version": 2,
                    "status": "healthy",
                    "effective_mode": "stable",
                    "selected_backend_ids": ["backend-a"],
                    "managed_port": 9999,
                    "last_error": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            "host: 127.0.0.1\nport: 9999\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 8318\n",
            encoding="utf-8",
        )
        (self.external_dir / "state.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "policy": {
                        "paid_routes_enabled": False,
                        "paid_route_allowlist": [],
                        "paid_route_default": "blocked",
                    },
                    "adapter": {"state": "stopped"},
                    "local_auth": {"token_present": False},
                    "routes": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.external_dir / "routes.json").write_text(
            json.dumps({"schema_version": 1, "routes": []}) + "\n",
            encoding="utf-8",
        )
        secrets_file = self.external_dir / "secrets.env"
        secrets_file.write_text("OPENROUTER_API_KEY=test-key\n", encoding="utf-8")
        os.chmod(secrets_file, 0o600)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_CONFIG_TOML"] = str(self.profile_dir / "config.toml")
        env["WBP_RUNTIME_MODE_FILE"] = str(self.profile_dir / "runtime-mode.txt")
        env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
            self.profile_dir / "runtime-effective-mode.txt"
        )
        env["WBP_REGISTRY_FILE"] = str(self.managed_dir / "backend-registry.json")
        env["WBP_STATE_FILE"] = str(self.managed_dir / "supervisor-state.json")
        env["WBP_MANAGED_CONFIG_FILE"] = str(self.managed_dir / "managed-config.yaml")
        env["WBP_EXTERNAL_MODELS_DIR"] = str(self.external_dir)
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    def truth_snapshot(self) -> dict[str, dict[str, object]]:
        paths = {
            "backend-registry.json": self.managed_dir / "backend-registry.json",
            "supervisor-state.json": self.managed_dir / "supervisor-state.json",
            "managed-config.yaml": self.managed_dir / "managed-config.yaml",
            "runtime-mode.txt": self.profile_dir / "runtime-mode.txt",
            "runtime-effective-mode.txt": self.profile_dir / "runtime-effective-mode.txt",
            "config.toml": self.profile_dir / "config.toml",
            "state.json": self.external_dir / "state.json",
            "routes.json": self.external_dir / "routes.json",
            "secrets.env": self.external_dir / "secrets.env",
        }
        return snapshot_truth_tree(paths, secret_labels={"secrets.env"})

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_read_effect_no_write(self, *args: str) -> dict[str, Any]:
        before = self.truth_snapshot()
        result = self.run_cli(*args)
        after = self.truth_snapshot()
        payload = _decode_single_json_object(result.stdout)

        self.assertEqual(payload["effect"], "read")
        self.assertEqual(payload["changed_files"], [])
        assert_no_truth_mutation(before, after)
        return payload

    def test_read_effect_commands_do_not_write_truth_files(self) -> None:
        commands = (
            ("invariant-check", "--json"),
            ("status", "--json"),
            ("rollback", "--latest", "--dry-run", "--json"),
            ("mode", "get", "--json"),
            ("accounts", "list", "--json"),
            (
                "external-models",
                "credentials",
                "status",
                "--provider",
                "openrouter",
                "--json",
            ),
        )

        for command in commands:
            with self.subTest(command=" ".join(command)):
                self.assert_read_effect_no_write(*command)

    def test_read_effect_error_path_does_not_write_truth_files(self) -> None:
        payload = self.assert_read_effect_no_write(
            "external-models",
            "credentials",
            "status",
            "--provider",
            "unknown-provider",
            "--json",
        )

        self.assertEqual(payload["status"], "error")
        self.assertEqual(
            payload["machine_error_code"],
            "EXTERNAL_MODELS_PROVIDER_UNSUPPORTED",
        )

    def test_status_is_read_effect_member_and_healthcheck_is_not(
        self,
    ) -> None:
        harness_commands = {
            ("invariant-check", "--json"),
            ("status", "--json"),
            ("rollback", "--latest", "--dry-run", "--json"),
            ("mode", "get", "--json"),
            ("accounts", "list", "--json"),
            (
                "external-models",
                "credentials",
                "status",
                "--provider",
                "openrouter",
                "--json",
            ),
            (
                "external-models",
                "credentials",
                "status",
                "--provider",
                "unknown-provider",
                "--json",
            ),
        }

        self.assertIn(("status", "--json"), harness_commands)
        self.assertNotIn(("healthcheck", "--json"), harness_commands)
