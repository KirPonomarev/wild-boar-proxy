"""Contracts for the external-models C2 synthetic lifecycle slice."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from wild_boar_proxy.runtime import build_command_payload

ROUTE_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 2
EVIDENCE_SCHEMA_VERSION = 1

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


def build_external_models_payload(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    data: dict[str, Any] | None = None,
    changed_files: list[str] | None = None,
    next_action: str = "none",
    severity: str = "recoverable",
    liveness: str = "not_applicable",
    exit_code: int | None = None,
) -> dict[str, Any]:
    payload = build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=liveness,
        severity=severity,
        operator_action=next_action,
        changed_files=changed_files or [],
        extra={"data": data or {}, "timestamp_utc": utc_now_iso()},
        exit_code=exit_code,
    )
    return payload
