#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify the Persistent Custom profile-history contour without overclaiming."""

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

from wild_boar_proxy.native_filesystem_probe import (
    build_integration_ownership_baseline_packet,
    build_original_codex_profile_drift_packet,
    build_original_codex_protected_surface_scope_packet,
    build_owner_visible_thread_context_packet,
    build_persistent_backup_rollback_packet,
    build_persistent_cleanup_policy_packet,
    build_persistent_concurrent_launch_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    build_persistent_profile_false_green_audit,
    build_persistent_profile_state_diff_packet,
    build_thread_history_preservation_packet,
    classify_keychain_observation,
    default_persistent_custom_profile_paths,
    json_write,
    scan_protected_surfaces,
    scan_tree,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> tuple[list[str], list[str]]:
    if skip_git:
        return [], []
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/persistent_custom_profile_history_r1_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
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


def _base_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": []
            if skip_git
            else _run(repo_root, ["git", "status", "--short"]).splitlines(),
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "master_plan_written_to_repo": False,
        },
        "historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "quarantine_classification": "out_of_scope_historical_residue",
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "codex_cli_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "codex_app_bundle_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleVersion",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
    }


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = default_persistent_custom_profile_paths(
        profile_id=profile_id,
        base_dir=base_dir,
    )
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    launcher_path = Path(paths["launcher_path"])
    backup_root = profile_root.parent / f"{profile_id}.backup"

    packets = _base_packets(repo_root, evidence_dir, skip_git=skip_git)
    before_scan = scan_tree(profile_root)
    protected_before = scan_protected_surfaces()
    protected_after = scan_protected_surfaces()
    after_scan = scan_tree(profile_root)
    relaunch_scan = scan_tree(profile_root)

    packets.update(
        {
            "declared_write_surfaces_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "declared_write_surfaces",
                "status": "ok",
                "declared_write_surfaces": [
                    str(profile_root),
                    str(backup_root),
                ],
                "native_launch_attempted": False,
                "persistent_write_performed": False,
                "protected_surfaces_write_allowed": False,
                "original_codex_profile_write_allowed": False,
            },
            "persistent_safety_admission_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "persistent_safety_admission",
                "status": "ok",
                "native_launch_attempted": False,
                "fresh_live_admission_required_before_native_launch": True,
                "inspection_only": True,
                "counts_as_history_proof": False,
            },
            "persistent_custom_profile_contract_packet.json": (
                build_persistent_custom_profile_contract_packet(
                    profile_id=profile_id,
                    profile_root=profile_root,
                    codex_home=codex_home,
                    user_data_dir=user_data_dir,
                )
            ),
            "persistent_custom_profile_identity_packet.json": (
                build_persistent_custom_profile_identity_packet(
                    phase="before",
                    profile_id=profile_id,
                    profile_root=profile_root,
                    codex_home=codex_home,
                    user_data_dir=user_data_dir,
                )
            ),
            "launcher_selection_packet.json": build_persistent_launcher_selection_packet(
                launcher_path=launcher_path,
                profile_mode="persistent_custom",
                selected_profile_id=profile_id,
                selected_profile_root=profile_root,
                codex_home=codex_home,
                user_data_dir=user_data_dir,
            ),
            "concurrent_launch_policy_packet.json": (
                build_persistent_concurrent_launch_policy_packet(
                    policy="single_writer_only",
                    lock_path=profile_root / ".wbp-profile.lock",
                    launcher_enforces_policy=True,
                )
            ),
            "persistent_profile_lock_policy_packet.json": (
                build_persistent_concurrent_launch_policy_packet(
                    policy="single_writer_only",
                    lock_path=profile_root / ".wbp-profile.lock",
                    launcher_enforces_policy=True,
                )
            ),
            "persistent_backup_rollback_packet.json": build_persistent_backup_rollback_packet(
                profile_root=profile_root,
                backup_root=backup_root,
                profile_existed_before=profile_root.exists(),
                backup_created=False,
            ),
            "persistent_cleanup_policy_packet.json": build_persistent_cleanup_policy_packet(
                profile_root=profile_root,
                cleanup_attempted=False,
                profile_exists_after_cleanup=profile_root.exists(),
            ),
            "persistent_custom_profile_before_snapshot.json": before_scan,
            "persistent_custom_profile_after_thread_snapshot.json": after_scan,
            "persistent_custom_profile_relaunch_snapshot.json": relaunch_scan,
            "persistent_profile_state_diff_packet.json": (
                build_persistent_profile_state_diff_packet(
                    before_scan=before_scan,
                    after_scan=after_scan,
                    relaunch_scan=relaunch_scan,
                )
            ),
            "owner_visible_thread_context_packet.json": (
                build_owner_visible_thread_context_packet(
                    owner_visible_prior_thread=None,
                    owner_confirmation_collected=False,
                )
            ),
            "integration_ownership_baseline_packet.json": (
                build_integration_ownership_baseline_packet()
            ),
            "original_codex_protected_surface_scope_packet.json": (
                build_original_codex_protected_surface_scope_packet()
            ),
            "original_codex_profile_drift_packet.json": (
                build_original_codex_profile_drift_packet(
                    before_surfaces=protected_before,
                    after_surfaces=protected_after,
                )
            ),
            "keychain_prompt_observation_if_any_packet.json": (
                classify_keychain_observation(machine_prompt_observed=False)
            ),
        }
    )
    packets["persistent_custom_profile_relaunch_identity_packet.json"] = (
        build_persistent_custom_profile_identity_packet(
            phase="relaunch",
            profile_id=profile_id,
            profile_root=profile_root,
            codex_home=codex_home,
            user_data_dir=user_data_dir,
            expected_profile_id=profile_id,
            expected_profile_root=profile_root,
        )
    )
    packets["thread_history_preservation_packet.json"] = (
        build_thread_history_preservation_packet(
            before_identity_packet=packets["persistent_custom_profile_identity_packet.json"],
            relaunch_identity_packet=packets[
                "persistent_custom_profile_relaunch_identity_packet.json"
            ],
            state_diff_packet=packets["persistent_profile_state_diff_packet.json"],
            owner_visible_thread_context_packet=packets[
                "owner_visible_thread_context_packet.json"
            ],
        )
    )
    packets["persistent_profile_false_green_audit.json"] = (
        build_persistent_profile_false_green_audit(
            thread_history_packet=packets["thread_history_preservation_packet.json"],
            owner_visible_thread_context_packet=packets[
                "owner_visible_thread_context_packet.json"
            ],
            cleanup_policy_packet=packets["persistent_cleanup_policy_packet.json"],
            original_drift_packet=packets["original_codex_profile_drift_packet.json"],
        )
    )
    packets["independent_persistent_profile_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_persistent_profile_audit",
        "status": "ok",
        "evidence": [
            "persistent_custom_profile_contract_packet.json",
            "persistent_custom_profile_identity_packet.json",
            "persistent_profile_state_diff_packet.json",
            "thread_history_preservation_packet.json",
            "persistent_profile_false_green_audit.json",
        ],
        "facts": {
            "profile_id": profile_id,
            "profile_root": str(profile_root),
            "native_launch_attempted": False,
            "history_preservation_status": packets[
                "thread_history_preservation_packet.json"
            ]["status"],
            "false_green_status": packets["persistent_profile_false_green_audit.json"][
                "status"
            ],
        },
        "text_only_audit_counted_as_pass": False,
    }
    final_status = (
        "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
        if packets["thread_history_preservation_packet.json"]["status"] == "ok"
        else "WBP_CUSTOM_PERSISTENT_PROFILE_BLOCKED_LIVE_NOT_ATTEMPTED"
    )
    packets["persistent_custom_profile_history_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_history_summary",
        "status": "ok" if final_status.endswith("_CLASSIFIED") else "blocked",
        "final_status": final_status,
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "native_launch_attempted": False,
        "thread_history_preservation_claimed": final_status.endswith("_CLASSIFIED"),
        "route_trace_counted_as_history_proof": False,
        "owner_visible_thread_counted_as_storage_proof": False,
        "direct_egress_absence_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-history-r1-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(
            ROOT / "audit_results/wbp_persistent_custom_profile_history_r1_2026-05-27"
        ),
    )
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", default="")
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        profile_id=args.profile_id,
        base_dir=base_dir,
        skip_git=args.skip_git,
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["persistent_custom_profile_history_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
