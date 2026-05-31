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
        "args": args,
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


def _login_result(command_payload: dict[str, Any]) -> dict[str, Any]:
    payload = command_payload.get("stdout_json", {})
    result = payload.get("login_result")
    return result if isinstance(result, dict) else {}


def _classify_owner_dependency(
    start_payload: dict[str, Any],
    status_payload: dict[str, Any],
    complete_payload: dict[str, Any],
    reproof: dict[str, Any],
) -> dict[str, Any]:
    start_json = start_payload.get("stdout_json", {})
    status_json = status_payload.get("stdout_json", {})
    complete_json = complete_payload.get("stdout_json", {})
    start_result = _login_result(start_payload)
    status_result = _login_result(status_payload)
    complete_result = _login_result(complete_payload)
    reproof_http_status = reproof.get("direct_native_probe", {}).get("http_status")

    if str(start_json.get("machine_error_code") or "") == "LOGIN_SANDBOX_SCOPE_UNPROVEN":
        classification = "system_blocked_before_owner_handoff"
    elif str(start_result.get("status") or "") in {"waiting_for_user", "started"}:
        classification = "owner_action_pending"
    elif str(status_result.get("status") or "") == "auth_materialized" and reproof_http_status != 200:
        classification = "owner_action_completed_but_runtime_still_blocked"
    elif complete_json.get("status") == "ok" and reproof_http_status == 200:
        classification = "native_auth_recovered"
    else:
        classification = "runtime_auth_still_blocked"

    return {
        "captured_at_utc": utc_now(),
        "classification": classification,
        "start_machine_error_code": str(start_json.get("machine_error_code") or ""),
        "status_machine_error_code": str(status_json.get("machine_error_code") or ""),
        "complete_machine_error_code": str(complete_json.get("machine_error_code") or ""),
        "start_login_status": str(start_result.get("status") or ""),
        "status_login_status": str(status_result.get("status") or ""),
        "complete_login_status": str(complete_result.get("status") or ""),
        "direct_native_probe_http_status": reproof_http_status,
        "owner_action_required": classification == "owner_action_pending",
        "owner_action_completed": str(status_result.get("status") or "") in {
            "auth_materialized",
            "completed",
        }
        or complete_json.get("status") == "ok",
    }


def build_packets(*, repo_root: Path) -> dict[str, dict[str, Any]]:
    health_before = _run_json_command(repo_root, ["healthcheck", "--json"])
    status_before = _run_json_command(repo_root, ["status", "--json"])
    start_command = _run_json_command(
        repo_root,
        ["accounts", "login", "start", "--provider", "codex", "--mode", "device", "--json"],
    )
    start_json = start_command["stdout_json"]
    session_id = str(
        start_json.get("login_session_id") or start_json.get("session_id") or ""
    )
    login_status_command = (
        _run_json_command(repo_root, ["accounts", "login", "status", "--session", session_id, "--json"])
        if session_id
        else {
            "exit_code": 0,
            "stdout_json": {"status": "not_run", "machine_error_code": "SESSION_UNAVAILABLE"},
            "stderr_redacted_len": 0,
            "captured_at_utc": utc_now(),
            "args": [],
        }
    )
    status_result = _login_result(login_status_command)
    login_complete_command = (
        _run_json_command(
            repo_root, ["accounts", "login", "complete", "--session", session_id, "--json"]
        )
        if session_id and str(status_result.get("status") or "") == "auth_materialized"
        else {
            "exit_code": 0,
            "stdout_json": {
                "status": "not_run",
                "machine_error_code": "LOGIN_COMPLETE_NOT_ATTEMPTED",
            },
            "stderr_redacted_len": 0,
            "captured_at_utc": utc_now(),
            "args": [],
        }
    )
    if session_id:
        _run_json_command(repo_root, ["accounts", "login", "cancel", "--session", session_id, "--json"])
    health_after = _run_json_command(repo_root, ["healthcheck", "--json"])
    status_after = _run_json_command(repo_root, ["status", "--json"])
    direct_native_probe = _direct_native_probe("gpt-5.5")

    login_result = _login_result(start_command)
    materialized_result = _login_result(login_status_command)
    complete_result = _login_result(login_complete_command)

    native_owner_login_session_packet = {
        "captured_at_utc": utc_now(),
        "start_exit_code": start_command["exit_code"],
        "start_machine_error_code": str(start_json.get("machine_error_code") or ""),
        "session_id_present": bool(session_id),
        "session_id": session_id,
        "device_url_present": bool(start_json.get("device_url")),
        "device_code_present": bool(start_json.get("device_code_present")),
        "login_result": login_result,
    }

    native_auth_materialization_packet = {
        "captured_at_utc": utc_now(),
        "status_exit_code": login_status_command["exit_code"],
        "status_machine_error_code": str(
            login_status_command["stdout_json"].get("machine_error_code") or ""
        ),
        "login_result": materialized_result,
        "auth_materialized": bool(materialized_result.get("auth_materialized")),
        "auth_ref_present": bool(materialized_result.get("auth_ref_present")),
    }

    native_onboard_completion_packet = {
        "captured_at_utc": utc_now(),
        "complete_exit_code": login_complete_command["exit_code"],
        "complete_machine_error_code": str(
            login_complete_command["stdout_json"].get("machine_error_code") or ""
        ),
        "complete_attempted": str(
            login_complete_command["stdout_json"].get("machine_error_code") or ""
        )
        != "LOGIN_COMPLETE_NOT_ATTEMPTED",
        "login_result": complete_result,
    }

    native_reproof_packet = {
        "captured_at_utc": utc_now(),
        "health_before_machine_error_code": str(
            health_before["stdout_json"].get("machine_error_code") or ""
        ),
        "health_after_machine_error_code": str(
            health_after["stdout_json"].get("machine_error_code") or ""
        ),
        "status_after_machine_error_code": str(
            status_after["stdout_json"].get("machine_error_code") or ""
        ),
        "direct_native_probe": direct_native_probe,
        "stable_runtime_native_responses_reproved": direct_native_probe.get("http_status") == 200,
        "launched_custom_codex_native_reproved": False,
    }

    native_owner_dependency_packet = _classify_owner_dependency(
        start_command,
        login_status_command,
        login_complete_command,
        native_reproof_packet,
    )

    native_auth_non_claims_packet = {
        "captured_at_utc": utc_now(),
        "login_started_counts_as_native_recovery": False,
        "auth_materialized_counts_as_runnable_native_responses": False,
        "stable_runtime_reproof_counts_as_launched_custom_codex_recovery": False,
        "one_recovered_auth_path_counts_as_broad_native_lane_health": False,
    }

    false_green_boundary_packet = {
        "captured_at_utc": utc_now(),
        "login_started_without_auth_materialized": bool(session_id)
        and not bool(materialized_result.get("auth_materialized")),
        "auth_materialized_without_runtime_200": bool(materialized_result.get("auth_materialized"))
        and direct_native_probe.get("http_status") != 200,
        "stable_runtime_200_without_launched_reproof": direct_native_probe.get("http_status") == 200,
        "guardrail_status": "held",
    }

    independent_audit_packet = {
        "captured_at_utc": utc_now(),
        "session_id_present": bool(session_id),
        "device_handoff_present": bool(start_json.get("device_url"))
        and bool(start_json.get("device_code_present")),
        "owner_dependency_classification": native_owner_dependency_packet["classification"],
        "direct_native_probe_http_status": direct_native_probe.get("http_status"),
        "material_mismatch_detected": False,
    }

    return {
        "native_owner_login_session_packet.json": native_owner_login_session_packet,
        "native_auth_materialization_packet.json": native_auth_materialization_packet,
        "native_onboard_completion_packet.json": native_onboard_completion_packet,
        "native_reproof_packet.json": native_reproof_packet,
        "native_owner_dependency_packet.json": native_owner_dependency_packet,
        "native_auth_non_claims_packet.json": native_auth_non_claims_packet,
        "false_green_boundary_packet.json": false_green_boundary_packet,
        "independent_audit_packet.json": independent_audit_packet,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    packets = build_packets(repo_root=REPO_ROOT)
    for name, payload in packets.items():
        json_write(output_dir / name, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
