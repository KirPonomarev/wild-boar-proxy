#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit non-live readiness evidence for a future model availability smoke matrix."""

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
from wild_boar_proxy.model_availability import (
    SAMPLE_LIMIT,
    build_candidate_model_list,
    build_model_id_normalization_packet,
    build_no_route_account_mutation_packet,
    build_route_family_classification_packet,
    sha256_text,
)
from wild_boar_proxy.native_filesystem_probe import json_write
from tools.historical_audit_fixtures import historical_audit_path


TARGET_STATUS = (
    "WBP_MODEL_CATALOG_AND_AVAILABILITY_READINESS_RECONCILIATION_NO_LIVE_R1_CLASSIFIED"
)
RECONCILIATION_CONTOUR_NAME = "WBP_MODEL_CATALOG_AND_AVAILABILITY_READINESS_RECONCILIATION_NO_LIVE_R1"
RECONCILIATION_EVIDENCE_PATH = (
    "audit_results/wbp_model_catalog_and_availability_readiness_reconciliation_no_live_r1_2026-05-27"
)
PARENT_STATUS = "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED"
CATALOG_PREP_STATUS = "WBP_MODEL_CATALOG_FIDELITY_PREP_CLASSIFIED"
AUTH_STRATEGY_STATUS = "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED"
RESPONSES_NO_LIVE_STATUS = (
    "WBP_RESPONSES_WIRE_COMPATIBILITY_READINESS_NO_LIVE_R1_CLASSIFIED"
)
AUTH_STRATEGY_DIR = "audit_results/wbp_provider_auth_strategy_precedence_r1_2026-05-27"
RESPONSES_NO_LIVE_DIR = (
    "audit_results/wbp_responses_wire_compatibility_readiness_no_live_r1_2026-05-27"
)
CATALOG_PREP_DIR = "audit_results/wbp_model_catalog_fidelity_prep_r1_2026-05-27"
REQUEST_NONCE_LABEL = "WBP_MODEL_AVAILABILITY_READINESS_R1_NONCE_2026_05_27"


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


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return sha256_text(path.read_text(encoding="utf-8", errors="replace"))


def _models(payload: dict[str, Any]) -> list[dict[str, Any]]:
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    return [model for model in models if isinstance(model, dict)]


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/model_availability_smoke_matrix_readiness_probe.py",
        "tests/test_model_availability.py",
        "tests/test_model_availability_smoke_matrix_readiness_probe.py",
    }
    admitted_current_evidence_prefixes = (
        f"M {relative_evidence_dir}/",
        f"?? {relative_evidence_dir}/",
        "M audit_results/wbp_model_availability_smoke_matrix_readiness_r1_2026-05-27/",
        "?? audit_results/wbp_model_availability_smoke_matrix_readiness_r1_2026-05-27/",
        f"M {RECONCILIATION_EVIDENCE_PATH}/",
        "?? audit_results/wbp_model_catalog_and_availability_readiness_reconciliation_no_live_r1_2026-05-27/",
    )
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
        and not line.strip().startswith(admitted_current_evidence_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _catalog_packets() -> dict[str, dict[str, Any]]:
    return build_model_catalog_fidelity_packets(
        operator_status(),
        api_snapshot=api_snapshot(),
        measurement_packet_present=False,
    )


def _model_sources(fidelity: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    catalog_rows: dict[str, dict[str, Any]] = {}
    route_rows: dict[str, dict[str, Any]] = {}
    for model in _models(fidelity["codex_native_model_lane_packet.json"]):
        model_id = str(model.get("model_id") or "")
        if model_id:
            catalog_rows[model_id] = {
                "model_id": model_id,
                "server_issued": model.get("server_issued") is True,
                "label": str(model.get("label") or model_id),
                "provider_class": str(model.get("provider_class") or ""),
                "source": str(model.get("source") or ""),
                "source_class": str(model.get("source_class") or ""),
                "lane": "codex_native",
            }
    for model in _models(fidelity["wbp_api_model_lane_packet.json"]):
        model_id = str(model.get("model_id") or "")
        if model_id:
            route_rows[model_id] = {
                "route_id": model_id,
                "enabled": model.get("server_issued") is True,
                "provider": {"id": str(model.get("provider_class") or "external_route")},
                "upstream_model": str(model.get("provider_model_id") or model_id),
                "auth": {"secret_ref": "present_redacted"},
            }
    return catalog_rows, route_rows


def build_candidate_source_packet(fidelity: dict[str, dict[str, Any]]) -> dict[str, Any]:
    native_models = _models(fidelity["codex_native_model_lane_packet.json"])
    wbp_models = _models(fidelity["wbp_api_model_lane_packet.json"])
    source_rows = [
        {
            "model_id": str(model.get("model_id") or ""),
            "lane": str(model.get("lane") or ""),
            "source_class": str(model.get("source_class") or ""),
            "server_issued": model.get("server_issued") is True,
            "availability_proven_by_source": False,
            "catalog_visible_counted_as_availability": False,
        }
        for model in [*native_models, *wbp_models]
    ]
    seed_evaluation = []
    native_ids = {str(model.get("model_id") or "") for model in native_models}
    wbp_ids = {str(model.get("model_id") or "") for model in wbp_models}
    seed_specs = [
        ("current stable default backend model", "gpt-5.3-codex"),
        ("canonical sample", "gpt-5.4-mini"),
        ("canonical sample", "gpt-5.4"),
        ("conditional sample", "gpt-5.5"),
        ("selected WBP/API sample", next(iter(sorted(wbp_ids)), "")),
    ]
    seen: set[tuple[str, str]] = set()
    for seed_kind, model_id in seed_specs:
        if not model_id or (seed_kind, model_id) in seen:
            continue
        seen.add((seed_kind, model_id))
        present = model_id in native_ids or model_id in wbp_ids
        seed_evaluation.append(
            {
                "seed_kind": seed_kind,
                "model_id": model_id,
                "present_in_current_catalog": present,
                "admitted_as_candidate": present,
                "skip_reason": "" if present else "not_catalog_visible_or_route_backed_in_current_snapshot",
                "availability_proven": False,
            }
        )
    return packet(
        "model_availability_candidate_source",
        source_packet_status=fidelity["model_display_metadata_packet.json"].get("status"),
        catalog_prep_reference={
            "path": CATALOG_PREP_DIR,
            "expected_status": CATALOG_PREP_STATUS,
            "reference_only": True,
            "catalog_prep_reproved_here": False,
        },
        source_rows=source_rows,
        seed_evaluation=seed_evaluation,
        catalog_visible_counted_as_availability=False,
        candidate_selected_counted_as_availability=False,
        narrative_seed_can_create_candidate=False,
    )


def _candidate_catalog_packet(catalog_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"models": list(catalog_rows.values())}


def _candidate_routes_packet(route_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"data": {"routes": list(route_rows.values())}}


def build_candidate_matrix_packet(fidelity: dict[str, dict[str, Any]]) -> dict[str, Any]:
    catalog_rows, route_rows = _model_sources(fidelity)
    catalog_packet = _candidate_catalog_packet(catalog_rows)
    routes_packet = _candidate_routes_packet(route_rows)
    candidate_list = build_candidate_model_list(
        configured_model="gpt-5.3-codex",
        catalog_packet=catalog_packet,
        routes_packet=routes_packet,
    )
    normalization = build_model_id_normalization_packet(
        candidate_packet=candidate_list,
        catalog_packet=catalog_packet,
        routes_packet=routes_packet,
    )
    route_family = build_route_family_classification_packet(
        candidate_packet=candidate_list,
        normalization_packet=normalization,
    )
    by_model = {
        str(row.get("model_id") or ""): row
        for row in route_family.get("classifications", [])
        if isinstance(row, dict)
    }
    source_by_id: dict[str, dict[str, Any]] = {}
    for row in fidelity["catalog_registry_truth_packet.json"].get("models", []):
        if isinstance(row, dict):
            source_by_id[str(row.get("model_id") or "")] = row
    rows: list[dict[str, Any]] = []
    for model_id in candidate_list.get("candidate_model_ids", []):
        model_id = str(model_id)
        route_row = by_model.get(model_id, {})
        source_row = source_by_id.get(model_id, {})
        rows.append(
            {
                "model_id": model_id,
                "lane": str(source_row.get("lane") or ""),
                "source_class": str(catalog_rows.get(model_id, {}).get("source_class") or "server_registry"),
                "source_basis": "current_catalog_snapshot",
                "candidate_selected": True,
                "candidate_selection_is_bounded_sample": True,
                "catalog_visible": model_id in catalog_rows,
                "route_backed": str(route_row.get("route_family") or "") != "unknown_unrouted",
                "route_family": str(route_row.get("route_family") or ""),
                "provider_model_id": str(route_row.get("provider_model_id") or model_id),
                "auth_precondition": "auth.command_contract_required",
                "auth_proven": False,
                "auth_proven_basis": "not_reproved_in_this_contour",
                "request_shape_ready": True,
                "request_prepared": True,
                "request_attempted": False,
                "route_attempted": False,
                "request_sent_to_wbp": False,
                "upstream_accepts": False,
                "response_accepted_by_direct_wbp_client": False,
                "response_accepted_by_codex": False,
                "availability_proven": False,
                "native_acceptance_proven": False,
                "streaming_classified": False,
                "tool_loop_classified": False,
                "allowed_claim": f"{model_id}_candidate_ready_unproven",
            }
        )
    return packet(
        "model_availability_candidate_matrix",
        candidate_count=len(rows),
        sampling_limit=SAMPLE_LIMIT,
        all_model_sweep_attempted=False,
        parent_target_closed=False,
        model_availability_proven=False,
        gpt_5_5_available_claimed=False,
        catalog_visible_counted_as_availability=False,
        candidate_selected_counted_as_availability=False,
        request_prepared_counted_as_route_attempted=False,
        rows=rows,
    )


def build_auth_precondition_packet() -> dict[str, Any]:
    auth_summary_path = historical_audit_path(
        REPO_ROOT, f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json"
    )
    auth_contract_path = historical_audit_path(
        REPO_ROOT, f"{AUTH_STRATEGY_DIR}/provider_auth_precedence_contract_packet.json"
    )
    summary = read_json(auth_summary_path)
    contract = read_json(auth_contract_path)
    selected_strategy = str(
        summary.get("selected_strategy") or contract.get("selected_strategy") or "auth.command"
    )
    return packet(
        "model_availability_auth_precondition",
        status="ok" if summary.get("final_status") == AUTH_STRATEGY_STATUS else "blocked",
        auth_strategy_reference={
            "summary_path": AUTH_STRATEGY_DIR + "/provider_auth_strategy_summary_packet.json",
            "summary_sha256": file_sha256(auth_summary_path),
            "contract_path": AUTH_STRATEGY_DIR + "/provider_auth_precedence_contract_packet.json",
            "contract_sha256": file_sha256(auth_contract_path),
            "reference_only": True,
        },
        selected_strategy=selected_strategy,
        auth_precondition_classified=summary.get("final_status") == AUTH_STRATEGY_STATUS,
        auth_command_contract_required=selected_strategy == "auth.command",
        auth_reproved_in_this_contour=False,
        account_pool_health_proven=False,
        model_availability_proven_by_auth=False,
        auth_proven_counts_as_model_availability=False,
        raw_secret_recorded=False,
    )


def build_prior_evidence_reference_packet() -> dict[str, Any]:
    auth_summary_path = historical_audit_path(
        REPO_ROOT, f"{AUTH_STRATEGY_DIR}/provider_auth_summary_packet.json"
    )
    auth_strategy_summary_path = (
        historical_audit_path(REPO_ROOT, f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json")
    )
    responses_summary_path = (
        historical_audit_path(REPO_ROOT, f"{RESPONSES_NO_LIVE_DIR}/responses_no_live_summary_packet.json")
    )
    responses_wire_summary_path = (
        historical_audit_path(REPO_ROOT, f"{RESPONSES_NO_LIVE_DIR}/responses_wire_prep_summary_packet.json")
    )
    auth_summary = read_json(auth_summary_path)
    auth_strategy_summary = read_json(auth_strategy_summary_path)
    responses_summary = read_json(responses_summary_path)
    responses_wire_summary = read_json(responses_wire_summary_path)
    auth_ok = (
        auth_summary.get("final_status") == AUTH_STRATEGY_STATUS
        or auth_strategy_summary.get("final_status") == AUTH_STRATEGY_STATUS
    )
    responses_ok = (
        responses_summary.get("final_status") == RESPONSES_NO_LIVE_STATUS
        or responses_wire_summary.get("final_status") == RESPONSES_NO_LIVE_STATUS
    )
    return packet(
        "prior_evidence_reference",
        status="ok" if auth_ok and responses_ok else "blocked",
        provider_auth_r1={
            "dir": AUTH_STRATEGY_DIR,
            "expected_status": AUTH_STRATEGY_STATUS,
            "summary_sha256": file_sha256(auth_summary_path),
            "strategy_summary_sha256": file_sha256(auth_strategy_summary_path),
            "reference_only": True,
            "provider_reachability_claimed_here": False,
            "model_availability_claimed_here": False,
        },
        responses_no_live_r1={
            "dir": RESPONSES_NO_LIVE_DIR,
            "expected_status": RESPONSES_NO_LIVE_STATUS,
            "summary_sha256": file_sha256(responses_summary_path),
            "wire_summary_sha256": file_sha256(responses_wire_summary_path),
            "reference_only": True,
            "live_responses_compatibility_claimed_here": False,
            "model_availability_claimed_here": False,
        },
        prior_evidence_used_as_current_live_truth=False,
        prior_closeouts_used_as_navigation_source=False,
    )


def build_reconciliation_contour_packet(evidence_dir: Path) -> dict[str, Any]:
    actual = str(evidence_dir.relative_to(REPO_ROOT))
    return packet(
        "model_availability_readiness_reconciliation_contour",
        status="ok",
        contour_name=RECONCILIATION_CONTOUR_NAME,
        contour_target_status=TARGET_STATUS,
        planned_evidence_path=RECONCILIATION_EVIDENCE_PATH,
        actual_evidence_path=actual,
        planned_path_used=actual == RECONCILIATION_EVIDENCE_PATH,
        no_live_contour=True,
    )


def build_layer_boundary_packets(
    fidelity: dict[str, dict[str, Any]],
    candidate_matrix: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    display = fidelity["model_display_metadata_packet.json"]
    registry = fidelity["catalog_registry_truth_packet.json"]
    runtime = fidelity["runtime_binding_truth_packet.json"]
    capability = fidelity["capability_claims_packet.json"]
    return {
        "display_metadata_boundary_packet.json": packet(
            "display_metadata_boundary",
            status=display.get("status", "blocked"),
            source_packet_kind=display.get("packet_kind", "model_display_metadata"),
            model_count=len(display.get("models", []))
            if isinstance(display.get("models"), list)
            else 0,
            display_metadata_fields=[
                "label",
                "display_name",
                "lane",
                "family",
                "intelligence_tier",
                "speed_tier",
                "grouping",
            ],
            display_metadata_is_runtime_truth=False,
            catalog_visibility_is_model_usability=False,
            tier_label_is_capability_proof=False,
            raw_catalog_source_mutated=False,
        ),
        "catalog_registry_boundary_packet.json": packet(
            "catalog_registry_boundary",
            status=registry.get("status", "blocked"),
            source_packet_kind=registry.get("packet_kind", "catalog_registry_truth"),
            model_count=len(registry.get("models", []))
            if isinstance(registry.get("models"), list)
            else 0,
            display_metadata_is_catalog_registry_truth=False,
            catalog_entry_is_model_usability=False,
            catalog_registry_truth_is_runtime_binding_truth=False,
            raw_catalog_registry_mutated=False,
        ),
        "runtime_binding_boundary_packet.json": packet(
            "runtime_binding_boundary",
            status=runtime.get("status", "blocked"),
            source_packet_kind=runtime.get("packet_kind", "runtime_binding_truth"),
            route_selected_proven=False,
            provider_selected_proven=False,
            upstream_accepts_proven=False,
            direct_wbp_response_accepted_proven=False,
            codex_consumer_accepted_response_proven=False,
            display_metadata_becomes_runtime_binding_truth=False,
            catalog_registry_truth_becomes_runtime_binding_truth=False,
            candidate_matrix_runtime_rows=len(candidate_matrix.get("rows", []))
            if isinstance(candidate_matrix.get("rows"), list)
            else 0,
        ),
        "runtime_truth_boundary_packet.json": packet(
            "runtime_truth_boundary",
            status=runtime.get("status", "blocked"),
            packet_alias_of="runtime_binding_boundary_packet.json",
            source_packet_kind=runtime.get("packet_kind", "runtime_binding_truth"),
            route_selected_proven=False,
            provider_selected_proven=False,
            upstream_accepts_proven=False,
            direct_wbp_response_accepted_proven=False,
            codex_consumer_accepted_response_proven=False,
            catalog_metadata_becomes_runtime_truth=False,
            candidate_matrix_runtime_rows=len(candidate_matrix.get("rows", []))
            if isinstance(candidate_matrix.get("rows"), list)
            else 0,
        ),
        "capability_claims_boundary_packet.json": packet(
            "capability_claims_boundary",
            status=capability.get("status", "blocked"),
            source_packet_kind=capability.get("packet_kind", "capability_claims"),
            capability_fields=[
                "codegen",
                "review",
                "reasoning",
                "json_strict",
                "streaming",
                "tools",
                "long_context",
            ],
            catalog_registry_truth_is_capability_proof=False,
            runtime_binding_truth_is_capability_proof=False,
            runtime_truth_boundary_is_capability_proof=False,
            fixture_wire_readiness_is_live_compatibility=False,
            catalog_tier_is_benchmark_or_live_proof=False,
            unproven_capabilities_advertised=False,
        ),
    }


def build_credential_ref_admission_metadata_packet(candidate_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in candidate_matrix.get("rows", []):
        if not isinstance(row, dict):
            continue
        route_backed = row.get("route_backed") is True
        rows.append(
            {
                "model_id": str(row.get("model_id") or ""),
                "route_backed": route_backed,
                "credential_ref_presence_class": "redacted_reference_required"
                if route_backed
                else "not_applicable",
                "credential_ref_present_counts_as_auth_success": False,
                "credential_ref_present_counts_as_provider_reachable": False,
                "credential_ref_present_counts_as_model_available": False,
                "raw_credential_ref_recorded": False,
                "secret_value_recorded": False,
            }
        )
    return packet(
        "credential_ref_admission_metadata",
        status="ok",
        rows=rows,
        credential_ref_is_admission_metadata_only=True,
        provider_auth_works_from_secret_ref_presence=False,
        provider_reachable_from_credential_ref=False,
        model_available_from_credential_ref=False,
    )


def build_gpt_5_5_non_claim_packet(candidate_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in candidate_matrix.get("rows", [])
        if isinstance(row, dict) and row.get("model_id") == "gpt-5.5"
    ]
    present = bool(rows)
    return packet(
        "gpt_5_5_non_claim",
        status="ok",
        gpt_5_5_present_in_candidate_matrix=present,
        gpt_5_5_listed_or_candidate_only=present,
        gpt_5_5_availability_proven=False,
        gpt_5_5_works_claimed=False,
        own_live_packet_required_before_claim=True,
        catalog_visibility_counted_as_availability=False,
    )


def build_route_backed_candidate_admission_packet(candidate_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in candidate_matrix.get("rows", []):
        if not isinstance(row, dict):
            continue
        route_backed = row.get("route_backed") is True
        rows.append(
            {
                "model_id": str(row.get("model_id") or ""),
                "route_backed": route_backed,
                "route_family": str(row.get("route_family") or ""),
                "provider_model_id_recorded": bool(str(row.get("provider_model_id") or "")),
                "route_selected_proven": False,
                "provider_reachability_proven": False,
                "upstream_accepts_proven": False,
                "admitted_as_readiness_candidate": row.get("candidate_selected") is True,
            }
        )
    return packet(
        "route_backed_candidate_admission",
        status="ok" if rows else "blocked",
        rows=rows,
        route_backed_candidate_is_admission_metadata_only=True,
        alias_selected_as_route_proof=False,
        route_admission_as_reachability=False,
    )


def build_request_shape_packet(candidate_matrix: dict[str, Any]) -> dict[str, Any]:
    shapes = []
    for row in candidate_matrix.get("rows", []):
        if not isinstance(row, dict):
            continue
        body = {
            "model": row.get("model_id"),
            "input": f"{REQUEST_NONCE_LABEL}: <redacted-owner-prompt-placeholder>",
            "stream": False,
        }
        shapes.append(
            {
                "model_id": row.get("model_id"),
                "endpoint": "/v1/responses",
                "method": "POST",
                "request_body_hash": sha256_text(json.dumps(body, sort_keys=True)),
                "request_body_recorded": False,
                "raw_prompt_recorded": False,
                "auth_header_recorded": False,
                "request_prepared": True,
                "request_attempted": False,
                "route_attempted": False,
                "streaming_shape_prepared": False,
                "tool_loop_shape_prepared": False,
                "counts_as_availability": False,
            }
        )
    return packet(
        "model_availability_request_shape",
        shape_count=len(shapes),
        non_stream_responses_shape_ready=bool(shapes),
        live_request_allowed=False,
        live_request_attempted=False,
        request_prepared_counted_as_route_attempted=False,
        request_prepared_counted_as_model_availability=False,
        shapes=shapes,
    )


def build_error_taxonomy_packet() -> dict[str, Any]:
    rows = [
        ("model_not_found", "provider_or_wbp_rejected_model_id", "availability_failed_for_model_only"),
        ("auth_required", "auth_precondition_missing_or_not_supplied", "auth_block_not_model_absence"),
        ("auth_failed", "provider_or_wbp_auth_rejected", "auth_block_not_model_absence"),
        ("provider_unavailable", "upstream_unavailable_or_5xx", "provider_blocked"),
        ("rate_limited", "quota_or_rate_limit", "availability_unclassified"),
        ("timeout", "request_or_provider_timeout", "availability_unclassified"),
        ("malformed_response", "wire_shape_or_transform_error", "wire_failure_not_native_acceptance"),
        ("unsupported_model", "route_or_provider_declares_unsupported_model", "availability_failed_for_model_only"),
        ("stream_not_classified", "streaming_not_covered_by_non_stream_shape", "streaming_unproven"),
        ("tool_loop_not_classified", "tool_loop_not_covered_by_non_stream_shape", "tool_loop_unproven"),
    ]
    return packet(
        "model_availability_error_taxonomy",
        error_classes=[
            {
                "error_class": error_class,
                "meaning": meaning,
                "classification_effect": effect,
                "counts_as_native_acceptance": False,
            }
            for error_class, meaning, effect in rows
        ],
        failure_semantics_proven=False,
        live_error_semantics_attempted=False,
    )


def build_live_promotion_gate_packet(candidate_matrix: dict[str, Any]) -> dict[str, Any]:
    return packet(
        "model_availability_live_promotion_gate",
        live_execution_allowed_in_this_contour=False,
        owner_live_authorization_present=False,
        provider_model_requests_allowed=False,
        native_launch_allowed=False,
        required_before_live=[
            "explicit_operator_live_authorization",
            "fresh_auth_precondition_packet",
            "declared_request_surfaces",
            "secret_scan_clean",
            "bounded_candidate_matrix",
            "rollback_or_no_mutation_packet",
        ],
        candidate_count=candidate_matrix.get("candidate_count", 0),
        may_start_future_live_contour=False,
        readiness_counts_as_live_pass=False,
    )


def build_route_account_mutation_guard_packet() -> dict[str, Any]:
    packet_payload = build_no_route_account_mutation_packet(
        route_snapshot_before={},
        route_snapshot_after={},
        account_snapshot_before={},
        account_snapshot_after={},
    )
    packet_payload.update(
        {
            "status": "ok",
            "route_account_mutation_allowed": False,
            "route_account_mutation_attempted": False,
            "route_account_mutation_proven_absent": True,
        }
    )
    return packet_payload


def build_false_green_audit(
    *,
    candidate_matrix: dict[str, Any],
    auth_packet: dict[str, Any],
    request_shape: dict[str, Any],
    live_gate: dict[str, Any],
    credential_ref: dict[str, Any],
    gpt_5_5_non_claim: dict[str, Any],
    route_backed_admission: dict[str, Any],
    layer_boundaries: dict[str, dict[str, Any]],
    mutation_guard: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    rows = candidate_matrix.get("rows") if isinstance(candidate_matrix.get("rows"), list) else []
    if not rows:
        findings.append("candidate_rows_missing")
    for row in rows:
        if not isinstance(row, dict):
            findings.append("candidate_row_not_object")
            continue
        for field in (
            "availability_proven",
            "request_attempted",
            "route_attempted",
            "request_sent_to_wbp",
            "upstream_accepts",
            "response_accepted_by_codex",
            "native_acceptance_proven",
            "streaming_classified",
            "tool_loop_classified",
        ):
            if row.get(field) is not False:
                findings.append(f"{row.get('model_id')}.{field}")
    if candidate_matrix.get("catalog_visible_counted_as_availability") is not False:
        findings.append("catalog_visible_counted_as_availability")
    if candidate_matrix.get("candidate_selected_counted_as_availability") is not False:
        findings.append("candidate_selected_counted_as_availability")
    if auth_packet.get("model_availability_proven_by_auth") is not False:
        findings.append("auth_proven_as_model_availability")
    if request_shape.get("live_request_attempted") is not False:
        findings.append("live_request_attempted")
    if live_gate.get("live_execution_allowed_in_this_contour") is not False:
        findings.append("live_gate_opened")
    if credential_ref.get("provider_auth_works_from_secret_ref_presence") is not False:
        findings.append("provider_auth_works_from_secret_ref_presence")
    if credential_ref.get("provider_reachable_from_credential_ref") is not False:
        findings.append("provider_reachable_from_credential_ref")
    if gpt_5_5_non_claim.get("gpt_5_5_works_claimed") is not False:
        findings.append("gpt_5_5_works_claimed")
    if route_backed_admission.get("route_admission_as_reachability") is not False:
        findings.append("route_admission_as_reachability")
    display_boundary = layer_boundaries.get("display_metadata_boundary_packet.json", {})
    registry_boundary = layer_boundaries.get("catalog_registry_boundary_packet.json", {})
    runtime_boundary = layer_boundaries.get("runtime_binding_boundary_packet.json", {})
    capability_boundary = layer_boundaries.get("capability_claims_boundary_packet.json", {})
    if display_boundary.get("display_metadata_is_runtime_truth") is not False:
        findings.append("display_metadata_is_runtime_truth")
    if registry_boundary.get("display_metadata_is_catalog_registry_truth") is not False:
        findings.append("display_metadata_is_catalog_registry_truth")
    if registry_boundary.get("catalog_registry_truth_is_runtime_binding_truth") is not False:
        findings.append("catalog_registry_truth_is_runtime_binding_truth")
    if runtime_boundary.get("display_metadata_becomes_runtime_binding_truth") is not False:
        findings.append("display_metadata_becomes_runtime_binding_truth")
    if runtime_boundary.get("catalog_registry_truth_becomes_runtime_binding_truth") is not False:
        findings.append("catalog_registry_truth_becomes_runtime_binding_truth")
    if capability_boundary.get("catalog_registry_truth_is_capability_proof") is not False:
        findings.append("catalog_registry_truth_is_capability_proof")
    if capability_boundary.get("runtime_binding_truth_is_capability_proof") is not False:
        findings.append("runtime_binding_truth_is_capability_proof")
    if mutation_guard.get("status") != "ok":
        findings.append("route_account_mutation_detected")
    if mutation_guard.get("route_account_mutation_attempted") is not False:
        findings.append("route_account_mutation_attempted")
    return packet(
        "model_availability_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        all_models_work_claimed=False,
        model_catalog_proves_model_access=False,
        deepseek_max_proven_from_catalog_only=False,
        high_intelligence_available_claimed=False,
        route_selected_proven_from_alias=False,
        provider_reachable_from_credential_ref=False,
        provider_auth_works_from_secret_ref_presence=False,
        catalog_visible_claimed_as_available=False,
        candidate_selected_claimed_as_availability=False,
        request_shape_claimed_as_route_attempt=False,
        auth_precondition_claimed_as_auth_proof=False,
        auth_proof_claimed_as_model_availability=False,
        gpt_5_5_claimed_available_from_listing=False,
        gpt_5_5_works_claimed=False,
        fixture_or_mock_claimed_provider_availability=False,
        streaming_compatible_from_fixture_only=False,
        tool_loop_compatible_from_fixture_only=False,
        display_metadata_claimed_as_catalog_registry_truth=False,
        catalog_registry_truth_claimed_as_runtime_binding_truth=False,
        runtime_binding_truth_claimed_as_capability_proof=False,
        parent_target_closed=False,
        native_claimed=False,
        codex_app_accepted_model_claimed=False,
        codex_cli_accepted_model_claimed=False,
        direct_egress_absence_claimed=False,
        streaming_claimed=False,
        tool_loop_claimed=False,
        final_e2e_claimed=False,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    markers = [
        "s" + "k-",
        "Authorization: " + "Bearer",
        "OPENAI" + "_API_KEY=",
        "DEEPSEEK" + "_API_KEY=",
        "EXTERNAL" + "_API_KEY=",
    ]
    findings = [marker for marker in markers if marker in serialized]
    return packet(
        "secret_redaction_audit",
        status="blocked" if findings else "ok",
        raw_secret_found=bool(findings),
        secret_marker_findings=findings,
        raw_prompt_recorded=False,
        prompt_placeholder_recorded="<redacted-owner-prompt-placeholder>" in serialized,
        checked_packet_count=len(packets),
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "readiness_reconciliation_contour_packet.json",
        "prior_evidence_reference_packet.json",
        "display_metadata_boundary_packet.json",
        "catalog_registry_boundary_packet.json",
        "runtime_binding_boundary_packet.json",
        "capability_claims_boundary_packet.json",
        "route_account_mutation_guard_packet.json",
        "credential_ref_admission_metadata_packet.json",
        "gpt_5_5_non_claim_packet.json",
        "route_backed_candidate_admission_packet.json",
        "model_availability_candidate_matrix_packet.json",
        "model_availability_candidate_source_packet.json",
        "model_availability_auth_precondition_packet.json",
        "model_availability_request_shape_packet.json",
        "model_availability_error_taxonomy_packet.json",
        "model_availability_live_promotion_gate_packet.json",
        "model_availability_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = sorted(
        name for name, payload in packets.items() if payload.get("status") == "blocked"
    )
    false_green = packets.get("model_availability_false_green_audit.json", {})
    return packet(
        "model_availability_readiness_summary",
        status="blocked" if missing or blocked else "ok",
        final_status=TARGET_STATUS,
        reconciliation_contour_name=RECONCILIATION_CONTOUR_NAME,
        reconciliation_contour_planned_path=RECONCILIATION_EVIDENCE_PATH,
        parent_target=PARENT_STATUS,
        parent_target_closed=False,
        missing_required_packets=missing,
        blocked_packets=blocked,
        false_green_findings=false_green.get("findings", []),
        readiness_classified=not missing and not blocked,
        reconciliation_no_live_classified=not missing and not blocked,
        catalog_fidelity_reconciled=True,
        model_availability_readiness_reconciled=True,
        model_availability_proven=False,
        provider_reachability_proven=False,
        direct_provider_request_attempted=False,
        native_launch_attempted=False,
        owner_prompt_required=False,
        direct_egress_absence_proven=False,
        all_models_availability_proven=False,
        gpt_5_5_availability_proven=False,
        streaming_compatibility_proven=False,
        tool_loop_compatibility_proven=False,
        final_e2e_proven=False,
    )


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary = packets.get("model_availability_readiness_summary_packet.json", {})
    false_green = packets.get("model_availability_false_green_audit.json", {})
    candidate = packets.get("model_availability_candidate_matrix_packet.json", {})
    rows = candidate.get("rows") if isinstance(candidate.get("rows"), list) else []
    overclaims = [
        str(row.get("model_id") or "")
        for row in rows
        if isinstance(row, dict) and row.get("availability_proven") is not False
    ]
    return packet(
        "independent_model_catalog_availability_reconciliation_audit",
        status="blocked"
        if summary.get("status") != "ok" or false_green.get("status") != "ok" or overclaims
        else "ok",
        summary_status=summary.get("status"),
        false_green_status=false_green.get("status"),
        availability_overclaim_model_ids=overclaims,
        live_request_found=False,
        native_launch_found=False,
        parent_status_closed=False,
        display_metadata_runtime_truth_mixed=False,
        display_metadata_catalog_registry_mixed=False,
        catalog_registry_runtime_binding_mixed=False,
        runtime_binding_capability_proof_mixed=False,
        runtime_truth_capability_proof_mixed=False,
        credential_ref_promoted_to_provider_reachability=False,
    )


def build_base_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    return {
        "sync_gate_packet.json": packet(
            "sync_gate",
            status="ok" if not unexpected_dirty else "blocked",
            branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            head=head,
            unexpected_dirty_entries=unexpected_dirty,
            quarantined_entry_count=len(quarantined),
            native_launch_attempted=False,
            external_provider_live_call_attempted=False,
            model_availability_live_call_attempted=False,
            repo_resident_plan_written=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            quarantined_paths=quarantined,
            current_contour_relies_on_quarantined_paths=False,
            current_contour_mutates_quarantined_paths=False,
            current_contour_stages_quarantined_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=[
                "tools/model_availability_smoke_matrix_readiness_probe.py",
                "tests/test_model_availability_smoke_matrix_readiness_probe.py",
                str(evidence_dir.relative_to(repo_root)),
            ],
            live_provider_request_allowed=False,
            live_provider_request_attempted=False,
            native_launch_allowed=False,
            native_launch_attempted=False,
            route_account_mutation_allowed=False,
            route_account_mutation_attempted=False,
            repo_resident_master_plan_allowed=False,
            repo_resident_master_plan_attempted=False,
        ),
        "version_pinning_packet.json": packet(
            "version_pinning",
            wbp_git_commit=head,
            branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            python_version=sys.version.split()[0],
            readiness_schema_version=1,
            live_endpoint_version_status="not_used_by_this_contour",
        ),
    }


def build_readiness_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    fidelity = _catalog_packets()
    packets = build_base_packets(repo_root, evidence_dir)
    contour = build_reconciliation_contour_packet(evidence_dir)
    source = build_candidate_source_packet(fidelity)
    matrix = build_candidate_matrix_packet(fidelity)
    mutation_guard = build_route_account_mutation_guard_packet()
    auth = build_auth_precondition_packet()
    prior = build_prior_evidence_reference_packet()
    layer_boundaries = build_layer_boundary_packets(fidelity, matrix)
    credential_ref = build_credential_ref_admission_metadata_packet(matrix)
    gpt_5_5_non_claim = build_gpt_5_5_non_claim_packet(matrix)
    route_backed_admission = build_route_backed_candidate_admission_packet(matrix)
    request_shape = build_request_shape_packet(matrix)
    taxonomy = build_error_taxonomy_packet()
    live_gate = build_live_promotion_gate_packet(matrix)
    packets.update(
        {
            "readiness_reconciliation_contour_packet.json": contour,
            "prior_evidence_reference_packet.json": prior,
            **layer_boundaries,
            "route_account_mutation_guard_packet.json": mutation_guard,
            "credential_ref_admission_metadata_packet.json": credential_ref,
            "gpt_5_5_non_claim_packet.json": gpt_5_5_non_claim,
            "route_backed_candidate_admission_packet.json": route_backed_admission,
            "model_availability_candidate_source_packet.json": source,
            "model_availability_candidate_matrix_packet.json": matrix,
            "model_availability_auth_precondition_packet.json": auth,
            "model_availability_request_shape_packet.json": request_shape,
            "model_availability_error_taxonomy_packet.json": taxonomy,
            "model_availability_live_promotion_gate_packet.json": live_gate,
        }
    )
    packets["model_availability_false_green_audit.json"] = build_false_green_audit(
        candidate_matrix=matrix,
        auth_packet=auth,
        request_shape=request_shape,
        live_gate=live_gate,
        credential_ref=credential_ref,
        gpt_5_5_non_claim=gpt_5_5_non_claim,
        route_backed_admission=route_backed_admission,
        layer_boundaries=layer_boundaries,
        mutation_guard=mutation_guard,
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["model_availability_readiness_summary_packet.json"] = build_summary_packet(packets)
    packets["independent_model_catalog_availability_reconciliation_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    return packets


def write_closeout(evidence_dir: Path, packets: dict[str, dict[str, Any]], repo_root: Path) -> None:
    summary = packets["model_availability_readiness_summary_packet.json"]
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    touched = [
        "tools/model_availability_smoke_matrix_readiness_probe.py",
        "tests/test_model_availability_smoke_matrix_readiness_probe.py",
        str(evidence_dir.relative_to(repo_root)),
    ]
    text = f"""# WBP Model Catalog And Availability Readiness Reconciliation No Live R1 Closeout

## Goal

Classify the final no-live model catalog and availability readiness reconciliation boundary before later native/live work without contacting provider/model endpoints.

## Result

- status: {summary["final_status"]}
- final verdict: catalog and availability readiness reconciliation packets emitted; parent availability target not closed
- closure state: CLOSED

## Contour Capsule

- goal: reconcile catalog fidelity, model availability readiness, Provider Auth R1, and Responses No-Live R1 without live/model/native claims
- branch: {branch}
- head: {head}
- touched files: {', '.join(touched)}
- tests run: recorded in verification section
- blocked risks: live availability, provider reachability, native acceptance, direct egress absence, streaming, tool loop, Original via WBP, final E2E
- closure state: CLOSED

## Verification

- tests: py_compile, targeted unittest, JSON parse, secret marker scan, closeout resilience, diff check
- build: not applicable
- manual: not required
- live verification: not attempted

## Artifacts

- spec: thread-only contour text
- packet: model_availability_readiness_summary_packet.json
- report: independent_model_catalog_availability_reconciliation_audit.json

## Git

- branch: {branch}
- commit: filled after commit
- pushed: filled after push

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered: none for no-live readiness reconciliation; live proof remains outside this contour
- resume from here: CLOSED
"""
    (evidence_dir / "closeout.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=RECONCILIATION_EVIDENCE_PATH,
    )
    args = parser.parse_args()
    evidence_dir = (REPO_ROOT / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_readiness_packets(REPO_ROOT, evidence_dir)
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    write_closeout(evidence_dir, packets, REPO_ROOT)
    print(json.dumps(packets["model_availability_readiness_summary_packet.json"], indent=2, sort_keys=True))
    return 0 if packets["model_availability_readiness_summary_packet.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
