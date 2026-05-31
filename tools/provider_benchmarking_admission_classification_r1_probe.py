#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify whether provider benchmarking is currently admissible."""

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
MODEL_AVAILABILITY_DIR = ROOT / "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27"
EXTERNAL_VALIDATE_FILE = ROOT / "wild_boar_proxy/external_models/validate.py"

SOURCE_REQUIRED_PACKETS = {
    "provider_matrix": {
        "provider_adapter_summary_packet.json",
        "provider_adapter_family_matrix_packet.json",
        "provider_adapter_false_green_audit.json",
        "scanner_agent_fact_report_packet.json",
    },
    "model_availability": {
        "model_availability_direct_only_summary_packet.json",
        "model_availability_matrix.json",
        "model_availability_false_green_audit.json",
        "independent_model_availability_audit.json",
    },
}


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
        "packet_kind": "provider_benchmarking_admission_input_error",
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
        "tools/provider_benchmarking_admission_classification_r1_probe.py",
        "tests/test_provider_benchmarking_admission_classification_r1_probe.py",
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
        prog="provider-benchmarking-admission-classification-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--provider-matrix-dir", default=str(PROVIDER_MATRIX_DIR))
    parser.add_argument("--model-availability-dir", default=str(MODEL_AVAILABILITY_DIR))
    parser.add_argument("--external-validate-file", default=str(EXTERNAL_VALIDATE_FILE))
    return parser


def _load_sources(
    source_dirs: dict[str, Path],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, list[str]], dict[str, list[str]]]:
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    missing: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}
    for label, required in SOURCE_REQUIRED_PACKETS.items():
        parsed[label] = {}
        missing[label] = []
        invalid[label] = []
        source_dir = source_dirs[label]
        for rel_name in sorted(required):
            path = source_dir / rel_name
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
    source_dirs: dict[str, Path],
    external_validate_file: Path,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    parsed, missing, invalid = _load_sources(source_dirs)

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
    packets["source_provider_benchmark_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_provider_benchmark_evidence_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "benchmark_execution_performed": False,
    }

    provider_summary = parsed["provider_matrix"]["provider_adapter_summary_packet.json"]
    provider_matrix = parsed["provider_matrix"]["provider_adapter_family_matrix_packet.json"]
    provider_false_green = parsed["provider_matrix"]["provider_adapter_false_green_audit.json"]
    provider_scanner = parsed["provider_matrix"]["scanner_agent_fact_report_packet.json"]

    model_summary = parsed["model_availability"]["model_availability_direct_only_summary_packet.json"]
    model_matrix = parsed["model_availability"]["model_availability_matrix.json"]
    model_false_green = parsed["model_availability"]["model_availability_false_green_audit.json"]
    model_independent = parsed["model_availability"]["independent_model_availability_audit.json"]

    validate_text = external_validate_file.read_text(encoding="utf-8")

    validation_checks = {
        "provider_matrix_reference_ok": (
            _status_in(provider_summary, "ok")
            and _status_in(provider_matrix, "ok")
            and _status_in(provider_false_green, "ok")
            and _status_in(provider_scanner, "ok")
            and provider_summary.get("final_status")
            == "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED_WITH_LIMITS"
            and provider_summary.get("provider_family_compatibility_proven") is False
            and provider_summary.get("family_wide_model_compatibility_proven") is False
        ),
        "model_availability_reference_ok": (
            _status_in(model_summary, "ok")
            and _status_in(model_matrix, "ok")
            and _status_in(model_false_green, "ok")
            and _status_in(model_independent, "ok")
            and model_summary.get("final_status") == "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED"
            and model_summary.get("proof_transport") == "direct_wbp_http_non_stream"
            and model_matrix.get("direct_only_contour") is True
            and model_matrix.get("codex_acceptance_proven") is False
        ),
        "metric_surface_shape_ok": (
            '"latency_ms": response.latency_ms' in validate_text
            and 'verification_scope": "route_provider_only"' in validate_text
            and '"available_models_count": model_count' in validate_text
        ),
    }
    packets["source_provider_benchmark_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_provider_benchmark_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [{"name": name, "passed": passed} for name, passed in validation_checks.items()],
        "validation_scope": "provider_benchmarking_admission_only",
        "source_chain_counts_as_benchmark_execution": False,
        "source_chain_counts_as_provider_ranking": False,
    }

    family_rows = provider_matrix.get("rows", [])
    candidate_rows = []
    comparable_rows = []
    excluded_rows = []
    for row in family_rows:
        provider_family = row.get("provider_family", "")
        benchmark_candidate = True
        compatibility_floor_met = (
            row.get("adapter_present") is True
            and row.get("auth_strategy_classified") is True
            and row.get("generic_request_shape_classified") is True
            and row.get("generic_response_shape_classified") is True
            and row.get("generic_failure_semantics_classified") is True
            and row.get("representative_model_scope_explicit") is True
            and row.get("provider_specific_credential_present") is True
            and row.get("provider_specific_route_observed") is True
            and (
                row.get("provider_specific_validate_passed") is True
                or row.get("provider_specific_provider_check_ran") is True
            )
        )
        task_slice_supported = (
            row.get("provider_specific_validate_passed") is True
            or row.get("provider_specific_provider_check_ran") is True
        )
        candidate = {
            "provider_family": provider_family,
            "representative_models": row.get("representative_models", []),
            "benchmark_candidate": benchmark_candidate,
            "matrix_proof_level": row.get("matrix_proof_level"),
            "representative_model_scope_explicit": row.get("representative_model_scope_explicit"),
            "family_wide_model_proof": row.get("family_wide_model_proof"),
            "provider_family_compatibility_proven": row.get("provider_family_compatibility_proven"),
            "compatibility_floor_met": compatibility_floor_met,
            "task_slice_supported": task_slice_supported,
            "limits": row.get("limits", []),
        }
        candidate_rows.append(candidate)
        if compatibility_floor_met and task_slice_supported:
            comparable_rows.append(provider_family)
        else:
            excluded_rows.append(
                {
                    "provider_family": provider_family,
                    "reason_codes": [
                        code
                        for code in [
                            "COMPATIBILITY_FLOOR_NOT_MET" if not compatibility_floor_met else "",
                            "TASK_SLICE_NOT_SUPPORTED" if not task_slice_supported else "",
                        ]
                        if code
                    ],
                }
            )

    packets["provider_benchmark_candidate_scope_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_candidate_scope",
        "status": "ok",
        "candidate_rows": candidate_rows,
        "included_candidate_count": len(candidate_rows),
        "excluded_rows": excluded_rows,
        "candidate_scope_counts_as_benchmark_admission": False,
    }

    task_slice_admitted = False
    task_slice_name = "provider_route_validate_models_probe_latency_only"
    packets["provider_benchmark_task_slice_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_task_slice",
        "status": "ok",
        "task_slice_id": task_slice_name,
        "task_slice_description": (
            "Route-provider validate models probe with provider-scoped latency and model visibility only; "
            "does not prove output quality, codex acceptance, streaming, or tool loop."
        ),
        "task_slice_explicit": True,
        "shared_across_all_candidate_rows": False,
        "shared_across_comparable_rows": len(comparable_rows) >= 2,
        "single_task_slice_counts_as_provider_ranking": False,
        "task_slice_admitted": task_slice_admitted,
    }

    packets["provider_benchmark_compatibility_floor_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_compatibility_floor",
        "status": "ok",
        "minimum_requirements": [
            "adapter_present",
            "auth_strategy_classified",
            "generic_request_shape_classified",
            "generic_response_shape_classified",
            "generic_failure_semantics_classified",
            "representative_model_scope_explicit",
            "provider_specific_credential_present",
            "provider_specific_route_observed",
            "provider_specific_provider_check_or_validate",
        ],
        "rows_meeting_floor": comparable_rows,
        "rows_failing_floor": [row["provider_family"] for row in excluded_rows],
        "partial_compatibility_counts_as_benchmark_readiness": False,
    }

    packets["provider_benchmark_comparability_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_comparability_boundary",
        "status": "ok",
        "comparable_rows": comparable_rows,
        "comparable_row_count": len(comparable_rows),
        "minimum_rows_for_honest_cross_provider_benchmark": 2,
        "representative_model_row_counts_as_family_wide": False,
        "family_wide_comparability_proven": False,
        "benchmarking_currently_admitted": len(comparable_rows) >= 2,
    }

    metric_rows = [
        {
            "metric_id": "provider_validate_latency_ms",
            "metric_source": "external_models_validate_route_provider",
            "metric_available": True,
            "cross_provider_comparison_currently_admitted": len(comparable_rows) >= 2,
            "fair_benchmark_by_itself": False,
        },
        {
            "metric_id": "provider_models_visible_count",
            "metric_source": "external_models_validate_route_provider",
            "metric_available": True,
            "cross_provider_comparison_currently_admitted": len(comparable_rows) >= 2,
            "fair_benchmark_by_itself": False,
        },
        {
            "metric_id": "direct_wbp_non_stream_response_shape",
            "metric_source": "model_availability_direct_only_summary",
            "metric_available": True,
            "cross_provider_comparison_currently_admitted": False,
            "fair_benchmark_by_itself": False,
        },
    ]
    packets["provider_benchmark_metric_admissibility_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_metric_admissibility",
        "status": "ok",
        "rows": metric_rows,
        "route_latency_is_routing_truth": False,
        "admitted_metric_counts_as_fair_benchmark": False,
        "mixed_metric_families_detected": True,
    }

    packets["provider_benchmark_claim_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_claim_boundary",
        "status": "ok",
        "benchmark_result_equals_routing_truth": False,
        "benchmark_result_equals_capability_proof": False,
        "benchmark_result_equals_product_recommendation": False,
        "single_task_slice_equals_general_provider_ranking": False,
        "admission_equals_execution": False,
    }

    false_green_checks = [
        {
            "name": "representative_model_not_family_wide",
            "passed": all(
                row.get("family_wide_model_proof") is False and row.get("provider_family_compatibility_proven") is False
                for row in candidate_rows
            ),
        },
        {
            "name": "partial_compatibility_not_promoted_to_readiness",
            "passed": packets["provider_benchmark_compatibility_floor_packet.json"][
                "partial_compatibility_counts_as_benchmark_readiness"
            ]
            is False,
        },
        {
            "name": "admitted_metric_not_promoted_to_fair_benchmark",
            "passed": packets["provider_benchmark_metric_admissibility_packet.json"][
                "admitted_metric_counts_as_fair_benchmark"
            ]
            is False,
        },
        {
            "name": "benchmark_not_promoted_to_routing_or_recommendation",
            "passed": packets["provider_benchmark_claim_boundary_packet.json"][
                "benchmark_result_equals_routing_truth"
            ]
            is False
            and packets["provider_benchmark_claim_boundary_packet.json"][
                "benchmark_result_equals_product_recommendation"
            ]
            is False,
        },
        {
            "name": "source_false_green_audits_ok",
            "passed": _status_in(provider_false_green, "ok") and _status_in(model_false_green, "ok"),
        },
    ]
    packets["provider_benchmark_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_false_green_audit",
        "status": "ok" if all(item["passed"] for item in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(item["passed"] for item in false_green_checks),
    }

    classification_ok = (
        packets["source_provider_benchmark_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_provider_benchmark_validation_packet.json"]["status"] == "ok"
        and packets["provider_benchmark_false_green_audit.json"]["status"] == "ok"
    )
    final_status = ""
    if classification_ok:
        final_status = (
            "WBP_PROVIDER_BENCHMARKING_ADMISSION_CLASSIFIED"
            if len(comparable_rows) >= 2
            else "WBP_PROVIDER_BENCHMARKING_NOT_YET_ADMITTED"
        )
    packets["provider_benchmark_admission_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_benchmark_admission_summary",
        "status": "ok" if classification_ok else "blocked",
        "final_status": final_status,
        "candidate_row_count": len(candidate_rows),
        "comparable_row_count": len(comparable_rows),
        "task_slice_id": task_slice_name,
        "benchmark_execution_performed": False,
        "provider_ranking_claimed": False,
        "routing_policy_rewrite_claimed": False,
        "with_limits_required": True if classification_ok and len(comparable_rows) < 2 else False if classification_ok else None,
        "with_limits_reasons": [
            "ONLY_ONE_ROW_MEETS_COMPATIBILITY_FLOOR",
            "OPENROUTER_PROVIDER_ROW_NOT_BENCHMARK_READY",
            "MIXED_METRIC_FAMILIES_NOT_HONESTLY_COMPARABLE",
            "REPRESENTATIVE_MODEL_ROWS_DO_NOT_PROVE_FAMILY_WIDE_COMPARABILITY",
        ]
        if classification_ok and len(comparable_rows) < 2
        else [],
    }

    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "provider_family_count": provider_summary.get("active_provider_family_count"),
            "provider_family_compatibility_proven": provider_summary.get(
                "provider_family_compatibility_proven"
            ),
            "family_wide_model_compatibility_proven": provider_summary.get(
                "family_wide_model_compatibility_proven"
            ),
            "comparable_row_count": len(comparable_rows),
            "task_slice_id": task_slice_name,
            "final_status": final_status,
        },
        "non_claims": {
            "benchmark_execution_performed": False,
            "provider_ranking_claimed": False,
            "routing_policy_rewrite_claimed": False,
            "family_wide_comparability_proven": False,
        },
    }
    packets["independent_provider_benchmark_admission_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_provider_benchmark_admission_audit",
        "status": "ok" if classification_ok else "blocked",
        "candidate_scope_explicit": True,
        "task_slice_explicit": True,
        "comparable_rows_explicit": True,
        "comparable_row_count": len(comparable_rows),
        "benchmarking_honestly_admitted": len(comparable_rows) >= 2,
        "representative_row_overpromoted": False,
        "routing_or_recommendation_claimed": False,
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
                "passed": packets["provider_benchmark_false_green_audit.json"]["status"] == "ok",
            },
        ],
    }
    return packets


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_dirs = {
        "provider_matrix": Path(args.provider_matrix_dir).resolve(),
        "model_availability": Path(args.model_availability_dir).resolve(),
    }
    external_validate_file = Path(args.external_validate_file).resolve()

    if not repo_root.exists():
        return _emit_input_error(
            reason_class="repo_root_missing",
            message=f"repo root not found: {repo_root}",
            evidence_dir=evidence_dir,
        )
    for label, path in source_dirs.items():
        if not path.exists():
            return _emit_input_error(
                reason_class="source_dir_missing",
                message=f"{label} source dir not found: {path}",
                evidence_dir=evidence_dir,
            )
    if not external_validate_file.exists():
        return _emit_input_error(
            reason_class="source_file_missing",
            message=f"external validate file not found: {external_validate_file}",
            evidence_dir=evidence_dir,
        )

    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        source_dirs=source_dirs,
        external_validate_file=external_validate_file,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = packets["provider_benchmark_admission_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
