"""Bounded provider validation helpers for external-models C3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors
from .http_client import request_json
from .paths import ExternalModelsPaths
from .routes import find_route, load_routes_file
from .state import (
    atomic_write_json,
    dual_lock,
    ensure_secrets_permissions,
    load_state_file,
    write_state_file,
)


def _parse_secrets_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _provider_headers(route: dict[str, Any], paths: ExternalModelsPaths) -> dict[str, str]:
    ensure_secrets_permissions(paths.secrets_file)
    auth = route["auth"]
    if auth.get("type") == "none":
        return {}
    secret_ref = str(auth.get("secret_ref", "")).strip()
    if not secret_ref:
        raise RuntimeErrorInfo(
            "Route auth secret_ref is missing.",
            machine_error_code=errors.MISSING_SECRET,
            operator_action="user_action",
        )
    secrets_map = _parse_secrets_file(paths.secrets_file)
    if secret_ref not in secrets_map:
        raise RuntimeErrorInfo(
            f"Route secret is missing: {secret_ref}",
            machine_error_code=errors.MISSING_SECRET,
            operator_action="user_action",
        )
    secret_value = secrets_map[secret_ref].strip()
    if not secret_value:
        raise RuntimeErrorInfo(
            f"Route secret is empty: {secret_ref}",
            machine_error_code=errors.INVALID_SECRET,
            operator_action="user_action",
        )
    auth_type = auth.get("type")
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {secret_value}"}
    raise RuntimeErrorInfo(
        f"Unsupported route auth type: {auth_type}",
        machine_error_code=errors.INVALID_REQUEST,
        operator_action="user_action",
    )


def _models_url(route: dict[str, Any]) -> str:
    return str(route["base_url"]).rstrip("/") + "/models"


def _completion_url(route: dict[str, Any]) -> str:
    return str(route["base_url"]).rstrip("/") + str(route["endpoint_path"])


def _write_network_evidence(
    *,
    paths: ExternalModelsPaths,
    route: dict[str, Any],
    command_context: str,
    result: dict[str, Any],
) -> Path:
    paths.evidence_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": contracts.EVIDENCE_SCHEMA_VERSION,
        "captured_at_utc": contracts.utc_now_iso(),
        "route_id": route["route_id"],
        "command_context": command_context,
        "network_dependent_evidence": True,
        "verification_scope": "route_provider_only",
        "result": result,
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    stamp = contracts.utc_now_iso().replace(":", "").replace("-", "")
    path = paths.evidence_dir / f"{route['route_id']}-{command_context.replace(' ', '_')}-{stamp}.json"
    atomic_write_json(path, payload)
    return path


def _route_observation_patch(
    *,
    availability_state: str,
    machine_error_code: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "availability_state": availability_state,
        "last_error": machine_error_code if machine_error_code != errors.OK else "",
    }
    if extra:
        payload.update(extra)
    return payload


def _update_route_observation(
    *,
    paths: ExternalModelsPaths,
    route_id: str,
    patch: dict[str, Any],
) -> str:
    with dual_lock(paths.routes_lock, paths.state_lock):
        state_payload = load_state_file(paths.state_file)
        route_state = dict(state_payload["routes"].get(route_id, {}))
        route_state.update(patch)
        state_payload["routes"][route_id] = route_state
        write_state_file(paths.state_file, state_payload)
    return str(paths.state_file)


def _handle_models_probe(route: dict[str, Any], paths: ExternalModelsPaths) -> tuple[dict[str, Any], int | None]:
    headers = _provider_headers(route, paths)
    response = request_json(url=_models_url(route), method="GET", headers=headers)
    if response.status_code in (401, 403):
        raise RuntimeErrorInfo(
            "Provider rejected route credentials.",
            machine_error_code=errors.PROVIDER_AUTH_FAILED,
            operator_action="user_action",
        )
    if response.status_code != 200:
        raise RuntimeErrorInfo(
            "Provider returned an invalid response to models probe.",
            machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
            operator_action="retry",
        )
    payload = response.payload
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise RuntimeErrorInfo(
            "Provider models probe returned malformed JSON.",
            machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
            operator_action="retry",
        )
    available_models = {
        str(item.get("id", ""))
        for item in payload["data"]
        if isinstance(item, dict) and item.get("id")
    }
    if str(route["upstream_model"]) not in available_models:
        raise RuntimeErrorInfo(
            f"Provider does not expose route model: {route['upstream_model']}",
            machine_error_code=errors.MODEL_NOT_AVAILABLE,
            operator_action="user_action",
        )
    return {
        "available_models_count": len(available_models),
        "latency_ms": response.latency_ms,
    }, len(available_models)


def validate_route_provider(paths: ExternalModelsPaths, route_id: str) -> tuple[dict[str, Any], list[str]]:
    route = find_route(load_routes_file(paths.routes_file), route_id)
    if str(route["cost_class"]) == "paid_direct":
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state="blocked",
                machine_error_code=errors.PAID_ROUTE_BLOCKED,
                extra={"last_validate": contracts.utc_now_iso()},
            ),
        )
        error = RuntimeErrorInfo(
            "Paid route validation is blocked by policy.",
            machine_error_code=errors.PAID_ROUTE_BLOCKED,
            operator_action="user_action",
        )
        error.changed_files = [state_path]
        error.data = {
            "validation_kind": "provider_route_validate",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": "blocked",
            "requested_model": route["route_id"],
            "provider": route["provider"],
        }
        raise error
    try:
        probe_data, model_count = _handle_models_probe(route, paths)
        observed_at = contracts.utc_now_iso()
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state="model_visible",
                machine_error_code=errors.OK,
                extra={
                    "last_validate": observed_at,
                    "evidence_level": "network_route_validate",
                    "latency_ms": probe_data["latency_ms"],
                },
            ),
        )
        result = {
            "status": "ok",
            "machine_error_code": errors.OK,
            "requested_model": route["route_id"],
            "effective_model": route["upstream_model"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
            "cost_class": route["cost_class"],
            "latency_ms": probe_data["latency_ms"],
            "verification_scope": "route_provider_only",
            "available_models_count": model_count,
        }
        evidence_path = _write_network_evidence(
            paths=paths,
            route=route,
            command_context="external-models routes validate",
            result=result,
        )
        data = {
            "validation_kind": "provider_route_validate",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": "model_visible",
            "requested_model": route["route_id"],
            "effective_model": route["upstream_model"],
            "provider": route["provider"],
            "evidence_path": str(evidence_path),
        }
        data.update(probe_data)
        return data, [state_path, str(evidence_path)]
    except RuntimeErrorInfo as exc:
        availability_state = {
            errors.PROVIDER_AUTH_FAILED: "provider_auth_failed",
            errors.PROVIDER_NETWORK_FAILED: "provider_network_failed",
            errors.MODEL_NOT_AVAILABLE: "model_not_available",
            errors.PAID_ROUTE_BLOCKED: "blocked",
            errors.MISSING_SECRET: "blocked",
            errors.UNSAFE_SECRET_PERMISSIONS: "blocked",
            errors.INVALID_SECRET: "blocked",
        }.get(exc.machine_error_code, "limited")
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state=availability_state,
                machine_error_code=exc.machine_error_code,
                extra={"last_validate": contracts.utc_now_iso()},
            ),
        )
        error = RuntimeErrorInfo(
            exc.message,
            machine_error_code=exc.machine_error_code,
            operator_action=exc.operator_action,
            severity=exc.severity,
            exit_code=exc.exit_code,
        )
        error.changed_files = [state_path]
        error.data = {
            "validation_kind": "provider_route_validate",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": availability_state,
            "requested_model": route["route_id"],
            "provider": route["provider"],
        }
        raise error from exc


def check_route_provider(paths: ExternalModelsPaths, route_id: str) -> tuple[dict[str, Any], list[str]]:
    route = find_route(load_routes_file(paths.routes_file), route_id)
    if str(route["cost_class"]) == "paid_direct":
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state="blocked",
                machine_error_code=errors.PAID_ROUTE_BLOCKED,
                extra={"last_check": contracts.utc_now_iso()},
            ),
        )
        error = RuntimeErrorInfo(
            "Paid route smoke check is blocked by policy.",
            machine_error_code=errors.PAID_ROUTE_BLOCKED,
            operator_action="user_action",
        )
        error.changed_files = [state_path]
        error.data = {
            "check_kind": "provider_route_smoke",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": "blocked",
            "requested_model": route["route_id"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
        }
        raise error
    try:
        headers = _provider_headers(route, paths)
        response = request_json(
            url=_completion_url(route),
            method="POST",
            headers=headers,
            payload={
                "model": route["upstream_model"],
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 8,
            },
        )
        if response.status_code in (401, 403):
            raise RuntimeErrorInfo(
                "Provider rejected route credentials.",
                machine_error_code=errors.PROVIDER_AUTH_FAILED,
                operator_action="user_action",
            )
        if response.status_code != 200:
            raise RuntimeErrorInfo(
                "Provider returned an invalid smoke-check response.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        payload = response.payload
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise RuntimeErrorInfo(
                "Provider smoke-check payload did not contain choices.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        observed_at = contracts.utc_now_iso()
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state="verified",
                machine_error_code=errors.OK,
                extra={
                    "last_check": observed_at,
                    "last_verified_at": observed_at,
                    "evidence_level": "network_route_check",
                    "latency_ms": response.latency_ms,
                    "fallback_used": False,
                    "effective_model": route["upstream_model"],
                },
            ),
        )
        result = {
            "status": "ok",
            "machine_error_code": errors.OK,
            "requested_model": route["route_id"],
            "effective_model": route["upstream_model"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
            "cost_class": route["cost_class"],
            "latency_ms": response.latency_ms,
            "verification_scope": "route_provider_only",
        }
        evidence_path = _write_network_evidence(
            paths=paths,
            route=route,
            command_context="external-models check",
            result=result,
        )
        return {
            "check_kind": "provider_route_smoke",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": "verified",
            "requested_model": route["route_id"],
            "effective_model": route["upstream_model"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
            "evidence_path": str(evidence_path),
            "latency_ms": response.latency_ms,
            "request_count": 1,
        }, [state_path, str(evidence_path)]
    except RuntimeErrorInfo as exc:
        availability_state = {
            errors.PROVIDER_AUTH_FAILED: "provider_auth_failed",
            errors.PROVIDER_NETWORK_FAILED: "provider_network_failed",
            errors.MODEL_NOT_AVAILABLE: "model_not_available",
            errors.PAID_ROUTE_BLOCKED: "blocked",
            errors.MISSING_SECRET: "blocked",
            errors.UNSAFE_SECRET_PERMISSIONS: "blocked",
            errors.INVALID_SECRET: "blocked",
        }.get(exc.machine_error_code, "limited")
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state=availability_state,
                machine_error_code=exc.machine_error_code,
                extra={"last_check": contracts.utc_now_iso()},
            ),
        )
        error = RuntimeErrorInfo(
            exc.message,
            machine_error_code=exc.machine_error_code,
            operator_action=exc.operator_action,
            severity=exc.severity,
            exit_code=exc.exit_code,
        )
        error.changed_files = [state_path]
        error.data = {
            "check_kind": "provider_route_smoke",
            "network_dependent": True,
            "listener_proven": False,
            "runtime_claim_blocked": True,
            "profile_ready": False,
            "verification_scope": "route_provider_only",
            "route_state": availability_state,
            "requested_model": route["route_id"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
        }
        raise error from exc
