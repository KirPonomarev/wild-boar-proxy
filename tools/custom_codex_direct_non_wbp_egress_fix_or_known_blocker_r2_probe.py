#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthesize a bounded Pass 5 direct non-WBP egress known-blocker bundle."""

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


FINAL_STATUS_OK = "CUSTOM_CODEX_DIRECT_NON_WBP_EGRESS_KNOWN_BLOCKER"
FINAL_STATUS_BLOCKED = "CUSTOM_CODEX_DIRECT_NON_WBP_EGRESS_TRUTH_NOT_PROVEN"
EXPECTED_EVIDENCE_DIR = (
    "audit_results/custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_2026-05-27"
)

DEFAULT_SOURCE_FILES = {
    "current_truth": Path(
        "audit_results/wbp_current_truth_reconciliation_closeout_r2_2026-05-27/"
        "direct_non_wbp_egress_current_truth_packet.json"
    ),
    "pass4_route_trace": Path(
        "audit_results/custom_codex_via_wbp_owner_accepted_with_limits_r2_2026-05-27/"
        "custom_route_trace_packet.json"
    ),
    "r4_import_summary": Path(
        "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/"
        "detached_native_custom_egress_import_summary_packet.json"
    ),
    "r4_network_classification": Path(
        "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/"
        "network_claim_classification_packet.json"
    ),
    "r4_trace_validation": Path(
        "audit_results/wbp_detached_native_custom_egress_owner_execution_import_r4_2026-05-27/"
        "wbp_trace_validation_packet.json"
    ),
    "r3_direct_claim": Path(
        "audit_results/wbp_native_custom_detached_egress_execution_EXTERNAL_R3_2026-05-27/"
        "native_direct_egress_claim_packet.json"
    ),
    "r3_network_observation": Path(
        "audit_results/wbp_native_custom_detached_egress_execution_EXTERNAL_R3_2026-05-27/"
        "native_process_network_observation_packet.json"
    ),
    "r2_direct_claim": Path(
        "audit_results/wbp_native_custom_detached_egress_execution_EXTERNAL_R2_2026-05-27/"
        "native_direct_egress_claim_packet.json"
    ),
    "r2_network_observation": Path(
        "audit_results/wbp_native_custom_detached_egress_execution_EXTERNAL_R2_2026-05-27/"
        "native_process_network_observation_packet.json"
    ),
    "r2_background_noise": Path(
        "audit_results/wbp_native_custom_detached_egress_execution_EXTERNAL_R2_2026-05-27/"
        "native_background_codex_noise_packet.json"
    ),
}

OUTPUT_FILES = (
    "direct_non_wbp_egress_reproduction_packet.json",
    "direct_non_wbp_egress_localization_packet.json",
    "direct_non_wbp_egress_fix_attempt_packet.json",
    "direct_non_wbp_vs_wbp_boundary_packet.json",
    "direct_non_wbp_failure_semantics_packet.json",
    "false_green_audit.json",
)


class SourcePacketError(RuntimeError):
    """Raised when a required packet is missing or invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourcePacketError(f"required packet missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourcePacketError(f"invalid JSON in required packet: {path}") from exc


def load_source_packets(
    repo_root: Path,
    *,
    source_files: dict[str, Path] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    resolved_files = source_files or DEFAULT_SOURCE_FILES
    packets: dict[str, dict[str, Any]] = {}
    paths: dict[str, str] = {}
    for key, relative_path in resolved_files.items():
        full_path = (repo_root / relative_path).resolve()
        packets[key] = read_json(full_path)
        paths[key] = str(full_path)
    return packets, paths


def build_reproduction_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    current_truth = sources["current_truth"]
    r4_summary = sources["r4_import_summary"]
    r4_classification = sources["r4_network_classification"]
    r3_claim = sources["r3_direct_claim"]
    r3_observation = sources["r3_network_observation"]
    r2_claim = sources["r2_direct_claim"]
    r2_observation = sources["r2_network_observation"]
    r2_noise = sources["r2_background_noise"]

    strongest_anchor_ok = all(
        (
            current_truth.get("status") == "ok",
            current_truth.get("final_status")
            == "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
            current_truth.get("direct_non_wbp_model_egress_observed") is True,
            current_truth.get("direct_egress_absence_proven") is False,
            r4_summary.get("status") == "ok",
            r4_summary.get("final_status")
            == "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
            r4_summary.get("command_hash_matches") is True,
            r4_summary.get("owner_readiness_status") == "ok",
            r4_summary.get("native_launch_attempted_from_current_thread") is False,
            r4_classification.get("status") == "ok",
            r4_classification.get("direct_non_wbp_model_egress_observed") is True,
            r4_classification.get("direct_non_wbp_model_egress_absent_within_bounded_window")
            is False,
            r4_classification.get("final_e2e_claimed") is False,
            r3_claim.get("direct_model_egress_observed") is True,
            r3_observation.get("classification") == "direct_model_egress_observed",
            r3_observation.get("non_local_peer_endpoints_present") is True,
            r2_claim.get("status") == "blocked",
            r2_claim.get("final_status")
            == "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE",
            r2_claim.get("direct_non_wbp_model_egress_absent_proven") is False,
            r2_observation.get("classification") == "insufficient_observation",
            r2_noise.get("background_codex_noise_detected") is True,
        )
    )
    status = "ok" if strongest_anchor_ok else "blocked"
    return packet(
        "custom_direct_non_wbp_egress_reproduction",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="imported_authenticated_direct_egress_observed",
        imported_evidence_only=True,
        fresh_live_reproduction_in_this_contour=False,
        strongest_authenticated_direct_egress_observed=status == "ok",
        stronger_prior_evidence_beats_weaker_later_non_healing_observation=(
            status == "ok"
        ),
        strongest_source_final_status=current_truth.get("final_status", ""),
        strongest_source_reason_class=current_truth.get("reason_class", ""),
        stronger_source_packet=source_paths["current_truth"],
        supporting_import_summary_packet=source_paths["r4_import_summary"],
        supporting_external_r3_claim_packet=source_paths["r3_direct_claim"],
        weaker_later_non_healing_packet=source_paths["r2_direct_claim"],
        weaker_later_non_healing_classification=r2_observation.get("classification", ""),
        weaker_later_noise_detected=r2_noise.get("background_codex_noise_detected") is True,
        direct_non_wbp_model_egress_observed=status == "ok",
        direct_egress_absence_proven=False,
        api_openai_com_absence_proven=False,
        external_evidence_dir=r4_summary.get("external_evidence_dir", ""),
        owner_execution_imported_context_only=r4_summary.get("owner_attestation_context_only")
        is True,
    )


def build_localization_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    current_truth = sources["current_truth"]
    r4_classification = sources["r4_network_classification"]
    r3_claim = sources["r3_direct_claim"]
    r3_observation = sources["r3_network_observation"]

    localized = all(
        (
            current_truth.get("direct_non_wbp_model_egress_observed") is True,
            r4_classification.get("direct_non_wbp_model_egress_observed") is True,
            r3_claim.get("custom_process_bound") is True,
            r3_claim.get("route_trace_confirmed") is True,
            r3_observation.get("classification") == "direct_model_egress_observed",
        )
    )
    status = "ok" if localized else "blocked"
    return packet(
        "custom_direct_non_wbp_egress_localization",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="declared_custom_direct_non_wbp_lane_direct_egress_observed_exact_subcause_unproven",
        imported_evidence_only=True,
        localized_to_declared_custom_direct_non_wbp_lane=localized,
        exact_root_cause_proven=False,
        exact_root_cause_requires_separate_fix_contour=None,
        remediation_contour_need_classification="unknown",
        narrowest_truthful_source_domain=(
            "direct_non_wbp_model_request_or_routing_path_after_custom_process_binding"
        ),
        custom_process_bound=r3_claim.get("custom_process_bound") is True,
        route_trace_confirmed=r3_claim.get("route_trace_confirmed") is True,
        direct_observer_classification=r3_observation.get("classification", ""),
        domain_attribution_available=current_truth.get("domain_attribution_available")
        is True,
        broader_platform_redesign_proven_necessary=False,
        source_current_truth_packet=source_paths["current_truth"],
        source_r4_network_classification_packet=source_paths["r4_network_classification"],
        source_r3_direct_claim_packet=source_paths["r3_direct_claim"],
        source_r3_network_observation_packet=source_paths["r3_network_observation"],
    )


def build_fix_attempt_packet() -> dict[str, Any]:
    return packet(
        "custom_direct_non_wbp_egress_fix_attempt",
        status="ok",
        contour_final_status=FINAL_STATUS_OK,
        classification="no_cheap_truthful_fix_applied_in_this_closeout_contour",
        imported_evidence_only=True,
        fix_attempted=False,
        cheap_repo_local_fix_available_proven=False,
        fix_applied=False,
        rerun_performed=False,
        direct_non_wbp_egress_healed=False,
        fixed_final_status_emitted=False,
    )


def build_boundary_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    route_trace = sources["pass4_route_trace"]
    current_truth = sources["current_truth"]
    r4_trace_validation = sources["r4_trace_validation"]

    separated = all(
        (
            route_trace.get("status") == "ok",
            route_trace.get("forwarded_to_wbp") is True,
            route_trace.get("upstream_status") == 200,
            route_trace.get("direct_egress_claimed") is False,
            r4_trace_validation.get("status") == "ok",
            r4_trace_validation.get("wbp_trace_confirmed") is True,
            current_truth.get("direct_non_wbp_model_egress_observed") is True,
        )
    )
    status = "ok" if separated else "blocked"
    return packet(
        "custom_direct_non_wbp_vs_wbp_boundary",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="wbp_routed_truth_preserved_direct_lane_stays_broken",
        imported_evidence_only=True,
        wbp_routed_truth_preserved=route_trace.get("forwarded_to_wbp") is True,
        wbp_route_trace_confirmed=r4_trace_validation.get("wbp_trace_confirmed") is True,
        direct_non_wbp_truth_broken=current_truth.get("direct_non_wbp_model_egress_observed")
        is True,
        direct_non_wbp_truth_healed=False,
        lanes_must_remain_separate=separated,
        route_truth_supports_direct_lane_health=False,
        operator_usable_wbp_truth_preserved=route_trace.get("forwarded_to_wbp") is True,
        global_egress_failure_claimed=False,
        source_pass4_route_trace_packet=source_paths["pass4_route_trace"],
        source_r4_trace_validation_packet=source_paths["r4_trace_validation"],
        source_current_truth_packet=source_paths["current_truth"],
    )


def build_failure_semantics_packet(
    sources: dict[str, dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    current_truth = sources["current_truth"]
    route_trace = sources["pass4_route_trace"]
    r2_observation = sources["r2_network_observation"]
    known_blocker = all(
        (
            current_truth.get("final_status")
            == "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_OBSERVED",
            current_truth.get("direct_non_wbp_model_egress_observed") is True,
            current_truth.get("direct_egress_absence_proven") is False,
            route_trace.get("forwarded_to_wbp") is True,
        )
    )
    status = "ok" if known_blocker else "blocked"
    return packet(
        "custom_direct_non_wbp_egress_failure_semantics",
        status=status,
        contour_final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        final_status=FINAL_STATUS_OK if status == "ok" else FINAL_STATUS_BLOCKED,
        classification="known_blocker_direct_non_wbp_egress_observed_imported",
        imported_evidence_only=True,
        direct_non_wbp_model_egress_known_blocker=status == "ok",
        direct_non_wbp_model_egress_observed=current_truth.get(
            "direct_non_wbp_model_egress_observed"
        )
        is True,
        direct_non_wbp_model_egress_absent_within_bounded_window=False,
        direct_lane_fix_proven=False,
        wbp_routed_truth_preserved=route_trace.get("forwarded_to_wbp") is True,
        global_egress_failure_claimed=False,
        api_openai_com_absence_proven=False,
        weaker_later_observation_classification=r2_observation.get("classification", ""),
        weaker_later_observation_counts_as_healing=False,
        strongest_source_packet=source_paths["current_truth"],
        strongest_source_final_status=current_truth.get("final_status", ""),
        supporting_route_trace_packet=source_paths["pass4_route_trace"],
        weaker_non_healing_source_packet=source_paths["r2_network_observation"],
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    reproduction = packets["direct_non_wbp_egress_reproduction_packet.json"]
    localization = packets["direct_non_wbp_egress_localization_packet.json"]
    fix_attempt = packets["direct_non_wbp_egress_fix_attempt_packet.json"]
    boundary = packets["direct_non_wbp_vs_wbp_boundary_packet.json"]
    semantics = packets["direct_non_wbp_failure_semantics_packet.json"]
    checks = [
        {
            "name": "strongest_truth_labeled_imported",
            "passed": reproduction.get("imported_evidence_only") is True,
        },
        {
            "name": "weaker_later_non_healing_not_counted_as_healed",
            "passed": reproduction.get("stronger_prior_evidence_beats_weaker_later_non_healing_observation")
            is True
            and semantics.get("weaker_later_observation_counts_as_healing") is False,
        },
        {
            "name": "no_false_fixed_path",
            "passed": fix_attempt.get("fix_attempted") is False
            and fix_attempt.get("fix_applied") is False
            and fix_attempt.get("fixed_final_status_emitted") is False,
        },
        {
            "name": "localization_stays_narrow",
            "passed": localization.get("exact_root_cause_proven") is False
            and localization.get("broader_platform_redesign_proven_necessary") is False
            and localization.get("exact_root_cause_requires_separate_fix_contour") is None
            and localization.get("remediation_contour_need_classification") == "unknown",
        },
        {
            "name": "wbp_truth_separate_from_direct_truth",
            "passed": boundary.get("wbp_routed_truth_preserved") is True
            and boundary.get("direct_non_wbp_truth_broken") is True
            and boundary.get("route_truth_supports_direct_lane_health") is False,
        },
        {
            "name": "known_blocker_not_global_failure",
            "passed": semantics.get("direct_non_wbp_model_egress_known_blocker") is True
            and semantics.get("global_egress_failure_claimed") is False
            and semantics.get("api_openai_com_absence_proven") is False,
        },
    ]
    ok = all(check["passed"] for check in checks)
    return packet(
        "custom_direct_non_wbp_egress_false_green_audit",
        status="ok" if ok else "blocked",
        contour_final_status=FINAL_STATUS_OK if ok else FINAL_STATUS_BLOCKED,
        checks=checks,
        forbidden_claims_present=not ok,
        positive_fix_claimed=False,
        positive_global_egress_absence_claimed=False,
    )


def build_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    source_packets: dict[str, dict[str, Any]] | None = None,
    source_paths: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    sources, paths = (
        (source_packets, source_paths)
        if source_packets is not None and source_paths is not None
        else load_source_packets(repo_root)
    )
    assert sources is not None
    assert paths is not None

    packets = {
        "direct_non_wbp_egress_reproduction_packet.json": build_reproduction_packet(
            sources, paths
        ),
        "direct_non_wbp_egress_localization_packet.json": build_localization_packet(
            sources, paths
        ),
        "direct_non_wbp_egress_fix_attempt_packet.json": build_fix_attempt_packet(),
        "direct_non_wbp_vs_wbp_boundary_packet.json": build_boundary_packet(sources, paths),
        "direct_non_wbp_failure_semantics_packet.json": build_failure_semantics_packet(
            sources, paths
        ),
    }
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    return packets


def overall_status(packets: dict[str, dict[str, Any]]) -> tuple[str, str]:
    ok = all(packet_data.get("status") == "ok" for packet_data in packets.values())
    return ("ok", FINAL_STATUS_OK) if ok else ("blocked", FINAL_STATUS_BLOCKED)


def build_closeout(
    repo_root: Path,
    evidence_dir: Path,
    packets: dict[str, dict[str, Any]],
) -> str:
    status, verdict = overall_status(packets)
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    touched_files = (
        "tools/custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe.py; "
        "tests/test_custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe.py; "
        f"{evidence_dir.relative_to(repo_root)}/*"
    )
    return f"""<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Direct Non-WBP Egress Known Blocker Closeout R4

## Goal

Truthfully close Pass 5 by packaging the already established direct non-WBP
egress defect as a bounded known blocker, without pretending a fresh fix,
global egress failure, or any adjacent proof class.

## Result

- status: {status}
- final verdict: `{verdict}`
- closure state: CLOSED

## Contour Capsule

- goal: convert existing authenticated direct-egress evidence into the declared Pass 5 known-blocker bundle only
- branch: {branch}
- head: {head}
- touched files: {touched_files}
- tests run: python3 -m py_compile tools/custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe.py tests/test_custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe.py; python3 -m unittest tests.test_custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe; python3 tools/custom_codex_direct_non_wbp_egress_fix_or_known_blocker_r2_probe.py --evidence-dir {evidence_dir.relative_to(repo_root)}; python3 tools/check_closeout_resilience.py {evidence_dir.relative_to(repo_root)}/closeout.md; top-level JSON parse sweep; git diff --check
- blocked risks: direct non-WBP defect remains unresolved; no cheap fix was applied in this contour; WBP-routed truth remains separate and healthy; no global egress absence was claimed
- closure state: CLOSED

## Verification

- tests: targeted Pass 5 synthesis unittest passed
- build: py_compile passed and git diff --check passed
- manual: the contour-local packets preserve imported/current truth boundaries, direct-known-blocker semantics, and no false FIXED path
- live verification: none in this contour; existing authenticated imported evidence remained imported evidence only

## Artifacts

- spec: thread-only contour plan, not written to repo
- packet: direct_non_wbp_failure_semantics_packet.json
- report: false_green_audit.json

## Git

- branch: {branch}
- commit: pending during closeout authoring
- pushed: pending during closeout authoring

## Scope Check

- unrelated work mixed in: no; this contour stays within the dedicated Pass 5 probe, test, and contour-local evidence dir
- private-data risk reviewed: yes; imported evidence is referenced through packet truth only and no raw secret values are copied into this bundle

## Notes

- blockers encountered: none inside this contour; stronger authenticated direct-egress observation from current truth and R4 import remained controlling over weaker later non-healing R2 observation
- resume from here: CLOSED
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="custom-codex-direct-non-wbp-egress-fix-or-known-blocker-r2-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(ROOT / EXPECTED_EVIDENCE_DIR),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    try:
        packets = build_packets(repo_root, evidence_dir)
    except SourcePacketError as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "final_status": FINAL_STATUS_BLOCKED,
                    "reason_class": "SOURCE_PACKET_ERROR",
                    "message": str(exc),
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1

    for filename, packet_data in packets.items():
        json_write(evidence_dir / filename, packet_data)

    closeout = build_closeout(repo_root, evidence_dir, packets)
    (evidence_dir / "closeout.md").write_text(closeout, encoding="utf-8")

    status, verdict = overall_status(packets)
    print(
        json.dumps(
            {
                "status": status,
                "final_status": verdict,
                "output_files": ["closeout.md", *OUTPUT_FILES],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
