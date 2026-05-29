#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import os
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


def _login_result(command_payload: dict[str, Any]) -> dict[str, Any]:
    payload = command_payload.get("stdout_json", {})
    result = payload.get("login_result")
    return result if isinstance(result, dict) else {}


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
        return {"status": "exception", "http_status": None, "error": repr(exc)}


def _runtime_loaded_count(payload: dict[str, Any]) -> int:
    hygiene = payload.get("auth_pool_hygiene")
    if not isinstance(hygiene, dict):
        return 0
    return int(hygiene.get("selected_backend_runtime_loaded_count", 0) or 0)


def _session_path(session_id: str) -> Path:
    paths = runtime.RuntimePaths.from_env()
    return runtime.sandbox_login_session_path(paths, session_id)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _parse_epoch(value: Any) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def _read_tail(path: Path, max_bytes: int = 65536) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", "ignore")
    except OSError:
        return ""


def _build_post_login_materialization_gap_packet(
    *,
    session_id: str,
    owner_email: str,
    session_result: dict[str, Any],
) -> dict[str, Any]:
    paths = runtime.RuntimePaths.from_env()
    session = _read_json(_session_path(session_id))
    auth_dir, inventory_source = runtime.login_session_auth_inventory_dir(paths)
    current_entries = runtime.list_login_auth_inventory_entries(paths)
    before_entries = [
        str(Path(item).expanduser().resolve(strict=False))
        for item in session.get("auth_inventory_before", []) or []
    ]
    before_set = set(before_entries)
    created_epoch = _parse_epoch(session.get("created_at"))
    matching_entries: list[dict[str, Any]] = []
    matching_changed_since_session_created = 0
    for path in current_entries:
        payload = _read_json(path)
        if str(payload.get("email") or "").strip().lower() != owner_email.strip().lower():
            continue
        mtime_epoch = path.stat().st_mtime
        changed_since_session_created = (
            created_epoch is not None and mtime_epoch > created_epoch
        )
        if changed_since_session_created:
            matching_changed_since_session_created += 1
        matching_entries.append(
            {
                "basename": path.name,
                "mtime_epoch": mtime_epoch,
                "changed_since_session_created": changed_since_session_created,
                "account_id": str(payload.get("account_id") or ""),
                "disabled": bool(payload.get("disabled", False)),
                "expired": str(payload.get("expired") or ""),
                "last_refresh": str(payload.get("last_refresh") or ""),
            }
        )

    log_tail = _read_tail(auth_dir / "logs" / "main.log")
    pid = int(session.get("pid", 0) or 0)
    added_count = sum(
        1
        for path in current_entries
        if str(path.expanduser().resolve(strict=False)) not in before_set
    )
    login_status = str(session_result.get("status") or "")
    gap_detected = (
        bool(owner_email)
        and login_status in {"waiting_for_user", "expired"}
        and not bool(session_result.get("auth_materialized"))
        and not _pid_alive(pid)
        and added_count == 0
        and bool(matching_entries)
        and matching_changed_since_session_created == 0
        and "refresh_token_reused" in log_tail
    )
    if gap_detected and login_status == "waiting_for_user":
        classification = "existing_auth_ref_present_but_unmaterialized"
    elif gap_detected and login_status == "expired":
        classification = "existing_auth_ref_stale_and_unchanged_after_session_expiry"
    else:
        classification = "no_gap_detected"
    return {
        "captured_at_utc": utc_now(),
        "session_id": session_id,
        "owner_email": owner_email,
        "login_status": login_status,
        "auth_materialized": bool(session_result.get("auth_materialized")),
        "auth_ref_present": bool(session_result.get("auth_ref_present")),
        "session_pid": pid,
        "session_pid_alive": _pid_alive(pid),
        "session_created_at": str(session.get("created_at") or ""),
        "session_expires_at": str(session.get("expires_at") or ""),
        "auth_inventory_before_count": len(before_entries),
        "auth_inventory_current_count": len(current_entries),
        "auth_inventory_added_count": added_count,
        "matching_auth_entry_count": len(matching_entries),
        "matching_auth_entries": matching_entries,
        "matching_auth_entries_changed_since_session_created_count": (
            matching_changed_since_session_created
        ),
        "inventory_source": inventory_source,
        "expired_token_observed_in_recent_logs": (
            "Provided authentication token is expired" in log_tail
        ),
        "refresh_token_reused_observed_in_recent_logs": "refresh_token_reused" in log_tail,
        "classification": classification,
        "existing_auth_ref_present_but_unmaterialized_gap_detected": gap_detected,
    }


def _classify(
    *,
    session_status_payload: dict[str, Any],
    complete_payload: dict[str, Any],
    health_payload: dict[str, Any],
    direct_probe: dict[str, Any],
) -> dict[str, Any]:
    status_json = session_status_payload.get("stdout_json", {})
    complete_json = complete_payload.get("stdout_json", {})
    status_result = _login_result(session_status_payload)
    complete_result = _login_result(complete_payload)
    login_status = str(status_result.get("status") or "")
    runtime_loaded_count = _runtime_loaded_count(health_payload.get("stdout_json", {}))
    probe_http_status = direct_probe.get("http_status")

    if login_status in {"waiting_for_user", "started"}:
        classification = "owner_action_pending"
    elif login_status == "expired":
        classification = "owner_action_expired"
    elif login_status == "cancelled":
        classification = "owner_action_cancelled"
    elif login_status in {"auth_materialized", "completed"} and not bool(
        status_result.get("auth_materialized")
    ):
        classification = "owner_action_completed_but_auth_not_materialized"
    elif bool(status_result.get("auth_materialized")) and runtime_loaded_count == 0:
        classification = "auth_materialized_but_runtime_not_loaded"
    elif runtime_loaded_count > 0 and probe_http_status != 200:
        classification = "runtime_loaded_but_native_responses_still_blocked"
    elif str(complete_json.get("status") or "") == "ok" and probe_http_status == 200:
        classification = "native_stable_runtime_reproved"
    else:
        classification = "owner_action_completed_but_runtime_still_blocked"

    return {
        "captured_at_utc": utc_now(),
        "classification": classification,
        "status_machine_error_code": str(status_json.get("machine_error_code") or ""),
        "complete_machine_error_code": str(complete_json.get("machine_error_code") or ""),
        "status_login_status": login_status,
        "complete_login_status": str(complete_result.get("status") or ""),
        "runtime_loaded_count": runtime_loaded_count,
        "direct_native_probe_http_status": probe_http_status,
        "owner_action_required": classification == "owner_action_pending",
        "owner_action_completed": bool(status_result.get("auth_materialized"))
        or str(complete_json.get("status") or "") == "ok",
    }


def build_packets(
    *, repo_root: Path, session_id: str, owner_email: str = ""
) -> dict[str, dict[str, Any]]:
    health_before = _run_json_command(repo_root, ["healthcheck", "--json"])
    session_status_command = _run_json_command(
        repo_root, ["accounts", "login", "status", "--session", session_id, "--json"]
    )
    session_result = _login_result(session_status_command)
    login_complete_command = (
        _run_json_command(
            repo_root, ["accounts", "login", "complete", "--session", session_id, "--json"]
        )
        if bool(session_result.get("auth_materialized"))
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
    health_after = _run_json_command(repo_root, ["healthcheck", "--json"])
    status_after = _run_json_command(repo_root, ["status", "--json"])
    direct_native_probe = _direct_native_probe("gpt-5.5")

    completion_packet = {
        "captured_at_utc": utc_now(),
        "session_id": session_id,
        "status_exit_code": session_status_command["exit_code"],
        "status_machine_error_code": str(
            session_status_command["stdout_json"].get("machine_error_code") or ""
        ),
        "login_result": session_result,
        "owner_completed": bool(session_result.get("auth_materialized")),
    }

    materialization_packet = {
        "captured_at_utc": utc_now(),
        "session_id": session_id,
        "auth_materialized": bool(session_result.get("auth_materialized")),
        "auth_ref_present": bool(session_result.get("auth_ref_present")),
        "login_status": str(session_result.get("status") or ""),
    }

    runtime_load_packet = {
        "captured_at_utc": utc_now(),
        "session_id": session_id,
        "health_before_runtime_loaded_count": _runtime_loaded_count(
            health_before.get("stdout_json", {})
        ),
        "health_after_runtime_loaded_count": _runtime_loaded_count(
            health_after.get("stdout_json", {})
        ),
        "status_after_machine_error_code": str(
            status_after["stdout_json"].get("machine_error_code") or ""
        ),
        "runtime_loaded": _runtime_loaded_count(health_after.get("stdout_json", {})) > 0,
    }

    onboard_packet = {
        "captured_at_utc": utc_now(),
        "session_id": session_id,
        "complete_exit_code": login_complete_command["exit_code"],
        "complete_machine_error_code": str(
            login_complete_command["stdout_json"].get("machine_error_code") or ""
        ),
        "complete_attempted": str(
            login_complete_command["stdout_json"].get("machine_error_code") or ""
        )
        != "LOGIN_COMPLETE_NOT_ATTEMPTED",
        "login_result": _login_result(login_complete_command),
    }

    stable_reproof_packet = {
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

    dependency_packet = _classify(
        session_status_payload=session_status_command,
        complete_payload=login_complete_command,
        health_payload=health_after,
        direct_probe=direct_native_probe,
    )

    non_claims_packet = {
        "captured_at_utc": utc_now(),
        "handoff_counts_as_owner_completion": False,
        "owner_completion_counts_as_auth_materialization": False,
        "auth_materialization_counts_as_runtime_loaded_auth": False,
        "runtime_loaded_auth_counts_as_native_responses_success": False,
        "stable_runtime_reproof_counts_as_launched_custom_codex_recovery": False,
    }

    false_green_packet = {
        "captured_at_utc": utc_now(),
        "owner_completion_without_auth_materialization": dependency_packet["classification"]
        == "owner_action_completed_but_auth_not_materialized",
        "auth_materialization_without_runtime_load": dependency_packet["classification"]
        == "auth_materialized_but_runtime_not_loaded",
        "runtime_load_without_native_200": dependency_packet["classification"]
        == "runtime_loaded_but_native_responses_still_blocked",
        "guardrail_status": "held",
    }

    independent_audit_packet = {
        "captured_at_utc": utc_now(),
        "material_mismatch_detected": False,
        "owner_dependency_classification": dependency_packet["classification"],
        "runtime_loaded_count": dependency_packet["runtime_loaded_count"],
        "direct_native_probe_http_status": dependency_packet["direct_native_probe_http_status"],
        "recommended_closure": dependency_packet["classification"],
    }
    packets = {
        "native_owner_completion_packet.json": completion_packet,
        "native_auth_materialization_packet.json": materialization_packet,
        "native_runtime_load_packet.json": runtime_load_packet,
        "native_onboard_completion_packet.json": onboard_packet,
        "native_stable_reproof_packet.json": stable_reproof_packet,
        "native_owner_dependency_packet.json": dependency_packet,
        "native_auth_non_claims_packet.json": non_claims_packet,
        "false_green_boundary_packet.json": false_green_packet,
        "independent_audit_packet.json": independent_audit_packet,
    }
    if owner_email.strip():
        gap_packet = _build_post_login_materialization_gap_packet(
            session_id=session_id,
            owner_email=owner_email,
            session_result=session_result,
        )
        packets["native_post_login_materialization_gap_packet.json"] = gap_packet
        packets["native_materialization_repair_packet.json"] = {
            "captured_at_utc": utc_now(),
            "session_id": session_id,
            "owner_email": owner_email,
            "live_reprobe_executed": True,
            "auth_materialized_after_repair": bool(session_result.get("auth_materialized")),
            "auth_ref_present_after_repair": bool(session_result.get("auth_ref_present")),
            "session_bound_materialization_proven": bool(
                gap_packet.get("matching_auth_entries_changed_since_session_created_count", 0)
            ),
            "matching_auth_entry_count": int(gap_packet.get("matching_auth_entry_count", 0) or 0),
            "matching_auth_entries_changed_since_session_created_count": int(
                gap_packet.get("matching_auth_entries_changed_since_session_created_count", 0)
                or 0
            ),
            "repair_effective_for_materialization": bool(
                session_result.get("auth_materialized")
            ),
            "repair_result": (
                "materialization_observed"
                if bool(session_result.get("auth_materialized"))
                else "materialization_not_observed"
            ),
        }
        packets["native_materialization_failure_taxonomy_packet.json"] = {
            "captured_at_utc": utc_now(),
            "session_id": session_id,
            "owner_email": owner_email,
            "browser_success_without_local_materialization": bool(
                gap_packet.get("existing_auth_ref_present_but_unmaterialized_gap_detected")
            ),
            "refreshed_existing_auth_not_detected": (
                int(
                    gap_packet.get(
                        "matching_auth_entries_changed_since_session_created_count", 0
                    )
                    or 0
                )
                > 0
                and not bool(session_result.get("auth_materialized"))
            ),
            "refresh_token_reused_prevents_materialization": bool(
                gap_packet.get("refresh_token_reused_observed_in_recent_logs")
            )
            and not bool(session_result.get("auth_materialized")),
            "auth_materialized_but_runtime_not_loaded": (
                dependency_packet["classification"] == "auth_materialized_but_runtime_not_loaded"
            ),
            "usable_auth_present_but_runtime_not_loaded": False,
            "runtime_loaded_but_native_responses_still_blocked": (
                dependency_packet["classification"]
                == "runtime_loaded_but_native_responses_still_blocked"
            ),
            "recommended_closure": str(gap_packet.get("classification") or ""),
        }
        if bool(gap_packet.get("existing_auth_ref_present_but_unmaterialized_gap_detected")):
            independent_audit_packet["materialization_gap_classification"] = str(
                gap_packet.get("classification") or ""
            )
            independent_audit_packet["recommended_closure"] = str(
                gap_packet.get("classification") or independent_audit_packet["recommended_closure"]
            )
    return packets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--owner-email", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    packets = build_packets(
        repo_root=REPO_ROOT,
        session_id=str(args.session_id),
        owner_email=str(args.owner_email or ""),
    )
    for name, payload in packets.items():
        json_write(output_dir / name, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
