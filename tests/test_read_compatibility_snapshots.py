# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SECRET_SENTINEL = "sentinel-secret-wbp-read-snapshot-should-not-leak-1234567890"

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
    "effect",
}

READ_COMPATIBILITY_COMMANDS = {
    "mode get --json": ("mode", "get", "--json"),
    "status --json": ("status", "--json"),
    "accounts list --json": ("accounts", "list", "--json"),
    "external-models credentials status --provider openrouter --json": (
        "external-models",
        "credentials",
        "status",
        "--provider",
        "openrouter",
        "--json",
    ),
}

EXPECTED_COMPATIBILITY_SNAPSHOTS: dict[str, dict[str, Any]] = {
    "mode get --json": {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Mode values are available.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "unknown",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "read",
        "desired_mode": "stable",
        "effective_mode": "stable",
    },
    "status --json": {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Runtime status snapshot is available.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "unknown",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "read",
        "desired_mode": "stable",
        "effective_mode": "stable",
        "endpoint": "http://127.0.0.1:8318/v1",
        "configured_model": "gpt-5.4",
        "requested_model": "gpt-5.4",
        "configured_proxy_url": "",
        "current_proxy_url": "",
        "pool_summary": {
            "active": 1,
            "reserve": 0,
            "retired": 0,
            "healthy": 0,
            "degraded": 0,
            "down": 0,
            "selected_backend_ids": ["backend-a"],
            "backend_count": 1,
        },
        "auth_pool_hygiene": {
            "status": "launch_capable_available",
            "machine_error_code": "OK",
            "blocking_reason": "",
            "launch_capable_backend_count": 1,
            "selected_backend_ids_observed": ["backend-a"],
            "delegated_from_status": False,
        },
        "launch_readiness": {
            "status": "not_evaluated",
            "owner_command_surface": "status --json",
            "delegated_from_status": False,
            "gate_passed": False,
            "blocking_reason": "live_attestation_not_run_by_status",
            "machine_error_code": "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
        },
        "runtime_guardrails": {
            "owner_command_surface": "status --json",
            "delegated_from_status": False,
            "status": "clear",
            "blocking_reason": "",
        },
        "attestation_summary": {
            "status": "not_run",
            "machine_error_code": "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
            "attestation_source": "status --json",
            "observed_at_utc": "",
        },
    },
    "accounts list --json": {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Account registry snapshot is available.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "unknown",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "read",
        "accounts": [
            {
                "id": "backend-a",
                "label": "Backend A",
                "pool": "active",
                "status": "healthy",
                "manual_hold": False,
                "auth_ref": "<TMP>/auth/backend-a.json",
                "fail_count": 0,
                "success_count": 1,
            }
        ],
        "registry_identity": {
            "status": "clear",
            "machine_error_code": "OK",
            "next_action": "none",
            "registry_schema_version": 2,
            "claim_blockers": [],
            "duplicate_auth_basenames": [],
            "duplicate_backend_ids": [],
            "empty_auth_ref_backends": [],
            "invalid_auth_basenames": [],
            "invalid_backend_pools": [],
            "missing_auth_refs": [],
            "unsupported_schema_versions": [],
        },
        "pool_policy": {
            "active_min": 1,
            "active_target": 2,
            "reserve_target": 0,
        },
        "stable_default_backend_id": "default-backend",
    },
    "external-models credentials status --provider openrouter --json": {
        "status": "ok",
        "exit_code": 0,
        "human_message": (
            "External-models credential status collected from sandbox owner paths."
        ),
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
        "liveness": "not_applicable",
        "severity": "recoverable",
        "operator_action": "none",
        "effect": "read",
        "timestamp_utc": "<TIMESTAMP>",
        "data": {
            "credential_result": {
                "schema_admitted": True,
                "classification_scope": "credential_admission_only",
                "scope": "sandbox",
                "status": "present",
                "provider": "openrouter",
                "source": "sandbox-managed",
                "credential_ref": "OPENROUTER_API_KEY",
                "credential_present": True,
                "secret_value_exposed": False,
                "expected_refs": [
                    "OPENROUTER_API_KEY",
                    "WBP_OPENROUTER_API_KEY",
                    "WBP_PROVIDER_OPENROUTER_API_KEY",
                ],
                "supported_sources": ["owner-env"],
                "provider_dashboard_url": "https://openrouter.ai/settings/keys",
                "provider_family": "provider_router",
                "auth_type": "bearer",
                "seed_source": "current_runtime",
                "browser_secret_intake": False,
                "browser_path_intake": False,
                "provider_family_compatibility_claimed": False,
                "provider_runtime_compatibility_claimed": False,
                "model_runtime_compatibility_claimed": False,
                "generic_route_transform_support_claimed": False,
                "generic_response_compatibility_claimed": False,
            }
        },
    },
}


def _strict_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, index = decoder.raw_decode(raw)
    if raw[index:].strip():
        raise AssertionError("stdout must contain exactly one JSON object")
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


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
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", normalized):
            return "<TIMESTAMP>"
        if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\+00:00|Z)",
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


class ReadCompatibilitySnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.auth_dir = self.root / "auth"
        self.external_dir = self.managed_dir / "external-models"
        for path in (
            self.profile_dir,
            self.managed_dir,
            self.stable_dir,
            self.auth_dir,
            self.external_dir,
        ):
            path.mkdir(parents=True)

        (self.profile_dir / "config.toml").write_text(
            'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:9999/v1"\n',
            encoding="utf-8",
        )
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n",
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

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=self.env(),
            text=True,
            capture_output=True,
            check=False,
        )

    def assert_read_packet_invariants(self, payload: dict[str, Any]) -> None:
        self.assertTrue(COMMAND_PACKET_REQUIRED_FIELDS <= set(payload))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["exit_code"], 0)
        self.assertEqual(payload["machine_error_code"], "OK")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["effect"], "read")

    def assert_no_secret_leak(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        self.assertNotIn(SECRET_SENTINEL, serialized)
        self.assertNotIn("sentinel-secret-wbp-read-snapshot", serialized)
        credential_result = (
            payload.get("data", {}).get("credential_result", {})
            if isinstance(payload.get("data"), dict)
            else {}
        )
        if credential_result:
            self.assertIs(credential_result.get("secret_value_exposed"), False)

    def test_read_commands_match_compatibility_snapshots(self) -> None:
        for label, command in READ_COMPATIBILITY_COMMANDS.items():
            with self.subTest(command=label):
                result = self.run_cli(*command)
                self.assertEqual(result.stderr, "")
                payload = _strict_json_object(result.stdout)
                self.assertEqual(result.returncode, payload["exit_code"])
                self.assert_read_packet_invariants(payload)
                self.assert_no_secret_leak(payload)
                normalized = _normalize(payload, temp_root=self.root)
                _assert_subset(
                    self,
                    EXPECTED_COMPATIBILITY_SNAPSHOTS[label],
                    normalized,
                )

    def test_repair_adjacent_commands_are_not_snapshot_members(self) -> None:
        self.assertIn(("status", "--json"), set(READ_COMPATIBILITY_COMMANDS.values()))
        self.assertNotIn(
            ("healthcheck", "--json"),
            set(READ_COMPATIBILITY_COMMANDS.values()),
        )
