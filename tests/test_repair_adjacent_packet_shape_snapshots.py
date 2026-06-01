# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SECRET_SENTINEL = "sk-wbp-repair-adjacent-secret-should-not-leak-1234567890"

COMMAND_PACKET_REQUIRED_FIELDS = {
    "status",
    "exit_code",
    "human_message",
    "machine_error_code",
    "changed_files",
    "next_action",
    "liveness",
    "severity",
    "operator_action",
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _strict_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, index = decoder.raw_decode(raw)
    if raw[index:].strip():
        raise AssertionError("stdout must contain exactly one JSON object")
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


def _assert_temp_contained(testcase: unittest.TestCase, root: Path, paths: list[str]) -> None:
    resolved_root = root.resolve()
    for raw_path in paths:
        testcase.assertIsInstance(raw_path, str)
        path = Path(raw_path).resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError:
            testcase.fail(f"changed_files entry escapes temp root: {raw_path}")


def _normalize(value: Any, *, temp_root: Path) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalize(item, temp_root=temp_root)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalize(item, temp_root=temp_root) for item in value]
    if isinstance(value, str):
        normalized = value.replace(str(temp_root), "<TMP>")
        normalized = re.sub(r"http://127\.0\.0\.1:\d+/v1", "<ENDPOINT>", normalized)
        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)",
            normalized,
        ):
            return "<TIMESTAMP>"
        return normalized
    return value


def _assert_subset(testcase: unittest.TestCase, expected: Any, actual: Any) -> None:
    if isinstance(expected, dict):
        testcase.assertIsInstance(actual, dict)
        for key, expected_value in expected.items():
            testcase.assertIn(key, actual)
            _assert_subset(testcase, expected_value, actual[key])
        return
    if isinstance(expected, list):
        testcase.assertIsInstance(actual, list)
        testcase.assertEqual(len(expected), len(actual))
        for expected_item, actual_item in zip(expected, actual):
            _assert_subset(testcase, expected_item, actual_item)
        return
    testcase.assertEqual(expected, actual)


class RepairAdjacentPacketShapeSnapshotTests(unittest.TestCase):
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
            json.dumps({"OPENAI_API_KEY": SECRET_SENTINEL}, ensure_ascii=True) + "\n",
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
                    "selected_backend_ids": [],
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
                },
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.external_dir / "routes.json").write_text(
            json.dumps({"schema_version": 1, "routes": []}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        secrets_file = self.external_dir / "secrets.env"
        secrets_file.write_text(
            f"OPENROUTER_API_KEY={SECRET_SENTINEL}\n",
            encoding="utf-8",
        )
        os.chmod(secrets_file, 0o600)
        self.launcher_script = self.managed_dir / "stable-runtime-launcher.sh"
        self.launcher_script.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        self.launcher_script.chmod(0o755)

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
        env["WBP_EXTERNAL_MODELS_DIR"] = str(self.external_dir)
        env["WBP_LAUNCHER_SCRIPT"] = str(self.launcher_script)
        env["WBP_SYNC_SCRIPT"] = str(self.managed_dir / "supervisor-sync.sh")
        env["WBP_ACCOUNTS_BIN"] = str(self.bin_dir / "codex-accounts")
        env["WBP_ONBOARD_BIN"] = str(self.bin_dir / "codex-account-onboard")
        env["WBP_LOCK_FILE"] = str(self.managed_dir / "wild-boar-proxy.lock")
        env["WBP_LAUNCHER_LOCK_FILE"] = str(
            self.managed_dir / "stable-runtime-launch.lock"
        )
        env["WBP_PROXY_REPROBE_DISABLE_LEGACY_CANDIDATES"] = "1"
        env["NO_PROXY"] = "*"
        env["no_proxy"] = "*"
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

    def assert_common_repair_adjacent_packet(self, payload: dict[str, Any]) -> None:
        self.assertTrue(COMMAND_PACKET_REQUIRED_FIELDS <= set(payload))
        self.assertNotIn("effect", payload)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["exit_code"], 1)
        self.assertNotEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["machine_error_code"], "STABLE_SERVICE_DISABLED")
        self.assertEqual(payload["liveness"], "down")
        self.assertNotEqual(payload["liveness"], "healthy")
        self.assertEqual(payload["next_action"], "retry")
        self.assertEqual(payload["operator_action"], "retry")
        self.assertEqual(payload["severity"], "recoverable")
        self.assertIsInstance(payload["changed_files"], list)
        _assert_temp_contained(self, self.root, payload["changed_files"])

    def assert_no_secret_leak(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        self.assertNotIn(SECRET_SENTINEL, serialized)
        self.assertNotIn("sk-wbp-repair-adjacent-secret", serialized)

    def test_healthcheck_absent_listener_packet_shape_is_repair_adjacent(self) -> None:
        result = self.run_cli("healthcheck", "--json")
        self.assertEqual(result.stderr, "")
        payload = _strict_json_object(result.stdout)
        self.assertEqual(result.returncode, payload["exit_code"])
        self.assert_common_repair_adjacent_packet(payload)
        self.assert_no_secret_leak(payload)

        normalized = _normalize(payload, temp_root=self.root)
        _assert_subset(
            self,
            {
                "human_message": (
                    "Stable service did not re-enable through the bounded healthcheck "
                    "recovery lane; listener is not reachable at <ENDPOINT>."
                ),
                "effective_mode": "stable",
                "endpoint": "<ENDPOINT>",
                "attestation": {
                    "attestation_source": "healthcheck --json",
                    "listener_ok": False,
                    "models_ok": False,
                    "responses_ok": False,
                    "base_url_match": True,
                    "effective_mode_match": True,
                    "model_match": True,
                    "observed_at_utc": "<TIMESTAMP>",
                },
                "launch_readiness": {
                    "owner_command_surface": "healthcheck --json",
                    "delegated_from_status": False,
                    "status": "blocked",
                    "gate_passed": False,
                    "listener_reachable": False,
                    "machine_error_code": "STABLE_SERVICE_DISABLED",
                },
                "runtime_guardrails": {
                    "owner_command_surface": "healthcheck --json",
                    "status": "blocked",
                    "recovery_effectful_claim_allowed": False,
                    "recovery_guardrail_status": "blocked",
                },
                "deterministic_stable_recovery_result": {
                    "owner_command_surface": "healthcheck --json",
                    "status": "failed",
                    "attempted": True,
                    "entry_lane": "stable_service_disabled",
                    "live_runtime_observation_confirmed": False,
                    "effectful_claim_allowed": False,
                },
            },
            normalized,
        )
