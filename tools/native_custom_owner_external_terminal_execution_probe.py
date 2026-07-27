#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify owner external Terminal execution evidence production."""

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
    build_current_thread_boundary_packet,
    build_external_evidence_presence_packet,
    build_external_execution_minimal_json_packet,
    build_external_execution_secret_scan_packet,
    build_no_safety_interpretation_packet,
    build_owner_command_reverification_packet,
    build_owner_execution_attestation_packet,
    build_owner_execution_false_green_audit,
    build_owner_execution_layer_separation_packet,
    build_owner_execution_observation_packet,
    build_owner_external_execution_result_packet,
    json_write,
)


# The probe verifies that the owner-reported external command matches the
# canonical quiescent-safety-retry probe invocation bound to the current
# repository root. The path is derived from repo_root at runtime so the probe
# remains correct in any checkout (primary worktree, plan-owned worktree, or
# CI clone) instead of being pinned to a single absolute path.
EXTERNAL_EVIDENCE_DIR_NAME = (
    "wbp_native_custom_quiescent_safety_retry_EXTERNAL_2026-05-26T000000Z"
)


def expected_shell_command_for(repo_root: Path) -> str:
    root = str(repo_root)
    return (
        f"cd {root} && python3 "
        f"{root}/tools/native_custom_quiescent_safety_retry_probe.py "
        f"--repo-root {root} "
        f"--evidence-dir {root}/audit_results/{EXTERNAL_EVIDENCE_DIR_NAME}"
    )


# Kept for backwards compatibility with callers that import the constant; the
# runtime path derives from repo_root via expected_shell_command_for().
EXPECTED_SHELL_COMMAND = expected_shell_command_for(ROOT)

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-cliproxy[A-Za-z0-9_-]+"),
    re.compile(r"OPENAI_API_KEY\"\s*:\s*\"[^<\"]+"),
    re.compile(r"experimental_bearer_token\s*=\s*\"(?!<redacted>)[^\"]+"),
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
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


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "owner_external_execution_input_error",
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
        "tools/native_custom_owner_external_terminal_execution_probe.py",
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


def _secret_matches(external_evidence_dir: Path) -> list[str]:
    if not external_evidence_dir.exists():
        return []
    matches: list[str] = []
    for path in sorted(external_evidence_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                matches.append(str(path))
                break
    return matches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="native-custom-owner-external-terminal-execution-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument(
        "--handoff-command-packet",
        default=str(
            ROOT
            / "audit_results/wbp_native_custom_external_detached_execution_handoff_2026-05-26/external_detached_command_packet.json"
        ),
    )
    parser.add_argument("--owner-reported-execution", action="store_true")
    parser.add_argument("--owner-reported-exit-code", type=int, default=None)
    parser.add_argument("--owner-reported-output-summary", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    handoff_path = Path(args.handoff_command_packet).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if not handoff_path.exists():
        return _emit_input_error(
            reason_class="HANDOFF_COMMAND_PACKET_MISSING",
            message="--handoff-command-packet does not exist.",
            evidence_dir=evidence_dir,
        )
    try:
        handoff_command = _read_json(handoff_path)
    except json.JSONDecodeError:
        return _emit_input_error(
            reason_class="HANDOFF_COMMAND_PACKET_INVALID_JSON",
            message="--handoff-command-packet is not valid JSON.",
            evidence_dir=evidence_dir,
        )
    external_evidence_dir = Path(str(handoff_command.get("evidence_dir", ""))).resolve()

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
    current_thread_boundary = build_current_thread_boundary_packet()
    command_reverification = build_owner_command_reverification_packet(
        handoff_command_packet=handoff_command,
        expected_shell_command=expected_shell_command_for(repo_root),
        external_evidence_dir=external_evidence_dir,
        repo_root=repo_root,
    )
    owner_attestation = build_owner_execution_attestation_packet(
        owner_reported_execution=args.owner_reported_execution
    )
    owner_observation = build_owner_execution_observation_packet(
        owner_reported_execution=args.owner_reported_execution,
        owner_reported_exit_code=args.owner_reported_exit_code,
        owner_reported_output_summary=args.owner_reported_output_summary,
    )
    evidence_presence = build_external_evidence_presence_packet(
        external_evidence_dir=external_evidence_dir,
    )
    minimal_json = build_external_execution_minimal_json_packet(
        evidence_presence_packet=evidence_presence,
    )
    secret_scan = build_external_execution_secret_scan_packet(
        external_evidence_dir=external_evidence_dir,
        matches=_secret_matches(external_evidence_dir),
    )
    no_safety = build_no_safety_interpretation_packet()
    layer_separation = build_owner_execution_layer_separation_packet()
    result = build_owner_external_execution_result_packet(
        command_reverification_packet=command_reverification,
        owner_attestation_packet=owner_attestation,
        evidence_presence_packet=evidence_presence,
        minimal_json_packet=minimal_json,
        secret_scan_packet=secret_scan,
        no_safety_interpretation_packet=no_safety,
    )
    false_green = build_owner_execution_false_green_audit(
        current_thread_boundary_packet=current_thread_boundary,
        command_reverification_packet=command_reverification,
        owner_attestation_packet=owner_attestation,
        owner_observation_packet=owner_observation,
        evidence_presence_packet=evidence_presence,
        minimal_json_packet=minimal_json,
        secret_scan_packet=secret_scan,
        no_safety_interpretation_packet=no_safety,
        result_packet=result,
        layer_separation_packet=layer_separation,
    )

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": version_packet,
        "current_thread_boundary_packet.json": current_thread_boundary,
        "owner_command_reverification_packet.json": command_reverification,
        "owner_execution_attestation_packet.json": owner_attestation,
        "owner_execution_observation_packet.json": owner_observation,
        "external_evidence_presence_after_owner_run_packet.json": evidence_presence,
        "external_execution_minimal_json_packet.json": minimal_json,
        "external_execution_secret_scan_packet.json": secret_scan,
        "no_safety_interpretation_packet.json": no_safety,
        "owner_execution_layer_separation_packet.json": layer_separation,
        "owner_external_execution_result_packet.json": result,
        "owner_execution_false_green_audit.json": false_green,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = {
        "captured_at_utc": _utc_now(),
        "status": result["status"],
        "final_status": result["final_status"],
        "shell_command": handoff_command.get("shell_command", ""),
        "owner_reported_execution": args.owner_reported_execution,
        "external_evidence_dir": str(external_evidence_dir),
        "external_evidence_dir_exists": result["external_evidence_dir_exists"],
        "safety_interpreted": result["safety_interpreted"],
        "protected_surface_interpreted": result["protected_surface_interpreted"],
        "launch_admission_interpreted": result["launch_admission_interpreted"],
        "exit_code_used_as_proof": result["exit_code_used_as_proof"],
        "native_safety_pass_claimed": result["native_safety_pass_claimed"],
        "routing_claimed": result["routing_claimed"],
        "ux_claimed": result["ux_claimed"],
        "egress_claimed": result["egress_claimed"],
    }
    json_write(evidence_dir / "owner_execution_summary_packet.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
