#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create a selective Persistent Custom profile state backup without live launch."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_original_codex_profile_drift_packet,
    build_original_codex_protected_surface_scope_packet,
    default_persistent_custom_profile_paths,
    json_write,
    scan_protected_surfaces,
)


VOLATILE_DIR_NAMES = {
    ".cache",
    ".tmp",
    "tmp",
    "temp",
    "cache",
    "cachedata",
    "code cache",
    "gpucache",
    "dawncache",
    "shadercache",
    "blob_storage",
    "crashpad",
    "logs",
}
VOLATILE_PATH_TOKENS = {
    ".cache/codex-runtimes",
    "codex-runtime-install-",
    "node_modules",
    ".pnpm",
    "electron-user-data/cache",
    "electron-user-data/gpucache",
    "electron-user-data/code cache",
}
SECRET_FILE_NAMES = {
    "auth.json",
    ".env",
    ".env.local",
}
SECRET_TEXT_MARKERS = (
    "OPENAI_API_KEY",
    "experimental_bearer_token",
    "access_token",
    "refresh_token",
    "secret-key",
)
STATE_ROOT_NAMES = {
    "sessions",
    "memories",
    "sqlite",
    "plugins",
    "skills",
    "vendor_imports",
    "computer-use",
    "shell_snapshots",
}
STATE_FILE_NAMES = {
    ".codex-global-state.json",
    ".codex-global-state.json.bak",
    ".personality_migration",
    "installation_id",
    "session_index.jsonl",
    "config.toml",
}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path: Path, root: Path) -> str:
    return "." if path == root else str(path.relative_to(root))


def _parts_lower(relative_path: str) -> list[str]:
    return [part.lower() for part in Path(relative_path).parts]


def classify_backup_surface(relative_path: str, *, is_dir: bool = False) -> dict[str, Any]:
    parts = _parts_lower(relative_path)
    normalized = relative_path.replace(os.sep, "/").lower()
    name = parts[-1] if parts else "."
    if relative_path == ".":
        return {
            "decision": "copy",
            "surface_class": "profile_root",
            "reason": "root_metadata",
        }
    if name in SECRET_FILE_NAMES or name.endswith(".pem") or name.endswith(".key"):
        return {
            "decision": "exclude",
            "surface_class": "secret_or_auth_surface",
            "reason": "secret_named_surface",
        }
    if any(part in VOLATILE_DIR_NAMES for part in parts) or any(
        token in normalized for token in VOLATILE_PATH_TOKENS
    ):
        return {
            "decision": "exclude",
            "surface_class": "cache_or_incidental_state",
            "reason": "volatile_cache_or_runtime_dependency",
        }
    if name in STATE_FILE_NAMES:
        return {
            "decision": "copy",
            "surface_class": "provider_wbp_linkage_state"
            if name == "config.toml"
            else "session_state",
            "reason": "known_state_file",
        }
    if parts and parts[0] == "sessions":
        return {
            "decision": "copy",
            "surface_class": "thread_history",
            "reason": "session_tree",
        }
    if parts and parts[0] in STATE_ROOT_NAMES:
        return {
            "decision": "copy",
            "surface_class": "integration_state_unclassified",
            "reason": "known_state_tree",
        }
    if name.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm", ".jsonl")):
        return {
            "decision": "copy",
            "surface_class": "session_state",
            "reason": "state_database_or_index",
        }
    if is_dir:
        return {
            "decision": "copy",
            "surface_class": "unclassified_profile_state",
            "reason": "directory_container",
        }
    return {
        "decision": "copy",
        "surface_class": "unclassified_profile_state",
        "reason": "default_state_copy",
    }


def _file_has_secret_marker(path: Path, *, max_bytes: int = 65536) -> bool:
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return False
    text = data.decode("utf-8", errors="ignore")
    return any(marker in text for marker in SECRET_TEXT_MARKERS)


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/persistent_custom_profile_backup_repair_r1_probe.py",
        "tests/test_native_filesystem_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
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


def _compact_tree_inspection(root: Path) -> dict[str, Any]:
    counts = {"files": 0, "dirs": 0, "symlinks": 0, "other": 0}
    total_bytes = 0
    top_level: list[str] = []
    if root.exists():
        top_level = sorted(child.name for child in root.iterdir())[:80]
        for path in root.rglob("*"):
            try:
                if path.is_symlink():
                    counts["symlinks"] += 1
                elif path.is_file():
                    counts["files"] += 1
                    total_bytes += path.stat().st_size
                elif path.is_dir():
                    counts["dirs"] += 1
                else:
                    counts["other"] += 1
            except OSError:
                counts["other"] += 1
    return {
        "captured_at_utc": _utc_now(),
        "root": str(root),
        "exists": root.exists(),
        "complete_marker_present": (root / ".wbp_backup_complete").exists(),
        "counts": counts,
        "total_file_bytes": total_bytes,
        "top_level_names": top_level,
        "raw_content_recorded": False,
    }


def _copy_selective_state(profile_root: Path, backup_root: Path) -> dict[str, Any]:
    copied: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    state_classes: set[str] = set()
    exclusion_classes: set[str] = set()
    backup_root.mkdir(parents=True, exist_ok=False)

    for source in sorted([profile_root, *profile_root.rglob("*")], key=lambda item: str(item)):
        relative_path = _safe_relative(source, profile_root)
        try:
            is_dir = source.is_dir()
            is_file = source.is_file()
            is_symlink = source.is_symlink()
        except OSError as exc:
            failures.append(
                {
                    "relative_path": relative_path,
                    "error_class": type(exc).__name__,
                    "stage": "stat",
                }
            )
            continue
        classification = classify_backup_surface(relative_path, is_dir=is_dir)
        if is_symlink:
            classification = {
                "decision": "exclude",
                "surface_class": "volatile_runtime_dependency",
                "reason": "symlink_not_required_for_state_backup",
            }
        if is_file and classification["decision"] == "copy" and _file_has_secret_marker(source):
            classification = {
                "decision": "exclude",
                "surface_class": "secret_or_auth_surface",
                "reason": "secret_marker_detected_without_recording_value",
            }
        target = backup_root / relative_path
        if classification["decision"] == "exclude":
            exclusion_classes.add(classification["surface_class"])
            excluded.append(
                {
                    "relative_path": relative_path,
                    "kind": "dir" if is_dir else "file" if is_file else "other",
                    **classification,
                    "raw_content_recorded": False,
                }
            )
            continue
        state_classes.add(classification["surface_class"])
        try:
            if is_dir:
                target.mkdir(parents=True, exist_ok=True)
                copied.append(
                    {
                        "relative_path": relative_path,
                        "kind": "dir",
                        **classification,
                    }
                )
            elif is_file:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target, follow_symlinks=False)
                copied.append(
                    {
                        "relative_path": relative_path,
                        "kind": "file",
                        "size": source.stat().st_size,
                        "sha256": _sha256(source),
                        **classification,
                    }
                )
        except OSError as exc:
            failures.append(
                {
                    "relative_path": relative_path,
                    "error_class": type(exc).__name__,
                    "stage": "copy",
                    "surface_class": classification["surface_class"],
                }
            )
    return {
        "copied": copied,
        "excluded": excluded,
        "failures": failures,
        "state_classes": sorted(state_classes),
        "exclusion_classes": sorted(exclusion_classes),
    }


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    findings = [marker for marker in SECRET_TEXT_MARKERS if marker in serialized]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "backup_repair_secret_redaction_audit",
        "status": "blocked" if findings else "ok",
        "raw_secret_found": bool(findings),
        "secret_marker_findings": findings,
        "raw_prompt_recorded": False,
        "raw_auth_recorded": False,
        "raw_session_body_recorded": False,
    }


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, dict[str, Any]]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    existing_backup_root = profile_root.parent / f"{profile_id}.backup"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    timestamped_backup_root = profile_root.parent / f"{profile_id}.backup.{timestamp}"
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)

    protected_before = scan_protected_surfaces()
    packets: dict[str, dict[str, Any]] = {
        "backup_repair_sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "backup_repair_sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": _run(repo_root, ["git", "status", "--short"]).splitlines(),
            "unexpected_dirty_entries": unexpected_dirty,
            "master_plan_written_to_repo": False,
        },
        "backup_repair_historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "backup_repair_historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "backup_repair_version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "backup_repair_version_pinning",
            "status": "ok",
            "codex_cli_version": _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "codex_app_bundle_version": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleVersion",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
        "persistent_profile_root_inspection_packet.json": _compact_tree_inspection(profile_root),
        "existing_backup_root_inspection_packet.json": _compact_tree_inspection(existing_backup_root),
        "incomplete_backup_classification_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "incomplete_backup_classification",
            "status": "ok",
            "existing_backup_root": str(existing_backup_root),
            "existing_backup_present": existing_backup_root.exists(),
            "existing_backup_complete_marker_present": (
                existing_backup_root / ".wbp_backup_complete"
            ).exists(),
            "existing_backup_authoritative": (
                existing_backup_root.exists()
                and (existing_backup_root / ".wbp_backup_complete").exists()
            ),
            "existing_backup_deleted": False,
            "existing_backup_counted_as_rollback_proof": False,
        },
        "backup_repair_policy_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "backup_repair_policy",
            "status": "ok",
            "policy": "timestamped_selective_state_backup",
            "persistent_profile_deletion_allowed": False,
            "incomplete_backup_deletion_allowed": False,
            "volatile_cache_exclusion_allowed": True,
            "native_launch_allowed": False,
            "raw_content_recording_allowed": False,
        },
        "backup_surface_classification_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "backup_surface_classification",
            "status": "ok",
            "copied_classes": [
                "thread_history",
                "session_state",
                "provider_wbp_linkage_state",
                "integration_state_unclassified",
                "unclassified_profile_state",
            ],
            "excluded_classes": [
                "cache_or_incidental_state",
                "volatile_runtime_dependency",
                "secret_or_auth_surface",
            ],
        },
        "original_codex_protected_surface_scope_packet.json": (
            build_original_codex_protected_surface_scope_packet()
        ),
    }

    copy_result = (
        _copy_selective_state(profile_root, timestamped_backup_root)
        if profile_root.exists() and packets["backup_repair_sync_gate_packet.json"]["status"] == "ok"
        else {"copied": [], "excluded": [], "failures": [], "state_classes": [], "exclusion_classes": []}
    )
    copied_files = [entry for entry in copy_result["copied"] if entry["kind"] == "file"]
    copied_dirs = [entry for entry in copy_result["copied"] if entry["kind"] == "dir"]
    excluded_entries = copy_result["excluded"]
    state_backup_ok = profile_root.exists() and bool(copied_files) and not copy_result["failures"]
    marker_path = timestamped_backup_root / ".wbp_backup_complete"
    if state_backup_ok:
        marker_payload = {
            "created_at_utc": _utc_now(),
            "profile_id": profile_id,
            "backup_scope": "selective_state_backup",
        }
        marker_path.write_text(json.dumps(marker_payload, sort_keys=True) + "\n", encoding="utf-8")

    protected_after = scan_protected_surfaces()
    packets.update(
        {
            "state_backup_manifest_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "state_backup_manifest",
                "status": "ok" if state_backup_ok else "blocked",
                "reason_class": "" if state_backup_ok else "STATE_BACKUP_COPY_FAILED",
                "backup_root": str(timestamped_backup_root),
                "copied_file_count": len(copied_files),
                "copied_dir_count": len(copied_dirs),
                "copied_state_classes": copy_result["state_classes"],
                "copied_files": copied_files,
                "copy_failures": copy_result["failures"],
                "raw_content_recorded": False,
            },
            "cache_exclusion_manifest_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "cache_exclusion_manifest",
                "status": "ok" if excluded_entries else "blocked",
                "reason_class": "" if excluded_entries else "CACHE_EXCLUSION_NOT_RECORDED",
                "excluded_count": len(excluded_entries),
                "excluded_classes": copy_result["exclusion_classes"],
                "excluded_entries": excluded_entries[:500],
                "excluded_entries_truncated": len(excluded_entries) > 500,
                "cache_excluded": bool(excluded_entries),
                "raw_content_recorded": False,
            },
            "timestamped_backup_manifest_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "timestamped_backup_manifest",
                "status": "ok" if state_backup_ok else "blocked",
                "profile_id": profile_id,
                "source_profile_root": str(profile_root),
                "timestamped_backup_root": str(timestamped_backup_root),
                "existing_incomplete_backup_root": str(existing_backup_root),
                "existing_incomplete_backup_preserved": existing_backup_root.exists(),
                "manifest_records_hashes_only": True,
            },
            "timestamped_backup_complete_marker_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "timestamped_backup_complete_marker",
                "status": "ok" if marker_path.exists() else "blocked",
                "marker_path": str(marker_path),
                "complete_marker_created": marker_path.exists(),
                "complete_marker_created_after_manifest_success": state_backup_ok,
            },
            "persistent_profile_after_backup_snapshot.json": _compact_tree_inspection(profile_root),
            "original_codex_drift_packet.json": build_original_codex_profile_drift_packet(
                before_surfaces=protected_before,
                after_surfaces=protected_after,
            ),
        }
    )
    rollback_ready = (
        packets["state_backup_manifest_packet.json"]["status"] == "ok"
        and packets["cache_exclusion_manifest_packet.json"]["status"] == "ok"
        and packets["timestamped_backup_complete_marker_packet.json"]["status"] == "ok"
        and packets["original_codex_drift_packet.json"].get("original_codex_write_performed_by_contour")
        is False
    )
    packets["rollback_readiness_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "rollback_readiness",
        "status": "ok" if rollback_ready else "blocked",
        "rollback_ready": rollback_ready,
        "state_backup": packets["state_backup_manifest_packet.json"]["status"] == "ok",
        "cache_excluded": packets["cache_exclusion_manifest_packet.json"]["status"] == "ok",
        "existing_incomplete_backup_counted": False,
        "original_codex_drift_classified": True,
        "original_codex_write_performed_by_contour": packets["original_codex_drift_packet.json"].get(
            "original_codex_write_performed_by_contour"
        )
        is True,
        "timestamped_backup_root": str(timestamped_backup_root),
        "thread_history_proven": False,
        "native_relaunch_proven": False,
    }
    packets["backup_repair_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "backup_repair_false_green_audit",
        "status": "ok" if rollback_ready else "blocked",
        "checks": [
            {
                "name": "incomplete_backup_not_counted",
                "passed": not packets["incomplete_backup_classification_packet.json"][
                    "existing_backup_counted_as_rollback_proof"
                ],
            },
            {
                "name": "persistent_profile_not_deleted",
                "passed": packets["persistent_profile_after_backup_snapshot.json"]["exists"] is True,
            },
            {
                "name": "complete_marker_requires_manifest_success",
                "passed": packets["timestamped_backup_complete_marker_packet.json"][
                    "complete_marker_created_after_manifest_success"
                ]
                is True,
            },
            {
                "name": "no_native_launch_claim",
                "passed": True,
            },
        ],
        "backup_repair_counts_as_thread_history_proof": False,
        "backup_repair_counts_as_native_relaunch_proof": False,
        "backup_repair_counts_as_route_or_egress_proof": False,
    }
    packets["backup_repair_secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    final_ok = (
        rollback_ready
        and packets["backup_repair_false_green_audit.json"]["status"] == "ok"
        and packets["backup_repair_secret_redaction_audit.json"]["status"] == "ok"
    )
    packets["backup_repair_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "backup_repair_summary",
        "status": "ok" if final_ok else "blocked",
        "final_status": "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_ROLLBACK_READY"
        if final_ok
        else "WBP_CUSTOM_PERSISTENT_PROFILE_BACKUP_BLOCKED_STATE_COPY_FAILED",
        "profile_id": profile_id,
        "profile_root": str(profile_root),
        "timestamped_backup_root": str(timestamped_backup_root),
        "existing_incomplete_backup_preserved": existing_backup_root.exists(),
        "rollback_ready": rollback_ready,
        "native_launch_attempted": False,
        "thread_history_claimed": False,
        "route_egress_model_claimed": False,
    }
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-backup-repair-r1")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(
            ROOT
            / "audit_results/wbp_persistent_custom_profile_backup_rollback_repair_r1_2026-05-27"
        ),
    )
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", default="")
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
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["backup_repair_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
