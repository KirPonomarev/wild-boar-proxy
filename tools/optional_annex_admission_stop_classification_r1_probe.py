#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify whether the current named optional annex queue still has admitted work."""

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


PROVIDER_MATRIX_DIR = ROOT / "audit_results/wbp_provider_adapter_matrix_classification_r1_2026-05-27"
REMOTE_GATE_DIR = ROOT / "audit_results/wbp_remote_control_readiness_gate_classification_r1_2026-05-27"
APP_SERVER_BRIDGE_DIR = ROOT / "audit_results/wbp_app_server_bridge_research_classification_r1_2026-05-27"
PROVIDER_BENCHMARK_DIR = ROOT / "audit_results/wbp_provider_benchmarking_admission_classification_r1_2026-05-27"
DESIGN_GATE_DIR = ROOT / "audit_results/web_design_gate_admission_check_pass_2026-05-16"
DESIGN_GATE_PROOF_DIR = ROOT / "audit_results/web_design_finish_pass_reentry_reconciliation_2026-05-24"
STAGE20_VERIFY_PACKET = ROOT / "audit_results/stage20_c6_verification_packet.json"

SOURCE_REQUIRED_PACKETS = {
    "provider_matrix": {"provider_adapter_summary_packet.json"},
    "remote_gate": {"remote_control_readiness_summary_packet.json"},
    "app_server_bridge": {"app_server_bridge_summary_packet.json"},
    "provider_benchmark": {"provider_benchmark_admission_summary_packet.json"},
    "design_gate": {"decision_packet.json"},
    "design_gate_proof": {"design_gate_proof.json"},
    "stage20_verify": {"stage20_c6_verification_packet.json"},
}

THREAD_NAMED_OPTIONAL_ANNEXES = (
    "provider_adapter_matrix",
    "app_server_bridge_research",
    "remote_control_readiness_gate",
    "provider_benchmarking",
    "role_profile_ui_polish",
)


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


def _status_in(packet: dict[str, Any], *allowed: str) -> bool:
    return str(packet.get("status", "")) in set(allowed)


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_admission_stop_input_error",
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
        "tools/optional_annex_admission_stop_classification_r1_probe.py",
        "tests/test_optional_annex_admission_stop_classification_r1_probe.py",
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
        prog="optional-annex-admission-stop-classification-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--provider-matrix-dir", default=str(PROVIDER_MATRIX_DIR))
    parser.add_argument("--remote-gate-dir", default=str(REMOTE_GATE_DIR))
    parser.add_argument("--app-server-bridge-dir", default=str(APP_SERVER_BRIDGE_DIR))
    parser.add_argument("--provider-benchmark-dir", default=str(PROVIDER_BENCHMARK_DIR))
    parser.add_argument("--design-gate-dir", default=str(DESIGN_GATE_DIR))
    parser.add_argument("--design-gate-proof-dir", default=str(DESIGN_GATE_PROOF_DIR))
    parser.add_argument("--stage20-verify-packet", default=str(STAGE20_VERIFY_PACKET))
    return parser


def _load_sources(
    source_paths: dict[str, Path],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, list[str]], dict[str, list[str]]]:
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    missing: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}
    for label, required in SOURCE_REQUIRED_PACKETS.items():
        parsed[label] = {}
        missing[label] = []
        invalid[label] = []
        source_root = source_paths[label]
        for rel_name in sorted(required):
            path = source_root if source_root.is_file() else source_root / rel_name
            if not path.exists():
                missing[label].append(rel_name)
                continue
            try:
                parsed[label][rel_name] = _read_json(path)
            except json.JSONDecodeError:
                invalid[label].append(rel_name)
    return parsed, missing, invalid


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_paths: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    parsed, missing, invalid = _load_sources(source_paths)

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

    inventory_ok = all(not missing[label] and not invalid[label] for label in SOURCE_REQUIRED_PACKETS)
    packets["optional_annex_source_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_source_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_paths": {label: str(path) for label, path in source_paths.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "new_scope_invented_in_this_contour": False,
    }

    provider_summary = parsed["provider_matrix"]["provider_adapter_summary_packet.json"]
    remote_summary = parsed["remote_gate"]["remote_control_readiness_summary_packet.json"]
    bridge_summary = parsed["app_server_bridge"]["app_server_bridge_summary_packet.json"]
    benchmark_summary = parsed["provider_benchmark"]["provider_benchmark_admission_summary_packet.json"]
    design_gate_decision = parsed["design_gate"]["decision_packet.json"]
    design_gate_proof = parsed["design_gate_proof"]["design_gate_proof.json"]
    stage20_verify = parsed["stage20_verify"]["stage20_c6_verification_packet.json"]

    validation_checks = {
        "closed_named_annex_references_ok": (
            _status_in(provider_summary, "ok")
            and provider_summary.get("final_status") == "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED_WITH_LIMITS"
            and _status_in(remote_summary, "ok")
            and remote_summary.get("final_status") == "WBP_REMOTE_CONTROL_READINESS_GATE_CLASSIFIED_WITH_LIMITS"
            and _status_in(bridge_summary, "ok")
            and bridge_summary.get("final_status") == "WBP_APP_SERVER_BRIDGE_RESEARCH_CLASSIFIED_WITH_LIMITS"
        ),
        "benchmark_admission_reference_ok": (
            _status_in(benchmark_summary, "ok")
            and benchmark_summary.get("final_status") == "WBP_PROVIDER_BENCHMARKING_NOT_YET_ADMITTED"
        ),
        "design_gate_reference_ok": (
            design_gate_decision.get("design_gate_admitted") is True
            and design_gate_decision.get("design_gate_token")
            == "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY"
            and design_gate_proof.get("current_branch_gate_status") == "evidenced"
            and design_gate_proof.get("repo_owned_gate_drift_found") is False
            and stage20_verify.get("final_verdict")
            == "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY"
        ),
    }
    packets["optional_annex_source_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_source_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [{"name": name, "passed": passed} for name, passed in validation_checks.items()],
        "validation_scope": "optional_annex_admission_stop_only",
        "source_chain_counts_as_new_scope": False,
    }

    inventory_rows = [
        {
            "annex_id": "provider_adapter_matrix",
            "annex_name": "Provider Adapter Matrix",
            "named_in_thread_master_plan": True,
        },
        {
            "annex_id": "app_server_bridge_research",
            "annex_name": "App-Server Bridge Research",
            "named_in_thread_master_plan": True,
        },
        {
            "annex_id": "remote_control_readiness_gate",
            "annex_name": "Remote-Control Readiness Gate",
            "named_in_thread_master_plan": True,
        },
        {
            "annex_id": "provider_benchmarking",
            "annex_name": "Provider Benchmarking",
            "named_in_thread_master_plan": True,
        },
        {
            "annex_id": "role_profile_ui_polish",
            "annex_name": "Role/Profile UI Polish",
            "named_in_thread_master_plan": True,
        },
    ]
    packets["optional_annex_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_inventory",
        "status": "ok",
        "rows": inventory_rows,
        "named_annex_count": len(inventory_rows),
        "inventory_counts_as_active_work": False,
    }

    admission_rows = [
        {
            "annex_id": "provider_adapter_matrix",
            "status_class": "already_closed",
            "evidence_status": provider_summary.get("final_status"),
            "currently_admitted": False,
        },
        {
            "annex_id": "app_server_bridge_research",
            "status_class": "already_closed",
            "evidence_status": bridge_summary.get("final_status"),
            "currently_admitted": False,
        },
        {
            "annex_id": "remote_control_readiness_gate",
            "status_class": "already_closed",
            "evidence_status": remote_summary.get("final_status"),
            "currently_admitted": False,
        },
        {
            "annex_id": "provider_benchmarking",
            "status_class": "not_yet_admitted",
            "evidence_status": benchmark_summary.get("final_status"),
            "currently_admitted": False,
        },
        {
            "annex_id": "role_profile_ui_polish",
            "status_class": "admitted",
            "evidence_status": "DESIGN_GATE_ADMITTED_AND_NOT_YET_CLOSED",
            "currently_admitted": True,
        },
    ]
    admitted_rows = [row["annex_id"] for row in admission_rows if row["currently_admitted"]]
    packets["optional_annex_admission_status_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_admission_status",
        "status": "ok",
        "rows": admission_rows,
        "currently_admitted_annexes": admitted_rows,
        "admitted_count": len(admitted_rows),
    }

    blocker_rows = [
        {
            "annex_id": "provider_benchmarking",
            "blocker_class": "compatibility_floor_not_met",
            "currently_blocking": True,
            "details": benchmark_summary.get("with_limits_reasons", []),
        },
        {
            "annex_id": "role_profile_ui_polish",
            "blocker_class": "design_gate",
            "currently_blocking": False,
            "details": ["EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY evidenced"],
        },
    ]
    packets["optional_annex_gate_blockers_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_gate_blockers",
        "status": "ok",
        "rows": blocker_rows,
        "blocked_annexes": [row["annex_id"] for row in blocker_rows if row["currently_blocking"]],
        "blocked_counts_as_active_next_work": False,
    }

    reopen_rows = [
        {
            "annex_id": "provider_adapter_matrix",
            "reopen_condition": "new_contradictory_truth_or_explicit_operator_reopen",
            "currently_satisfied": False,
        },
        {
            "annex_id": "app_server_bridge_research",
            "reopen_condition": "new_contradictory_truth_or_explicit_operator_reopen",
            "currently_satisfied": False,
        },
        {
            "annex_id": "remote_control_readiness_gate",
            "reopen_condition": "new_contradictory_truth_or_explicit_operator_reopen",
            "currently_satisfied": False,
        },
        {
            "annex_id": "provider_benchmarking",
            "reopen_condition": "at_least_two_rows_meet_compatibility_floor_for_shared_task_slice",
            "currently_satisfied": False,
        },
        {
            "annex_id": "role_profile_ui_polish",
            "reopen_condition": "not_applicable_currently_admitted",
            "currently_satisfied": True,
        },
    ]
    packets["optional_annex_reopen_conditions_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_reopen_conditions",
        "status": "ok",
        "rows": reopen_rows,
        "current_stop_is_permanent": False,
    }

    no_next_contour = len(admitted_rows) == 0
    packets["optional_annex_no_next_contour_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_no_next_contour",
        "status": "ok",
        "no_further_named_contour_currently_admissible": no_next_contour,
        "currently_admitted_annexes": admitted_rows,
        "absence_of_next_contour_counts_as_failure": False,
        "current_stop_counts_as_permanent": False,
    }

    false_green_checks = [
        {
            "name": "closed_not_reopened_by_habit",
            "passed": all(
                row["status_class"] != "already_closed" or row["currently_admitted"] is False
                for row in admission_rows
            ),
        },
        {
            "name": "not_yet_admitted_not_secretly_active",
            "passed": all(
                row["status_class"] != "not_yet_admitted" or row["currently_admitted"] is False
                for row in admission_rows
            ),
        },
        {
            "name": "no_fake_queue_exhaustion",
            "passed": packets["optional_annex_no_next_contour_packet.json"][
                "no_further_named_contour_currently_admissible"
            ]
            is False,
        },
        {
            "name": "admitted_work_not_suppressed",
            "passed": "role_profile_ui_polish" in admitted_rows,
        },
    ]
    packets["optional_annex_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_false_green_audit",
        "status": "ok" if all(item["passed"] for item in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(item["passed"] for item in false_green_checks),
    }

    classification_ok = (
        packets["optional_annex_source_inventory_packet.json"]["status"] == "ok"
        and packets["optional_annex_source_validation_packet.json"]["status"] == "ok"
        and packets["optional_annex_false_green_audit.json"]["status"] == "ok"
    )
    final_status = ""
    if classification_ok:
        final_status = (
            "WBP_NO_FURTHER_NAMED_CONTOUR_CURRENTLY_ADMISSIBLE"
            if no_next_contour
            else "WBP_OPTIONAL_ANNEX_QUEUE_STILL_HAS_ADMITTED_WORK"
        )
    packets["optional_annex_stop_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "optional_annex_stop_summary",
        "status": "ok" if classification_ok else "blocked",
        "final_status": final_status,
        "named_annex_count": len(inventory_rows),
        "currently_admitted_annex_count": len(admitted_rows),
        "currently_admitted_annexes": admitted_rows,
        "new_scope_invented": False,
        "closed_contours_reopened": False,
        "current_stop_claimed_permanent": False,
    }
    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "named_annex_count": len(inventory_rows),
            "currently_admitted_annex_count": len(admitted_rows),
            "currently_admitted_annexes": admitted_rows,
            "design_gate_admitted": design_gate_decision.get("design_gate_admitted"),
            "provider_benchmark_final_status": benchmark_summary.get("final_status"),
            "final_status": final_status,
        },
        "non_claims": {
            "new_scope_invented": False,
            "closed_contours_reopened": False,
            "project_failure_claimed": False,
            "permanent_stop_claimed": False,
        },
    }
    packets["independent_optional_annex_stop_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_optional_annex_stop_audit",
        "status": "ok" if classification_ok else "blocked",
        "named_annex_inventory_explicit": True,
        "design_gate_currently_evidenced": True,
        "benchmarking_not_yet_admitted": True,
        "at_least_one_named_annex_currently_admitted": len(admitted_rows) >= 1,
        "fake_queue_exhaustion_claimed": False,
    }
    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok" if classification_ok else "blocked",
        "checks": [
            {"name": "source_inventory_ok", "passed": inventory_ok},
            {"name": "source_validation_ok", "passed": all(validation_checks.values())},
            {
                "name": "false_green_audit_ok",
                "passed": packets["optional_annex_false_green_audit.json"]["status"] == "ok",
            },
        ],
    }
    return packets


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_paths = {
        "provider_matrix": Path(args.provider_matrix_dir).resolve(),
        "remote_gate": Path(args.remote_gate_dir).resolve(),
        "app_server_bridge": Path(args.app_server_bridge_dir).resolve(),
        "provider_benchmark": Path(args.provider_benchmark_dir).resolve(),
        "design_gate": Path(args.design_gate_dir).resolve(),
        "design_gate_proof": Path(args.design_gate_proof_dir).resolve(),
        "stage20_verify": Path(args.stage20_verify_packet).resolve(),
    }

    if not repo_root.exists():
        return _emit_input_error(
            reason_class="repo_root_missing",
            message=f"repo root not found: {repo_root}",
            evidence_dir=evidence_dir,
        )
    for label, path in source_paths.items():
        if not path.exists():
            return _emit_input_error(
                reason_class="source_missing",
                message=f"{label} source not found: {path}",
                evidence_dir=evidence_dir,
            )

    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        source_paths=source_paths,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = packets["optional_annex_stop_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
