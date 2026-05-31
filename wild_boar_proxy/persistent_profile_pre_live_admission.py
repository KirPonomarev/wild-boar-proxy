# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pre-live admission helpers for Persistent Custom profile contours."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TARGET_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_PRE_LIVE_ADMISSION_R5_CLASSIFIED"
PARENT_STATUS = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"

R1_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_LAUNCHER_CONTRACT_READINESS_R1_CLASSIFIED"
R2_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_LAUNCHER_DRY_RUN_ENFORCEMENT_READINESS_R2_CLASSIFIED"
R3_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_STATE_DIFF_REDACTION_READINESS_R3_CLASSIFIED"
R4_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_RESTORE_DRY_RUN_READINESS_R4_CLASSIFIED"

REFERENCE_SPECS = {
    "r1_launcher_contract": {
        "packet_kind": "persistent_pre_live_r1_launcher_contract_reference",
        "summary": "persistent_launcher_readiness_summary_packet.json",
        "expected_final_status": R1_STATUS,
        "supporting": [
            "persistent_launcher_contract_packet.json",
            "persistent_profile_identity_contract_packet.json",
            "persistent_profile_path_authority_packet.json",
            "original_codex_profile_non_dependency_packet.json",
            "persistent_launcher_non_substitution_packet.json",
        ],
    },
    "r2_dry_run_enforcement": {
        "packet_kind": "persistent_pre_live_r2_dry_run_enforcement_reference",
        "summary": "persistent_launcher_enforcement_summary_packet.json",
        "expected_final_status": R2_STATUS,
        "supporting": [
            "persistent_launcher_enforcement_contract_packet.json",
            "persistent_path_authority_enforcement_packet.json",
            "persistent_no_silent_fallback_packet.json",
            "persistent_original_profile_guard_packet.json",
            "persistent_launcher_live_enforcement_non_claim_packet.json",
        ],
    },
    "r3_state_diff": {
        "packet_kind": "persistent_pre_live_r3_state_diff_reference",
        "summary": "persistent_state_diff_summary_packet.json",
        "expected_final_status": R3_STATUS,
        "supporting": [
            "persistent_profile_snapshot_schema_packet.json",
            "persistent_profile_diff_schema_packet.json",
            "persistent_redaction_policy_packet.json",
            "thread_history_non_claim_packet.json",
        ],
    },
    "r4_backup_restore": {
        "packet_kind": "persistent_pre_live_r4_backup_restore_reference",
        "summary": "persistent_backup_restore_summary_packet.json",
        "expected_final_status": R4_STATUS,
        "supporting": [
            "persistent_backup_restore_contract_packet.json",
            "persistent_backup_path_authority_packet.json",
            "persistent_restore_path_authority_packet.json",
            "persistent_destructive_action_guard_packet.json",
            "persistent_original_profile_backup_restore_guard_packet.json",
        ],
    },
}

REFERENCE_KEY_TO_FILENAME = {
    "r1_launcher_contract": "persistent_pre_live_r1_launcher_contract_reference_packet.json",
    "r2_dry_run_enforcement": "persistent_pre_live_r2_dry_run_enforcement_reference_packet.json",
    "r3_state_diff": "persistent_pre_live_r3_state_diff_reference_packet.json",
    "r4_backup_restore": "persistent_pre_live_r4_backup_restore_reference_packet.json",
}

NON_CLAIM_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_input_required",
    "owner_prompt_required",
    "live_provider_request_attempted",
    "persistent_profile_state_written",
    "backup_created",
    "restore_executed",
    "cleanup_attempted",
    "cleanup_executed",
    "rollback_executed",
    "rollback_proven",
    "command_executed",
    "lock_acquired",
    "thread_history_preservation_claimed",
    "profile_storage_persistence_claimed",
    "native_ux_claimed",
    "keychain_behavior_classified",
    "route_proven",
    "direct_egress_absence_claimed",
    "model_availability_claimed",
    "original_reversibility_proven",
    "final_e2e_claimed",
}

FORBIDDEN_TRUE_FIELDS = {
    *NON_CLAIM_FIELDS,
    "prior_ok_treated_as_live_proof",
    "prior_evidence_reclassified_to_stronger_claim",
    "admission_counts_as_live_launch_safe",
    "admission_counts_as_runtime_permission",
    "admission_counts_as_thread_history_proof",
    "admission_counts_as_native_ux_acceptance",
    "admission_counts_as_backup_created",
    "admission_counts_as_restore_verified",
    "admission_counts_as_route_proof",
    "admission_counts_as_egress_proof",
    "admission_counts_as_model_availability",
    "admission_counts_as_original_reversibility",
    "admission_counts_as_final_e2e",
    "old_owner_visible_context_used_as_current_ui_proof",
    "old_route_trace_used_as_current_route_proof",
    "r3_state_diff_readiness_used_as_saved_thread_proof",
    "r4_backup_restore_readiness_used_as_backup_or_restore_execution",
    "original_codex_profile_dependency",
    "original_codex_profile_mutated",
    "original_codex_profile_runtime_dependency",
    "original_codex_used_as_source",
    "original_codex_used_as_target",
    "browser_client_path_authority",
    "remote_client_path_authority",
    "client_model_provider_authority",
    "silent_fallback_to_ephemeral_allowed",
    "destructive_action_allowed_by_default",
}


@dataclass(frozen=True)
class PriorEvidenceLocation:
    key: str
    evidence_dir: Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _field_true(value: Any, field: str) -> bool:
    if isinstance(value, dict):
        if value.get(field) is True:
            return True
        return any(_field_true(nested, field) for nested in value.values())
    if isinstance(value, list):
        return any(_field_true(nested, field) for nested in value)
    return False


def _extract_non_claim_flags(summary: dict[str, Any]) -> dict[str, bool]:
    return {
        field: bool(summary.get(field))
        for field in sorted(NON_CLAIM_FIELDS)
        if field in summary
    }


def _safe_json(path: Path) -> tuple[dict[str, Any], str]:
    if not path.exists():
        return {}, "missing"
    try:
        return read_json(path), ""
    except (OSError, json.JSONDecodeError) as exc:
        return {}, type(exc).__name__


def build_prior_reference_packet(
    *,
    repo_root: Path,
    location: PriorEvidenceLocation,
) -> dict[str, Any]:
    spec = REFERENCE_SPECS[location.key]
    evidence_dir = location.evidence_dir.resolve(strict=False)
    summary_path = evidence_dir / str(spec["summary"])
    summary, read_error = _safe_json(summary_path)
    summary_hash = sha256_file(summary_path) if summary_path.exists() and not read_error else ""
    supporting_packets: list[dict[str, Any]] = []
    missing_supporting_packets: list[str] = []
    for filename in spec["supporting"]:
        support_path = evidence_dir / filename
        if not support_path.exists():
            missing_supporting_packets.append(filename)
            continue
        supporting_packets.append(
            {
                "packet_name": filename,
                "packet_path": display_path(support_path, repo_root),
                "packet_sha256": sha256_file(support_path),
            }
        )

    expected_final_status = str(spec["expected_final_status"])
    status_ok = summary.get("status") == "ok"
    final_status_ok = summary.get("final_status") == expected_final_status
    hash_recorded = bool(summary_hash)
    non_claim_flags = _extract_non_claim_flags(summary)
    non_claim_overclaims = [
        field for field, value in non_claim_flags.items() if value is True
    ]
    ok = (
        not read_error
        and status_ok
        and final_status_ok
        and hash_recorded
        and not missing_supporting_packets
        and not non_claim_overclaims
    )
    return packet(
        str(spec["packet_kind"]),
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PRIOR_EVIDENCE_REFERENCE_UNUSABLE",
        contour_key=location.key,
        evidence_dir=display_path(evidence_dir, repo_root),
        summary_packet_name=str(spec["summary"]),
        summary_packet_path=display_path(summary_path, repo_root),
        summary_packet_present=summary_path.exists(),
        summary_packet_read_error=read_error,
        summary_packet_sha256=summary_hash,
        prior_status=summary.get("status", ""),
        prior_final_status=summary.get("final_status", ""),
        expected_final_status=expected_final_status,
        prior_status_ok=status_ok,
        prior_final_status_ok=final_status_ok,
        packet_hash_recorded=hash_recorded,
        supporting_packets=supporting_packets,
        missing_supporting_packets=missing_supporting_packets,
        non_claim_flags=non_claim_flags,
        non_claim_overclaims=non_claim_overclaims,
        prior_ok_treated_as_live_proof=False,
        prior_evidence_reclassified_to_stronger_claim=False,
        old_owner_visible_context_used_as_current_ui_proof=False,
        old_route_trace_used_as_current_route_proof=False,
        r3_state_diff_readiness_used_as_saved_thread_proof=False,
        r4_backup_restore_readiness_used_as_backup_or_restore_execution=False,
    )


def build_prior_reference_hashes_packet(
    references: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    entries = [
        {
            "contour_key": ref.get("contour_key"),
            "summary_packet_path": ref.get("summary_packet_path"),
            "summary_packet_sha256": ref.get("summary_packet_sha256"),
            "supporting_packets": ref.get("supporting_packets", []),
        }
        for ref in references.values()
    ]
    missing_hashes = [
        str(entry.get("contour_key"))
        for entry in entries
        if not entry.get("summary_packet_sha256")
    ]
    return packet(
        "persistent_pre_live_prior_reference_hashes",
        status="ok" if not missing_hashes else "blocked",
        referenced_packet_count=sum(
            1 + len(entry.get("supporting_packets", [])) for entry in entries
        ),
        references=entries,
        missing_summary_hashes=missing_hashes,
        reference_hashes_are_live_proof=False,
    )


def build_admission_contract_packet() -> dict[str, Any]:
    return packet(
        "persistent_pre_live_admission_contract",
        parent_target=PARENT_STATUS,
        target_status=TARGET_STATUS,
        contour_scope="pre_live_admission_only",
        admission_is_required_planning_prerequisite=True,
        admission_counts_as_runtime_permission=False,
        admission_counts_as_live_launch_safe=False,
        admission_counts_as_thread_history_proof=False,
        admission_counts_as_native_ux_acceptance=False,
        admission_counts_as_backup_created=False,
        admission_counts_as_restore_verified=False,
        admission_counts_as_route_proof=False,
        admission_counts_as_egress_proof=False,
        admission_counts_as_model_availability=False,
        admission_counts_as_original_reversibility=False,
        admission_counts_as_final_e2e=False,
    )


def build_no_live_execution_packet() -> dict[str, Any]:
    return packet(
        "persistent_pre_live_no_live_execution",
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_input_required=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        persistent_profile_state_written=False,
        backup_created=False,
        restore_executed=False,
        cleanup_attempted=False,
        rollback_executed=False,
        command_executed=False,
        lock_acquired=False,
    )


def build_original_codex_boundary_packet(
    references: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    blocked_reference_keys = [
        key
        for key, ref in references.items()
        if ref.get("status") != "ok"
        or _field_true(ref, "original_codex_profile_dependency")
        or _field_true(ref, "original_codex_profile_runtime_dependency")
        or _field_true(ref, "original_codex_profile_mutated")
        or _field_true(ref, "original_codex_used_as_source")
        or _field_true(ref, "original_codex_used_as_target")
    ]
    return packet(
        "persistent_pre_live_original_codex_boundary",
        status="ok" if not blocked_reference_keys else "blocked",
        blocked_reference_keys=blocked_reference_keys,
        original_codex_profile_dependency=False,
        original_codex_profile_runtime_dependency=False,
        original_codex_profile_mutated=False,
        original_codex_used_as_source=False,
        original_codex_used_as_target=False,
        original_codex_reversibility_proven=False,
    )


def build_block_reason_matrix_packet(
    references: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for key, ref in references.items():
        rows.append(
            {
                "contour_key": key,
                "missing_reference": not ref.get("summary_packet_present"),
                "blocked_reference_status": ref.get("prior_status") != "ok",
                "blocked_final_status": ref.get("prior_final_status")
                != ref.get("expected_final_status"),
                "missing_hash": not ref.get("summary_packet_sha256"),
                "missing_supporting_packets": ref.get("missing_supporting_packets", []),
                "non_claim_overclaims": ref.get("non_claim_overclaims", []),
            }
        )
    blocked_rows = [
        row
        for row in rows
        if row["missing_reference"]
        or row["blocked_reference_status"]
        or row["blocked_final_status"]
        or row["missing_hash"]
        or row["missing_supporting_packets"]
        or row["non_claim_overclaims"]
    ]
    return packet(
        "persistent_pre_live_block_reason_matrix",
        status="ok" if not blocked_rows else "blocked",
        rows=rows,
        blocked_rows=blocked_rows,
        block_reasons_are_admission_only=True,
    )


def build_admission_decision_packet(
    *,
    references: dict[str, dict[str, Any]],
    original_boundary_packet: dict[str, Any],
    no_live_execution_packet: dict[str, Any],
) -> dict[str, Any]:
    missing = sorted(set(REFERENCE_SPECS) - set(references))
    blocked = sorted(
        key for key, ref in references.items() if ref.get("status") != "ok"
    )
    no_live_ok = no_live_execution_packet.get("status") == "ok"
    original_ok = original_boundary_packet.get("status") == "ok"
    admitted = not missing and not blocked and no_live_ok and original_ok
    return packet(
        "persistent_pre_live_admission_decision",
        status="ok" if admitted else "blocked",
        admission_decision="admitted_for_planning" if admitted else "blocked",
        missing_reference_keys=missing,
        blocked_reference_keys=blocked,
        no_live_execution_ok=no_live_ok,
        original_codex_boundary_ok=original_ok,
        future_live_contour_may_be_planned=admitted,
        admission_counts_as_runtime_permission=False,
        admission_counts_as_live_launch_safe=False,
        admission_counts_as_thread_history_proof=False,
        admission_counts_as_native_ux_acceptance=False,
        admission_counts_as_backup_created=False,
        admission_counts_as_restore_verified=False,
        admission_counts_as_route_proof=False,
        admission_counts_as_egress_proof=False,
        admission_counts_as_model_availability=False,
        admission_counts_as_original_reversibility=False,
        admission_counts_as_final_e2e=False,
    )


def _scan_forbidden_true(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_FIELDS and nested is True:
                findings.append(nested_path)
            findings.extend(_scan_forbidden_true(nested, nested_path))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_scan_forbidden_true(nested, f"{prefix}[{index}]"))
    return findings


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    for filename, payload in packets.items():
        findings.extend(f"{filename}.{path}" for path in _scan_forbidden_true(payload))
    blocked = [
        filename
        for filename, payload in packets.items()
        if payload.get("status") == "blocked"
        and filename != "persistent_pre_live_summary_packet.json"
    ]
    findings.extend(f"{filename}.status=blocked" for filename in blocked)
    return packet(
        "persistent_pre_live_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_true_fields=sorted(FORBIDDEN_TRUE_FIELDS),
        prior_reference_truth_only=True,
        text_only_audit_counted_as_pass=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "persistent_pre_live_admission_contract_packet.json",
        "persistent_pre_live_r1_launcher_contract_reference_packet.json",
        "persistent_pre_live_r2_dry_run_enforcement_reference_packet.json",
        "persistent_pre_live_r3_state_diff_reference_packet.json",
        "persistent_pre_live_r4_backup_restore_reference_packet.json",
        "persistent_pre_live_admission_decision_packet.json",
        "persistent_pre_live_block_reason_matrix_packet.json",
        "persistent_pre_live_no_live_execution_packet.json",
        "persistent_pre_live_original_codex_boundary_packet.json",
        "persistent_pre_live_prior_reference_hashes_packet.json",
        "persistent_pre_live_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = sorted(
        filename
        for filename in required & set(packets)
        if packets[filename].get("status") != "ok"
    )
    ok = not missing and not blocked
    return packet(
        "persistent_pre_live_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "PERSISTENT_PRE_LIVE_ADMISSION_R5_BLOCKED",
        parent_target=PARENT_STATUS,
        parent_target_closed=False,
        this_target_closed=ok,
        missing_required_packets=missing,
        blocked_packets=blocked,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_input_required=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        persistent_profile_state_written=False,
        backup_created=False,
        restore_executed=False,
        cleanup_attempted=False,
        rollback_proven=False,
        thread_history_preservation_claimed=False,
        profile_storage_persistence_claimed=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        route_proven=False,
        direct_egress_absence_claimed=False,
        model_availability_claimed=False,
        original_reversibility_proven=False,
        final_e2e_claimed=False,
    )


def build_admission_packets(
    *,
    repo_root: Path,
    locations: list[PriorEvidenceLocation],
) -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    references: dict[str, dict[str, Any]] = {}
    for location in locations:
        reference = build_prior_reference_packet(repo_root=repo_root, location=location)
        references[location.key] = reference
        packets[REFERENCE_KEY_TO_FILENAME[location.key]] = reference

    packets["persistent_pre_live_admission_contract_packet.json"] = (
        build_admission_contract_packet()
    )
    packets["persistent_pre_live_no_live_execution_packet.json"] = (
        build_no_live_execution_packet()
    )
    packets["persistent_pre_live_original_codex_boundary_packet.json"] = (
        build_original_codex_boundary_packet(references)
    )
    packets["persistent_pre_live_prior_reference_hashes_packet.json"] = (
        build_prior_reference_hashes_packet(references)
    )
    packets["persistent_pre_live_block_reason_matrix_packet.json"] = (
        build_block_reason_matrix_packet(references)
    )
    packets["persistent_pre_live_admission_decision_packet.json"] = (
        build_admission_decision_packet(
            references=references,
            original_boundary_packet=packets[
                "persistent_pre_live_original_codex_boundary_packet.json"
            ],
            no_live_execution_packet=packets[
                "persistent_pre_live_no_live_execution_packet.json"
            ],
        )
    )
    packets["persistent_pre_live_false_green_audit.json"] = build_false_green_audit(
        packets
    )
    packets["persistent_pre_live_summary_packet.json"] = build_summary_packet(packets)
    return packets
