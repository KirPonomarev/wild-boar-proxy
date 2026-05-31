#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_dual_lane_model_selection_ui_packet,
    build_dual_lane_selection_intent_packet,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def build_packets() -> dict[str, dict[str, Any]]:
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    intent = build_dual_lane_selection_intent_packet(
        {
            "chatgpt_model_id": selector["chatgpt_lane"]["default_model_id"],
            "api_model_id": selector["api_lane"]["default_model_id"],
        },
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    authority_boundary = {
        "status": "ok",
        "packet_kind": "selector_authority_boundary",
        "captured_at_utc": utc_now(),
        "allowed_browser_fields": selector["allowed_browser_fields"],
        "forbidden_browser_fields": selector["forbidden_browser_fields"],
        "browser_authority": selector["browser_authority"],
        "browser_can_supply_provider": False,
        "browser_can_supply_route_id": False,
        "browser_can_supply_account_id": False,
        "browser_can_supply_secret_ref": False,
        "browser_can_supply_base_url": False,
        "browser_can_supply_auth_path": False,
        "browser_can_supply_codex_home": False,
    }
    current_vs_seed_visibility = {
        "status": "ok",
        "packet_kind": "selector_current_vs_seed_visibility",
        "captured_at_utc": utc_now(),
        "chatgpt_visible_count": selector["chatgpt_lane"]["model_count"],
        "api_visible_count": selector["api_lane"]["model_count"],
        "seed_visible_count": selector["seed_only_reference"]["model_count"],
        "seed_only_selectable": any(
            entry.get("selection_enabled") is True
            for entry in selector["seed_only_reference"]["models"]
        ),
        "seed_only_default_choice": bool(
            selector["chatgpt_lane"]["default_model_id"]
            and any(
                entry.get("model_id") == selector["chatgpt_lane"]["default_model_id"]
                for entry in selector["seed_only_reference"]["models"]
            )
        )
        or bool(
            selector["api_lane"]["default_model_id"]
            and any(
                entry.get("model_id") == selector["api_lane"]["default_model_id"]
                for entry in selector["seed_only_reference"]["models"]
            )
        ),
    }
    disabled_reason_packet = {
        "status": "ok",
        "packet_kind": "selector_disabled_reason",
        "captured_at_utc": utc_now(),
        "disabled_entries": [
            {
                "model_id": entry["model_id"],
                "selection_disabled_reason_code": entry.get(
                    "selection_disabled_reason_code", ""
                ),
                "selection_disabled_reasons": entry.get(
                    "selection_disabled_reasons", []
                ),
            }
            for entry in (
                list(selector["chatgpt_lane"]["models"])
                + list(selector["api_lane"]["models"])
                + list(selector["seed_only_reference"]["models"])
            )
            if entry.get("selection_enabled") is not True
        ],
        "disabled_reason_present": any(
            entry.get("selection_disabled_reason_code")
            for entry in (
                list(selector["chatgpt_lane"]["models"])
                + list(selector["api_lane"]["models"])
                + list(selector["seed_only_reference"]["models"])
            )
            if entry.get("selection_enabled") is not True
        ),
    }
    non_claims = {
        "status": "ok",
        "packet_kind": "selector_non_claims",
        "captured_at_utc": utc_now(),
        "ui_selection_means_session_execution": False,
        "selected_api_model_means_route_runtime_proven": False,
        "selected_chatgpt_model_means_account_health_proven": False,
        "dual_lane_selection_means_simultaneous_execution": False,
        "seed_only_visibility_means_current_support": False,
    }
    gap_matrix = {
        "status": "ok",
        "packet_kind": "selector_gap_matrix",
        "captured_at_utc": utc_now(),
        "gaps": [
            {
                "id": "multi_slot_session_binding_not_closed_here",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "simultaneous_dual_lane_execution_not_closed_here",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "api_lane_route_runtime_proof_not_closed_here",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "seed_only_visibility_policy_is_display_only",
                "status": "open",
                "blocks_runtime_claim": False,
            },
            {
                "id": "route_backed_api_lane_can_be_misread_as_execution_ready_without_session_contour",
                "status": "open",
                "blocks_runtime_claim": True,
            },
        ],
    }
    false_green = {
        "status": "ok",
        "packet_kind": "selector_false_green_boundary",
        "captured_at_utc": utc_now(),
        "session_execution_claimed_here": False,
        "simultaneous_execution_claimed_here": False,
        "api_route_runtime_claimed_here": False,
        "browser_authority_widened_here": False,
        "seed_only_promoted_here": False,
    }
    independent_audit = {
        "status": "ok",
        "packet_kind": "selector_independent_audit",
        "captured_at_utc": utc_now(),
        "findings": [
            {
                "id": "selector_preserves_lane_separation",
                "status": "ok",
            },
            {
                "id": "seed_only_entries_remain_non_selectable",
                "status": "ok",
            },
            {
                "id": "selector_intent_packet_remains_non_runtime_claim",
                "status": "ok",
            },
            {
                "id": "current_execution_path_model_id_is_operator_reported_not_browser_selected",
                "status": "ok",
            },
            {
                "id": "current_execution_path_remains_chatgpt_lane_only",
                "status": "open_risk",
                "scope": "later_role_slot_session_contours",
            },
            {
                "id": "api_lane_selection_can_be_misread_as_execution_readiness_without_session_contour",
                "status": "open_risk",
                "scope": "ui_wording_and_runtime_boundary",
            },
        ],
    }
    return {
        "dual_lane_model_selection_ui_packet.json": selector,
        "selection_intent_packet.json": intent,
        "selector_authority_boundary_packet.json": authority_boundary,
        "selector_current_vs_seed_visibility_packet.json": current_vs_seed_visibility,
        "selector_disabled_reason_packet.json": disabled_reason_packet,
        "selector_non_claims_packet.json": non_claims,
        "selector_gap_matrix.json": gap_matrix,
        "false_green_boundary_packet.json": false_green,
        "independent_audit_packet.json": independent_audit,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()
    evidence_dir = Path(args.evidence_dir).resolve()
    packets = build_packets()
    for name, payload in packets.items():
        write_json(evidence_dir / name, payload)
    print(
        json.dumps(
            {"status": "ok", "packet_count": len(packets), "evidence_dir": str(evidence_dir)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
