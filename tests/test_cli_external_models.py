# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sample_route(route_id: str = "wbp-deepseek-v3") -> dict[str, object]:
    return {
        "schema_version": 1,
        "route_id": route_id,
        "display_name": "DeepSeek V3",
        "provider": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "endpoint_path": "/chat/completions",
        "upstream_model": "deepseek/deepseek-chat",
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": "OPENROUTER_API_KEY"},
        "cost_class": "paid_or_free_limited",
        "lane_role": "candidate",
        "fallback_eligible": False,
        "enabled": True,
    }


class ExternalModelsCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.profile_dir = self.root / "profile"
        self.managed_dir = self.root / "managed"
        self.stable_dir = self.root / "stable"
        self.external_dir = self.root / "external-models"
        self.profile_dir.mkdir(parents=True)
        self.managed_dir.mkdir(parents=True)
        self.stable_dir.mkdir(parents=True)
        self.external_dir.mkdir(parents=True)
        (self.profile_dir / "config.toml").write_text("", encoding="utf-8")
        (self.profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (self.profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (self.managed_dir / "backend-registry.json").write_text(
            json.dumps({"schema_version": 2, "backends": []}) + "\n", encoding="utf-8"
        )
        (self.managed_dir / "supervisor-state.json").write_text(
            json.dumps({"schema_version": 2}) + "\n", encoding="utf-8"
        )
        (self.stable_dir / "config.yaml").write_text(
            "host: 127.0.0.1\nport: 8318\n", encoding="utf-8"
        )
        (self.external_dir / "secrets.env").write_text(
            "OPENROUTER_API_KEY=test-key\n", encoding="utf-8"
        )
        os.chmod(self.external_dir / "secrets.env", 0o600)

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
        return env

    def run_cli(
        self, *args: str, stdin_text: str | None = None, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = self.env()
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "wild_boar_proxy", *args],
            cwd=ROOT,
            env=env,
            input=stdin_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def parse_payload(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        for field in (
            "status",
            "exit_code",
            "human_message",
            "machine_error_code",
            "changed_files",
            "next_action",
            "liveness",
            "severity",
            "operator_action",
            "data",
            "timestamp_utc",
        ):
            self.assertIn(field, payload)
        return payload

    def test_routes_add_list_disable_remove_round_trip(self) -> None:
        route_file = self.root / "route.json"
        route_file.write_text(json.dumps(sample_route()) + "\n", encoding="utf-8")

        add_result = self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--file",
            str(route_file),
        )
        add_payload = self.parse_payload(add_result)
        self.assertEqual(add_payload["status"], "ok")
        self.assertEqual(add_payload["machine_error_code"], "OK")

        list_result = self.run_cli("external-models", "routes", "list", "--json")
        list_payload = self.parse_payload(list_result)
        self.assertEqual(list_payload["data"]["count"], 1)
        self.assertEqual(list_payload["data"]["routes"][0]["route_id"], "wbp-deepseek-v3")

        disable_result = self.run_cli(
            "external-models",
            "routes",
            "disable",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        disable_payload = self.parse_payload(disable_result)
        self.assertTrue(disable_payload["data"]["enabled"] is False)

        remove_result = self.run_cli(
            "external-models",
            "routes",
            "remove",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        remove_payload = self.parse_payload(remove_result)
        self.assertEqual(remove_payload["status"], "ok")
        routes_payload = json.loads((self.external_dir / "routes.json").read_text())
        self.assertEqual(routes_payload["routes"], [])

    def test_routes_add_from_stdin_and_models_projection(self) -> None:
        add_result = self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route("wbp-qwen-coder")),
        )
        self.assertEqual(self.parse_payload(add_result)["status"], "ok")
        models_result = self.run_cli("external-models", "models", "--json")
        models_payload = self.parse_payload(models_result)
        self.assertEqual(models_payload["data"]["count"], 1)
        model = models_payload["data"]["models"][0]
        self.assertEqual(model["route_id"], "wbp-qwen-coder")
        self.assertNotIn("auth", model)

    def test_duplicate_route_is_rejected(self) -> None:
        route_file = self.root / "route.json"
        route_file.write_text(json.dumps(sample_route()) + "\n", encoding="utf-8")
        first = self.run_cli(
            "external-models", "routes", "add", "--json", "--file", str(route_file)
        )
        self.assertEqual(self.parse_payload(first)["status"], "ok")
        second = self.run_cli(
            "external-models", "routes", "add", "--json", "--file", str(route_file)
        )
        payload = self.parse_payload(second)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "duplicate_route")

    def test_profile_packet_is_non_mutating_and_local_only(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )
        profile_result = self.run_cli(
            "external-models",
            "profile",
            "codex-desktop",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(profile_result)
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["data"]["writes_external_config"])
        self.assertFalse(payload["data"]["profile_ready"])
        self.assertIsNone(payload["data"]["base_url"])

    def test_evidence_capture_writes_local_artifact(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )
        result = self.run_cli(
            "external-models",
            "evidence",
            "capture",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        evidence_path = Path(payload["data"]["evidence_path"])
        self.assertTrue(evidence_path.exists())
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertFalse(evidence_payload["network_dependent_evidence"])

    def test_status_uses_isolated_external_model_paths(self) -> None:
        result = self.run_cli("external-models", "status", "--json")
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["foundation_phase"], "C1")
        self.assertEqual(
            Path(payload["data"]["paths"]["routes_file"]).resolve(),
            (self.external_dir / "routes.json").resolve(),
        )

    def test_secrets_permissions_are_enforced(self) -> None:
        self.run_cli(
            "external-models",
            "routes",
            "add",
            "--json",
            "--stdin",
            stdin_text=json.dumps(sample_route()),
        )
        os.chmod(self.external_dir / "secrets.env", 0o644)
        result = self.run_cli(
            "external-models",
            "profile",
            "codex-desktop",
            "--json",
            "--route",
            "wbp-deepseek-v3",
        )
        payload = self.parse_payload(result)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["machine_error_code"], "unsafe_secret_permissions")
        self.assertEqual(
            stat.S_IMODE((self.external_dir / "secrets.env").stat().st_mode), 0o644
        )


class ZeroTestSelectionGuardTests(unittest.TestCase):
    def test_module_contains_real_tests(self) -> None:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(ExternalModelsCliTests)
        self.assertGreaterEqual(suite.countTestCases(), 6)
