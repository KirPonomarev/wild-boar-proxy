#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

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

from wild_boar_proxy.native_launch_contract import (  # noqa: E402
    NATIVE_LAUNCH_MODES,
    build_native_launch_contract_packet,
)
from tools.historical_audit_fixtures import historical_audit_path  # noqa: E402


ACCELERATION_DIR = Path("audit_results/acceleration_and_throughput_classification_r1_2026-05-28")
FINAL_E2E_DIR = Path("audit_results/final_dual_lane_agent_workflow_e2e_r1_2026-05-28")
INTEGRITY_DIR = Path("audit_results/stronger_integrity_recheck_r1_2026-05-28")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    completed = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {completed.returncode}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _version_scope(repo_root: Path) -> dict[str, str]:
    return {
        "codex_cli_version": _run(repo_root, ["codex", "--version"]),
        "codex_cli_path": _run(repo_root, ["which", "codex"]),
        "codex_app_path": "/Applications/Codex.app",
        "codex_app_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        "codex_app_bundle_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
        ),
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
    }


def _required_inputs(repo_root: Path) -> dict[str, dict[str, Any]]:
    return {
        "lane_measurement_comparison": _read_json(
            historical_audit_path(repo_root, ACCELERATION_DIR / "lane_measurement_comparison_packet.json")
        ),
        "latency_classification": _read_json(
            historical_audit_path(repo_root, ACCELERATION_DIR / "latency_classification_packet.json")
        ),
        "measurement_integrity": _read_json(
            historical_audit_path(repo_root, ACCELERATION_DIR / "measurement_integrity_packet.json")
        ),
        "acceleration_non_claims": _read_json(
            historical_audit_path(repo_root, ACCELERATION_DIR / "acceleration_non_claims_packet.json")
        ),
        "final_runtime": _read_json(
            historical_audit_path(repo_root, FINAL_E2E_DIR / "final_dual_lane_runtime_packet.json")
        ),
        "final_integrity": _read_json(
            historical_audit_path(repo_root, FINAL_E2E_DIR / "final_dual_lane_integrity_packet.json")
        ),
        "integrity_strengthening": _read_json(
            historical_audit_path(repo_root, INTEGRITY_DIR / "integrity_strengthening_packet.json")
        ),
        "original_codex_untouched": _read_json(
            historical_audit_path(repo_root, INTEGRITY_DIR / "original_codex_untouched_packet.json")
        ),
    }


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del evidence_dir
    imported = _required_inputs(repo_root)
    version_scope = _version_scope(repo_root)
    launch_contract = build_native_launch_contract_packet()
    lane_comparison = imported["lane_measurement_comparison"]
    latency = imported["latency_classification"]
    integrity = imported["final_integrity"]
    integrity_strengthening = imported["integrity_strengthening"]
    untouched = imported["original_codex_untouched"]
    runtime = imported["final_runtime"]

    custom_measurement_source = str(latency.get("measurement_source_classification") or "")
    custom_packet_latency_present = bool(latency.get("packet_latency_surface_present"))
    custom_wall_clock_present = bool(latency.get("wall_clock_surface_present"))
    original_side_timing_visible = False
    original_side_request_count_visible = False
    original_side_token_usage_visible = False
    measurement_visibility_only = custom_packet_latency_present or custom_wall_clock_present
    launch_modes_cover_original_and_custom = set(launch_contract["allowed_launch_modes"]) == set(
        NATIVE_LAUNCH_MODES
    )
    version_scope_observed = bool(version_scope["codex_cli_path"] or version_scope["codex_app_path"])

    comparison_blocker = (
        "original_side_measurement_surface_absent_and_custom_side_remains_"
        "bounded_contour_local_runner_harness_only"
    )

    packets: dict[str, dict[str, Any]] = {}
    packets["original_vs_custom_comparability_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_vs_custom_comparability",
        "status": "ok",
        "launch_modes_cover_original_and_custom": launch_modes_cover_original_and_custom,
        "launch_modes": list(launch_contract["allowed_launch_modes"]),
        "same_binary_scope_observed": version_scope_observed,
        "same_binary_proven_for_measured_paths": False,
        "same_binary_scope_counts_as_same_path": False,
        "same_execution_path_proven": False,
        "execution_path_equivalence_classification": "unknown_or_divergent",
        "custom_measurement_source_classification": custom_measurement_source,
        "original_measurement_source_classification": "not_observed_in_admitted_inputs",
        "model_identity_classification": "not_cleanly_matched_for_original_vs_custom",
        "mode_effort_identity_classification": "mode_contract_only_not_runtime_matched",
        "task_shape_classification": "bounded_labels_only_not_reexecuted_across_both_paths",
        "measurement_visibility_does_not_prove_comparison_admissibility": False,
        "approximate_equivalence_counts_as_clean_acceleration": False,
        "comparison_admitted": False,
        "comparison_status": "limited_or_not_admitted",
        "comparison_blocker": comparison_blocker,
    }
    packets["acceleration_measurement_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "acceleration_measurement",
        "status": "ok",
        "custom_packet_latency_surface_present": custom_packet_latency_present,
        "custom_wall_clock_surface_present": custom_wall_clock_present,
        "custom_chatgpt_lane_median_packet_latency_ms": latency.get(
            "chatgpt_lane_median_packet_latency_ms"
        ),
        "custom_api_lane_median_packet_latency_ms": latency.get("api_lane_median_packet_latency_ms"),
        "custom_chatgpt_lane_median_wall_clock_ms": latency.get(
            "chatgpt_lane_median_wall_clock_ms"
        ),
        "custom_api_lane_median_wall_clock_ms": latency.get("api_lane_median_wall_clock_ms"),
        "custom_measurement_source_classification": custom_measurement_source,
        "original_side_timing_visible": original_side_timing_visible,
        "original_side_request_count_visible": original_side_request_count_visible,
        "original_side_token_usage_visible": original_side_token_usage_visible,
        "visible_timing_fields_authorize_comparison": False,
        "measurement_surface_truth_only": measurement_visibility_only,
    }
    packets["acceleration_classification_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "acceleration_classification",
        "status": "ok",
        "final_status": "ORIGINAL_VS_CUSTOM_ACCELERATION_RECONCILIATION_CLASSIFIED_WITH_LIMITS",
        "prior_comparison_status": lane_comparison.get("comparison_status"),
        "prior_comparison_blocker": lane_comparison.get("comparison_blocker"),
        "current_comparison_status": "limited_or_not_admitted",
        "current_comparison_blocker": comparison_blocker,
        "prior_limiter_reduced": False,
        "blocker_refined_here": True,
        "known_blocker_localized": True,
        "observed_acceleration_claim_admitted": False,
        "bounded_observed_acceleration_implies_product_wide_gain": False,
        "timing_difference_implies_quality_superiority": False,
        "same_binary_clean_proof_observed": False,
        "integrity_boundary_kept_separate": True,
        "history_boundary_reopened": False,
        "final_e2e_runtime_imported_without_reproof": True,
        "original_codex_untouched_scope_only": untouched.get(
            "original_codex_untouched_within_admitted_scope"
        )
        is True,
        "ambient_drift_still_blocks_stronger_integrity": integrity.get(
            "ambient_protected_surface_drift_can_block_stronger_claims"
        )
        is True,
        "integrity_blocker_localized_as_ambient_external": integrity_strengthening.get(
            "current_integrity_classification"
        )
        == "integrity_blocker_localized_as_ambient_external",
        "same_custom_codex_environment_proven_for_dual_lane_flow": runtime.get(
            "same_custom_codex_environment"
        )
        is True,
    }
    packets["acceleration_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "acceleration_non_claims",
        "status": "ok",
        "timing_difference_implies_quality_superiority": False,
        "provider_declared_fast_path_equals_observed_acceleration": False,
        "imported_earlier_timing_packets_alone_prove_original_vs_custom_acceleration": False,
        "one_bounded_comparison_proves_broad_product_acceleration": False,
        "visible_timing_fields_alone_authorize_comparison": False,
        "same_binary_alone_proves_fair_acceleration_comparison": False,
        "bounded_observed_acceleration_implies_product_wide_speed_gain": False,
        "approximate_model_mode_equivalence_yields_clean_acceleration_proof": False,
    }
    packets["acceleration_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "acceleration_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "original_side_timing_surface_not_observed_in_admitted_inputs",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "same_binary_not_proven_for_measured_paths",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "execution_path_equivalence_not_proven",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "model_mode_equivalence_remains_contract_only",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "bounded_measurements_do_not_prove_product_wide_speed_gain",
                "severity": "medium",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "visible_timing_data_treated_as_sufficient_comparison_proof": False,
        "same_binary_treated_as_same_path": False,
        "partial_equivalence_treated_as_clean_comparability": False,
        "bounded_acceleration_treated_as_broad_product_speedup": False,
        "timing_treated_as_quality_gain": False,
        "imported_packets_treated_as_reproven_acceleration": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "custom_side_measurement_surfaces_exist_but_remain_contour_local_only",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "original_side_timing_surface_absent_in_admitted_inputs",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "same_binary_scope_observation_does_not_upgrade_path_equivalence",
                "severity": "high",
                "status": "confirmed",
            },
            {
                "id": "clean_original_vs_custom_acceleration_claim_remains_not_admitted",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    return packets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    packets = build_packets(
        repo_root=args.repo_root.resolve(),
        evidence_dir=args.evidence_dir.resolve(),
    )
    for filename, payload in packets.items():
        json_write(args.evidence_dir / filename, payload)
    summary = {
        "status": "ok",
        "packet_count": len(packets),
        "evidence_dir": str(args.evidence_dir.resolve()),
        "packets": sorted(packets),
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
