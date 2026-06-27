"""Observed state, locks, and evidence helpers for external-models."""

from __future__ import annotations

import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from wild_boar_proxy import state_store
from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors

LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 60.0
EVIDENCE_SUFFIX_SAFE_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            f"State file is not valid JSON: {path}",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        ) from exc


def _schema_invalid(message: str) -> None:
    raise RuntimeErrorInfo(
        message,
        machine_error_code=errors.SCHEMA_INVALID,
        operator_action="stop",
    )


def _unsupported_schema_version(message: str) -> None:
    raise RuntimeErrorInfo(
        message,
        machine_error_code=errors.UNSUPPORTED_SCHEMA_VERSION,
        operator_action="stop",
    )


def _require_dict(value: Any, *, surface_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _schema_invalid(f"{surface_name} must be a JSON object.")
    return value


def _require_string(value: Any, *, field_name: str, surface_name: str) -> str:
    if not isinstance(value, str):
        _schema_invalid(f"{surface_name} field {field_name} is missing or invalid.")
    return value


def _require_bool(value: Any, *, field_name: str, surface_name: str) -> bool:
    if not isinstance(value, bool):
        _schema_invalid(f"{surface_name} field {field_name} is missing or invalid.")
    return value


def _require_int_or_none(value: Any, *, field_name: str, surface_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        _schema_invalid(f"{surface_name} field {field_name} is missing or invalid.")
    return value


def _require_string_or_none(value: Any, *, field_name: str, surface_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _schema_invalid(f"{surface_name} field {field_name} is missing or invalid.")
    return value


def _require_string_list(value: Any, *, field_name: str, surface_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _schema_invalid(f"{surface_name} field {field_name} is missing or invalid.")
    return value


def _require_sha256_hex(value: Any, *, field_name: str, surface_name: str) -> str:
    digest = _require_string(value, field_name=field_name, surface_name=surface_name)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        _schema_invalid(f"{surface_name} field {field_name} is missing or invalid.")
    return digest


def _require_exact_fields(
    payload: dict[str, Any],
    *,
    required_fields: frozenset[str],
    surface_name: str,
) -> None:
    missing = sorted(required_fields - payload.keys())
    unexpected = sorted(set(payload.keys()) - required_fields)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        _schema_invalid(f"{surface_name} is invalid: {', '.join(details)}")


def _validate_observed_routes_payload(payload: Any) -> dict[str, dict[str, Any]]:
    routes_payload = _require_dict(payload, surface_name="external-models state routes")
    for route_id, route_state in routes_payload.items():
        route_id_error = contracts.route_id_validation_error(route_id)
        if route_id_error:
            _schema_invalid(route_id_error)
        route_state_dict = _require_dict(
            route_state,
            surface_name=f"external-models state routes[{route_id}]",
        )
        unexpected = sorted(
            set(route_state_dict.keys()) - contracts.OBSERVED_ROUTE_ALLOWED_FIELDS
        )
        if unexpected:
            _schema_invalid(
                "external-models state routes "
                f"[{route_id}] has unexpected fields: {unexpected}"
            )
        for field_name, value in route_state_dict.items():
            surface_name = f"external-models state routes[{route_id}]"
            if field_name in {
                "availability_state",
                "direct_provider_error",
                "evidence_level",
                "last_verified_at",
                "last_validate",
                "last_check",
                "last_error",
                "effective_model",
            }:
                _require_string(value, field_name=field_name, surface_name=surface_name)
            elif field_name == "latency_ms":
                _require_int_or_none(value, field_name=field_name, surface_name=surface_name)
            elif field_name in {
                "fallback_used",
                "bridge_green_counts_as_provider_proof",
                "bridge_live_response_observed",
            }:
                _require_bool(value, field_name=field_name, surface_name=surface_name)
    return routes_payload


def _validate_state_payload(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != contracts.STATE_SCHEMA_VERSION:
        _unsupported_schema_version("Unsupported external-models state schema version.")
    _require_exact_fields(
        payload,
        required_fields=contracts.STATE_TOP_LEVEL_FIELDS,
        surface_name="external-models state payload",
    )

    policy = _require_dict(payload.get("policy"), surface_name="external-models state policy")
    _require_exact_fields(
        policy,
        required_fields=contracts.STATE_POLICY_FIELDS,
        surface_name="external-models state policy",
    )
    _require_bool(
        policy.get("paid_routes_enabled"),
        field_name="paid_routes_enabled",
        surface_name="external-models state policy",
    )
    _require_string_list(
        policy.get("paid_route_allowlist"),
        field_name="paid_route_allowlist",
        surface_name="external-models state policy",
    )
    _require_string(
        policy.get("paid_route_default"),
        field_name="paid_route_default",
        surface_name="external-models state policy",
    )

    adapter = _require_dict(payload.get("adapter"), surface_name="external-models state adapter")
    _require_exact_fields(
        adapter,
        required_fields=contracts.STATE_ADAPTER_FIELDS,
        surface_name="external-models state adapter",
    )
    _require_string(
        adapter.get("lifecycle_mode"),
        field_name="lifecycle_mode",
        surface_name="external-models state adapter",
    )
    _require_string(
        adapter.get("state"),
        field_name="state",
        surface_name="external-models state adapter",
    )
    _require_string(
        adapter.get("host"),
        field_name="host",
        surface_name="external-models state adapter",
    )
    _require_int_or_none(
        adapter.get("port"),
        field_name="port",
        surface_name="external-models state adapter",
    )
    _require_string_or_none(
        adapter.get("base_url"),
        field_name="base_url",
        surface_name="external-models state adapter",
    )
    _require_bool(
        adapter.get("listener_proven"),
        field_name="listener_proven",
        surface_name="external-models state adapter",
    )
    _require_bool(
        adapter.get("runtime_claim_blocked"),
        field_name="runtime_claim_blocked",
        surface_name="external-models state adapter",
    )
    _require_string_or_none(
        adapter.get("started_at_utc"),
        field_name="started_at_utc",
        surface_name="external-models state adapter",
    )
    _require_string(
        adapter.get("last_transition"),
        field_name="last_transition",
        surface_name="external-models state adapter",
    )

    local_auth = _require_dict(
        payload.get("local_auth"),
        surface_name="external-models state local_auth",
    )
    _require_exact_fields(
        local_auth,
        required_fields=contracts.STATE_LOCAL_AUTH_FIELDS,
        surface_name="external-models state local_auth",
    )
    _require_string(
        local_auth.get("token_ref"),
        field_name="token_ref",
        surface_name="external-models state local_auth",
    )
    _require_bool(
        local_auth.get("token_present"),
        field_name="token_present",
        surface_name="external-models state local_auth",
    )
    _require_string_or_none(
        local_auth.get("token_created_at_utc"),
        field_name="token_created_at_utc",
        surface_name="external-models state local_auth",
    )

    _validate_observed_routes_payload(payload.get("routes"))


def _validate_evidence_result(
    payload: Any,
    *,
    route_id: str,
    surface_name: str,
) -> dict[str, Any]:
    result = _require_dict(payload, surface_name=f"{surface_name} result")
    required_fields = frozenset(
        {
            "status",
            "machine_error_code",
            "requested_model",
            "effective_model",
            "provider",
            "fallback_used",
            "fallback_chain",
            "cost_class",
            "latency_ms",
        }
    )
    missing = sorted(required_fields - result.keys())
    if missing:
        _schema_invalid(f"{surface_name} result is invalid: missing={missing}")
    requested_model = _require_string(
        result.get("requested_model"),
        field_name="requested_model",
        surface_name=f"{surface_name} result",
    )
    if requested_model != route_id:
        _schema_invalid(
            f"{surface_name} result field requested_model must match route_id."
        )
    _require_string(
        result.get("status"),
        field_name="status",
        surface_name=f"{surface_name} result",
    )
    _require_string(
        result.get("machine_error_code"),
        field_name="machine_error_code",
        surface_name=f"{surface_name} result",
    )
    _require_string_or_none(
        result.get("effective_model"),
        field_name="effective_model",
        surface_name=f"{surface_name} result",
    )
    _require_string(
        result.get("provider"),
        field_name="provider",
        surface_name=f"{surface_name} result",
    )
    _require_bool(
        result.get("fallback_used"),
        field_name="fallback_used",
        surface_name=f"{surface_name} result",
    )
    _require_string_list(
        result.get("fallback_chain"),
        field_name="fallback_chain",
        surface_name=f"{surface_name} result",
    )
    _require_string(
        result.get("cost_class"),
        field_name="cost_class",
        surface_name=f"{surface_name} result",
    )
    _require_int_or_none(
        result.get("latency_ms"),
        field_name="latency_ms",
        surface_name=f"{surface_name} result",
    )
    if "verification_scope" in result:
        _require_string(
            result.get("verification_scope"),
            field_name="verification_scope",
            surface_name=f"{surface_name} result",
        )
    return result


def _validate_evidence_payload(payload: dict[str, Any]) -> None:
    required_fields = frozenset(
        {
            "schema_version",
            "captured_at_utc",
            "route_id",
            "command_context",
            "network_dependent_evidence",
            "result",
            "artifact_sha256",
        }
    )
    allowed_fields = required_fields | frozenset({"verification_scope"})
    missing = sorted(required_fields - payload.keys())
    unexpected = sorted(set(payload.keys()) - allowed_fields)
    if missing or unexpected:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        _schema_invalid(f"external-models evidence payload is invalid: {', '.join(details)}")
    if payload.get("schema_version") != contracts.EVIDENCE_SCHEMA_VERSION:
        _unsupported_schema_version("Unsupported external-models evidence schema version.")
    route_id = _require_string(
        payload.get("route_id"),
        field_name="route_id",
        surface_name="external-models evidence payload",
    )
    route_id_error = contracts.route_id_validation_error(route_id)
    if route_id_error:
        _schema_invalid(route_id_error)
    _require_string(
        payload.get("captured_at_utc"),
        field_name="captured_at_utc",
        surface_name="external-models evidence payload",
    )
    _require_string(
        payload.get("command_context"),
        field_name="command_context",
        surface_name="external-models evidence payload",
    )
    network_dependent = _require_bool(
        payload.get("network_dependent_evidence"),
        field_name="network_dependent_evidence",
        surface_name="external-models evidence payload",
    )
    result = _validate_evidence_result(
        payload.get("result"),
        route_id=route_id,
        surface_name="external-models evidence payload",
    )
    verification_scope = payload.get("verification_scope")
    if network_dependent:
        _require_string(
            verification_scope,
            field_name="verification_scope",
            surface_name="external-models evidence payload",
        )
    elif verification_scope is not None:
        _schema_invalid(
            "external-models evidence payload must not declare verification_scope for local evidence."
        )
    result_verification_scope = result.get("verification_scope")
    if verification_scope is not None and result_verification_scope not in {None, verification_scope}:
        _schema_invalid(
            "external-models evidence payload result verification_scope must match top-level verification_scope."
        )
    artifact_sha256 = _require_sha256_hex(
        payload.get("artifact_sha256"),
        field_name="artifact_sha256",
        surface_name="external-models evidence payload",
    )
    canonical_payload = dict(payload)
    canonical_payload.pop("artifact_sha256", None)
    expected_sha256 = hashlib.sha256(
        json.dumps(canonical_payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    if artifact_sha256 != expected_sha256:
        _schema_invalid("external-models evidence payload artifact_sha256 does not match payload.")


def atomic_write_json(
    path: Path,
    payload: Any,
    *,
    validator: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    if not isinstance(payload, dict):
        _schema_invalid(f"External-models JSON payload must be an object: {path}")
    if validator is not None:
        validator(payload)
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
    )


def atomic_write_text(path: Path, text: str, *, mode: int | None = None) -> None:
    try:
        state_store.write_text(path, text, mode=mode)
    except state_store.StateStoreError as exc:
        raise RuntimeErrorInfo(
            f"Failed to write external-models state file: {path}",
            machine_error_code=errors.STATE_WRITE_FAILED,
            operator_action="retry",
            exit_code=1,
        ) from exc


def write_secrets_file_text(path: Path, text: str) -> None:
    atomic_write_text(path, text, mode=0o600)


@contextmanager
def serialized_lock(path: Path) -> Iterator[None]:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "created_at_utc": contracts.utc_now_iso(),
            "created_at_monotonic": time.monotonic(),
        }
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True)
            break
        except FileExistsError:
            existing = None
            try:
                existing = _read_json(path)
            except RuntimeErrorInfo:
                existing = None
            created_at = 0.0
            pid = -1
            if isinstance(existing, dict):
                created_at = float(existing.get("created_at_monotonic", 0.0))
                pid = int(existing.get("pid", -1))
            lock_is_stale = (pid > 0 and not _pid_alive(pid)) or (
                created_at > 0.0 and (time.monotonic() - created_at) > STALE_LOCK_SECONDS
            )
            if lock_is_stale:
                path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise RuntimeErrorInfo(
                    f"Timed out waiting for lock: {path}",
                    machine_error_code=errors.LOCK_TIMEOUT,
                    operator_action="retry",
                    exit_code=1,
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


@contextmanager
def dual_lock(first: Path, second: Path) -> Iterator[None]:
    with serialized_lock(first):
        with serialized_lock(second):
            yield


def load_state_file(state_file: Path) -> dict[str, Any]:
    if not state_file.exists():
        return contracts.default_state_payload()
    payload = _read_json(state_file)
    if not isinstance(payload, dict):
        raise RuntimeErrorInfo(
            "External-models state must be a JSON object.",
            machine_error_code=errors.STATE_CORRUPT,
            operator_action="stop",
        )
    schema_version = payload.get("schema_version")
    if schema_version == 1:
        migrated = contracts.default_state_payload()
        migrated["policy"] = dict(payload.get("policy", migrated["policy"]))
        migrated["routes"] = dict(payload.get("routes", {}))
        return migrated
    if schema_version != contracts.STATE_SCHEMA_VERSION:
        raise RuntimeErrorInfo(
            "Unsupported external-models state schema version.",
            machine_error_code=errors.UNSUPPORTED_SCHEMA_VERSION,
            operator_action="stop",
        )
    return payload


def write_state_file(state_file: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(state_file, payload, validator=_validate_state_payload)


def write_evidence_file(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(path, payload, validator=_validate_evidence_payload)


def build_evidence_artifact_path(
    *,
    evidence_dir: Path,
    route_id: object,
    suffix: str,
) -> Path:
    route_id_error = contracts.route_id_validation_error(route_id)
    if route_id_error:
        raise RuntimeErrorInfo(
            route_id_error,
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if not suffix or any(char not in EVIDENCE_SUFFIX_SAFE_CHARS for char in suffix):
        raise RuntimeErrorInfo(
            "Evidence artifact suffix is invalid.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_root = evidence_dir.resolve()
    path = evidence_dir / f"{route_id}-{suffix}.json"
    resolved_path = path.resolve()
    if not resolved_path.is_relative_to(evidence_root):
        raise RuntimeErrorInfo(
            "Evidence artifact path must stay within evidence_dir.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    return path


def ensure_secrets_permissions(secrets_file: Path) -> None:
    if not secrets_file.exists():
        return
    mode = secrets_file.stat().st_mode & 0o777
    if mode != 0o600:
        raise RuntimeErrorInfo(
            f"Unsafe permissions on secrets file: {secrets_file}",
            machine_error_code=errors.UNSAFE_SECRET_PERMISSIONS,
            operator_action="user_action",
        )


def capture_local_evidence(
    *,
    evidence_dir: Path,
    route: dict[str, Any],
    packet: dict[str, Any],
) -> Path:
    route_id = route.get("route_id")
    stamp = contracts.utc_now_iso().replace(":", "").replace("-", "")
    payload = {
        "schema_version": contracts.EVIDENCE_SCHEMA_VERSION,
        "captured_at_utc": contracts.utc_now_iso(),
        "route_id": route_id,
        "command_context": "external-models evidence capture",
        "network_dependent_evidence": False,
        "result": {
            "status": packet["status"],
            "machine_error_code": packet["machine_error_code"],
            "requested_model": route_id,
            "effective_model": None,
            "provider": route["provider"],
            "fallback_used": False,
            "fallback_chain": [route_id],
            "cost_class": route["cost_class"],
            "latency_ms": None,
        },
    }
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    path = build_evidence_artifact_path(
        evidence_dir=evidence_dir,
        route_id=route_id,
        suffix=stamp,
    )
    write_evidence_file(path, payload)
    return path
