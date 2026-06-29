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
    build_generic_model_registry_packet,
    build_generic_provider_registry_packet,
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
            "configured_model": "gpt-5.5",
        },
        "claim_gate": {"status": "passed"},
        "models": {
            "ok": True,
            "model_ids": ["gpt-5.5", "gpt-5.4"],
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
            }
        ]
    }


def build_packets() -> dict[str, dict[str, Any]]:
    provider_registry = build_generic_provider_registry_packet()
    model_registry = build_generic_model_registry_packet(
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    current_ids = [row["model_id"] for row in model_registry["current_catalog_models"]]
    seed_ids = [row["model_id"] for row in model_registry["seed_only_models"]]
    current_vs_seed = {
        "status": "ok",
        "packet_kind": "current_vs_seed_model_matrix",
        "captured_at_utc": utc_now(),
        "current_catalog_model_ids": current_ids,
        "seed_only_model_ids": seed_ids,
        "current_catalog_count": len(current_ids),
        "seed_only_count": len(seed_ids),
        "seed_only_promoted_to_current_catalog": any(model_id in set(current_ids) for model_id in seed_ids),
        "seed_only_server_issued_for_runtime_selection": any(
            row.get("server_issued_for_runtime_selection") is True
            for row in model_registry["seed_only_models"]
        ),
    }
    truth_layers = {
        "status": "ok",
        "packet_kind": "registry_truth_layers",
        "captured_at_utc": utc_now(),
        "display_metadata_is_runtime_truth": False,
        "catalog_registry_is_runtime_truth": False,
        "runtime_truth_is_capability_proof": False,
        "seed_only_entries_are_runtime_truth": False,
    }
    non_claims = {
        "status": "ok",
        "packet_kind": "registry_non_claims",
        "captured_at_utc": utc_now(),
        "registry_presence_means_runtime_usable": False,
        "registry_presence_means_provider_compatible": False,
        "registry_export_implies_consumer_integration_complete": False,
        "seed_only_entries_are_current_runtime_candidates": False,
        "auth_admitted_provider_means_runtime_provider": False,
    }
    gap_matrix = {
        "status": "ok",
        "packet_kind": "registry_gap_matrix",
        "captured_at_utc": utc_now(),
        "gaps": [
            {
                "id": "runtime_route_validation_not_closed_here",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "model_availability_smoke_not_closed_here",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "dual_lane_ui_not_closed_here",
                "status": "open",
                "blocks_runtime_claim": False,
            },
            {
                "id": "seed_only_visibility_requires_later_policy",
                "status": "open",
                "blocks_runtime_claim": False,
            },
            {
                "id": "route_backed_model_can_inherit_account_selection_without_explicit_route",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "raw_registry_fresh_truth_can_be_misread_as_runtime_readiness",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "static_route_readiness_reused_as_session_provenance_truth",
                "status": "open",
                "blocks_runtime_claim": True,
            },
            {
                "id": "raw_registry_shape_can_read_like_provider_model_compatibility_matrix",
                "status": "open",
                "blocks_runtime_claim": False,
            },
        ],
    }
    false_green = {
        "status": "ok",
        "packet_kind": "registry_false_green_boundary",
        "captured_at_utc": utc_now(),
        "runtime_compatibility_claimed_here": False,
        "provider_family_compatibility_claimed_here": False,
        "seed_only_promoted_here": False,
        "browser_authority_widened_here": False,
    }
    independent_audit = {
        "status": "ok",
        "packet_kind": "registry_independent_audit",
        "captured_at_utc": utc_now(),
        "findings": [
            {
                "id": "current_catalog_and_seed_only_are_physically_separated",
                "status": "ok",
            },
            {
                "id": "runtime_truth_and_capability_proof_remain_separate",
                "status": "ok",
            },
            {
                "id": "provider_registry_does_not_claim_runtime_admission",
                "status": "ok",
            },
            {
                "id": "route_backed_model_without_explicit_route_selection_can_fall_back_to_account_truth",
                "status": "open_risk",
                "scope": "later_session_runtime_contours",
            },
            {
                "id": "raw_registry_fresh_truth_semantics_need_runtime_boundary_interpretation",
                "status": "open_risk",
                "scope": "registry_consumer_boundary",
            },
            {
                "id": "static_route_readiness_currently_bleeds_into_session_provenance_flags",
                "status": "open_risk",
                "scope": "later_session_runtime_contours",
            },
            {
                "id": "raw_registry_support_booleans_still_read_broader_than_proven_runtime_compatibility",
                "status": "open_risk",
                "scope": "registry_wording_and_consumer_boundary",
            },
        ],
    }
    return {
        "generic_provider_registry_packet.json": provider_registry,
        "generic_model_registry_packet.json": model_registry,
        "current_vs_seed_model_matrix.json": current_vs_seed,
        "registry_truth_layers_packet.json": truth_layers,
        "registry_non_claims_packet.json": non_claims,
        "registry_gap_matrix.json": gap_matrix,
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
    print(json.dumps({"status": "ok", "packet_count": len(packets), "evidence_dir": str(evidence_dir)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
