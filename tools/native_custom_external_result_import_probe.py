#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import and classify external detached native safety evidence."""

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
    build_external_result_command_integrity_packet,
    build_external_result_execution_ownership_packet,
    build_external_result_import_packet,
    build_external_result_secret_scan_packet,
    build_import_allowed_claims_matrix,
    build_keychain_boundary_packet,
    build_layer_separation_packet,
    build_native_safety_import_false_green_audit,
    build_protected_surface_import_summary,
    classify_native_safety_retry_import,
    json_write,
    validate_external_evidence_packets,
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
        "tools/native_custom_external_result_import_probe.py",
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
    parser = argparse.ArgumentParser(prog="native-custom-external-result-import-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument(
        "--handoff-dir",
        default=str(
            ROOT
            / "audit_results/wbp_native_custom_external_detached_execution_handoff_2026-05-26"
        ),
    )
    parser.add_argument(
        "--external-evidence-dir",
        default=str(
            ROOT
            / "audit_results/wbp_native_custom_quiescent_safety_retry_EXTERNAL_2026-05-26T000000Z"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    handoff_dir = Path(args.handoff_dir).resolve()
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

    handoff_command = _read_json(handoff_dir / "external_detached_command_packet.json")
    import_contract = _read_json(handoff_dir / "evidence_import_contract_packet.json")
    execution_ownership = build_external_result_execution_ownership_packet()
    command_integrity = build_external_result_command_integrity_packet(
        handoff_command_packet=handoff_command,
        external_evidence_dir=external_evidence_dir,
        repo_root=repo_root,
    )
    validation = validate_external_evidence_packets(
        external_evidence_dir=external_evidence_dir,
        required_packets=import_contract["required_packets"],
    )
    secret_scan = build_external_result_secret_scan_packet(
        external_evidence_dir=external_evidence_dir,
        matches=_secret_matches(external_evidence_dir),
    )
    protected_summary = build_protected_surface_import_summary(
        validation_packet=validation,
    )
    keychain_boundary = build_keychain_boundary_packet(
        keychain_packet=validation.get("parsed_packets", {}).get(
            "keychain_observation_packet.json", {}
        )
    )
    layer_separation = build_layer_separation_packet()
    allowed_claims = build_import_allowed_claims_matrix()
    classification = classify_native_safety_retry_import(
        command_integrity_packet=command_integrity,
        validation_packet=validation,
        secret_scan_packet=secret_scan,
        protected_surface_summary_packet=protected_summary,
        keychain_boundary_packet=keychain_boundary,
    )
    import_packet = build_external_result_import_packet(
        validation_packet=validation,
        classification_packet=classification,
    )
    false_green = build_native_safety_import_false_green_audit(
        execution_ownership_packet=execution_ownership,
        command_integrity_packet=command_integrity,
        validation_packet=validation,
        secret_scan_packet=secret_scan,
        classification_packet=classification,
        allowed_claims_matrix=allowed_claims,
        layer_separation_packet=layer_separation,
        keychain_boundary_packet=keychain_boundary,
    )

    packets = {
        "sync_gate_packet.json": sync_packet,
        "historical_dirt_quarantine_packet.json": dirt_packet,
        "version_pinning_packet.json": version_packet,
        "execution_ownership_packet.json": execution_ownership,
        "external_command_integrity_packet.json": command_integrity,
        "external_evidence_validation_packet.json": validation,
        "external_result_secret_scan_packet.json": secret_scan,
        "protected_surface_import_summary.json": protected_summary,
        "keychain_boundary_packet.json": keychain_boundary,
        "layer_separation_packet.json": layer_separation,
        "import_allowed_claims_matrix.json": allowed_claims,
        "native_safety_retry_classification_packet.json": classification,
        "external_result_import_packet.json": import_packet,
        "native_safety_import_false_green_audit.json": false_green,
    }
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = {
        "captured_at_utc": _utc_now(),
        "status": classification["status"],
        "final_status": classification["final_status"],
        "external_evidence_dir": str(external_evidence_dir),
        "external_evidence_dir_exists": validation["external_evidence_dir_exists"],
        "external_result_imported": import_packet["external_result_imported"],
        "current_thread_external_command_executed": False,
        "current_thread_native_launch_attempted": False,
        "native_safety_pass_claimed": classification["native_safety_pass_claimed"],
    }
    json_write(evidence_dir / "import_summary_packet.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if classification["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
