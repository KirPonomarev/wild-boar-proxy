#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Owner-gated Original Codex via WBP bounded live contour probe.

This tool intentionally stops before any Original profile write unless the
exact owner authorization surface is present. The no-authorization path is a
valid blocked packet, not a partial green.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_original_auth_boundary_packet,
    build_original_live_false_green_audit,
    build_original_live_owner_authorization_packet,
    build_original_live_rollback_point_packet,
    build_original_live_summary_packet,
    build_original_live_temporary_route_apply_admission_packet,
    build_original_process_window_state_packet,
    build_original_profile_inventory_packet,
    build_original_readiness_reference_packet,
    build_selected_model_trace_claim_packet,
    collect_codex_process_inventory,
    json_write,
)


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"access_token[\"']?\s*[:=]\s*[\"'][^\"']{8,}", re.IGNORECASE),
)
READINESS_SUMMARY = (
    "audit_results/original_codex_via_wbp_reversibility_readiness_2026-05-26/"
    "original_readiness_summary_packet.json"
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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = (
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/original_codex_via_wbp_bounded_live_reversibility_probe.py",
    )
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _base_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": _run(repo_root, ["git", "status", "--short"]).splitlines(),
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
            "codex_cli_version": _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version_optional_not_blocking": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "original_bounded_live_schema_version": 1,
        },
    }


def _declared_write_surfaces_packet(owner_auth: dict[str, Any]) -> dict[str, Any]:
    write_allowed = owner_auth.get("status") == "ok"
    declared = ["fresh evidence directory only"]
    if write_allowed:
        declared.append(str(owner_auth.get("exact_target_path", "")))
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": declared,
        "owner_authorization_required": True,
        "owner_authorization_status": owner_auth.get("status"),
        "original_codex_profile_write_allowed": write_allowed,
        "original_codex_profile_write_performed": False,
        "native_original_launch_allowed": write_allowed,
        "native_original_launch_attempted": False,
        "auth_json_mutation_allowed": False,
        "auth_json_runtime_dependency_allowed": False,
        "hidden_cleanup_allowed": False,
    }


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    raw_secret_found = any(pattern.search(serialized) for pattern in SECRET_PATTERNS)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_live_secret_redaction_audit",
        "status": "blocked" if raw_secret_found else "ok",
        "raw_secret_found": raw_secret_found,
        "auth_json_token_value_recorded": False,
        "auth_header_recorded": False,
        "upstream_secret_recorded": False,
        "checked_packet_count": len(packets),
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "declared_write_surfaces_packet.json",
        "original_readiness_reference_packet.json",
        "owner_authorization_packet.json",
        "original_profile_before_packet.json",
        "original_auth_boundary_packet.json",
        "original_process_window_before_packet.json",
        "rollback_point_packet.json",
        "temporary_route_apply_admission_packet.json",
        "selected_model_trace_claim_packet.json",
        "original_via_wbp_summary_packet.json",
        "original_via_wbp_false_green_audit.json",
        "original_live_secret_redaction_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = [
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    ]
    summary = packets.get("original_via_wbp_summary_packet.json", {})
    owner_auth = packets.get("owner_authorization_packet.json", {})
    false_green = packets.get("original_via_wbp_false_green_audit.json", {})
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_original_via_wbp_audit",
        "status": "ok" if not missing and false_green.get("status") == "ok" else "blocked",
        "referenced_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": sorted(blocked),
        "owner_authorization_status": owner_auth.get("status"),
        "blocked_closeout_is_honest": summary.get("status") == "blocked",
        "no_original_profile_write_without_authorization": (
            owner_auth.get("status") != "ok"
            and summary.get("original_profile_write_performed") is False
        ),
        "no_native_original_launch_without_authorization": (
            owner_auth.get("status") != "ok"
            and summary.get("native_original_launch_attempted") is False
        ),
        "false_green_audit_ok": false_green.get("status") == "ok",
        "direct_egress_absence_claimed": summary.get("direct_egress_absence_proven") is True,
        "model_availability_claimed": summary.get("model_availability_proven") is True,
        "final_e2e_claimed": summary.get("final_e2e_proven") is True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="original-codex-via-wbp-bounded-live-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--exact-target-path", default=str(Path.home() / ".codex" / "config.toml"))
    parser.add_argument("--allowed-write-operation", default="")
    parser.add_argument("--rollback-mode", default="")
    parser.add_argument("--launch-permission", action="store_true")
    parser.add_argument("--owner-prompt-permission", action="store_true")
    parser.add_argument("--restore-permission", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    readiness_path = repo_root / READINESS_SUMMARY
    readiness_summary = _read_json(readiness_path) if readiness_path.exists() else {}
    owner_auth = build_original_live_owner_authorization_packet(
        owner_authorized=args.owner_authorized,
        exact_target_path=args.exact_target_path,
        allowed_write_operation=args.allowed_write_operation,
        rollback_mode=args.rollback_mode,
        launch_permission=args.launch_permission,
        owner_prompt_permission=args.owner_prompt_permission,
        restore_permission=args.restore_permission,
    )
    packets: dict[str, dict[str, Any]] = _base_packets(repo_root, evidence_dir)
    packets["owner_authorization_packet.json"] = owner_auth
    packets["declared_write_surfaces_packet.json"] = _declared_write_surfaces_packet(
        owner_auth
    )
    packets["original_readiness_reference_packet.json"] = (
        build_original_readiness_reference_packet(
            readiness_summary_packet=readiness_summary,
            source_path=str(readiness_path),
        )
    )
    process_inventory = collect_codex_process_inventory(
        custom_user_data_dir="__original_bounded_live_no_custom_launch__"
    )
    profile_before = build_original_profile_inventory_packet()
    auth_boundary = build_original_auth_boundary_packet(
        profile_inventory_packet=profile_before
    )
    process_window = build_original_process_window_state_packet(
        process_inventory_packet=process_inventory
    )
    rollback_point = build_original_live_rollback_point_packet(
        profile_before_packet=profile_before,
        owner_authorization_packet=owner_auth,
        rollback_point_created=False,
        rollback_point_verified=False,
    )
    apply_admission = build_original_live_temporary_route_apply_admission_packet(
        owner_authorization_packet=owner_auth,
        rollback_point_packet=rollback_point,
        readiness_reference_packet=packets["original_readiness_reference_packet.json"],
    )
    selected_model = build_selected_model_trace_claim_packet()
    summary = build_original_live_summary_packet(
        owner_authorization_packet=owner_auth,
        apply_admission_packet=apply_admission,
    )
    false_green = build_original_live_false_green_audit(
        summary_packet=summary,
        selected_model_trace_claim_packet=selected_model,
    )
    packets.update(
        {
            "original_profile_before_packet.json": profile_before,
            "original_auth_boundary_packet.json": auth_boundary,
            "original_process_window_before_packet.json": process_window,
            "rollback_point_packet.json": rollback_point,
            "temporary_route_apply_admission_packet.json": apply_admission,
            "selected_model_trace_claim_packet.json": selected_model,
            "original_via_wbp_summary_packet.json": summary,
            "original_via_wbp_false_green_audit.json": false_green,
        }
    )
    packets["original_live_secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    packets["independent_original_via_wbp_audit.json"] = _independent_audit(packets)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
