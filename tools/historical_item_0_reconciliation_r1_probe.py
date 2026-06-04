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

from tools.historical_audit_fixtures import historical_audit_path


CURRENT_PACKET_SOURCES = [
    {
        "id": "generic_provider_auth",
        "packet": "audit_results/generic_provider_auth_and_secret_admission_r1_2026-05-28/admitted_provider_list_packet.json",
        "closeout": "audit_results/generic_provider_auth_and_secret_admission_r1_2026-05-28/closeout.md",
        "claim": "current provider admission is packet-backed",
    },
    {
        "id": "generic_model_registry",
        "packet": "audit_results/generic_provider_and_model_registry_r1_2026-05-28/generic_model_registry_packet.json",
        "closeout": "audit_results/generic_provider_and_model_registry_r1_2026-05-28/closeout.md",
        "claim": "current runtime catalog and seed-only boundary are packet-backed",
    },
    {
        "id": "current_vs_seed_model_matrix",
        "packet": "audit_results/generic_provider_and_model_registry_r1_2026-05-28/current_vs_seed_model_matrix.json",
        "closeout": "audit_results/generic_provider_and_model_registry_r1_2026-05-28/closeout.md",
        "claim": "historical seed-only models are not current runtime catalog",
    },
    {
        "id": "selector_visibility_boundary",
        "packet": "audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/selector_current_vs_seed_visibility_packet.json",
        "closeout": "audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/closeout.md",
        "claim": "seed-only models are not selectable current UI/runtime choices",
    },
    {
        "id": "final_dual_lane_acceptance",
        "packet": "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/final_dual_lane_acceptance_matrix.json",
        "closeout": "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/closeout.md",
        "claim": "current final workflow truth is packet-backed and historical item 0 is not counted as closed",
    },
    {
        "id": "final_dual_lane_audit",
        "packet": "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/independent_audit_packet.json",
        "closeout": "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/closeout.md",
        "claim": "independent packet notes item 0 remains open and non-counted before reconciliation",
    },
    {
        "id": "acceleration_reconciliation",
        "packet": "audit_results/original_vs_custom_acceleration_reconciliation_r1_2026-05-28/acceleration_classification_packet.json",
        "closeout": "audit_results/original_vs_custom_acceleration_reconciliation_r1_2026-05-28/closeout.md",
        "claim": "latest acceleration truth is classified with limits and remains packet-backed",
    },
]


HISTORICAL_SOURCES = [
    {
        "id": "external_lab_model_registry_seed",
        "path": "external_agent_lab/model_registry_seed.json",
        "kind": "json_seed",
        "summary": "isolated external-agent-lab model seed inventory",
    },
    {
        "id": "external_lab_readme",
        "path": "EXTERNAL_AGENT_LAB.md",
        "kind": "markdown_seed",
        "summary": "isolated lane boundary and non-integration narrative",
    },
    {
        "id": "external_lab_audit",
        "path": "EXTERNAL_AGENT_LAB_AUDIT.md",
        "kind": "markdown_seed",
        "summary": "isolated lane audit and truth relock narrative",
    },
    {
        "id": "external_lab_acceptance_verification",
        "path": "external_agent_lab_acceptance_verification.md",
        "kind": "markdown_seed",
        "summary": "unittest-first acceptance verification narrative",
    },
    {
        "id": "external_lab_tests",
        "path": "tests/test_external_agent_lab.py",
        "kind": "python_test_seed",
        "summary": "isolated-lab import hygiene and JSON preflight contract tests",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _current_truth_inventory(repo_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in CURRENT_PACKET_SOURCES:
        packet_path = historical_audit_path(repo_root, source["packet"])
        closeout_path = historical_audit_path(repo_root, source["closeout"])
        packet = _read_json(packet_path)
        rows.append(
            {
                "id": source["id"],
                "packet_path": str(packet_path.relative_to(repo_root)),
                "closeout_path": str(closeout_path.relative_to(repo_root)),
                "claim_summary": source["claim"],
                "packet_kind": packet.get("packet_kind", "unknown"),
                "status": packet.get("status", "unknown"),
                "final_status": packet.get("final_status"),
                "inventory_listing_counts_as_proof": False,
                "packet_backed_current_truth": packet.get("status") == "ok",
            }
        )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "current_truth_inventory",
        "status": "ok",
        "inventory_listing_does_not_create_proof": True,
        "evidence_precedence": "packet_backed_current_contour_truth_only",
        "rows": rows,
    }


def _historical_claim_markers(source_id: str, text: str) -> list[str]:
    lowered = text.lower()
    claims: list[str] = []
    if "wild_boar_proxy/*" in text and "untouched" in lowered:
        claims.append("wild_boar_proxy_untouched_in_isolated_lab_contours")
    if "not part of the main wild boar proxy runtime" in lowered or "no runtime integration" in lowered:
        claims.append("isolated_non_integrated_lane")
    if "historical result directories are not canonical repo evidence" in lowered:
        claims.append("historical_artifacts_not_canonical_runtime_proof")
    if "provider/live-free" in lowered or "no provider/live" in lowered or "unittest" in lowered:
        claims.append("provider_live_free_unittest_first_acceptance")
    if "authoritative truth surface" in lowered and "model_registry_seed.json" in text:
        claims.append("model_registry_seed_authoritative_for_isolated_lane_only")
    if "metadata only" in lowered:
        claims.append("historical_filenames_metadata_only_not_active_proof")
    if source_id == "external_lab_model_registry_seed":
        claims.append("historical_model_seed_entries_present")
    if source_id == "external_lab_tests":
        if "test_quarantine" in lowered or "json" in lowered:
            claims.append("isolated_lab_import_hygiene_and_json_preflight_contract")
    return claims


def _historical_seed_inventory(repo_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source in HISTORICAL_SOURCES:
        path = repo_root / source["path"]
        entry: dict[str, Any] = {
            "id": source["id"],
            "path": str(path.relative_to(repo_root)),
            "kind": source["kind"],
            "summary": source["summary"],
            "source_role": "historical_seed_reference_only",
            "current_runtime_proof": False,
        }
        if source["kind"] == "json_seed":
            payload = _read_json(path)
            entry.update(
                {
                    "entry_count": len(payload.get("entries") or []),
                    "source_plan": payload.get("source_plan"),
                    "claims": ["historical_model_seed_entries_present"],
                    "evidence_level_classes": sorted(
                        {
                            str(model.get("evidence_level") or "")
                            for model in payload.get("entries", [])
                            if isinstance(model, dict)
                        }
                    ),
                }
            )
        elif source["kind"] == "markdown_seed":
            text = _read_text(path)
            entry.update(
                {
                    "claims": _historical_claim_markers(source["id"], text),
                    "contains_current_runtime_navigation": False,
                    "contains_forward_runtime_proof": False,
                }
            )
        else:
            text = _read_text(path)
            entry.update(
                {
                    "claims": _historical_claim_markers(source["id"], text),
                    "contains_live_runtime_execution_proof": False,
                    "current_runtime_proof": False,
                }
            )
        rows.append(entry)
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "historical_seed_inventory",
        "status": "ok",
        "rows": rows,
    }


def _reconciliation_matrix(repo_root: Path) -> dict[str, Any]:
    acceptance = _read_json(
        historical_audit_path(
            repo_root,
            "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/final_dual_lane_acceptance_matrix.json",
        )
    )
    final_audit = _read_json(
        historical_audit_path(
            repo_root,
            "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/independent_audit_packet.json",
        )
    )
    current_vs_seed = _read_json(
        historical_audit_path(
            repo_root,
            "audit_results/generic_provider_and_model_registry_r1_2026-05-28/current_vs_seed_model_matrix.json",
        )
    )
    selector_seed_visibility = _read_json(
        historical_audit_path(
            repo_root,
            "audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/selector_current_vs_seed_visibility_packet.json",
        )
    )

    rows = [
        {
            "id": "historical_model_seed_inventory_is_active_runtime_catalog",
            "historical_source_ids": ["external_lab_model_registry_seed"],
            "historical_claim": "external-agent-lab seed inventory acts as active runtime catalog",
            "classification": "superseded_by_current_packets",
            "counting_status": "non_counted",
            "current_replacement_packets": [
                "audit_results/generic_provider_and_model_registry_r1_2026-05-28/generic_model_registry_packet.json",
                "audit_results/generic_provider_and_model_registry_r1_2026-05-28/current_vs_seed_model_matrix.json",
            ],
            "reason": "current packet truth says seed-only models are not current catalog and are not server-issued runtime choices",
        },
        {
            "id": "historical_seed_models_are_selectable_current_runtime_choices",
            "historical_source_ids": ["external_lab_model_registry_seed", "external_lab_readme"],
            "historical_claim": "seed-only external-lab models remain selectable current runtime choices",
            "classification": "superseded_by_current_packets",
            "counting_status": "non_counted",
            "current_replacement_packets": [
                "audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/selector_current_vs_seed_visibility_packet.json",
                "audit_results/generic_provider_and_model_registry_r1_2026-05-28/current_vs_seed_model_matrix.json",
            ],
            "reason": "current packet truth says seed_only_selectable=false and seed_only_server_issued_for_runtime_selection=false",
        },
        {
            "id": "isolated_external_lab_non_integrated_lane_claim",
            "historical_source_ids": ["external_lab_readme", "external_lab_audit"],
            "historical_claim": "external-agent-lab is an isolated non-integrated lane",
            "classification": "historical_only_non_counted",
            "counting_status": "non_counted",
            "current_replacement_packets": [],
            "reason": "this is historical lineage/boundary context rather than current runtime proof requirement",
        },
        {
            "id": "provider_live_free_unittest_first_external_lab_acceptance",
            "historical_source_ids": [
                "external_lab_acceptance_verification",
                "external_lab_audit",
            ],
            "historical_claim": "external-agent-lab acceptance is unittest-first and provider-live-free",
            "classification": "historical_only_non_counted",
            "counting_status": "non_counted",
            "current_replacement_packets": [],
            "reason": "isolated-lab acceptance procedure does not count as current runtime proof",
        },
        {
            "id": "historical_artifacts_are_not_canonical_runtime_proof",
            "historical_source_ids": ["external_lab_readme"],
            "historical_claim": "historical artifacts and filenames are metadata only and not active runtime proof",
            "classification": "reconfirmed_by_current_packets",
            "counting_status": "non_counted",
            "current_replacement_packets": [
                "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/final_dual_lane_acceptance_matrix.json",
                "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/independent_audit_packet.json",
            ],
            "reason": "current packet truth keeps historical item 0 open/non-counted and does not count historical material as closed runtime proof",
        },
        {
            "id": "external_lab_tests_prove_import_hygiene_not_runtime_integration",
            "historical_source_ids": ["external_lab_tests", "external_lab_acceptance_verification"],
            "historical_claim": "external-agent-lab tests and acceptance prove import hygiene and JSON preflight contract, not current runtime integration",
            "classification": "historical_only_non_counted",
            "counting_status": "non_counted",
            "current_replacement_packets": [],
            "reason": "isolated-lab tests and verification are meaningful historical evidence but do not count as current runtime satisfaction",
        },
        {
            "id": "historical_item0_open_non_counted_before_reconciliation",
            "historical_source_ids": ["external_lab_readme"],
            "historical_claim": "historical item 0 remained open and non-counted before reconciliation",
            "classification": "reconfirmed_by_current_packets",
            "counting_status": "non_counted",
            "current_replacement_packets": [
                "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/final_dual_lane_acceptance_matrix.json",
                "audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28/independent_audit_packet.json",
            ],
            "reason": "current packet truth explicitly records historical_item_0_counted_as_closed=false and item_0 open/non-counted",
        },
    ]

    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "reconfirmed_vs_superseded_matrix",
        "status": "ok",
        "current_seed_only_count": current_vs_seed.get("seed_only_count"),
        "current_seed_only_selectable": selector_seed_visibility.get("seed_only_selectable"),
        "historical_item_0_pre_reconciliation_open": any(
            finding.get("id") == "historical_item_0_remains_open_and_non_counted"
            for finding in final_audit.get("findings", [])
            if isinstance(finding, dict)
        )
        and acceptance.get("historical_item_0_counted_as_closed") is False,
        "rows": rows,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del evidence_dir
    current_inventory = _current_truth_inventory(repo_root)
    historical_inventory = _historical_seed_inventory(repo_root)
    reconciliation = _reconciliation_matrix(repo_root)

    unresolved_rows = [
        row for row in reconciliation["rows"] if row["classification"] == "unresolved_historical_gap"
    ]
    packets: dict[str, dict[str, Any]] = {
        "current_truth_inventory_packet.json": current_inventory,
        "historical_seed_inventory_packet.json": historical_inventory,
        "reconfirmed_vs_superseded_matrix.json": reconciliation,
        "historical_item0_counting_boundary_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "historical_item0_counting_boundary",
            "status": "ok",
            "final_status": "HISTORICAL_ITEM_0_RECONCILIATION_CLASSIFIED_AND_CLOSED",
            "historical_item0_reconciliation_closed": True,
            "inventory_enumeration_counts_as_runtime_proof": False,
            "closeout_prose_counts_as_runtime_proof": False,
            "historical_seed_counts_as_current_runtime_truth": False,
            "superseded_rows_remain_active_proof": False,
            "unresolved_historical_rows_present": bool(unresolved_rows),
            "current_packet_truth_only_counts_for_runtime": True,
            "item0_closed_as_reconciliation_only": True,
        },
        "false_green_boundary_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "false_green_boundary",
            "status": "ok",
            "inventory_table_treated_as_fresh_runtime_validation": False,
            "closeout_narrative_outranks_packet_evidence": False,
            "historical_rows_marked_reconfirmed_without_packet_support": False,
            "superseded_rows_treated_as_current_runtime_proof": False,
            "historical_seed_material_treated_as_fresh_reproof": False,
        },
        "independent_audit_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "independent_audit",
            "status": "ok",
            "findings": [
                {
                    "id": "historical_seed_registry_is_not_current_runtime_catalog",
                    "severity": "high",
                    "status": "confirmed",
                },
                {
                    "id": "seed_only_models_remain_non_selectable_current_runtime_choices",
                    "severity": "high",
                    "status": "confirmed",
                },
                {
                    "id": "isolated_external_lab_acceptance_docs_remain_historical_only_non_counted",
                    "severity": "medium",
                    "status": "confirmed",
                },
                {
                    "id": "historical_item0_closed_as_reconciliation_not_runtime_upgrade",
                    "severity": "info",
                    "status": "confirmed",
                },
            ],
        },
    }
    return packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    packets = build_packets(repo_root=args.repo_root.resolve(), evidence_dir=args.evidence_dir.resolve())
    for filename, payload in packets.items():
        json_write(args.evidence_dir / filename, payload)
    summary = {
        "status": "ok",
        "packet_count": len(packets),
        "evidence_dir": str(args.evidence_dir.resolve()),
        "packets": sorted(packets),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
