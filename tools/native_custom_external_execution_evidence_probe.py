#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify external detached native safety execution evidence production."""

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
    build_external_evidence_presence_packet,
    build_external_execution_command_verification_packet,
    build_external_execution_false_green_audit,
    build_external_execution_observation_packet,
    build_external_execution_result_packet,
    build_external_execution_scope_boundary_packet,
    build_external_execution_secret_scan_packet,
    build_execution_layer_separation_packet,
    build_owner_execution_boundary_packet,
    json_write,
)


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
        "tools/native_custom_external_execution_evidence_probe.py",
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
        prog="native-custom-external-execution-evidence-probe"
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
    parser.add_argument("--reported-exit-code", type=int, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    handoff_command = _read_json(Path(args.handoff_command_packet).resolve())
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
    scope = build_external_execution_scope_boundary_packet()
    owner_boundary = build_owner_execution_boundary_packet()
    command_verification = build_external_execution_command_verification_packet(
        handoff_command_packet=handoff_command,
        external_evidence_dir=external_evidence_dir,
        repo_root=repo_root,
    )
    observation = build_external_execution_observation_packet(
        shell_command=str(handoff_command.get("shell_command", "")),
        reported_exit_code=args.reported_exit_code,
    )
    presence = build_external_evidence_presence_packet(
        external_evidence_dir=external_evidence_dir,
    )
    secret_scan = build_external_execution_secret_scan_packet(
        external_evidence_dir=external_evidence_dir,
        matches=_secret_matches(external_evidence_dir),
    )
    layer_separation = build_execution_layer_separation_packet()
    result = build_external_execution_result_packet(
        command_verification_packet=command_verification,
        evidence_presence_packet=presence,
        secret_scan_packet=secret_scan,
    )
    false_green = build_external_execution_false_green_audit(
        scope_boundary_packet=scope,
        command_verification_packet=command_verification,
        owner_boundary_packet=owner_boundary,
        observation_packet=observation,
        evidence_presence_packet=presence,
        secret_scan_packet=secret_scan,
        result_packet=result,
        layer_separation_packet=layer_separation,
    )

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": version_packet,
        "execution_scope_boundary_packet.json": scope,
        "owner_execution_boundary_packet.json": owner_boundary,
        "external_execution_command_verification_packet.json": command_verification,
        "external_execution_observation_packet.json": observation,
        "external_evidence_presence_packet.json": presence,
        "external_execution_secret_scan_packet.json": secret_scan,
        "execution_layer_separation_packet.json": layer_separation,
        "external_execution_result_packet.json": result,
        "external_execution_false_green_audit.json": false_green,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = {
        "captured_at_utc": _utc_now(),
        "status": result["status"],
        "final_status": result["final_status"],
        "shell_command": handoff_command.get("shell_command", ""),
        "external_evidence_dir": str(external_evidence_dir),
        "external_evidence_dir_exists": result["external_evidence_dir_exists"],
        "current_thread_executed_command": False,
        "native_launch_from_current_thread": False,
        "safety_result_imported": False,
        "filesystem_safety_classified": False,
        "native_safety_pass_claimed": False,
    }
    json_write(evidence_dir / "external_execution_summary_packet.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
