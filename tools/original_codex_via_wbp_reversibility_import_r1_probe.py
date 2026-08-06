#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import packet-backed Original-via-WBP reversibility evidence under current bounds."""

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


SOURCE_REQUIRED_PACKETS = {
    "declared_write_surfaces_packet.json",
    "original_profile_before_packet.json",
    "rollback_point_packet.json",
    "temporary_route_apply_execution_packet.json",
    "original_auth_boundary_packet.json",
    "native_original_launch_execution_packet.json",
    "wbp_trace_observation_packet.json",
    "restore_verification_packet.json",
    "original_via_wbp_false_green_audit.json",
    "independent_original_via_wbp_audit.json",
    "original_via_wbp_summary_packet.json",
}


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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_reversibility_import_input_error",
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


def _historical_quarantine(
    repo_root: Path, evidence_dir: Path
) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
                "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            )
        )
    ]
    admitted_current_contour = [
        "tools/original_codex_via_wbp_reversibility_import_r1_probe.py",
        "tests/test_original_codex_via_wbp_reversibility_import_r1_probe.py",
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


def _version_packet(repo_root: Path) -> dict[str, Any]:
    return {
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="original-codex-via-wbp-reversibility-import-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--source-evidence-dir", required=True)
    return parser


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_evidence_dir: Path,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": status_lines,
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
        "master_plan_written_to_repo": False,
    }
    packets["historical_dirt_quarantine_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "quarantine_classification": "out_of_scope_historical_residue",
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["version_pinning_packet.json"] = _version_packet(repo_root)

    parsed: dict[str, dict[str, Any]] = {}
    missing_packets: list[str] = []
    invalid_packets: list[str] = []
    for name in sorted(SOURCE_REQUIRED_PACKETS):
        path = source_evidence_dir / name
        if not path.exists():
            missing_packets.append(name)
            continue
        try:
            parsed[name] = _read_json(path)
        except json.JSONDecodeError:
            invalid_packets.append(name)

    packets["source_original_wbp_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_original_wbp_evidence_inventory",
        "status": "ok" if not missing_packets and not invalid_packets else "blocked",
        "source_evidence_dir": str(source_evidence_dir),
        "required_packets": sorted(SOURCE_REQUIRED_PACKETS),
        "missing_packets": missing_packets,
        "invalid_json_packets": invalid_packets,
        "source_packet_count": len(parsed),
        "historical_source_packet_chain": True,
        "current_owner_action_collected": False,
    }

    source_summary = parsed.get("original_via_wbp_summary_packet.json", {})
    source_false_green = parsed.get("original_via_wbp_false_green_audit.json", {})
    source_independent = parsed.get("independent_original_via_wbp_audit.json", {})
    source_restore = parsed.get("restore_verification_packet.json", {})
    source_trace = parsed.get("wbp_trace_observation_packet.json", {})
    source_apply = parsed.get("temporary_route_apply_execution_packet.json", {})
    source_write_surfaces = parsed.get("declared_write_surfaces_packet.json", {})

    source_summary_ok = (
        source_summary.get("status") == "ok"
        and source_summary.get("final_status")
        == "ORIGINAL_CODEX_VIA_WBP_TEMP_ROUTE_AND_RESTORE_PROVEN_WITH_LIMITS"
        and source_summary.get("original_route_proven") is True
        and source_summary.get("rollback_executed") is True
        and source_summary.get("restore_verified") is True
        and source_false_green.get("status") == "ok"
        and source_independent.get("status") == "ok"
        and source_restore.get("status") == "ok"
        and source_trace.get("status") == "ok"
        and source_apply.get("status") == "ok"
        and source_write_surfaces.get("status") == "ok"
    )
    packets["source_original_wbp_summary_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_original_wbp_summary_validation",
        "status": "ok" if source_summary_ok else "blocked",
        "source_summary_status": source_summary.get("status", "missing"),
        "source_summary_final_status": source_summary.get("final_status", ""),
        "source_false_green_status": source_false_green.get("status", "missing"),
        "source_independent_audit_status": source_independent.get("status", "missing"),
        "source_restore_status": source_restore.get("status", "missing"),
        "source_trace_status": source_trace.get("status", "missing"),
        "source_apply_status": source_apply.get("status", "missing"),
        "counts_as_general_original_works_claim": False,
        "counts_as_final_e2e_claim": False,
    }

    prestate = parsed.get("original_profile_before_packet.json", {})
    prestate_ok = (
        prestate.get("status") == "ok"
        and prestate.get("config_before_hash_or_absent_state_recorded") is True
        and prestate.get("native_original_launch_attempted") is False
        and prestate.get("original_profile_write_performed") is False
        and isinstance(prestate.get("config_toml"), dict)
        and prestate["config_toml"].get("hash_recorded") is True
    )
    packets["original_wbp_prestate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_prestate_import",
        "status": "ok" if prestate_ok else "blocked",
        "source_packet": str(source_evidence_dir / "original_profile_before_packet.json"),
        "declared_observed_surfaces_only": True,
        "config_before_hash_or_absent_state_recorded": (
            prestate.get("config_before_hash_or_absent_state_recorded") is True
        ),
        "config_toml_before_state": prestate.get("config_toml", {}),
        "auth_json_hash_recorded": prestate.get("auth_json_hash_recorded") is True,
        "auth_json_execution_dependency": (
            prestate.get("current_auth_json_execution_dependency") is True
        ),
        "counts_as_broad_original_filesystem_innocence": False,
    }

    write_surfaces_ok = (
        source_write_surfaces.get("status") == "ok"
        and source_write_surfaces.get("owner_authorization_required") is True
        and source_write_surfaces.get("owner_authorization_status") == "ok"
        and source_write_surfaces.get("original_codex_profile_write_allowed") is True
        and "/Users/kirillponomarev/.codex/config.toml"
        in source_write_surfaces.get("declared_write_surfaces", [])
    )
    packets["original_wbp_declared_write_surfaces_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_declared_write_surfaces_import",
        "status": "ok" if write_surfaces_ok else "blocked",
        "source_packet": str(source_evidence_dir / "declared_write_surfaces_packet.json"),
        "declared_write_surfaces": source_write_surfaces.get("declared_write_surfaces", []),
        "owner_authorization_required": (
            source_write_surfaces.get("owner_authorization_required") is True
        ),
        "owner_authorization_status": source_write_surfaces.get(
            "owner_authorization_status", "missing"
        ),
        "original_codex_profile_write_allowed": (
            source_write_surfaces.get("original_codex_profile_write_allowed") is True
        ),
        "current_probe_performed_original_write": False,
    }

    activation = parsed.get("temporary_route_apply_execution_packet.json", {})
    activation_ok = (
        activation.get("status") == "ok"
        and activation.get("apply_attempted") is True
        and activation.get("apply_succeeded") is True
        and activation.get("original_profile_write_performed") is True
        and activation.get("written_surfaces") == ["/Users/kirillponomarev/.codex/config.toml"]
    )
    packets["original_wbp_temporary_activation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_temporary_activation_import",
        "status": "ok" if activation_ok else "blocked",
        "source_packet": str(
            source_evidence_dir / "temporary_route_apply_execution_packet.json"
        ),
        "apply_attempted": activation.get("apply_attempted") is True,
        "apply_succeeded": activation.get("apply_succeeded") is True,
        "exact_target_path": activation.get("exact_target_path", ""),
        "written_surfaces": activation.get("written_surfaces", []),
        "activation_counts_as_route_success_proof": False,
        "activation_counts_as_reversibility_proof": False,
    }

    route_reference_ok = (
        source_trace.get("status") == "ok"
        and source_trace.get("route_status") == "confirmed"
        and source_trace.get("forwarded_to_wbp") is True
        and source_trace.get("request_observed") is True
        and source_trace.get("response_observed") is True
        and source_trace.get("upstream_status_ok") is True
    )
    packets["original_wbp_route_observation_reference_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_route_observation_reference",
        "status": "ok" if route_reference_ok else "blocked",
        "source_packet": str(source_evidence_dir / "wbp_trace_observation_packet.json"),
        "request_observed": source_trace.get("request_observed") is True,
        "response_observed": source_trace.get("response_observed") is True,
        "forwarded_to_wbp": source_trace.get("forwarded_to_wbp") is True,
        "upstream_status": source_trace.get("upstream_status"),
        "route_status": source_trace.get("route_status", "missing"),
        "route_observation_supporting_only": True,
        "route_observation_reopens_runtime_route_proof": False,
        "route_observation_counts_as_reversibility_proof": False,
    }

    restore = parsed.get("restore_verification_packet.json", {})
    rollback_point = parsed.get("rollback_point_packet.json", {})
    reversal_ok = (
        restore.get("status") == "ok"
        and restore.get("rollback_execution_attempted") is True
        and restore.get("restore_verified") is True
        and rollback_point.get("status") == "ok"
        and rollback_point.get("rollback_point_created") is True
        and rollback_point.get("rollback_point_verified") is True
    )
    packets["original_wbp_reversal_execution_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_reversal_execution_import",
        "status": "ok" if reversal_ok else "blocked",
        "restore_source_packet": str(source_evidence_dir / "restore_verification_packet.json"),
        "rollback_source_packet": str(source_evidence_dir / "rollback_point_packet.json"),
        "rollback_execution_attempted": restore.get("rollback_execution_attempted") is True,
        "restore_verified": restore.get("restore_verified") is True,
        "restore_matches_before": restore.get("restore_matches_before") is True,
        "rollback_point_created": rollback_point.get("rollback_point_created") is True,
        "rollback_point_verified": rollback_point.get("rollback_point_verified") is True,
        "reversal_executed_counts_as_reversibility_proof": False,
    }

    poststate_ok = (
        restore.get("status") == "ok"
        and restore.get("restore_matches_before") is True
        and isinstance(restore.get("before_state"), dict)
        and isinstance(restore.get("after_state"), dict)
        and restore["before_state"].get("sha256") == restore["after_state"].get("sha256")
    )
    packets["original_wbp_poststate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_poststate_import",
        "status": "ok" if poststate_ok else "blocked",
        "source_packet": str(source_evidence_dir / "restore_verification_packet.json"),
        "declared_observed_surfaces_only": True,
        "before_state": restore.get("before_state", {}),
        "after_state": restore.get("after_state", {}),
        "restore_matches_before": restore.get("restore_matches_before") is True,
        "observed_poststate_clean_counts_as_unobserved_surface_innocence": False,
    }

    classification_ok = (
        packets["source_original_wbp_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_original_wbp_summary_validation_packet.json"]["status"] == "ok"
        and packets["original_wbp_prestate_packet.json"]["status"] == "ok"
        and packets["original_wbp_declared_write_surfaces_packet.json"]["status"] == "ok"
        and packets["original_wbp_temporary_activation_packet.json"]["status"] == "ok"
        and packets["original_wbp_route_observation_reference_packet.json"]["status"]
        == "ok"
        and packets["original_wbp_reversal_execution_packet.json"]["status"] == "ok"
        and packets["original_wbp_poststate_packet.json"]["status"] == "ok"
    )
    packets["original_wbp_reversibility_classification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_reversibility_classification",
        "status": "ok" if classification_ok else "blocked",
        "final_status": (
            "ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE"
            if classification_ok
            else "ORIGINAL_CODEX_VIA_WBP_REVERSIBILITY_CLASSIFIED_WITH_LIMITS"
        ),
        "reversibility_proven_on_declared_observed_surfaces_only": classification_ok,
        "source_live_pass_imported": True,
        "current_owner_action_collected": False,
        "current_original_profile_write_performed": False,
        "route_observation_supporting_only": True,
        "general_original_works_claimed": False,
        "broad_original_filesystem_innocence_claimed": False,
        "final_e2e_claimed": False,
    }

    false_green_checks = [
        {
            "name": "reversal_executed_not_treated_as_reversibility_by_itself",
            "passed": packets["original_wbp_reversal_execution_packet.json"][
                "reversal_executed_counts_as_reversibility_proof"
            ]
            is False,
        },
        {
            "name": "route_observation_supporting_only",
            "passed": packets["original_wbp_route_observation_reference_packet.json"][
                "route_observation_supporting_only"
            ]
            is True,
        },
        {
            "name": "observed_poststate_not_widened_to_unobserved_surfaces",
            "passed": packets["original_wbp_poststate_packet.json"][
                "observed_poststate_clean_counts_as_unobserved_surface_innocence"
            ]
            is False,
        },
        {
            "name": "source_false_green_audit_ok",
            "passed": source_false_green.get("status") == "ok",
        },
        {
            "name": "no_general_original_or_final_e2e_claim",
            "passed": packets["original_wbp_reversibility_classification_packet.json"][
                "general_original_works_claimed"
            ]
            is False
            and packets["original_wbp_reversibility_classification_packet.json"][
                "final_e2e_claimed"
            ]
            is False,
        },
    ]
    packets["original_wbp_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(
            check["passed"] for check in false_green_checks
        ),
        "current_owner_action_collected": False,
        "source_live_pass_imported": True,
    }

    packets["independent_original_wbp_reversibility_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_original_wbp_reversibility_audit",
        "status": "ok"
        if packets["source_original_wbp_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["original_wbp_reversibility_classification_packet.json"]["status"] == "ok"
        and packets["original_wbp_false_green_audit.json"]["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "source_original_wbp_summary_validation_packet.json",
            "original_wbp_prestate_packet.json",
            "original_wbp_declared_write_surfaces_packet.json",
            "original_wbp_temporary_activation_packet.json",
            "original_wbp_route_observation_reference_packet.json",
            "original_wbp_reversal_execution_packet.json",
            "original_wbp_poststate_packet.json",
            "original_wbp_reversibility_classification_packet.json",
            "original_wbp_false_green_audit.json",
        ],
        "source_live_pass_imported": True,
        "current_owner_action_collected": False,
        "current_original_profile_write_performed": False,
        "general_original_works_claimed": False,
        "broad_original_filesystem_innocence_claimed": False,
        "final_e2e_claimed": False,
    }

    packets["original_wbp_reversibility_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_wbp_reversibility_summary",
        "status": packets["original_wbp_reversibility_classification_packet.json"]["status"],
        "final_status": packets["original_wbp_reversibility_classification_packet.json"][
            "final_status"
        ],
        "source_live_pass_imported": True,
        "current_owner_action_collected": False,
        "current_original_profile_write_performed": False,
        "source_evidence_dir": str(source_evidence_dir),
        "reversibility_proven_on_declared_observed_surfaces_only": classification_ok,
        "general_original_works_claimed": False,
        "broad_original_filesystem_innocence_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_evidence_dir = Path(args.source_evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
        )
    if not source_evidence_dir.exists():
        return _emit_input_error(
            reason_class="SOURCE_EVIDENCE_DIR_MISSING",
            message="--source-evidence-dir does not exist.",
            evidence_dir=evidence_dir,
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        packets = build_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            source_evidence_dir=source_evidence_dir,
        )
    except json.JSONDecodeError:
        return _emit_input_error(
            reason_class="SOURCE_PACKET_INVALID_JSON",
            message="A source packet was not valid JSON.",
            evidence_dir=evidence_dir,
        )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(
        json.dumps(
            packets["original_wbp_reversibility_summary_packet.json"],
            indent=2,
            sort_keys=True,
        )
    )
    return (
        0
        if packets["original_wbp_reversibility_summary_packet.json"]["status"] == "ok"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
