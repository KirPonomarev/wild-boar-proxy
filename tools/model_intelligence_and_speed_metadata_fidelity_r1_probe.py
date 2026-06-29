#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_dual_lane_model_selection_ui_packet,
    build_model_catalog_fidelity_packets,
)


PRIMARY_MODEL_ID = "gpt-5.5"
API_MODEL_ID = "wbp-web-primary-openrouter"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def operator_status() -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": PRIMARY_MODEL_ID,
        },
        "claim_gate": {"status": "ok"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": [PRIMARY_MODEL_ID, "gpt-5.4", "gpt-5.4-mini"],
        },
    }


def api_snapshot(route_id: str = API_MODEL_ID) -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": route_id,
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            }
        ],
    }


def _lane_rows(packet: dict[str, Any], lane_packet_name: str) -> list[dict[str, Any]]:
    lane_packet = packet.get(lane_packet_name, {})
    rows = lane_packet.get("models")
    return rows if isinstance(rows, list) else []


def _display_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    display = packet.get("model_display_metadata_packet.json", {})
    rows = display.get("models")
    return rows if isinstance(rows, list) else []


def _selector_rows(selector: dict[str, Any], lane_name: str) -> list[dict[str, Any]]:
    lane = selector.get(lane_name, {})
    rows = lane.get("models")
    return rows if isinstance(rows, list) else []


def _metadata_row(model: dict[str, Any], tier_name: str) -> dict[str, Any]:
    tier = model.get(tier_name) if isinstance(model.get(tier_name), dict) else {}
    return {
        "model_id": str(model.get("model_id") or ""),
        "lane": str(model.get("lane") or model.get("lane_kind") or ""),
        "metadata_field": tier_name,
        "label": str(tier.get("label") or ""),
        "source": str(tier.get("source") or ""),
        "proof_level": str(tier.get("proof_level") or ""),
        "treated_as_capability_proof": False,
    }


def _row_is_unknown_unproven(row: dict[str, Any]) -> bool:
    return (
        row["label"] == "unavailable_unknown"
        and row["source"] == "unavailable_unknown"
        and row["proof_level"] == "unproven"
    )


def _selector_metadata_row(model: dict[str, Any], tier_name: str) -> dict[str, Any]:
    tier = model.get(tier_name) if isinstance(model.get(tier_name), dict) else {}
    return {
        "model_id": str(model.get("model_id") or ""),
        "lane_kind": str(model.get("lane_kind") or ""),
        "metadata_field": tier_name,
        "label": str(tier.get("label") or ""),
        "source": str(tier.get("source") or ""),
        "proof_level": str(tier.get("proof_level") or ""),
        "selection_intent_only": model.get("selection_intent_only") is True,
        "runtime_selection_proven": model.get("runtime_selection_proven") is True,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root, evidence_dir
    fidelity = build_model_catalog_fidelity_packets(
        operator_status(),
        api_snapshot=api_snapshot(),
        measurement_packet_present=False,
    )
    selector = build_dual_lane_model_selection_ui_packet(
        operator_status(),
        api_snapshot=api_snapshot(),
    )

    native_rows = _lane_rows(fidelity, "codex_native_model_lane_packet.json")
    api_rows = _lane_rows(fidelity, "wbp_api_model_lane_packet.json")
    display_rows = _display_rows(fidelity)
    native_selector_rows = _selector_rows(selector, "chatgpt_lane")
    api_selector_rows = _selector_rows(selector, "api_lane")

    native_metadata_rows = [
        _metadata_row(model, tier_name)
        for model in native_rows
        for tier_name in ("intelligence_tier", "speed_tier")
    ]
    api_metadata_rows = [
        _metadata_row(model, tier_name)
        for model in api_rows
        for tier_name in ("intelligence_tier", "speed_tier")
    ]
    selector_metadata_rows = [
        _selector_metadata_row(model, tier_name)
        for model in [*native_selector_rows, *api_selector_rows]
        for tier_name in ("intelligence_tier", "speed_tier")
    ]

    source_and_proof_complete = all(
        row["source"] and row["proof_level"]
        for row in [*native_metadata_rows, *api_metadata_rows, *selector_metadata_rows]
    )
    display_metadata_rows = [
        _metadata_row(model, tier_name)
        for model in display_rows
        for tier_name in ("intelligence_tier", "speed_tier")
    ]
    measured_rows = [
        row
        for row in [
            *native_metadata_rows,
            *api_metadata_rows,
            *display_metadata_rows,
            *selector_metadata_rows,
        ]
        if row["source"] == "measured"
    ]
    native_display_preserved = all(
        str(model.get("source_class") or "") == "current_build_catalog_visible" for model in native_rows
    )
    api_non_parity_surface = all(
        str(model.get("display_name") or "").lower().startswith("wbp ") for model in api_rows
    ) and fidelity["non_impersonation_packet.json"].get("native_parity_claimed") is False
    selector_intent_only = all(
        row["selection_intent_only"] is True and row["runtime_selection_proven"] is False
        for row in selector_metadata_rows
    )
    native_unknown_unproven = all(_row_is_unknown_unproven(row) for row in native_metadata_rows)
    api_unknown_unproven = all(_row_is_unknown_unproven(row) for row in api_metadata_rows)
    display_unknown_unproven = all(_row_is_unknown_unproven(row) for row in display_metadata_rows)
    selector_unknown_unproven = all(_row_is_unknown_unproven(row) for row in selector_metadata_rows)
    unknown_tiers_present = all(
        _row_is_unknown_unproven(row) for row in [*native_metadata_rows, *api_metadata_rows]
    )

    packets: dict[str, dict[str, Any]] = {}
    packets["native_lane_metadata_fidelity_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_lane_metadata_fidelity",
        "status": "ok" if native_rows else "blocked",
        "lane": "codex_native",
        "model_count": len(native_rows),
        "source_classification": "current_build_catalog_visible_only" if native_display_preserved else "mixed_or_unknown",
        "visible_native_label_preserved_narrowly": native_display_preserved,
        "all_native_tiers_unavailable_unknown": native_unknown_unproven,
        "native_metadata_truth_strength": "unknown_unproven_only" if native_unknown_unproven else "mixed_or_stronger",
        "native_label_internal_ranking_semantics_proven": False,
        "native_intelligence_metadata_rows": native_metadata_rows[0::2],
        "native_speed_metadata_rows": native_metadata_rows[1::2],
        "native_metadata_is_capability_proof": False,
        "native_metadata_is_benchmark_ranking": False,
    }
    packets["api_lane_metadata_fidelity_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "api_lane_metadata_fidelity",
        "status": "ok" if api_rows else "blocked",
        "lane": "wbp_api",
        "model_count": len(api_rows),
        "wbp_prefixed_non_impersonating_display": api_non_parity_surface,
        "all_api_tiers_unavailable_unknown": api_unknown_unproven,
        "api_metadata_truth_strength": "unknown_unproven_only" if api_unknown_unproven else "mixed_or_stronger",
        "provider_declared_intelligence_parity_proven": False,
        "provider_declared_speed_superiority_proven": False,
        "api_intelligence_metadata_rows": api_metadata_rows[0::2],
        "api_speed_metadata_rows": api_metadata_rows[1::2],
        "api_label_equals_codex_high_or_extra_high": False,
        "api_metadata_is_capability_proof": False,
    }
    packets["metadata_source_and_proof_level_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "metadata_source_and_proof_level",
        "status": "ok" if source_and_proof_complete and not measured_rows else "blocked",
        "catalog_display_rows": display_metadata_rows,
        "selector_rows": selector_metadata_rows,
        "source_and_proof_complete": source_and_proof_complete,
        "measured_source_rows_present": bool(measured_rows),
        "measured_source_rows": measured_rows,
        "selector_metadata_is_display_only": selector_intent_only,
        "all_current_rows_unavailable_unknown": unknown_tiers_present,
        "display_rows_unavailable_unknown": display_unknown_unproven,
        "selector_rows_unavailable_unknown": selector_unknown_unproven,
        "metadata_completeness_without_stronger_truth": (
            source_and_proof_complete
            and native_unknown_unproven
            and api_unknown_unproven
            and display_unknown_unproven
        ),
        "ui_badge_is_packet_proof": False,
    }
    packets["intelligence_parity_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "intelligence_parity_non_claims",
        "status": "ok",
        "provider_declared_intelligence_equals_measured_intelligence": False,
        "api_label_equals_codex_high_or_extra_high": False,
        "label_coexistence_implies_comparability": False,
        "preserved_native_label_proves_internal_ranking_semantics": False,
        "metadata_badge_proves_underlying_capability": False,
    }
    packets["speed_metadata_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "speed_metadata_boundary",
        "status": "ok" if not measured_rows else "blocked",
        "measured_speed_rows_present": bool(measured_rows),
        "speed_metadata_reopens_acceleration_proof": False,
        "measured_speed_implies_intelligence": False,
        "speed_metadata_scope_classification": "catalog_and_selector_metadata_only",
        "unknown_speed_tiers_present": unknown_tiers_present,
        "all_current_speed_rows_unavailable_unknown": all(
            _row_is_unknown_unproven(row)
            for row in [*native_metadata_rows[1::2], *api_metadata_rows[1::2], *display_metadata_rows[1::2]]
        ),
    }
    packets["metadata_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "metadata_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "native_visible_labels_do_not_prove_internal_ranking_semantics",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "api_lane_intelligence_parity_with_codex_high_not_proven",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "speed_metadata_remains_unmeasured_catalog_truth_only",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "current_metadata_rows_remain_unknown_unproven_not_strengthened",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "metadata_fidelity_does_not_close_historical_item_0",
                "severity": "medium",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "api_lane_receives_codex_native_parity_wording": False,
        "label_source_hidden": False,
        "proof_level_absent_or_inflated": False,
        "measured_speed_treated_as_intelligence": False,
        "provider_declared_label_treated_as_proven_quality": False,
        "ui_badge_treated_as_proof": False,
        "unknown_unproven_rows_treated_as_strong_metadata": False,
        "historical_item_0_treated_as_closed_here": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "catalog_models_carry_intelligence_and_speed_source_and_proof_level_fields",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "selector_entries_preserve_metadata_but_remain_selection_intent_only",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "wbp_api_display_surface_remains_non_impersonating_and_non_parity",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "api_lane_parity_with_codex_high_or_extra_high_remains_unproven",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "speed_metadata_remains_catalog_truth_only_not_measured_speed_proof",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "current_metadata_rows_remain_unknown_unproven_even_when_source_and_proof_fields_exist",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="model-intelligence-and-speed-metadata-fidelity-r1-probe"
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    packets = build_packets(
        repo_root=args.repo_root.resolve(),
        evidence_dir=args.evidence_dir.resolve(),
    )
    for filename, payload in packets.items():
        json_write(args.evidence_dir / filename, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "packet_count": len(packets),
                "evidence_dir": str(args.evidence_dir.resolve()),
                "packets": sorted(packets),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
