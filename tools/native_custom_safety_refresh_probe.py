#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run the bounded native Custom safety refresh contour helper."""

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

from wild_boar_proxy.native_filesystem_probe import json_write, run_native_filesystem_probe


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


def _json_file_status(path: Path) -> str:
    if not path.exists():
        return "missing"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid_json"
    return "present"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="native-custom-safety-refresh-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    return parser


def _write_preamble_packets(repo_root: Path, evidence_dir: Path, *, endpoint: str, model: str) -> None:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(("M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/", "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/", "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/"))
    ]
    admitted_current_contour = [
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_safety_refresh_probe.py",
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {evidence_dir.relative_to(repo_root)}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    sync_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": status_lines,
        "unexpected_dirty_entries": unexpected_dirty,
        "admitted_current_contour_paths": admitted_current_contour,
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
    auth_reference = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "auth_strategy_reference",
        "status": "ok",
        "referenced_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "referenced_commit": "3db0431cff061fbf676e4218fac3116da5657149",
        "referenced_packet": str(
            repo_root
            / "audit_results/wbp_provider_auth_strategy_contract_2026-05-26/provider_auth_strategy_packet.json"
        ),
        "referenced_packet_status": _json_file_status(
            repo_root
            / "audit_results/wbp_provider_auth_strategy_contract_2026-05-26/provider_auth_strategy_packet.json"
        ),
        "auth_strategy_reproved_in_this_contour": False,
    }
    model_reference = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "model_availability_reference",
        "status": "ok",
        "referenced_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        "referenced_commit": "9cb099d4cf0e4c3a2ac72e67b2462957881cfaf3",
        "referenced_packet": str(
            repo_root
            / "audit_results/wbp_model_availability_smoke_matrix_2026-05-26/model_availability_matrix.json"
        ),
        "referenced_packet_status": _json_file_status(
            repo_root
            / "audit_results/wbp_model_availability_smoke_matrix_2026-05-26/model_availability_matrix.json"
        ),
        "model_availability_reproved_in_this_contour": False,
        "selected_safety_model": model,
    }
    write_surfaces = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "endpoint": endpoint,
        "selected_model": model,
        "declared_write_surfaces": [
            "fresh evidence directory only",
            "server-owned isolated temp Custom profile under /tmp/wbp-native-fs-*",
            "server-owned isolated CODEX_HOME under /tmp/wbp-native-fs-*",
            "server-owned isolated user-data-dir under /tmp/wbp-native-fs-*",
        ],
        "protected_surfaces_write_allowed": False,
        "original_codex_bundle_write_allowed": False,
        "original_codex_profile_write_allowed": False,
    }

    for name, packet in {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": version_packet,
        "auth_strategy_reference_packet.json": auth_reference,
        "model_availability_reference_packet.json": model_reference,
        "declared_write_surfaces_packet.json": write_surfaces,
    }.items():
        json_write(evidence_dir / name, packet)


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    _write_preamble_packets(
        repo_root,
        evidence_dir,
        endpoint=args.endpoint,
        model=args.model,
    )
    packet = run_native_filesystem_probe(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        endpoint=args.endpoint,
        model=args.model,
    )
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
