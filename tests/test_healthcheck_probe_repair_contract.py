# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from wild_boar_proxy import runtime as runtime_mod


ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _file_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    stat_result = path.stat()
    return {
        "exists": True,
        "size": stat_result.st_size,
        "mode": stat_result.st_mode & 0o777,
        "mtime_ns": stat_result.st_mtime_ns,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _strict_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, index = decoder.raw_decode(raw)
    if raw[index:].strip():
        raise AssertionError("stdout must contain exactly one JSON object")
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


class HealthcheckProbeRepairContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.auth_dir = self.root / "auth"
        self.external_dir = self.managed_dir / "external-models"
        self.bin_dir = self.managed_dir / "bin"
        for path in (
            self.profile_dir,
            self.managed_dir,
            self.stable_dir,
            self.auth_dir,
            self.external_dir,
            self.bin_dir,
        ):
            path.mkdir(parents=True)

        self.stable_port = _free_port()
        stable_endpoint = f"http://127.0.0.1:{self.stable_port}/v1"
        (self.profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "{stable_endpoint}"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n",
            encoding="utf-8",
        )
        (self.profile_dir / "auth.json").write_text(
            json.dumps({"OPENAI_API_KEY": "sk-healthcheck-probe-secret"}) + "\n",
            encoding="utf-8",
        )
        backend_auth = self.auth_dir / "backend-a.json"
        backend_auth.write_text("{}\n", encoding="utf-8")
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
                            "auth_ref": str(backend_auth),
                            "fail_count": 0,
                            "success_count": 1,
                        }
                    ],
                },
                ensure_ascii=True,
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
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.managed_dir / "managed-config.yaml").write_text(
            "host: 127.0.0.1\nport: 9999\n",
            encoding="utf-8",
        )
        (self.stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {self.stable_port}\n",
            encoding="utf-8",
        )
        self.launcher_script = self.managed_dir / "stable-runtime-launcher.sh"
        self.launcher_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        self.launcher_script.chmod(0o755)
        self.pid_file = self.managed_dir / "managed-proxy.pid"
        self.pid_file.write_text("999999\n", encoding="utf-8")
        self.paths = runtime_mod.RuntimePaths(
            profile_dir=self.profile_dir,
            managed_dir=self.managed_dir,
            stable_config=self.stable_dir / "config.yaml",
            auth_file=self.profile_dir / "auth.json",
            config_toml=self.profile_dir / "config.toml",
            runtime_mode_file=self.profile_dir / "runtime-mode.txt",
            runtime_effective_mode_file=self.profile_dir / "runtime-effective-mode.txt",
            registry_file=self.managed_dir / "backend-registry.json",
            state_file=self.managed_dir / "supervisor-state.json",
            managed_config_file=self.managed_dir / "managed-config.yaml",
            launcher_script=self.launcher_script,
            sync_script=self.managed_dir / "supervisor-sync.sh",
            accounts_bin=self.bin_dir / "codex-accounts",
            onboard_bin=self.bin_dir / "codex-account-onboard",
            lock_file=self.managed_dir / "wild-boar-proxy.lock",
            launcher_lock_file=self.managed_dir / "stable-runtime-launch.lock",
            repair_target_inventory_dir=self.managed_dir / "stable-repair-target",
            repair_target_reference_file=self.managed_dir / "approved-repair-target.json",
            target_switch_transaction_file=(
                self.managed_dir / "target-switch-transaction.json"
            ),
            stable_runtime_generated_config_file=(
                self.managed_dir / "stable-runtime-config.generated.yaml"
            ),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["WBP_PROFILE_DIR"] = str(self.profile_dir)
        env["WBP_MANAGED_DIR"] = str(self.managed_dir)
        env["WBP_STABLE_CONFIG"] = str(self.stable_dir / "config.yaml")
        env["WBP_AUTH_FILE"] = str(self.profile_dir / "auth.json")
        env["WBP_CONFIG_TOML"] = str(self.profile_dir / "config.toml")
        env["WBP_RUNTIME_MODE_FILE"] = str(self.profile_dir / "runtime-mode.txt")
        env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(
            self.profile_dir / "runtime-effective-mode.txt"
        )
        env["WBP_REGISTRY_FILE"] = str(self.managed_dir / "backend-registry.json")
        env["WBP_STATE_FILE"] = str(self.managed_dir / "supervisor-state.json")
        env["WBP_MANAGED_CONFIG_FILE"] = str(self.managed_dir / "managed-config.yaml")
        env["WBP_LAUNCHER_SCRIPT"] = str(self.launcher_script)
        env["WBP_LOCK_FILE"] = str(self.managed_dir / "wild-boar-proxy.lock")
        env["WBP_LAUNCHER_LOCK_FILE"] = str(
            self.managed_dir / "stable-runtime-launch.lock"
        )
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
        return env

    def truth_snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            "backend-registry.json": _file_snapshot(
                self.managed_dir / "backend-registry.json"
            ),
            "supervisor-state.json": _file_snapshot(
                self.managed_dir / "supervisor-state.json"
            ),
            "managed-config.yaml": _file_snapshot(
                self.managed_dir / "managed-config.yaml"
            ),
            "runtime-mode.txt": _file_snapshot(
                self.profile_dir / "runtime-mode.txt"
            ),
            "runtime-effective-mode.txt": _file_snapshot(
                self.profile_dir / "runtime-effective-mode.txt"
            ),
            "config.toml": _file_snapshot(self.profile_dir / "config.toml"),
            "managed-proxy.pid": _file_snapshot(self.pid_file),
        }

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_healthcheck_probe_declares_probe_and_does_not_write_truth_files(self) -> None:
        before = self.truth_snapshot()
        result = self.run_cli("healthcheck", "--json")
        after = self.truth_snapshot()
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.stderr, "")
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["machine_error_code"], "LISTENER_DOWN")
        self.assertNotEqual(payload["machine_error_code"], "STABLE_SERVICE_DISABLED")
        self.assertEqual(payload["attestation"]["attestation_source"], "healthcheck --json")
        self.assertEqual(
            payload["launch_readiness"]["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertEqual(
            payload["runtime_guardrails"]["owner_command_surface"],
            "healthcheck --json",
        )
        self.assertNotIn("deterministic_stable_recovery_result", payload)
        self.assertNotIn("proxy_reprobe_adoption_result", payload)
        self.assertEqual(before, after)

    def test_healthcheck_probe_does_not_call_repair_primitives(self) -> None:
        with (
            mock.patch.object(
                runtime_mod,
                "clear_stale_managed_pid_if_needed",
                side_effect=AssertionError("probe must not clean stale pid"),
            ),
            mock.patch.object(
                runtime_mod,
                "reconcile_stable_fallback",
                side_effect=AssertionError("probe must not reconcile fallback"),
            ),
            mock.patch.object(
                runtime_mod,
                "refresh_last_known_good_proxy_from_healthcheck",
                side_effect=AssertionError("probe must not refresh last known good"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_stable_runtime_launcher_attempt",
                side_effect=AssertionError("probe must not launch repair"),
            ),
            mock.patch.object(
                runtime_mod,
                "run_current_proxy_owner_path_activation",
                side_effect=AssertionError("probe must not adopt current proxy"),
            ),
            mock.patch.object(
                runtime_mod,
                "write_stable_runtime_consumer_snapshot",
                side_effect=AssertionError("probe must not write snapshots"),
            ),
        ):
            payload = runtime_mod.run_healthcheck_probe(self.paths)

        self.assertEqual(payload["effect"], "probe")
        self.assertEqual(payload["changed_files"], [])

    def test_healthcheck_repair_declares_repair(self) -> None:
        result = self.run_cli("healthcheck", "--repair", "--json")
        payload = _strict_json_object(result.stdout)

        self.assertEqual(result.returncode, payload["exit_code"])
        self.assertEqual(payload["effect"], "repair")
        self.assertEqual(
            payload["attestation"]["attestation_source"],
            "healthcheck --repair --json",
        )
        self.assertIsInstance(payload["changed_files"], list)


if __name__ == "__main__":
    unittest.main()
