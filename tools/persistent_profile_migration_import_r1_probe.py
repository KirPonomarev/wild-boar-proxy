#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import packet-backed Persistent Custom migration/import boundaries under current limits."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import json_write


DEFAULT_SOURCE_DIRS = {
    "r1_contract": ROOT
    / "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27",
    "r4_dry_run": ROOT
    / "audit_results/wbp_persistent_profile_backup_restore_dry_run_readiness_r4_2026-05-27",
    "backup_repair": ROOT
    / "audit_results/wbp_persistent_custom_profile_backup_rollback_repair_r1_2026-05-27",
    "history_import": ROOT
    / "audit_results/wbp_persistent_custom_profile_history_import_r1_2026-05-27",
}

SOURCE_REQUIRED_PACKETS = {
    "r1_contract": {
        "persistent_launcher_readiness_summary_packet.json",
        "persistent_launcher_false_green_audit.json",
        "persistent_profile_identity_contract_packet.json",
        "persistent_backup_export_policy_packet.json",
        "persistent_migration_import_non_claim_packet.json",
        "original_codex_profile_non_dependency_packet.json",
    },
    "r4_dry_run": {
        "persistent_backup_restore_summary_packet.json",
        "persistent_backup_restore_contract_packet.json",
        "persistent_backup_path_authority_packet.json",
        "persistent_restore_path_authority_packet.json",
        "persistent_backup_manifest_schema_packet.json",
        "persistent_restore_manifest_schema_packet.json",
        "persistent_original_profile_backup_restore_guard_packet.json",
        "persistent_backup_restore_equivalence_non_claim_packet.json",
        "persistent_backup_restore_non_claim_packet.json",
        "persistent_backup_restore_false_green_audit.json",
        "independent_persistent_backup_restore_dry_run_audit.json",
    },
    "backup_repair": {
        "backup_repair_summary_packet.json",
        "state_backup_manifest_packet.json",
        "backup_surface_classification_packet.json",
        "backup_repair_policy_packet.json",
        "backup_repair_false_green_audit.json",
    },
    "history_import": {
        "persistent_profile_continuity_classification_packet.json",
        "persistent_profile_summary_packet.json",
        "persistent_profile_false_green_audit.json",
        "independent_persistent_profile_audit.json",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_import_input_error",
        "status": "blocked",
        "reason_class": reason_class,
        "message": message,
        "traceback_emitted": False,
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        json_write(evidence_dir / "input_error_packet.json", packet)
    print(json.dumps(packet, indent=2, sort_keys=True), file=sys.stderr)
    return 2


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _historical_quarantine(
    repo_root: Path, evidence_dir: Path
) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
                "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            )
        )
    ]
    admitted_current_contour = [
        "tools/persistent_profile_migration_import_r1_probe.py",
        "tests/test_persistent_profile_migration_import_r1_probe.py",
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _version_packet(repo_root: Path) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "status": "ok",
        "codex_cli_version": _run(repo_root, ["codex", "--version"], check=False),
        "codex_cli_path": _run(repo_root, ["which", "codex"], check=False),
        "codex_app_path": "/Applications/Codex.app",
        "codex_app_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
            check=False,
        ),
        "codex_app_bundle_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
            check=False,
        ),
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="persistent-profile-migration-import-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--r1-contract-dir", default=str(DEFAULT_SOURCE_DIRS["r1_contract"]))
    parser.add_argument("--r4-dry-run-dir", default=str(DEFAULT_SOURCE_DIRS["r4_dry_run"]))
    parser.add_argument("--backup-repair-dir", default=str(DEFAULT_SOURCE_DIRS["backup_repair"]))
    parser.add_argument("--history-import-dir", default=str(DEFAULT_SOURCE_DIRS["history_import"]))
    return parser


def _load_sources(
    source_dirs: dict[str, Path],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, list[str]], dict[str, list[str]]]:
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    missing: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}
    for label, required in SOURCE_REQUIRED_PACKETS.items():
        parsed[label] = {}
        missing[label] = []
        invalid[label] = []
        source_dir = source_dirs[label]
        for name in sorted(required):
            path = source_dir / name
            if not path.exists():
                missing[label].append(name)
                continue
            try:
                parsed[label][name] = _read_json(path)
            except json.JSONDecodeError:
                invalid[label].append(name)
    return parsed, missing, invalid


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_dirs: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    parsed, missing, invalid = _load_sources(source_dirs)

    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": status_lines,
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
        "master_plan_written_to_repo": False,
    }
    packets["historical_dirt_quarantine_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "quarantine_classification": "out_of_scope_historical_residue",
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["version_pinning_packet.json"] = _version_packet(repo_root)

    inventory_ok = all(not missing[label] and not invalid[label] for label in SOURCE_REQUIRED_PACKETS)
    packets["source_persistent_migration_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_persistent_migration_evidence_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "current_live_migration_execution_performed": False,
    }

    r1 = parsed["r1_contract"]
    r4 = parsed["r4_dry_run"]
    repair = parsed["backup_repair"]
    history = parsed["history_import"]

    r1_summary = r1["persistent_launcher_readiness_summary_packet.json"]
    r1_false_green = r1["persistent_launcher_false_green_audit.json"]
    r1_identity = r1["persistent_profile_identity_contract_packet.json"]
    r1_backup_policy = r1["persistent_backup_export_policy_packet.json"]
    r1_migration = r1["persistent_migration_import_non_claim_packet.json"]
    r1_original = r1["original_codex_profile_non_dependency_packet.json"]

    r4_summary = r4["persistent_backup_restore_summary_packet.json"]
    r4_contract = r4["persistent_backup_restore_contract_packet.json"]
    r4_backup_path = r4["persistent_backup_path_authority_packet.json"]
    r4_restore_path = r4["persistent_restore_path_authority_packet.json"]
    r4_backup_manifest = r4["persistent_backup_manifest_schema_packet.json"]
    r4_restore_manifest = r4["persistent_restore_manifest_schema_packet.json"]
    r4_original_guard = r4["persistent_original_profile_backup_restore_guard_packet.json"]
    r4_equivalence = r4["persistent_backup_restore_equivalence_non_claim_packet.json"]
    r4_non_claim = r4["persistent_backup_restore_non_claim_packet.json"]
    r4_false_green = r4["persistent_backup_restore_false_green_audit.json"]
    r4_independent = r4["independent_persistent_backup_restore_dry_run_audit.json"]

    repair_summary = repair["backup_repair_summary_packet.json"]
    repair_manifest = repair["state_backup_manifest_packet.json"]
    repair_surface = repair["backup_surface_classification_packet.json"]
    repair_policy = repair["backup_repair_policy_packet.json"]
    repair_false_green = repair["backup_repair_false_green_audit.json"]

    history_class = history["persistent_profile_continuity_classification_packet.json"]
    history_summary = history["persistent_profile_summary_packet.json"]
    history_false_green = history["persistent_profile_false_green_audit.json"]
    history_independent = history["independent_persistent_profile_audit.json"]

    validation_checks = {
        "r1_migration_boundary_ok": (
            r1_summary.get("status") == "ok"
            and r1_false_green.get("status") == "ok"
            and r1_identity.get("status") == "ok"
            and r1_backup_policy.get("status") == "ok"
            and r1_migration.get("status") == "ok"
            and r1_migration.get("migration_import_disabled_for_ordinary_launch") is True
            and r1_migration.get("migration_requires_separate_explicit_contour") is True
            and r1_migration.get("migration_import_performed") is False
            and r1_migration.get("original_codex_profile_used_as_source") is False
            and r1_migration.get("current_auth_json_copied") is False
            and r1_original.get("status") == "ok"
            and r1_original.get("original_codex_profile_dependency") is False
            and r1_original.get("original_codex_profile_used_as_custom_shortcut") is False
        ),
        "r4_backup_restore_boundary_ok": (
            r4_summary.get("status") == "ok"
            and r4_contract.get("status") == "ok"
            and r4_contract.get("contour_scope") == "dry_run_backup_restore_readiness_only"
            and r4_contract.get("backup_execution_allowed") is False
            and r4_contract.get("restore_execution_allowed") is False
            and r4_backup_path.get("status") == "ok"
            and r4_restore_path.get("status") == "ok"
            and r4_original_guard.get("status") == "ok"
            and r4_original_guard.get("original_codex_used_as_source") is False
            and r4_original_guard.get("original_codex_used_as_target") is False
            and r4_equivalence.get("status") == "ok"
            and r4_equivalence.get("restored_state_equivalence_proven") is False
            and r4_non_claim.get("status") == "ok"
            and r4_non_claim.get("restore_executed") is False
            and r4_false_green.get("status") == "ok"
            and r4_independent.get("status") == "ok"
        ),
        "backup_repair_reference_ok": (
            repair_summary.get("status") == "ok"
            and repair_summary.get("final_status")
            == "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY"
            and repair_summary.get("rollback_ready") is True
            and repair_manifest.get("status") == "ok"
            and repair_surface.get("status") == "ok"
            and repair_policy.get("status") == "ok"
            and repair_false_green.get("status") == "ok"
        ),
        "history_reference_limited_and_separate": (
            history_summary.get("status") == "ok"
            and history_class.get("status") == "ok"
            and history_class.get("final_status")
            == "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED_WITH_LIMITS"
            and history_class.get("with_limits_required") is True
            and history_class.get("route_proof_claimed") is False
            and history_class.get("final_e2e_claimed") is False
            and history_false_green.get("status") == "ok"
            and history_independent.get("status") == "ok"
        ),
    }
    packets["source_persistent_migration_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_persistent_migration_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [
            {"name": name, "passed": passed}
            for name, passed in validation_checks.items()
        ],
        "validation_scope": "bounded_migration_import_classification_only",
        "source_chain_counts_as_migration_execution": False,
        "source_chain_counts_as_persistent_continuity_reproof": False,
    }

    scope_ok = (
        packets["source_persistent_migration_evidence_inventory_packet.json"]["status"] == "ok"
        and validation_checks["r1_migration_boundary_ok"]
        and validation_checks["r4_backup_restore_boundary_ok"]
    )
    packets["persistent_profile_migration_scope_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_scope",
        "status": "ok" if scope_ok else "blocked",
        "migration_scope_explicit": (
            r1_migration.get("migration_requires_separate_explicit_contour") is True
        ),
        "ordinary_launch_not_migration": (
            r1_migration.get("migration_import_disabled_for_ordinary_launch") is True
        ),
        "migration_import_performed_in_source_chain": (
            r1_migration.get("migration_import_performed") is True
        ),
        "current_contour_executes_migration": False,
        "backup_restore_execution_proven": False,
        "scope_boundary_counts_as_execution_success": False,
    }

    trigger_ok = (
        r1_migration.get("migration_import_disabled_for_ordinary_launch") is True
        and r1_migration.get("migration_requires_separate_explicit_contour") is True
    )
    packets["persistent_profile_migration_trigger_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_trigger",
        "status": "ok" if trigger_ok else "blocked",
        "explicit_migration_trigger_required": (
            r1_migration.get("migration_requires_separate_explicit_contour") is True
        ),
        "trigger_observed_in_this_contour": False,
        "implicit_first_launch_counts_as_migration": False,
        "ordinary_launch_counts_as_migration": False,
        "hidden_migration_allowed": False,
    }

    source_profile_id = repair_summary.get("profile_id", "")
    target_profile_id = r1_identity.get("persistent_profile_id", "")
    target_profile_root = r4_restore_path.get("restore_target_root", "")
    source_target_ok = (
        r1_identity.get("status") == "ok"
        and r4_backup_path.get("status") == "ok"
        and r4_restore_path.get("status") == "ok"
        and source_profile_id == target_profile_id
        and r4_restore_path.get("restore_target_is_persistent_profile_root") is True
        and r4_original_guard.get("original_codex_used_as_source") is False
        and r4_original_guard.get("original_codex_used_as_target") is False
        and r1_migration.get("current_auth_json_copied") is False
    )
    packets["persistent_profile_source_target_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_source_target",
        "status": "ok" if source_target_ok else "blocked",
        "source_identity_type": "selective_state_backup_artifact_for_persistent_custom_profile",
        "source_profile_id": source_profile_id,
        "source_backup_root": repair_summary.get("timestamped_backup_root", ""),
        "source_backup_root_under_wbp_control": (
            r4_backup_path.get("backup_root_under_wbp_backup_root") is True
        ),
        "target_identity_type": "persistent_custom_profile",
        "target_profile_id": target_profile_id,
        "target_profile_root": target_profile_root,
        "target_profile_root_matches_identity_contract": (
            target_profile_root == r1_identity.get("persistent_profile_root", "")
        ),
        "source_profile_id_matches_target_profile_id": source_profile_id == target_profile_id,
        "cross_profile_migration_proven": False,
        "original_codex_used_as_source": (
            r4_original_guard.get("original_codex_used_as_source") is True
        ),
        "original_codex_used_as_target": (
            r4_original_guard.get("original_codex_used_as_target") is True
        ),
        "current_auth_json_copied": r1_migration.get("current_auth_json_copied") is True,
    }

    copied_state_classes = repair_surface.get("copied_classes", [])
    excluded_state_classes = repair_surface.get("excluded_classes", [])
    unknown_state_classes = sorted(
        state_class
        for state_class in copied_state_classes
        if "unclassified" in str(state_class)
    )
    matrix_ok = (
        repair_manifest.get("status") == "ok"
        and repair_surface.get("status") == "ok"
        and bool(copied_state_classes)
        and bool(excluded_state_classes)
    )
    packets["persistent_profile_state_copy_matrix.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_state_copy_matrix",
        "status": "ok" if matrix_ok else "blocked",
        "copied_state_classes": copied_state_classes,
        "excluded_state_classes": excluded_state_classes,
        "unknown_or_unclassified_state_classes": unknown_state_classes,
        "copied_file_count": repair_manifest.get("copied_file_count", 0),
        "copied_dir_count": repair_manifest.get("copied_dir_count", 0),
        "copy_failure_count": len(repair_manifest.get("copy_failures", [])),
        "copied_equals_restored_equivalence": False,
        "omitted_state_classes_count_as_harmless": False,
        "copy_matrix_complete_for_bounded_backup_surface": matrix_ok,
    }

    recovery_policy_ok = (
        repair_summary.get("rollback_ready") is True
        and r1_backup_policy.get("rollback_expectation_declared") is True
        and repair_policy.get("policy") == "timestamped_selective_state_backup"
        and repair_policy.get("persistent_profile_deletion_allowed") is False
    )
    packets["persistent_profile_migration_recovery_policy_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_recovery_policy",
        "status": "ok" if recovery_policy_ok else "blocked",
        "rollback_ready": repair_summary.get("rollback_ready") is True,
        "rollback_expectation_declared": (
            r1_backup_policy.get("rollback_expectation_declared") is True
        ),
        "recovery_policy": repair_policy.get("policy", ""),
        "backup_required_before_first_persistent_write": (
            r1_backup_policy.get("backup_export_required_before_first_persistent_write")
            is True
        ),
        "rollback_policy_counts_as_successful_migration": False,
        "rollback_execution_proven": False,
    }

    verification_ok = (
        r4_backup_manifest.get("status") == "ok"
        and r4_restore_manifest.get("status") == "ok"
        and r4_equivalence.get("status") == "ok"
        and history_class.get("status") == "ok"
    )
    packets["persistent_profile_migration_verification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_verification",
        "status": "ok" if verification_ok else "blocked",
        "verification_boundary": "schema_and_bounded_backup_artifact_only",
        "backup_manifest_schema_ready": r4_backup_manifest.get("status") == "ok",
        "restore_manifest_schema_ready": r4_restore_manifest.get("status") == "ok",
        "restored_state_equivalence_proven": (
            r4_equivalence.get("restored_state_equivalence_proven") is True
        ),
        "migration_execution_verified": False,
        "persistent_continuity_reproved": False,
        "restored_behavior_proven": False,
        "route_proof_claimed": False,
        "auth_proof_claimed": False,
        "final_e2e_claimed": False,
    }

    classification_ok = (
        packets["persistent_profile_migration_scope_packet.json"]["status"] == "ok"
        and packets["persistent_profile_migration_trigger_packet.json"]["status"] == "ok"
        and packets["persistent_profile_source_target_packet.json"]["status"] == "ok"
        and packets["persistent_profile_state_copy_matrix.json"]["status"] == "ok"
        and packets["persistent_profile_migration_recovery_policy_packet.json"]["status"]
        == "ok"
        and packets["persistent_profile_migration_verification_packet.json"]["status"] == "ok"
    )
    packets["persistent_profile_migration_classification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_classification",
        "status": "ok" if classification_ok else "blocked",
        "final_status": (
            "WBP_CUSTOM_PERSISTENT_PROFILE_MIGRATION_CLASSIFIED_WITH_LIMITS"
            if classification_ok
            else ""
        ),
        "migration_trigger_explicit": True,
        "ordinary_launch_not_migration": True,
        "source_target_boundary_classified": classification_ok,
        "state_copy_matrix_classified": matrix_ok,
        "rollback_restore_policy_explicit": recovery_policy_ok,
        "original_silent_shortcut_excluded": (
            r1_migration.get("original_codex_profile_used_as_source") is False
            and r1_original.get("original_codex_profile_used_as_custom_shortcut") is False
            and r1_migration.get("current_auth_json_copied") is False
            and r4_original_guard.get("original_codex_used_as_source") is False
        ),
        "migration_execution_proven": False,
        "restored_state_equivalence_proven": False,
        "persistent_continuity_claimed": False,
        "route_proof_claimed": False,
        "auth_proof_claimed": False,
        "native_ux_claimed": False,
        "final_e2e_claimed": False,
        "with_limits_required": True,
        "with_limits_reasons": [
            "MIGRATION_EXECUTION_NOT_PROVEN",
            "RESTORED_STATE_EQUIVALENCE_NOT_PROVEN",
            "UNKNOWN_OR_UNCLASSIFIED_STATE_CLASSES_PRESENT",
            "POST_MIGRATION_RESTORED_BEHAVIOR_NOT_PROVEN",
        ],
    }

    false_green_checks = [
        {
            "name": "ordinary_launch_not_treated_as_migration",
            "passed": packets["persistent_profile_migration_scope_packet.json"][
                "ordinary_launch_not_migration"
            ]
            is True,
        },
        {
            "name": "original_not_silent_source",
            "passed": packets["persistent_profile_migration_classification_packet.json"][
                "original_silent_shortcut_excluded"
            ]
            is True,
        },
        {
            "name": "migration_execution_not_claimed",
            "passed": packets["persistent_profile_migration_classification_packet.json"][
                "migration_execution_proven"
            ]
            is False,
        },
        {
            "name": "restored_equivalence_not_claimed",
            "passed": packets["persistent_profile_migration_classification_packet.json"][
                "restored_state_equivalence_proven"
            ]
            is False,
        },
        {
            "name": "no_continuity_route_auth_or_final_e2e_claim",
            "passed": packets["persistent_profile_migration_classification_packet.json"][
                "persistent_continuity_claimed"
            ]
            is False
            and packets["persistent_profile_migration_classification_packet.json"][
                "route_proof_claimed"
            ]
            is False
            and packets["persistent_profile_migration_classification_packet.json"][
                "auth_proof_claimed"
            ]
            is False
            and packets["persistent_profile_migration_classification_packet.json"][
                "final_e2e_claimed"
            ]
            is False,
        },
        {
            "name": "source_false_green_audits_ok",
            "passed": r1_false_green.get("status") == "ok"
            and r4_false_green.get("status") == "ok"
            and repair_false_green.get("status") == "ok"
            and history_false_green.get("status") == "ok",
        },
    ]
    packets["persistent_profile_migration_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(check["passed"] for check in false_green_checks),
    }

    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "explicit_migration_trigger_required": True,
            "migration_import_performed_in_source_chain": False,
            "source_profile_id": source_profile_id,
            "target_profile_id": target_profile_id,
            "source_backup_root": repair_summary.get("timestamped_backup_root", ""),
            "target_profile_root": target_profile_root,
            "copied_state_classes": copied_state_classes,
            "excluded_state_classes": excluded_state_classes,
            "unknown_or_unclassified_state_classes": unknown_state_classes,
            "rollback_ready": repair_summary.get("rollback_ready") is True,
            "migration_execution_proven": False,
            "restored_state_equivalence_proven": False,
            "final_status": packets["persistent_profile_migration_classification_packet.json"].get(
                "final_status", ""
            ),
        },
        "non_claims": {
            "persistent_continuity_claimed": False,
            "route_proof_claimed": False,
            "auth_proof_claimed": False,
            "final_e2e_claimed": False,
        },
    }

    packets["independent_persistent_profile_migration_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_persistent_profile_migration_audit",
        "status": "ok"
        if packets["source_persistent_migration_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_persistent_migration_validation_packet.json"]["status"] == "ok"
        and packets["persistent_profile_migration_classification_packet.json"]["status"] == "ok"
        and packets["persistent_profile_migration_false_green_audit.json"]["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "source_persistent_migration_evidence_inventory_packet.json",
            "source_persistent_migration_validation_packet.json",
            "persistent_profile_migration_scope_packet.json",
            "persistent_profile_migration_trigger_packet.json",
            "persistent_profile_source_target_packet.json",
            "persistent_profile_state_copy_matrix.json",
            "persistent_profile_migration_recovery_policy_packet.json",
            "persistent_profile_migration_verification_packet.json",
            "persistent_profile_migration_classification_packet.json",
            "persistent_profile_migration_false_green_audit.json",
            "scanner_agent_fact_report_packet.json",
        ],
        "current_live_migration_execution_collected": False,
        "current_owner_action_collected": False,
        "migration_execution_proven": False,
        "persistent_continuity_claimed": False,
        "route_proof_claimed": False,
        "auth_proof_claimed": False,
        "final_e2e_claimed": False,
    }

    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok"
        if classification_ok
        and packets["persistent_profile_migration_false_green_audit.json"]["status"] == "ok"
        and packets["independent_persistent_profile_migration_audit.json"]["status"] == "ok"
        else "blocked",
        "top_level_packet_statuses": {
            name: packet.get("status", "missing") for name, packet in packets.items()
        },
        "ok_packet_count": sum(
            1 for packet in packets.values() if packet.get("status") == "ok"
        ),
        "blocked_packet_count": sum(
            1 for packet in packets.values() if packet.get("status") == "blocked"
        ),
    }

    packets["persistent_profile_migration_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_migration_summary",
        "status": "ok"
        if packets["verification_results_packet.json"]["status"] == "ok"
        else "blocked",
        "final_status": (
            packets["persistent_profile_migration_classification_packet.json"].get(
                "final_status", ""
            )
            if packets["verification_results_packet.json"]["status"] == "ok"
            else ""
        ),
        "migration_trigger_explicit": True,
        "migration_execution_proven": False,
        "restored_state_equivalence_proven": False,
        "persistent_continuity_claimed": False,
        "route_proof_claimed": False,
        "auth_proof_claimed": False,
        "final_e2e_claimed": False,
        "with_limits_required": True,
    }
    return packets


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_dirs = {
        "r1_contract": Path(args.r1_contract_dir).resolve(),
        "r4_dry_run": Path(args.r4_dry_run_dir).resolve(),
        "backup_repair": Path(args.backup_repair_dir).resolve(),
        "history_import": Path(args.history_import_dir).resolve(),
    }
    if not repo_root.exists():
        return _emit_input_error(
            reason_class="REPO_ROOT_MISSING",
            message=f"repo root does not exist: {repo_root}",
            evidence_dir=evidence_dir,
        )
    for label, path in source_dirs.items():
        if not path.exists():
            return _emit_input_error(
                reason_class="SOURCE_EVIDENCE_DIR_MISSING",
                message=f"{label} source evidence dir does not exist: {path}",
                evidence_dir=evidence_dir,
            )
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
            evidence_dir=evidence_dir,
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        source_dirs=source_dirs,
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(
        json.dumps(
            packets["persistent_profile_migration_summary_packet.json"],
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if packets["persistent_profile_migration_summary_packet.json"]["status"] == "ok"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
