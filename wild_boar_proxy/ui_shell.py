# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from subprocess import SubprocessError
from typing import Any

from wild_boar_proxy.process_runner import (
    PROCESS_NOT_FOUND,
    PROCESS_OK,
    PROCESS_TIMEOUT,
    run_bounded_process,
)

try:
    from tkinter import StringVar, Tk, messagebox
    from tkinter import ttk
except ModuleNotFoundError as exc:
    StringVar = None  # type: ignore[assignment]
    Tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]
    _TKINTER_IMPORT_ERROR: ModuleNotFoundError | None = exc

    class _UnavailableMessagebox:
        def askyesno(self, *args: Any, **kwargs: Any) -> bool:
            raise RuntimeError("tkinter is unavailable")

        def showinfo(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("tkinter is unavailable")

    messagebox = _UnavailableMessagebox()
else:
    _TKINTER_IMPORT_ERROR = None


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
EXTERNAL_STATUS_FIELDS = (
    "foundation_phase",
    "adapter_runtime_available",
    "lifecycle_mode",
    "adapter_state",
    "listener_proven",
    "runtime_claim_blocked",
    "profile_ready",
    "routes_count",
    "observed_routes_count",
    "adapter",
    "local_auth",
)
EXTERNAL_OBSERVED_ROUTE_FIELDS = (
    "availability_state",
    "evidence_level",
    "last_verified_at",
    "last_validate",
    "last_check",
    "last_error",
    "latency_ms",
    "fallback_used",
    "effective_model",
)
EXTERNAL_MODELS_FIELDS = (
    "models",
    "count",
    "source",
    "listener_proven",
    "runtime_claim_blocked",
)
EXTERNAL_MODEL_FIELDS = (
    "route_id",
    "display_name",
    "provider",
    "base_url",
    "endpoint_path",
    "upstream_model",
    "compatibility",
    "cost_class",
    "enabled",
    "lane_role",
    "fallback_eligible",
    "synthetic_adapter_state",
    "profile_ready",
)
EXTERNAL_ROUTES_LIST_FIELDS = ("routes", "count")
EXTERNAL_ROUTE_FIELDS = (
    "schema_version",
    "route_id",
    "display_name",
    "provider",
    "base_url",
    "endpoint_path",
    "upstream_model",
    "compatibility",
    "auth",
    "cost_class",
    "lane_role",
    "fallback_eligible",
    "enabled",
)
EXTERNAL_PROFILE_FIELDS = (
    "profile_kind",
    "route_id",
    "base_url",
    "model",
    "api_key_source",
    "writes_external_config",
    "profile_ready",
    "listener_proven",
    "runtime_claim_blocked",
    "synthetic_endpoint_contract",
    "prerequisite",
)
ONBOARDING_RESULT_FIELDS = (
    "input_mode",
    "explicit_auth_ref",
    "new_backend_ids",
    "selected_backend_id",
    "selection_status",
    "reserve_first_enforced",
    "auth_snapshot_before_login_status",
    "auth_snapshot_before_login_count",
    "auth_snapshot_before_login_digest",
    "auth_snapshot_before_login_source",
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
DIAGNOSTICS_RESULT_FIELDS = ("bundle_path",)
STABLE_REPAIR_RESULT_FIELDS = ()
ACCOUNT_CAPACITY_TARGET = 25
DEFAULT_ACTIVE_WINDOW_TARGET = 10
UI_SHELL_COMMAND_TIMEOUT_SECONDS = 120.0
UI_SHELL_COMMAND_OUTPUT_CAP_BYTES = 256 * 1024


class UiShellError(Exception):
    """Raised when the UI cannot trust a command result."""


def _require_tkinter() -> None:
    if Tk is None or StringVar is None or ttk is None:
        raise UiShellError("tkinter is required for the desktop UI") from _TKINTER_IMPORT_ERROR


def _require_tkinter_root() -> None:
    if Tk is None:
        raise UiShellError("tkinter is required for the desktop UI") from _TKINTER_IMPORT_ERROR


def parse_exact_json_object(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    try:
        payload, end = decoder.raw_decode(stdout)
    except json.JSONDecodeError as exc:
        raise UiShellError("stdout must contain exactly one JSON object") from exc
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
        try:
            result = run_bounded_process(
                [*self._base_command, *args],
                cwd=self._cwd,
                env=self._env if self._env is not None else os.environ.copy(),
                timeout_seconds=UI_SHELL_COMMAND_TIMEOUT_SECONDS,
                output_cap_bytes=UI_SHELL_COMMAND_OUTPUT_CAP_BYTES,
            )
        except Exception as exc:
            raise UiShellError("command execution failed before JSON payload was available") from exc
        if result.timed_out or result.machine_error_code == PROCESS_TIMEOUT:
            raise UiShellError("command execution timed out before JSON payload was available")
        if result.machine_error_code == PROCESS_NOT_FOUND:
            raise UiShellError("command executable was not found before JSON payload was available")
        if result.exit_code is None:
            raise UiShellError("command execution ended without an exit code")
        if result.machine_error_code not in {PROCESS_OK, "PROCESS_FAILED"}:
            raise UiShellError("command execution failed before JSON payload was available")
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


@dataclass(frozen=True)
class ExternalModelRecord:
    route_id: str
    display_name: str
    provider: str
    base_url: str
    endpoint_path: str
    upstream_model: str
    compatibility: str
    cost_class: str
    enabled: bool
    lane_role: str
    fallback_eligible: bool
    synthetic_adapter_state: str
    profile_ready: bool
    thinking: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExternalRouteRecord:
    route_id: str
    display_name: str
    provider: str
    base_url: str
    endpoint_path: str
    upstream_model: str
    compatibility: str
    cost_class: str
    enabled: bool
    lane_role: str
    fallback_eligible: bool
    auth_type: str
    secret_ref: str
    thinking: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExternalActionResult:
    action: str
    status: str
    human_message: str
    machine_error_code: str
    next_action: str
    liveness: str
    severity: str
    operator_action: str
    route_id: str
    verification_scope: str
    route_state: str
    listener_proven: bool
    runtime_claim_blocked: bool
    profile_ready: bool
    network_dependent: bool
    evidence_path: str
    effective_model: str
    provider: str
    fallback_used: str
    fallback_chain: str
    latency_ms: str
    request_count: str
    writes_external_config: str
    prerequisite: str
    base_url: str
    changed_files: tuple[str, ...]
    observed_at_utc: str
    is_stale: bool
    stale_reason: str


@dataclass(frozen=True)
class QuickStartLedgerEntry:
    observed_at_utc: str
    action_id: str
    status: str
    machine_error_code: str
    next_action: str
    human_message: str


@dataclass(frozen=True)
class ExternalModelsSnapshot:
    foundation_phase: str
    adapter_runtime_available: bool
    lifecycle_mode: str
    adapter_state: str
    listener_proven: bool
    runtime_claim_blocked: bool
    profile_ready: bool
    routes_count: int
    observed_routes_count: int
    observed_routes: dict[str, dict[str, Any]]
    local_token_present: bool
    available_secret_refs: tuple[str, ...] | None
    models_source: str
    models: tuple[ExternalModelRecord, ...]
    routes: tuple[ExternalRouteRecord, ...]
    integration_error: str

    @classmethod
    def integration_failure(cls, message: str) -> "ExternalModelsSnapshot":
        return cls(
            foundation_phase="unknown",
            adapter_runtime_available=False,
            lifecycle_mode="unknown",
            adapter_state="unknown",
            listener_proven=False,
            runtime_claim_blocked=True,
            profile_ready=False,
            routes_count=0,
            observed_routes_count=0,
            observed_routes={},
            local_token_present=False,
            available_secret_refs=None,
            models_source="integration_failure",
            models=(),
            routes=(),
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


def _normalize_external_model_record(raw: dict[str, Any]) -> ExternalModelRecord:
    require_fields(raw, EXTERNAL_MODEL_FIELDS, "external model record")
    return ExternalModelRecord(
        route_id=str(raw["route_id"]),
        display_name=str(raw["display_name"]),
        provider=str(raw["provider"]),
        base_url=str(raw["base_url"]),
        endpoint_path=str(raw["endpoint_path"]),
        upstream_model=str(raw["upstream_model"]),
        compatibility=str(raw["compatibility"]),
        cost_class=str(raw["cost_class"]),
        enabled=require_bool(raw["enabled"], "external model enabled"),
        lane_role=str(raw["lane_role"]),
        fallback_eligible=require_bool(
            raw["fallback_eligible"], "external model fallback_eligible"
        ),
        synthetic_adapter_state=str(raw["synthetic_adapter_state"]),
        profile_ready=require_bool(raw["profile_ready"], "external model profile_ready"),
        thinking=dict(raw.get("thinking") or {}),
    )


def _normalize_external_route_record(raw: dict[str, Any]) -> ExternalRouteRecord:
    require_fields(raw, EXTERNAL_ROUTE_FIELDS, "external route record")
    auth = raw["auth"]
    if not isinstance(auth, dict):
        raise UiShellError("external route auth must be an object")
    return ExternalRouteRecord(
        route_id=str(raw["route_id"]),
        display_name=str(raw["display_name"]),
        provider=str(raw["provider"]),
        base_url=str(raw["base_url"]),
        endpoint_path=str(raw["endpoint_path"]),
        upstream_model=str(raw["upstream_model"]),
        compatibility=str(raw["compatibility"]),
        cost_class=str(raw["cost_class"]),
        enabled=require_bool(raw["enabled"], "external route enabled"),
        lane_role=str(raw["lane_role"]),
        fallback_eligible=require_bool(
            raw["fallback_eligible"], "external route fallback_eligible"
        ),
        auth_type=str(auth.get("type", "")),
        secret_ref=str(auth.get("secret_ref", "")),
        thinking=dict(raw.get("thinking") or {}),
    )


def build_external_models_snapshot(
    *,
    status_payload: dict[str, Any],
    models_payload: dict[str, Any],
    routes_payload: dict[str, Any],
) -> ExternalModelsSnapshot:
    require_fields(status_payload, ("data",), "external-models status payload")
    require_fields(models_payload, ("data",), "external-models models payload")
    require_fields(routes_payload, ("data",), "external-models routes list payload")

    status_data = status_payload["data"]
    models_data = models_payload["data"]
    routes_data = routes_payload["data"]
    if not isinstance(status_data, dict):
        raise UiShellError("external-models status data must be an object")
    if not isinstance(models_data, dict):
        raise UiShellError("external-models models data must be an object")
    if not isinstance(routes_data, dict):
        raise UiShellError("external-models routes list data must be an object")

    require_fields(status_data, EXTERNAL_STATUS_FIELDS, "external-models status data")
    require_fields(models_data, EXTERNAL_MODELS_FIELDS, "external-models models data")
    require_fields(routes_data, EXTERNAL_ROUTES_LIST_FIELDS, "external-models routes data")

    models_raw = models_data["models"]
    if not isinstance(models_raw, list):
        raise UiShellError("external-models models must be a list")
    models = tuple(
        _normalize_external_model_record(item) for item in models_raw if isinstance(item, dict)
    )
    if len(models) != len(models_raw):
        raise UiShellError("external-models models must contain only objects")

    routes_raw = routes_data["routes"]
    if not isinstance(routes_raw, list):
        raise UiShellError("external-models routes must be a list")
    routes = tuple(
        _normalize_external_route_record(item) for item in routes_raw if isinstance(item, dict)
    )
    if len(routes) != len(routes_raw):
        raise UiShellError("external-models routes must contain only objects")

    local_auth = status_data["local_auth"]
    if not isinstance(local_auth, dict):
        raise UiShellError("external-models status local_auth must be an object")
    observed_routes = _normalize_external_observed_routes(
        status_data.get("observed_routes", {})
    )
    available_secret_refs_raw = status_data.get("available_secret_refs")
    available_secret_refs: tuple[str, ...] | None = None
    if available_secret_refs_raw is not None:
        if not isinstance(available_secret_refs_raw, list):
            raise UiShellError("external-models available_secret_refs must be a list when present")
        normalized_refs: list[str] = []
        for item in available_secret_refs_raw:
            if not isinstance(item, str) or not item.strip():
                raise UiShellError("external-models available_secret_refs must contain non-empty strings")
            normalized_refs.append(item.strip())
        available_secret_refs = tuple(normalized_refs)

    return ExternalModelsSnapshot(
        foundation_phase=str(status_data["foundation_phase"]),
        adapter_runtime_available=require_bool(
            status_data["adapter_runtime_available"],
            "external-models adapter_runtime_available",
        ),
        lifecycle_mode=str(status_data["lifecycle_mode"]),
        adapter_state=str(status_data["adapter_state"]),
        listener_proven=require_bool(
            status_data["listener_proven"], "external-models listener_proven"
        ),
        runtime_claim_blocked=require_bool(
            status_data["runtime_claim_blocked"],
            "external-models runtime_claim_blocked",
        ),
        profile_ready=require_bool(
            status_data["profile_ready"], "external-models profile_ready"
        ),
        routes_count=require_nonnegative_int(
            status_data["routes_count"], "external-models routes_count"
        ),
        observed_routes_count=require_nonnegative_int(
            status_data["observed_routes_count"],
            "external-models observed_routes_count",
        ),
        observed_routes=observed_routes,
        local_token_present=require_bool(
            local_auth.get("token_present", False), "external-models local token present"
        ),
        available_secret_refs=available_secret_refs,
        models_source=str(models_data["source"]),
        models=models,
        routes=routes,
        integration_error="",
    )


def external_route_secret_available(
    snapshot: ExternalModelsSnapshot,
    secret_ref: str,
) -> bool:
    if not secret_ref:
        return False
    if snapshot.available_secret_refs is not None:
        return secret_ref in snapshot.available_secret_refs
    return snapshot.local_token_present


def _normalize_external_observed_routes(payload: Any) -> dict[str, dict[str, Any]]:
    if payload in ({}, None):
        return {}
    if not isinstance(payload, dict):
        raise UiShellError("external-models observed_routes must be an object")
    normalized: dict[str, dict[str, Any]] = {}
    for route_id, route_state in payload.items():
        if not isinstance(route_id, str) or not route_id:
            raise UiShellError("external-models observed route id must be a non-empty string")
        if not isinstance(route_state, dict):
            raise UiShellError("external-models observed route state must be an object")
        normalized_state: dict[str, Any] = {}
        for field in EXTERNAL_OBSERVED_ROUTE_FIELDS:
            if field in route_state:
                normalized_state[field] = route_state[field]
        normalized[route_id] = normalized_state
    return normalized


def load_external_models_snapshot(runner: JsonCommandRunner) -> ExternalModelsSnapshot:
    return build_external_models_snapshot(
        status_payload=runner.run("external-models", "status", "--json").payload,
        models_payload=runner.run("external-models", "models", "--json").payload,
        routes_payload=runner.run("external-models", "routes", "list", "--json").payload,
    )


def run_external_profile_and_refresh(
    runner: JsonCommandRunner, route_id: str
) -> tuple[dict[str, Any], ExternalModelsSnapshot]:
    action_result = runner.run(
        "external-models",
        "profile",
        "codex-desktop",
        "--route",
        route_id,
        "--json",
    )
    snapshot = load_external_models_snapshot(runner)
    return action_result.payload, snapshot


def run_external_check_and_refresh(
    runner: JsonCommandRunner, route_id: str
) -> tuple[dict[str, Any], ExternalModelsSnapshot]:
    action_result = runner.run("external-models", "check", "--route", route_id, "--json")
    snapshot = load_external_models_snapshot(runner)
    return action_result.payload, snapshot


def build_external_action_result(
    *, action: str, action_payload: dict[str, Any]
) -> ExternalActionResult:
    require_fields(
        action_payload,
        (
            "status",
            "human_message",
            "machine_error_code",
            "changed_files",
            "next_action",
            "liveness",
            "severity",
            "operator_action",
            "data",
        ),
        "external action payload",
    )
    data = action_payload["data"]
    if not isinstance(data, dict):
        raise UiShellError("external action payload data must be an object")
    changed_files = action_payload["changed_files"]
    if not isinstance(changed_files, list):
        raise UiShellError("external action changed_files must be a list")
    return ExternalActionResult(
        action=action,
        status=str(action_payload["status"]),
        human_message=str(action_payload["human_message"]),
        machine_error_code=str(action_payload["machine_error_code"]),
        next_action=str(action_payload["next_action"]),
        liveness=str(action_payload["liveness"]),
        severity=str(action_payload["severity"]),
        operator_action=str(action_payload["operator_action"]),
        route_id=str(data.get("route_id", data.get("requested_model", ""))),
        verification_scope=str(data.get("verification_scope", "")),
        route_state=str(data.get("route_state", "")),
        listener_proven=require_bool(
            data.get("listener_proven", False), "external action listener_proven"
        ),
        runtime_claim_blocked=require_bool(
            data.get("runtime_claim_blocked", False),
            "external action runtime_claim_blocked",
        ),
        profile_ready=require_bool(
            data.get("profile_ready", False), "external action profile_ready"
        ),
        network_dependent=require_bool(
            data.get("network_dependent", data.get("network_dependent_evidence", False)),
            "external action network_dependent",
        ),
        evidence_path=str(data.get("evidence_path", "")),
        effective_model=str(data.get("effective_model", "")),
        provider=str(data.get("provider", "")),
        fallback_used=format_onboarding_value(data.get("fallback_used", "")),
        fallback_chain=format_onboarding_value(data.get("fallback_chain", "")),
        latency_ms=format_onboarding_value(data.get("latency_ms", "")),
        request_count=format_onboarding_value(data.get("request_count", "")),
        writes_external_config=format_onboarding_value(
            data.get("writes_external_config", "")
        ),
        prerequisite=str(data.get("prerequisite", "")),
        base_url=str(data.get("base_url", "")),
        changed_files=tuple(str(item) for item in changed_files),
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        is_stale=False,
        stale_reason="",
    )


def mark_external_action_stale(
    action: ExternalActionResult | None,
    *,
    reason: str,
) -> ExternalActionResult | None:
    if action is None:
        return None
    return replace(action, is_stale=True, stale_reason=reason)


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


def build_live_runtime_status_payload(
    *,
    status_payload: dict[str, Any],
    health_payload: dict[str, Any],
) -> dict[str, Any]:
    require_fields(
        health_payload,
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
        ),
        "healthcheck payload",
    )
    attestation = health_payload.get("attestation")
    if not isinstance(attestation, dict):
        raise UiShellError("healthcheck payload attestation must be an object")
    require_fields(
        attestation,
        ("attestation_source", "observed_at_utc"),
        "healthcheck attestation",
    )
    merged = dict(status_payload)
    for field in (
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
        "last_error",
    ):
        if field in health_payload:
            merged[field] = health_payload[field]
    merged["attestation_summary"] = {
        "status": health_payload["status"],
        "machine_error_code": health_payload["machine_error_code"],
        "attestation_source": str(attestation["attestation_source"]),
        "observed_at_utc": str(attestation["observed_at_utc"]),
    }
    return merged


def load_runtime_snapshot(
    runner: JsonCommandRunner, *, live_probe: bool = False
) -> RuntimeSnapshot:
    status_payload = runner.run("status", "--json").payload
    mode_payload = runner.run("mode", "get", "--json").payload
    if live_probe:
        status_payload = build_live_runtime_status_payload(
            status_payload=status_payload,
            health_payload=runner.run("healthcheck", "--json").payload,
        )
    return build_runtime_snapshot(
        status_payload=status_payload,
        mode_payload=mode_payload,
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


def run_diagnostics_export_and_refresh(
    runner: JsonCommandRunner,
) -> tuple[dict[str, Any], RuntimeSnapshot, AccountPoolSnapshot]:
    action_result = runner.run("diagnostics", "export", "--json")
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


def run_stable_repair_and_refresh(
    runner: JsonCommandRunner,
) -> tuple[dict[str, Any], RuntimeSnapshot, AccountPoolSnapshot]:
    action_result = runner.run("stable", "repair", "--apply", "--json")
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


def build_diagnostics_field_values(action_payload: dict[str, Any]) -> dict[str, str]:
    result = {field: "" for field in DIAGNOSTICS_RESULT_FIELDS}
    for field in DIAGNOSTICS_RESULT_FIELDS:
        if field in action_payload:
            result[field] = format_onboarding_value(action_payload[field])
    return result


def build_external_profile_field_values(action_payload: dict[str, Any]) -> dict[str, str]:
    result = {field: "" for field in EXTERNAL_PROFILE_FIELDS}
    data = action_payload.get("data")
    if data is None:
        return result
    if not isinstance(data, dict):
        raise UiShellError("external profile data must be an object when present")
    for field in EXTERNAL_PROFILE_FIELDS:
        if field in data:
            result[field] = format_onboarding_value(data[field])
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


def classify_external_profile_rendered_state(
    action_payload: dict[str, Any], field_values: dict[str, str], *, malformed: bool
) -> str:
    if malformed:
        return "integration_failure"
    command_status = str(action_payload.get("status", ""))
    if command_status == "integration_failure":
        return "integration_failure"
    if command_status != "ok":
        return "failure"
    if (
        field_values.get("profile_kind", "") == "codex_desktop_openai_compatible"
        and field_values.get("route_id", "")
        and field_values.get("writes_external_config", "") == "false"
    ):
        return "profile_packet_only"
    return "unknown"


def select_primary_external_route(
    snapshot: ExternalModelsSnapshot,
) -> ExternalRouteRecord | None:
    enabled_routes = [route for route in snapshot.routes if route.enabled]
    if len(enabled_routes) == 1:
        return enabled_routes[0]
    if len(snapshot.routes) == 1:
        return snapshot.routes[0]
    for route in snapshot.routes:
        if route.enabled:
            return route
    return snapshot.routes[0] if snapshot.routes else None


def describe_primary_external_route(
    snapshot: ExternalModelsSnapshot,
) -> dict[str, str | bool]:
    route = select_primary_external_route(snapshot)
    if route is None:
        return {
            "route_id": "",
            "display_name": "",
            "provider": "",
            "secret_ref": "",
            "enabled": False,
            "role_label": "",
            "secret_status_label": "unknown",
            "validation_label": "not configured",
            "validation_visual_state": "neutral",
            "last_checked": "",
            "status_code": "missing",
            "note": "Основной API route не подтверждён bounded snapshot.",
        }
    secret_ref = route.secret_ref
    if external_route_secret_available(snapshot, secret_ref):
        secret_status_label = "available"
        secret_visual_state = "green"
        status_code = "enabled" if route.enabled else "disabled"
        status_label = "Разрешён" if route.enabled else "Отключён"
        note = (
            "Маршрут показан по registry-пакету. Отдельная проверка запроса ещё не выполнялась."
            if route.enabled
            else "Маршрут отключён в registry-пакете."
        )
        validation_label = "not checked"
        validation_visual_state = "neutral"
        observed = snapshot.observed_routes.get(route.route_id, {}) or {}
        observed_state = str(observed.get("availability_state", "")).strip()
        last_checked = format_onboarding_value(
            observed.get("last_check")
            or observed.get("last_validate")
            or observed.get("last_verified_at")
            or ""
        )
        if observed_state == "verified":
            validation_label = "ok"
            validation_visual_state = "green"
            note = "Проверочный запрос маршрута зафиксирован bounded packet и refresh truth."
        elif observed_state == "model_visible":
            validation_label = "ok"
            validation_visual_state = "blue"
            note = "Проверка provider route завершилась без runtime claims."
        elif observed_state in {"provider_auth_failed", "model_not_available"}:
            validation_label = "validate failed"
            validation_visual_state = "red"
            note = "Последняя provider-проверка маршрута завершилась ошибкой."
        elif observed_state in {"provider_network_failed", "limited"}:
            validation_label = "check failed"
            validation_visual_state = "amber"
            note = "Последняя проверка маршрута требует внимания оператора."
        elif observed_state == "blocked":
            validation_label = "blocked"
            validation_visual_state = "amber"
            note = "Последняя проверка маршрута требует внимания оператора."
        return {
            "route_id": route.route_id,
            "display_name": route.display_name,
            "provider": route.provider,
            "secret_ref": secret_ref,
            "enabled": route.enabled,
            "role_label": "main route" if route.enabled else "candidate",
            "secret_status_label": secret_status_label,
            "secret_visual_state": secret_visual_state,
            "validation_label": validation_label,
            "validation_visual_state": validation_visual_state,
            "last_checked": last_checked,
            "status_code": status_code,
            "status_label": status_label,
            "note": note,
        }
    if secret_ref:
        return {
            "route_id": route.route_id,
            "display_name": route.display_name,
            "provider": route.provider,
            "secret_ref": secret_ref,
            "enabled": route.enabled,
            "role_label": "main route" if route.enabled else "candidate",
            "secret_status_label": "missing",
            "secret_visual_state": "amber",
            "validation_label": "blocked by secret",
            "validation_visual_state": "amber",
            "last_checked": "",
            "status_code": "missing_secret" if route.enabled else "disabled",
            "status_label": "Требует ключ" if route.enabled else "Отключён",
            "note": "Локальный ключ не подтверждён; маршрут нельзя считать готовым к проверочному запросу.",
        }
    return {
        "route_id": route.route_id,
        "display_name": route.display_name,
        "provider": route.provider,
        "secret_ref": "",
        "enabled": route.enabled,
        "role_label": "main route" if route.enabled else "candidate",
        "secret_status_label": "unknown",
        "secret_visual_state": "neutral",
        "validation_label": "not checked",
        "validation_visual_state": "neutral",
        "last_checked": "",
        "status_code": "enabled" if route.enabled else "disabled",
        "status_label": "Разрешён" if route.enabled else "Отключён",
        "note": "Маршрут не сообщает bounded secret_ref.",
    }


def build_quick_start_account_component(account_snapshot: AccountPoolSnapshot) -> dict[str, str]:
    visible_count = len(account_snapshot.accounts)
    problem_count = sum(
        1
        for account in account_snapshot.accounts
        if account.status in {"down", "degraded"} or bool(account.last_error)
    )
    if account_snapshot.integration_error:
        return {
            "status": "failed",
            "machine_error_code": "UI_CHECK_ALL_ACCOUNTS_UNAVAILABLE",
            "human_message": account_snapshot.integration_error,
        }
    if visible_count <= 0:
        return {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_NO_ACCOUNTS",
            "human_message": "В sandbox пока нет подключённых аккаунтов; ready не подтверждается.",
        }
    if problem_count > 0:
        return {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_ACCOUNTS_NEED_ATTENTION",
            "human_message": "В accounts snapshot есть problem-аккаунты; нужен следующий шаг.",
        }
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "human_message": account_snapshot.human_message,
    }


def build_quick_start_runtime_component(runtime_snapshot: RuntimeSnapshot) -> dict[str, str]:
    if runtime_snapshot.integration_error:
        return {
            "status": "failed",
            "machine_error_code": runtime_snapshot.machine_error_code or "UI_CHECK_ALL_RUNTIME_UNAVAILABLE",
            "human_message": runtime_snapshot.integration_error,
            "visual_state": "integration_failure",
        }
    if runtime_snapshot.liveness == "healthy":
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": runtime_snapshot.human_message,
            "visual_state": "healthy",
        }
    if runtime_snapshot.liveness in {"degraded", "stale", "unknown"}:
        return {
            "status": "partial",
            "machine_error_code": runtime_snapshot.machine_error_code or "UI_CHECK_ALL_RUNTIME_DEGRADED",
            "human_message": runtime_snapshot.human_message,
            "visual_state": runtime_snapshot.liveness,
        }
    return {
        "status": "failed",
        "machine_error_code": runtime_snapshot.machine_error_code or "UI_CHECK_ALL_RUNTIME_FAILED",
        "human_message": runtime_snapshot.human_message,
        "visual_state": runtime_snapshot.liveness,
    }


def build_quick_start_api_component(
    snapshot: ExternalModelsSnapshot,
    *,
    api_check_payload: dict[str, Any] | None = None,
    route_id: str = "",
) -> dict[str, str]:
    route_summary = describe_primary_external_route(snapshot)
    if snapshot.integration_error:
        return {
            "status": "failed",
            "machine_error_code": "UI_CHECK_ALL_API_UNAVAILABLE",
            "human_message": snapshot.integration_error,
            "route_id": route_id,
            "refresh_status": "failed",
        }
    if not str(route_summary["route_id"]):
        return {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_API_ROUTE_MISSING",
            "human_message": "Основной API route не подтверждён bounded snapshot.",
            "route_id": "",
            "refresh_status": "complete",
        }
    if route_summary["enabled"] is not True:
        return {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_API_ROUTE_DISABLED",
            "human_message": "Основной API route отключён; ready не подтверждается.",
            "route_id": str(route_summary["route_id"]),
            "refresh_status": "complete",
        }
    if str(route_summary["secret_status_label"]) == "missing":
        return {
            "status": "partial",
            "machine_error_code": "UI_CHECK_ALL_API_SECRET_REF_MISSING",
            "human_message": "Для основного API route отсутствует подтверждённый secret_ref.",
            "route_id": str(route_summary["route_id"]),
            "refresh_status": "complete",
        }
    if api_check_payload is None:
        validation_visual = str(route_summary["validation_visual_state"])
        if validation_visual == "green":
            status = "ok"
        elif validation_visual in {"blue", "amber", "neutral"}:
            status = "partial"
        else:
            status = "failed"
        return {
            "status": status,
            "machine_error_code": "OK" if status == "ok" else str(route_summary["status_code"]),
            "human_message": str(route_summary["note"]),
            "route_id": str(route_summary["route_id"]),
            "refresh_status": "complete",
        }
    if str(api_check_payload.get("status", "")) != "ok":
        return {
            "status": "failed",
            "machine_error_code": str(api_check_payload.get("machine_error_code", "UI_CHECK_ALL_API_CHECK_FAILED")),
            "human_message": str(api_check_payload.get("human_message", "Проверка API route завершилась ошибкой.")),
            "route_id": route_id,
            "refresh_status": "complete",
        }
    validation_visual = str(route_summary["validation_visual_state"])
    observed_status = "ok" if validation_visual in {"green", "blue"} else ("partial" if validation_visual == "amber" else "failed")
    return {
        "status": observed_status,
        "machine_error_code": "OK" if observed_status == "ok" else str(route_summary["status_code"]),
        "human_message": str(route_summary["note"]),
        "route_id": str(route_summary["route_id"]),
        "refresh_status": "complete",
    }


def build_quick_start_check_all_payload(
    *,
    runtime_snapshot: RuntimeSnapshot,
    account_snapshot: AccountPoolSnapshot,
    external_snapshot: ExternalModelsSnapshot,
    api_check_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    accounts_component = build_quick_start_account_component(account_snapshot)
    route_summary = describe_primary_external_route(external_snapshot)
    api_component = build_quick_start_api_component(
        external_snapshot,
        api_check_payload=api_check_payload,
        route_id=str(route_summary["route_id"]),
    )
    runtime_component = build_quick_start_runtime_component(runtime_snapshot)
    component_statuses = (
        accounts_component["status"],
        api_component["status"],
        runtime_component["status"],
    )
    if any(status == "failed" for status in component_statuses):
        bundle_verdict = "failed"
        bundle_status = "command_error"
        machine_error_code = "UI_CHECK_ALL_FAILED"
        human_message = "Одна или несколько bounded проверок завершились с blocking failure."
        next_action = "inspect_bundle"
    elif any(status == "partial" for status in component_statuses):
        bundle_verdict = "partial"
        bundle_status = "partial_success"
        machine_error_code = "UI_CHECK_ALL_PARTIAL"
        human_message = "Проверка завершилась частично: нужен следующий шаг по bounded truth surfaces."
        next_action = "review_follow_up"
    else:
        bundle_verdict = "ready"
        bundle_status = "ok"
        machine_error_code = "OK"
        human_message = "Все bounded truth surfaces подтверждены для Quick Start summary."
        next_action = "none"
    return {
        "status": bundle_status,
        "exit_code": 0 if bundle_status != "command_error" else 1,
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": [],
        "next_action": next_action,
        "data": {
            "bundle_verdict": bundle_verdict,
            "hidden_mutation_absent": True,
            "bundle": {
                "accounts": accounts_component,
                "api": api_component,
                "runtime": runtime_component,
            },
            "bundle_refresh_sources": [
                "accounts-list",
                "external-models-routes",
                "runtime-status",
            ],
            "api_check_packet": {
                "status": str(api_check_payload.get("status")) if api_check_payload is not None else "not_run",
                "machine_error_code": str(api_check_payload.get("machine_error_code")) if api_check_payload is not None else "NOT_RUN",
                "human_message": str(api_check_payload.get("human_message")) if api_check_payload is not None else "API verify action was not run.",
                "next_action": str(api_check_payload.get("next_action")) if api_check_payload is not None else "none",
            },
        },
    }


class MinimalCompanionShell:
    def __init__(self, root: Tk, runner: JsonCommandRunner) -> None:
        _require_tkinter()
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
        self.health_var = StringVar(value="unknown / ")
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
        self.account_capacity_var = StringVar(
            value=(
                f"{ACCOUNT_CAPACITY_TARGET} managed / "
                f"{DEFAULT_ACTIVE_WINDOW_TARGET} active default"
            )
        )
        self.account_integration_var = StringVar(value="")
        self.quick_start_source_var = StringVar(value="unknown")
        self.quick_start_account_status_var = StringVar(value="unknown")
        self.quick_start_account_note_var = StringVar(value="")
        self.quick_start_api_status_var = StringVar(value="unknown")
        self.quick_start_api_note_var = StringVar(value="")
        self.quick_start_route_label_var = StringVar(value="")
        self.quick_start_route_provider_var = StringVar(value="")
        self.quick_start_route_secret_ref_var = StringVar(value="")
        self.quick_start_route_last_checked_var = StringVar(value="")
        self.quick_start_route_validation_var = StringVar(value="")
        self.quick_start_onboard_reason_var = StringVar(value="")
        self.quick_start_api_reason_var = StringVar(value="")
        self.quick_start_check_all_reason_var = StringVar(value="")
        self.quick_start_check_all_status_var = StringVar(value="")
        self.quick_start_check_all_machine_error_var = StringVar(value="")
        self.quick_start_check_all_next_action_var = StringVar(value="")
        self.quick_start_check_all_verdict_var = StringVar(value="")
        self.quick_start_check_all_message_var = StringVar(value="")
        self.quick_start_events: list[QuickStartLedgerEntry] = []
        self._latest_external_action: ExternalActionResult | None = None
        self.external_foundation_phase_var = StringVar(value="unknown")
        self.external_adapter_state_var = StringVar(value="unknown")
        self.external_routes_count_var = StringVar(value="0")
        self.external_listener_var = StringVar(value="false")
        self.external_runtime_claim_var = StringVar(value="true")
        self.external_profile_ready_var = StringVar(value="false")
        self.external_integration_var = StringVar(value="")
        self.external_route_var = StringVar(value="")
        self.external_route_display_var = StringVar(value="")
        self.external_route_provider_var = StringVar(value="")
        self.external_route_secret_ref_var = StringVar(value="")
        self.external_route_enabled_var = StringVar(value="")
        self.external_profile_command_status_var = StringVar(value="")
        self.external_profile_command_exit_code_var = StringVar(value="")
        self.external_profile_command_human_message_var = StringVar(value="")
        self.external_profile_command_machine_error_var = StringVar(value="")
        self.external_profile_command_changed_files_var = StringVar(value="")
        self.external_profile_command_next_action_var = StringVar(value="")
        self.external_profile_rendered_state_var = StringVar(value="unknown")
        self.external_profile_field_vars = {
            field: StringVar(value="")
            for field in EXTERNAL_PROFILE_FIELDS
        }
        self._external_models_snapshot = ExternalModelsSnapshot.integration_failure(
            "Refresh required."
        )
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
        self.diagnostics_command_status_var = StringVar(value="")
        self.diagnostics_command_exit_code_var = StringVar(value="")
        self.diagnostics_command_human_message_var = StringVar(value="")
        self.diagnostics_command_machine_error_var = StringVar(value="")
        self.diagnostics_command_changed_files_var = StringVar(value="")
        self.diagnostics_command_next_action_var = StringVar(value="")
        self.diagnostics_field_vars = {
            field: StringVar(value="")
            for field in DIAGNOSTICS_RESULT_FIELDS
        }
        self.stable_repair_command_status_var = StringVar(value="")
        self.stable_repair_command_exit_code_var = StringVar(value="")
        self.stable_repair_command_human_message_var = StringVar(value="")
        self.stable_repair_command_machine_error_var = StringVar(value="")
        self.stable_repair_command_changed_files_var = StringVar(value="")
        self.stable_repair_command_next_action_var = StringVar(value="")

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

        quick_start_box = ttk.LabelFrame(container, text="Quick Start", padding=12)
        quick_start_box.pack(fill="x", pady=(0, 16))
        self._add_status_row(quick_start_box, "Source", self.quick_start_source_var)
        self._add_status_row(quick_start_box, "Account", self.quick_start_account_status_var)
        self._add_status_row(quick_start_box, "Account note", self.quick_start_account_note_var)
        self._add_status_row(quick_start_box, "API", self.quick_start_api_status_var)
        self._add_status_row(quick_start_box, "API note", self.quick_start_api_note_var)
        self._add_status_row(quick_start_box, "Route label", self.quick_start_route_label_var)
        self._add_status_row(quick_start_box, "Provider", self.quick_start_route_provider_var)
        self._add_status_row(quick_start_box, "Secret ref", self.quick_start_route_secret_ref_var)
        self._add_status_row(quick_start_box, "Validation", self.quick_start_route_validation_var)
        self._add_status_row(quick_start_box, "Last checked", self.quick_start_route_last_checked_var)

        quick_start_actions = ttk.Frame(quick_start_box)
        quick_start_actions.pack(fill="x", pady=(8, 0))
        self.quick_start_onboard_button = ttk.Button(
            quick_start_actions,
            text="Connect Account",
            command=self.run_onboard_action,
        )
        self.quick_start_onboard_button.pack(side="left")
        self.quick_start_api_button = ttk.Button(
            quick_start_actions,
            text="Check API",
            command=self.run_external_check_action,
        )
        self.quick_start_api_button.pack(side="left", padx=(8, 0))
        self.quick_start_check_all_button = ttk.Button(
            quick_start_actions,
            text="Check All",
            command=self.run_quick_start_check_all_action,
        )
        self.quick_start_check_all_button.pack(side="left", padx=(8, 0))
        ttk.Button(
            quick_start_actions,
            text="Refresh Ledger",
            command=self.refresh,
        ).pack(side="left", padx=(8, 0))

        self._add_status_row(quick_start_box, "Connect reason", self.quick_start_onboard_reason_var)
        self._add_status_row(quick_start_box, "API reason", self.quick_start_api_reason_var)
        self._add_status_row(quick_start_box, "Check-all reason", self.quick_start_check_all_reason_var)
        self._add_status_row(
            quick_start_box,
            "Bundle status",
            self.quick_start_check_all_status_var,
        )
        self._add_status_row(
            quick_start_box,
            "Bundle verdict",
            self.quick_start_check_all_verdict_var,
        )
        self._add_status_row(
            quick_start_box,
            "Bundle machine error",
            self.quick_start_check_all_machine_error_var,
        )
        self._add_status_row(
            quick_start_box,
            "Bundle next action",
            self.quick_start_check_all_next_action_var,
        )
        self._add_status_row(
            quick_start_box,
            "Bundle message",
            self.quick_start_check_all_message_var,
        )

        ledger_box = ttk.LabelFrame(container, text="Action Ledger", padding=12)
        ledger_box.pack(fill="both", expand=False, pady=(0, 16))
        ledger_columns = ("observed_at", "action", "status", "machine_error", "next_action")
        self.quick_start_ledger_tree = ttk.Treeview(
            ledger_box,
            columns=ledger_columns,
            show="headings",
            height=5,
        )
        for column, heading, width in (
            ("observed_at", "Observed", 180),
            ("action", "Action", 180),
            ("status", "Status", 120),
            ("machine_error", "Machine error", 180),
            ("next_action", "Next action", 180),
        ):
            self.quick_start_ledger_tree.heading(column, text=heading)
            self.quick_start_ledger_tree.column(column, width=width, anchor="w")
        self.quick_start_ledger_tree.pack(fill="x", expand=False)

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
        self._add_status_row(status_box, "Health", self.health_var)
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
        ttk.Button(
            controls_box,
            text="Run Stable Repair",
            command=self.run_stable_repair_action,
        ).pack(fill="x", pady=4)
        ttk.Button(
            controls_box,
            text="Export Diagnostics",
            command=self.run_diagnostics_action,
        ).pack(fill="x", pady=4)
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

        diagnostics_box = ttk.LabelFrame(controls_box, text="Diagnostics Export", padding=8)
        diagnostics_box.pack(fill="x", pady=(8, 0))
        self._add_status_row(
            diagnostics_box,
            "Command status",
            self.diagnostics_command_status_var,
        )
        self._add_status_row(
            diagnostics_box,
            "Exit code",
            self.diagnostics_command_exit_code_var,
        )
        self._add_status_row(
            diagnostics_box,
            "Human message",
            self.diagnostics_command_human_message_var,
        )
        self._add_status_row(
            diagnostics_box,
            "Machine error",
            self.diagnostics_command_machine_error_var,
        )
        self._add_status_row(
            diagnostics_box,
            "Changed files",
            self.diagnostics_command_changed_files_var,
        )
        self._add_status_row(
            diagnostics_box,
            "Next action",
            self.diagnostics_command_next_action_var,
        )
        self._add_status_row(
            diagnostics_box,
            "Bundle path",
            self.diagnostics_field_vars["bundle_path"],
        )

        stable_repair_box = ttk.LabelFrame(controls_box, text="Stable Repair", padding=8)
        stable_repair_box.pack(fill="x", pady=(8, 0))
        self._add_status_row(
            stable_repair_box,
            "Command status",
            self.stable_repair_command_status_var,
        )
        self._add_status_row(
            stable_repair_box,
            "Exit code",
            self.stable_repair_command_exit_code_var,
        )
        self._add_status_row(
            stable_repair_box,
            "Human message",
            self.stable_repair_command_human_message_var,
        )
        self._add_status_row(
            stable_repair_box,
            "Machine error",
            self.stable_repair_command_machine_error_var,
        )
        self._add_status_row(
            stable_repair_box,
            "Changed files",
            self.stable_repair_command_changed_files_var,
        )
        self._add_status_row(
            stable_repair_box,
            "Next action",
            self.stable_repair_command_next_action_var,
        )

        external_box = ttk.LabelFrame(container, text="Desktop Bridge Admission", padding=12)
        external_box.pack(fill="x", pady=(16, 0))
        external_summary = ttk.Frame(external_box)
        external_summary.pack(fill="x")
        self._add_status_row(
            external_summary, "Foundation phase", self.external_foundation_phase_var
        )
        self._add_status_row(
            external_summary, "Adapter state", self.external_adapter_state_var
        )
        self._add_status_row(
            external_summary, "Routes count", self.external_routes_count_var
        )
        self._add_status_row(
            external_summary, "Listener proven", self.external_listener_var
        )
        self._add_status_row(
            external_summary, "Runtime claim blocked", self.external_runtime_claim_var
        )
        self._add_status_row(
            external_summary, "Profile ready", self.external_profile_ready_var
        )
        self._add_status_row(
            external_summary, "Integration", self.external_integration_var
        )

        external_route_row = ttk.Frame(external_box)
        external_route_row.pack(fill="x", pady=(8, 0))
        ttk.Label(external_route_row, text="Route:", width=16).pack(side="left")
        self.external_route_combo = ttk.Combobox(
            external_route_row,
            textvariable=self.external_route_var,
            state="readonly",
        )
        self.external_route_combo.pack(side="left", fill="x", expand=True)
        self.external_route_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._sync_external_route_summary(),
        )
        ttk.Button(
            external_route_row,
            text="Profile Codex Desktop",
            command=self.run_external_profile_action,
        ).pack(side="left", padx=(8, 0))
        self._add_status_row(external_box, "Route label", self.external_route_display_var)
        self._add_status_row(external_box, "Provider", self.external_route_provider_var)
        self._add_status_row(external_box, "Secret ref", self.external_route_secret_ref_var)
        self._add_status_row(external_box, "Enabled", self.external_route_enabled_var)
        self._add_status_row(
            external_box, "Rendered state", self.external_profile_rendered_state_var
        )
        self._add_status_row(
            external_box, "Command status", self.external_profile_command_status_var
        )
        self._add_status_row(
            external_box, "Exit code", self.external_profile_command_exit_code_var
        )
        self._add_status_row(
            external_box, "Human message", self.external_profile_command_human_message_var
        )
        self._add_status_row(
            external_box, "Machine error", self.external_profile_command_machine_error_var
        )
        self._add_status_row(
            external_box, "Changed files", self.external_profile_command_changed_files_var
        )
        self._add_status_row(
            external_box, "Next action", self.external_profile_command_next_action_var
        )
        for label, field in (
            ("Profile kind", "profile_kind"),
            ("Route ID", "route_id"),
            ("Base URL", "base_url"),
            ("Model", "model"),
            ("API key source", "api_key_source"),
            ("Writes config", "writes_external_config"),
            ("Profile ready", "profile_ready"),
            ("Listener proven", "listener_proven"),
            ("Runtime claim blocked", "runtime_claim_blocked"),
            ("Synthetic contract", "synthetic_endpoint_contract"),
            ("Prerequisite", "prerequisite"),
        ):
            self._add_status_row(external_box, label, self.external_profile_field_vars[field])

        onboarding_box = ttk.LabelFrame(container, text="Account Connect Evidence", padding=12)
        onboarding_box.pack(fill="x", pady=(16, 0))

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
            ("Auth snapshot status", "auth_snapshot_before_login_status"),
            ("Auth snapshot count", "auth_snapshot_before_login_count"),
            ("Auth snapshot digest", "auth_snapshot_before_login_digest"),
            ("Auth snapshot source", "auth_snapshot_before_login_source"),
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
        self._add_status_row(account_summary, "Managed contour", self.account_capacity_var)
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
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
        try:
            account_snapshot = load_account_pool_snapshot(self.runner)
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
        if not runtime_snapshot.integration_error and not account_snapshot.integration_error:
            try:
                ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
            except UiShellError as exc:
                runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
                account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
        try:
            external_snapshot = load_external_models_snapshot(self.runner)
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            external_snapshot = ExternalModelsSnapshot.integration_failure(str(exc))
        self.root.after(
            0,
            lambda: self._apply_refresh_results(
                runtime_snapshot,
                account_snapshot,
                external_snapshot=external_snapshot,
            ),
        )

    def _apply_runtime_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        self._last_runtime_snapshot = snapshot
        self.state_var.set(snapshot.overall_state)
        self.exit_code_var.set(str(snapshot.exit_code))
        self.next_action_var.set(snapshot.next_action)
        self.desired_mode_var.set(snapshot.desired_mode)
        self.effective_mode_var.set(snapshot.effective_mode)
        self.endpoint_var.set(snapshot.endpoint)
        self.current_proxy_var.set(snapshot.current_proxy_url)
        self.health_var.set(
            f"{snapshot.liveness} / {snapshot.machine_error_code}"
        )
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
        self._last_account_snapshot = snapshot
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
        self.account_capacity_var.set(
            f"{snapshot.capacity_target} managed / "
            f"{DEFAULT_ACTIVE_WINDOW_TARGET} active default"
        )
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

    def _apply_external_models_snapshot(self, snapshot: ExternalModelsSnapshot) -> None:
        self._external_models_snapshot = snapshot
        self.external_foundation_phase_var.set(snapshot.foundation_phase)
        self.external_adapter_state_var.set(snapshot.adapter_state)
        self.external_routes_count_var.set(str(snapshot.routes_count))
        self.external_listener_var.set("true" if snapshot.listener_proven else "false")
        self.external_runtime_claim_var.set(
            "true" if snapshot.runtime_claim_blocked else "false"
        )
        self.external_profile_ready_var.set("true" if snapshot.profile_ready else "false")
        self.external_integration_var.set(snapshot.integration_error)
        route_ids = [route.route_id for route in snapshot.routes]
        self.external_route_combo["values"] = route_ids
        selected_route = self.external_route_var.get().strip()
        if selected_route not in route_ids:
            self.external_route_var.set(route_ids[0] if route_ids else "")
        self._sync_external_route_summary()
        self._apply_quick_start_summary()

    def _sync_external_route_summary(self) -> None:
        selected_route = self.external_route_var.get().strip()
        route = next(
            (item for item in self._external_models_snapshot.routes if item.route_id == selected_route),
            None,
        )
        if route is None:
            self.external_route_display_var.set("")
            self.external_route_provider_var.set("")
            self.external_route_secret_ref_var.set("")
            self.external_route_enabled_var.set("")
            return
        self.external_route_display_var.set(route.display_name)
        self.external_route_provider_var.set(route.provider)
        self.external_route_secret_ref_var.set(route.secret_ref)
        self.external_route_enabled_var.set("true" if route.enabled else "false")

    def _apply_quick_start_summary(self) -> None:
        self.quick_start_source_var.set("live_sandbox")
        account_snapshot = getattr(
            self,
            "_last_account_snapshot",
            AccountPoolSnapshot.integration_failure("Refresh required."),
        )
        account_component = build_quick_start_account_component(account_snapshot)
        self.quick_start_account_status_var.set(account_component["status"])
        self.quick_start_account_note_var.set(account_component["human_message"])

        route_summary = describe_primary_external_route(self._external_models_snapshot)
        self.quick_start_api_status_var.set(str(route_summary["status_code"]))
        self.quick_start_api_note_var.set(str(route_summary["note"]))
        self.quick_start_route_label_var.set(str(route_summary["display_name"]))
        self.quick_start_route_provider_var.set(str(route_summary["provider"]))
        self.quick_start_route_secret_ref_var.set(str(route_summary["secret_ref"]))
        self.quick_start_route_last_checked_var.set(str(route_summary["last_checked"]))
        self.quick_start_route_validation_var.set(str(route_summary["validation_label"]))

        self.quick_start_onboard_reason_var.set("" if not self._busy else "busy")
        api_reason = ""
        if not str(route_summary["route_id"]):
            api_reason = "main route missing"
        elif route_summary["enabled"] is not True:
            api_reason = "route disabled"
        elif str(route_summary["secret_status_label"]) == "missing":
            api_reason = "secret_ref missing"
        self.quick_start_api_reason_var.set(api_reason if not self._busy else "busy")
        self.quick_start_check_all_reason_var.set("" if not self._busy else "busy")

    def _record_quick_start_ledger_entry(
        self,
        action_id: str,
        payload: dict[str, Any],
    ) -> None:
        entry = QuickStartLedgerEntry(
            observed_at_utc=datetime.now(timezone.utc).isoformat(),
            action_id=action_id,
            status=str(payload.get("status", "")),
            machine_error_code=str(payload.get("machine_error_code", "")),
            next_action=str(payload.get("next_action", "")),
            human_message=str(payload.get("human_message", "")),
        )
        self.quick_start_events.insert(0, entry)
        self.quick_start_events = self.quick_start_events[:12]
        for item in self.quick_start_ledger_tree.get_children():
            self.quick_start_ledger_tree.delete(item)
        for index, event in enumerate(self.quick_start_events):
            self.quick_start_ledger_tree.insert(
                "",
                "end",
                iid=f"quick-start-ledger-{index}",
                values=(
                    event.observed_at_utc,
                    event.action_id,
                    event.status,
                    event.machine_error_code,
                    event.next_action,
                ),
            )

    def _apply_refresh_results(
        self,
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        *,
        banner: str | None = None,
        external_snapshot: ExternalModelsSnapshot | None = None,
    ) -> None:
        self._apply_runtime_snapshot(runtime_snapshot)
        self._apply_account_snapshot(account_snapshot)
        if external_snapshot is not None:
            self._apply_external_models_snapshot(external_snapshot)
        self.banner_var.set(banner or runtime_snapshot.human_message)
        self.set_busy(False)
        self._apply_quick_start_summary()

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

    def run_external_profile_action(self) -> None:
        if self._busy:
            return
        route_id = self.external_route_var.get().strip()
        if not route_id:
            messagebox.showinfo(
                "Route required",
                "Refresh route truth and select a route before generating the desktop profile.",
                parent=self.root,
            )
            return
        if route_id not in {route.route_id for route in self._external_models_snapshot.routes}:
            messagebox.showinfo(
                "Route unavailable",
                "Refresh route truth before generating the desktop profile packet.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Generate bounded Codex Desktop profile packet and refresh external-models truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Generating desktop profile packet...")
        threading.Thread(
            target=self._external_profile_worker,
            args=(route_id,),
            daemon=True,
        ).start()

    def run_external_check_action(self) -> None:
        if self._busy:
            return
        route_summary = describe_primary_external_route(self._external_models_snapshot)
        route_id = str(route_summary["route_id"])
        if not route_id:
            messagebox.showinfo(
                "Route required",
                "Refresh route truth before running the bounded API check.",
                parent=self.root,
            )
            return
        if route_summary["enabled"] is not True:
            messagebox.showinfo(
                "Route disabled",
                "Основной API route отключён; bounded API check недоступен.",
                parent=self.root,
            )
            return
        if str(route_summary["secret_status_label"]) == "missing":
            messagebox.showinfo(
                "Secret missing",
                "Для основного API route не подтверждён secret_ref.",
                parent=self.root,
            )
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run bounded API check and refresh external-models truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running API check...")
        threading.Thread(
            target=self._external_check_worker,
            args=(route_id,),
            daemon=True,
        ).start()

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

    def run_diagnostics_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Export redacted diagnostics bundle and refresh command truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running diagnostics export...")
        threading.Thread(target=self._diagnostics_worker, daemon=True).start()

    def run_stable_repair_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run stable repair and refresh command truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running stable repair...")
        threading.Thread(target=self._stable_repair_worker, daemon=True).start()

    def run_onboard_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run reserve-first account onboarding and refresh command truth?",
            parent=self.root,
        ):
            return
        command = ["accounts", "onboard", "--json"]
        self.set_busy(True)
        self.banner_var.set("Running onboarding...")
        threading.Thread(
            target=self._onboard_worker,
            args=(tuple(command),),
            daemon=True,
        ).start()

    def run_quick_start_check_all_action(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Confirm action",
            "Run bounded Quick Start check-all bundle and refresh command truth?",
            parent=self.root,
        ):
            return
        self.set_busy(True)
        self.banner_var.set("Running Quick Start check-all...")
        threading.Thread(
            target=self._quick_start_check_all_worker,
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
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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

    def _external_profile_worker(self, route_id: str) -> None:
        try:
            action_payload, external_snapshot = run_external_profile_and_refresh(
                self.runner, route_id
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
                "data": {},
            }
            external_snapshot = ExternalModelsSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_external_profile_results(
                action_payload,
                external_snapshot,
                banner=banner,
            ),
        )

    def _external_check_worker(self, route_id: str) -> None:
        try:
            action_payload, external_snapshot = run_external_check_and_refresh(
                self.runner, route_id
            )
            runtime_snapshot = load_runtime_snapshot(self.runner)
            account_snapshot = load_account_pool_snapshot(self.runner)
            ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
            banner = str(action_payload["human_message"])
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
                "data": {},
            }
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            external_snapshot = ExternalModelsSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_external_check_results(
                action_payload,
                runtime_snapshot,
                account_snapshot,
                external_snapshot,
                banner=banner,
            ),
        )

    def _quick_start_check_all_worker(self) -> None:
        api_check_payload: dict[str, Any] | None = None
        try:
            runtime_snapshot = load_runtime_snapshot(self.runner)
            account_snapshot = load_account_pool_snapshot(self.runner)
            ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
            external_snapshot = load_external_models_snapshot(self.runner)
            route_summary = describe_primary_external_route(external_snapshot)
            if (
                str(route_summary["route_id"])
                and route_summary["enabled"] is True
                and str(route_summary["secret_status_label"]) != "missing"
            ):
                api_check_payload, external_snapshot = run_external_check_and_refresh(
                    self.runner,
                    str(route_summary["route_id"]),
                )
            bundle_payload = build_quick_start_check_all_payload(
                runtime_snapshot=runtime_snapshot,
                account_snapshot=account_snapshot,
                external_snapshot=external_snapshot,
                api_check_payload=api_check_payload,
            )
            banner = str(bundle_payload["human_message"])
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            external_snapshot = ExternalModelsSnapshot.integration_failure(str(exc))
            bundle_payload = {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
                "data": {
                    "bundle_verdict": "failed",
                    "hidden_mutation_absent": True,
                    "bundle": {
                        "accounts": {"status": "failed", "machine_error_code": "UI_INTEGRATION_FAILURE", "human_message": str(exc)},
                        "api": {"status": "failed", "machine_error_code": "UI_INTEGRATION_FAILURE", "human_message": str(exc)},
                        "runtime": {"status": "failed", "machine_error_code": "UI_INTEGRATION_FAILURE", "human_message": str(exc)},
                    },
                    "bundle_refresh_sources": [],
                    "api_check_packet": {
                        "status": "not_run",
                        "machine_error_code": "NOT_RUN",
                        "human_message": "API verify action was not run.",
                        "next_action": "retry",
                    },
                },
            }
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_quick_start_check_all_results(
                bundle_payload,
                runtime_snapshot,
                account_snapshot,
                external_snapshot,
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
            except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
                runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
                banner = "Operator action failed."
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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

    def _diagnostics_worker(self) -> None:
        try:
            action_payload, runtime_snapshot, account_snapshot = (
                run_diagnostics_export_and_refresh(self.runner)
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
            }
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_diagnostics_results(
                action_payload,
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _stable_repair_worker(self) -> None:
        try:
            action_payload, runtime_snapshot, account_snapshot = (
                run_stable_repair_and_refresh(self.runner)
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
            action_payload = {
                "status": "integration_failure",
                "exit_code": 1,
                "human_message": "UI integration failure.",
                "machine_error_code": "UI_INTEGRATION_FAILURE",
                "changed_files": [],
                "next_action": "retry",
            }
            runtime_snapshot = RuntimeSnapshot.integration_failure(str(exc))
            account_snapshot = AccountPoolSnapshot.integration_failure(str(exc))
            banner = "Operator action failed."

        self.root.after(
            0,
            lambda: self._apply_stable_repair_results(
                action_payload,
                runtime_snapshot,
                account_snapshot,
                banner=banner,
            ),
        )

    def _account_check_worker(self, backend_id: str) -> None:
        try:
            action_payload, account_snapshot = run_account_validate_and_refresh(
                self.runner, backend_id
            )
            banner = str(action_payload["human_message"])
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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

    def _apply_external_profile_payload(self, action_payload: dict[str, Any]) -> None:
        self.external_profile_command_status_var.set(str(action_payload.get("status", "")))
        self.external_profile_command_exit_code_var.set(str(action_payload.get("exit_code", "")))
        self.external_profile_command_human_message_var.set(
            str(action_payload.get("human_message", ""))
        )
        self.external_profile_command_machine_error_var.set(
            str(action_payload.get("machine_error_code", ""))
        )
        self.external_profile_command_next_action_var.set(
            str(action_payload.get("next_action", ""))
        )
        changed_files_value = action_payload.get("changed_files")
        if changed_files_value is None:
            self.external_profile_command_changed_files_var.set("")
        else:
            self.external_profile_command_changed_files_var.set(
                format_onboarding_value(changed_files_value)
            )
        malformed_surface = False
        try:
            field_values = build_external_profile_field_values(action_payload)
        except UiShellError:
            field_values = {field: "" for field in EXTERNAL_PROFILE_FIELDS}
            malformed_surface = True
        for field, value in field_values.items():
            self.external_profile_field_vars[field].set(value)
        rendered_state = classify_external_profile_rendered_state(
            action_payload,
            field_values,
            malformed=malformed_surface,
        )
        self.external_profile_rendered_state_var.set(rendered_state)

    def _apply_external_profile_results(
        self,
        action_payload: dict[str, Any],
        external_snapshot: ExternalModelsSnapshot,
        *,
        banner: str,
    ) -> None:
        self._record_quick_start_ledger_entry("external_profile", action_payload)
        self._apply_external_profile_payload(action_payload)
        self._apply_external_models_snapshot(external_snapshot)
        self.banner_var.set(banner)
        self.set_busy(False)

    def _apply_external_check_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        external_snapshot: ExternalModelsSnapshot,
        *,
        banner: str,
    ) -> None:
        self._latest_external_action = build_external_action_result(
            action="external_check",
            action_payload=action_payload,
        ) if action_payload.get("status") != "integration_failure" else None
        self._record_quick_start_ledger_entry("api_route_check", action_payload)
        self._apply_refresh_results(
            runtime_snapshot,
            account_snapshot,
            banner=banner,
            external_snapshot=external_snapshot,
        )

    def _apply_quick_start_check_all_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        external_snapshot: ExternalModelsSnapshot,
        *,
        banner: str,
    ) -> None:
        data = action_payload.get("data")
        if not isinstance(data, dict):
            data = {}
        self.quick_start_check_all_status_var.set(str(action_payload.get("status", "")))
        self.quick_start_check_all_machine_error_var.set(
            str(action_payload.get("machine_error_code", ""))
        )
        self.quick_start_check_all_next_action_var.set(
            str(action_payload.get("next_action", ""))
        )
        self.quick_start_check_all_verdict_var.set(str(data.get("bundle_verdict", "")))
        self.quick_start_check_all_message_var.set(str(action_payload.get("human_message", "")))
        self._record_quick_start_ledger_entry("quick_start_check_all", action_payload)
        self._apply_refresh_results(
            runtime_snapshot,
            account_snapshot,
            banner=banner,
            external_snapshot=external_snapshot,
        )

    def _apply_diagnostics_payload(self, action_payload: dict[str, Any]) -> None:
        self.diagnostics_command_status_var.set(str(action_payload.get("status", "")))
        self.diagnostics_command_exit_code_var.set(str(action_payload.get("exit_code", "")))
        self.diagnostics_command_human_message_var.set(
            str(action_payload.get("human_message", ""))
        )
        self.diagnostics_command_machine_error_var.set(
            str(action_payload.get("machine_error_code", ""))
        )
        self.diagnostics_command_next_action_var.set(str(action_payload.get("next_action", "")))
        changed_files_value = action_payload.get("changed_files")
        if changed_files_value is None:
            self.diagnostics_command_changed_files_var.set("")
        else:
            self.diagnostics_command_changed_files_var.set(
                format_onboarding_value(changed_files_value)
            )
        field_values = build_diagnostics_field_values(action_payload)
        for field, value in field_values.items():
            self.diagnostics_field_vars[field].set(value)

    def _apply_diagnostics_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        *,
        banner: str,
    ) -> None:
        self._apply_diagnostics_payload(action_payload)
        self._apply_refresh_results(runtime_snapshot, account_snapshot, banner=banner)

    def _apply_stable_repair_payload(self, action_payload: dict[str, Any]) -> None:
        self.stable_repair_command_status_var.set(str(action_payload.get("status", "")))
        self.stable_repair_command_exit_code_var.set(str(action_payload.get("exit_code", "")))
        self.stable_repair_command_human_message_var.set(
            str(action_payload.get("human_message", ""))
        )
        self.stable_repair_command_machine_error_var.set(
            str(action_payload.get("machine_error_code", ""))
        )
        self.stable_repair_command_next_action_var.set(
            str(action_payload.get("next_action", ""))
        )
        changed_files_value = action_payload.get("changed_files")
        if changed_files_value is None:
            self.stable_repair_command_changed_files_var.set("")
        else:
            self.stable_repair_command_changed_files_var.set(
                format_onboarding_value(changed_files_value)
            )

    def _apply_stable_repair_results(
        self,
        action_payload: dict[str, Any],
        runtime_snapshot: RuntimeSnapshot,
        account_snapshot: AccountPoolSnapshot,
        *,
        banner: str,
    ) -> None:
        self._apply_stable_repair_payload(action_payload)
        self._apply_refresh_results(runtime_snapshot, account_snapshot, banner=banner)

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
        except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
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
        self._record_quick_start_ledger_entry("onboard_account", action_payload)
        self._apply_onboarding_payload(action_payload)
        self._apply_refresh_results(runtime_snapshot, account_snapshot, banner=banner)


def run_packaged_continuity_smoke_json() -> tuple[dict[str, Any], int]:
    root: Tk | None = None
    try:
        _require_tkinter_root()
        root = Tk()
        root.withdraw()
        runner = JsonCommandRunner()
        shell = MinimalCompanionShell(root, runner)
        runtime_snapshot = load_runtime_snapshot(runner, live_probe=True)
        account_snapshot = load_account_pool_snapshot(runner)
        ensure_capacity_data_consistency(runtime_snapshot, account_snapshot)
        external_snapshot = load_external_models_snapshot(runner)
        shell._apply_refresh_results(
            runtime_snapshot,
            account_snapshot,
            banner=runtime_snapshot.human_message,
            external_snapshot=external_snapshot,
        )
        route_summary = describe_primary_external_route(external_snapshot)
        bundle_payload = build_quick_start_check_all_payload(
            runtime_snapshot=runtime_snapshot,
            account_snapshot=account_snapshot,
            external_snapshot=external_snapshot,
            api_check_payload=None,
        )
        shell._apply_quick_start_check_all_results(
            bundle_payload,
            runtime_snapshot,
            account_snapshot,
            external_snapshot,
            banner=str(bundle_payload["human_message"]),
        )
        data = bundle_payload.get("data")
        if not isinstance(data, dict):
            data = {}
        bundle = data.get("bundle")
        if not isinstance(bundle, dict):
            bundle = {}
        result = {
            "status": "ok",
            "machine_error_code": str(bundle_payload.get("machine_error_code", "OK")),
            "human_message": str(bundle_payload.get("human_message", "")),
            "desktop_surface": "admitted_tk_shell_packaged",
            "continuity": {
                "packaged_launch": True,
                "quick_start_opened": shell.quick_start_source_var.get() == "live_sandbox",
                "account_truth_loaded": bool(shell.quick_start_account_status_var.get()),
                "api_truth_loaded": bool(shell.quick_start_api_status_var.get()),
                "check_all_ran": bool(shell.quick_start_check_all_status_var.get()),
                "ledger_opened": hasattr(shell, "quick_start_ledger_tree"),
            },
            "quick_start_summary": {
                "source": shell.quick_start_source_var.get(),
                "account_status": shell.quick_start_account_status_var.get(),
                "account_note": shell.quick_start_account_note_var.get(),
                "api_status": shell.quick_start_api_status_var.get(),
                "api_note": shell.quick_start_api_note_var.get(),
                "route_label": shell.quick_start_route_label_var.get(),
                "route_provider": shell.quick_start_route_provider_var.get(),
                "route_secret_ref": shell.quick_start_route_secret_ref_var.get(),
                "route_validation": shell.quick_start_route_validation_var.get(),
                "route_last_checked": shell.quick_start_route_last_checked_var.get(),
                "runtime_liveness": shell.liveness_var.get(),
                "bundle_status": shell.quick_start_check_all_status_var.get(),
                "bundle_verdict": shell.quick_start_check_all_verdict_var.get(),
                "bundle_machine_error": shell.quick_start_check_all_machine_error_var.get(),
                "bundle_next_action": shell.quick_start_check_all_next_action_var.get(),
                "bundle_message": shell.quick_start_check_all_message_var.get(),
            },
            "bundle_components": bundle,
            "ledger": [
                {
                    "action_id": entry.action_id,
                    "status": entry.status,
                    "machine_error_code": entry.machine_error_code,
                    "next_action": entry.next_action,
                    "human_message": entry.human_message,
                }
                for entry in shell.quick_start_events
            ],
            "direct_packets": {
                "status": {
                    "status": runtime_snapshot.overall_state,
                    "machine_error_code": runtime_snapshot.machine_error_code,
                    "liveness": runtime_snapshot.liveness,
                },
                "accounts": {
                    "status": account_snapshot.registry_identity_status,
                    "machine_error_code": account_snapshot.registry_identity_machine_error_code,
                    "account_count": len(account_snapshot.accounts),
                },
                "api": {
                    "routes_count": external_snapshot.routes_count,
                    "local_token_present": external_snapshot.local_token_present,
                    "route_id": str(route_summary["route_id"]),
                },
            },
        }
        required_steps = result["continuity"]
        required_truth = {
            "source_live": result["quick_start_summary"]["source"] == "live_sandbox",
            "account_ok": result["quick_start_summary"]["account_status"] == "ok",
            "api_enabled": result["quick_start_summary"]["api_status"] == "enabled",
            "route_ready": result["quick_start_summary"]["route_validation"] == "ok",
            "route_secret_ref_present": bool(result["quick_start_summary"]["route_secret_ref"]),
            "runtime_healthy": result["quick_start_summary"]["runtime_liveness"] == "healthy",
            "bundle_ok": result["quick_start_summary"]["bundle_status"] == "ok",
            "bundle_ready": result["quick_start_summary"]["bundle_verdict"] == "ready",
            "bundle_machine_error_ok": result["quick_start_summary"]["bundle_machine_error"] == "OK",
            "bundle_next_action_none": result["quick_start_summary"]["bundle_next_action"] == "none",
            "bundle_components_ok": all(
                isinstance(component, dict) and str(component.get("status")) == "ok"
                for component in bundle.values()
            ),
            "ledger_has_check_all": any(
                entry["action_id"] == "quick_start_check_all"
                for entry in result["ledger"]
            ),
        }
        if not all(bool(required_steps[key]) for key in required_steps) or not all(
            required_truth.values()
        ):
            result["status"] = "error"
            result["machine_error_code"] = "PACKAGED_CONTINUITY_INCOMPLETE"
            result["human_message"] = (
                "Packaged continuity smoke did not complete every required baseline step."
            )
            result["failed_checks"] = sorted(
                key for key, value in {**required_steps, **required_truth}.items() if not value
            )
            return result, 1
        return result, 0
    except (UiShellError, SubprocessError, OSError, json.JSONDecodeError) as exc:
        return (
            {
                "status": "error",
                "machine_error_code": "PACKAGED_CONTINUITY_SMOKE_FAILED",
                "human_message": str(exc),
                "desktop_surface": "admitted_tk_shell_packaged",
            },
            1,
        )
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--smoke-packaged-continuity-json"]:
        payload, exit_code = run_packaged_continuity_smoke_json()
        sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
        return exit_code
    _require_tkinter_root()
    root = Tk()
    runner = JsonCommandRunner()
    MinimalCompanionShell(root, runner)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
