# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy.codex_model_registry import (
    build_dual_lane_model_selection_ui_packet,
    build_dual_lane_selection_intent_packet,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "custom_codex_dual_lane_model_selection_ui_r1_probe.py"


def operator_status() -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.4",
        },
        "claim_gate": {"status": "blocked_by_runtime_truth_gate"},
        "models": {
            "ok": True,
            "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
            "server_issued": True,
        },
    }


def api_snapshot() -> dict[str, object]:
    return {
        "routes": [
            {
                "route_id": "wbp-web-primary-openrouter",
                "provider": "openrouter",
                "upstream_model": "openrouter/upstream",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            },
            {
                "route_id": "wbp-disabled-openrouter",
                "provider": "openrouter",
                "upstream_model": "openrouter/disabled",
                "enabled": False,
                "secret_ref": "",
            },
        ]
    }


class CustomCodexDualLaneModelSelectionUiR1ProbeTests(unittest.TestCase):
    def test_selector_packet_preserves_lane_boundaries(self) -> None:
        selector = build_dual_lane_model_selection_ui_packet(
            operator_status(),
            api_snapshot=api_snapshot(),
        )

        self.assertTrue(selector["server_issued"])
        self.assertFalse(selector["selector_runtime_readiness_claimed"])
        self.assertFalse(selector["simultaneous_execution_proven"])
        self.assertEqual(selector["allowed_browser_fields"], ["chatgpt_model_id", "api_model_id"])
        self.assertIn("model_id", selector["forbidden_browser_fields"])
        self.assertTrue(
            all(entry["lane_kind"] == "codex_native" for entry in selector["chatgpt_lane"]["models"])
        )
        self.assertTrue(
            all(entry["lane_kind"] == "wbp_api" for entry in selector["api_lane"]["models"])
        )
        self.assertTrue(
            all(entry["selection_enabled"] is False for entry in selector["seed_only_reference"]["models"])
        )

    def test_selection_intent_packet_stays_non_runtime_and_server_issued(self) -> None:
        selector = build_dual_lane_model_selection_ui_packet(
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        packet = build_dual_lane_selection_intent_packet(
            {
                "chatgpt_model_id": selector["chatgpt_lane"]["default_model_id"],
                "api_model_id": selector["api_lane"]["default_model_id"],
            },
            operator_status(),
            api_snapshot=api_snapshot(),
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["selection_intent_only"])
        self.assertFalse(packet["selector_runtime_readiness_claimed"])
        self.assertFalse(packet["session_execution_wired"])
        self.assertFalse(packet["simultaneous_execution_proven"])
        self.assertTrue(packet["selected_models_are_server_issued"])
        self.assertEqual(packet["current_execution_path_model_id"], "gpt-5.4")
        self.assertEqual(packet["current_execution_path_source"], "operator_reported_configured_model")
        self.assertFalse(packet["browser_selected_chatgpt_matches_current_execution_path"])
        self.assertEqual(packet["current_execution_path_scope"], "chatgpt_lane_only_in_this_contour")
        self.assertEqual(packet["api_lane_scope"], "selection_intent_only_until_role_slot_session_contour")

    def test_probe_writes_packets_and_keeps_seed_and_runtime_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_dir = Path(tmpdir) / "evidence"
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--repo-root",
                    str(ROOT),
                    "--evidence-dir",
                    str(evidence_dir),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["packet_count"], 9)

            selector = json.loads(
                (evidence_dir / "dual_lane_model_selection_ui_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(selector["selector_runtime_readiness_claimed"])
            self.assertFalse(selector["flat_model_truth_presented"])

            intent = json.loads(
                (evidence_dir / "selection_intent_packet.json").read_text(encoding="utf-8")
            )
            self.assertTrue(intent["selection_intent_only"])
            self.assertTrue(intent["selected_models_are_server_issued"])
            self.assertFalse(intent["session_execution_wired"])
            self.assertEqual(intent["current_execution_path_model_id"], "gpt-5.4")
            self.assertFalse(intent["browser_selected_chatgpt_matches_current_execution_path"])

            visibility = json.loads(
                (evidence_dir / "selector_current_vs_seed_visibility_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreaterEqual(visibility["seed_visible_count"], 1)
            self.assertFalse(visibility["seed_only_selectable"])
            self.assertFalse(visibility["seed_only_default_choice"])

            boundary = json.loads(
                (evidence_dir / "selector_authority_boundary_packet.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(boundary["browser_can_supply_provider"])
            self.assertFalse(boundary["browser_can_supply_route_id"])
            self.assertFalse(boundary["browser_can_supply_account_id"])

            gaps = json.loads(
                (evidence_dir / "selector_gap_matrix.json").read_text(encoding="utf-8")
            )
            gap_ids = {gap["id"] for gap in gaps["gaps"]}
            self.assertIn("multi_slot_session_binding_not_closed_here", gap_ids)
            self.assertIn(
                "route_backed_api_lane_can_be_misread_as_execution_ready_without_session_contour",
                gap_ids,
            )
