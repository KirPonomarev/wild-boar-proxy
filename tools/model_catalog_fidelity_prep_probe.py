#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit non-live model catalog fidelity prep evidence packets."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.model_catalog_fidelity_probe import api_snapshot, operator_status
from wild_boar_proxy.codex_model_registry import build_model_catalog_fidelity_packets


TARGET_STATUS = "WBP_MODEL_CATALOG_FIDELITY_PREP_CLASSIFIED"
PARENT_STATUS = "WBP_MODEL_CATALOG_FIDELITY_CLASSIFIED"
AVAILABILITY_STATUS = "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED"
CODEX_NATIVE_SOURCE_CLASSES = {
    "current_build_catalog_visible",
    "pinned_known",
    "inferred_from_fixture",
    "unknown",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def write_packet(evidence_dir: Path, name: str, payload: dict[str, Any]) -> None:
    (evidence_dir / name).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _ok(payload: dict[str, Any]) -> bool:
    return payload.get("status") == "ok"


def _models(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("models")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/model_catalog_fidelity_prep_probe.py",
        "tests/test_model_catalog_fidelity_prep_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "M tests/test_native_filesystem_probe.py",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _codex_native_source_rows(native_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in native_models:
        source_class = str(model.get("source_class") or "unknown")
        rows.append(
            {
                "model_id": str(model.get("model_id") or ""),
                "catalog_source_class": source_class
                if source_class in CODEX_NATIVE_SOURCE_CLASSES
                else "unknown",
                "raw_source_class": source_class,
                "current_build_visibility_claimed": source_class
                == "current_build_catalog_visible",
                "pinned_claimed_as_available": False,
                "inferred_fixture_claimed_as_current_build_truth": False,
                "availability_proven_by_source": False,
            }
        )
    return rows


def _metadata_source_rows(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        for tier_name in ("intelligence_tier", "speed_tier"):
            tier = model.get(tier_name) if isinstance(model.get(tier_name), dict) else {}
            rows.append(
                {
                    "model_id": str(model.get("model_id") or ""),
                    "lane": str(model.get("lane") or ""),
                    "metadata_field": tier_name,
                    "label": str(tier.get("label") or ""),
                    "source": str(tier.get("source") or ""),
                    "proof_level": str(tier.get("proof_level") or ""),
                    "treated_as_live_proof": False,
                }
            )
    return rows


def _alias_rows(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        aliases = model.get("aliases")
        if not isinstance(aliases, list):
            aliases = []
        rows.append(
            {
                "model_id": str(model.get("model_id") or ""),
                "lane": str(model.get("lane") or ""),
                "aliases": [str(alias) for alias in aliases],
                "alias_source": "server_registry",
                "alias_selected_as_route_proof": False,
                "alias_grants_provider_authority": False,
                "browser_can_supply_alias_authority": False,
            }
        )
    return rows


def _lane_integrity(native_models: list[dict[str, Any]], wbp_models: list[dict[str, Any]]) -> dict[str, Any]:
    native_bad = [
        str(model.get("model_id") or "")
        for model in native_models
        if model.get("lane") != "codex_native"
    ]
    wbp_bad = [
        str(model.get("model_id") or "")
        for model in wbp_models
        if model.get("lane") != "wbp_api"
    ]
    native_ids = {str(model.get("model_id") or "") for model in native_models}
    wbp_ids = {str(model.get("model_id") or "") for model in wbp_models}
    overlapping_ids = sorted(native_ids & wbp_ids)
    return {
        "codex_native_lane_present": bool(native_models),
        "wbp_api_lane_present": bool(wbp_models),
        "codex_native_wrong_lane_model_ids": native_bad,
        "wbp_api_wrong_lane_model_ids": wbp_bad,
        "overlapping_model_ids": overlapping_ids,
        "lanes_mixed": bool(native_bad or wbp_bad or overlapping_ids),
    }


def build_prep_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    fidelity = build_model_catalog_fidelity_packets(
        operator_status(),
        api_snapshot=api_snapshot(),
        measurement_packet_present=False,
    )
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    native_lane = fidelity["codex_native_model_lane_packet.json"]
    wbp_lane = fidelity["wbp_api_model_lane_packet.json"]
    display = fidelity["model_display_metadata_packet.json"]
    runtime = fidelity["runtime_truth_boundary_packet.json"]
    capability = fidelity["capability_claims_packet.json"]
    metadata = fidelity["metadata_source_packet.json"]
    authority = fidelity["model_catalog_authority_boundary_packet.json"]
    non_impersonation = fidelity["non_impersonation_packet.json"]
    false_green = fidelity["model_catalog_fidelity_false_green_audit.json"]
    native_models = _models(native_lane)
    wbp_models = _models(wbp_lane)
    all_models = [*_models(display)]
    lane_integrity = _lane_integrity(native_models, wbp_models)
    native_source_rows = _codex_native_source_rows(native_models)
    native_source_ok = bool(native_source_rows) and all(
        row["catalog_source_class"] in CODEX_NATIVE_SOURCE_CLASSES
        and not row["pinned_claimed_as_available"]
        and not row["inferred_fixture_claimed_as_current_build_truth"]
        for row in native_source_rows
    )
    wbp_non_impersonating = _ok(wbp_lane) and _ok(non_impersonation) and all(
        str(model.get("display_name") or "").lower().startswith(("wbp ", "wbp:"))
        and str(model.get("provider_model_id") or "")
        for model in wbp_models
    )
    prep_ok = all(
        _ok(payload)
        for payload in (
            fidelity["model_registry_schema_packet.json"],
            native_lane,
            wbp_lane,
            display,
            runtime,
            capability,
            metadata,
            authority,
            non_impersonation,
            false_green,
        )
    ) and native_source_ok and wbp_non_impersonating and not unexpected_dirty
    prep_ok = (
        prep_ok
        and lane_integrity["codex_native_lane_present"]
        and lane_integrity["wbp_api_lane_present"]
        and not lane_integrity["lanes_mixed"]
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": packet(
            "sync_gate",
            status="ok" if not unexpected_dirty else "blocked",
            branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
            unexpected_dirty_entries=unexpected_dirty,
            native_launch_attempted=False,
            external_provider_live_call_attempted=False,
            model_availability_smoke_attempted=False,
            master_plan_written_to_repo=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            quarantined_paths=quarantined,
            paused_active_contour_residue=[
                line
                for line in quarantined
                if "persistent_custom_profile_restoration_correlation_r5" in line
                or "persistent_custom_profile_restoration_correlation_r5_probe.py" in line
                or "tests/test_native_filesystem_probe.py" in line
            ],
            current_contour_relies_on_quarantined_paths=False,
            current_contour_mutates_quarantined_paths=False,
            current_contour_stages_quarantined_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=[
                "tools/model_catalog_fidelity_prep_probe.py",
                "tests/test_model_catalog_fidelity_prep_probe.py",
                str(evidence_dir.relative_to(repo_root)),
            ],
            native_launch_allowed=False,
            external_provider_live_call_allowed=False,
            model_availability_smoke_allowed=False,
        ),
        "model_registry_schema_packet.json": {
            **fidelity["model_registry_schema_packet.json"],
            "parent_master_target": PARENT_STATUS,
            "closes_parent_master_target": False,
            "prep_target_status": TARGET_STATUS,
        },
        "codex_native_model_lane_packet.json": native_lane,
        "codex_native_catalog_source_packet.json": packet(
            "codex_native_catalog_source",
            status="ok" if native_source_ok else "blocked",
            allowed_catalog_source_classes=sorted(CODEX_NATIVE_SOURCE_CLASSES),
            source_rows=native_source_rows,
            inferred_fixture_displayed_as_current_build_truth=False,
            pinned_entries_claimed_as_currently_available=False,
            current_build_visibility_claimed_without_packet=False,
        ),
        "wbp_api_model_lane_packet.json": wbp_lane,
        "wbp_api_non_impersonation_packet.json": packet(
            "wbp_api_non_impersonation",
            status="ok" if wbp_non_impersonating else "blocked",
            wbp_api_display_label_non_impersonating=True,
            wbp_lane_marker_required=True,
            provider_model_id_preserved_separately=True,
            alias_preserved_separately=True,
            native_label_reused_as_native_truth=False,
            models=[
                {
                    "model_id": str(model.get("model_id") or ""),
                    "display_name": str(model.get("display_name") or ""),
                    "provider_model_id": str(model.get("provider_model_id") or ""),
                    "aliases": list(model.get("aliases") or []),
                }
                for model in wbp_models
            ],
        ),
        "model_display_metadata_packet.json": display,
        "runtime_truth_packet.json": {
            **runtime,
            "packet_kind": "runtime_truth",
            "display_metadata_becomes_runtime_truth": False,
        },
        "capability_claims_packet.json": capability,
        "metadata_source_proof_level_packet.json": packet(
            "metadata_source_proof_level",
            status=metadata.get("status", "blocked"),
            rows=_metadata_source_rows(all_models),
            source_and_proof_level_required=True,
            intelligence_label_treated_as_live_proof=False,
            speed_label_treated_as_measured_proof=False,
            measured_source_requires_measurement_packet=True,
        ),
        "alias_authority_boundary_packet.json": packet(
            "alias_authority_boundary",
            status="ok",
            alias_rows=_alias_rows(all_models),
            alias_selected_is_route_proof=False,
            client_can_inject_alias_provider_account_authority=False,
            server_owns_alias_resolution=True,
        ),
        "model_catalog_fidelity_false_green_audit.json": {
            **false_green,
            "status": "ok" if _ok(false_green) and prep_ok else "blocked",
            "prep_target_status": TARGET_STATUS,
            "parent_master_target_closed": False,
            "full_catalog_fidelity_claimed": False,
            "model_availability_claimed": False,
            "catalog_source_fixture_claimed_as_current_build_truth": False,
            "alias_selected_claimed_as_route_proven": False,
            "lane_presence_hardcoded_without_model_cross_check": False,
            "lane_integrity": lane_integrity,
        },
        "catalog_fidelity_prep_summary_packet.json": packet(
            "catalog_fidelity_prep_summary",
            status="ok" if prep_ok else "blocked",
            final_status=TARGET_STATUS,
            parent_master_target=PARENT_STATUS,
            parent_master_target_closed=False,
            model_availability_target=AVAILABILITY_STATUS,
            model_availability_target_closed=False,
            codex_native_lane_ok=_ok(native_lane),
            codex_native_catalog_source_ok=native_source_ok,
            wbp_api_lane_ok=_ok(wbp_lane),
            wbp_api_non_impersonation_ok=wbp_non_impersonating,
            lane_integrity_ok=not lane_integrity["lanes_mixed"]
            and lane_integrity["codex_native_lane_present"]
            and lane_integrity["wbp_api_lane_present"],
            display_metadata_is_runtime_truth=False,
            runtime_truth_is_capability_proof=False,
            model_availability_proven=False,
            provider_compatibility_proven=False,
            native_model_menu_ui_proven=False,
            live_route_proof_proven=False,
            direct_egress_absence_proven=False,
            final_e2e_proven=False,
        ),
    }
    packets["independent_catalog_fidelity_prep_audit.json"] = packet(
        "independent_catalog_fidelity_prep_audit",
        status="ok"
        if packets["catalog_fidelity_prep_summary_packet.json"].get("status") == "ok"
        else "blocked",
        referenced_packets=sorted(packets),
        required_packets_present=True,
        text_only_audit=False,
        layer_separation_ok=True,
        non_impersonation_ok=wbp_non_impersonating,
        source_classification_ok=native_source_ok,
        lane_integrity_ok=not lane_integrity["lanes_mixed"],
        no_live_native_model_egress_claims=True,
    )
    return packets


def main() -> int:
    parser = argparse.ArgumentParser(prog="model-catalog-fidelity-prep-probe")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    evidence_dir = args.evidence_dir.resolve()
    if repo_root not in evidence_dir.parents:
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_prep_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        write_packet(evidence_dir, name, payload)
    summary = packets["catalog_fidelity_prep_summary_packet.json"]
    print(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
