"""Route lifecycle helpers for the external-models C2 synthetic lifecycle slice."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors
from .paths import ExternalModelsPaths
from .state import atomic_write_json, dual_lock, ensure_secrets_permissions, load_state_file, serialized_lock, write_state_file


def _load_json_from_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeErrorInfo(
            f"Route file not found: {path}",
            machine_error_code=errors.INVALID_REQUEST,
            operator_action="user_action",
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            f"Route file is not valid JSON: {path}",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        ) from exc


def _load_json_from_stdin() -> Any:
    raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            "stdin did not contain valid JSON.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        ) from exc


def load_route_input(*, file_path: str | None, use_stdin: bool) -> dict[str, Any]:
    if bool(file_path) == bool(use_stdin):
        raise RuntimeErrorInfo(
            "Provide exactly one of --file or --stdin.",
            machine_error_code=errors.INVALID_REQUEST,
            operator_action="user_action",
        )
    payload = _load_json_from_stdin() if use_stdin else _load_json_from_file(Path(file_path))
    if not isinstance(payload, dict):
        raise RuntimeErrorInfo(
            "Route payload must be a JSON object.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    return payload


def load_routes_file(routes_file: Path) -> dict[str, Any]:
    if not routes_file.exists():
        return contracts.default_routes_payload()
    payload = _load_json_from_file(routes_file)
    if not isinstance(payload, dict):
        raise RuntimeErrorInfo(
            "External-models routes file must be a JSON object.",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        )
    schema_version = payload.get("schema_version")
    if schema_version != contracts.ROUTE_SCHEMA_VERSION:
        raise RuntimeErrorInfo(
            "Unsupported external-models routes schema version.",
            machine_error_code=errors.UNSUPPORTED_SCHEMA_VERSION,
            operator_action="stop",
        )
    if set(payload.keys()) - contracts.ROUTES_TOP_LEVEL_FIELDS:
        raise RuntimeErrorInfo(
            "Unexpected top-level fields in routes.json.",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        )
    routes = payload.get("routes", [])
    if not isinstance(routes, list):
        raise RuntimeErrorInfo(
            "routes.json must contain a list under routes.",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        )
    return payload


def write_routes_file(routes_file: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(routes_file, payload)


def validate_route_schema(route: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(contracts.ROUTE_REQUIRED_FIELDS - route.keys())
    unexpected = sorted(set(route.keys()) - contracts.ROUTE_ALLOWED_FIELDS)
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        raise RuntimeErrorInfo(
            "Route schema is invalid: " + ", ".join(details),
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if route.get("schema_version") != contracts.ROUTE_SCHEMA_VERSION:
        raise RuntimeErrorInfo(
            "Unsupported route schema version.",
            machine_error_code=errors.UNSUPPORTED_SCHEMA_VERSION,
            operator_action="user_action",
        )
    route_id = route.get("route_id")
    if not isinstance(route_id, str) or not route_id.strip():
        raise RuntimeErrorInfo(
            "route_id is required.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if not route_id.startswith("wbp-"):
        raise RuntimeErrorInfo(
            "route_id must use the wbp- prefix.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    base_url = str(route.get("base_url", ""))
    if base_url.startswith("http://") and not (
        base_url.startswith("http://127.0.0.1")
        or base_url.startswith("http://localhost")
        or base_url.startswith("http://[::1]")
    ):
        raise RuntimeErrorInfo(
            "Remote route base_url must use https://.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if not base_url.startswith(("https://", "http://127.0.0.1", "http://localhost", "http://[::1]")):
        raise RuntimeErrorInfo(
            "base_url must use a supported scheme.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    auth = route.get("auth")
    if not isinstance(auth, dict):
        raise RuntimeErrorInfo(
            "auth must be an object.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if auth.get("type") != "none" and not auth.get("secret_ref"):
        raise RuntimeErrorInfo(
            "auth.secret_ref is required for authenticated routes.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    return route


def route_models_projection(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_id": route["route_id"],
        "display_name": route["display_name"],
        "provider": route["provider"],
        "base_url": route["base_url"],
        "endpoint_path": route["endpoint_path"],
        "upstream_model": route["upstream_model"],
        "compatibility": route["compatibility"],
        "cost_class": route["cost_class"],
        "enabled": route["enabled"],
        "lane_role": route["lane_role"],
        "fallback_eligible": route["fallback_eligible"],
    }


def find_route(routes_payload: dict[str, Any], route_id: str) -> dict[str, Any]:
    for route in routes_payload["routes"]:
        if route["route_id"] == route_id:
            return route
    raise RuntimeErrorInfo(
        f"Route not found: {route_id}",
        machine_error_code=errors.ROUTE_NOT_FOUND,
        operator_action="user_action",
    )


def add_route(paths: ExternalModelsPaths, route: dict[str, Any]) -> list[str]:
    validate_route_schema(route)
    with serialized_lock(paths.routes_lock):
        routes_payload = load_routes_file(paths.routes_file)
        if any(existing["route_id"] == route["route_id"] for existing in routes_payload["routes"]):
            raise RuntimeErrorInfo(
                f"Route already exists: {route['route_id']}",
                machine_error_code=errors.DUPLICATE_ROUTE,
                operator_action="user_action",
            )
        routes_payload["routes"].append(route)
        write_routes_file(paths.routes_file, routes_payload)
    return [str(paths.routes_file)]


def update_route(paths: ExternalModelsPaths, route_id: str, route: dict[str, Any]) -> list[str]:
    validate_route_schema(route)
    if route["route_id"] != route_id:
        raise RuntimeErrorInfo(
            "Route payload route_id must match --route.",
            machine_error_code=errors.INVALID_REQUEST,
            operator_action="user_action",
        )
    with serialized_lock(paths.routes_lock):
        routes_payload = load_routes_file(paths.routes_file)
        replaced = False
        updated_routes = []
        for existing in routes_payload["routes"]:
            if existing["route_id"] == route_id:
                updated_routes.append(route)
                replaced = True
            else:
                updated_routes.append(existing)
        if not replaced:
            raise RuntimeErrorInfo(
                f"Route not found: {route_id}",
                machine_error_code=errors.ROUTE_NOT_FOUND,
                operator_action="user_action",
            )
        routes_payload["routes"] = updated_routes
        write_routes_file(paths.routes_file, routes_payload)
    return [str(paths.routes_file)]


def remove_route(paths: ExternalModelsPaths, route_id: str) -> list[str]:
    changed_files: list[str] = []
    with dual_lock(paths.routes_lock, paths.state_lock):
        routes_payload = load_routes_file(paths.routes_file)
        route = find_route(routes_payload, route_id)
        if route["enabled"]:
            raise RuntimeErrorInfo(
                f"Disable the route before removing it: {route_id}",
                machine_error_code=errors.ROUTE_NOT_DISABLED,
                operator_action="user_action",
            )
        routes_payload["routes"] = [
            existing
            for existing in routes_payload["routes"]
            if existing["route_id"] != route_id
        ]
        write_routes_file(paths.routes_file, routes_payload)
        changed_files.append(str(paths.routes_file))
        state_payload = load_state_file(paths.state_file)
        if state_payload["routes"].pop(route_id, None) is not None:
            write_state_file(paths.state_file, state_payload)
            changed_files.append(str(paths.state_file))
    return changed_files


def set_route_enabled(paths: ExternalModelsPaths, route_id: str, enabled: bool) -> list[str]:
    with serialized_lock(paths.routes_lock):
        routes_payload = load_routes_file(paths.routes_file)
        route = find_route(routes_payload, route_id)
        route["enabled"] = enabled
        write_routes_file(paths.routes_file, routes_payload)
    return [str(paths.routes_file)]


def list_routes(paths: ExternalModelsPaths) -> list[dict[str, Any]]:
    return load_routes_file(paths.routes_file)["routes"]


def foundation_status(paths: ExternalModelsPaths) -> dict[str, Any]:
    routes_payload = load_routes_file(paths.routes_file)
    state_payload = load_state_file(paths.state_file)
    return {
        "foundation_phase": "C3",
        "adapter_runtime_available": False,
        "lifecycle_mode": state_payload["adapter"]["lifecycle_mode"],
        "adapter_state": state_payload["adapter"]["state"],
        "listener_proven": False,
        "runtime_claim_blocked": True,
        "profile_ready": False,
        "routes_count": len(routes_payload["routes"]),
        "observed_routes_count": len(state_payload["routes"]),
        "paths": {
            "routes_file": str(paths.routes_file),
            "state_file": str(paths.state_file),
            "secrets_file": str(paths.secrets_file),
            "evidence_dir": str(paths.evidence_dir),
        },
    }


def models_listing(paths: ExternalModelsPaths) -> list[dict[str, Any]]:
    state_payload = load_state_file(paths.state_file)
    return [
        route_models_projection(route)
        | {
            "synthetic_adapter_state": state_payload["adapter"]["state"],
            "profile_ready": False,
        }
        for route in list_routes(paths)
    ]


def profile_packet(paths: ExternalModelsPaths, route_id: str) -> dict[str, Any]:
    route = find_route(load_routes_file(paths.routes_file), route_id)
    ensure_secrets_permissions(paths.secrets_file)
    state_payload = load_state_file(paths.state_file)
    return {
        "profile_kind": "codex_desktop_openai_compatible",
        "route_id": route["route_id"],
        "base_url": state_payload["adapter"]["base_url"],
        "model": route["route_id"],
        "api_key_source": "managed_local_token",
        "writes_external_config": False,
        "profile_ready": False,
        "listener_proven": False,
        "runtime_claim_blocked": True,
        "synthetic_endpoint_contract": True,
        "prerequisite": "live_listener_contour_required",
    }
