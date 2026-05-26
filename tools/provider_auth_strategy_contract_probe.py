#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit WBP provider auth strategy contract evidence packets."""

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

from wild_boar_proxy.native_filesystem_probe import json_write
from wild_boar_proxy.provider_auth_strategy import (
    build_auth_command_output_format_packet,
    build_auth_strategy_decision_matrix,
    build_auth_strategy_false_green_audit,
    build_auth_token_boundary_packet,
    build_authority_boundary_packet,
    build_current_codex_auth_independence_packet,
    build_file_auth_fallback_deferred_packet,
    build_file_auth_fallback_exclusion_packet,
    build_file_auth_non_substitution_packet,
    build_no_ambient_authority_packet,
    build_provider_auth_strategy_packet,
    build_secret_source_confusion_guard_packet,
    classify_native_config_auth_surface,
    provider_auth_text_has_secret,
    validate_provider_auth_strategy_packet,
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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _auth_command_config(auth_command: Path) -> str:
    return (
        'model = "gpt-5.4-mini"\n'
        'model_provider = "wbp"\n\n'
        "[model_providers.wbp]\n"
        'base_url = "http://127.0.0.1:8318/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n\n"
        "[model_providers.wbp.auth]\n"
        f'command = "{auth_command}"\n'
    )


def _bounded_bearer_config() -> str:
    return (
        'model = "gpt-5.4-mini"\n'
        'model_provider = "wbp"\n\n'
        "[model_providers.wbp]\n"
        'base_url = "http://127.0.0.1:8318/v1"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n"
        'experimental_bearer_token = "fixture-local-wbp-token-redacted-by-packet"\n'
    )


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/provider_auth_strategy.py",
        "tests/test_provider_auth_strategy.py",
        "tools/provider_auth_strategy_contract_probe.py",
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
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "provider_auth_strategy_schema_version": 1,
            "codex_app_version_optional_not_blocking": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
        },
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": ["fresh evidence directory only"],
            "native_launch_allowed": False,
            "native_launch_attempted": False,
            "protected_surfaces_write_allowed": False,
            "original_codex_profile_write_allowed": False,
            "runtime_route_or_account_mutation_allowed": False,
        },
    }


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "secret_redaction_audit",
        "status": "blocked" if provider_auth_text_has_secret(serialized) else "ok",
        "raw_secret_found": provider_auth_text_has_secret(serialized),
        "raw_upstream_secret_recorded": False,
        "auth_header_recorded": False,
        "current_codex_auth_json_recorded": False,
        "checked_packet_count": len(packets),
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "provider_auth_strategy_packet.json",
        "auth_strategy_precedence_packet.json",
        "auth_strategy_decision_matrix_packet.json",
        "auth_command_contract_packet.json",
        "auth_command_output_format_packet.json",
        "bounded_bearer_fallback_packet.json",
        "file_auth_fallback_exclusion_packet.json",
        "file_auth_fallback_deferred_packet.json",
        "file_auth_non_substitution_packet.json",
        "authority_boundary_packet.json",
        "current_codex_auth_independence_packet.json",
        "no_ambient_authority_packet.json",
        "auth_token_boundary_packet.json",
        "secret_source_confusion_guard_packet.json",
        "secret_redaction_audit.json",
        "auth_strategy_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = [
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_auth_strategy_audit",
        "status": "blocked" if missing or blocked else "ok",
        "referenced_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": sorted(blocked),
        "auth_command_selected": packets["auth_strategy_decision_matrix_packet.json"].get(
            "auth_command_selected"
        )
        is True,
        "bounded_bearer_not_silent": packets["auth_strategy_decision_matrix_packet.json"].get(
            "silent_fallback_detected"
        )
        is False,
        "file_auth_deferred": packets["file_auth_fallback_deferred_packet.json"].get(
            "status"
        )
        == "ok",
        "current_codex_auth_json_not_runtime_dependency": packets[
            "current_codex_auth_independence_packet.json"
        ].get("status")
        == "ok",
        "raw_secret_found": packets["secret_redaction_audit.json"].get("raw_secret_found")
        is True,
        "no_native_model_egress_or_final_claims": packets[
            "auth_strategy_false_green_audit.json"
        ].get("status")
        == "ok",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="provider-auth-strategy-contract-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    auth_command = repo_root / "wbp_codex_auth_command.py"
    provider_packet = build_provider_auth_strategy_packet(
        auth_command_path=auth_command,
        native_config_text=_bounded_bearer_config(),
        explicit_bearer_contract=True,
        browser_payload={},
    )
    decision_matrix = build_auth_strategy_decision_matrix(provider_packet)
    output_format = build_auth_command_output_format_packet(provider_packet)
    file_auth = build_file_auth_fallback_deferred_packet(provider_packet)
    file_auth_exclusion = build_file_auth_fallback_exclusion_packet(provider_packet)
    file_auth_non_substitution = build_file_auth_non_substitution_packet(provider_packet)
    current_auth = build_current_codex_auth_independence_packet(provider_packet)
    no_ambient_authority = build_no_ambient_authority_packet(provider_packet)
    authority_boundary = build_authority_boundary_packet(provider_packet)
    source_guard = build_secret_source_confusion_guard_packet(provider_packet)
    auth_token_boundary = build_auth_token_boundary_packet(provider_packet)
    false_green = build_auth_strategy_false_green_audit(
        provider_auth_strategy_packet=provider_packet,
        decision_matrix_packet=decision_matrix,
        file_auth_fallback_deferred_packet=file_auth,
        current_codex_auth_independence_packet=current_auth,
        secret_source_confusion_guard_packet=source_guard,
    )
    native_auth_command_surface = classify_native_config_auth_surface(
        _auth_command_config(auth_command),
        explicit_bearer_contract=False,
    )
    validation_failures = validate_provider_auth_strategy_packet(provider_packet)
    packets: dict[str, dict[str, Any]] = _base_packets(repo_root, evidence_dir)
    packets.update(
        {
            "provider_auth_strategy_packet.json": provider_packet,
            "auth_strategy_precedence_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "auth_strategy_precedence",
                "status": "ok" if not validation_failures else "blocked",
                "preferred_strategy": provider_packet["preferred_strategy"],
                "selected_strategy": provider_packet["selected_strategy"],
                "silent_fallback_allowed": False,
                "fallbacks": provider_packet["fallbacks"],
                "validation_failures": validation_failures,
            },
            "auth_strategy_decision_matrix_packet.json": decision_matrix,
            "auth_strategy_decision_matrix.json": decision_matrix,
            "auth_command_contract_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "auth_command_contract",
                "status": "ok",
                **provider_packet["auth_command"],
                "auth_command_path": provider_packet["auth_command"]["path"],
                "native_live_invocation_attempted": False,
            },
            "auth_command_output_format_packet.json": output_format,
            "authority_boundary_packet.json": authority_boundary,
            "native_config_auth_surface_packet.json": provider_packet[
                "native_config_auth_surface"
            ],
            "native_auth_command_config_surface_packet.json": native_auth_command_surface,
            "bounded_bearer_fallback_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "bounded_bearer_fallback",
                "status": "ok",
                **provider_packet["fallbacks"]["bounded_local_bearer"],
                "preferred_strategy": False,
                "explicit_contract_required": True,
                "explicit_contract_present_in_packet": True,
                "raw_token_in_packet": False,
                "native_launch_attempted": False,
            },
            "file_auth_fallback_exclusion_packet.json": file_auth_exclusion,
            "file_auth_fallback_deferred_packet.json": file_auth,
            "file_auth_non_substitution_packet.json": file_auth_non_substitution,
            "current_codex_auth_independence_packet.json": current_auth,
            "no_ambient_authority_packet.json": no_ambient_authority,
            "auth_token_boundary_packet.json": auth_token_boundary,
            "secret_source_confusion_guard_packet.json": source_guard,
            "auth_strategy_false_green_audit.json": false_green,
        }
    )
    packets["secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    packets["independent_auth_strategy_audit.json"] = _independent_audit(packets)
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_auth_strategy_summary",
        "status": "ok"
        if all(packet.get("status") != "blocked" for packet in packets.values())
        else "blocked",
        "final_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
        "selected_strategy": provider_packet["selected_strategy"],
        "auth_command_selected": decision_matrix["auth_command_selected"],
        "bounded_bearer_selected": decision_matrix["bounded_bearer_selected"],
        "file_auth_selected": decision_matrix["file_auth_selected"],
        "silent_fallback_detected": decision_matrix["silent_fallback_detected"],
        "native_launch_attempted": False,
        "model_availability_proven": False,
        "direct_egress_absence_proven": False,
        "final_e2e_proven": False,
    }
    packets["provider_auth_strategy_summary_packet.json"] = summary
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
