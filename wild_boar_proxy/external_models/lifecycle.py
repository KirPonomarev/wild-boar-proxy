"""Synthetic lifecycle helpers for the external-models C2 slice."""

from __future__ import annotations

import base64
import os
import secrets
import socket
from pathlib import Path
from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import contracts, errors
from .paths import ExternalModelsPaths
from .state import (
    dual_lock,
    ensure_secrets_permissions,
    load_state_file,
    write_state_file,
)

RESERVED_PORTS = {8318, 8320}
TOKEN_KEY = "WBP_EXTERNAL_MODELS_LOCAL_TOKEN"


def _parse_secrets_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_secrets_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={values[key]}" for key in sorted(values)]
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.chmod(temp_path, 0o600)
    temp_path.replace(path)
    os.chmod(path, 0o600)


def ensure_local_token(paths: ExternalModelsPaths) -> tuple[bool, str | None]:
    ensure_secrets_permissions(paths.secrets_file)
    values = _parse_secrets_file(paths.secrets_file)
    if values.get(TOKEN_KEY):
        return False, None
    token = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("ascii").rstrip("=")
    values[TOKEN_KEY] = token
    _write_secrets_file(paths.secrets_file, values)
    return True, contracts.utc_now_iso()


def allocate_synthetic_port() -> int:
    for _ in range(32):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        if port not in RESERVED_PORTS:
            return port
    raise RuntimeErrorInfo(
        "Failed to allocate a synthetic external-models port.",
        machine_error_code=errors.PORT_ALLOCATION_FAILED,
        operator_action="retry",
    )


def start_synthetic_adapter(paths: ExternalModelsPaths) -> tuple[dict[str, Any], list[str], bool]:
    changed_files: list[str] = []
    token_created = False
    with dual_lock(paths.routes_lock, paths.state_lock):
        state_payload = load_state_file(paths.state_file)
        adapter = state_payload["adapter"]
        if adapter["state"] == "started":
            return state_payload, changed_files, token_created
        token_created, created_at = ensure_local_token(paths)
        if token_created:
            changed_files.append(str(paths.secrets_file))
            state_payload["local_auth"]["token_created_at_utc"] = created_at
        port = allocate_synthetic_port()
        state_payload["local_auth"]["token_present"] = True
        adapter.update(
            {
                "lifecycle_mode": "synthetic",
                "state": "started",
                "host": "127.0.0.1",
                "port": port,
                "base_url": f"http://127.0.0.1:{port}/v1",
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "started_at_utc": contracts.utc_now_iso(),
                "last_transition": "start",
            }
        )
        write_state_file(paths.state_file, state_payload)
        changed_files.append(str(paths.state_file))
    return state_payload, changed_files, token_created


def stop_synthetic_adapter(paths: ExternalModelsPaths) -> tuple[dict[str, Any], list[str]]:
    changed_files: list[str] = []
    with dual_lock(paths.routes_lock, paths.state_lock):
        state_payload = load_state_file(paths.state_file)
        adapter = state_payload["adapter"]
        if adapter["state"] == "stopped":
            return state_payload, changed_files
        adapter.update(
            {
                "lifecycle_mode": "synthetic",
                "state": "stopped",
                "host": "127.0.0.1",
                "port": None,
                "base_url": None,
                "listener_proven": False,
                "runtime_claim_blocked": True,
                "last_transition": "stop",
            }
        )
        write_state_file(paths.state_file, state_payload)
        changed_files.append(str(paths.state_file))
    return state_payload, changed_files


def synthetic_status_payload(paths: ExternalModelsPaths) -> dict[str, Any]:
    state_payload = load_state_file(paths.state_file)
    return {
        "foundation_phase": "C2",
        "adapter_runtime_available": False,
        "lifecycle_mode": state_payload["adapter"]["lifecycle_mode"],
        "adapter_state": state_payload["adapter"]["state"],
        "listener_proven": False,
        "runtime_claim_blocked": True,
        "profile_ready": False,
        "routes_count": len(_safe_routes(paths)),
        "observed_routes_count": len(state_payload["routes"]),
        "paths": {
            "routes_file": str(paths.routes_file),
            "state_file": str(paths.state_file),
            "secrets_file": str(paths.secrets_file),
            "evidence_dir": str(paths.evidence_dir),
        },
        "adapter": dict(state_payload["adapter"]),
        "local_auth": {
            "token_ref": state_payload["local_auth"]["token_ref"],
            "token_present": state_payload["local_auth"]["token_present"],
            "token_created_at_utc": state_payload["local_auth"]["token_created_at_utc"],
        },
    }


def _safe_routes(paths: ExternalModelsPaths) -> list[dict[str, Any]]:
    from .routes import list_routes

    return list_routes(paths)
