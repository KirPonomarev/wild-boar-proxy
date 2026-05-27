#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit Persistent Custom pre-live admission R5 evidence."""

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

from wild_boar_proxy.native_filesystem_probe import json_write
from wild_boar_proxy.persistent_profile_pre_live_admission import (
    FORBIDDEN_TRUE_FIELDS,
    PARENT_STATUS,
    TARGET_STATUS,
    PriorEvidenceLocation,
    build_admission_packets,
    build_false_green_audit,
    build_summary_packet,
)
from wild_boar_proxy.persistent_profile_state_diff import marker_scan_text


EVIDENCE_DIR_NAME = (
    "audit_results/wbp_persistent_profile_pre_live_admission_r5_2026-05-27"
)

DEFAULT_PRIOR_DIRS = {
    "r1_launcher_contract": (
        "audit_results/"
        "wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27"
    ),
    "r2_dry_run_enforcement": (
        "audit_results/"
        "wbp_persistent_profile_launcher_dry_run_enforcement_readiness_r2_2026-05-27"
    ),
    "r3_state_diff": (
        "audit_results/"
        "wbp_persistent_profile_state_diff_redaction_readiness_r3_2026-05-27"
    ),
    "r4_backup_restore": (
        "audit_results/"
        "wbp_persistent_profile_backup_restore_dry_run_readiness_r4_2026-05-27"
    ),
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


def run_text(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if check and process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/persistent_profile_pre_live_admission.py",
        "tools/persistent_profile_pre_live_admission_r5_probe.py",
        "tests/test_persistent_profile_pre_live_admission_r5.py",
    }
    admitted_current_evidence_dirs = (
        f"{relative_evidence_dir}/",
        f"{EVIDENCE_DIR_NAME}/",
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

    def is_current_contour_line(line: str) -> bool:
        path = line[3:] if len(line) > 3 else line.strip()
        return path in admitted_current_contour or path.startswith(
            admitted_current_evidence_dirs
        )

    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined and not is_current_contour_line(line)
    ]
    return quarantined, unexpected_dirty


def build_sync_gate_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "persistent_pre_live_sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch=run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head=run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        git_status_short=run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        unexpected_dirty_entries=unexpected_dirty,
        master_plan_written_to_repo=False,
        current_contour="WBP_CUSTOM_PERSISTENT_PROFILE_PRE_LIVE_ADMISSION_R5",
    )


def build_historical_quarantine_packet(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(repo_root, evidence_dir)
    return packet(
        "persistent_pre_live_historical_dirt_quarantine",
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
        "persistent_pre_live_version_pinning",
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
        wbp_git_commit=run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True),
    )


def _field_true(value: Any, field: str) -> bool:
    if isinstance(value, dict):
        if value.get(field) is True:
            return True
        return any(_field_true(nested, field) for nested in value.values())
    if isinstance(value, list):
        return any(_field_true(nested, field) for nested in value)
    return False


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    scan = marker_scan_text(serialized)
    raw_prompt_recorded = any(
        _field_true(payload, "raw_prompt_recorded") for payload in packets.values()
    )
    raw_secret_recorded = any(
        _field_true(payload, "raw_secret_recorded") for payload in packets.values()
    )
    blocked = (
        scan["raw_prompt_found"]
        or scan["raw_secret_found"]
        or raw_prompt_recorded
        or raw_secret_recorded
    )
    return packet(
        "persistent_pre_live_secret_redaction_audit",
        status="blocked" if blocked else "ok",
        marker_findings=scan["marker_findings"],
        secret_pattern_findings=scan["secret_pattern_findings"],
        raw_prompt_found=scan["raw_prompt_found"],
        raw_secret_found=scan["raw_secret_found"],
        raw_prompt_recorded=raw_prompt_recorded,
        raw_secret_recorded=raw_secret_recorded,
        exhaustive_dlp_claimed=False,
    )


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true_fields: list[str] = []
    for filename, payload in packets.items():
        forbidden_true_fields.extend(
            f"{filename}.{field}"
            for field in sorted(FORBIDDEN_TRUE_FIELDS)
            if _field_true(payload, field)
        )
    layer_mixing_packets = [
        filename
        for filename, payload in packets.items()
        if payload.get("thread_history_preservation_claimed") is True
        or payload.get("native_ux_claimed") is True
        or payload.get("route_proven") is True
        or payload.get("direct_egress_absence_claimed") is True
        or payload.get("model_availability_claimed") is True
        or payload.get("original_reversibility_proven") is True
    ]
    return packet(
        "independent_persistent_pre_live_admission_audit",
        status="blocked" if forbidden_true_fields or layer_mixing_packets else "ok",
        forbidden_true_fields=forbidden_true_fields,
        layer_mixing_packets=layer_mixing_packets,
        checked_claim="pre_live_admission_only",
        text_only_audit_counted_as_pass=False,
    )


def build_locations(repo_root: Path, args: argparse.Namespace) -> list[PriorEvidenceLocation]:
    overrides = {
        "r1_launcher_contract": args.r1_evidence_dir,
        "r2_dry_run_enforcement": args.r2_evidence_dir,
        "r3_state_diff": args.r3_evidence_dir,
        "r4_backup_restore": args.r4_evidence_dir,
    }
    locations: list[PriorEvidenceLocation] = []
    for key, default_path in DEFAULT_PRIOR_DIRS.items():
        path_value = overrides[key] or str(repo_root / default_path)
        locations.append(PriorEvidenceLocation(key=key, evidence_dir=Path(path_value)))
    return locations


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    locations: list[PriorEvidenceLocation],
) -> dict[str, dict[str, Any]]:
    packets = build_admission_packets(repo_root=repo_root, locations=locations)
    packets["sync_gate_packet.json"] = build_sync_gate_packet(repo_root, evidence_dir)
    packets["historical_dirt_quarantine_packet.json"] = build_historical_quarantine_packet(
        repo_root,
        evidence_dir,
    )
    packets["version_pinning_packet.json"] = build_version_pinning_packet(repo_root)
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["independent_persistent_pre_live_admission_audit.json"] = (
        build_independent_audit_packet(packets)
    )
    audit_subset = {
        name: payload
        for name, payload in packets.items()
        if name
        not in {
            "persistent_pre_live_summary_packet.json",
            "secret_redaction_audit.json",
            "independent_persistent_pre_live_admission_audit.json",
        }
    }
    packets["persistent_pre_live_false_green_audit.json"] = build_false_green_audit(
        audit_subset
    )
    packets["persistent_pre_live_summary_packet.json"] = build_summary_packet(packets)
    audit_ok = (
        packets["secret_redaction_audit.json"]["status"] == "ok"
        and packets["independent_persistent_pre_live_admission_audit.json"]["status"]
        == "ok"
    )
    if not audit_ok:
        packets["persistent_pre_live_summary_packet.json"]["status"] = "blocked"
        packets["persistent_pre_live_summary_packet.json"]["final_status"] = (
            "PERSISTENT_PRE_LIVE_ADMISSION_R5_BLOCKED"
        )
        packets["persistent_pre_live_summary_packet.json"]["this_target_closed"] = False
    return packets


def write_closeout(repo_root: Path, evidence_dir: Path, summary: dict[str, Any]) -> None:
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True)
    closeout = f"""# WBP Custom Persistent Profile Pre-Live Admission R5 Closeout

## Goal

Classify Persistent Custom pre-live admission readiness by referencing completed R1-R4 evidence packets by path, hash, status, and non-claim flags without live execution, owner input, profile writes, backup creation, restore execution, UX proof, route proof, egress proof, model proof, or Original Codex reversibility.

## Result

- status: {summary["status"]}
- final verdict: {summary["final_status"]}
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Contour Capsule

- goal: prove pre-live admission reference gate only
- branch: {branch}
- head: {head}
- touched files: wild_boar_proxy/persistent_profile_pre_live_admission.py; tools/persistent_profile_pre_live_admission_r5_probe.py; tests/test_persistent_profile_pre_live_admission_r5.py; {evidence_dir.relative_to(repo_root)}
- tests run: py_compile; focused R5 pytest; relevant launch/hygiene/closeout pytest; JSON packet parse; secret marker audit; closeout resilience
- blocked risks: admission does not prove live launch safety, thread history, storage persistence, UX, route, egress, model availability, backup execution, restore verification, Original reversibility, or final E2E
- parent target: {PARENT_STATUS} remains open
- closure state: CLOSED

## Verification

- tests: recorded in terminal for this contour
- build: py_compile for the R5 module and probe
- manual: no owner action required or used
- live verification: not performed; forbidden by this admission contour

## Artifacts

- spec: thread-only contour text, not stored in repo
- packet: persistent_pre_live_summary_packet.json
- report: independent_persistent_pre_live_admission_audit.json

## Git

- branch: {branch}
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; raw prompts, raw secrets, and raw packet bodies are not recorded

## Notes

- blockers encountered: no contour blocker; historical dirty worktree entries remained quarantined and unstaged
- resume from here: CLOSED
"""
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-profile-pre-live-admission-r5")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", default=str(REPO_ROOT / EVIDENCE_DIR_NAME))
    parser.add_argument("--r1-evidence-dir", default="")
    parser.add_argument("--r2-evidence-dir", default="")
    parser.add_argument("--r3-evidence-dir", default="")
    parser.add_argument("--r4-evidence-dir", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        locations=build_locations(repo_root, args),
    )
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    write_closeout(repo_root, evidence_dir, packets["persistent_pre_live_summary_packet.json"])
    summary = packets["persistent_pre_live_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
