"""Bounded provider validation helpers for external-models C3."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors, transforms
from .http_client import request_json
from .paths import ExternalModelsPaths
from .routes import find_route, load_routes_file
from .state import (
    build_evidence_artifact_path,
    dual_lock,
    ensure_secrets_permissions,
    load_state_file,
    write_evidence_file,
    write_state_file,
)


def _direct_provider_proof_fields(*, direct_provider_response_observed: bool) -> dict[str, Any]:
    return {
        "direct_provider_auth_proven": bool(direct_provider_response_observed),
        "direct_provider_response_observed": bool(direct_provider_response_observed),
        "provider_auth_ok": bool(direct_provider_response_observed),
        "bridge_green_counts_as_provider_proof": False,
        "provider_auth_smoke_required_before_full_runner": True,
        "positive_provider_proof_gate_satisfied": bool(direct_provider_response_observed),
    }


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


def _load_runtime_context_from_env() -> dict[str, Any]:
    profile_dir = os.environ.get("WBP_PROFILE_DIR", "").strip()
    if not profile_dir:
        return {}
    context_path = Path(profile_dir).expanduser() / "wbp-agent-runtime-context.json"
    try:
        parsed = json.loads(context_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _runtime_context_allows_route(context: dict[str, Any], route_id: str) -> bool:
    allowed = context.get("allowed_api_route_ids")
    return isinstance(allowed, list) and route_id in allowed


def _replace_bridge_placeholders(value: Any, *, request_id: str, expected_text: str) -> Any:
    if isinstance(value, str):
        return value.replace("<unique-id>", request_id).replace(
            "<expected_text>",
            expected_text,
        )
    if isinstance(value, list):
        return [
            _replace_bridge_placeholders(
                item,
                request_id=request_id,
                expected_text=expected_text,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            str(key): _replace_bridge_placeholders(
                item,
                request_id=request_id,
                expected_text=expected_text,
            )
            for key, item in value.items()
        }
    return value


def _response_text_from_field(payload: Any, field_name: str) -> str:
    if not isinstance(payload, dict):
        return ""
    value: Any = payload
    for part in field_name.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(part)
    return str(value) if isinstance(value, str) else ""


def _bridge_live_format_data(
    *,
    route: dict[str, Any],
    expected_text: str,
    response_text: str,
    latency_ms: int | None,
    bridge_kind: str,
    request_count: int,
    request_id: str = "",
) -> dict[str, Any]:
    is_file_bridge = "file_bridge" in bridge_kind
    data = {
        "check_kind": "api_only_live_route_format",
        "network_dependent": True,
        "verification_scope": "route_provider_only_no_write",
        "route_state": "live_response_observed_no_write",
        "requested_model": route["route_id"],
        "effective_model": route["upstream_model"],
        "provider": route["provider"],
        "fallback_used": False,
        "fallback_chain": [route["route_id"]],
        "cost_class": route["cost_class"],
        "latency_ms": latency_ms,
        "request_count": request_count,
        "retry_count": 0,
        "parallel_fanout_attempted": False,
        "expected_text": expected_text,
        "expected_text_observed": expected_text in response_text,
        "response_preview_bounded": response_text[:160],
        "response_text_length": len(response_text),
        "changed_files": [],
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "commands_started_by_provider": False,
        "codex_history_sent": False,
        "repo_context_sent": False,
        "request_shape": "runtime_context_bridge",
        "response_profile": "runtime_context_bridge",
        "response_shape": "output_text",
        "runtime_context_bridge_used": not is_file_bridge,
        "runtime_context_file_bridge_used": is_file_bridge,
        "bridge_or_file_bridge_used": True,
        "bridge_kind": bridge_kind,
        **_direct_provider_proof_fields(direct_provider_response_observed=False),
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    if is_file_bridge and request_id:
        data["file_bridge_response_request_id_sha256"] = hashlib.sha256(
            request_id.encode("utf-8")
        ).hexdigest()
    return data


def _runtime_context_loopback_bridge_data(
    *,
    context: dict[str, Any],
    route: dict[str, Any],
    expected_text: str,
) -> dict[str, Any] | None:
    bridge = context.get("deepseek_live_format_check_bridge")
    if not isinstance(bridge, dict) or bridge.get("enabled") is not True:
        return None
    if str(bridge.get("model") or "") != str(route["route_id"]):
        return None
    urls = bridge.get("url_candidates")
    if not isinstance(urls, list) or not urls:
        raw_url = str(bridge.get("url") or "").strip()
        urls = [raw_url] if raw_url else []
    request_template = bridge.get("request_json_template")
    if not isinstance(request_template, dict):
        return None
    field_name = str(bridge.get("response_text_field") or "output_text")
    last_error: RuntimeErrorInfo | None = None
    for raw_url in urls:
        url = str(raw_url).strip()
        if not url:
            continue
        request_id = secrets.token_urlsafe(16)
        payload = _replace_bridge_placeholders(
            request_template,
            request_id=request_id,
            expected_text=expected_text,
        )
        try:
            response = request_json(
                url=url,
                method=str(bridge.get("method") or "POST"),
                headers={},
                payload=payload,
            )
        except RuntimeErrorInfo as exc:
            last_error = exc
            continue
        if response.status_code != 200:
            continue
        response_text = _response_text_from_field(response.payload, field_name)
        if not response_text:
            continue
        return _bridge_live_format_data(
            route=route,
            expected_text=expected_text,
            response_text=response_text,
            latency_ms=response.latency_ms,
            bridge_kind=str(bridge.get("bridge_kind") or "runtime_context_loopback_bridge"),
            request_count=1,
        )
    if last_error is not None:
        return None
    return None


def _runtime_context_file_bridge_data(
    *,
    context: dict[str, Any],
    route: dict[str, Any],
    expected_text: str,
) -> dict[str, Any] | None:
    bridge = context.get("deepseek_live_format_check_file_bridge")
    if not isinstance(bridge, dict) or bridge.get("enabled") is not True:
        return None
    if str(bridge.get("model") or "") != str(route["route_id"]):
        return None
    request_template = bridge.get("request_json_template")
    if not isinstance(request_template, dict):
        return None
    request_dir_raw = str(bridge.get("request_dir") or "").strip()
    response_dir_raw = str(bridge.get("response_dir") or "").strip()
    if not request_dir_raw or not response_dir_raw:
        return None
    request_dir = Path(request_dir_raw).expanduser()
    response_dir = Path(response_dir_raw).expanduser()
    request_extension = str(bridge.get("request_extension") or ".json")
    response_extension = str(bridge.get("response_extension") or ".json")
    request_id = secrets.token_urlsafe(16)
    request_path = request_dir / f"{request_id}{request_extension}"
    response_path = response_dir / f"{request_id}{response_extension}"
    payload = _replace_bridge_placeholders(
        request_template,
        request_id=request_id,
        expected_text=expected_text,
    )
    started_at = time.monotonic()
    try:
        request_dir.mkdir(parents=True, exist_ok=True)
        response_dir.mkdir(parents=True, exist_ok=True)
        request_path.write_text(
            json.dumps(payload, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return None
    timeout_seconds = max(float(bridge.get("timeout_seconds") or 45.0), 0.0)
    poll_interval = max(float(bridge.get("poll_interval_seconds") or 0.25), 0.01)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if response_path.exists():
            break
        time.sleep(poll_interval)
    if not response_path.exists():
        return None
    try:
        parsed = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    field_name = str(bridge.get("response_text_field") or "output_text")
    response_text = _response_text_from_field(parsed, field_name)
    if not response_text:
        return None
    return _bridge_live_format_data(
        route=route,
        expected_text=expected_text,
        response_text=response_text,
        latency_ms=int((time.monotonic() - started_at) * 1000),
        bridge_kind=str(bridge.get("bridge_kind") or "file_bridge"),
        request_count=1,
        request_id=request_id,
    )


def _runtime_context_bridge_live_format_data(
    *,
    route: dict[str, Any],
    route_id: str,
    expected_text: str,
) -> dict[str, Any] | None:
    context = _load_runtime_context_from_env()
    if not context or not _runtime_context_allows_route(context, route_id):
        return None
    return _runtime_context_loopback_bridge_data(
        context=context,
        route=route,
        expected_text=expected_text,
    ) or _runtime_context_file_bridge_data(
        context=context,
        route=route,
        expected_text=expected_text,
    )


def _require_enabled_route(route: dict[str, Any], *, action_label: str) -> None:
    if route.get("enabled") is False:
        raise RuntimeErrorInfo(
            f"External-models route is disabled for {action_label}: {route['route_id']}",
            machine_error_code=errors.ROUTE_DISABLED,
            operator_action="user_action",
        )


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
    path = build_evidence_artifact_path(
        evidence_dir=paths.evidence_dir,
        route_id=route.get("route_id"),
        suffix=f"{command_context.replace(' ', '_')}-{stamp}",
    )
    write_evidence_file(path, payload)
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
    transforms.validate_route_transform_profiles(route)
    transform_metadata = transforms.route_transform_metadata(route)
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
        error.data.update(transform_metadata)
        raise error
    try:
        _require_enabled_route(route, action_label="validate")
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
        result.update(transform_metadata)
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
        data.update(transform_metadata)
        return data, [state_path, str(evidence_path)]
    except RuntimeErrorInfo as exc:
        availability_state = {
            errors.PROVIDER_AUTH_FAILED: "provider_auth_failed",
            errors.PROVIDER_NETWORK_FAILED: "provider_network_failed",
            errors.MODEL_NOT_AVAILABLE: "model_not_available",
            errors.PAID_ROUTE_BLOCKED: "blocked",
            errors.ROUTE_DISABLED: "blocked",
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
        error.data.update(transform_metadata)
        raise error from exc


def check_route_provider(paths: ExternalModelsPaths, route_id: str) -> tuple[dict[str, Any], list[str]]:
    route = find_route(load_routes_file(paths.routes_file), route_id)
    transforms.validate_route_transform_profiles(route)
    transform_metadata = transforms.route_transform_metadata(route)
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
        error.data.update(transform_metadata)
        raise error
    try:
        _require_enabled_route(route, action_label="check")
        headers = _provider_headers(route, paths)
        request_payload, request_metadata = transforms.build_check_request(
            route, user_prompt="ping"
        )
        response = request_json(
            url=_completion_url(route),
            method="POST",
            headers=headers,
            payload=request_payload,
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
        _response_text, response_metadata = transforms.extract_check_response(route, payload)
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
        result.update(request_metadata)
        result.update(
            {
                "response_profile": response_metadata["response_profile"],
                "response_shape": response_metadata["response_shape"],
            }
        )
        evidence_path = _write_network_evidence(
            paths=paths,
            route=route,
            command_context="external-models check",
            result=result,
        )
        data = {
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
            "runtime_context_bridge_used": False,
            "runtime_context_file_bridge_used": False,
            "bridge_or_file_bridge_used": False,
            **_direct_provider_proof_fields(direct_provider_response_observed=True),
        }
        data.update(request_metadata)
        data.update(
            {
                "response_profile": response_metadata["response_profile"],
                "response_shape": response_metadata["response_shape"],
            }
        )
        return data, [state_path, str(evidence_path)]
    except RuntimeErrorInfo as exc:
        bridge_data = (
            _runtime_context_bridge_live_format_data(
                route=route,
                route_id=route_id,
                expected_text="pong",
            )
            if exc.machine_error_code == errors.PROVIDER_NETWORK_FAILED
            else None
        )
        availability_state = {
            errors.PROVIDER_AUTH_FAILED: "provider_auth_failed",
            errors.PROVIDER_NETWORK_FAILED: "provider_network_failed",
            errors.MODEL_NOT_AVAILABLE: "model_not_available",
            errors.PAID_ROUTE_BLOCKED: "blocked",
            errors.ROUTE_DISABLED: "blocked",
            errors.MISSING_SECRET: "blocked",
            errors.UNSAFE_SECRET_PERMISSIONS: "blocked",
            errors.INVALID_SECRET: "blocked",
        }.get(exc.machine_error_code, "limited")
        if bridge_data is not None:
            availability_state = "provider_network_failed_bridge_observed"
        state_extra = {"last_check": contracts.utc_now_iso()}
        if bridge_data is not None:
            state_extra.update(
                {
                    "bridge_live_response_observed": True,
                    "bridge_green_counts_as_provider_proof": False,
                    "direct_provider_error": exc.machine_error_code,
                }
            )
        state_path = _update_route_observation(
            paths=paths,
            route_id=route_id,
            patch=_route_observation_patch(
                availability_state=availability_state,
                machine_error_code=exc.machine_error_code,
                extra=state_extra,
            ),
        )
        bridge_message_suffix = ""
        if bridge_data is not None:
            bridge_message_suffix = (
                " Runtime context bridge observed a live response, but it does "
                "not count as direct provider proof."
            )
        error = RuntimeErrorInfo(
            f"{exc.message}{bridge_message_suffix}",
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
            "runtime_context_bridge_used": False,
            "runtime_context_file_bridge_used": False,
            "bridge_or_file_bridge_used": False,
            **_direct_provider_proof_fields(direct_provider_response_observed=False),
        }
        if bridge_data is not None:
            error.data.update(
                {
                    "runtime_context_bridge_used": (
                        bridge_data.get("runtime_context_bridge_used") is True
                    ),
                    "runtime_context_file_bridge_used": (
                        bridge_data.get("runtime_context_file_bridge_used") is True
                    ),
                    "bridge_or_file_bridge_used": True,
                    "bridge_live_response_observed": (
                        bridge_data.get("expected_text_observed") is True
                    ),
                    "bridge_expected_text_observed": (
                        bridge_data.get("expected_text_observed") is True
                    ),
                    "bridge_response_preview_bounded": str(
                        bridge_data.get("response_preview_bounded") or ""
                    ),
                    "bridge_response_text_length": int(
                        bridge_data.get("response_text_length") or 0
                    ),
                    "bridge_latency_ms": bridge_data.get("latency_ms"),
                    "bridge_kind": str(bridge_data.get("bridge_kind") or ""),
                    "bridge_request_count": int(bridge_data.get("request_count") or 0),
                    "bridge_state_written": False,
                    "bridge_evidence_written": False,
                    "bridge_green_counts_as_provider_proof": False,
                }
            )
            if "file_bridge_response_request_id_sha256" in bridge_data:
                error.data["file_bridge_response_request_id_sha256"] = bridge_data[
                    "file_bridge_response_request_id_sha256"
                ]
        error.data.update(transform_metadata)
        raise error from exc


def check_route_provider_once_no_write(
    paths: ExternalModelsPaths,
    route_id: str,
    *,
    user_prompt: str,
    expected_text: str,
) -> dict[str, Any]:
    route = find_route(load_routes_file(paths.routes_file), route_id)
    transforms.validate_route_transform_profiles(route)
    transform_metadata = transforms.route_transform_metadata(route)
    if str(route["cost_class"]) == "paid_direct":
        raise RuntimeErrorInfo(
            "Paid route live format check is blocked by policy.",
            machine_error_code=errors.PAID_ROUTE_BLOCKED,
            operator_action="user_action",
        )
    _require_enabled_route(route, action_label="live-format-check")
    bridge_data = _runtime_context_bridge_live_format_data(
        route=route,
        route_id=route_id,
        expected_text=expected_text,
    )
    if bridge_data is not None:
        return {**bridge_data, **transform_metadata}
    headers = _provider_headers(route, paths)
    request_payload, request_metadata = transforms.build_check_request(
        route, user_prompt=user_prompt
    )
    response = request_json(
        url=_completion_url(route),
        method="POST",
        headers=headers,
        payload=request_payload,
    )
    if response.status_code in (401, 403):
        error = RuntimeErrorInfo(
            "Provider rejected route credentials.",
            machine_error_code=errors.PROVIDER_AUTH_FAILED,
            operator_action="user_action",
        )
        error.data = {
            "check_kind": "api_only_live_route_format",
            "network_dependent": True,
            "verification_scope": "route_provider_only_no_write",
            "route_state": "provider_auth_failed",
            "requested_model": route["route_id"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
            "runtime_context_bridge_used": False,
            "runtime_context_file_bridge_used": False,
            "bridge_or_file_bridge_used": False,
            **_direct_provider_proof_fields(direct_provider_response_observed=False),
        }
        raise error
    if response.status_code != 200:
        error = RuntimeErrorInfo(
            "Provider returned an invalid live-format response.",
            machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
            operator_action="retry",
        )
        error.data = {
            "check_kind": "api_only_live_route_format",
            "network_dependent": True,
            "verification_scope": "route_provider_only_no_write",
            "route_state": "invalid_upstream_response",
            "requested_model": route["route_id"],
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route["route_id"]],
            "runtime_context_bridge_used": False,
            "runtime_context_file_bridge_used": False,
            "bridge_or_file_bridge_used": False,
            **_direct_provider_proof_fields(direct_provider_response_observed=False),
        }
        raise error
    response_text, response_metadata = transforms.extract_check_response(route, response.payload)
    return {
        "check_kind": "api_only_live_route_format",
        "network_dependent": True,
        "verification_scope": "route_provider_only_no_write",
        "route_state": "live_response_observed_no_write",
        "requested_model": route["route_id"],
        "effective_model": route["upstream_model"],
        "provider": route["provider"],
        "fallback_used": False,
        "fallback_chain": [route["route_id"]],
        "cost_class": route["cost_class"],
        "latency_ms": response.latency_ms,
        "request_count": 1,
        "retry_count": 0,
        "parallel_fanout_attempted": False,
        "expected_text": expected_text,
        "expected_text_observed": expected_text in response_text,
        "response_preview_bounded": response_text[:160],
        "response_text_length": len(response_text),
        "changed_files": [],
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "commands_started_by_provider": False,
        "codex_history_sent": False,
        "repo_context_sent": False,
        "runtime_context_bridge_used": False,
        "runtime_context_file_bridge_used": False,
        "bridge_or_file_bridge_used": False,
        **_direct_provider_proof_fields(direct_provider_response_observed=True),
        **request_metadata,
        "response_profile": response_metadata["response_profile"],
        "response_shape": response_metadata["response_shape"],
    }
