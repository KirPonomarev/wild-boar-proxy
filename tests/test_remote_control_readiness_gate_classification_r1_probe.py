# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RemoteControlReadinessGateClassificationR1ProbeTests(unittest.TestCase):
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

    def _write_source_files(self, root: Path, *, loopback_web_files: bool = True) -> dict[str, Path]:
        live_server = root / "wild_boar_proxy" / "web_design_live_server.py"
        web_ui = root / "wild_boar_proxy" / "web_ui.py"
        harness = root / "tools" / "operator_control_surface_harness.py"

        default_host = "127.0.0.1" if loopback_web_files else "0.0.0.0"
        live_server.write_text(
            f'''
import argparse
def owner_authorization_phrase_present(value): return True
def build_handler():
    class Handler:
        def do_GET(self):
            if parsed.path == "/api/actions":
                return
            if parsed.path == "/api/operator/status":
                return
        def do_POST(self):
            if parsed.path == "/api/operator/run":
                return
            if parsed.path == "/api/action":
                return
        def log_message(self, fmt, *args):
            return
    return Handler
def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="{default_host}")
''',
            encoding="utf-8",
        )
        web_ui.write_text(
            f'''
import argparse
def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="{default_host}")
    return parser
''',
            encoding="utf-8",
        )
        harness.write_text(
            '''
from http.server import ThreadingHTTPServer
def run_server(args):
    server = ThreadingHTTPServer(("127.0.0.1", 9999), None)
    class Handler:
        def do_GET(self):
            if parsed.path == "/api/status":
                return
            if parsed.path == "/api/models":
                return
        def do_POST(self):
            if parsed.path == "/api/run":
                return
        def log_message(self, fmt, *args):
            return
''',
            encoding="utf-8",
        )
        return {
            "web_live_server_file": live_server,
            "web_ui_file": web_ui,
            "harness_file": harness,
        }

    def _write_sources(self, root: Path) -> dict[str, Path]:
        dirs = {
            "provider_auth": root / "audit_results" / "provider_auth",
            "web_menu": root / "audit_results" / "web_menu",
            "login_bridge": root / "audit_results" / "login_bridge",
            "operator_ready": root / "audit_results" / "operator_ready",
        }
        for path in dirs.values():
            path.mkdir(parents=True)

        provider_auth_packets = {
            "authority_boundary_packet.json": {
                "status": "ok",
                "browser_can_supply_token_path_model_provider_authority": False,
                "remote_can_supply_token_path_model_provider_authority": False,
                "browser_allowed_request_shape": ["server-approved profile"],
                "server_owns_model_route_selection": True,
                "server_owns_provider_endpoint_selection": True,
                "server_owns_secret_redaction": True,
                "semantic_alias_coverage_proven": False,
            },
            "provider_auth_browser_authority_packet.json": {
                "status": "ok",
                "browser_can_supply_token_path_model_provider_authority": False,
                "remote_can_supply_token_path_model_provider_authority": False,
            },
            "provider_auth_source_inventory_packet.json": {
                "status": "ok",
                "all_auth_sources_classified": True,
            },
            "provider_auth_strategy_summary_packet.json": {
                "status": "ok",
                "selected_strategy": "auth.command",
                "silent_fallback_detected": False,
            },
            "auth_strategy_false_green_audit.json": {"status": "ok"},
        }
        for name, packet in provider_auth_packets.items():
            self._write_json(root, f"audit_results/provider_auth/{name}", packet)

        web_menu_packets = {
            "baseline.json": {
                "status": "ok",
                "actions_count": 3,
                "action_phase": "sandbox_actions",
            },
            "proof.json": {
                "status": "ok",
                "live_checks": {"actions_status": 200},
                "assertions": {"sync_truthfully_parked": True},
                "packets": {
                    "api_route_credential_check": {
                        "result": {
                            "data": {
                                "browser_secret_intake": False,
                                "browser_path_intake": False,
                            }
                        }
                    }
                },
            },
            "independent_audit.json": {"status": "pass"},
        }
        for name, packet in web_menu_packets.items():
            self._write_json(root, f"audit_results/web_menu/{name}", packet)

        login_bridge_packets = {
            "evidence/browser-run-summary.json": {
                "status": "ok",
                "server_url": "http://127.0.0.1:61608/?screen=quick-start",
                "login_bridge": {
                    "browser_secret_intake": False,
                    "browser_path_intake": False,
                },
                "raw_auth_ref_exposed_in_action_response": False,
            },
            "independent_audit.json": {"status": "pass_after_fixes"},
        }
        for name, packet in login_bridge_packets.items():
            self._write_json(root, f"audit_results/login_bridge/{name}", packet)

        operator_ready_packets = {
            "operator_recovery_matrix.json": {
                "assertions": {
                    "bounded_local_operator_surface_ready": True,
                },
                "diagnostics_failure_guard_packet": {
                    "actions": [
                        {"id": "process_kill_live", "classification": "visible_disabled"},
                        {"id": "touch_original_codex", "classification": "visible_disabled"},
                        {"id": "rollback_apply_admission", "classification": "dry_run_admission"},
                        {"id": "stop_cleanup_live", "classification": "admitted_live_performed"},
                    ]
                },
            },
            "browser_projection_proof.json": {
                "status": "passed",
                "url": "http://127.0.0.1:8791/",
                "endpoint": {
                    "bounded_local_operator_surface_ready": True,
                    "diagnostics_export_redacted": True,
                },
                "forbidden_query_probe": {
                    "status": "blocked",
                },
            },
            "independent_audit.json": {"status": "passed_after_repair"},
        }
        for name, packet in operator_ready_packets.items():
            self._write_json(root, f"audit_results/operator_ready/{name}", packet)

        return dirs

    def test_probe_classifies_remote_readiness_with_limits(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "remote_control_readiness_gate_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            files = self._write_source_files(temp_repo)
            evidence_dir = temp_repo / "audit_results" / "remote_readiness"

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
                    "--web-menu-dir",
                    str(dirs["web_menu"]),
                    "--login-bridge-dir",
                    str(dirs["login_bridge"]),
                    "--operator-ready-dir",
                    str(dirs["operator_ready"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--web-ui-file",
                    str(files["web_ui_file"]),
                    "--harness-file",
                    str(files["harness_file"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (evidence_dir / "remote_control_readiness_summary_packet.json").read_text()
            )
            enforcement = json.loads(
                (evidence_dir / "remote_control_enforcement_boundary_packet.json").read_text()
            )
            inventory = json.loads(
                (evidence_dir / "remote_control_surface_inventory_packet.json").read_text()
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(
                summary["final_status"],
                "WBP_REMOTE_CONTROL_READINESS_GATE_CLASSIFIED_WITH_LIMITS",
            )
            self.assertFalse(enforcement["public_exposure_fully_enforced_for_all_surfaces"])
            self.assertEqual(inventory["surface_count"], 3)

    def test_probe_accepts_historical_source_packets_without_top_level_status(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "remote_control_readiness_gate_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            files = self._write_source_files(temp_repo)

            baseline_path = dirs["web_menu"] / "baseline.json"
            baseline = json.loads(baseline_path.read_text())
            baseline.pop("status", None)
            baseline["focus_actions"] = {"api_route_credential_check": {"available": True}}
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

            proof_path = dirs["web_menu"] / "proof.json"
            proof = json.loads(proof_path.read_text())
            proof.pop("status", None)
            proof_path.write_text(json.dumps(proof), encoding="utf-8")

            operator_path = dirs["operator_ready"] / "operator_recovery_matrix.json"
            operator = json.loads(operator_path.read_text())
            operator.pop("status", None)
            operator["diagnostics_failure_guard_packet"]["actions"].append(
                {"id": "touch_original_codex", "classification": "visible_disabled"}
            )
            operator_path.write_text(json.dumps(operator), encoding="utf-8")

            evidence_dir = temp_repo / "audit_results" / "remote_readiness"

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
                    "--web-menu-dir",
                    str(dirs["web_menu"]),
                    "--login-bridge-dir",
                    str(dirs["login_bridge"]),
                    "--operator-ready-dir",
                    str(dirs["operator_ready"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--web-ui-file",
                    str(files["web_ui_file"]),
                    "--harness-file",
                    str(files["harness_file"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            validation = json.loads(
                (evidence_dir / "source_remote_control_validation_packet.json").read_text()
            )
            failed = [item["name"] for item in validation["checks"] if not item["passed"]]
            self.assertEqual(failed, [])

    def test_probe_blocks_when_browser_authority_is_admitted(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "remote_control_readiness_gate_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            files = self._write_source_files(temp_repo)
            bad = dirs["provider_auth"] / "authority_boundary_packet.json"
            packet = json.loads(bad.read_text())
            packet["browser_can_supply_token_path_model_provider_authority"] = True
            bad.write_text(json.dumps(packet), encoding="utf-8")
            evidence_dir = temp_repo / "audit_results" / "remote_readiness"

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
                    "--web-menu-dir",
                    str(dirs["web_menu"]),
                    "--login-bridge-dir",
                    str(dirs["login_bridge"]),
                    "--operator-ready-dir",
                    str(dirs["operator_ready"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--web-ui-file",
                    str(files["web_ui_file"]),
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
                (evidence_dir / "source_remote_control_validation_packet.json").read_text()
            )
            failed = {item["name"] for item in validation["checks"] if not item["passed"]}
            self.assertIn("provider_auth_boundaries_ok", failed)

    def test_probe_blocks_when_surface_inventory_is_not_loopback_default(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tool = repo_root / "tools" / "remote_control_readiness_gate_classification_r1_probe.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_repo = Path(tmpdir)
            self._init_repo(temp_repo)
            dirs = self._write_sources(temp_repo)
            files = self._write_source_files(temp_repo, loopback_web_files=False)
            evidence_dir = temp_repo / "audit_results" / "remote_readiness"

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
                    "--web-menu-dir",
                    str(dirs["web_menu"]),
                    "--login-bridge-dir",
                    str(dirs["login_bridge"]),
                    "--operator-ready-dir",
                    str(dirs["operator_ready"]),
                    "--web-live-server-file",
                    str(files["web_live_server_file"]),
                    "--web-ui-file",
                    str(files["web_ui_file"]),
                    "--harness-file",
                    str(files["harness_file"]),
                ],
                cwd=repo_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1, result.stderr)
            inventory = json.loads(
                (evidence_dir / "remote_control_surface_inventory_packet.json").read_text()
            )
            self.assertEqual(inventory["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
