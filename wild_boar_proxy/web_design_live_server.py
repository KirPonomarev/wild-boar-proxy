# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Read-only live preview server for the first web-design screen."""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from wild_boar_proxy.ui_shell import (
    JsonCommandRunner,
    UiShellError,
    build_account_pool_snapshot,
    build_runtime_snapshot,
)
from wild_boar_proxy.web_design_command_adapter import CommandRunner, execute_command


ROOT = Path(__file__).resolve().parents[1]
WEB_DESIGN_UI = ROOT / "wild_boar_proxy" / "web_design_ui"
READONLY_COMMAND_IDS = (
    "status",
    "mode_get",
    "accounts_list",
    "healthcheck",
    "rollout_rotation_inspect",
)
PRIMARY_COMMAND_IDS = ("status", "mode_get", "accounts_list")
DETAIL_COMMAND_IDS = ("healthcheck", "rollout_rotation_inspect")
ACCOUNTS_READONLY_COMMAND_IDS = ("accounts_list",)
ACCOUNT_ID_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "._-:@"
)
ACCOUNT_ID_UI_ACTIONS = frozenset(
    {
        "validate_account",
        "promote_account",
        "demote_account",
        "retire_account",
        "hold_account",
        "release_account",
    }
)
UI_ACTION_ALLOWLIST = {
    "refresh_health_detail": {
        "adapter_command_id": "healthcheck",
        "action_role": "runtime_detail",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "runtime detail refresh only",
        "display_name": "Healthcheck",
        "human_meaning": "Refresh runtime health detail without changing runtime state.",
    },
    "export_diagnostics": {
        "adapter_command_id": "diagnostics_export",
        "action_role": "support_artifact",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "support artifact only",
        "display_name": "Diagnostics export",
        "human_meaning": "Create a diagnostics support artifact without making it runtime truth.",
    },
    "stable_repair_plan": {
        "adapter_command_id": "stable_repair_dry_run",
        "action_role": "recovery_planning",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "dry-run recovery planning only",
        "display_name": "Stable repair dry-run",
        "human_meaning": "Preview stable repair work without applying changes.",
    },
    "validate_account": {
        "adapter_command_id": "accounts_validate",
        "action_role": "account_verification",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account verification request only; refreshed accounts list remains truth",
        "display_name": "Validate account",
        "human_meaning": "Run account verification for the selected account, then refresh accounts truth.",
    },
    "promote_account": {
        "adapter_command_id": "accounts_promote",
        "action_role": "account_lifecycle_promotion",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account promotion request only; refreshed accounts list remains truth",
        "display_name": "Promote account",
        "human_meaning": "Request reserve-to-active promotion for the selected account, then refresh accounts truth.",
    },
    "demote_account": {
        "adapter_command_id": "accounts_demote",
        "action_role": "account_lifecycle_demotion",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account demotion request only; refreshed accounts list remains truth",
        "display_name": "Demote account",
        "human_meaning": "Request active-to-reserve demotion for the selected account, then refresh accounts truth.",
    },
    "retire_account": {
        "adapter_command_id": "accounts_retire",
        "action_role": "account_lifecycle_retirement",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "terminal account retirement request only; refreshed accounts list remains truth",
        "display_name": "Retire account",
        "human_meaning": "Request terminal lifecycle retirement for the selected account, then refresh accounts truth.",
    },
    "hold_account": {
        "adapter_command_id": "accounts_hold",
        "action_role": "account_lifecycle_hold",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account hold request only; refreshed accounts list remains truth",
        "display_name": "Hold account",
        "human_meaning": "Place the selected account on manual hold, then refresh accounts truth.",
    },
    "release_account": {
        "adapter_command_id": "accounts_release",
        "action_role": "account_lifecycle_release",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "account release request only; refreshed accounts list remains truth",
        "display_name": "Release account",
        "human_meaning": "Release the selected account from manual hold, then refresh accounts truth.",
    },
    "sync_runtime": {
        "adapter_command_id": "sync",
        "action_role": "controlled_runtime_mutation",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "sync request only; refreshed live overview remains truth",
        "display_name": "Sync runtime",
        "human_meaning": "Run managed sync, then refresh the overview from live JSON truth.",
    },
    "set_mode_stable": {
        "adapter_command_id": "mode_stable",
        "action_role": "controlled_mode_mutation",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "mode request only; refreshed live overview remains truth",
        "display_name": "Set stable mode",
        "human_meaning": "Request stable mode, then refresh desired/effective mode from live JSON truth.",
    },
    "set_mode_managed": {
        "adapter_command_id": "mode_managed",
        "action_role": "controlled_mode_mutation",
        "mutates_runtime": True,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "mode request only; refreshed live overview remains truth",
        "display_name": "Set managed mode",
        "human_meaning": "Request managed mode, then refresh desired/effective mode from live JSON truth.",
    },
    "launch_smoke": {
        "adapter_command_id": "smoke",
        "action_role": "runtime_smoke_check",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": True,
        "action_claim_scope": "runtime smoke check only; not host-client launch success",
        "display_name": "Launch smoke",
        "human_meaning": "Run a runtime smoke check without claiming host-client launch success.",
    },
    "launch_client_dispatch": {
        "adapter_command_id": "launch_client",
        "action_role": "host_client_dispatch",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": True,
        "post_action_refresh_required": True,
        "action_claim_scope": "bounded OS dispatch request only; not host-client session success",
        "display_name": "Launch client",
        "human_meaning": "Request bounded host-client dispatch, then refresh live overview truth.",
    },
}


def build_live_readonly_snapshot(runner: CommandRunner) -> dict[str, Any]:
    commands: dict[str, dict[str, Any]] = {}
    for command_id in PRIMARY_COMMAND_IDS:
        result = execute_command(runner, command_id)
        commands[command_id] = result
        if result["status"] != "ok":
            return _integration_failure(
                "Live read-only primary command failed.",
                str(result["human_message"]),
                str(result["machine_error_code"]),
                commands,
            )

    try:
        runtime = build_runtime_snapshot(
            status_payload=commands["status"]["packet"],
            mode_payload=commands["mode_get"]["packet"],
        )
        accounts = build_account_pool_snapshot(commands["accounts_list"]["packet"])
    except UiShellError as exc:
        return _integration_failure(
            "Live read-only packet validation failed.",
            str(exc),
            "UI_LIVE_READONLY_PACKET_INVALID",
            commands,
        )

    warnings: list[dict[str, str]] = []
    for command_id in DETAIL_COMMAND_IDS:
        result = execute_command(runner, command_id)
        commands[command_id] = result
        if result["status"] != "ok":
            warnings.append(_warning_from_result(command_id, result))

    visual_state = _visual_state(runtime.liveness)
    if visual_state == "healthy" and any(warning["severity"] == "degraded" for warning in warnings):
        visual_state = "degraded"
    hold_count = sum(1 for account in accounts.accounts if account.manual_hold)
    problem_count = sum(
        1
        for account in accounts.accounts
        if account.status in {"down", "degraded"} or bool(account.last_error)
    )

    return {
        "schema_version": 1,
        "status": "ok",
        "ui_state": visual_state,
        "source": "live_readonly",
        "primary_truth_ok": True,
        "has_warnings": bool(warnings),
        "warnings": warnings,
        "evidence_summary": _evidence_summary(commands, warnings),
        "runtime": {
            "visual_state": visual_state,
            "status_label": _status_label(visual_state),
            "desired_mode": runtime.desired_mode,
            "effective_mode": runtime.effective_mode,
            "endpoint": runtime.endpoint or runtime.current_proxy_url,
            "machine_error_code": runtime.machine_error_code,
            "human_message": runtime.human_message,
            "last_error": runtime.last_error,
            "observed_at_utc": runtime.attestation_observed_at,
        },
        "pool_summary": {
            "active": accounts.active_count,
            "reserve": accounts.reserve_count,
            "hold": hold_count,
            "problem": problem_count,
            "active_note": f"{runtime.active_count} active in status packet",
            "reserve_note": f"{runtime.reserve_count} reserve in status packet",
            "hold_note": "manual hold accounts",
            "problem_note": "degraded/down/error accounts",
        },
        "events": _events_from_commands(commands, visual_state, warnings),
        "commands": _public_command_results(commands),
    }


def build_accounts_readonly_snapshot(runner: CommandRunner) -> dict[str, Any]:
    result = execute_command(runner, "accounts_list")
    commands = {"accounts_list": result}
    if result["status"] != "ok":
        return _accounts_integration_failure(
            "Accounts read-only command failed.",
            str(result["human_message"]),
            str(result["machine_error_code"]),
        )

    packet = result["packet"]
    try:
        accounts = build_account_pool_snapshot(packet)
    except UiShellError as exc:
        return _accounts_integration_failure(
            "Accounts read-only packet validation failed.",
            str(exc),
            "UI_ACCOUNTS_READONLY_PACKET_INVALID",
        )

    rows = _account_rows(accounts.accounts, packet)
    summary = _account_summary(rows, accounts)
    return {
        "schema_version": 1,
        "status": "ok",
        "source": "accounts_readonly",
        "primary_truth_ok": True,
        "privacy": {
            "redacted": True,
            "raw_command_packet_included": False,
            "forbidden_fields_excluded": ["secret_references", "tokens", "raw_paths", "raw_logs"],
        },
        "registry_identity": {
            "status": accounts.registry_identity_status,
            "machine_error_code": accounts.registry_identity_machine_error_code,
            "next_action": accounts.registry_identity_next_action,
        },
        "summary": summary,
        "accounts": rows,
        "commands": _public_command_results(commands),
    }


def run_ui_action(
    runner: CommandRunner,
    payload: dict[str, Any],
    *,
    launch_client_path: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _blocked_action("unknown", "UI action payload must be an object.")
    if "command_id" in payload:
        return _blocked_action("unknown", "Browser must submit ui_action, not command_id.")

    ui_action = payload.get("ui_action")
    if not isinstance(ui_action, str):
        return _blocked_action("unknown", "UI action must be a string.")

    action_spec = UI_ACTION_ALLOWLIST.get(ui_action)
    if action_spec is None:
        return _blocked_action(ui_action, "UI action is not allowlisted.")

    allowed_payload_keys = {"ui_action"}
    if ui_action in ACCOUNT_ID_UI_ACTIONS:
        allowed_payload_keys.add("account_id")
    unsupported_keys = sorted(set(payload) - allowed_payload_keys)
    if unsupported_keys:
        return _blocked_action(ui_action, f"Unsupported UI action fields: {', '.join(unsupported_keys)}.")

    structured_args: dict[str, str] | None = None
    allow_disabled = False
    if ui_action in ACCOUNT_ID_UI_ACTIONS:
        structured_args, blocked = _account_action_args(runner, payload, ui_action=ui_action)
        if blocked is not None:
            return blocked
    if ui_action == "launch_client_dispatch":
        if not launch_client_path:
            return _unavailable_action(
                ui_action,
                "Bounded launch client path is unavailable.",
                "UI_LAUNCH_CLIENT_PATH_UNAVAILABLE",
            )
        structured_args = {"client_path": launch_client_path}
        allow_disabled = True

    result = execute_command(
        runner,
        str(action_spec["adapter_command_id"]),
        structured_args=structured_args,
        allow_disabled=allow_disabled,
    )
    return {
        "schema_version": 1,
        "status": "ok" if result["status"] == "ok" else "command_error",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": action_spec["action_role"],
        "mutates_runtime": action_spec["mutates_runtime"],
        "affects_primary_truth": action_spec["affects_primary_truth"],
        "confirmation_required": action_spec["confirmation_required"],
        "post_action_refresh_required": action_spec["post_action_refresh_required"],
        "action_claim_scope": action_spec["action_claim_scope"],
        "account_id": structured_args.get("account_id") if structured_args else "",
        "result": _action_result(result),
    }


def ui_action_metadata(*, launch_client_path: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "ok",
        "source": "ui_action_metadata",
        "actions": {
            ui_action: {
                "ui_action": ui_action,
                "display_name": str(action_spec["display_name"]),
                "human_meaning": str(action_spec["human_meaning"]),
                "action_role": str(action_spec["action_role"]),
                "mutates_runtime": bool(action_spec["mutates_runtime"]),
                "affects_primary_truth": bool(action_spec["affects_primary_truth"]),
                "confirmation_required": bool(action_spec["confirmation_required"]),
                "post_action_refresh_required": bool(action_spec["post_action_refresh_required"]),
                "action_claim_scope": str(action_spec["action_claim_scope"]),
                "available": _action_available(ui_action, launch_client_path=launch_client_path),
                "unavailable_reason": _action_unavailable_reason(
                    ui_action,
                    launch_client_path=launch_client_path,
                ),
            }
            for ui_action, action_spec in sorted(UI_ACTION_ALLOWLIST.items())
        },
    }


def build_handler(
    *,
    runner: CommandRunner | None = None,
    static_dir: Path = WEB_DESIGN_UI,
    launch_client_path: str | None = None,
) -> type[BaseHTTPRequestHandler]:
    command_runner = runner or JsonCommandRunner()
    static_root = static_dir.resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/api/live-readonly":
                self._send_json(build_live_readonly_snapshot(command_runner))
                return
            if parsed.path == "/api/accounts-readonly":
                self._send_json(build_accounts_readonly_snapshot(command_runner))
                return
            if parsed.path == "/api/actions":
                self._send_json(ui_action_metadata(launch_client_path=launch_client_path))
                return
            self._send_static(parsed.path)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/action":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_json(
                run_ui_action(
                    command_runner,
                    self._read_json_body(),
                    launch_client_path=launch_client_path,
                )
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

        def _send_json(self, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return {}
            if length <= 0:
                return {}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}

        def _send_static(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            target = (static_root / relative).resolve()
            if static_root not in target.parents and target != static_root:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            body = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _blocked_action(ui_action: str, human_message: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "blocked",
        "result": {
            "status": "integration_failure",
            "machine_error_code": "UI_ACTION_NOT_ALLOWED",
            "human_message": human_message,
            "next_action": "none",
            "changed_files": [],
            "data": {},
        },
    }


def _unavailable_action(ui_action: str, human_message: str, machine_error_code: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "ui_action",
        "ui_action": ui_action,
        "action_role": "blocked",
        "mutates_runtime": False,
        "affects_primary_truth": False,
        "confirmation_required": False,
        "post_action_refresh_required": False,
        "action_claim_scope": "unavailable",
        "result": {
            "status": "integration_failure",
            "machine_error_code": machine_error_code,
            "human_message": human_message,
            "next_action": "user_action",
            "changed_files": [],
            "data": {},
        },
    }


def _account_action_args(
    runner: CommandRunner,
    payload: dict[str, Any],
    *,
    ui_action: str,
) -> tuple[dict[str, str] | None, dict[str, Any] | None]:
    account_id = payload.get("account_id")
    if not isinstance(account_id, str):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} requires account_id.",
            "UI_ACCOUNT_ID_REQUIRED",
        )
    account_id = account_id.strip()
    if (
        not account_id
        or account_id in {".", ".."}
        or len(account_id) > 96
        or any(char not in ACCOUNT_ID_SAFE_CHARS for char in account_id)
    ):
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} got an unsafe account_id.",
            "UI_ACCOUNT_ID_INVALID",
        )

    result = execute_command(runner, "accounts_list")
    if result["status"] != "ok":
        return None, _unavailable_action(
            ui_action,
            "Accounts list is unavailable; account action target cannot be verified.",
            _account_list_unavailable_code(ui_action),
        )
    try:
        accounts = build_account_pool_snapshot(result["packet"])
    except UiShellError:
        return None, _unavailable_action(
            ui_action,
            "Accounts packet is invalid; account action target cannot be verified.",
            _account_list_invalid_code(ui_action),
        )
    target_account = next(
        (account for account in accounts.accounts if account.backend_id == account_id),
        None,
    )
    if target_account is None:
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} target is not present in accounts list.",
            "UI_ACCOUNT_ID_NOT_FOUND",
        )
    if ui_action in {
        "promote_account",
        "demote_account",
        "retire_account",
        "hold_account",
        "release_account",
    } and target_account.pool == "retired":
        return None, _unavailable_action(
            ui_action,
            f"{ui_action} target is already retired; terminal retirement has no automatic return path.",
            "UI_ACCOUNT_LIFECYCLE_RETIRED_INELIGIBLE",
        )
    if ui_action == "retire_account" and target_account.pool not in {"active", "reserve"}:
        return None, _unavailable_action(
            ui_action,
            "retire_account target is not active or reserve.",
            "UI_ACCOUNT_RETIRE_INELIGIBLE",
        )
    if ui_action == "promote_account" and target_account.pool != "reserve":
        return None, _unavailable_action(
            ui_action,
            "promote_account target is not in reserve.",
            "UI_ACCOUNT_PROMOTE_INELIGIBLE",
        )
    if ui_action == "promote_account" and target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "promote_account target is on manual hold.",
            "UI_ACCOUNT_PROMOTE_INELIGIBLE",
        )
    if ui_action == "demote_account" and target_account.pool != "active":
        return None, _unavailable_action(
            ui_action,
            "demote_account target is not active.",
            "UI_ACCOUNT_DEMOTE_INELIGIBLE",
        )
    if ui_action == "demote_account" and target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "demote_account target is on manual hold.",
            "UI_ACCOUNT_DEMOTE_INELIGIBLE",
        )
    if ui_action == "hold_account" and target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "hold_account target is already on manual hold.",
            "UI_ACCOUNT_HOLD_INELIGIBLE",
        )
    if ui_action == "release_account" and not target_account.manual_hold:
        return None, _unavailable_action(
            ui_action,
            "release_account target is not on manual hold.",
            "UI_ACCOUNT_RELEASE_INELIGIBLE",
        )
    return {"account_id": account_id}, None


def _account_list_unavailable_code(ui_action: str) -> str:
    if ui_action == "validate_account":
        return "UI_ACCOUNT_VALIDATE_ACCOUNT_LIST_UNAVAILABLE"
    return "UI_ACCOUNT_LIFECYCLE_ACCOUNT_LIST_UNAVAILABLE"


def _account_list_invalid_code(ui_action: str) -> str:
    if ui_action == "validate_account":
        return "UI_ACCOUNT_VALIDATE_ACCOUNT_LIST_INVALID"
    return "UI_ACCOUNT_LIFECYCLE_ACCOUNT_LIST_INVALID"


def _action_available(ui_action: str, *, launch_client_path: str | None) -> bool:
    if ui_action == "launch_client_dispatch":
        return bool(launch_client_path)
    return True


def _action_unavailable_reason(ui_action: str, *, launch_client_path: str | None) -> str:
    if ui_action == "launch_client_dispatch" and not launch_client_path:
        return "Bounded launch client path is unavailable."
    return ""


def _action_result(result: dict[str, Any]) -> dict[str, Any]:
    packet = result.get("packet")
    data = packet.get("data", {}) if isinstance(packet, dict) else {}
    return {
        "status": result["status"],
        "machine_error_code": result["machine_error_code"],
        "human_message": result["human_message"],
        "next_action": result["next_action"],
        "changed_files": result["changed_files"],
        "data": data if isinstance(data, dict) else {},
    }


def _integration_failure(
    human_message: str,
    last_error: str,
    machine_error_code: str,
    commands: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "ui_state": "integration_failure",
        "source": "live_readonly",
        "primary_truth_ok": False,
        "has_warnings": True,
        "warnings": [
            {
                "command_id": "primary_truth",
                "role": "primary",
                "severity": "integration_failure",
                "machine_error_code": machine_error_code,
                "human_message": last_error,
            }
        ],
        "evidence_summary": {
            "primary_truth_ok": False,
            "detail_warnings": 0,
            "rollout_warnings": 0,
            "highest_warning_severity": "integration_failure",
        },
        "runtime": {
            "visual_state": "integration_failure",
            "status_label": "Ошибка интеграции",
            "desired_mode": "unknown",
            "effective_mode": "unknown",
            "endpoint": "unknown",
            "machine_error_code": machine_error_code,
            "human_message": human_message,
            "last_error": last_error,
            "observed_at_utc": "live-readonly",
        },
        "pool_summary": {
            "active": 0,
            "reserve": 0,
            "hold": 0,
            "problem": 0,
            "active_note": "live read failed",
            "reserve_note": "live read failed",
            "hold_note": "live read failed",
            "problem_note": "live read failed",
        },
        "events": [
            {
                "level": "red",
                "message": human_message,
                "observed_at": "live-readonly",
            }
        ],
        "commands": _public_command_results(commands),
    }


def _accounts_integration_failure(
    human_message: str,
    last_error: str,
    machine_error_code: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "integration_failure",
        "source": "accounts_readonly",
        "primary_truth_ok": False,
        "privacy": {
            "redacted": True,
            "raw_command_packet_included": False,
            "forbidden_fields_excluded": ["secret_references", "tokens", "raw_paths", "raw_logs"],
        },
        "registry_identity": {
            "status": "unknown",
            "machine_error_code": machine_error_code,
            "next_action": "retry",
        },
        "summary": {
            "active": 0,
            "reserve": 0,
            "retired": 0,
            "hold": 0,
            "problem": 0,
            "healthy": 0,
            "degraded": 0,
            "down": 0,
            "capacity_target": 20,
            "visible_count": 0,
            "human_message": human_message,
            "machine_error_code": machine_error_code,
            "last_error": last_error,
        },
        "accounts": [],
        "commands": {},
    }


def _public_command_results(commands: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        command_id: {
            "status": result["status"],
            "ui_state": result["ui_state"],
            "role": _command_role(command_id),
            "machine_error_code": result["machine_error_code"],
            "human_message": result["human_message"],
            "exit_code": result["exit_code"],
            "next_action": result["next_action"],
        }
        for command_id, result in commands.items()
    }


def _account_rows(accounts: tuple[Any, ...], packet: dict[str, Any]) -> list[dict[str, Any]]:
    raw_by_id = {
        str(item.get("id")): item
        for item in packet.get("accounts", [])
        if isinstance(item, dict) and "id" in item
    }
    return [
        {
            "id": _safe_account_id(account.backend_id),
            "label": _safe_account_label(account.label, account.backend_id),
            "pool": account.pool,
            "pool_label": _pool_label(account.pool, account.manual_hold),
            "status": account.status,
            "status_label": _account_status_label(account.status, account.manual_hold),
            "visual_state": _account_visual_state(account.status, account.manual_hold, account.last_error),
            "manual_hold": account.manual_hold,
            "enabled": _optional_bool(raw_by_id.get(account.backend_id, {}), "enabled"),
            "fail_count": account.fail_count,
            "success_count": account.success_count,
            "last_success": account.last_success,
            "last_error_class": _safe_short_text(
                raw_by_id.get(account.backend_id, {}).get("last_error_class", "")
            ),
            "last_error_summary": _redact_error(account.last_error),
            "cooldown_until": account.cooldown_until,
            "notes_summary": _safe_short_text(account.notes),
        }
        for account in accounts
    ]


def _account_summary(rows: list[dict[str, Any]], accounts: Any) -> dict[str, Any]:
    return {
        "active": accounts.active_count,
        "reserve": accounts.reserve_count,
        "retired": accounts.retired_count,
        "hold": sum(1 for row in rows if row["manual_hold"]),
        "problem": sum(
            1
            for row in rows
            if row["visual_state"] in {"red", "amber"} or bool(row["last_error_summary"])
        ),
        "healthy": sum(1 for row in rows if row["status"] == "healthy"),
        "degraded": sum(1 for row in rows if row["status"] == "degraded"),
        "down": sum(1 for row in rows if row["status"] == "down"),
        "capacity_target": accounts.capacity_target,
        "visible_count": len(rows),
        "human_message": accounts.human_message,
        "machine_error_code": accounts.machine_error_code,
        "last_error": "",
    }


def _safe_account_id(value: str) -> str:
    return _safe_short_text(value, max_length=64) or "unknown-account"


def _safe_account_label(label: str, backend_id: str) -> str:
    value = label or backend_id
    if "@" in value:
        left, _, domain = value.partition("@")
        safe_left = left[:3] + "***" if left else "***"
        domain_tail = domain.split(".")[-1] if "." in domain else "account"
        return f"{safe_left}@***.{domain_tail}"
    return _safe_short_text(value, max_length=72) or _safe_account_id(backend_id)


def _safe_short_text(value: object, *, max_length: int = 96) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("\r", " ").strip()
    for marker in (
        "/" + "Users/",
        "/" + "Volumes/",
        "/" + "tmp/",
        "/" + "var/",
        ".cli" + "-proxy-api",
        ".co" + "dex",
    ):
        text = text.replace(marker, "[redacted]/")
    if len(text) > max_length:
        return f"{text[: max_length - 1]}…"
    return text


def _redact_error(value: str) -> str:
    text = _safe_short_text(value, max_length=120)
    if not text:
        return ""
    if "HTTP 429" in text or "usage_limit" in text or "quota" in text:
        return "quota or usage limit"
    if "HTTP 401" in text or "auth" in text.lower() or "session" in text.lower():
        return "auth/session error"
    if "timeout" in text.lower():
        return "timeout"
    return text


def _optional_bool(raw: dict[str, Any], key: str) -> bool | None:
    value = raw.get(key)
    return value if isinstance(value, bool) else None


def _pool_label(pool: str, manual_hold: bool) -> str:
    if manual_hold:
        return "На удержании"
    return {
        "active": "Активные",
        "reserve": "Резерв",
        "retired": "Выведен",
    }.get(pool, pool)


def _account_status_label(status: str, manual_hold: bool) -> str:
    if manual_hold:
        return "Удержание"
    return {
        "healthy": "Работает",
        "degraded": "Деградация",
        "down": "Недоступен",
        "unknown": "Неизвестно",
    }.get(status, status)


def _account_visual_state(status: str, manual_hold: bool, last_error: str) -> str:
    if manual_hold:
        return "amber"
    if status == "healthy" and not last_error:
        return "green"
    if status == "down" or last_error:
        return "red"
    if status == "degraded":
        return "amber"
    return "neutral"


def _events_from_commands(
    commands: dict[str, dict[str, Any]],
    visual_state: str,
    warnings: list[dict[str, str]],
) -> list[dict[str, str]]:
    events = [
        {
            "level": "green" if visual_state == "healthy" else "amber",
            "message": str(commands["status"]["human_message"]),
            "observed_at": "status --json",
        },
    ]
    for warning in warnings:
        events.append(
            {
                "level": "amber",
                "message": warning["human_message"],
                "observed_at": warning["command_id"],
            }
        )
    for command_id in DETAIL_COMMAND_IDS:
        if command_id in commands and commands[command_id]["status"] == "ok":
            events.append(
                {
                    "level": "blue",
                    "message": str(commands[command_id]["human_message"]),
                    "observed_at": _command_observed_at(command_id),
                }
            )
    return events


def _warning_from_result(command_id: str, result: dict[str, Any]) -> dict[str, str]:
    return {
        "command_id": command_id,
        "label": _command_observed_at(command_id),
        "role": _command_role(command_id),
        "severity": "degraded" if command_id == "healthcheck" else "warning",
        "machine_error_code": str(result["machine_error_code"]),
        "human_message": str(result["human_message"]),
    }


def _evidence_summary(
    commands: dict[str, dict[str, Any]],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "primary_truth_ok": True,
        "detail_warnings": sum(1 for warning in warnings if warning["role"] == "runtime_detail"),
        "rollout_warnings": sum(1 for warning in warnings if warning["role"] == "rollout_evidence"),
        "highest_warning_severity": _highest_warning_severity(warnings),
        "available_detail_commands": [
            command_id for command_id in DETAIL_COMMAND_IDS if command_id in commands
        ],
    }


def _highest_warning_severity(warnings: list[dict[str, str]]) -> str:
    if any(warning["severity"] == "degraded" for warning in warnings):
        return "degraded"
    if warnings:
        return "warning"
    return "none"


def _command_role(command_id: str) -> str:
    if command_id in PRIMARY_COMMAND_IDS:
        return "primary_truth"
    if command_id == "healthcheck":
        return "runtime_detail"
    if command_id == "rollout_rotation_inspect":
        return "rollout_evidence"
    return "unknown"


def _command_observed_at(command_id: str) -> str:
    return {
        "healthcheck": "healthcheck --json",
        "rollout_rotation_inspect": "rollout rotation inspect --json",
    }.get(command_id, command_id)


def _visual_state(liveness: str) -> str:
    if liveness in {"healthy", "degraded", "down", "stale", "unknown"}:
        return liveness
    return "integration_failure"


def _status_label(visual_state: str) -> str:
    return {
        "healthy": "Работает",
        "degraded": "Есть деградация",
        "down": "Не работает",
        "stale": "Устаревшие данные",
        "unknown": "Неизвестно",
        "integration_failure": "Ошибка интеграции",
    }.get(visual_state, "Неизвестно")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--launch-client-path", default=None)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer(
        (args.host, args.port),
        build_handler(launch_client_path=args.launch_client_path),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
