#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy import runtime  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _run_json_command(repo_root: Path, args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        ["python3", "-m", "wild_boar_proxy", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    return {
        "exit_code": completed.returncode,
        "stdout_json": payload if isinstance(payload, dict) else {},
        "stderr_redacted_len": len(completed.stderr),
        "captured_at_utc": utc_now(),
    }


def _managed_state_snapshot() -> dict[str, Any]:
    paths = runtime.RuntimePaths.from_env()
    state = runtime.read_json(paths.state_file, required=False)
    snapshot = state.get(runtime.SELECTED_BACKEND_SNAPSHOT_FIELD)
    snapshot_ids = (
        runtime.normalize_selected_backend_ids(snapshot.get("selected_backend_ids"))
        if isinstance(snapshot, dict)
        else []
    )
    return {
        "selected_backend_ids": runtime.selected_backend_ids_from_state(state),
        "selected_backend_ids_count": len(runtime.selected_backend_ids_from_state(state)),
        "selected_backend_ids_observed_at": str(
            state.get("selected_backend_ids_observed_at") or ""
        ),
        "stable_default_backend_id": str(state.get("stable_default_backend_id") or ""),
        "selected_backend_snapshot_present": isinstance(snapshot, dict),
        "selected_backend_snapshot_ids": snapshot_ids,
        "selected_backend_snapshot_count": len(snapshot_ids),
        "selected_backend_snapshot_observed_at": (
            str(snapshot.get("observed_at_utc") or "") if isinstance(snapshot, dict) else ""
        ),
    }


def _direct_native_probe(model_id: str) -> dict[str, Any]:
    auth_path = Path("/Users/kirillponomarev/.codex-custom-cli/auth.json")
    auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))
    api_key = str(auth_payload.get("OPENAI_API_KEY") or "")
    request = urllib.request.Request(
        "http://127.0.0.1:8318/v1/responses",
        data=json.dumps(
            {"model": model_id, "input": "Respond with exactly OK"}
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with runtime.proxyless_urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", "ignore")
            return {
                "status": "ok",
                "http_status": int(response.status),
                "body_preview": body[:500],
            }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")
        return {
            "status": "http_error",
            "http_status": int(exc.code),
            "body_preview": detail[:500],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "exception",
            "http_status": None,
            "error": repr(exc),
        }


def build_packets(*, repo_root: Path) -> dict[str, dict[str, Any]]:
    pre_sync_state = _managed_state_snapshot()
    sync_command = _run_json_command(repo_root, ["sync", "--json"])
    post_sync_state = _managed_state_snapshot()
    post_sync_direct_probe = _direct_native_probe("gpt-5.5")
    healthcheck_command = _run_json_command(repo_root, ["healthcheck", "--json"])
    post_healthcheck_state = _managed_state_snapshot()
    status_command = _run_json_command(repo_root, ["status", "--json"])
    accounts_command = _run_json_command(repo_root, ["accounts", "list", "--json"])

    health_payload = healthcheck_command["stdout_json"]
    status_payload = status_command["stdout_json"]
    health_hygiene = (
        health_payload.get("auth_pool_hygiene")
        if isinstance(health_payload.get("auth_pool_hygiene"), dict)
        else {}
    )
    status_hygiene = (
        status_payload.get("auth_pool_hygiene")
        if isinstance(status_payload.get("auth_pool_hygiene"), dict)
        else {}
    )
    recovery_hint = (
        health_payload.get("native_auth_recovery_hint")
        if isinstance(health_payload.get("native_auth_recovery_hint"), dict)
        else {}
    )

    selection_packet = {
        "captured_at_utc": utc_now(),
        "pre_sync_selected_backend_ids_count": pre_sync_state["selected_backend_ids_count"],
        "pre_sync_snapshot_count": pre_sync_state["selected_backend_snapshot_count"],
        "post_sync_selected_backend_ids_count": post_sync_state["selected_backend_ids_count"],
        "post_sync_snapshot_count": post_sync_state["selected_backend_snapshot_count"],
        "post_healthcheck_selected_backend_ids_count": post_healthcheck_state[
            "selected_backend_ids_count"
        ],
        "post_healthcheck_snapshot_count": post_healthcheck_state[
            "selected_backend_snapshot_count"
        ],
        "health_selected_backend_ids_observed_count": len(
            runtime.normalize_selected_backend_ids(
                health_hygiene.get("selected_backend_ids_observed")
            )
        ),
        "health_selected_backend_ids_runtime_loaded_count": int(
            health_hygiene.get("selected_backend_runtime_loaded_count", 0) or 0
        ),
        "health_selected_backend_observation_source": str(
            health_hygiene.get("selected_backend_observation_source") or ""
        ),
        "health_selected_backend_snapshot_validation_status": str(
            health_hygiene.get("selected_backend_snapshot_validation_status") or ""
        ),
        "selection_gap_detected": recovery_hint.get("selection_gap_detected") is True,
        "sync_repopulated_selected_backend_ids": post_sync_state[
            "selected_backend_ids_count"
        ]
        > pre_sync_state["selected_backend_ids_count"],
        "status_hygiene_consistent_with_health": (
            status_hygiene.get("selected_backend_observation_source")
            == health_hygiene.get("selected_backend_observation_source")
            and status_hygiene.get("selected_backend_ids_observed")
            == health_hygiene.get("selected_backend_ids_observed")
        ),
    }

    recovery_packet = {
        "captured_at_utc": utc_now(),
        "sync_machine_error_code": str(
            sync_command["stdout_json"].get("machine_error_code") or ""
        ),
        "sync_effective_mode": str(sync_command["stdout_json"].get("effective_mode") or ""),
        "health_machine_error_code": str(health_payload.get("machine_error_code") or ""),
        "native_auth_recovery_hint": recovery_hint,
        "owner_action_required": recovery_hint.get("owner_action_required") is True,
        "next_action": str(recovery_hint.get("next_action") or ""),
        "command_surface": str(recovery_hint.get("command_surface") or ""),
        "auth_recovery_restored": post_sync_direct_probe.get("http_status") == 200,
        "hard_blocker_precisely_localized": (
            recovery_hint.get("status") == "owner_action_required"
            and post_sync_direct_probe.get("http_status") == 503
        ),
    }

    failure_taxonomy_packet = {
        "captured_at_utc": utc_now(),
        "sync_ok": sync_command["stdout_json"].get("machine_error_code") == "OK",
        "health_machine_error_code": str(health_payload.get("machine_error_code") or ""),
        "status_machine_error_code": str(status_payload.get("machine_error_code") or ""),
        "direct_native_probe_status": post_sync_direct_probe.get("status"),
        "direct_native_probe_http_status": post_sync_direct_probe.get("http_status"),
        "auth_unavailable_present": str(health_payload.get("machine_error_code") or "")
        == "AUTH_UNAVAILABLE"
        and post_sync_direct_probe.get("http_status") == 503,
        "launch_capable_backend_count": int(
            health_hygiene.get("launch_capable_backend_count", 0) or 0
        ),
        "accounts_registry_count": len(
            (accounts_command["stdout_json"].get("accounts") or [])
            if isinstance(accounts_command["stdout_json"].get("accounts"), list)
            else []
        ),
    }

    recovered_candidate_packet = {
        "captured_at_utc": utc_now(),
        "model_id": "gpt-5.5",
        "post_sync_direct_probe": post_sync_direct_probe,
        "post_sync_selected_backend_ids_count": post_sync_state["selected_backend_ids_count"],
        "post_healthcheck_selected_backend_ids_count": post_healthcheck_state[
            "selected_backend_ids_count"
        ],
        "restored_on_admitted_surface": post_sync_direct_probe.get("http_status") == 200,
    }

    runtime_alignment_packet = {
        "captured_at_utc": utc_now(),
        "status_effective_mode": str(status_payload.get("effective_mode") or ""),
        "status_endpoint": str(status_payload.get("endpoint") or ""),
        "status_configured_model": str(status_payload.get("configured_model") or ""),
        "health_selected_backend_observation_source": str(
            health_hygiene.get("selected_backend_observation_source") or ""
        ),
        "health_selected_backend_runtime_loaded_count": int(
            health_hygiene.get("selected_backend_runtime_loaded_count", 0) or 0
        ),
        "health_selected_backend_observed_count": len(
            runtime.normalize_selected_backend_ids(
                health_hygiene.get("selected_backend_ids_observed")
            )
        ),
        "launched_custom_codex_recovery_proven": False,
        "stable_runtime_recovery_proven": post_sync_direct_probe.get("http_status") == 200,
    }

    non_claims_packet = {
        "captured_at_utc": utc_now(),
        "non_claims": [
            "sync success does not prove runnable native auth",
            "selected backend snapshot does not prove runtime-loaded auth",
            "owner_action_required hint does not prove launched Custom Codex native recovery",
            "static accounts validate does not prove live /v1/responses success",
        ],
    }

    false_green_boundary_packet = {
        "captured_at_utc": utc_now(),
        "native_lane_restored_claim_blocked": post_sync_direct_probe.get("http_status") != 200,
        "selection_truth_separated_from_runtime_auth_truth": (
            selection_packet["health_selected_backend_ids_observed_count"] > 0
            and post_sync_direct_probe.get("http_status") == 503
        ),
        "static_validate_counts_as_runnable_auth": False,
        "api_fallback_counts_as_native_recovery": False,
    }

    independent_audit_packet = {
        "captured_at_utc": utc_now(),
        "material_mismatch_detected": not (
            selection_packet["health_selected_backend_ids_observed_count"] > 0
            and failure_taxonomy_packet["auth_unavailable_present"]
            and recovery_packet["owner_action_required"]
        ),
        "selection_truth_recovered_but_runtime_auth_still_blocked": (
            selection_packet["health_selected_backend_ids_observed_count"] > 0
            and selection_packet["health_selected_backend_ids_observed_count"] > 0
            and post_sync_direct_probe.get("http_status") == 503
        ),
        "recommended_closure": (
            "blocker_localized_owner_action_required"
            if recovery_packet["hard_blocker_precisely_localized"]
            else "further_repair_needed"
        ),
    }

    return {
        "native_backend_selection_truth_packet.json": selection_packet,
        "native_auth_recovery_attempt_packet.json": recovery_packet,
        "native_auth_failure_taxonomy_packet.json": failure_taxonomy_packet,
        "native_recovered_candidate_probe_packet.json": recovered_candidate_packet,
        "native_runtime_alignment_packet.json": runtime_alignment_packet,
        "native_auth_non_claims_packet.json": non_claims_packet,
        "false_green_boundary_packet.json": false_green_boundary_packet,
        "independent_audit_packet.json": independent_audit_packet,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    packets = build_packets(repo_root=REPO_ROOT)
    for name, payload in packets.items():
        json_write(output_dir / name, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
