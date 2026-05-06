# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from tkinter import StringVar, Tk, messagebox
from tkinter import ttk
from typing import Any


VALID_LIVENESS = {"healthy", "degraded", "down", "stale", "unknown"}
VALID_ACCOUNT_POOLS = {"active", "reserve", "retired"}
POOL_SUMMARY_FIELDS = (
    "active",
    "reserve",
    "retired",
    "healthy",
    "degraded",
    "down",
)
ATTESTATION_SUMMARY_FIELDS = (
    "status",
    "machine_error_code",
    "attestation_source",
    "observed_at_utc",
)
ACCOUNT_FIELDS = (
    "id",
    "label",
    "pool",
    "manual_hold",
    "status",
    "fail_count",
    "success_count",
    "last_success",
    "last_error",
    "cooldown_until",
    "notes",
)
REGISTRY_IDENTITY_FIELDS = (
    "status",
    "machine_error_code",
    "next_action",
)
ONBOARDING_RESULT_FIELDS = (
    "input_mode",
    "explicit_auth_ref",
    "new_backend_ids",
    "selected_backend_id",
    "selection_status",
    "reserve_first_enforced",
    "pool_after_onboarding",
    "validate_attempted",
    "validate_outcome",
    "sync_attempted",
    "sync_outcome",
    "status_observed",
    "external_command_exit_code",
    "external_command_status",
    "active_routing_changed",
    "final_outcome",
)
CLIENT_LAUNCH_RESULT_FIELDS = (
    "status",
    "attempted",
    "client_path",
    "client_path_kind",
    "runtime_precondition_checked",
    "runtime_precondition_status",
    "effective_mode_observed",
    "endpoint_observed",
    "profile_context",
    "env_sanitized",
    "dispatch_method",
    "dispatch_attempted",
    "dispatch_observed",
    "dispatch_exit_code",
    "launch_claim_scope",
    "final_outcome",
)
SMOKE_RESULT_FIELDS = (
    "launch_mode",
    "desired_mode",
    "effective_mode",
    "endpoint",
    "current_proxy_url",
    "launcher_exit_code",
    "stabilization_seconds",
    "last_error",
    "attestation_summary",
    "stable_runtime_consumer",
)
ACCOUNT_CAPACITY_TARGET = 20


class UiShellError(Exception):
    """Raised when the UI cannot trust a command result."""


def parse_exact_json_object(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, end = decoder.raw_decode(stdout)
    if not isinstance(payload, dict):
        raise UiShellError("stdout JSON must be an object")
    if stdout[end:].strip():
        raise UiShellError("stdout must contain exactly one JSON object")
    return payload


def require_fields(payload: dict[str, Any], fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        missing_fields = ", ".join(sorted(missing))
        raise UiShellError(f"{context} missing required fields: {missing_fields}")


def require_nonnegative_int(value: Any, context: str) -> int:
    if isinstance(value, bool):
        raise UiShellError(f"{context} must be a nonnegative integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise UiShellError(f"{context} must be a nonnegative integer") from exc
    if number < 0:
        raise UiShellError(f"{context} must be a nonnegative integer")
    return number


def require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise UiShellError(f"{context} must be a boolean")
    return value


@dataclass(frozen=True)
class CommandResult:
    payload: dict[str, Any]
    stderr: str


class JsonCommandRunner:
    def __init__(
        self,
        *,
        base_command: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._base_command = base_command or [sys.executable, "-m", "wild_boar_proxy"]
        self._cwd = cwd
        self._env = env

    def run(self, *args: str) -> CommandResult:
        result = subprocess.run(
            [*self._base_command, *args],
            cwd=self._cwd,
            env=self._env,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = parse_exact_json_object(result.stdout)
        require_fields(
            payload,
            (
                "status",
                "exit_code",
                "human_message",
                "machine_error_code",
                "changed_files",
                "next_action",
            ),
            "command payload",
        )
        return CommandResult(payload=payload, stderr=result.stderr)


@dataclass(frozen=True)
class RuntimeSnapshot:
    overall_state: str
    exit_code: int
    human_message: str
    next_action: str
    machine_error_code: str
    desired_mode: str
    effective_mode: str
    endpoint: str
    current_proxy_url: str
    liveness: str
    severity: str
    operator_action: str
    active_count: int
    reserve_count: int
    retired_count: int
    healthy_count: int
    degraded_count: int
    down_count: int
    attestation_status: str
    attestation_machine_error_code: str
    attestation_source: str
    attestation_observed_at: str
    last_error: str
    integration_error: str

    @classmethod
    def integration_failure(cls, message: str) -> "RuntimeSnapshot":
        return cls(
            overall_state="integration_failure",
            exit_code=1,
            human_message="UI integration failure.",
            next_action="retry",
            machine_error_code="UI_INTEGRATION_FAILURE",
            desired_mode="unknown",
            effective_mode="unknown",
            endpoint="",
            current_proxy_url="",
            liveness="unknown",
            severity="recoverable",
            operator_action="retry",
            active_count=0,
            reserve_count=0,
            retired_count=0,
            healthy_count=0,
            degraded_count=0,
            down_count=0,
            attestation_status="unknown",
            attestation_machine_error_code="UI_INTEGRATION_FAILURE",
            attestation_source="",
            attestation_observed_at="",
            last_error="",
            integration_error=message,
        )


@dataclass(frozen=True)
class AccountRecord:
    backend_id: str
    label: str
    pool: str
    manual_hold: bool
    status: str
    fail_count: int
    success_count: int
    last_success: str
    last_error: str
    cooldown_until: str
    notes: str


@dataclass(frozen=True)
class AccountPoolSnapshot:
    human_message: str
    machine_error_code: str
    registry_identity_status: str
    registry_identity_machine_error_code: str
    registry_identity_next_action: str
    active_count: int
    reserve_count: int
    retired_count: int
    capacity_target: int
    accounts: tuple[AccountRecord, ...]
    integration_error: str

    @classmethod
    def integration_failure(cls, message: str) -> "AccountPoolSnapshot":
        return cls(
            human_message="UI integration failure.",
            machine_error_code="UI_INTEGRATION_FAILURE",
            registry_identity_status="unknown",
            registry_identity_machine_error_code="UI_INTEGRATION_FAILURE",
            registry_identity_next_action="retry",
            active_count=0,
            reserve_count=0,
            retired_count=0,
            capacity_target=ACCOUNT_CAPACITY_TARGET,
            accounts=(),
            integration_error=message,
        )


def build_runtime_snapshot(
    *,
    status_payload: dict[str, Any],
    mode_payload: dict[str, Any] | None = None,
) -> RuntimeSnapshot:
    require_fields(
        status_payload,
        (
            "status",
            "exit_code",
            "human_message",
            "machine_error_code",
            "next_action",
            "liveness",
            "severity",
            "operator_action",
            "desired_mode",
            "effective_mode",
            "endpoint",
            "current_proxy_url",
            "pool_summary",
            "attestation_summary",
        ),
        "status payload",
    )
    if mode_payload is None:
        mode_payload = {
            "desired_mode": status_payload["desired_mode"],
            "effective_mode": status_payload["effective_mode"],
        }
    require_fields(mode_payload, ("desired_mode", "effective_mode"), "mode payload")

    desired_mode = str(mode_payload["desired_mode"])
    effective_mode = str(mode_payload["effective_mode"])
    if desired_mode != str(status_payload["desired_mode"]):
        raise UiShellError("mode get and status disagree about desired mode")
    if effective_mode != str(status_payload["effective_mode"]):
        raise UiShellError("mode get and status disagree about effective mode")

    liveness = str(status_payload["liveness"])
    if liveness not in VALID_LIVENESS:
        raise UiShellError(f"unsupported liveness value: {liveness}")

    pool_summary = status_payload["pool_summary"]
    if not isinstance(pool_summary, dict):
        raise UiShellError("status pool_summary must be an object")
    require_fields(pool_summary, POOL_SUMMARY_FIELDS, "pool_summary")

    attestation_summary = status_payload["attestation_summary"]
    if not isinstance(attestation_summary, dict):
        raise UiShellError("status attestation_summary must be an object")
    require_fields(attestation_summary, ATTESTATION_SUMMARY_FIELDS, "attestation_summary")

    return RuntimeSnapshot(
        overall_state=str(status_payload["status"]),
        exit_code=require_nonnegative_int(status_payload["exit_code"], "status exit_code"),
        human_message=str(status_payload["human_message"]),
        next_action=str(status_payload["next_action"]),
        machine_error_code=str(status_payload["machine_error_code"]),
        desired_mode=desired_mode,
        effective_mode=effective_mode,
        endpoint=str(status_payload["endpoint"]),
        current_proxy_url=str(status_payload["current_proxy_url"]),
        liveness=liveness,
        severity=str(status_payload["severity"]),
        operator_action=str(status_payload["operator_action"]),
        active_count=require_nonnegative_int(pool_summary["active"], "pool_summary.active"),
        reserve_count=require_nonnegative_int(pool_summary["reserve"], "pool_summary.reserve"),
        retired_count=require_nonnegative_int(pool_summary["retired"], "pool_summary.retired"),
        healthy_count=require_nonnegative_int(pool_summary["healthy"], "pool_summary.healthy"),
        degraded_count=require_nonnegative_int(
            pool_summary["degraded"], "pool_summary.degraded"
        ),
        down_count=require_nonnegative_int(pool_summary["down"], "pool_summary.down"),
        attestation_status=str(attestation_summary["status"]),
        attestation_machine_error_code=str(attestation_summary["machine_error_code"]),
        attestation_source=str(attestation_summary["attestation_source"]),
        attestation_observed_at=str(attestation_summary["observed_at_utc"]),
        last_error=str(status_payload.get("last_error", "")),
        integration_error="",
    )


def normalize_account_record(raw: dict[str, Any]) -> AccountRecord:
    require_fields(raw, ACCOUNT_FIELDS, "account record")
    pool = str(raw["pool"])
    if pool not in VALID_ACCOUNT_POOLS:
        raise UiShellError(f"unsupported account pool value: {pool}")
    return AccountRecord(
        backend_id=str(raw["id"]),
        label=str(raw["label"]),
        pool=pool,
        manual_hold=require_bool(raw["manual_hold"], "account.manual_hold"),
        status=str(raw["status"]),
        fail_count=require_nonnegative_int(raw["fail_count"], "account.fail_count"),
        success_count=require_nonnegative_int(raw["success_count"], "account.success_count"),
        last_success="" if raw["last_success"] is None else str(raw["last_success"]),
        last_error="" if raw["last_error"] is None else str(raw["last_error"]),
        cooldown_until="" if raw["cooldown_until"] is None else str(raw["cooldown_until"]),
        notes="" if raw["notes"] is None else str(raw["notes"]),
    )


def build_account_pool_snapshot(accounts_payload: dict[str, Any]) -> AccountPoolSnapshot:
    require_fields(
        accounts_payload,
        (
            "human_message",
            "machine_error_code",
            "accounts",
            "registry_identity",
        ),
        "accounts payload",
    )
    accounts_raw = accounts_payload["accounts"]
    if not isinstance(accounts_raw, list):
        raise UiShellError("accounts payload accounts must be a list")
    accounts = tuple(normalize_account_record(item) for item in accounts_raw if isinstance(item, dict))
    if len(accounts) != len(accounts_raw):
        raise UiShellError("accounts payload accounts must contain only objects")

    registry_identity = accounts_payload["registry_identity"]
    if not isinstance(registry_identity, dict):
        raise UiShellError("registry_identity must be an object")
    require_fields(registry_identity, REGISTRY_IDENTITY_FIELDS, "registry_identity")

    active_count = sum(1 for account in accounts if account.pool == "active")
    reserve_count = sum(1 for account in accounts if account.pool == "reserve")
    retired_count = sum(1 for account in accounts if account.pool == "retired")

    return AccountPoolSnapshot(
        human_message=str(accounts_payload["human_message"]),
        machine_error_code=str(accounts_payload["machine_error_code"]),
        registry_identity_status=str(registry_identity["status"]),
        registry_identity_machine_error_code=str(registry_identity["machine_error_code"]),
        registry_identity_next_action=str(registry_identity["next_action"]),
        active_count=active_count,
        reserve_count=reserve_count,
        retired_count=retired_count,
        capacity_target=ACCOUNT_CAPACITY_TARGET,
        accounts=accounts,
        integration_error="",
    )


def ensure_capacity_data_consistency(
    runtime_snapshot: RuntimeSnapshot, account_snapshot: AccountPoolSnapshot
) -> None:
    runtime_counts = (
        runtime_snapshot.active_count,
        runtime_snapshot.reserve_count,
        runtime_snapshot.retired_count,
    )
    account_counts = (
        account_snapshot.active_count,
        account_snapshot.reserve_count,
        account_snapshot.retired_count,
    )
    if runtime_counts != account_counts:
        raise UiShellError(
            "status pool_summary and accounts list disagree about "
            "active, reserve, or retired counts"
        )


def load_runtime_snapshot(runner: JsonCommandRunner) -> RuntimeSnapshot:
    return build_runtime_snapshot(
        status_payload=runner.run("status", "--json").payload,
        mode_payload=runner.run("mode", "get", "--json").payload,
    )


def load_account_pool_snapshot(runner: JsonCommandRunner) -> AccountPoolSnapshot:
    return build_account_pool_snapshot(runner.run("accounts", "list", "--json").payload)


def run_mode_control_and_refresh(
    runner: JsonCommandRunner, command: tuple[str, ...]
) -> tuple[dict[str, Any], RuntimeSnapshot]:
    action_result = runner.run(*command)
    snapshot = load_runtime_snapshot(runner)
    return action_result.payload, snapshot


def run_launch_client_and_refresh(
    runner: JsonCommandRunner, command: tuple[str, ...]
) -> tuple[dict[str, Any], RuntimeSnapshot]:
    action_result = runner.run(*command)
    status_payload = runner.run("status", "--json").payload
    snapshot = build_runtime_snapshot(status_payload=status_payload)
    return action_result.payload, snapshot


def run_smoke_and_refresh(
    runner: JsonCommandRunner,
) -> tuple[dict[str, Any], RuntimeSnapshot]:
    action_result = runner.run("launch", "smoke", "--json")
    status_payload = runner.run("status", "--json").payload
    snapshot = build_runtime_snapshot(status_payload=status_payload)
    return action_result.payload, snapshot


def run_sync_and_refresh(
    runner: JsonCommandRunner,
) -> tuple[dict[str, Any], RuntimeSnapshot, AccountPoolSnapshot]:
    action_result = runner.run("sync", "--json")
    status_payload = runner.run("status", "--json").payload
    accounts_payload = runner.run("accounts", "list", "--json").payload
    mode_payload = runner.run("mode", "get", "--json").payload
    runtime_snapshot = build_runtime_snapshot(
        status_payload=status_payload,
        mode_payload=mode_payload,
    )
    account_snapshot = build_account_pool_snapshot(accounts_payload)
    ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
    return action_result.payload, runtime_snapshot, account_snapshot


def run_account_validate_and_refresh(
    runner: JsonCommandRunner, backend_id: str
) -> tuple[dict[str, Any], AccountPoolSnapshot]:
    action_result = runner.run("accounts", "validate", backend_id, "--json")
    snapshot = load_account_pool_snapshot(runner)
    return action_result.payload, snapshot


def run_account_mutation_and_refresh(
    runner: JsonCommandRunner, command: tuple[str, ...]
) -> tuple[dict[str, Any], RuntimeSnapshot, AccountPoolSnapshot]:
    action_result = runner.run(*command)
    accounts_payload = runner.run("accounts", "list", "--json").payload
    status_payload = runner.run("status", "--json").payload
    runtime_snapshot = build_runtime_snapshot(status_payload=status_payload)
    account_snapshot = build_account_pool_snapshot(accounts_payload)
    ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
    return action_result.payload, runtime_snapshot, account_snapshot


def run_account_onboard_and_refresh(
    runner: JsonCommandRunner, command: tuple[str, ...]
) -> tuple[dict[str, Any], RuntimeSnapshot, AccountPoolSnapshot]:
    action_result = runner.run(*command)
    accounts_payload = runner.run("accounts", "list", "--json").payload
    status_payload = runner.run("status", "--json").payload
    runtime_snapshot = build_runtime_snapshot(status_payload=status_payload)
    account_snapshot = build_account_pool_snapshot(accounts_payload)
    ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
    return action_result.payload, runtime_snapshot, account_snapshot


def format_onboarding_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def build_onboarding_field_values(action_payload: dict[str, Any]) -> dict[str, str]:
    result = {field: "" for field in ONBOARDING_RESULT_FIELDS}
    onboarding_result = action_payload.get("onboarding_result")
    if onboarding_result is None:
        return result
    if not isinstance(onboarding_result, dict):
        raise UiShellError("onboarding_result must be an object when present")
    for field in ONBOARDING_RESULT_FIELDS:
        if field in onboarding_result:
            result[field] = format_onboarding_value(onboarding_result[field])
    return result


def build_client_launch_field_values(action_payload: dict[str, Any]) -> dict[str, str]:
    result = {field: "" for field in CLIENT_LAUNCH_RESULT_FIELDS}
    launch_result = action_payload.get("client_launch_result")
    if launch_result is None:
        return result
    if not isinstance(launch_result, dict):
        raise UiShellError("client_launch_result must be an object when present")
    for field in CLIENT_LAUNCH_RESULT_FIELDS:
        if field in launch_result:
            result[field] = format_onboarding_value(launch_result[field])
    return result


def classify_client_launch_rendered_state(
    action_payload: dict[str, Any], field_values: dict[str, str], *, malformed: bool
) -> str:
    if malformed:
        return "integration_failure"
    command_status = str(action_payload.get("status", ""))
    if command_status == "integration_failure":
        return "integration_failure"
    if command_status != "ok":
        return "failure"
    final_outcome = field_values.get("final_outcome", "")
    claim_scope = field_values.get("launch_claim_scope", "")
    dispatch_observed = field_values.get("dispatch_observed", "")
    attempted = field_values.get("attempted", "")
    dispatch_attempted = field_values.get("dispatch_attempted", "")
    runtime_precondition_status = field_values.get("runtime_precondition_status", "")
    dispatch_exit_code = field_values.get("dispatch_exit_code", "")
    if (
        final_outcome == "dispatch_requested"
        and claim_scope == "os_dispatch_only"
        and dispatch_observed in {"true", "requested"}
        and attempted == "true"
        and dispatch_attempted == "true"
        and runtime_precondition_status in {"ok", "passed"}
        and dispatch_exit_code in {"", "0", "null"}
    ):
        return "bounded_dispatch_only"
    if final_outcome in {
        "runtime_precondition_failed",
        "client_path_missing",
        "client_path_invalid",
        "dispatch_failed",
        "unsupported_launch_shape",
    }:
        return "failure"
    if field_values.get("runtime_precondition_status", "") == "failed":
        return "failure"
    return "unknown"


def build_smoke_field_values(action_payload: dict[str, Any]) -> dict[str, str]:
    result = {field: "" for field in SMOKE_RESULT_FIELDS}
    for field in SMOKE_RESULT_FIELDS:
        if field not in action_payload:
            continue
        value = action_payload[field]
        if field in {"attestation_summary", "stable_runtime_consumer"} and not isinstance(
            value, dict
        ):
            raise UiShellError(f"{field} must be an object when present")
        result[field] = format_onboarding_value(value)
    return result


def classify_smoke_rendered_state(
    action_payload: dict[str, Any], *, malformed: bool
) -> str:
    if malformed:
        return "integration_failure"
    command_status = str(action_payload.get("status", ""))
    if command_status == "integration_failure":
        return "integration_failure"
    if command_status != "ok":
        return "failure"
    launch_mode = str(action_payload.get("launch_mode", ""))
    if launch_mode != "smoke":
        return "unknown"
    return "bounded_runtime_smoke_only"


class MinimalCompanionShell:
    def __init__(self, root: Tk, runner: JsonCommandRunner) -> None:
        self.root = root
        self.runner = runner
        self.root.title("Wild Boar Proxy")
        self.root.geometry("1180x760")
        self.root.minsize(960, 640)
        self._busy = False

        self.banner_var = StringVar(value="Refresh required.")
        self.state_var = StringVar(value="unknown")
        self.exit_code_var = StringVar(value="0")
        self.next_action_var = StringVar(value="unknown")
        self.desired_mode_var = StringVar(value="unknown")
        self.effective_mode_var = StringVar(value="unknown")
        self.endpoint_var = StringVar(value="")
        self.current_proxy_var = StringVar(value="")
        self.liveness_var = StringVar(value="unknown")
        self.severity_var = StringVar(value="recoverable")
        self.operator_action_var = StringVar(value="none")
        self.machine_error_var = StringVar(value="")
        self.pool_var = StringVar(value="A:0 R:0 T:0 H:0 D:0 X:0")
        self.attestation_var = StringVar(value="")
        self.last_error_var = StringVar(value="")
        self.integration_var = StringVar(value="")
        self.account_registry_var = StringVar(value="unknown")
        self.account_counts_var = StringVar(value="A:0 R:0 T:0")
        self.account_capacity_var = StringVar(value=str(ACCOUNT_CAPACITY_TARGET))
        self.account_integration_var = StringVar(value="")
        self.onboarding_auth_ref_var = StringVar(value="")
        self.onboarding_command_status_var = StringVar(value="")
        self.onboarding_machine_error_var = StringVar(value="")
        self.onboarding_next_action_var = StringVar(value="")
        self.onboarding_field_vars = {
            field: StringVar(value="")
            for field in ONBOARDING_RESULT_FIELDS
        }
        self.launch_client_path_var = StringVar(value="")
        self.launch_command_status_var = StringVar(value="")
        self.launch_command_exit_code_var = StringVar(value="")
        self.launch_command_human_message_var = StringVar(value="")
        self.launch_command_machine_error_var = StringVar(value="")
        self.launch_command_changed_files_var = StringVar(value="")
        self.launch_command_next_action_var = StringVar(value="")
        self.launch_rendered_state_var = StringVar(value="unknown")
        self.launch_field_vars = {
            field: StringVar(value="")
            for field in CLIENT_LAUNCH_RESULT_FIELDS
        }
        self.smoke_command_status_var = StringVar(value="")
        self.smoke_command_exit_code_var = StringVar(value="")
        self.smoke_command_human_message_var = StringVar(value="")
        self.smoke_command_machine_error_var = StringVar(value="")
        self.smoke_command_changed_files_var = StringVar(value="")
        self.smoke_command_next_action_var = StringVar(value="")
        self.smoke_rendered_state_var = StringVar(value="unknown")
        self.smoke_field_vars = {
            field: StringVar(value="")
            for field in SMOKE_RESULT_FIELDS
        }

        self._build_layout()
        self.root.after(0, self.refresh)

    def _build_layout(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x")
        ttk.Label(header, text="Wild Boar Proxy", font=("TkDefaultFont", 15, "bold")).pack(
            side="left"
        )
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="right")

        ttk.Label(container, textvariable=self.banner_var, padding=(0, 10, 0, 10)).pack(
            fill="x"
        )

        top = ttk.Frame(container)
        top.pack(fill="both", expand=False)

        status_box = ttk.LabelFrame(top, text="Runtime Status", padding=12)
        status_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._add_status_row(status_box, "State", self.state_var)
        self._add_status_row(status_box, "Exit code", self.exit_code_var)
        self._add_status_row(status_box, "Next action", self.next_action_var)
        self._add_status_row(status_box, "Desired mode", self.desired_mode_var)
        self._add_status_row(status_box, "Effective mode", self.effective_mode_var)
        self._add_status_row(status_box, "Endpoint", self.endpoint_var)
        self._add_status_row(status_box, "Current proxy", self.current_proxy_var)
        self._add_status_row(status_box, "Liveness", self.liveness_var)
        self._add_status_row(status_box, "Severity", self.severity_var)
        self._add_status_row(status_box, "Operator action", self.operator_action_var)
        self._add_status_row(status_box, "Machine error", self.machine_error_var)
        self._add_status_row(status_box, "Pool", self.pool_var)
        self._add_status_row(status_box, "Attestation", self.attestation_var)
        self._add_status_row(status_box, "Last error", self.last_error_var)
        self._add_status_row(status_box, "Integration", self.integration_var)

        controls_box = ttk.LabelFrame(top, text="Mode Controls", padding=12)
        controls_box.pack(side="left", fill="y", padx=(8, 0))
        ttk.Button(
            controls_box,
            text="Switch Stable",
            command=lambda: self.run_mode_action(
                "Switch desired mode to stable?",
                ("mode", "set", "stable", "--json"),
            ),
        ).pack(fill="x", pady=4)
        ttk.Button(
            controls_box,
            text="Switch Managed",
            command=lambda: self.run_mode_action(
                "Switch desired mode to managed?",
                ("mode", "set", "managed", "--json"),
            ),
        ).pack(fill="x", pady=4)
        ttk.Button(
            controls_box,
            text="Run Managed Sync",
            command=self.run_sync_action,
        ).pack(fill="x", pady=4)
        ttk.Button(
            controls_box,
            text="Smoke Test",
            command=self.run_smoke_action,
        ).pack(fill="x", pady=4)
        launch_box = ttk.LabelFrame(controls_box, text="Launch Client", padding=8)
        launch_box.pack(fill="x", pady=(8, 0))
        launch_input = ttk.Frame(launch_box)
        launch_input.pack(fill="x")
        ttk.Label(launch_input, text="Client path:", width=10).pack(side="left")
        ttk.Entry(launch_input, textvariable=self.launch_client_path_var).pack(
            side="left",
            fill="x",
            expand=True,
        )
        ttk.Button(
            launch_box,
            text="Launch Client",
            command=self.run_launch_client_action,
        ).pack(fill="x", pady=(8, 0))
        self._add_status_row(
            launch_box,
            "Rendered state",
            self.launch_rendered_state_var,
        )
        self._add_status_row(
            launch_box,
            "Command status",
            self.launch_command_status_var,
        )
        self._add_status_row(
            launch_box,
            "Exit code",
            self.launch_command_exit_code_var,
        )
        self._add_status_row(
            launch_box,
            "Human message",
            self.launch_command_human_message_var,
        )
        self._add_status_row(
            launch_box,
            "Machine error",
            self.launch_command_machine_error_var,
        )
        self._add_status_row(
            launch_box,
            "Changed files",
            self.launch_command_changed_files_var,
        )
        self._add_status_row(
            launch_box,
            "Next action",
            self.launch_command_next_action_var,
        )
        for label, field in (
            ("Launch status", "status"),
            ("Attempted", "attempted"),
            ("Client path", "client_path"),
            ("Path kind", "client_path_kind"),
            ("Precondition checked", "runtime_precondition_checked"),
            ("Precondition status", "runtime_precondition_status"),
            ("Effective mode", "effective_mode_observed"),
            ("Endpoint", "endpoint_observed"),
            ("Profile context", "profile_context"),
            ("Env sanitized", "env_sanitized"),
            ("Dispatch method", "dispatch_method"),
            ("Dispatch attempted", "dispatch_attempted"),
            ("Dispatch observed", "dispatch_observed"),
            ("Dispatch exit code", "dispatch_exit_code"),
            ("Claim scope", "launch_claim_scope"),
            ("Final outcome", "final_outcome"),
        ):
            self._add_status_row(launch_box, label, self.launch_field_vars[field])

        smoke_box = ttk.LabelFrame(controls_box, text="Smoke Test", padding=8)
        smoke_box.pack(fill="x", pady=(8, 0))
        self._add_status_row(
            smoke_box,
            "Rendered state",
            self.smoke_rendered_state_var,
        )
        self._add_status_row(
            smoke_box,
            "Command status",
            self.smoke_command_status_var,
        )
        self._add_status_row(
            smoke_box,
            "Exit code",
            self.smoke_command_exit_code_var,
        )
        self._add_status_row(
            smoke_box,
            "Human message",
            self.smoke_command_human_message_var,
        )
        self._add_status_row(
            smoke_box,
            "Machine error",
            self.smoke_command_machine_error_var,
        )
        self._add_status_row(
            smoke_box,
            "Changed files",
            self.smoke_command_changed_files_var,
        )
        self._add_status_row(
            smoke_box,
            "Next action",
            self.smoke_command_next_action_var,
        )
        for label, field in (
            ("Launch mode", "launch_mode"),
            ("Desired mode", "desired_mode"),
            ("Effective mode", "effective_mode"),
            ("Endpoint", "endpoint"),
            ("Current proxy", "current_proxy_url"),
            ("Launcher exit", "launcher_exit_code"),
            ("Stabilization", "stabilization_seconds"),
            ("Last error", "last_error"),
            ("Attestation", "attestation_summary"),
            ("Stable consumer", "stable_runtime_consumer"),
        ):
            self._add_status_row(smoke_box, label, self.smoke_field_vars[field])

        onboarding_box = ttk.LabelFrame(container, text="Onboarding", padding=12)
        onboarding_box.pack(fill="x", pady=(16, 0))

        onboarding_input = ttk.Frame(onboarding_box)
        onboarding_input.pack(fill="x")
        ttk.Label(onboarding_input, text="Explicit auth ref:", width=16).pack(side="left")
        ttk.Entry(onboarding_input, textvariable=self.onboarding_auth_ref_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(
            onboarding_input,
            text="Onboard Explicit Auth",
            command=self.run_onboard_action,
        ).pack(side="left", padx=(8, 0))

        onboarding_summary = ttk.Frame(onboarding_box)
        onboarding_summary.pack(fill="x", pady=(8, 4))
        self._add_status_row(
            onboarding_summary, "Command status", self.onboarding_command_status_var
        )
        self._add_status_row(
            onboarding_summary, "Machine error", self.onboarding_machine_error_var
        )
        self._add_status_row(
            onboarding_summary, "Next action", self.onboarding_next_action_var
        )

        for label, field in (
            ("Input mode", "input_mode"),
            ("Explicit auth ref", "explicit_auth_ref"),
            ("New backend IDs", "new_backend_ids"),
            ("Selected backend", "selected_backend_id"),
            ("Selection status", "selection_status"),
            ("Reserve first", "reserve_first_enforced"),
            ("Pool after", "pool_after_onboarding"),
            ("Validate attempted", "validate_attempted"),
            ("Validate outcome", "validate_outcome"),
            ("Sync attempted", "sync_attempted"),
            ("Sync outcome", "sync_outcome"),
            ("Status observed", "status_observed"),
            ("External exit code", "external_command_exit_code"),
            ("External status", "external_command_status"),
            ("Routing changed", "active_routing_changed"),
            ("Final outcome", "final_outcome"),
        ):
            self._add_status_row(onboarding_box, label, self.onboarding_field_vars[field])

        accounts_box = ttk.LabelFrame(container, text="Account Pool", padding=12)
        accounts_box.pack(fill="both", expand=True, pady=(16, 0))

        account_summary = ttk.Frame(accounts_box)
        account_summary.pack(fill="x")
        self._add_status_row(account_summary, "Registry identity", self.account_registry_var)
        self._add_status_row(account_summary, "Account counts", self.account_counts_var)
        self._add_status_row(account_summary, "Capacity target", self.account_capacity_var)
        self._add_status_row(account_summary, "Integration", self.account_integration_var)

        account_actions = ttk.Frame(accounts_box)
        account_actions.pack(fill="x", pady=(10, 10))
        ttk.Button(account_actions, text="Validate", command=self.run_validate_action).pack(
            side="left"
        )
        ttk.Button(account_actions, text="Recheck", command=self.run_recheck_action).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(account_actions, text="Promote", command=self.run_promote_action).pack(
            side="left", padx=(16, 0)
        )
        ttk.Button(account_actions, text="Demote", command=self.run_demote_action).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(account_actions, text="Hold", command=self.run_hold_action).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(account_actions, text="Release", command=self.run_release_action).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(account_actions, text="Retire", command=self.run_retire_action).pack(
            side="left", padx=(8, 0)
        )

        columns = (
            "id",
            "label",
            "pool",
            "hold",
            "status",
            "fail",
            "success",
            "last_success",
            "last_error",
            "cooldown_until",
            "notes",
        )
        self.accounts_tree = ttk.Treeview(
            accounts_box,
            columns=columns,
            show="headings",
            height=14,
        )
        for column, heading, width in (
            ("id", "ID", 140),
            ("label", "Label", 150),
            ("pool", "Pool", 90),
            ("hold", "Hold", 60),
            ("status", "Status", 100),
            ("fail", "Fail", 60),
            ("success", "Success", 70),
            ("last_success", "Last Success", 170),
            ("last_error", "Last Error", 220),
            ("cooldown_until", "Cooldown Until", 170),
            ("notes", "Notes", 180),
        ):
            self.accounts_tree.heading(column, text=heading)
            self.accounts_tree.column(column, width=width, anchor="w")
        self.accounts_tree.pack(fill="both", expand=True)

    def _add_status_row(self, parent: ttk.Widget, label: str, variable: StringVar) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=f"{label}:", width=16).pack(side="left")
        ttk.Label(row, textvariable=variable).pack(side="left", fill="x", expand=True)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy

    def refresh(self) -> None:
        if self._busy:
            return
        self.set_busy(True)
        self.banner_var.set("Refreshing command truth...")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            runtime_snapshot = load_runtime_snapshot(self.runner)
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
        try:
            account_snapshot = load_account_pool_snapshot(self.runner)
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
        if not runtime_snapshot.integration_error and not account_snapshot.integration_error:
            try:
                ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
            except UiShellError as exc:
                runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
                account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
        self.root.after(
            0,
            lambda: self._apply_refresh_results(runtime_snapshot, account_snapshot),
        )

    def _apply_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        self.state_var.set(snapshot.overall_state)
        self.exit_code_var.set(str(snapshot.exit_code))
        self.next_action_var.set(snapshot.next_action)
        self.desired_mode_var.set(snapshot.desired_mode)
        self.effective_mode_var.set(snapshot.effective_mode)
        self.endpoint_var.set(snapshot.endpoint)
        self.current_proxy_var.set(snapshot.current_proxy_url)
        self.liveness_var.set(snapshot.liveness)
        self.severity_var.set(snapshot.severity)
        self.operator_action_var.set(snapshot.operator_action)
        self.machine_error_var.set(snapshot.machine_error_code)
        self.pool_var.set(
            "A:{active} R:{reserve} T:{retired} H:{healthy} D:{degraded} X:{down}".format(
                active=snapshot.active_count,
                reserve=snapshot.reserve_count,
                retired=snapshot.retired_count,
                healthy=snapshot.healthy_count,
                degraded=snapshot.degraded_count,
                down=snapshot.down_count,
            )
        )
        self.attestation_var.set(
            (
                f"{snapshot.attestation_status} / "
                f"{snapshot.attestation_machine_error_code} / "
                f"{snapshot.attestation_source} @ {snapshot.attestation_observed_at}"
            ).strip()
        )
        self.last_error_var.set(snapshot.last_error)
        self.integration_var.set(snapshot.integration_error)

    def _apply_account_snapshot(self, snapshot: AccountPoolSnapshot) -> None:
        self.account_registry_var.set(
            (
                f"{snapshot.registry_identity_status} / "
                f"{snapshot.registry_identity_machine_error_code} / "
                f"{snapshot.registry_identity_next_action}"
            ).strip()
        )
        self.account_counts_var.set(
            "A:{active} R:{reserve} T:{retired}".format(
                active=snapshot.active_count,
                reserve=snapshot.reserve_count,
                retired=snapshot.retired_count,
            )
        )
        self.account_capacity_var.set(str(snapshot.capacity_target))
        self.account_integration_var.set(snapshot.integration_error)

        for item in self.accounts_tree.get_children():
            self.accounts_tree.delete(item)
        for account in snapshot.accounts:
            self.accounts_tree.insert(
                "",
                "end",
                iid=account.backend_id,
                values=(
                    account.backend_id,
                    account.label,
                    account.pool,
                    "yes" if account.manual_hold else "no",
                    account.status,
                    account.fail_count,
                    account.success_count,
                    account.last_success,
                    account.last_error,
                    account.cooldown_until,
                    account.notes,
                ),
            )

    def _apply_refresh_results(
        self,
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        *,
        banner: str | None = None,
    ) -> None:
        self._apply_runtime_snapshot(runtime_snapshot)
        self._apply_account_snapshot(account_snapshot)
        self.banner_var.set(banner or runtime_snapshot.human_message)
        self.set_busy(False)

    def run_mode_action(self, prompt: str, command: tuple[str, ...]) -> None:
        if self._busy:
            return
        if not messagebox.askyesno("Confirm action", prompt, parent=self.root):
            return
        self.set_busy(True)
        self.banner_var.set("Running operator action...")
        threading.Thread(target=self._action_worker, args=(command,), daemon=True).start()

    def run_sync_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run managed sync and refresh runtime truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running operator action...")
        threading.Thread(target=self._sync_worker, daemon=True).start()

    def run_launch_client_action(self) -> None:
        if self._busy:
            return
        client_path = self.launch_client_path_var.get().strip()
        if not client_path:
            messagebox.showinfo(
                "Client path required",
                "Enter absolute client path before launch.",
                parent=self.root,
            )
            return
        if not os.path.isabs(client_path):
            messagebox.showinfo(
                "Absolute path required",
                "Enter an absolute client path before launch.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run bounded launch-client dispatch and refresh runtime truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running launch client...")
        threading.Thread(
            target=self._launch_client_worker,
            args=(("launch", "client", "--client-path", client_path, "--json"),),
            daemon=True,
        ).start()

    def run_smoke_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run runtime smoke test and refresh runtime truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running smoke test...")
        threading.Thread(target=self._smoke_worker, daemon=True).start()

    def run_onboard_action(self) -> None:
        if self._busy:
            return
        auth_ref = self.onboarding_auth_ref_var.get().strip()
        if not auth_ref:
            messagebox.showinfo(
                "Explicit auth required",
                "Enter explicit auth ref before onboarding.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run reserve-first explicit-auth onboarding and refresh command truth?",
            parent=self.root,
        ):
            return
        command = ["accounts", "onboard", "--json", "--auth-ref", auth_ref, "--non-interactive"]
        self.set_busy(True)
        self.banner_var.set("Running onboarding...")
        threading.Thread(
            target=self._onboard_worker,
            args=(tuple(command),),
            daemon=True,
        ).start()

    def _selected_account_id(self) -> str | None:
        selection = self.accounts_tree.selection()
        if not selection:
            return None
        return str(selection[0])

    def run_validate_action(self) -> None:
        self._run_account_check_action("Validate")

    def run_recheck_action(self) -> None:
        self._run_account_check_action("Recheck")

    def _run_account_check_action(self, label: str) -> None:
        if self._busy:
            return
        backend_id = self._selected_account_id()
        if backend_id is None:
            messagebox.showinfo("Select account", "Select an account first.", parent=self.root)
            return
        self.set_busy(True)
        self.banner_var.set(f"Running {label.lower()}...")
        threading.Thread(
            target=self._account_check_worker,
            args=(backend_id,),
            daemon=True,
        ).start()

    def run_promote_action(self) -> None:
        self._run_account_mutation_action(
            "Promote",
            "Promote selected reserve account into active routing?",
            "promote",
        )

    def run_demote_action(self) -> None:
        self._run_account_mutation_action(
            "Demote",
            "Demote selected active account back to reserve?",
            "demote",
        )

    def run_hold_action(self) -> None:
        self._run_account_mutation_action(
            "Hold",
            "Place selected account on hold and isolate it from active routing?",
            "hold",
        )

    def run_release_action(self) -> None:
        self._run_account_mutation_action(
            "Release",
            "Release selected held account back to reserve semantics?",
            "release",
        )

    def run_retire_action(self) -> None:
        self._run_account_mutation_action(
            "Retire",
            "Retire selected account with terminal no-return semantics?",
            "retire",
        )

    def _run_account_mutation_action(
        self,
        label: str,
        prompt: str,
        subcommand: str,
    ) -> None:
        if self._busy:
            return
        backend_id = self._selected_account_id()
        if backend_id is None:
            messagebox.showinfo("Select account", "Select an account first.", parent=self.root)
            return
        if not messagebox.askyesno("Confirm action", prompt, parent=self.root):
            return
        self.set_busy(True)
        self.banner_var.set(f"Running {label.lower()}...")
        threading.Thread(
            target=self._account_mutation_worker,
            args=(("accounts", subcommand, backend_id, "--json"),),
            daemon=True,
        ).start()

    def _action_worker(self, command: tuple[str, ...]) -> None:
        try:
            action_payload, runtime_snapshot = run_mode_control_and_refresh(self.runner, command)
            account_snapshot = load_account_pool_snapshot(self.runner)
            ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_refresh_results(
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _sync_worker(self) -> None:
        try:
            action_payload, runtime_snapshot, account_snapshot = run_sync_and_refresh(
                self.runner
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_refresh_results(
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _launch_client_worker(self, command: tuple[str, ...]) -> None:
        try:
            action_payload, runtime_snapshot = run_launch_client_and_refresh(
                self.runner, command
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
            }
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_launch_client_results(
                action_payload,
                runtime_snapshot,
                banner=banner,
            ),
        )

    def _smoke_worker(self) -> None:
        action_payload: dict[str, Any] | None = None
        try:
            action_payload = self.runner.run("launch", "smoke", "--json").payload
            banner = str(action_payload.get("human_message", "Smoke test completed."))
            try:
                status_payload = self.runner.run("status", "--json").payload
                runtime_snapshot = build_runtime_snapshot(status_payload=status_payload)
            except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
                runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
                banner = "Operator action failed."
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = action_payload or {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
            }
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_smoke_results(
                action_payload,
                runtime_snapshot,
                banner=banner,
            ),
        )

    def _account_check_worker(self, backend_id: str) -> None:
        try:
            action_payload, account_snapshot = run_account_validate_and_refresh(
                self.runner, backend_id
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        def apply() -> None:
            self._apply_account_snapshot(account_snapshot)
            self.banner_var.set(banner)
            self.set_busy(False)

        self.root.after(0, apply)

    def _account_mutation_worker(self, command: tuple[str, ...]) -> None:
        try:
            action_payload, runtime_snapshot, account_snapshot = run_account_mutation_and_refresh(
                self.runner, command
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_refresh_results(
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _apply_launch_client_payload(self, action_payload: dict[str, Any]) -> None:
        self.launch_command_status_var.set(str(action_payload.get("status", "")))
        self.launch_command_exit_code_var.set(str(action_payload.get("exit_code", "")))
        self.launch_command_human_message_var.set(str(action_payload.get("human_message", "")))
        self.launch_command_machine_error_var.set(str(action_payload.get("machine_error_code", "")))
        self.launch_command_next_action_var.set(str(action_payload.get("next_action", "")))
        changed_files_value = action_payload.get("changed_files")
        if changed_files_value is None:
            self.launch_command_changed_files_var.set("")
        else:
            self.launch_command_changed_files_var.set(format_onboarding_value(changed_files_value))
        malformed_surface = False
        try:
            field_values = build_client_launch_field_values(action_payload)
        except UiShellError:
            field_values = {field: "" for field in CLIENT_LAUNCH_RESULT_FIELDS}
            malformed_surface = True
        for field, value in field_values.items():
            self.launch_field_vars[field].set(value)
        rendered_state = classify_client_launch_rendered_state(
            action_payload, field_values, malformed=malformed_surface
        )
        self.launch_rendered_state_var.set(rendered_state)

    def _apply_launch_client_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        *,
        banner: str,
    ) -> None:
        self._apply_launch_client_payload(action_payload)
        self._apply_runtime_snapshot(runtime_snapshot)
        self.banner_var.set(banner)
        self.set_busy(False)

    def _apply_smoke_payload(self, action_payload: dict[str, Any]) -> None:
        self.smoke_command_status_var.set(str(action_payload.get("status", "")))
        self.smoke_command_exit_code_var.set(str(action_payload.get("exit_code", "")))
        self.smoke_command_human_message_var.set(str(action_payload.get("human_message", "")))
        self.smoke_command_machine_error_var.set(str(action_payload.get("machine_error_code", "")))
        self.smoke_command_next_action_var.set(str(action_payload.get("next_action", "")))
        changed_files_value = action_payload.get("changed_files")
        if changed_files_value is None:
            self.smoke_command_changed_files_var.set("")
        else:
            self.smoke_command_changed_files_var.set(format_onboarding_value(changed_files_value))
        malformed_surface = False
        try:
            field_values = build_smoke_field_values(action_payload)
        except UiShellError:
            field_values = {field: "" for field in SMOKE_RESULT_FIELDS}
            malformed_surface = True
        for field, value in field_values.items():
            self.smoke_field_vars[field].set(value)
        rendered_state = classify_smoke_rendered_state(
            action_payload, malformed=malformed_surface
        )
        self.smoke_rendered_state_var.set(rendered_state)

    def _apply_smoke_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        *,
        banner: str,
    ) -> None:
        self._apply_smoke_payload(action_payload)
        self._apply_runtime_snapshot(runtime_snapshot)
        self.banner_var.set(banner)
        self.set_busy(False)

    def _apply_onboarding_payload(self, action_payload: dict[str, Any]) -> None:
        self.onboarding_command_status_var.set(str(action_payload.get("status", "")))
        self.onboarding_machine_error_var.set(str(action_payload.get("machine_error_code", "")))
        self.onboarding_next_action_var.set(str(action_payload.get("next_action", "")))
        try:
            field_values = build_onboarding_field_values(action_payload)
        except UiShellError:
            field_values = {field: "" for field in ONBOARDING_RESULT_FIELDS}
        for field, value in field_values.items():
            self.onboarding_field_vars[field].set(value)

    def _onboard_worker(self, command: tuple[str, ...]) -> None:
        try:
            action_payload, runtime_snapshot, account_snapshot = run_account_onboard_and_refresh(
                self.runner, command
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = {
                "status": "integration_failure",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "next_action": "retry",
            }
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_onboarding_refresh_results(
                action_payload,
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _apply_onboarding_refresh_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        *,
        banner: str,
    ) -> None:
        self._apply_onboarding_payload(action_payload)
        self._apply_refresh_results(runtime_snapshot, account_snapshot, banner=banner)


def main() -> int:
    root = Tk()
    runner = JsonCommandRunner()
    MinimalCompanionShell(root, runner)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
