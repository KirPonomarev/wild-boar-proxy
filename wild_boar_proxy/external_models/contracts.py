"""Contracts for the external-models C2 synthetic lifecycle slice."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import unicodedata
from typing import Any

from wild_boar_proxy.command_effects import validate_effect
from wild_boar_proxy.core import packets as command_packets
from wild_boar_proxy.runtime import build_command_payload

ROUTE_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 2
EVIDENCE_SCHEMA_VERSION = 1
ROUTE_ID_PATTERN = re.compile(r"^wbp-[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

ROUTES_TOP_LEVEL_FIELDS = frozenset({"schema_version", "routes"})
ROUTE_ALLOWED_FIELDS = frozenset(
    {
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
        "transform_profile",
        "response_profile",
        "thinking",
        "check_max_tokens",
    }
)
ROUTE_REQUIRED_FIELDS = frozenset(
    {
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
    }
)

STATE_TOP_LEVEL_FIELDS = frozenset(
    {"schema_version", "policy", "adapter", "local_auth", "routes"}
)
STATE_POLICY_FIELDS = frozenset(
    {"paid_routes_enabled", "paid_route_allowlist", "paid_route_default"}
)
STATE_ADAPTER_FIELDS = frozenset(
    {
        "lifecycle_mode",
        "state",
        "host",
        "port",
        "base_url",
        "listener_proven",
        "runtime_claim_blocked",
        "started_at_utc",
        "last_transition",
    }
)
STATE_LOCAL_AUTH_FIELDS = frozenset(
    {"token_ref", "token_present", "token_created_at_utc"}
)
OBSERVED_ROUTE_ALLOWED_FIELDS = frozenset(
    {
        "availability_state",
        "bridge_green_counts_as_provider_proof",
        "bridge_live_response_observed",
        "direct_provider_error",
        "evidence_level",
        "last_verified_at",
        "last_validate",
        "last_check",
        "last_error",
        "latency_ms",
        "fallback_used",
        "effective_model",
    }
)


def sanitize_observed_routes(routes_payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(routes_payload, dict):
        return {}
    sanitized: dict[str, dict[str, Any]] = {}
    for route_id, route_state in routes_payload.items():
        if not isinstance(route_id, str) or not route_id.strip():
            continue
        if not isinstance(route_state, dict):
            continue
        bounded = {
            field: route_state[field]
            for field in OBSERVED_ROUTE_ALLOWED_FIELDS
            if field in route_state
        }
        if bounded:
            sanitized[route_id] = bounded
    return sanitized


def route_id_validation_error(route_id: object) -> str | None:
    if not isinstance(route_id, str):
        return "route_id is required."
    if unicodedata.normalize("NFKC", route_id) != route_id:
        return "route_id must use canonical ASCII characters."
    if ".." in route_id:
        return "route_id must not contain parent-directory markers."
    if not ROUTE_ID_PATTERN.fullmatch(route_id):
        return "route_id must match ^wbp-[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$."
    return None


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def default_state_payload() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "policy": {
            "paid_routes_enabled": False,
            "paid_route_allowlist": [],
            "paid_route_default": "blocked",
        },
        "adapter": {
            "lifecycle_mode": "synthetic",
            "state": "stopped",
            "host": "127.0.0.1",
            "port": None,
            "base_url": None,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "started_at_utc": None,
            "last_transition": "init",
        },
        "local_auth": {
            "token_ref": "managed_local_token",
            "token_present": False,
            "token_created_at_utc": None,
        },
        "routes": {},
    }


def default_routes_payload() -> dict[str, Any]:
    return {"schema_version": ROUTE_SCHEMA_VERSION, "routes": []}


def operator_action_for_next_action(*, ok: bool, next_action: str) -> str:
    if next_action in command_packets.COMMAND_OPERATOR_ACTION_VALUES:
        return next_action
    return "none" if ok else "user_action"


def build_external_models_payload(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    data: dict[str, Any] | None = None,
    changed_files: list[str] | None = None,
    next_action: str = "none",
    operator_action: str | None = None,
    severity: str = "recoverable",
    liveness: str = "not_applicable",
    exit_code: int | None = None,
    effect: str | None = None,
) -> dict[str, Any]:
    generic_operator_action = (
        operator_action
        if operator_action is not None
        else operator_action_for_next_action(ok=ok, next_action=next_action)
    )
    payload = build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=liveness,
        severity=severity,
        operator_action=generic_operator_action,
        changed_files=changed_files or [],
        extra={
            "data": data or {},
            "timestamp_utc": utc_now_iso(),
            "next_action": next_action,
        },
        exit_code=exit_code,
        effect=validate_effect(effect) if effect is not None else None,
    )
    return payload
