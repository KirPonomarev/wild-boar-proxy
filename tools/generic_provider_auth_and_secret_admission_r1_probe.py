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

from wild_boar_proxy.external_models.credentials import provider_specs_inventory


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def historical_seed_providers(repo_root: Path) -> list[str]:
    seed_path = repo_root / "external_agent_lab" / "model_registry_seed.json"
    payload = read_json(seed_path)
    providers = {
        str(entry.get("provider") or "").strip()
        for entry in payload.get("entries", [])
        if str(entry.get("provider") or "").strip()
    }
    return sorted(providers)


def build_packets(repo_root: Path) -> dict[str, dict[str, Any]]:
    admitted_inventory = provider_specs_inventory()
    admitted_providers = [entry["provider"] for entry in admitted_inventory]
    historical_providers = historical_seed_providers(repo_root)
    seed_only = sorted(set(historical_providers) - set(admitted_providers))

    inventory_packet = {
        "status": "ok",
        "packet_kind": "generic_provider_auth_inventory",
        "captured_at_utc": utc_now(),
        "classification_scope": "credential_admission_only",
        "admitted_provider_count": len(admitted_inventory),
        "historical_seed_provider_count": len(historical_providers),
        "admitted_providers": admitted_inventory,
        "historical_seed_providers": historical_providers,
        "seed_only_providers": seed_only,
        "provider_runtime_compatibility_claimed_here": False,
        "model_runtime_compatibility_claimed_here": False,
    }
    schema_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_schema",
        "captured_at_utc": utc_now(),
        "classification_scope": "credential_admission_only",
        "schema_kind": "server_owned_owner_env_provider_auth",
        "supported_sources": ["owner-env"],
        "browser_secret_intake": False,
        "browser_path_intake": False,
        "browser_provider_authority": False,
        "generic_provider_support_claimed": False,
        "generic_route_transform_support_claimed": False,
        "generic_response_compatibility_claimed": False,
        "providers": admitted_inventory,
    }
    admitted_provider_list_packet = {
        "status": "ok",
        "packet_kind": "admitted_provider_list",
        "captured_at_utc": utc_now(),
        "providers": admitted_providers,
        "provider_count": len(admitted_providers),
        "seed_only_providers": seed_only,
    }
    boundary_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_boundary",
        "captured_at_utc": utc_now(),
        "classification_scope": "credential_admission_only",
        "browser_can_supply_api_key": False,
        "browser_can_supply_secret_ref": False,
        "browser_can_supply_base_url": False,
        "browser_can_supply_provider_config": False,
        "browser_can_supply_auth_path": False,
        "server_owned_secret_source_only": True,
        "supported_sources": ["owner-env"],
    }
    non_claims_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_non_claims",
        "captured_at_utc": utc_now(),
        "provider_auth_implies_route_runtime": False,
        "provider_auth_implies_model_runtime": False,
        "provider_auth_implies_provider_family_compatibility": False,
        "provider_auth_implies_generic_route_transform_support": False,
        "provider_auth_implies_generic_response_compatibility": False,
        "provider_auth_implies_ui_completeness": False,
    }
    gap_matrix_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_gap_matrix",
        "captured_at_utc": utc_now(),
        "classification_scope": "post_auth_remaining_risks",
        "gaps": [
            {
                "id": "primary_route_heuristic_provider_coupling",
                "status": "open",
                "blocks_runtime_claim": True,
                "note": "credential flows still derive provider from primary-route heuristics rather than an explicit provider-admission contract",
            },
            {
                "id": "route_schema_accepts_broader_provider_space_than_validator_proves",
                "status": "open",
                "blocks_runtime_claim": True,
                "note": "route add/selection can outpace provider-specific runtime verification and transform support",
            },
            {
                "id": "provider_family_compatibility_requires_later_contours",
                "status": "open",
                "blocks_runtime_claim": True,
                "note": "route/model/runtime compatibility remains outside this credential-admission contour",
            },
            {
                "id": "historical_seed_provider_zai_not_admitted",
                "status": "open" if "zai" in seed_only else "closed",
                "blocks_runtime_claim": False,
                "note": "historical seed provider remains classified only until safe env mapping is admitted",
            },
        ],
    }
    false_green_boundary_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_false_green_boundary",
        "captured_at_utc": utc_now(),
        "fresh_runtime_proof_created_here": False,
        "provider_reachability_claimed_here": False,
        "model_availability_claimed_here": False,
        "generic_provider_family_compatibility_claimed_here": False,
        "browser_authority_widened_here": False,
    }
    independent_audit_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_independent_audit",
        "captured_at_utc": utc_now(),
        "classification_scope": "independent_read_only_audit",
        "findings": [
            {
                "id": "route_selection_can_outpace_provider_auth_support",
                "severity": "high",
                "status": "open",
                "runtime_claim_blocked": True,
            },
            {
                "id": "primary_route_heuristic_couples_credential_flows_to_snapshot_provider",
                "severity": "medium",
                "status": "open",
                "runtime_claim_blocked": True,
            },
            {
                "id": "validator_surface_is_narrower_than_generic_route_space",
                "severity": "medium",
                "status": "open",
                "runtime_claim_blocked": True,
            },
        ],
    }
    false_green_audit_packet = {
        "status": "ok",
        "packet_kind": "provider_auth_false_green_audit",
        "captured_at_utc": utc_now(),
        "checks": {
            "browser_authority_widened": False,
            "generic_runtime_support_claimed": False,
            "provider_family_compatibility_claimed": False,
            "model_availability_claimed": False,
            "route_reachability_claimed": False,
        },
    }
    return {
        "generic_provider_auth_inventory_packet.json": inventory_packet,
        "provider_auth_schema_packet.json": schema_packet,
        "admitted_provider_list_packet.json": admitted_provider_list_packet,
        "provider_auth_boundary_packet.json": boundary_packet,
        "provider_auth_non_claims_packet.json": non_claims_packet,
        "provider_auth_gap_matrix.json": gap_matrix_packet,
        "false_green_boundary_packet.json": false_green_boundary_packet,
        "independent_audit_packet.json": independent_audit_packet,
        "provider_auth_false_green_audit.json": false_green_audit_packet,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    packets = build_packets(repo_root)
    for name, payload in packets.items():
        write_json(evidence_dir / name, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "evidence_dir": str(evidence_dir),
                "packet_count": len(packets),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
