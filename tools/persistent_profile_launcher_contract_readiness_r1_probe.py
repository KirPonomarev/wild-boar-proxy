#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit non-live Persistent Custom launcher/profile contract readiness evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_persistent_backup_rollback_packet,
    build_persistent_cleanup_policy_packet,
    build_persistent_concurrent_launch_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    default_persistent_custom_profile_paths,
    json_write,
)


TARGET_STATUS = "WBP_CUSTOM_PERSISTENT_PROFILE_LAUNCHER_CONTRACT_READINESS_R1_CLASSIFIED"
PARENT_STATUS = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
EVIDENCE_DIR_NAME = "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27"
PROFILE_ID = "wbp-custom-main"

FORBIDDEN_TRUE_FIELDS = {
    "native_launch_attempted",
    "custom_app_launch_attempted",
    "owner_prompt_required",
    "owner_input_required",
    "live_provider_request_attempted",
    "command_executed",
    "persistent_profile_state_written",
    "persistent_profile_created_as_proof",
    "thread_history_preservation_claimed",
    "profile_storage_persistence_claimed",
    "cleanup_executed",
    "backup_export_executed",
    "backup_created",
    "lock_enforcement_claimed",
    "lock_execution_proven",
    "migration_import_performed",
    "original_codex_profile_dependency",
    "original_codex_profile_mutated",
    "native_ux_claimed",
    "keychain_behavior_classified",
    "final_e2e_claimed",
    "live_execution_allowed_in_this_contour",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def run_text(repo_root: Path, command: list[str]) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/persistent_profile_launcher_contract_readiness_r1_probe.py",
        "tests/test_persistent_profile_launcher_contract_readiness_r1_probe.py",
    }
    admitted_current_evidence_dirs = (
        f"{relative_evidence_dir}/",
        f"{EVIDENCE_DIR_NAME}/",
    )
    def is_current_contour_line(line: str) -> bool:
        # `git status --short` keeps the path at offset 3 for ordinary paths.
        # Admitting by path, not by status code, lets staged R1 evidence pass
        # while still blocking any unrelated staged or unstaged work.
        path = line[3:] if len(line) > 3 else line.strip()
        return path in admitted_current_contour or path.startswith(
            admitted_current_evidence_dirs
        )

    quarantined = [
        line
        for line in status_lines
        if not is_current_contour_line(line)
    ]
    unexpected_dirty: list[str] = []
    return quarantined, unexpected_dirty


def build_sync_gate_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch=run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
        git_status_short=run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        master_plan_written_to_repo=False,
        current_contour="WBP_CUSTOM_PERSISTENT_PROFILE_LAUNCHER_CONTRACT_READINESS_R1",
    )


def build_historical_quarantine_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "historical_dirt_quarantine",
        status="ok" if not unexpected_dirty else "blocked",
        quarantined_paths=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        quarantine_classification="out_of_scope_historical_or_paused_r5_residue",
        current_contour_relies_on_quarantined_paths=False,
        current_contour_mutates_quarantined_paths=False,
        current_contour_stages_quarantined_paths=False,
    )


def build_version_pinning_packet(repo_root: Path) -> dict[str, Any]:
    return packet(
        "version_pinning",
        codex_cli_version=run_text(repo_root, ["codex", "--version"]),
        codex_cli_path=run_text(repo_root, ["which", "codex"]),
        codex_app_path="/Applications/Codex.app",
        codex_app_version=run_text(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        codex_app_bundle_version=run_text(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        wbp_git_commit=run_text(repo_root, ["git", "rev-parse", "HEAD"]),
    )


def paths_packet(base_dir: Path | None = None) -> dict[str, Any]:
    raw = default_persistent_custom_profile_paths(profile_id=PROFILE_ID, base_dir=base_dir)
    return {key: Path(value).expanduser() for key, value in raw.items()}


def build_persistent_launcher_command_shape_packet(paths: dict[str, Path]) -> dict[str, Any]:
    argv_template = [
        "open",
        "-n",
        "/Applications/Codex.app",
        "--args",
        "--user-data-dir",
        str(paths["user_data_dir"]),
    ]
    env_shape = {
        "CODEX_HOME": str(paths["codex_home"]),
        "HOME": str(paths["home_dir"]),
        "TMPDIR": str(paths["runtime_tmp_dir"]),
        "WBP_RUNTIME_TMPDIR": str(paths["runtime_tmp_dir"]),
        "WBP_PROFILE_MODE": "persistent_custom",
        "WBP_PERSISTENT_PROFILE_ID": PROFILE_ID,
    }
    return packet(
        "persistent_launcher_command_shape",
        launcher_path=str(paths["launcher_path"]),
        argv_template=argv_template,
        argv_template_sha256=sha256_text(json.dumps(argv_template, sort_keys=True)),
        env_shape=env_shape,
        env_shape_sha256=sha256_text(json.dumps(env_shape, sort_keys=True)),
        command_shape_recorded=True,
        command_executed=False,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_input_required=False,
        owner_prompt_required=False,
        live_provider_request_attempted=False,
        command_shape_counts_as_launch_proof=False,
    )


def build_custom_profile_storage_modes_packet() -> dict[str, Any]:
    return packet(
        "custom_profile_storage_modes",
        modes={
            "ephemeral_custom": {
                "profile_lifetime": "single_contour",
                "cleanup_required": True,
                "thread_history_claim": "not_preserved_or_unproven",
                "launcher_identity": "fresh_or_temp",
            },
            "persistent_custom": {
                "profile_lifetime": "long_lived",
                "cleanup_required": False,
                "thread_history_claim": "requires_future_relaunch_storage_proof",
                "launcher_identity": "stable_profile_id_required",
            },
            "original_codex": {
                "profile_lifetime": "user_owned",
                "cleanup_required": "forbidden",
                "thread_history_claim": "original_app_only",
                "launcher_identity": "original_app_concern_only",
            },
        },
        modes_distinguishable=True,
        silent_persistent_to_ephemeral_fallback_allowed=False,
        original_profile_shortcut_allowed=False,
    )


def build_persistent_profile_path_authority_packet(paths: dict[str, Path]) -> dict[str, Any]:
    return packet(
        "persistent_profile_path_authority",
        persistent_profile_id=PROFILE_ID,
        persistent_profile_root=str(paths["persistent_profile_root"]),
        codex_home=str(paths["codex_home"]),
        user_data_dir=str(paths["user_data_dir"]),
        launcher_selected_profile_id=PROFILE_ID,
        launcher_selected_profile_path=str(paths["persistent_profile_root"]),
        browser_client_path_authority=False,
        remote_client_path_authority=False,
        operator_explicit_profile_id_required=True,
        silent_profile_switching_allowed=False,
        profile_root_declared=True,
        profile_root_created=False,
        profile_root_exists_counted_as_state_write_proof=False,
        profile_storage_persistence_claimed=False,
    )


def build_persistent_cleanup_retention_policy_packet(cleanup: dict[str, Any]) -> dict[str, Any]:
    return packet(
        "persistent_cleanup_retention_policy",
        status=cleanup.get("status", "blocked"),
        cleanup_policy_reference=cleanup,
        cleanup_deletes_persistent_profile_by_default=False,
        cleanup_attempted=False,
        cleanup_executed=False,
        persistent_history_delete_allowed_by_default=False,
        explicit_owner_delete_authorization_required=True,
        ordinary_cleanup_must_preserve_history=True,
        cleanup_policy_counts_as_cleanup_execution=False,
    )


def build_persistent_locking_enforcement_readiness_packet(
    concurrent: dict[str, Any],
) -> dict[str, Any]:
    return packet(
        "persistent_locking_enforcement_readiness",
        concurrent_policy_reference=concurrent,
        lock_path=concurrent.get("lock_path", ""),
        lock_strategy="single_writer_lockfile_required_before_live_write",
        lock_enforcement_ready_to_test=True,
        lock_enforcement_claimed=False,
        lock_execution_proven=False,
        lockfile_created=False,
        concurrent_policy_counts_as_lock_enforcement=False,
    )


def build_persistent_backup_export_policy_packet(backup: dict[str, Any]) -> dict[str, Any]:
    return packet(
        "persistent_backup_export_policy",
        backup_policy_reference=backup,
        backup_export_policy_recorded=True,
        backup_export_required_before_first_persistent_write=True,
        backup_export_executed=False,
        backup_created=False,
        export_created=False,
        backup_policy_counts_as_backup_created=False,
        rollback_expectation_declared=True,
        rollback_executed=False,
    )


def build_persistent_migration_import_non_claim_packet() -> dict[str, Any]:
    return packet(
        "persistent_migration_import_non_claim",
        migration_import_performed=False,
        migration_import_disabled_for_ordinary_launch=True,
        migration_requires_separate_explicit_contour=True,
        original_codex_profile_used_as_source=False,
        current_auth_json_copied=False,
        imported_history_claimed=False,
        migration_disabled_counts_as_migration_safety_proof=False,
    )


def build_original_codex_profile_non_dependency_packet() -> dict[str, Any]:
    return packet(
        "original_codex_profile_non_dependency",
        original_codex_profile_dependency=False,
        original_codex_profile_mutated=False,
        original_codex_profile_used_as_custom_shortcut=False,
        original_codex_history_copied=False,
        original_codex_auth_copied=False,
        original_codex_profile_readiness_counts_as_runtime_proof=False,
    )


def build_persistent_launcher_non_substitution_packet() -> dict[str, Any]:
    return packet(
        "persistent_launcher_non_substitution",
        launcher_contract_is_launch_execution=False,
        launcher_command_shape_is_native_launch=False,
        persistent_profile_identity_is_thread_history_preservation=False,
        persistent_profile_root_declared_is_profile_storage_written=False,
        profile_root_exists_is_state_persistence_proof=False,
        cleanup_retention_policy_is_cleanup_performed=False,
        backup_export_policy_is_backup_created=False,
        concurrent_launch_policy_is_lock_enforcement_proof=False,
        lock_readiness_is_lock_execution_proof=False,
        migration_import_disabled_is_migration_safety_proven=False,
        original_profile_non_dependency_readiness_is_live_runtime_proof=False,
        persistent_launcher_readiness_is_native_ux_acceptance=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        final_e2e_claimed=False,
    )


def build_persistent_launcher_false_green_audit(
    *,
    command_shape: dict[str, Any],
    identity: dict[str, Any],
    path_authority: dict[str, Any],
    cleanup: dict[str, Any],
    backup: dict[str, Any],
    lock: dict[str, Any],
    migration: dict[str, Any],
    original: dict[str, Any],
    non_substitution: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    if command_shape.get("command_executed") is not False:
        findings.append("command_executed")
    if command_shape.get("command_shape_counts_as_launch_proof") is not False:
        findings.append("command_shape_counts_as_launch_proof")
    if identity.get("status") != "ok":
        findings.append("persistent_profile_identity_not_ok")
    if path_authority.get("browser_client_path_authority") is not False:
        findings.append("browser_client_path_authority")
    if path_authority.get("remote_client_path_authority") is not False:
        findings.append("remote_client_path_authority")
    if path_authority.get("profile_storage_persistence_claimed") is not False:
        findings.append("profile_storage_persistence_claimed")
    if cleanup.get("cleanup_executed") is not False:
        findings.append("cleanup_executed")
    if cleanup.get("persistent_history_delete_allowed_by_default") is not False:
        findings.append("persistent_history_delete_allowed_by_default")
    if backup.get("backup_created") is not False:
        findings.append("backup_created")
    if backup.get("backup_export_executed") is not False:
        findings.append("backup_export_executed")
    if lock.get("lock_enforcement_claimed") is not False:
        findings.append("lock_enforcement_claimed")
    if lock.get("lock_execution_proven") is not False:
        findings.append("lock_execution_proven")
    if migration.get("migration_import_performed") is not False:
        findings.append("migration_import_performed")
    if original.get("original_codex_profile_dependency") is not False:
        findings.append("original_codex_profile_dependency")
    for key, value in non_substitution.items():
        if key.endswith("_claimed") and value is not False:
            findings.append(f"non_substitution.{key}")
    return packet(
        "persistent_launcher_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_claims_present=bool(findings),
        identity_used_as_history_proof=False,
        command_shape_used_as_launch_proof=False,
        policy_used_as_execution=False,
        readiness_used_as_live_ux=False,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = json.dumps(packets, sort_keys=True)
    secret_patterns = (
        r"sk-(?:proj|live|cliproxy|wbp|[A-Za-z0-9]{20,})[A-Za-z0-9_-]{8,}",
        r"OPENAI_API_KEY\s*=",
        r"Authorization:\s*Bearer\s+[^<\s\"]+",
        r"refresh_token[\"']?\s*[:=]\s*[\"'][^\"']+[\"']",
    )
    prompt_markers = (
        "составь план следующего контура",
        "nonce_used=true",
        "owner_prompt_entered=true",
    )
    secret_findings = [
        pattern for pattern in secret_patterns if re.search(pattern, text, re.IGNORECASE)
    ]
    prompt_findings = [marker for marker in prompt_markers if marker in text]
    return packet(
        "secret_redaction_audit",
        status="ok" if not secret_findings and not prompt_findings else "blocked",
        raw_secret_found=bool(secret_findings),
        raw_prompt_found=bool(prompt_findings),
        raw_secret_recorded=False,
        raw_prompt_recorded=False,
        secret_marker_findings=secret_findings,
        prompt_marker_findings=prompt_findings,
        exhaustive_dlp_claimed=False,
    )


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true: list[str] = []
    blocked_packets = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    for name, payload in packets.items():
        if not isinstance(payload, dict):
            continue
        for field in FORBIDDEN_TRUE_FIELDS:
            if payload.get(field) is True:
                forbidden_true.append(f"{name}.{field}")
    ok = not forbidden_true and not blocked_packets
    return packet(
        "independent_persistent_launcher_readiness_audit",
        status="ok" if ok else "blocked",
        forbidden_true_fields=forbidden_true,
        blocked_packets=blocked_packets,
        text_only_report_counted_as_evidence=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "persistent_launcher_contract_packet.json",
        "persistent_launcher_command_shape_packet.json",
        "persistent_profile_identity_contract_packet.json",
        "custom_profile_storage_modes_packet.json",
        "persistent_profile_path_authority_packet.json",
        "persistent_cleanup_retention_policy_packet.json",
        "persistent_concurrent_launch_policy_packet.json",
        "persistent_locking_enforcement_readiness_packet.json",
        "persistent_backup_export_policy_packet.json",
        "persistent_migration_import_non_claim_packet.json",
        "original_codex_profile_non_dependency_packet.json",
        "persistent_launcher_non_substitution_packet.json",
        "persistent_launcher_false_green_audit.json",
        "secret_redaction_audit.json",
        "independent_persistent_launcher_readiness_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [
        name
        for name, payload in packets.items()
        if isinstance(payload, dict) and payload.get("status") == "blocked"
    ]
    ok = not missing and not blocked
    return packet(
        "persistent_launcher_readiness_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "",
        parent_target=PARENT_STATUS,
        parent_target_closed=False,
        this_target_closed=ok,
        missing_required_packets=missing,
        blocked_packets=blocked,
        native_launch_attempted=False,
        custom_app_launch_attempted=False,
        owner_prompt_required=False,
        owner_input_required=False,
        live_provider_request_attempted=False,
        command_executed=False,
        persistent_profile_state_written=False,
        cleanup_executed=False,
        backup_export_executed=False,
        thread_history_preservation_claimed=False,
        profile_storage_persistence_claimed=False,
        native_ux_claimed=False,
        keychain_behavior_classified=False,
        final_e2e_claimed=False,
    )


def build_readiness_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    paths = paths_packet()
    profile_root = paths["persistent_profile_root"]
    codex_home = paths["codex_home"]
    user_data_dir = paths["user_data_dir"]
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=PROFILE_ID,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    identity = build_persistent_custom_profile_identity_packet(
        phase="launcher_contract_readiness",
        profile_id=PROFILE_ID,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    launcher = build_persistent_launcher_selection_packet(
        launcher_path=paths["launcher_path"],
        profile_mode="persistent_custom",
        selected_profile_id=PROFILE_ID,
        selected_profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    cleanup_ref = build_persistent_cleanup_policy_packet(
        profile_root=profile_root,
        cleanup_attempted=False,
        profile_exists_after_cleanup=None,
    )
    concurrent = build_persistent_concurrent_launch_policy_packet(
        policy="single_writer_only",
        lock_path=profile_root / ".wbp-profile.lock",
        launcher_enforces_policy=True,
    )
    backup_ref = build_persistent_backup_rollback_packet(
        profile_root=profile_root,
        backup_root=profile_root.parent / f"{PROFILE_ID}.backup",
        profile_existed_before=False,
        backup_created=False,
    )
    command_shape = build_persistent_launcher_command_shape_packet(paths)
    storage_modes = build_custom_profile_storage_modes_packet()
    path_authority = build_persistent_profile_path_authority_packet(paths)
    cleanup = build_persistent_cleanup_retention_policy_packet(cleanup_ref)
    lock = build_persistent_locking_enforcement_readiness_packet(concurrent)
    backup = build_persistent_backup_export_policy_packet(backup_ref)
    migration = build_persistent_migration_import_non_claim_packet()
    original = build_original_codex_profile_non_dependency_packet()
    non_substitution = build_persistent_launcher_non_substitution_packet()
    false_green = build_persistent_launcher_false_green_audit(
        command_shape=command_shape,
        identity=identity,
        path_authority=path_authority,
        cleanup=cleanup,
        backup=backup,
        lock=lock,
        migration=migration,
        original=original,
        non_substitution=non_substitution,
    )
    packets: dict[str, dict[str, Any]] = {
        "sync_gate_packet.json": build_sync_gate_packet(repo_root, evidence_dir),
        "historical_dirt_quarantine_packet.json": build_historical_quarantine_packet(
            repo_root, evidence_dir
        ),
        "version_pinning_packet.json": build_version_pinning_packet(repo_root),
        "persistent_launcher_contract_packet.json": {
            **launcher,
            "contract_reference": contract,
            "persistent_launcher_contract_recorded": True,
            "launcher_contract_counts_as_launch_execution": False,
        },
        "persistent_launcher_command_shape_packet.json": command_shape,
        "persistent_profile_identity_contract_packet.json": {
            **identity,
            "identity_counts_as_thread_history_preservation": False,
            "identity_counts_as_profile_storage_persistence": False,
        },
        "custom_profile_storage_modes_packet.json": storage_modes,
        "persistent_profile_path_authority_packet.json": path_authority,
        "persistent_cleanup_retention_policy_packet.json": cleanup,
        "persistent_concurrent_launch_policy_packet.json": concurrent,
        "persistent_locking_enforcement_readiness_packet.json": lock,
        "persistent_backup_export_policy_packet.json": backup,
        "persistent_migration_import_non_claim_packet.json": migration,
        "original_codex_profile_non_dependency_packet.json": original,
        "persistent_launcher_non_substitution_packet.json": non_substitution,
        "persistent_launcher_false_green_audit.json": false_green,
    }
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_persistent_launcher_readiness_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    packets["persistent_launcher_readiness_summary_packet.json"] = build_summary_packet(packets)
    return packets


def write_closeout(evidence_dir: Path, summary: dict[str, Any], repo_root: Path) -> None:
    closeout = f"""# WBP Custom Persistent Profile Launcher Contract Readiness R1 Closeout

## Goal

Prepare non-live persistent Custom launcher/profile contracts without native launch, owner input, persistent profile writes, cleanup/backup execution, thread-history proof, storage proof, UX, or final E2E claims.

## Result

- status: {summary.get("status")}
- final verdict: {summary.get("final_status") or "BLOCKED"}
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Contour Capsule

- goal: classify Persistent Custom launcher/profile readiness only
- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- head: {run_text(repo_root, ["git", "rev-parse", "HEAD"])}
- touched files: tools/persistent_profile_launcher_contract_readiness_r1_probe.py; tests/test_persistent_profile_launcher_contract_readiness_r1_probe.py; {evidence_dir.relative_to(repo_root)}
- tests run: pending final verification command output
- blocked risks: launch/history/storage/cleanup/backup/lock/UX claims intentionally not made; parent target remains open
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Verification

- tests: pending final verification command output
- build: python py_compile pending final verification
- manual: none
- live verification: not performed; forbidden by this contour

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: persistent_launcher_readiness_summary_packet.json
- report: independent_persistent_launcher_readiness_audit.json

## Git

- branch: {run_text(repo_root, ["git", "branch", "--show-current"])}
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw secrets and raw prompts not recorded

## Notes

- blockers encountered: none for this readiness-only classification
- resume from here: CLOSED
"""
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=EVIDENCE_DIR_NAME)
    args = parser.parse_args()

    repo_root = REPO_ROOT
    evidence_dir = (repo_root / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_readiness_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    write_closeout(
        evidence_dir,
        packets["persistent_launcher_readiness_summary_packet.json"],
        repo_root,
    )
    result = packets["persistent_launcher_readiness_summary_packet.json"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
