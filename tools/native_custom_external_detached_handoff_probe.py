#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate handoff-only packets for an external detached native safety retry."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_external_detached_command_admission_packet,
    build_external_detached_handoff_allowed_claims_matrix,
    build_external_detached_handoff_command_packet,
    build_external_detached_handoff_false_green_audit,
    build_external_detached_import_contract_packet,
    build_external_detached_operator_boundary_packet,
    build_no_launch_from_current_thread_packet,
    json_write,
)


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


def _json_file_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_json"
    return "present"


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
            )
        )
    ]
    admitted_current_contour = [
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_external_detached_handoff_probe.py",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="native-custom-external-detached-handoff-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--external-evidence-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    external_evidence_dir = Path(args.external_evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    sync_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": _run(repo_root, ["git", "status", "--short"]).splitlines(),
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
        "master_plan_written_to_repo": False,
    }
    dirt_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "quarantine_classification": "out_of_scope_historical_residue",
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    version_packet = {
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
    previous_blocker = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "previous_blocker_reference",
        "status": "ok",
        "referenced_commit": "f7a4eb7297e8c6096486318dd757b1c3b3cfc3ea",
        "referenced_status": "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_HOSTED_EXECUTOR_CONTEXT",
        "referenced_packet": str(
            repo_root
            / "audit_results/wbp_native_custom_quiescent_safety_retry_2026-05-26/native_safety_blocker_packet.json"
        ),
        "referenced_packet_status": _json_file_status(
            repo_root
            / "audit_results/wbp_native_custom_quiescent_safety_retry_2026-05-26/native_safety_blocker_packet.json"
        ),
        "referenced_native_launch_attempted": False,
    }
    current_host_reference = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "current_host_context_reference",
        "status": "ok",
        "referenced_packet": str(
            repo_root
            / "audit_results/wbp_native_custom_quiescent_safety_retry_2026-05-26/host_context_packet.json"
        ),
        "referenced_packet_status": _json_file_status(
            repo_root
            / "audit_results/wbp_native_custom_quiescent_safety_retry_2026-05-26/host_context_packet.json"
        ),
        "referenced_executor_context": "protected_codex_hosted",
        "current_thread_native_launch_admitted": False,
    }
    command_packet = build_external_detached_handoff_command_packet(
        repo_root=repo_root,
        evidence_dir=external_evidence_dir,
    )
    command_admission = build_external_detached_command_admission_packet(
        command_packet,
        repo_root=repo_root,
    )
    operator_boundary = build_external_detached_operator_boundary_packet()
    declared_write_surfaces = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": [
            str(evidence_dir),
            str(external_evidence_dir),
            "/tmp/wbp-native-fs-* only during later external retry if admitted",
        ],
        "protected_surfaces_write_allowed": False,
        "original_codex_bundle_write_allowed": False,
        "route_model_account_provider_mutation_allowed": False,
    }
    rollback = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "rollback_expectation",
        "status": "ok",
        "owned_surfaces": [str(evidence_dir), str(external_evidence_dir)],
        "cleanup_commands": [
            f"rm -rf {external_evidence_dir}",
        ],
        "protected_surfaces_must_not_be_manually_deleted": True,
        "current_codex_profile_cleanup_allowed": False,
    }
    import_contract = build_external_detached_import_contract_packet()
    no_launch = build_no_launch_from_current_thread_packet()
    allowed_claims = build_external_detached_handoff_allowed_claims_matrix()
    false_green = build_external_detached_handoff_false_green_audit(
        command_admission_packet=command_admission,
        import_contract_packet=import_contract,
        no_launch_packet=no_launch,
        allowed_claims_matrix=allowed_claims,
    )

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": version_packet,
        "previous_blocker_reference_packet.json": previous_blocker,
        "current_host_context_reference_packet.json": current_host_reference,
        "command_dry_run_admission_packet.json": command_admission,
        "external_detached_command_packet.json": command_packet,
        "operator_action_boundary_packet.json": operator_boundary,
        "declared_write_surfaces_packet.json": declared_write_surfaces,
        "rollback_expectation_packet.json": rollback,
        "evidence_import_contract_packet.json": import_contract,
        "no_launch_from_current_thread_packet.json": no_launch,
        "allowed_claims_matrix.json": allowed_claims,
        "handoff_false_green_audit.json": false_green,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = {
        "captured_at_utc": _utc_now(),
        "status": "ok" if command_admission["status"] == "ok" and false_green["status"] == "ok" else "blocked",
        "final_status": "EXTERNAL_DETACHED_NATIVE_SAFETY_RETRY_HANDOFF_READY",
        "command_admission_status": command_admission["status"],
        "handoff_only": True,
        "external_command_executed": False,
        "external_result_imported": False,
        "native_safety_pass_claimed": False,
        "shell_command": command_packet["shell_command"],
        "evidence_dir": str(evidence_dir),
        "external_evidence_dir": str(external_evidence_dir),
    }
    json_write(evidence_dir / "handoff_summary_packet.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
