#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit WEB control-surface action wiring/guard evidence packets (R2)."""

from __future__ import annotations

import argparse
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TARGET_STATUS = "WBP_WEB_CONTROL_SURFACE_ACTIONS_WIRED_AND_GUARDED_R2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, *, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def _ensure_tkinter_stub() -> None:
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        stub = types.ModuleType("tkinter")

        class _Tk:
            def withdraw(self) -> None:
                return None

            def destroy(self) -> None:
                return None

        class _StringVar:
            def __init__(self, value: str = "") -> None:
                self._value = value

            def get(self) -> str:
                return self._value

            def set(self, value: str) -> None:
                self._value = value

        stub.Tk = _Tk
        stub.StringVar = _StringVar
        stub.messagebox = types.SimpleNamespace(showinfo=lambda *args, **kwargs: None)
        stub.ttk = types.SimpleNamespace()
        sys.modules["tkinter"] = stub
        sys.modules["tkinter.ttk"] = stub.ttk


def _load_modules() -> tuple[Any, Any]:
    _ensure_tkinter_stub()
    from wild_boar_proxy import web_design_live_server as live_server
    from wild_boar_proxy import web_design_command_adapter as command_adapter

    return live_server, command_adapter


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _command_packet(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok",
        "exit_code": 0,
        "human_message": "Command completed.",
        "machine_error_code": "OK",
        "changed_files": [],
        "next_action": "none",
    }
    payload.update(overrides)
    return payload


class _CommandResult:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.stderr = ""


class _MappingRunner:
    def __init__(self, payloads: dict[tuple[str, ...], dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, ...]] = []

    def run(self, *args: str) -> _CommandResult:
        self.calls.append(args)
        try:
            payload = self.payloads[args]
        except KeyError as exc:
            raise RuntimeError(f"missing payload for argv: {args}") from exc
        return _CommandResult(dict(payload))


def _api_snapshot_payloads() -> dict[tuple[str, ...], dict[str, Any]]:
    return {
        ("accounts", "login", "status", "--session", "codex-session-1", "--json"): _command_packet(
            human_message="Owner login session status captured.",
            data={
                "login_result": {
                    "status": "pending",
                    "session_id": "codex-session-1",
                    "provider": "codex",
                    "device_url": "https://example.invalid/device",
                    "device_code": "ABCD-EFGH",
                }
            },
        ),
        ("external-models", "status", "--json"): _command_packet(
            human_message="External models status captured from local route registry.",
            data={
                "registry_status": "ok",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "routes": {
                    "count": 0,
                    "enabled_count": 0,
                    "providers": [],
                    "primary_route_id": "",
                    "status": "empty",
                    "source": "local_registry",
                },
                "listener": {
                    "status": "stopped",
                    "listener_proven": False,
                    "runtime_claim_blocked": True,
                },
            },
        ),
        ("external-models", "models", "--json"): _command_packet(
            human_message="External-models route models listed from local registry.",
            data={
                "count": 0,
                "source": "local_routes_registry",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "models": [],
            },
        ),
        ("external-models", "routes", "list", "--json"): _command_packet(
            human_message="External-models routes listed from local registry.",
            data={"count": 0, "routes": []},
        ),
        ("external-models", "credentials", "status", "--provider", "openrouter", "--json"): _command_packet(
            human_message="External-models credential status collected from owner env refs.",
            data={
                "credential_result": {
                    "status": "present",
                    "provider": "openrouter",
                    "credential_ref": "OPENROUTER_API_KEY",
                    "credential_present": True,
                    "supported_sources": ["owner-env"],
                    "expected_refs": [
                        "OPENROUTER_API_KEY",
                        "WBP_OPENROUTER_API_KEY",
                        "WBP_PROVIDER_OPENROUTER_API_KEY",
                    ],
                    "provider_dashboard_url": "https://openrouter.ai/settings/keys",
                    "secret_value_exposed": False,
                    "browser_secret_intake": False,
                    "browser_path_intake": False,
                }
            },
        ),
    }


def build_web_control_surface_matrix_packet(live_server: Any, command_adapter: Any) -> dict[str, Any]:
    adapter_rows = {
        row["command_id"]: row
        for row in command_adapter.allowlist_metadata()
    }
    server_owned_actions = {
        "setup_discovery",
        "legacy_import_discovery",
        "legacy_import",
        "onboard_account_dry_run",
        "onboard_account",
        "account_login_status",
        "account_login_complete",
        "account_login_cancel",
        "api_route_credential_check",
        "api_route_connect",
        "launch_custom_client_native",
        "quick_start_check_all",
    }
    rows: list[dict[str, Any]] = []
    unwired: list[str] = []
    for ui_action, spec in sorted(live_server.UI_ACTION_ALLOWLIST.items()):
        command_id = str(spec.get("adapter_command_id") or "")
        adapter = adapter_rows.get(command_id)
        if adapter is not None:
            wiring = "wired_to_adapter_command_surface"
        elif ui_action in server_owned_actions:
            wiring = "wired_to_server_owned_packet_surface"
        else:
            wiring = "unwired"
            unwired.append(ui_action)
        rows.append(
            {
                "ui_action": ui_action,
                "adapter_command_id": command_id,
                "wiring": wiring,
                "confirmation_required": bool(spec.get("confirmation_required")),
                "adapter_ui_enabled": adapter.get("ui_enabled") if adapter is not None else None,
                "adapter_command_known": adapter is not None,
            }
        )
    return packet(
        "web_control_surface_matrix",
        status="ok" if not unwired else "blocked",
        required_action_count=len(rows),
        adapter_command_count=len(adapter_rows),
        unwired_actions=unwired,
        rows=rows,
    )


def build_readonly_live_action_boundary_packet(live_server: Any) -> dict[str, Any]:
    metadata = live_server.ui_action_metadata(action_phase=live_server.LIVE_READONLY_ACTION_PHASE)
    actions = metadata["actions"]
    mismatches: list[str] = []
    for ui_action in sorted(live_server.PARKED_IN_LIVE_READONLY_ACTIONS):
        row = actions.get(ui_action)
        if not isinstance(row, dict):
            mismatches.append(f"{ui_action}:missing")
            continue
        if row.get("available") is not False:
            mismatches.append(f"{ui_action}:available")
        if row.get("disabled_reason_code") != live_server.LIVE_READONLY_ACTION_DISABLED_REASON_CODE:
            mismatches.append(f"{ui_action}:disabled_reason_code")
        if tuple(row.get("disabled_reasons", [])) != tuple(live_server.LIVE_READONLY_ACTION_DISABLED_REASONS):
            mismatches.append(f"{ui_action}:disabled_reasons")
    expected_live_available = {"setup_discovery", "legacy_import_discovery"}
    live_available = sorted(
        name for name, row in actions.items() if isinstance(row, dict) and row.get("available") is True
    )
    unexpected_live_available = sorted(set(live_available) - expected_live_available)
    return packet(
        "readonly_live_action_boundary",
        status="ok" if not mismatches and not unexpected_live_available else "blocked",
        action_phase=live_server.LIVE_READONLY_ACTION_PHASE,
        parked_action_count=len(live_server.PARKED_IN_LIVE_READONLY_ACTIONS),
        parked_actions=sorted(live_server.PARKED_IN_LIVE_READONLY_ACTIONS),
        parked_actions_blocked_with_packet_reason=not mismatches,
        parked_action_mismatches=mismatches,
        expected_live_available_actions=sorted(expected_live_available),
        observed_live_available_actions=live_available,
        unexpected_live_available_actions=unexpected_live_available,
        disabled_reason_code=live_server.LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
    )


def build_auth_authority_boundary_packet(live_server: Any, command_adapter: Any) -> dict[str, Any]:
    internal_disabled_commands = {
        "accounts_onboard_auth_ref",
        "accounts_login_start_sandbox",
        "accounts_login_complete_sandbox",
        "accounts_login_start_codex_device",
        "accounts_login_status",
        "accounts_login_complete_codex",
        "accounts_login_cancel",
        "external_models_routes_add_server_owned",
        "external_models_credentials_status_provider",
        "external_models_credentials_status_openrouter",
        "external_models_credentials_admit_provider_owner_env",
        "external_models_credentials_admit_openrouter_owner_env",
        "launch_client",
    }
    adapter_rows = {
        row["command_id"]: row
        for row in command_adapter.allowlist_metadata()
    }
    ui_enabled_violations = [
        command_id
        for command_id in sorted(internal_disabled_commands)
        if adapter_rows.get(command_id, {}).get("ui_enabled") is not False
    ]

    runner = _MappingRunner(_api_snapshot_payloads())
    launch_contract = live_server.LaunchCopyContract(
        client_path="/bin/sh",
        profile_dir="/tmp/wbp-r2-auth-profile",
        data_dir="/tmp/wbp-r2-auth-data",
        copy_port=9121,
        action_server_port=9021,
    )
    check_rows = [
        {
            "name": "legacy_import_discovery_browser_path_forbidden",
            "result": live_server.run_ui_action(
                runner,
                {"ui_action": "legacy_import_discovery", "source_path": "/tmp/browser-owned"},
                launch_copy_contract=launch_contract,
                action_phase=live_server.SANDBOX_ACTION_PHASE,
            ),
            "expected_machine_error_code": "UI_LEGACY_IMPORT_DISCOVERY_BROWSER_PATH_FORBIDDEN",
        },
        {
            "name": "legacy_import_browser_fields_forbidden",
            "result": live_server.run_ui_action(
                runner,
                {"ui_action": "legacy_import", "token_ref": "lid-test-token", "source_dir": "/tmp/browser-owned"},
                launch_copy_contract=launch_contract,
                action_phase=live_server.SANDBOX_ACTION_PHASE,
            ),
            "expected_machine_error_code": "UI_LEGACY_IMPORT_BROWSER_FIELDS_FORBIDDEN",
        },
        {
            "name": "api_route_connect_browser_secret_forbidden",
            "result": live_server.run_ui_action(
                runner,
                {"ui_action": "api_route_connect", "api_key": "secret"},
                launch_copy_contract=launch_contract,
                action_phase=live_server.SANDBOX_ACTION_PHASE,
            ),
            "expected_machine_error_code": "UI_ACTION_NOT_ALLOWED",
        },
    ]
    failed_checks = [
        row["name"]
        for row in check_rows
        if row["result"].get("status") != "integration_failure"
        or row["result"].get("result", {}).get("machine_error_code") != row["expected_machine_error_code"]
    ]
    check_results = [
        {
            "name": row["name"],
            "status": row["result"].get("status"),
            "machine_error_code": row["result"].get("result", {}).get("machine_error_code"),
            "expected_machine_error_code": row["expected_machine_error_code"],
            "passed": row["name"] not in failed_checks,
        }
        for row in check_rows
    ]
    return packet(
        "auth_authority_boundary",
        status="ok" if not ui_enabled_violations and not failed_checks else "blocked",
        internal_disabled_commands=sorted(internal_disabled_commands),
        ui_enabled_violations=ui_enabled_violations,
        browser_secret_or_path_intake_guard_checks=check_results,
        failed_guard_checks=failed_checks,
    )


def build_route_account_mutation_guard_packet(live_server: Any, command_adapter: Any) -> dict[str, Any]:
    adapter_rows = {
        row["command_id"]: row
        for row in command_adapter.allowlist_metadata()
    }
    account_mutation_actions = [
        "promote_account",
        "demote_account",
        "retire_account",
        "hold_account",
        "release_account",
    ]
    route_mutation_actions = [
        "api_route_connect",
        "api_route_allow",
        "api_route_disable",
        "api_route_remove",
    ]
    findings: list[str] = []
    for ui_action in account_mutation_actions:
        spec = live_server.UI_ACTION_ALLOWLIST[ui_action]
        command_id = str(spec.get("adapter_command_id") or "")
        adapter = adapter_rows.get(command_id, {})
        if spec.get("confirmation_required") is not True:
            findings.append(f"{ui_action}:confirmation_required")
        if adapter.get("required_args") != ["account_id"]:
            findings.append(f"{ui_action}:required_args")
    for ui_action in route_mutation_actions:
        spec = live_server.UI_ACTION_ALLOWLIST[ui_action]
        command_id = str(spec.get("adapter_command_id") or "")
        if ui_action == "api_route_connect":
            claim_scope = str(spec.get("action_claim_scope") or "")
            if "browser api_key/route_id/secret/path запрещены" not in claim_scope:
                findings.append("api_route_connect:claim_scope_guard")
            continue
        adapter = adapter_rows.get(command_id, {})
        if spec.get("confirmation_required") is not True:
            findings.append(f"{ui_action}:confirmation_required")
        if adapter.get("required_args") != ["route_id"]:
            findings.append(f"{ui_action}:required_args")
    return packet(
        "route_account_mutation_guard",
        status="ok" if not findings else "blocked",
        account_mutation_actions=account_mutation_actions,
        route_mutation_actions=route_mutation_actions,
        findings=findings,
        route_account_mutation_allowed_only_via_guarded_actions=True,
        route_account_mutation_attempted=False,
    )


def build_cost_guard_packet(live_server: Any) -> dict[str, Any]:
    runner = _MappingRunner(_api_snapshot_payloads())
    route_spec = live_server._server_owned_api_route_spec(runner)
    cost_class = str(route_spec.get("cost_class") or "")
    allowed_cost_classes = {
        "paid_or_free_limited",
        "paid",
        "free_limited",
        "owner_managed",
    }
    api_actions = [
        "api_route_credential_check",
        "api_route_connect",
        "api_route_validate",
        "api_route_check",
        "api_route_allow",
        "api_route_disable",
        "api_route_remove",
        "api_route_profile",
        "api_route_evidence_capture",
    ]
    overclaim_findings = []
    for ui_action in api_actions:
        claim_scope = str(live_server.UI_ACTION_ALLOWLIST[ui_action].get("action_claim_scope") or "")
        lowered = claim_scope.lower()
        if "free" in lowered or "unlimited" in lowered or "безлимит" in lowered:
            overclaim_findings.append(f"{ui_action}:cost_overclaim_wording")
    cost_class_valid = cost_class in allowed_cost_classes
    return packet(
        "cost_guard",
        status="ok" if cost_class_valid and not overclaim_findings else "blocked",
        route_spec_cost_class=cost_class,
        route_spec_cost_class_allowed=cost_class_valid,
        allowed_cost_classes=sorted(allowed_cost_classes),
        api_action_cost_overclaim_findings=overclaim_findings,
        browser_cost_authority_allowed=False,
    )


def build_disabled_reason_matrix_packet(live_server: Any) -> dict[str, Any]:
    sandbox_contract = live_server.LaunchCopyContract(
        client_path="/bin/sh",
        profile_dir="/tmp/wbp-r2-sandbox-profile",
        data_dir="/tmp/wbp-r2-sandbox-data",
        copy_port=9122,
        action_server_port=9022,
    )
    phases = {
        "live_readonly": live_server.ui_action_metadata(action_phase=live_server.LIVE_READONLY_ACTION_PHASE),
        "sandbox_no_contract": live_server.ui_action_metadata(action_phase=live_server.SANDBOX_ACTION_PHASE),
        "sandbox_with_contract": live_server.ui_action_metadata(
            action_phase=live_server.SANDBOX_ACTION_PHASE,
            launch_copy_contract=sandbox_contract,
        ),
    }
    missing_reason_entries: list[str] = []
    rows: dict[str, Any] = {}
    for phase_name, metadata in phases.items():
        phase_rows = []
        for ui_action, action_row in sorted(metadata["actions"].items()):
            if action_row.get("available") is True:
                continue
            code = str(action_row.get("disabled_reason_code") or "")
            raw_reasons = action_row.get("disabled_reasons")
            if isinstance(raw_reasons, (list, tuple)):
                reasons = [str(reason) for reason in raw_reasons if str(reason)]
            else:
                reasons = []
            if not code:
                missing_reason_entries.append(f"{phase_name}:{ui_action}:missing_code")
            if not reasons:
                missing_reason_entries.append(f"{phase_name}:{ui_action}:missing_reasons")
            phase_rows.append(
                {
                    "ui_action": ui_action,
                    "disabled_reason_code": code,
                    "disabled_reasons": reasons,
                    "availability_state": str(action_row.get("availability_state") or ""),
                }
            )
        rows[phase_name] = phase_rows
    return packet(
        "disabled_reason_matrix",
        status="ok" if not missing_reason_entries else "blocked",
        rows=rows,
        missing_reason_entries=missing_reason_entries,
    )


def build_action_verification_results_packet(live_server: Any) -> dict[str, Any]:
    runner = _MappingRunner(
        {
            ("sync", "--json"): _command_packet(human_message="Sync completed."),
            **_api_snapshot_payloads(),
        }
    )
    sandbox_contract = live_server.LaunchCopyContract(
        client_path="/bin/sh",
        profile_dir="/tmp/wbp-r2-action-profile",
        data_dir="/tmp/wbp-r2-action-data",
        copy_port=9123,
        action_server_port=9023,
    )
    checks = []

    live_blocked = live_server.run_ui_action(
        runner,
        {"ui_action": "refresh_health_detail"},
        action_phase=live_server.LIVE_READONLY_ACTION_PHASE,
    )
    checks.append(
        {
            "name": "live_readonly_refresh_health_detail_blocked",
            "passed": live_blocked.get("status") == "integration_failure"
            and live_blocked.get("result", {}).get("machine_error_code")
            == live_server.LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
            "status": live_blocked.get("status"),
            "machine_error_code": live_blocked.get("result", {}).get("machine_error_code"),
        }
    )

    login_live_blocked = live_server.run_ui_action(
        runner,
        {"ui_action": "account_login_status", "session_id": "codex-session-1"},
        action_phase=live_server.LIVE_READONLY_ACTION_PHASE,
    )
    checks.append(
        {
            "name": "live_readonly_account_login_status_blocked",
            "passed": login_live_blocked.get("status") == "integration_failure"
            and login_live_blocked.get("result", {}).get("machine_error_code")
            == live_server.LIVE_READONLY_ACTION_DISABLED_REASON_CODE,
            "status": login_live_blocked.get("status"),
            "machine_error_code": login_live_blocked.get("result", {}).get("machine_error_code"),
        }
    )

    sandbox_login_denied = live_server.run_ui_action(
        runner,
        {"ui_action": "account_login_status", "session_id": "codex-session-1"},
        action_phase=live_server.SANDBOX_ACTION_PHASE,
    )
    checks.append(
        {
            "name": "sandbox_account_login_status_requires_contract",
            "passed": sandbox_login_denied.get("status") == "integration_failure"
            and sandbox_login_denied.get("result", {}).get("machine_error_code")
            == live_server.SANDBOX_ACTION_PREFLIGHT_REQUIRED_CODE,
            "status": sandbox_login_denied.get("status"),
            "machine_error_code": sandbox_login_denied.get("result", {}).get("machine_error_code"),
        }
    )

    onboarding_preview = live_server.run_ui_action(
        runner,
        {"ui_action": "onboard_account_dry_run"},
        launch_copy_contract=sandbox_contract,
        action_phase=live_server.SANDBOX_ACTION_PHASE,
    )
    checks.append(
        {
            "name": "sandbox_onboard_account_dry_run_admitted",
            "passed": onboarding_preview.get("status") == "ok"
            and onboarding_preview.get("result", {}).get("machine_error_code") == "OK",
            "status": onboarding_preview.get("status"),
            "machine_error_code": onboarding_preview.get("result", {}).get("machine_error_code"),
        }
    )

    credential_check = live_server.run_ui_action(
        runner,
        {"ui_action": "api_route_credential_check"},
        launch_copy_contract=sandbox_contract,
        action_phase=live_server.SANDBOX_ACTION_PHASE,
    )
    checks.append(
        {
            "name": "sandbox_api_route_credential_check_packet_backed",
            "passed": (
                credential_check.get("status") == "ok"
                and credential_check.get("result", {}).get("machine_error_code") == "OK"
            )
            or (
                credential_check.get("status") == "integration_failure"
                and credential_check.get("result", {}).get("machine_error_code")
                == live_server.API_ROUTE_CONNECT_PREFLIGHT_UNSAFE_CODE
            ),
            "status": credential_check.get("status"),
            "machine_error_code": credential_check.get("result", {}).get("machine_error_code"),
        }
    )

    sync_full = live_server.run_ui_action(
        runner,
        {"ui_action": "sync_runtime"},
        action_phase=live_server.FULL_ACTION_PHASE,
    )
    checks.append(
        {
            "name": "full_sync_runtime_wired",
            "passed": sync_full.get("status") == "ok"
            and sync_full.get("result", {}).get("machine_error_code") == "OK",
            "status": sync_full.get("status"),
            "machine_error_code": sync_full.get("result", {}).get("machine_error_code"),
        }
    )
    failed = [row["name"] for row in checks if not row["passed"]]
    return packet(
        "action_verification_results",
        status="ok" if not failed else "blocked",
        checks=checks,
        failed_checks=failed,
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    required = {
        "web_control_surface_matrix_packet.json",
        "readonly_live_action_boundary_packet.json",
        "auth_authority_boundary_packet.json",
        "route_account_mutation_guard_packet.json",
        "cost_guard_packet.json",
        "disabled_reason_matrix_packet.json",
        "action_verification_results_packet.json",
    }
    missing = sorted(required - set(packets))
    if missing:
        findings.append("missing_required_packets")
    blocked_packets = sorted(
        name
        for name, payload in packets.items()
        if payload.get("status") == "blocked"
    )
    if blocked_packets:
        findings.append("blocked_packets_present")
    matrix = packets.get("web_control_surface_matrix_packet.json", {})
    if matrix.get("unwired_actions"):
        findings.append("unwired_actions_present")
    readonly = packets.get("readonly_live_action_boundary_packet.json", {})
    if readonly.get("unexpected_live_available_actions"):
        findings.append("unexpected_live_available_actions")
    action_results = packets.get("action_verification_results_packet.json", {})
    if action_results.get("failed_checks"):
        findings.append("action_verification_failed_checks")
    return packet(
        "web_control_surface_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        missing_required_packets=missing,
        blocked_packets=blocked_packets,
        target_status=TARGET_STATUS,
        ui_polish_claimed=False,
        runtime_redesign_claimed=False,
    )


def build_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    del repo_root, evidence_dir
    live_server, command_adapter = _load_modules()
    packets: dict[str, dict[str, Any]] = {
        "web_control_surface_matrix_packet.json": build_web_control_surface_matrix_packet(
            live_server, command_adapter
        ),
        "readonly_live_action_boundary_packet.json": build_readonly_live_action_boundary_packet(
            live_server
        ),
        "auth_authority_boundary_packet.json": build_auth_authority_boundary_packet(
            live_server, command_adapter
        ),
        "route_account_mutation_guard_packet.json": build_route_account_mutation_guard_packet(
            live_server, command_adapter
        ),
        "cost_guard_packet.json": build_cost_guard_packet(live_server),
        "disabled_reason_matrix_packet.json": build_disabled_reason_matrix_packet(live_server),
        "action_verification_results_packet.json": build_action_verification_results_packet(
            live_server
        ),
    }
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    return packets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="web-control-surface-actions-wired-and-guarded-r2-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    packets = build_packets(repo_root, evidence_dir)
    for name, payload in packets.items():
        _write_json(evidence_dir / name, payload)
    blocked = [name for name, payload in packets.items() if payload.get("status") == "blocked"]
    return 0 if not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
