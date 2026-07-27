#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_custom_sessions import (  # noqa: E402
    CODING_AGENT_MODEL_SLOT,
    CodexCustomSessionManager,
)


PRIMARY_MODEL_ID = "gpt-5.5"
API_MODEL_ID = "wbp-web-primary-openrouter"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def command(packet: dict[str, object]) -> dict[str, object]:
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": "ok",
        "packet": packet,
    }


def account(backend_id: str, priority: int = 10) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": "active",
        "status": "healthy",
        "fail_count": 0,
        "success_count": 7,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "manual_hold": False,
        "auth_ref": "/tmp/wbp-redacted-auth.json",
    }


def commands() -> dict[str, dict[str, object]]:
    return {
        "status": command(
            {
                "status": "ok",
                "machine_error_code": "OK",
                "claim_gate": {"status": "ok"},
                "pool_summary": {"selected_backend_ids": ["acct-a"]},
                "auth_pool_hygiene": {
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            }
        ),
        "accounts_list": command({"accounts": [account("acct-a"), account("acct-b", 20)]}),
        "rollout_rotation_inspect": command({"status": "ok", "machine_error_code": "OK"}),
    }


def operator_status() -> dict[str, object]:
    return {
        "status": {"status": "ok", "machine_error_code": "OK"},
        "claim_gate": {"status": "ok"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": [PRIMARY_MODEL_ID, "gpt-5.4"],
        },
    }


def api_snapshot(route_id: str = API_MODEL_ID) -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": route_id,
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            }
        ],
    }


class TimedPromptRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def _sleep_seconds(self, *, model_id: str, prompt: str) -> float:
        prompt_upper = prompt.upper()
        if "FAIL" in prompt_upper:
            return 0.015
        if "MEDIUM" in prompt_upper:
            return 0.045 if model_id == PRIMARY_MODEL_ID else 0.055
        return 0.020 if model_id == PRIMARY_MODEL_ID else 0.030

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(dict(payload))
        model_id = str(payload.get("model_id") or "")
        prompt = str(payload.get("prompt") or "")
        configured_provider = "external_route" if model_id == API_MODEL_ID else "cliproxy"
        started = time.monotonic()
        time.sleep(self._sleep_seconds(model_id=model_id, prompt=prompt))
        duration_seconds = round(time.monotonic() - started, 3)
        if "FAIL" in prompt.upper():
            return {
                "status": "failed",
                "machine_error_code": "ENGINE_PROMPT_FAILED",
                "error_class": "SyntheticFailure",
                "duration_seconds": duration_seconds,
                "secret_value_recorded": False,
                "configured_provider": configured_provider,
                "configured_wire_api": "responses",
                "wbp_endpoint_configured": True,
                "config_endpoint_matches": True,
                "config_provider_matches": True,
                "config_wire_api_matches": True,
                "command_uses_stdin_dash": True,
                "command_json_mode": True,
                "env_codex_home_is_temp": True,
                "env_home_is_temp": True,
                "workdir_is_temp": True,
                "command_workdir_is_temp": True,
                "command_output_file_is_temp": True,
                "current_codex_home_used": False,
            }
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "final_message": f"OK::{model_id}::{prompt.split()[0]}",
            "duration_seconds": duration_seconds,
            "token_usage": {
                "prompt_tokens": 4 if "SMALL" in prompt.upper() else 8,
                "completion_tokens": 6 if "SMALL" in prompt.upper() else 12,
                "total_tokens": 10 if "SMALL" in prompt.upper() else 20,
            },
            "secret_value_recorded": False,
            "configured_provider": configured_provider,
            "configured_wire_api": "responses",
            "wbp_endpoint_configured": True,
            "config_endpoint_matches": True,
            "config_provider_matches": True,
            "config_wire_api_matches": True,
            "command_uses_stdin_dash": True,
            "command_json_mode": True,
            "env_codex_home_is_temp": True,
            "env_home_is_temp": True,
            "workdir_is_temp": True,
            "command_workdir_is_temp": True,
            "command_output_file_is_temp": True,
            "current_codex_home_used": False,
            "independent_wbp_trace_observed": True,
            "trace_observer_packet": {
                "path": "/v1/responses",
                "upstream_status": 200,
                "forwarded_to_wbp": True,
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
            },
        }


def _probe_source_boundaries(repo_root: Path) -> dict[str, Any]:
    operator_surface_text = (repo_root / "wild_boar_proxy" / "operator_surface.py").read_text(
        encoding="utf-8"
    )
    cli_runner_text = (repo_root / "wild_boar_proxy" / "cli_runner.py").read_text(
        encoding="utf-8"
    )
    codex_custom_sessions_text = (
        repo_root / "wild_boar_proxy" / "codex_custom_sessions.py"
    ).read_text(encoding="utf-8")
    return {
        "operator_surface_duration_seconds_present": '"duration_seconds": round(time.time() - started, 3)' in operator_surface_text,
        "cli_runner_duration_seconds_present": '"duration_seconds": round(time.time() - started, 3)' in cli_runner_text,
        "codex_custom_sessions_latency_ms_from_runner_duration_present": "duration_seconds = result.get(\"duration_seconds\")" in codex_custom_sessions_text
        and '"latency_ms": latency_ms' in codex_custom_sessions_text,
        "cross_surface_comparison_currently_admitted": False,
        "comparison_blocker": "mixed_wall_clock_and_runner_reported_timing_surfaces",
    }


def _measure_prompt(
    manager: CodexCustomSessionManager,
    session_id: str,
    payload: dict[str, Any],
    runner: TimedPromptRunner,
) -> dict[str, Any]:
    started = time.monotonic()
    packet = manager.prompt_packet(
        session_id,
        payload,
        runner.run,
        owner_authorized=True,
    )
    wall_clock_ms = int((time.monotonic() - started) * 1000)
    return {
        "request": dict(payload),
        "packet": packet,
        "wall_clock_ms": wall_clock_ms,
    }


def _lane_measurements(entries: list[dict[str, Any]], slot_id: str) -> list[dict[str, Any]]:
    return [
        entry
        for entry in entries
        if str(entry["packet"].get("current_execution_slot_id") or "") == slot_id
    ]


def _ok_latency_values(entries: list[dict[str, Any]]) -> list[int]:
    values: list[int] = []
    for entry in entries:
        packet = entry["packet"]
        latency_ms = packet.get("latency_ms")
        if packet.get("status") == "ok" and isinstance(latency_ms, int):
            values.append(latency_ms)
    return values


def _wall_clock_values(entries: list[dict[str, Any]]) -> list[int]:
    return [
        int(entry["wall_clock_ms"])
        for entry in entries
        if entry["packet"].get("status") == "ok" and isinstance(entry["wall_clock_ms"], int)
    ]


def _median_or_none(values: list[int]) -> float | None:
    return round(float(statistics.median(values)), 3) if values else None


def build_packets(*, repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del evidence_dir
    source_boundaries = _probe_source_boundaries(repo_root)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = CodexCustomSessionManager(Path(tmpdir) / "probe_session_root")
        runner = TimedPromptRunner()
        created = manager.create_packet(
            {
                "primary_model_id": PRIMARY_MODEL_ID,
                "coding_agent_model_id": API_MODEL_ID,
            },
            commands(),
            operator_status(),
            api_snapshot=api_snapshot(),
        )
        session_id = str(created.get("session", {}).get("session_id") or "")
        runs = [
            _measure_prompt(
                manager,
                session_id,
                {"prompt": "SMALL_CHATGPT task."},
                runner,
            ),
            _measure_prompt(
                manager,
                session_id,
                {"prompt": "SMALL_API task.", "slot_id": CODING_AGENT_MODEL_SLOT},
                runner,
            ),
            _measure_prompt(
                manager,
                session_id,
                {"prompt": "MEDIUM_CHATGPT task."},
                runner,
            ),
            _measure_prompt(
                manager,
                session_id,
                {"prompt": "MEDIUM_API task.", "slot_id": CODING_AGENT_MODEL_SLOT},
                runner,
            ),
            _measure_prompt(
                manager,
                session_id,
                {"prompt": "FAIL_API task.", "slot_id": CODING_AGENT_MODEL_SLOT},
                runner,
            ),
        ]
        transcript = manager.transcript_packet(session_id)

    primary_runs = _lane_measurements(runs, "primary_model_slot")
    api_runs = _lane_measurements(runs, "coding_agent_model_slot")
    primary_ok_latencies = _ok_latency_values(primary_runs)
    api_ok_latencies = _ok_latency_values(api_runs)
    primary_wall = _wall_clock_values(primary_runs)
    api_wall = _wall_clock_values(api_runs)
    failed_runs = [entry for entry in runs if entry["packet"].get("status") != "ok"]
    throughput_total_wall_clock_ms = sum(entry["wall_clock_ms"] for entry in runs)
    successful_run_count = sum(1 for entry in runs if entry["packet"].get("status") == "ok")

    packets: dict[str, dict[str, Any]] = {}
    packets["latency_classification_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "latency_classification",
        "status": "ok",
        "measurement_source_classification": "bounded_contour_local_runner_harness_only",
        "chatgpt_lane_packet_latency_ms": primary_ok_latencies,
        "api_lane_packet_latency_ms": api_ok_latencies,
        "chatgpt_lane_wall_clock_ms": primary_wall,
        "api_lane_wall_clock_ms": api_wall,
        "chatgpt_lane_median_packet_latency_ms": _median_or_none(primary_ok_latencies),
        "api_lane_median_packet_latency_ms": _median_or_none(api_ok_latencies),
        "chatgpt_lane_median_wall_clock_ms": _median_or_none(primary_wall),
        "api_lane_median_wall_clock_ms": _median_or_none(api_wall),
        "packet_latency_surface_present": bool(primary_ok_latencies and api_ok_latencies),
        "wall_clock_surface_present": bool(primary_wall and api_wall),
        "live_stack_acceleration_proven": False,
        "user_visible_productivity_gain_proven": False,
    }
    packets["throughput_classification_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "throughput_classification",
        "status": "ok",
        "measurement_source_classification": "bounded_contour_local_runner_harness_only",
        "run_count_total": len(runs),
        "run_count_successful": successful_run_count,
        "run_count_failed": len(failed_runs),
        "sequential_only": True,
        "concurrency_guard_required": True,
        "throughput_total_wall_clock_ms": throughput_total_wall_clock_ms,
        "successful_runs_per_second": round(
            successful_run_count / (throughput_total_wall_clock_ms / 1000.0), 3
        )
        if throughput_total_wall_clock_ms
        else None,
        "concurrent_throughput_proven": False,
        "throughput_implies_cost_efficiency": False,
    }
    packets["lane_measurement_comparison_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "lane_measurement_comparison",
        "status": "ok",
        "chatgpt_lane_measured": bool(primary_runs),
        "api_lane_measured": bool(api_runs),
        "same_harness_conditions": True,
        "same_guard_conditions": True,
        "same_execution_path": False,
        "comparison_admitted": False,
        "comparison_status": "limited_or_not_admitted",
        "comparison_blocker": "lane_paths_and_timing_sources_are_not_cleanly_comparable_for_acceleration_claims",
        "current_only_measurements_remain_useful": True,
        "clean_acceleration_ordering_claimed": False,
    }
    packets["measurement_integrity_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "measurement_integrity",
        "status": "ok",
        "run_count_declared": len(runs),
        "failed_runs_retained": len(failed_runs) == 1,
        "failed_run_machine_error_codes": [
            str(entry["packet"].get("machine_error_code") or "") for entry in failed_runs
        ],
        "transcript_entry_count": len(transcript.get("entries") or []),
        "transcript_preserves_failed_or_blocked_events": any(
            str(entry.get("event") or "").startswith("prompt_failed")
            for entry in transcript.get("entries", [])
            if isinstance(entry, dict)
        ),
        "packet_latency_comes_from_runner_reported_duration": source_boundaries[
            "codex_custom_sessions_latency_ms_from_runner_duration_present"
        ],
        "operator_surface_wall_clock_duration_present": source_boundaries[
            "operator_surface_duration_seconds_present"
        ],
        "cli_runner_wall_clock_duration_present": source_boundaries[
            "cli_runner_duration_seconds_present"
        ],
        "mixed_timing_surfaces_detected": True,
        "cross_surface_comparison_currently_admitted": False,
    }
    packets["acceleration_non_claims_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "acceleration_non_claims",
        "status": "ok",
        "measured_latency_implies_better_answers": False,
        "measured_latency_implies_user_visible_productivity_gain": False,
        "sequential_throughput_implies_safe_parallel_throughput": False,
        "throughput_implies_cost_efficiency": False,
        "one_medium_task_generalizes_to_coding_workloads": False,
        "current_measurements_stable_over_time": False,
    }
    packets["acceleration_gap_matrix.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "acceleration_gap_matrix",
        "status": "ok",
        "gaps": [
            {
                "id": "live_stack_acceleration_not_proven_beyond_contour_local_harness",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "mixed_timing_surfaces_block_clean_cross_surface_comparison",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "user_visible_productivity_gain_not_proven_here",
                "severity": "medium",
                "status": "open",
            },
            {
                "id": "concurrent_throughput_remains_unproven_here",
                "severity": "high",
                "status": "open",
            },
        ],
    }
    packets["false_green_boundary_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "current_only_measurements_treated_as_comparative_speedup": False,
        "failed_or_slow_runs_dropped_from_evidence": False,
        "sequential_throughput_treated_as_concurrency_readiness": False,
        "speed_treated_as_quality_or_reasoning_gain": False,
        "timing_treated_as_cost_efficiency_proof": False,
    }
    packets["independent_audit_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "independent_audit",
        "status": "ok",
        "findings": [
            {
                "id": "timing_surface_exists_in_custom_session_packets_and_wall_clock_helpers",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "failed_runs_are_retained_in_measurement_packets_and_transcript",
                "severity": "info",
                "status": "confirmed",
            },
            {
                "id": "clean_acceleration_comparison_remains_not_admitted_under_mixed_timing_surfaces",
                "severity": "high",
                "status": "open",
            },
            {
                "id": "contour_local_runner_harness_does_not_count_as_live_stack_acceleration_proof",
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
