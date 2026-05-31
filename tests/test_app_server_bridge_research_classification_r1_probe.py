# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AppServerBridgeResearchClassificationR1ProbeTests(unittest.TestCase):
    def _init_repo(self, repo_root: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        (repo_root / "README.md").write_text("fixture\n", encoding="utf-8")
        (repo_root / "audit_results").mkdir()
        (repo_root / "audit_results" / ".gitkeep").write_text("", encoding="utf-8")
        (repo_root / "wild_boar_proxy").mkdir()
        (repo_root / "tools").mkdir()
        subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
        subprocess.run(["git", "add", "audit_results/.gitkeep"], cwd=repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-m", "fixture"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )

    def _write_json(self, root: Path, rel: str, packet: dict) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(packet), encoding="utf-8")

    def _write_text(self, root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _write_sources(self, root: Path) -> tuple[dict[str, Path], dict[str, Path]]:
        dirs = {
            "provider_auth": root / "audit_results" / "provider_auth",
            "remote_gate": root / "audit_results" / "remote_gate",
            "setup_import": root / "audit_results" / "setup_import",
            "isolated_app_e2e": root / "audit_results" / "isolated_app_e2e",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        provider_packets = {
            "authority_boundary_packet.json": {
                "status": "ok",
                "browser_can_supply_token_path_model_provider_authority": False,
                "remote_can_supply_token_path_model_provider_authority": False,
                "browser_allowed_request_shape": ["server-approved alias"],
                "server_owns_model_route_selection": True,
                "server_owns_provider_endpoint_selection": True,
            },
            "provider_auth_strategy_summary_packet.json": {
                "status": "ok",
                "selected_strategy": "auth.command",
                "silent_fallback_detected": False,
            },
            "auth_strategy_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in provider_packets.items():
            self._write_json(root, f"audit_results/provider_auth/{name}", packet)

        remote_packets = {
            "remote_control_readiness_summary_packet.json": {
                "status": "ok",
                "final_status": "WBP_REMOTE_CONTROL_READINESS_GATE_CLASSIFIED_WITH_LIMITS",
                "network_auth_middleware_proven": False,
                "public_exposure_fully_enforced_for_all_surfaces": False,
                "remote_control_implemented": False,
            },
            "remote_control_authority_boundary_packet.json": {
                "status": "ok",
                "browser_can_supply_token_path_model_provider_authority": False,
                "remote_can_supply_token_path_model_provider_authority": False,
            },
            "remote_control_command_surface_packet.json": {
                "status": "ok",
                "dangerous_visible_disabled_actions": ["process_kill_live"],
            },
            "remote_control_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in remote_packets.items():
            self._write_json(root, f"audit_results/remote_gate/{name}", packet)

        self._write_text(
            root,
            "audit_results/setup_import/spec.md",
            "no command adapter or runtime bridge execution path is enabled\n",
        )
        self._write_json(
            root,
            "audit_results/setup_import/evidence/verification_summary.json",
            {
                "scope": {
                    "command_adapter_changed": False,
                    "runtime_bridge_changed": False,
                    "execution_enabled": False,
                }
            },
        )
        self._write_json(
            root,
            "audit_results/setup_import/evidence/independent_audit_report.json",
            {"verdict": "PASS"},
        )

        self._write_json(
            root,
            "audit_results/isolated_app_e2e/proof.json",
            {
                "launched_gui_process": {
                    "observed": True,
                    "child_app_server_command": "/Applications/Codex.app/.../codex app-server --analytics-default-enabled",
                },
                "followup_control_surface_probe": {
                    "isolated_codex_home_socket_found": False,
                    "child_tcp_or_udp_listener_found": False,
                },
                "boundary_verdict": {
                    "status": "blocked",
                    "machine_classification": "blocked_by_current_codex_protection_boundary",
                },
            },
        )
        self._write_json(
            root,
            "audit_results/isolated_app_e2e/independent_audit.json",
            {
                "checks": [
                    {
                        "name": "strict_gui_through_app_proof",
                        "fact": "no isolated app-server control socket was observed for the launched GUI child",
                    }
                ]
            },
        )
        self._write_text(
            root,
            "audit_results/isolated_app_e2e/closeout.md",
            "same-home debug app-server send-message-v2 could not be truthfully tied to the launched GUI child\n",
        )

        command_adapter = root / "wild_boar_proxy" / "web_design_command_adapter.py"
        web_live_server = root / "wild_boar_proxy" / "web_design_live_server.py"
        harness = root / "tools" / "operator_control_surface_harness.py"

        command_adapter.write_text(
            '''
"""This module is the only planned Python-side bridge."""
from dataclasses import dataclass
@dataclass(frozen=True)
class CommandSpec:
    command_id: str
ALLOWLIST = {
    "status": CommandSpec(command_id="status"),
    "hidden": CommandSpec(command_id="hidden"),
}
def placeholder():
    ui_enabled=False
    ui_enabled=False
def execute_command():
    return None
''',
            encoding="utf-8",
        )
        web_live_server.write_text(
            '''
UI_ACTION_ALLOWLIST = {
    "refresh": {"adapter_command_id": "status"},
    "launch": {"adapter_command_id": "launch_client"},
}
''',
            encoding="utf-8",
        )
        harness.write_text(
            '''
from http.server import ThreadingHTTPServer
server = ThreadingHTTPServer(("127.0.0.1", 9999), None)
''',
            encoding="utf-8",
        )
        return dirs, {
            "command_adapter_file": command_adapter,
            "web_live_server_file": web_live_server,
            "harness_file": harness,
        }

    def test_probe_classifies_bridge_research_with_limits(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "app_server_bridge_research_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs, files = self._write_sources(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "bridge_research"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--provider-auth-dir",
                    str(dirs["provider_auth"]),
                    "--remote-gate-dir",
                    str(dirs["remote_gate"]),
                    "--setup-import-dir",
                    str(dirs["setup_import"]),
                    "--isolated-app-e2e-dir",
                    str(dirs["isolated_app_e2e"]),
                    "--command-adapter-file",
                    str(files["command_adapter_file"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--harness-file",
                    str(files["harness_file"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((evidence_dir / "app_server_bridge_summary_packet.json").read_text())
            substitution = json.loads(
                (evidence_dir / "app_server_bridge_substitution_risk_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "WBP_APP_SERVER_BRIDGE_RESEARCH_CLASSIFIED_WITH_LIMITS",
            )
            self.assertFalse(substitution["research_equals_implementation_admission"])

    def test_probe_blocks_when_remote_authority_is_admitted(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "app_server_bridge_research_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs, files = self._write_sources(temp_repo)
            bad = dirs["provider_auth"] / "authority_boundary_packet.json"
            packet = json.loads(bad.read_text())
            packet["remote_can_supply_token_path_model_provider_authority"] = True
            bad.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "bridge_research"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--provider-auth-dir",
                    str(dirs["provider_auth"]),
                    "--remote-gate-dir",
                    str(dirs["remote_gate"]),
                    "--setup-import-dir",
                    str(dirs["setup_import"]),
                    "--isolated-app-e2e-dir",
                    str(dirs["isolated_app_e2e"]),
                    "--command-adapter-file",
                    str(files["command_adapter_file"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--harness-file",
                    str(files["harness_file"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            validation = json.loads(
                (evidence_dir / "source_app_server_bridge_validation_packet.json").read_text()
            )
            failed = {item["name"] for item in validation["checks"] if not item["passed"]}
            self.assertIn("provider_auth_boundary_ok", failed)

    def test_probe_blocks_when_historical_child_surface_is_promoted_without_limit_truth(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "app_server_bridge_research_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs, files = self._write_sources(temp_repo)
            bad = dirs["isolated_app_e2e"] / "proof.json"
            packet = json.loads(bad.read_text())
            packet["followup_control_surface_probe"]["isolated_codex_home_socket_found"] = True
            bad.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "bridge_research"

            result = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "--repo-root",
                    str(temp_repo),
                    "--evidence-dir",
                    str(evidence_dir),
                    "--provider-auth-dir",
                    str(dirs["provider_auth"]),
                    "--remote-gate-dir",
                    str(dirs["remote_gate"]),
                    "--setup-import-dir",
                    str(dirs["setup_import"]),
                    "--isolated-app-e2e-dir",
                    str(dirs["isolated_app_e2e"]),
                    "--command-adapter-file",
                    str(files["command_adapter_file"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--harness-file",
                    str(files["harness_file"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            validation = json.loads(
                (evidence_dir / "source_app_server_bridge_validation_packet.json").read_text()
            )
            failed = {item["name"] for item in validation["checks"] if not item["passed"]}
            self.assertIn("isolated_app_bridge_limit_truth_ok", failed)


if __name__ == "__main__":
    unittest.main()
