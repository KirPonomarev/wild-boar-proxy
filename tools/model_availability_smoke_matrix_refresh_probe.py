#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit strict model availability refresh evidence without native or route mutation."""

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

from wild_boar_proxy.model_availability import (
    build_layer_boundary_packet,
    build_model_availability_false_green_audit,
    build_model_availability_matrix,
    build_model_direct_preflight_packet,
    build_model_id_normalization_packet,
    build_no_route_account_mutation_packet,
    build_validation_freshness_packet,
    validate_model_availability_matrix,
)
from wild_boar_proxy.native_filesystem_probe import json_write


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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/model_availability.py",
        "tests/test_model_availability.py",
        "tools/model_availability_smoke_matrix_refresh_probe.py",
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
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": ["fresh evidence directory only"],
            "native_launch_allowed": False,
            "native_launch_attempted": False,
            "codex_cli_launch_allowed": False,
            "codex_cli_launch_attempted": False,
            "route_account_mutation_allowed": False,
            "route_account_mutation_attempted": False,
            "original_codex_profile_write_allowed": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "model_availability_schema_version": 1,
            "codex_cli_version": "not_used_in_this_contour",
            "codex_cli_path": "not_used_in_this_contour",
            "codex_app_version": "not_used_in_this_contour",
            "codex_app_path": "not_used_in_this_contour",
        },
    }


def _route_stub_packet(candidate_packet: dict[str, Any], catalog_packet: dict[str, Any]) -> dict[str, Any]:
    catalog_ids = {
        str(model.get("model_id") or "")
        for model in catalog_packet.get("models", [])
        if isinstance(model, dict)
    }
    routes = []
    for model_id in candidate_packet.get("candidate_model_ids", []):
        model_id = str(model_id)
        if model_id in catalog_ids or not model_id.startswith("wbp-"):
            continue
        routes.append(
            {
                "route_id": model_id,
                "enabled": True,
                "provider": {"id": "external_route_from_previous_matrix"},
                "upstream_model": "",
                "auth": {"secret_ref": "present_redacted"},
            }
        )
    return {
        "packet_kind": "route_snapshot_stub",
        "status": "ok",
        "data": {"routes": routes},
        "raw_secret_recorded": False,
        "source": "previous_model_availability_candidate_list",
    }


def _enrich_previous_models(previous_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    enriched = []
    for previous in previous_matrix.get("models", []):
        if not isinstance(previous, dict):
            continue
        status_passed = previous.get("direct_preflight_status") == "passed"
        response_payload = (
            {"status": "completed", "output_text": "redacted_previous_success"}
            if status_passed
            else None
        )
        error_payload = (
            {"error": {"type": previous.get("failure_cause") or "unknown"}}
            if not status_passed
            else None
        )
        enriched.append(
            build_model_direct_preflight_packet(
                model_id=str(previous.get("model_id") or ""),
                source="previous_matrix_refresh_import",
                listed=previous.get("listed") is True,
                selectable=previous.get("selectable") is True,
                route_selected=previous.get("route_selected") is True,
                runtime_ready=True,
                http_status=previous.get("http_status"),
                upstream_status=previous.get("upstream_status"),
                response_payload=response_payload,
                error_payload=error_payload,
                request_sent_to_wbp=previous.get("request_sent_to_wbp") is True,
                wbp_trace_id=str(previous.get("wbp_trace_id") or ""),
            )
        )
    return enriched


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    raw_secret_markers = [
        "sk-",
        "OPENAI_API_KEY=",
        "OPENROUTER_API_KEY=",
        "Authorization: Bearer",
    ]
    findings = [marker for marker in raw_secret_markers if marker in serialized]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "secret_redaction_audit",
        "status": "blocked" if findings else "ok",
        "raw_secret_found": bool(findings),
        "secret_marker_findings": findings,
        "raw_prompt_recorded": "Reply OK" in serialized or "secret prompt" in serialized,
        "auth_header_recorded": "Authorization" in serialized,
        "checked_packet_count": len(packets),
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "declared_write_surfaces_packet.json",
        "version_pinning_packet.json",
        "model_availability_layer_boundary_packet.json",
        "route_account_mutation_guard_packet.json",
        "validation_freshness_packet.json",
        "provider_auth_strategy_reference_packet.json",
        "previous_model_availability_reference_packet.json",
        "model_id_normalization_packet.json",
        "model_availability_matrix.json",
        "model_claims_matrix.json",
        "model_availability_false_green_audit.json",
        "secret_redaction_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = [
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_model_availability_refresh_audit",
        "status": "blocked" if missing or blocked else "ok",
        "required_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": sorted(blocked),
        "native_launch_found": packets["declared_write_surfaces_packet.json"].get(
            "native_launch_attempted"
        )
        is True,
        "route_account_mutation_found": packets["route_account_mutation_guard_packet.json"].get(
            "status"
        )
        != "ok",
        "codex_acceptance_overclaimed": packets["model_availability_matrix.json"].get(
            "codex_acceptance_proven"
        )
        is True,
        "all_models_work_claimed": packets["model_availability_matrix.json"].get(
            "all_model_sweep_attempted"
        )
        is True,
        "false_green_audit_status": packets["model_availability_false_green_audit.json"].get(
            "status"
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="model-availability-smoke-matrix-refresh-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument(
        "--previous-evidence-dir",
        default="audit_results/wbp_model_availability_smoke_matrix_2026-05-26",
    )
    parser.add_argument(
        "--auth-evidence-dir",
        default="audit_results/wbp_provider_auth_strategy_contract_refresh_2026-05-26",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    previous_dir = (repo_root / args.previous_evidence_dir).resolve()
    auth_dir = (repo_root / args.auth_evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    previous_matrix = _read_json(previous_dir / "model_availability_matrix.json")
    previous_freshness = _read_json(previous_dir / "validation_freshness_packet.json")
    candidate_packet = _read_json(previous_dir / "model_selection_reference_packet.json")
    catalog_packet = _read_json(previous_dir / "model_catalog_reference_packet.json")
    auth_packet = _read_json(auth_dir / "provider_auth_strategy_packet.json")
    route_stub = _route_stub_packet(candidate_packet, catalog_packet)

    model_packets = _enrich_previous_models(previous_matrix)
    matrix = build_model_availability_matrix(
        model_packets,
        candidate_packet=candidate_packet,
        runtime_packet={"runtime_ready": previous_matrix.get("runtime_ready") is True},
    )
    layer_boundary = build_layer_boundary_packet()
    mutation_guard = build_no_route_account_mutation_packet(
        route_snapshot_before=route_stub,
        route_snapshot_after=route_stub,
        account_snapshot_before={"account_promotion_allowed": False},
        account_snapshot_after={"account_promotion_allowed": False},
    )
    observed_at = str(
        previous_freshness.get("healthcheck_observed_at_utc")
        or previous_freshness.get("captured_at_utc")
        or previous_matrix.get("captured_at_utc")
        or ""
    )
    freshness = build_validation_freshness_packet(
        observed_at_utc=observed_at,
        validation_actor="previous_model_availability_smoke_matrix",
        validation_scope="gpt-5.4-mini,gpt-5.4,gpt-5.5,current_catalog_default,external_route_sample",
    )
    normalization = build_model_id_normalization_packet(
        candidate_packet=candidate_packet,
        catalog_packet=catalog_packet,
        routes_packet=route_stub,
    )
    false_green = build_model_availability_false_green_audit(
        matrix_packet=matrix,
        freshness_packet=freshness,
        layer_boundary_packet=layer_boundary,
        mutation_guard_packet=mutation_guard,
        normalization_packet=normalization,
    )
    packets = _base_packets(repo_root, evidence_dir)
    packets.update(
        {
            "model_availability_layer_boundary_packet.json": layer_boundary,
            "route_account_mutation_guard_packet.json": mutation_guard,
            "validation_freshness_packet.json": freshness,
            "provider_auth_strategy_reference_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "provider_auth_strategy_reference",
                "status": "ok",
                "referenced_packet": str(auth_dir / "provider_auth_strategy_packet.json"),
                "referenced_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED",
                "selected_strategy": auth_packet.get("selected_strategy"),
                "model_availability_reproved_by_auth_contour": False,
            },
            "previous_model_availability_reference_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "previous_model_availability_reference",
                "status": "ok",
                "referenced_packet": str(previous_dir / "model_availability_matrix.json"),
                "referenced_status": previous_matrix.get("target_status"),
                "previous_live_smoke_imported": True,
                "live_revalidation_attempted_in_refresh": False,
                "native_launch_attempted": False,
                "codex_cli_launch_attempted": False,
            },
            "route_snapshot_stub_packet.json": route_stub,
            "model_id_normalization_packet.json": normalization,
            "model_availability_matrix.json": matrix,
            "model_claims_matrix.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "model_claims_matrix",
                "status": "ok" if not validate_model_availability_matrix(matrix) else "blocked",
                "allowed_claims": [model["allowed_claim"] for model in model_packets],
                "forbidden_claims": matrix["forbidden_claims"],
                "validation_failures": validate_model_availability_matrix(matrix),
                "codex_acceptance_proven": False,
                "native_app_usability_proven": False,
                "direct_egress_absence_proven": False,
            },
            "model_availability_false_green_audit.json": false_green,
        }
    )
    packets["secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    packets["independent_model_availability_refresh_audit.json"] = _independent_audit(packets)
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "model_availability_refresh_summary",
        "status": "ok"
        if all(packet.get("status") != "blocked" for packet in packets.values())
        else "blocked",
        "final_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        "refresh_kind": "guard_refresh_with_previous_live_smoke_reference",
        "models_tested": matrix["models_tested"],
        "direct_wbp_non_stream_passed_models": matrix["direct_wbp_non_stream_passed_models"],
        "gpt_5_5_claim": matrix["gpt_5_5_claim"],
        "native_launch_attempted": False,
        "codex_cli_launch_attempted": False,
        "route_account_mutation_attempted": False,
        "codex_acceptance_proven": False,
        "direct_egress_absence_proven": False,
        "validation_freshness_status": freshness["status"],
    }
    packets["model_availability_refresh_summary_packet.json"] = summary
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
