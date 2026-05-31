# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dry-run backup/restore readiness helpers for Persistent Custom profiles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .native_filesystem_probe import (
    PROTECTED_SURFACE_PATHS,
    default_persistent_custom_profile_paths,
)
from .persistent_profile_state_diff import redacted_snapshot_entry


TARGET_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_RESTORE_DRY_RUN_READINESS_R4_CLASSIFIED"
PARENT_STATUS = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"

RESTORE_POLICIES = {
    "dry_run_validate_only",
    "owner_authorized_destructive_restore_required",
}

RETENTION_POLICIES = {
    "manual_retention_until_owner_delete",
    "bounded_count_no_auto_delete_without_owner",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    path = _resolved(path)
    parent = _resolved(parent)
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(left: Path, right: Path) -> bool:
    left = _resolved(left)
    right = _resolved(right)
    return _path_is_relative_to(left, right) or _path_is_relative_to(right, left)


def _packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


@dataclass(frozen=True)
class PersistentBackupRestoreDryRunConfig:
    """All paths and execution flags needed to render dry-run packets."""

    profile_id: str
    persistent_profile_root: Path
    backup_root: Path
    restore_target_root: Path
    wbp_backup_root: Path
    original_codex_home: Path
    original_app_support_dir: Path
    owner_authorized_destructive_action: bool = False
    backup_execution_allowed: bool = False
    restore_execution_allowed: bool = False
    cleanup_execution_allowed: bool = False
    delete_execution_allowed: bool = False
    real_profile_inventory_allowed: bool = False
    rollback_proof_claimed: bool = False
    restored_state_equivalence_claimed: bool = False


def default_dry_run_config(
    *,
    profile_id: str = "wbp-custom-main",
    base_dir: Path | None = None,
    backup_base_dir: Path | None = None,
) -> PersistentBackupRestoreDryRunConfig:
    paths = default_persistent_custom_profile_paths(
        profile_id=profile_id,
        base_dir=base_dir,
    )
    profile_root = Path(paths["persistent_profile_root"])
    backup_root_base = (
        backup_base_dir
        if backup_base_dir is not None
        else Path.home()
        / "Library"
        / "Application Support"
        / "WildBoarProxy"
        / "CodexProfileBackups"
    )
    return PersistentBackupRestoreDryRunConfig(
        profile_id=profile_id,
        persistent_profile_root=profile_root,
        backup_root=backup_root_base / profile_id,
        restore_target_root=profile_root,
        wbp_backup_root=backup_root_base,
        original_codex_home=PROTECTED_SURFACE_PATHS["codex_dir"],
        original_app_support_dir=PROTECTED_SURFACE_PATHS["default_app_support_codex"],
    )


def _original_surfaces(config: PersistentBackupRestoreDryRunConfig) -> dict[str, Path]:
    return {
        **PROTECTED_SURFACE_PATHS,
        "original_codex_home": config.original_codex_home,
        "original_app_support_dir": config.original_app_support_dir,
    }


def _original_overlap(path: Path, config: PersistentBackupRestoreDryRunConfig) -> bool:
    return any(_paths_overlap(path, original) for original in _original_surfaces(config).values())


def build_backup_path_authority_packet(
    config: PersistentBackupRestoreDryRunConfig,
) -> dict[str, Any]:
    profile_root = _resolved(config.persistent_profile_root)
    backup_root = _resolved(config.backup_root)
    wbp_backup_root = _resolved(config.wbp_backup_root)
    under_wbp_backup_root = _path_is_relative_to(backup_root, wbp_backup_root)
    overlaps_profile_root = _paths_overlap(backup_root, profile_root)
    overlaps_original = _original_overlap(backup_root, config)
    ok = (
        bool(config.profile_id)
        and under_wbp_backup_root
        and not overlaps_profile_root
        and not overlaps_original
    )
    return _packet(
        "persistent_backup_path_authority",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_BACKUP_PATH_AUTHORITY_UNSAFE",
        persistent_profile_id=config.profile_id,
        persistent_profile_root=str(profile_root),
        wbp_backup_root=str(wbp_backup_root),
        backup_root=str(backup_root),
        backup_root_under_wbp_backup_root=under_wbp_backup_root,
        backup_root_overlaps_persistent_profile=overlaps_profile_root,
        backup_root_overlaps_original_codex=overlaps_original,
        browser_client_path_authority=False,
        remote_client_path_authority=False,
        backup_created=False,
        backup_execution_allowed=False,
    )


def build_restore_path_authority_packet(
    config: PersistentBackupRestoreDryRunConfig,
) -> dict[str, Any]:
    profile_root = _resolved(config.persistent_profile_root)
    restore_target = _resolved(config.restore_target_root)
    backup_root = _resolved(config.backup_root)
    target_is_persistent_root = restore_target == profile_root
    target_escapes_profile = not _path_is_relative_to(restore_target, profile_root)
    target_overlaps_original = _original_overlap(restore_target, config)
    target_overlaps_backup_root = _paths_overlap(restore_target, backup_root)
    ok = (
        bool(config.profile_id)
        and target_is_persistent_root
        and not target_escapes_profile
        and not target_overlaps_original
        and not target_overlaps_backup_root
    )
    return _packet(
        "persistent_restore_path_authority",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_RESTORE_PATH_AUTHORITY_UNSAFE",
        persistent_profile_id=config.profile_id,
        persistent_profile_root=str(profile_root),
        backup_root=str(backup_root),
        restore_target_root=str(restore_target),
        restore_target_is_persistent_profile_root=target_is_persistent_root,
        restore_target_escapes_persistent_profile=target_escapes_profile,
        restore_target_overlaps_original_codex=target_overlaps_original,
        restore_target_overlaps_backup_root=target_overlaps_backup_root,
        browser_client_path_authority=False,
        remote_client_path_authority=False,
        restore_executed=False,
        restore_execution_allowed=False,
    )


def synthetic_backup_entries() -> list[dict[str, Any]]:
    return [
        redacted_snapshot_entry(
            relative_path="settings/config.toml",
            size=72,
            content_hash=sha256_text("r4-settings-hash-only"),
        ),
        redacted_snapshot_entry(
            relative_path="Local Storage/state.vscdb",
            size=280,
            content_hash=sha256_text("r4-session-hash-only"),
        ),
        redacted_snapshot_entry(
            relative_path="conversations/thread-redacted.json",
            size=512,
            content_hash=sha256_text("r4-thread-hash-only"),
        ),
        redacted_snapshot_entry(
            relative_path="integrations/connector-state.json",
            size=96,
            content_hash=sha256_text("r4-integration-hash-only"),
        ),
    ]


def build_backup_manifest_schema_packet(
    config: PersistentBackupRestoreDryRunConfig,
    *,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entries = entries or synthetic_backup_entries()
    digest_input = [
        {
            "relative_path": entry["relative_path"],
            "kind": entry.get("kind"),
            "size": entry.get("size"),
            "sha256": entry.get("sha256"),
            "state_class": entry.get("state_class"),
        }
        for entry in sorted(entries, key=lambda item: str(item["relative_path"]))
    ]
    return _packet(
        "persistent_backup_manifest_schema",
        persistent_profile_id=config.profile_id,
        persistent_profile_root=str(_resolved(config.persistent_profile_root)),
        backup_root=str(_resolved(config.backup_root)),
        schema_version="persistent_backup_manifest_dry_run_v1",
        required_entry_fields=["relative_path", "kind", "size", "sha256", "state_class"],
        entry_count=len(entries),
        planned_entries=entries,
        manifest_digest=sha256_text(json.dumps(digest_input, sort_keys=True)),
        synthetic_fixture=True,
        manifest_materialized_from_real_profile=False,
        manifest_records_hashes_only=True,
        content_recorded=False,
        raw_prompt_recorded=False,
        raw_secret_recorded=False,
        backup_created=False,
        path_hash_inventory_is_restorable_backup=False,
    )


def build_restore_manifest_schema_packet(
    config: PersistentBackupRestoreDryRunConfig,
    *,
    backup_manifest_packet: dict[str, Any],
) -> dict[str, Any]:
    planned_entries = [
        {
            "relative_path": entry["relative_path"],
            "kind": entry.get("kind"),
            "size": entry.get("size"),
            "sha256": entry.get("sha256"),
            "state_class": entry.get("state_class"),
            "restore_action": "would_validate_path_and_hash_only",
            "content_restored": False,
        }
        for entry in backup_manifest_packet.get("planned_entries", [])
        if isinstance(entry, dict)
    ]
    return _packet(
        "persistent_restore_manifest_schema",
        persistent_profile_id=config.profile_id,
        backup_root=str(_resolved(config.backup_root)),
        restore_target_root=str(_resolved(config.restore_target_root)),
        schema_version="persistent_restore_manifest_dry_run_v1",
        required_entry_fields=[
            "relative_path",
            "kind",
            "size",
            "sha256",
            "state_class",
            "restore_action",
        ],
        planned_entries=planned_entries,
        planned_entry_count=len(planned_entries),
        restore_executed=False,
        restore_execution_allowed=False,
        restored_state_equivalence_proven=False,
        restored_state_equivalence_claimed=False,
        content_restored=False,
        raw_prompt_recorded=False,
        raw_secret_recorded=False,
    )


def build_retention_policy_packet(
    config: PersistentBackupRestoreDryRunConfig,
    *,
    policy: str = "manual_retention_until_owner_delete",
    max_retained_backups: int | None = None,
) -> dict[str, Any]:
    policy_known = policy in RETENTION_POLICIES
    bounded_count_valid = policy != "bounded_count_no_auto_delete_without_owner" or (
        isinstance(max_retained_backups, int) and max_retained_backups > 0
    )
    ok = policy_known and bounded_count_valid
    return _packet(
        "persistent_retention_policy",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_RETENTION_POLICY_UNSAFE",
        persistent_profile_id=config.profile_id,
        policy=policy,
        max_retained_backups=max_retained_backups,
        automatic_delete_allowed=False,
        owner_authorization_required_for_delete=True,
        cleanup_deletes_persistent_history_by_default=False,
        retention_policy_is_history_preservation_proof=False,
    )


def build_destructive_action_guard_packet(
    config: PersistentBackupRestoreDryRunConfig,
) -> dict[str, Any]:
    execution_flags = {
        "backup_execution_allowed": config.backup_execution_allowed,
        "restore_execution_allowed": config.restore_execution_allowed,
        "cleanup_execution_allowed": config.cleanup_execution_allowed,
        "delete_execution_allowed": config.delete_execution_allowed,
    }
    execution_requested = any(execution_flags.values())
    unauthorized_destructive_requested = (
        any(
            execution_flags[key]
            for key in (
                "restore_execution_allowed",
                "cleanup_execution_allowed",
                "delete_execution_allowed",
            )
        )
        and not config.owner_authorized_destructive_action
    )
    ok = not execution_requested and not unauthorized_destructive_requested
    return _packet(
        "persistent_destructive_action_guard",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_DRY_RUN_FORBIDS_EXECUTION",
        owner_authorized_destructive_action=config.owner_authorized_destructive_action,
        execution_flags=execution_flags,
        backup_execution_attempted=False,
        restore_execution_attempted=False,
        cleanup_execution_attempted=False,
        delete_execution_attempted=False,
        destructive_action_performed=False,
        dry_run_only=True,
        owner_authorization_required_for_destructive_restore=True,
        owner_authorization_required_for_delete=True,
    )


def build_original_profile_backup_restore_guard_packet(
    config: PersistentBackupRestoreDryRunConfig,
) -> dict[str, Any]:
    backup_overlaps_original = _original_overlap(config.backup_root, config)
    restore_overlaps_original = _original_overlap(config.restore_target_root, config)
    profile_overlaps_original = _original_overlap(config.persistent_profile_root, config)
    original_used = backup_overlaps_original or restore_overlaps_original or profile_overlaps_original
    return _packet(
        "persistent_original_profile_backup_restore_guard",
        status="blocked" if original_used else "ok",
        reason_class="ORIGINAL_CODEX_PROFILE_USED_AS_BACKUP_RESTORE_SURFACE"
        if original_used
        else "",
        persistent_profile_root=str(_resolved(config.persistent_profile_root)),
        backup_root=str(_resolved(config.backup_root)),
        restore_target_root=str(_resolved(config.restore_target_root)),
        original_surfaces={name: str(_resolved(path)) for name, path in _original_surfaces(config).items()},
        persistent_profile_overlaps_original_codex=profile_overlaps_original,
        backup_root_overlaps_original_codex=backup_overlaps_original,
        restore_target_overlaps_original_codex=restore_overlaps_original,
        original_codex_used_as_source=False,
        original_codex_used_as_target=False,
        original_codex_profile_mutated=False,
        original_codex_runtime_dependency=False,
    )


def build_equivalence_non_claim_packet(
    config: PersistentBackupRestoreDryRunConfig,
) -> dict[str, Any]:
    forbidden = config.rollback_proof_claimed or config.restored_state_equivalence_claimed
    return _packet(
        "persistent_backup_restore_equivalence_non_claim",
        status="blocked" if forbidden else "ok",
        reason_class="PERSISTENT_BACKUP_RESTORE_EQUIVALENCE_OVERCLAIM"
        if forbidden
        else "",
        persistent_profile_id=config.profile_id,
        backup_plan_rendered=True,
        restore_plan_rendered=True,
        backup_created=False,
        restore_executed=False,
        rollback_executed=False,
        rollback_proven=False,
        restored_state_equivalence_proven=False,
        restored_state_equivalence_claimed=config.restored_state_equivalence_claimed,
        path_hash_inventory_is_restorable_backup=False,
        manifest_schema_is_materialized_backup=False,
    )


def build_non_claim_packet(config: PersistentBackupRestoreDryRunConfig) -> dict[str, Any]:
    return _packet(
        "persistent_backup_restore_non_claim",
        persistent_profile_id=config.profile_id,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_input_required=False,
        live_provider_request_attempted=False,
        persistent_profile_state_written=False,
        backup_created=False,
        restore_executed=False,
        cleanup_attempted=False,
        rollback_executed=False,
        rollback_proven=False,
        thread_history_preservation_claimed=False,
        profile_storage_persistence_claimed=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        direct_egress_absence_claimed=False,
        model_availability_claimed=False,
        original_reversibility_proven=False,
        final_e2e_claimed=False,
    )


FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_input_required",
    "live_provider_request_attempted",
    "persistent_profile_state_written",
    "backup_created",
    "restore_executed",
    "cleanup_attempted",
    "rollback_executed",
    "rollback_proven",
    "thread_history_preservation_claimed",
    "profile_storage_persistence_claimed",
    "native_ux_claimed",
    "keychain_behavior_classified",
    "direct_egress_absence_claimed",
    "model_availability_claimed",
    "original_reversibility_proven",
    "final_e2e_claimed",
    "path_hash_inventory_is_restorable_backup",
    "manifest_schema_is_materialized_backup",
    "manifest_materialized_from_real_profile",
    "restored_state_equivalence_proven",
    "content_recorded",
    "content_restored",
    "raw_prompt_recorded",
    "raw_secret_recorded",
    "original_codex_used_as_source",
    "original_codex_used_as_target",
    "original_codex_profile_mutated",
    "original_codex_runtime_dependency",
    "destructive_action_performed",
}


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
    for filename, packet in packets.items():
        findings.extend(f"{filename}.{path}" for path in _scan_forbidden_true(packet))
    required_ok = all(
        packet.get("status") == "ok"
        for packet in packets.values()
        if isinstance(packet, dict)
        and packet.get("packet_kind")
        not in {"persistent_backup_restore_summary"}
    )
    if not required_ok:
        blocked = [
            name for name, packet in packets.items() if packet.get("status") == "blocked"
        ]
        findings.extend(f"{name}.status=blocked" for name in blocked)
    return _packet(
        "persistent_backup_restore_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_true_fields=sorted(FORBIDDEN_TRUE_FIELDS),
        dry_run_truth_required=True,
        text_only_audit_counted_as_pass=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required_packets = {
        "persistent_backup_restore_contract_packet.json",
        "persistent_backup_path_authority_packet.json",
        "persistent_restore_path_authority_packet.json",
        "persistent_backup_manifest_schema_packet.json",
        "persistent_restore_manifest_schema_packet.json",
        "persistent_retention_policy_packet.json",
        "persistent_destructive_action_guard_packet.json",
        "persistent_original_profile_backup_restore_guard_packet.json",
        "persistent_backup_restore_equivalence_non_claim_packet.json",
        "persistent_backup_restore_non_claim_packet.json",
        "persistent_backup_restore_false_green_audit.json",
    }
    missing = sorted(required_packets - set(packets))
    blocked = sorted(
        name
        for name in required_packets & set(packets)
        if packets[name].get("status") != "ok"
    )
    ok = not missing and not blocked
    return _packet(
        "persistent_backup_restore_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "PERSISTENT_BACKUP_RESTORE_DRY_RUN_READINESS_BLOCKED",
        parent_target=PARENT_STATUS,
        parent_target_closed=False,
        this_target_closed=ok,
        missing_required_packets=missing,
        blocked_packets=blocked,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_input_required=False,
        live_provider_request_attempted=False,
        persistent_profile_state_written=False,
        backup_created=False,
        restore_executed=False,
        cleanup_attempted=False,
        rollback_executed=False,
        rollback_proven=False,
        thread_history_preservation_claimed=False,
        profile_storage_persistence_claimed=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        original_reversibility_proven=False,
        final_e2e_claimed=False,
    )


def build_contract_packet(config: PersistentBackupRestoreDryRunConfig) -> dict[str, Any]:
    return _packet(
        "persistent_backup_restore_contract",
        persistent_profile_id=config.profile_id,
        parent_target=PARENT_STATUS,
        target_status=TARGET_STATUS,
        profile_mode="persistent_custom",
        contour_scope="dry_run_backup_restore_readiness_only",
        backup_execution_allowed=False,
        restore_execution_allowed=False,
        cleanup_execution_allowed=False,
        delete_execution_allowed=False,
        real_profile_inventory_allowed=False,
        rollback_proof_claimed=False,
        restored_state_equivalence_claimed=False,
        backup_plan_is_backup_created=False,
        restore_plan_is_restore_executed=False,
        manifest_schema_is_materialized_backup=False,
    )


def build_readiness_packets(
    config: PersistentBackupRestoreDryRunConfig,
) -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    packets["persistent_backup_restore_contract_packet.json"] = build_contract_packet(config)
    packets["persistent_backup_path_authority_packet.json"] = (
        build_backup_path_authority_packet(config)
    )
    packets["persistent_restore_path_authority_packet.json"] = (
        build_restore_path_authority_packet(config)
    )
    packets["persistent_backup_manifest_schema_packet.json"] = (
        build_backup_manifest_schema_packet(config)
    )
    packets["persistent_restore_manifest_schema_packet.json"] = (
        build_restore_manifest_schema_packet(
            config,
            backup_manifest_packet=packets["persistent_backup_manifest_schema_packet.json"],
        )
    )
    packets["persistent_retention_policy_packet.json"] = build_retention_policy_packet(config)
    packets["persistent_destructive_action_guard_packet.json"] = (
        build_destructive_action_guard_packet(config)
    )
    packets["persistent_original_profile_backup_restore_guard_packet.json"] = (
        build_original_profile_backup_restore_guard_packet(config)
    )
    packets["persistent_backup_restore_equivalence_non_claim_packet.json"] = (
        build_equivalence_non_claim_packet(config)
    )
    packets["persistent_backup_restore_non_claim_packet.json"] = build_non_claim_packet(config)
    packets["persistent_backup_restore_false_green_audit.json"] = build_false_green_audit(packets)
    packets["persistent_backup_restore_summary_packet.json"] = build_summary_packet(packets)
    return packets
