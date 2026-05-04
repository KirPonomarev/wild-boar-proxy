from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RuntimeErrorInfo(Exception):
    def __init__(
        self,
        message: str,
        *,
        machine_error_code: str,
        severity: str = "fatal",
        operator_action: str = "stop",
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.machine_error_code = machine_error_code
        self.severity = severity
        self.operator_action = operator_action
        self.exit_code = exit_code


@dataclass(frozen=True)
class RuntimePaths:
    profile_dir: Path
    managed_dir: Path
    stable_config: Path
    auth_file: Path
    config_toml: Path
    runtime_mode_file: Path
    runtime_effective_mode_file: Path
    registry_file: Path
    state_file: Path
    managed_config_file: Path
    launcher_script: Path
    sync_script: Path
    accounts_bin: Path
    onboard_bin: Path
    lock_file: Path
    repair_target_inventory_dir: Path
    repair_target_reference_file: Path
    target_switch_transaction_file: Path

    @classmethod
    def from_env(cls) -> "RuntimePaths":
        profile_dir = Path(
            os.environ.get("WBP_PROFILE_DIR", "~/.codex-custom-cli")
        ).expanduser()
        managed_dir = Path(
            os.environ.get("WBP_MANAGED_DIR", str(profile_dir / "managed"))
        ).expanduser()
        return cls(
            profile_dir=profile_dir,
            managed_dir=managed_dir,
            stable_config=Path(
                os.environ.get("WBP_STABLE_CONFIG", "~/.cli-proxy-api/config.yaml")
            ).expanduser(),
            auth_file=Path(
                os.environ.get("WBP_AUTH_FILE", str(profile_dir / "auth.json"))
            ).expanduser(),
            config_toml=Path(
                os.environ.get("WBP_CONFIG_TOML", str(profile_dir / "config.toml"))
            ).expanduser(),
            runtime_mode_file=Path(
                os.environ.get(
                    "WBP_RUNTIME_MODE_FILE", str(profile_dir / "runtime-mode.txt")
                )
            ).expanduser(),
            runtime_effective_mode_file=Path(
                os.environ.get(
                    "WBP_RUNTIME_EFFECTIVE_MODE_FILE",
                    str(profile_dir / "runtime-effective-mode.txt"),
                )
            ).expanduser(),
            registry_file=Path(
                os.environ.get(
                    "WBP_REGISTRY_FILE", str(managed_dir / "backend-registry.json")
                )
            ).expanduser(),
            state_file=Path(
                os.environ.get(
                    "WBP_STATE_FILE", str(managed_dir / "supervisor-state.json")
                )
            ).expanduser(),
            managed_config_file=Path(
                os.environ.get(
                    "WBP_MANAGED_CONFIG_FILE", str(managed_dir / "managed-config.yaml")
                )
            ).expanduser(),
            launcher_script=Path(
                os.environ.get(
                    "WBP_LAUNCHER_SCRIPT", str(profile_dir / "codex-custom-launch.sh")
                )
            ).expanduser(),
            sync_script=Path(
                os.environ.get(
                    "WBP_SYNC_SCRIPT", str(managed_dir / "supervisor-sync.sh")
                )
            ).expanduser(),
            accounts_bin=Path(
                os.environ.get(
                    "WBP_ACCOUNTS_BIN", str(managed_dir / "bin" / "codex-accounts")
                )
            ).expanduser(),
            onboard_bin=Path(
                os.environ.get(
                    "WBP_ONBOARD_BIN",
                    str(managed_dir / "bin" / "codex-account-onboard"),
                )
            ).expanduser(),
            lock_file=Path(
                os.environ.get(
                    "WBP_LOCK_FILE", str(managed_dir / "wild-boar-proxy.lock")
                )
            ).expanduser(),
            repair_target_inventory_dir=managed_dir / "stable-repair-target",
            repair_target_reference_file=managed_dir / "approved-repair-target.json",
            target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitized_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env.pop(key, None)
    env.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
    env.setdefault("no_proxy", env["NO_PROXY"])
    return env


def proxyless_urlopen(request: urllib.request.Request, timeout: int):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(request, timeout=timeout)


def read_json(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise RuntimeErrorInfo(
                f"Missing JSON file: {path}",
                machine_error_code="MISSING_JSON_FILE",
                operator_action="user_action",
            )
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            f"Invalid JSON in {path}: {exc}",
            machine_error_code="INVALID_JSON_FILE",
            operator_action="stop",
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeErrorInfo(
            f"Expected JSON object in {path}",
            machine_error_code="INVALID_JSON_SHAPE",
            operator_action="stop",
        )
    return data


def read_text(path: Path, *, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8").strip()


def read_simple_key_value(path: Path, key: str, separator: str) -> str:
    if not path.exists():
        return ""
    prefix = f"{key}{separator}"
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            if value.startswith('"') and value.endswith('"'):
                return value[1:-1]
            return value
    return ""


def read_yaml_value(path: Path, key: str) -> str:
    return read_simple_key_value(path, key, ":")


def read_toml_string(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*\"(.*)\"\s*$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if match:
            return match.group(1)
    return ""


def write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(value + "\n", encoding="utf-8")
    tmp_path.replace(path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, ensure_ascii=False))


def write_toml_string_atomic(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    pattern = re.compile(rf"^{re.escape(key)}\s*=")
    rewritten: list[str] = []
    for raw_line in lines:
        if pattern.match(raw_line.strip()):
            rewritten.append(f'{key} = "{value}"')
            updated = True
        else:
            rewritten.append(raw_line)
    if not updated:
        rewritten.append(f'{key} = "{value}"')
    write_text_atomic(path, "\n".join(rewritten))


def read_api_key(path: Path) -> str:
    data = read_json(path)
    api_key = data.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeErrorInfo(
            f"Missing OPENAI_API_KEY in {path}",
            machine_error_code="MISSING_API_KEY",
            operator_action="user_action",
        )
    return str(api_key)


def socket_is_listening(host: str, port: int) -> bool:
    sock = socket.socket()
    sock.settimeout(1)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def http_get_json(url: str, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {api_key}"}
    )
    with proxyless_urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeErrorInfo(
                f"Expected JSON object from {url}",
                machine_error_code="INVALID_HTTP_JSON",
                severity="recoverable",
                operator_action="retry",
            )
        return payload


def http_post_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with proxyless_urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeErrorInfo(
                f"Expected JSON object from {url}",
                machine_error_code="INVALID_HTTP_JSON",
                severity="recoverable",
                operator_action="retry",
            )
        return data


def get_model(paths: RuntimePaths, fallback: str = "gpt-5.4") -> str:
    return read_toml_string(paths.config_toml, "model") or fallback


def get_desired_mode(paths: RuntimePaths) -> str:
    mode = read_text(paths.runtime_mode_file, default="stable")
    return mode if mode in {"stable", "managed"} else "stable"


def get_effective_mode(paths: RuntimePaths, state: dict[str, Any]) -> str:
    mode = read_text(paths.runtime_effective_mode_file)
    if mode in {"stable", "managed"}:
        return mode
    state_mode = state.get("effective_mode")
    if state_mode in {"stable", "managed"}:
        return str(state_mode)
    return "stable"


def read_effective_mode_artifact(paths: RuntimePaths) -> str:
    mode = read_text(paths.runtime_effective_mode_file)
    return mode if mode in {"stable", "managed"} else ""


def reconcile_effective_mode_for_reporting(
    effective_mode: str, *, listener_ok: bool
) -> str:
    if effective_mode == "managed" and not listener_ok:
        return "stable"
    return effective_mode


def get_endpoint(paths: RuntimePaths, effective_mode: str) -> tuple[str, int, str]:
    if effective_mode == "managed":
        host = read_yaml_value(paths.managed_config_file, "host") or "127.0.0.1"
        port = int(read_yaml_value(paths.managed_config_file, "port") or "8320")
    else:
        host = read_yaml_value(paths.stable_config, "host") or "127.0.0.1"
        port = int(read_yaml_value(paths.stable_config, "port") or "8318")
    return host, port, f"http://{host}:{port}/v1"


def get_selected_backends_digest(state: dict[str, Any]) -> str:
    ids = state.get("selected_backend_ids") or []
    encoded = json.dumps(sorted(ids), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_auth_basename(auth_ref: Any) -> str:
    return Path(str(auth_ref or "")).name


def get_stable_auth_inventory_source(paths: RuntimePaths) -> tuple[Path, dict[str, Any]]:
    auth_dir_value = read_yaml_value(paths.stable_config, "auth-dir")
    if auth_dir_value:
        auth_dir_path = Path(auth_dir_value).expanduser()
        if auth_dir_path.is_absolute():
            path_resolution = "expanduser" if str(auth_dir_value).startswith("~") else "absolute"
            scan_path = auth_dir_path
        else:
            path_resolution = "stable_config_parent"
            scan_path = paths.stable_config.parent / auth_dir_path
        return scan_path, {
            "source": "auth-dir",
            "path": auth_dir_value,
            "path_resolution": path_resolution,
            "exists": scan_path.is_dir(),
        }

    scan_path = paths.stable_config.parent
    return scan_path, {
        "source": "stable_config_parent",
        "path": str(paths.stable_config.parent),
        "path_resolution": "fallback",
        "exists": scan_path.is_dir(),
    }


def get_backend_identifier(backend: dict[str, Any], index: int) -> str:
    backend_id = backend.get("id")
    if backend_id:
        return str(backend_id)
    return f"<missing-id:{index}>"


def get_registry_identity(registry: dict[str, Any]) -> dict[str, Any]:
    backends = registry.get("backends") or []
    backend_ids: dict[str, list[str]] = {}
    auth_basenames: dict[str, list[str]] = {}
    missing_auth_refs = []
    empty_auth_ref_backends = []
    invalid_auth_basenames = []

    for index, backend in enumerate(backends):
        backend_key = get_backend_identifier(backend, index)
        backend_id = backend.get("id")
        if backend_id:
            backend_ids.setdefault(str(backend_id), []).append(backend_key)

        if "auth_ref" not in backend:
            missing_auth_refs.append(backend_key)
            continue

        auth_ref = backend.get("auth_ref")
        if auth_ref is None or not str(auth_ref).strip():
            empty_auth_ref_backends.append(backend_key)
            continue

        auth_basename = get_auth_basename(auth_ref)
        if not auth_basename or auth_basename in {".", ".."}:
            invalid_auth_basenames.append(backend_key)
            continue
        auth_basenames.setdefault(auth_basename, []).append(backend_key)

    duplicate_backend_ids = sorted(
        backend_id for backend_id, matches in backend_ids.items() if len(matches) > 1
    )
    duplicate_auth_basenames = sorted(
        auth_basename
        for auth_basename, matches in auth_basenames.items()
        if len(matches) > 1
    )
    ambiguous = bool(
        duplicate_backend_ids
        or duplicate_auth_basenames
        or missing_auth_refs
        or empty_auth_ref_backends
        or invalid_auth_basenames
    )
    claim_blockers = [
        "stable-15-proved",
        "active-only-traffic",
        "pool-participation-correct",
    ]
    return {
        "status": "ambiguous" if ambiguous else "clear",
        "machine_error_code": "REGISTRY_IDENTITY_AMBIGUOUS" if ambiguous else "OK",
        "duplicate_backend_ids": duplicate_backend_ids,
        "duplicate_auth_basenames": duplicate_auth_basenames,
        "missing_auth_refs": sorted(missing_auth_refs),
        "empty_auth_ref_backends": sorted(empty_auth_ref_backends),
        "invalid_auth_basenames": sorted(invalid_auth_basenames),
        "claim_blockers": claim_blockers if ambiguous else [],
        "next_action": "inspect_registry_identity" if ambiguous else "none",
    }


def is_stable_auth_allowed(backend: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    if backend.get("enabled", True) is False:
        reasons.append("disabled")
    if backend.get("pool") != "active":
        reasons.append("pool_not_active")
    if bool(backend.get("manual_hold")):
        reasons.append("manual_hold")
    if str(backend.get("status", "")).lower() in {"down", "fatal", "retired"}:
        reasons.append("status_not_allowed")
    if not backend.get("auth_ref"):
        reasons.append("missing_auth_ref")
    return not reasons, reasons


def get_stable_policy_drift(paths: RuntimePaths, registry: dict[str, Any]) -> dict[str, Any]:
    backends = registry.get("backends") or []
    mapped_backends = {
        auth_basename: backend
        for backend in backends
        if (auth_basename := get_auth_basename(backend.get("auth_ref")))
    }
    allowed_auths = set()
    allowed_backends = []
    for auth_basename, backend in mapped_backends.items():
        allowed, _ = is_stable_auth_allowed(backend)
        if allowed:
            allowed_auths.add(auth_basename)
            allowed_backends.append((auth_basename, backend))

    configured_active_count = sum(
        1
        for backend in backends
        if backend.get("pool") == "active" and backend.get("enabled", True) is not False
    )
    stable_auth_dir, inventory_source = get_stable_auth_inventory_source(paths)
    claim_blockers = [
        "stable-15-proved",
        "active-only-traffic",
        "pool-participation-correct",
    ]
    if not stable_auth_dir.is_dir():
        return {
            "status": "unknown",
            "machine_error_code": "STABLE_POLICY_DRIFT_UNKNOWN",
            "configured_active_count": configured_active_count,
            "allowed_stable_auth_count": len(allowed_auths),
            "stable_auth_inventory_count": 0,
            "stable_auth_inventory_source": inventory_source,
            "disallowed_configured_auths": [],
            "missing_auths": [],
            "unknown_auths": [],
            "claim_blockers": claim_blockers[:2],
            "next_action": "inspect_stable_policy_drift",
        }

    inventory = sorted(path.name for path in stable_auth_dir.glob("codex-*.json"))
    inventory_set = set(inventory)
    disallowed_configured_auths = []
    missing_auths = []
    unknown_auths = []
    for auth_basename in inventory:
        backend = mapped_backends.get(auth_basename)
        if backend is None:
            unknown_auths.append(auth_basename)
            continue
        allowed, reasons = is_stable_auth_allowed(backend)
        if not allowed:
            disallowed_configured_auths.append(
                {
                    "backend_id": backend.get("id"),
                    "auth_basename": auth_basename,
                    "pool": backend.get("pool"),
                    "manual_hold": bool(backend.get("manual_hold")),
                    "status": backend.get("status"),
                    "enabled": backend.get("enabled", True),
                    "reason": ",".join(reasons),
                }
            )
    for auth_basename, backend in allowed_backends:
        if auth_basename not in inventory_set:
            missing_auths.append(
                {
                    "backend_id": backend.get("id"),
                    "auth_basename": auth_basename,
                    "pool": backend.get("pool"),
                    "manual_hold": bool(backend.get("manual_hold")),
                    "status": backend.get("status"),
                    "enabled": backend.get("enabled", True),
                    "reason": "auth_ref_not_in_stable_inventory",
                }
            )

    detected = bool(disallowed_configured_auths or missing_auths or unknown_auths)
    return {
        "status": "detected" if detected else "clear",
        "machine_error_code": "STABLE_POLICY_DRIFT" if detected else "OK",
        "configured_active_count": configured_active_count,
        "allowed_stable_auth_count": len(allowed_auths),
        "stable_auth_inventory_count": len(inventory),
        "stable_auth_inventory_source": inventory_source,
        "disallowed_configured_auths": disallowed_configured_auths,
        "missing_auths": missing_auths,
        "unknown_auths": unknown_auths,
        "claim_blockers": claim_blockers if detected else [],
        "next_action": "inspect_stable_policy_drift" if detected else "none",
    }


def summarize_registry_identity(registry_identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": registry_identity.get("status", "unknown"),
        "machine_error_code": registry_identity.get("machine_error_code", "UNKNOWN"),
    }


def get_claim_gate(
    policy_drift: dict[str, Any], registry_identity: dict[str, Any]
) -> dict[str, Any]:
    blocked_claims = set()
    sources = []
    if policy_drift.get("claim_blockers"):
        blocked_claims.update(str(claim) for claim in policy_drift["claim_blockers"])
        sources.append("policy_drift")
    if registry_identity.get("claim_blockers"):
        blocked_claims.update(str(claim) for claim in registry_identity["claim_blockers"])
        sources.append("registry_identity")

    blocked = bool(blocked_claims)
    return {
        "status": "blocked" if blocked else "clear",
        "machine_error_code": "CLAIM_GATE_BLOCKED" if blocked else "OK",
        "blocked_claims": sorted(blocked_claims),
        "sources": sources,
        "next_action": "inspect_claim_gate" if blocked else "none",
    }


def get_lock_preflight(paths: RuntimePaths) -> dict[str, Any]:
    if not paths.lock_file.exists():
        return {"status": "available", "machine_error_code": "OK", "holder_pid": None}

    holder = read_text(paths.lock_file)
    alive = bool(holder and process_is_alive(holder))
    return {
        "status": "held" if alive else "stale",
        "machine_error_code": "LOCK_HELD" if alive else "STALE_LOCK_FILE",
        "holder_pid": holder or None,
    }


TARGET_SWITCH_TRANSACTION_PHASES = ["snapshot", "stage", "verify", "switch", "rollback"]
TARGET_SWITCH_VERIFY_SCOPE = [
    "target_reference_correctness",
    "switch_completion_only",
    "transaction_completeness",
]
TARGET_SWITCH_FORBIDDEN_SURFACES = [
    "~/.cli-proxy-api",
    "engine_baseline_auth_storage",
    "backend-registry.json",
    "supervisor-state.json",
]
TARGET_SWITCH_DECLARED_WRITE_SURFACES = [
    "approved_control_target_reference_surface",
    "target_switch_transaction_metadata",
]
APPROVED_REPAIR_TARGET_SCHEMA_VERSION = 1
TARGET_SWITCH_TRANSACTION_METADATA_SCHEMA_VERSION = 1
APPROVED_REPAIR_TARGET_IDENTITY = "companion_managed_stable_auth_inventory"
APPROVED_REPAIR_TARGET_KIND = "control_owned_inventory_path"


def read_json_if_file(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    return read_json(path)


def build_approved_repair_target_file_payload(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "schema_version": APPROVED_REPAIR_TARGET_SCHEMA_VERSION,
        "target_identity": APPROVED_REPAIR_TARGET_IDENTITY,
        "target_kind": APPROVED_REPAIR_TARGET_KIND,
        "inventory_dir": str(paths.repair_target_inventory_dir),
        "ownership": "control_layer",
        "location_scope": "companion_managed_data",
    }


def build_target_switch_transaction_file_payload(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "schema_version": TARGET_SWITCH_TRANSACTION_METADATA_SCHEMA_VERSION,
        "transaction_status": "applied",
        "target_identity": APPROVED_REPAIR_TARGET_IDENTITY,
        "target_kind": APPROVED_REPAIR_TARGET_KIND,
        "inventory_dir": str(paths.repair_target_inventory_dir),
        "reference_file": str(paths.repair_target_reference_file),
        "ownership": "control_layer",
        "location_scope": "companion_managed_data",
    }


def get_target_switch_materialization_status(paths: RuntimePaths) -> str:
    expected_reference = build_approved_repair_target_file_payload(paths)
    expected_transaction = build_target_switch_transaction_file_payload(paths)
    approved_target = read_json_if_file(paths.repair_target_reference_file)
    transaction_surface = read_json_if_file(paths.target_switch_transaction_file)
    if (
        paths.repair_target_inventory_dir.is_dir()
        and approved_target == expected_reference
        and transaction_surface == expected_transaction
    ):
        return "applied_control_target_reference"
    return "declared_review_only"


def snapshot_candidate_paths(candidates: list[Path]) -> dict[Path, int]:
    result: dict[Path, int] = {}
    for candidate in candidates:
        if candidate.exists():
            result[candidate] = candidate.stat().st_mtime_ns
    return result


def snapshot_target_switch_guard_surfaces(paths: RuntimePaths) -> dict[str, Any]:
    stable_auth_dir, inventory_source = get_stable_auth_inventory_source(paths)
    stable_inventory = {}
    if stable_auth_dir.is_dir():
        stable_inventory = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(stable_auth_dir.glob("codex-*.json"))
        }
    return {
        "registry": paths.registry_file.read_text(encoding="utf-8"),
        "state": paths.state_file.read_text(encoding="utf-8"),
        "stable_config": paths.stable_config.read_text(encoding="utf-8"),
        "config_toml": paths.config_toml.read_text(encoding="utf-8"),
        "runtime_mode": paths.runtime_mode_file.read_text(encoding="utf-8"),
        "runtime_effective_mode": paths.runtime_effective_mode_file.read_text(
            encoding="utf-8"
        ),
        "observed_inventory_source": inventory_source,
        "stable_inventory": stable_inventory,
    }


def snapshot_path_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "missing"}
    if path.is_dir():
        return {"state": "dir"}
    return {"state": "file", "text": path.read_text(encoding="utf-8")}


def restore_path_state(path: Path, snapshot: dict[str, Any]) -> None:
    state = snapshot.get("state")
    if state == "missing":
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
        return
    if state == "dir":
        path.mkdir(parents=True, exist_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(str(snapshot.get("text", "")), encoding="utf-8")
    tmp_path.replace(path)


def rollback_target_switch_apply(
    paths: RuntimePaths,
    *,
    reference_snapshot: dict[str, Any],
    transaction_snapshot: dict[str, Any],
    target_dir_preexisted: bool,
) -> None:
    restore_path_state(paths.repair_target_reference_file, reference_snapshot)
    restore_path_state(paths.target_switch_transaction_file, transaction_snapshot)
    if (
        not target_dir_preexisted
        and paths.repair_target_inventory_dir.is_dir()
        and not any(paths.repair_target_inventory_dir.iterdir())
    ):
        paths.repair_target_inventory_dir.rmdir()


def get_approved_repair_target_reference(paths: RuntimePaths) -> dict[str, Any]:
    expected = build_approved_repair_target_file_payload(paths)
    materialized = read_json_if_file(paths.repair_target_reference_file)
    return {
        "status": (
            "materialized_aligned"
            if materialized == expected and paths.repair_target_inventory_dir.is_dir()
            else "fixed_not_materialized"
        ),
        "schema_version": APPROVED_REPAIR_TARGET_SCHEMA_VERSION,
        "target_identity": APPROVED_REPAIR_TARGET_IDENTITY,
        "target_kind": APPROVED_REPAIR_TARGET_KIND,
        "inventory_dir": str(paths.repair_target_inventory_dir),
        "reference_file": str(paths.repair_target_reference_file),
        "ownership": "control_layer",
        "location_scope": "companion_managed_data",
        "reference_file_exists": paths.repair_target_reference_file.exists(),
        "inventory_dir_exists": paths.repair_target_inventory_dir.is_dir(),
    }


def get_target_switch_transaction_metadata_surface(
    paths: RuntimePaths,
) -> dict[str, Any]:
    expected = build_target_switch_transaction_file_payload(paths)
    materialized = read_json_if_file(paths.target_switch_transaction_file)
    return {
        "status": (
            "materialized_aligned"
            if materialized == expected
            else "reserved_not_materialized"
        ),
        "schema_version": TARGET_SWITCH_TRANSACTION_METADATA_SCHEMA_VERSION,
        "transaction_file": str(paths.target_switch_transaction_file),
        "ownership": "control_layer",
        "location_scope": "companion_managed_data",
        "transaction_file_exists": paths.target_switch_transaction_file.exists(),
    }


def build_target_switch_surface_context(paths: RuntimePaths) -> dict[str, Any]:
    inventory_source = get_stable_auth_inventory_source(paths)[1]
    approved_target = get_approved_repair_target_reference(paths)
    transaction_metadata_surface = get_target_switch_transaction_metadata_surface(paths)
    return {
        "status": get_target_switch_materialization_status(paths),
        "observed_stable_inventory_source": inventory_source,
        "approved_repair_target_reference": approved_target,
        "target_switch_transaction_metadata_surface": transaction_metadata_surface,
        "mode_set_is_target_switch": False,
    }


def run_stable_target_switch_apply(paths: RuntimePaths) -> dict[str, Any]:
    lock_preflight = get_lock_preflight(paths)
    if lock_preflight.get("status") == "held":
        return build_command_payload(
            ok=False,
            human_message="Target switch apply blocked by mutation lock.",
            machine_error_code="LOCK_HELD",
            liveness="unknown",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={
                "next_action": "retry_after_lock_released",
                "command_mode": "apply",
                "target_surface": build_target_switch_surface_context(paths),
                "write_surface_declared": True,
                "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
            },
        )
    if lock_preflight.get("status") == "stale":
        return build_command_payload(
            ok=False,
            human_message="Target switch apply blocked by stale mutation lock.",
            machine_error_code="TARGET_SWITCH_APPLY_BLOCKED",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "inspect_stale_lock",
                "command_mode": "apply",
                "target_surface": build_target_switch_surface_context(paths),
                "write_surface_declared": True,
                "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
            },
        )

    if paths.repair_target_inventory_dir.exists() and not paths.repair_target_inventory_dir.is_dir():
        return build_command_payload(
            ok=False,
            human_message="Target switch apply blocked by invalid approved target directory.",
            machine_error_code="TARGET_SWITCH_INVALID_TARGET_DIR",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "inspect_target_switch_contract",
                "command_mode": "apply",
                "target_surface": build_target_switch_surface_context(paths),
                "write_surface_declared": True,
                "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
            },
        )
    if paths.repair_target_inventory_dir.is_dir() and any(
        paths.repair_target_inventory_dir.glob("codex-*.json")
    ):
        return build_command_payload(
            ok=False,
            human_message="Target switch apply blocked because the approved target inventory already contains auth files.",
            machine_error_code="TARGET_SWITCH_DIR_NOT_EMPTY",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "inspect_target_switch_contract",
                "command_mode": "apply",
                "target_surface": build_target_switch_surface_context(paths),
                "write_surface_declared": True,
                "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
            },
        )

    expected_reference = build_approved_repair_target_file_payload(paths)
    expected_transaction = build_target_switch_transaction_file_payload(paths)
    already_aligned = (
        paths.repair_target_inventory_dir.is_dir()
        and read_json_if_file(paths.repair_target_reference_file) == expected_reference
        and read_json_if_file(paths.target_switch_transaction_file) == expected_transaction
    )
    if already_aligned:
        return build_command_payload(
            ok=True,
            human_message="Target switch apply found the approved target already active.",
            machine_error_code="TARGET_SWITCH_ALREADY_ACTIVE",
            liveness="unknown",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "target_surface": build_target_switch_surface_context(paths),
                "write_surface_declared": True,
                "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
            },
        )

    guard_before = snapshot_target_switch_guard_surfaces(paths)
    before = snapshot_candidate_paths(
        [
            paths.repair_target_inventory_dir,
            paths.repair_target_reference_file,
            paths.target_switch_transaction_file,
        ]
    )
    reference_snapshot = snapshot_path_state(paths.repair_target_reference_file)
    transaction_snapshot = snapshot_path_state(paths.target_switch_transaction_file)
    target_dir_preexisted = paths.repair_target_inventory_dir.exists()

    try:
        with serialized_lock(paths):
            paths.repair_target_inventory_dir.mkdir(parents=True, exist_ok=True)
            write_json_atomic(paths.repair_target_reference_file, expected_reference)
            write_json_atomic(paths.target_switch_transaction_file, expected_transaction)
            if snapshot_target_switch_guard_surfaces(paths) != guard_before:
                raise RuntimeErrorInfo(
                    "Target switch apply verification failed because forbidden surfaces changed.",
                    machine_error_code="TARGET_SWITCH_VERIFICATION_FAILED",
                    severity="recoverable",
                    operator_action="user_action",
                )
            if read_json(paths.repair_target_reference_file) != expected_reference:
                raise RuntimeErrorInfo(
                    "Target switch apply verification failed for approved target reference.",
                    machine_error_code="TARGET_SWITCH_VERIFICATION_FAILED",
                    severity="recoverable",
                    operator_action="user_action",
                )
            if read_json(paths.target_switch_transaction_file) != expected_transaction:
                raise RuntimeErrorInfo(
                    "Target switch apply verification failed for transaction metadata.",
                    machine_error_code="TARGET_SWITCH_VERIFICATION_FAILED",
                    severity="recoverable",
                    operator_action="user_action",
                )
    except Exception as exc:
        rollback_target_switch_apply(
            paths,
            reference_snapshot=reference_snapshot,
            transaction_snapshot=transaction_snapshot,
            target_dir_preexisted=target_dir_preexisted,
        )
        if isinstance(exc, RuntimeErrorInfo):
            return build_command_payload(
                ok=False,
                human_message=exc.message,
                machine_error_code=exc.machine_error_code,
                liveness="unknown",
                severity=exc.severity,
                operator_action=exc.operator_action,
                changed_files=[],
                extra={
                    "next_action": exc.operator_action,
                    "command_mode": "apply",
                    "target_surface": build_target_switch_surface_context(paths),
                    "write_surface_declared": True,
                    "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                    "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                    "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                    "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
                },
                exit_code=exc.exit_code,
            )
        return build_command_payload(
            ok=False,
            human_message=f"Target switch apply failed: {exc}",
            machine_error_code="TARGET_SWITCH_APPLY_FAILED",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "inspect_target_switch_contract",
                "command_mode": "apply",
                "target_surface": build_target_switch_surface_context(paths),
                "write_surface_declared": True,
                "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
                "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
                "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
                "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
            },
        )

    changed_files = detect_changed_files(
        before,
        [
            paths.repair_target_inventory_dir,
            paths.repair_target_reference_file,
            paths.target_switch_transaction_file,
        ],
    )
    return build_command_payload(
        ok=True,
        human_message="Target switch apply completed on approved control-layer surfaces.",
        machine_error_code="TARGET_SWITCH_APPLIED",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=changed_files,
        extra={
            "command_mode": "apply",
            "target_surface": build_target_switch_surface_context(paths),
            "write_surface_declared": True,
            "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
            "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
            "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
            "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
        },
    )


def run_stable_target_switch_contract(
    paths: RuntimePaths, *, apply: bool
) -> dict[str, Any]:
    if apply:
        return run_stable_target_switch_apply(paths)
    extra = {
        "command_mode": "dry_run",
        "target_surface": build_target_switch_surface_context(paths),
        "write_surface_declared": True,
        "declared_write_surfaces": TARGET_SWITCH_DECLARED_WRITE_SURFACES,
        "forbidden_surfaces": TARGET_SWITCH_FORBIDDEN_SURFACES,
        "transaction_phases": TARGET_SWITCH_TRANSACTION_PHASES,
        "verify_scope": TARGET_SWITCH_VERIFY_SCOPE,
    }
    return build_command_payload(
        ok=True,
        human_message="Target switch contract surface is available.",
        machine_error_code="TARGET_SWITCH_CONTRACT_READY",
        liveness="unknown",
        severity="recoverable",
        operator_action="user_action",
        changed_files=[],
        extra={**extra, "next_action": "review_target_switch_contract"},
    )


def build_stable_repair_transaction_plan(
    paths: RuntimePaths,
    registry: dict[str, Any],
    policy_drift: dict[str, Any],
    lock_preflight: dict[str, Any],
) -> dict[str, Any]:
    backends = registry.get("backends") or []
    mapped_backends = {
        auth_basename: backend
        for backend in backends
        if (auth_basename := get_auth_basename(backend.get("auth_ref")))
    }
    stable_auth_dir, _ = get_stable_auth_inventory_source(paths)
    inventory = (
        sorted(path.name for path in stable_auth_dir.glob("codex-*.json"))
        if stable_auth_dir.is_dir()
        else []
    )
    inventory_set = set(inventory)
    allowed_auths = []
    would_keep = []
    for auth_basename, backend in sorted(mapped_backends.items()):
        allowed, _ = is_stable_auth_allowed(backend)
        if not allowed:
            continue
        item = {
            "backend_id": backend.get("id"),
            "auth_basename": auth_basename,
            "pool": backend.get("pool"),
            "status": backend.get("status"),
        }
        allowed_auths.append(item)
        if auth_basename in inventory_set:
            would_keep.append(item)

    would_remove = [
        {
            "auth_basename": auth_basename,
            "reason": "auth_not_in_registry",
        }
        for auth_basename in policy_drift.get("unknown_auths", [])
    ]
    would_remove.extend(
        {
            "backend_id": item.get("backend_id"),
            "auth_basename": item.get("auth_basename"),
            "reason": item.get("reason", "auth_not_allowed_by_registry_policy"),
        }
        for item in policy_drift.get("disallowed_configured_auths", [])
    )
    would_add = [
        {
            "backend_id": item.get("backend_id"),
            "auth_basename": item.get("auth_basename"),
            "reason": item.get("reason", "auth_ref_not_in_stable_inventory"),
        }
        for item in policy_drift.get("missing_auths", [])
    ]

    blocked_reasons = []
    if lock_preflight.get("status") == "held":
        blocked_reasons.append(
            {
                "machine_error_code": "LOCK_HELD",
                "reason": "mutation_lock_held",
                "holder_pid": lock_preflight.get("holder_pid"),
            }
        )
    elif lock_preflight.get("status") == "stale":
        blocked_reasons.append(
            {
                "machine_error_code": "STABLE_REPAIR_DRY_RUN_BLOCKED",
                "reason": "stale_lock_file_present",
                "holder_pid": lock_preflight.get("holder_pid"),
            }
        )

    return {
        "mode": "dry_run",
        "snapshot_required": True,
        "lock_required": True,
        "lock_preflight": lock_preflight,
        "stable_auth_inventory_source": policy_drift.get("stable_auth_inventory_source", {}),
        "approved_repair_target_reference": get_approved_repair_target_reference(paths),
        "target_switch_transaction_metadata_surface": (
            get_target_switch_transaction_metadata_surface(paths)
        ),
        "allowed_auths": allowed_auths,
        "disallowed_auths": policy_drift.get("disallowed_configured_auths", []),
        "missing_auths": policy_drift.get("missing_auths", []),
        "unknown_auths": policy_drift.get("unknown_auths", []),
        "would_add": would_add,
        "would_remove": sorted(would_remove, key=lambda item: item.get("auth_basename") or ""),
        "would_keep": would_keep,
        "blocked_reasons": blocked_reasons,
    }


def run_stable_repair_dry_run(paths: RuntimePaths) -> dict[str, Any]:
    registry = read_json(paths.registry_file)
    registry_identity = get_registry_identity(registry)
    policy_drift = get_stable_policy_drift(paths, registry)
    lock_preflight = get_lock_preflight(paths)
    transaction_plan = build_stable_repair_transaction_plan(
        paths, registry, policy_drift, lock_preflight
    )

    if registry_identity.get("status") != "clear":
        transaction_plan["blocked_reasons"].append(
            {
                "machine_error_code": "REGISTRY_IDENTITY_AMBIGUOUS",
                "reason": "registry_identity_ambiguous",
            }
        )
        return build_command_payload(
            ok=False,
            human_message="Stable repair dry-run blocked by ambiguous registry identity.",
            machine_error_code="REGISTRY_IDENTITY_AMBIGUOUS",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "inspect_registry_identity",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "registry_identity": registry_identity,
            },
        )

    if lock_preflight.get("status") == "held":
        return build_command_payload(
            ok=False,
            human_message="Stable repair dry-run blocked by mutation lock.",
            machine_error_code="LOCK_HELD",
            liveness="unknown",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={
                "next_action": "retry_after_lock_released",
                "would_change": False,
                "transaction_plan": transaction_plan,
            },
        )

    if lock_preflight.get("status") == "stale":
        return build_command_payload(
            ok=False,
            human_message="Stable repair dry-run blocked by stale mutation lock.",
            machine_error_code="STABLE_REPAIR_DRY_RUN_BLOCKED",
            liveness="unknown",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={
                "next_action": "inspect_stale_lock",
                "would_change": False,
                "transaction_plan": transaction_plan,
            },
        )

    if policy_drift.get("status") == "unknown":
        inventory_source = policy_drift.get("stable_auth_inventory_source", {})
        machine_error_code = (
            "STABLE_AUTH_DIR_MISSING"
            if inventory_source.get("exists") is False
            else "STABLE_POLICY_DRIFT_UNKNOWN"
        )
        transaction_plan["blocked_reasons"].append(
            {
                "machine_error_code": machine_error_code,
                "reason": "stable_auth_inventory_unavailable",
            }
        )
        return build_command_payload(
            ok=False,
            human_message="Stable repair dry-run blocked by unavailable stable auth inventory.",
            machine_error_code=machine_error_code,
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "next_action": "inspect_stable_policy_drift",
                "would_change": False,
                "transaction_plan": transaction_plan,
            },
        )

    if policy_drift.get("status") == "clear":
        return build_command_payload(
            ok=True,
            human_message="Stable repair dry-run completed; no repair needed.",
            machine_error_code="STABLE_REPAIR_NOT_NEEDED",
            liveness="unknown",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            extra={
                "would_change": False,
                "transaction_plan": transaction_plan,
            },
        )

    return build_command_payload(
        ok=True,
        human_message="Stable repair dry-run completed.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="user_action",
        changed_files=[],
        extra={
            "next_action": "review_transaction_plan",
            "would_change": True,
            "transaction_plan": transaction_plan,
        },
    )


def response_ok(payload: dict[str, Any]) -> bool:
    def iter_strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            strings: list[str] = []
            for nested in value.values():
                strings.extend(iter_strings(nested))
            return strings
        if isinstance(value, list):
            strings = []
            for nested in value:
                strings.extend(iter_strings(nested))
            return strings
        return []

    return any(item.strip() == "OK" for item in iter_strings(payload))


def is_proxy_path_error(error_detail: str) -> bool:
    lowered = error_detail.lower()
    return any(
        marker in lowered
        for marker in (
            "proxyconnect tcp",
            "proxy error",
            "socks connect tcp",
            "connection refused",
        )
    )


def parse_local_proxy_candidate(candidate: str) -> tuple[str, int] | None:
    try:
        parsed = urllib.parse.urlparse(candidate)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if not host or not port:
        return None
    if host not in {"localhost", "::1"} and not host.startswith("127."):
        return None
    return host, port


def get_proxy_reprobe_candidates(state: dict[str, Any]) -> list[str]:
    raw_candidates = []
    env_candidates = os.environ.get("WBP_PROXY_REPROBE_CANDIDATES", "")
    raw_candidates.extend(item.strip() for item in env_candidates.split(","))
    raw_candidates.append(str(state.get("current_proxy_url") or ""))

    candidates: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        if not candidate or candidate in seen:
            continue
        if parse_local_proxy_candidate(candidate) is None:
            continue
        candidates.append(candidate)
        seen.add(candidate)
        if len(candidates) >= 8:
            break
    return candidates


def probe_proxy_candidate(candidate: str) -> bool:
    parsed = parse_local_proxy_candidate(candidate)
    if parsed is None:
        return False
    host, port = parsed
    return socket_is_listening(host, port)


def run_proxy_reprobe(state: dict[str, Any]) -> dict[str, Any]:
    candidates = get_proxy_reprobe_candidates(state)
    for candidate in candidates:
        if probe_proxy_candidate(candidate):
            return {
                "attempted": True,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "found_candidate": True,
                "working_candidate": candidate,
            }
    return {
        "attempted": bool(candidates),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "found_candidate": False,
        "working_candidate": None,
    }


def process_is_alive(pid_text: str) -> bool:
    try:
        pid = int(pid_text.strip())
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def managed_pid_path(paths: RuntimePaths) -> Path:
    return paths.managed_dir / "managed-proxy.pid"


def reconcile_stable_fallback(
    paths: RuntimePaths,
    state: dict[str, Any],
    *,
    stable_endpoint: str,
    error_message: str,
    stable_listener_ok: bool,
) -> dict[str, Any]:
    stable_state = dict(state)
    stable_state["status"] = "failed"
    stable_state["last_error"] = error_message
    stable_state["effective_mode"] = "stable"
    stable_state["selected_backend_ids"] = []
    stable_state["healthy_count"] = 1 if stable_listener_ok else 0
    stable_state["degraded_count"] = 0
    stable_state["down_count"] = 1
    stable_state["last_sync_at"] = now_iso()

    with serialized_lock(paths):
        write_json_atomic(paths.state_file, stable_state)
        write_text_atomic(paths.runtime_effective_mode_file, "stable")
        write_toml_string_atomic(paths.config_toml, "base_url", stable_endpoint)
        managed_pid_path(paths).unlink(missing_ok=True)

    return read_json(paths.state_file, required=False)


@contextmanager
def serialized_lock(paths: RuntimePaths):
    paths.lock_file.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(paths.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            holder = read_text(paths.lock_file)
            if holder and process_is_alive(holder):
                raise RuntimeErrorInfo(
                    f"Mutation lock is held by pid {holder}.",
                    machine_error_code="LOCK_HELD",
                    severity="recoverable",
                    operator_action="retry",
                )
            paths.lock_file.unlink(missing_ok=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
        yield
    finally:
        paths.lock_file.unlink(missing_ok=True)


def build_command_payload(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    liveness: str,
    severity: str,
    operator_action: str,
    changed_files: list[str],
    extra: dict[str, Any] | None = None,
    exit_code: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok" if ok else "error",
        "exit_code": 0 if ok else (1 if exit_code is None else exit_code),
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": changed_files,
        "next_action": operator_action,
        "liveness": liveness,
        "severity": severity,
        "operator_action": operator_action,
    }
    if extra:
        payload.update(extra)
    return payload


def summarize_status(paths: RuntimePaths) -> dict[str, Any]:
    desired_mode = get_desired_mode(paths)
    health_payload = run_healthcheck(paths)
    registry = read_json(paths.registry_file)
    policy_drift = get_stable_policy_drift(paths, registry)
    registry_identity = get_registry_identity(registry)
    state = read_json(paths.state_file, required=False)
    current_proxy_url = state.get("current_proxy_url", "")
    pool_summary = {
        "active": int(state.get("active_count", 0) or 0),
        "reserve": int(state.get("reserve_count", 0) or 0),
        "retired": int(state.get("retired_count", 0) or 0),
        "healthy": int(state.get("healthy_count", 0) or 0),
        "degraded": int(state.get("degraded_count", 0) or 0),
        "down": int(state.get("down_count", 0) or 0),
        "selected_backend_ids": state.get("selected_backend_ids") or [],
        "backend_count": len(registry.get("backends") or []),
    }

    return build_command_payload(
        ok=health_payload["status"] == "ok",
        human_message=(
            "Runtime status summary is available."
            if health_payload["status"] == "ok"
            else "Runtime status summary reflects live attestation failure."
        ),
        machine_error_code=str(health_payload["machine_error_code"]),
        liveness=str(health_payload["liveness"]),
        severity=str(health_payload["severity"]),
        operator_action=str(health_payload["operator_action"]),
        changed_files=[],
        exit_code=int(health_payload["exit_code"]),
        extra={
            "desired_mode": desired_mode,
            "effective_mode": health_payload["effective_mode"],
            "endpoint": health_payload["endpoint"],
            "current_proxy_url": current_proxy_url,
            "pool_summary": pool_summary,
            "policy_drift": policy_drift,
            "registry_identity_summary": summarize_registry_identity(registry_identity),
            "claim_gate": get_claim_gate(policy_drift, registry_identity),
            "last_error": health_payload.get("last_error", state.get("last_error", "")),
            "attestation_summary": {
                "status": health_payload["status"],
                "machine_error_code": health_payload["machine_error_code"],
                "attestation_source": health_payload["attestation"]["attestation_source"],
                "observed_at_utc": health_payload["attestation"]["observed_at_utc"],
            },
        },
    )


def run_healthcheck(paths: RuntimePaths, model: str | None = None) -> dict[str, Any]:
    state = read_json(paths.state_file, required=False)
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
    host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
    configured_base_url = read_toml_string(paths.config_toml, "base_url")
    listener_ok = socket_is_listening(host, port)
    state_effective_mode = state.get("effective_mode")
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)

    stale_managed_residue = (
        state_effective_mode not in {None, "", "stable"}
        or bool(state.get("selected_backend_ids"))
        or managed_pid_path(paths).exists()
        or configured_base_url != reported_endpoint
    )
    if reported_effective_mode == "stable" and stale_managed_residue:
        stable_host, stable_port, _ = get_endpoint(paths, "stable")
        stable_listener_ok = socket_is_listening(stable_host, stable_port)
        error_message = state.get("last_error", "")
        if not error_message and effective_mode == "managed" and not listener_ok:
            error_message = (
                f"Listener is not reachable at {attestation_endpoint}; "
                f"effective endpoint is reconciled to {reported_endpoint}."
            )
        state = reconcile_stable_fallback(
            paths,
            state,
            stable_endpoint=reported_endpoint,
            error_message=error_message,
            stable_listener_ok=stable_listener_ok,
        )
        effective_mode = get_effective_mode(paths, state)
        host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
        configured_base_url = read_toml_string(paths.config_toml, "base_url")
        listener_ok = socket_is_listening(host, port)

    models_ok = False
    responses_ok = False
    model_name = model or get_model(paths)
    error_detail = ""
    proxy_reprobe: dict[str, Any] | None = None

    if listener_ok:
        api_key = read_api_key(paths.auth_file)
        try:
            models_payload = http_get_json(f"{attestation_endpoint}/models", api_key)
            models_ok = isinstance(models_payload.get("data"), list)
            responses_payload = http_post_json(
                f"{attestation_endpoint}/responses",
                api_key,
                {"model": model_name, "input": "Respond with exactly OK"},
            )
            responses_ok = response_ok(responses_payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore").strip()
            error_detail = f"HTTP {exc.code}: {detail}" if detail else f"HTTP {exc.code}"
        except urllib.error.URLError as exc:
            error_detail = str(exc.reason)
        except RuntimeErrorInfo:
            raise
        except Exception as exc:  # noqa: BLE001
            error_detail = str(exc)

    state_effective_mode = state.get("effective_mode")
    effective_mode_artifact = read_effective_mode_artifact(paths)
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
    expected_base_url = reported_endpoint
    base_url_match = configured_base_url == expected_base_url
    effective_mode_match = (
        state_effective_mode in {None, "", reported_effective_mode}
        and effective_mode_artifact == reported_effective_mode
    )

    if not listener_ok:
        liveness = "down"
        severity = "recoverable"
        operator_action = "retry"
        machine_error_code = "LISTENER_DOWN"
        if reported_endpoint != attestation_endpoint:
            human_message = (
                f"Listener is not reachable at {attestation_endpoint}; "
                f"effective endpoint is reconciled to {reported_endpoint}."
            )
        else:
            human_message = f"Listener is not reachable at {attestation_endpoint}."
        ok = False
    elif models_ok and responses_ok and base_url_match and effective_mode_match:
        liveness = "healthy"
        severity = "recoverable"
        operator_action = "none"
        machine_error_code = "OK"
        human_message = "Runtime attestation passed."
        ok = True
    else:
        liveness = "degraded"
        severity = "recoverable"
        operator_action = "retry"
        if listener_ok and is_proxy_path_error(error_detail):
            proxy_reprobe = run_proxy_reprobe(state)
            if proxy_reprobe["found_candidate"]:
                machine_error_code = "PROXY_PATH_BROKEN"
                human_message = (
                    "Runtime attestation failed because the outbound proxy path is broken; "
                    "a local proxy candidate is reachable."
                )
            else:
                machine_error_code = "PROXY_REPROBE_FAILED"
                human_message = (
                    "Runtime attestation failed because the outbound proxy path is broken; "
                    "no bounded local proxy candidate is reachable."
                )
        else:
            machine_error_code = "ATTESTATION_FAILED"
            human_message = "Runtime attestation failed one or more checks."
        ok = False

    attestation = {
        "listener_ok": listener_ok,
        "models_ok": models_ok,
        "responses_ok": responses_ok,
        "effective_mode_match": effective_mode_match,
        "base_url_match": base_url_match,
        "selected_backends_digest": get_selected_backends_digest(state),
        "observed_at_utc": now_iso(),
        "runtime_version": str(state.get("version", state.get("schema_version", "unknown"))),
        "attestation_source": "healthcheck --json",
    }
    extra = {
        "desired_mode": desired_mode,
        "effective_mode": reported_effective_mode,
        "endpoint": reported_endpoint,
        "attestation": attestation,
        "last_error": error_detail
        or (
            "Missing or invalid runtime-effective-mode.txt"
            if not effective_mode_artifact
            else state.get("last_error", "")
        ),
    }
    if proxy_reprobe is not None:
        extra["proxy_reprobe"] = proxy_reprobe

    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=liveness,
        severity=severity,
        operator_action=operator_action,
        changed_files=[],
        extra=extra,
    )


def mode_get(paths: RuntimePaths) -> dict[str, Any]:
    state = read_json(paths.state_file, required=False)
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
    host, port, _ = get_endpoint(paths, effective_mode)
    listener_ok = socket_is_listening(host, port)
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    return build_command_payload(
        ok=True,
        human_message="Mode values are available.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "desired_mode": desired_mode,
            "effective_mode": reported_effective_mode,
        },
    )


def mode_set(paths: RuntimePaths, mode: str) -> dict[str, Any]:
    if mode not in {"stable", "managed"}:
        raise RuntimeErrorInfo(
            f"Unsupported mode: {mode}",
            machine_error_code="INVALID_MODE",
            operator_action="user_action",
        )
    with serialized_lock(paths):
        write_text_atomic(paths.runtime_mode_file, mode)
    state = read_json(paths.state_file, required=False)
    effective_mode = get_effective_mode(paths, state)
    return build_command_payload(
        ok=True,
        human_message=f"Desired mode set to {mode}.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[str(paths.runtime_mode_file)],
        extra={
            "desired_mode": mode,
            "effective_mode": effective_mode,
        },
    )


def snapshot_known_files(paths: RuntimePaths) -> dict[Path, int]:
    candidates = [
        paths.registry_file,
        paths.state_file,
        paths.managed_config_file,
        paths.config_toml,
        paths.runtime_mode_file,
        paths.runtime_effective_mode_file,
    ]
    result: dict[Path, int] = {}
    for candidate in candidates:
        if candidate.exists():
            result[candidate] = candidate.stat().st_mtime_ns
    return result


def detect_changed_files(before: dict[Path, int], after_paths: list[Path]) -> list[str]:
    changed: list[str] = []
    for candidate in after_paths:
        if not candidate.exists():
            continue
        after = candidate.stat().st_mtime_ns
        if before.get(candidate) != after:
            changed.append(str(candidate))
    return changed


def get_launch_stabilization_seconds() -> float:
    raw = os.environ.get("WBP_LAUNCH_STABILIZATION_SECONDS", "30")
    try:
        value = float(raw)
    except ValueError:
        return 30.0
    return value if value >= 0 else 30.0


def run_launch_smoke(paths: RuntimePaths) -> dict[str, Any]:
    if not paths.launcher_script.exists():
        raise RuntimeErrorInfo(
            f"Missing launcher script: {paths.launcher_script}",
            machine_error_code="MISSING_LAUNCHER_SCRIPT",
            operator_action="user_action",
        )
    before = snapshot_known_files(paths)
    with serialized_lock(paths):
        result = subprocess.run(
            [str(paths.launcher_script), "smoke"],
            capture_output=True,
            text=True,
            env=sanitized_env(),
            check=False,
        )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.stdout:
        sys.stderr.write(result.stdout)

    changed_files = detect_changed_files(
        before,
        [
            paths.config_toml,
            paths.registry_file,
            paths.state_file,
            paths.managed_config_file,
            paths.runtime_effective_mode_file,
        ],
    )
    status_payload = summarize_status(paths)
    stabilization_seconds = get_launch_stabilization_seconds()
    if (
        result.returncode == 0
        and status_payload["status"] == "ok"
        and str(status_payload["effective_mode"]) == "managed"
        and stabilization_seconds > 0
    ):
        time.sleep(stabilization_seconds)
        status_payload = summarize_status(paths)
    desired_mode = str(status_payload["desired_mode"])
    effective_mode = str(status_payload["effective_mode"])
    launch_ok = result.returncode == 0 and status_payload["status"] == "ok"
    if launch_ok:
        machine_error_code = "OK"
        human_message = "Launcher smoke completed."
    elif result.returncode != 0:
        machine_error_code = "LAUNCHER_EXIT_NONZERO"
        human_message = "Launcher smoke exited non-zero."
    else:
        machine_error_code = str(status_payload["machine_error_code"])
        human_message = "Launcher smoke failed or did not remain in a healthy runtime state."
    return build_command_payload(
        ok=launch_ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=str(status_payload["liveness"]),
        severity=str(status_payload["severity"]),
        operator_action=str(status_payload["operator_action"]),
        changed_files=changed_files,
        extra={
            "desired_mode": desired_mode,
            "effective_mode": effective_mode,
            "endpoint": status_payload["endpoint"],
            "current_proxy_url": status_payload.get("current_proxy_url", ""),
            "attestation_summary": status_payload.get("attestation_summary", {}),
            "last_error": status_payload.get("last_error", ""),
            "launch_mode": "smoke",
            "launcher_exit_code": result.returncode,
            "stabilization_seconds": stabilization_seconds,
        },
        exit_code=result.returncode if result.returncode != 0 else status_payload["exit_code"],
    )


def run_sync(paths: RuntimePaths, model: str | None = None) -> dict[str, Any]:
    if not paths.sync_script.exists():
        raise RuntimeErrorInfo(
            f"Missing sync script: {paths.sync_script}",
            machine_error_code="MISSING_SYNC_SCRIPT",
            operator_action="user_action",
        )
    before = snapshot_known_files(paths)
    command = [str(paths.sync_script), model or get_model(paths)]
    with serialized_lock(paths):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=sanitized_env(),
            check=False,
        )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.stdout:
        sys.stderr.write(result.stdout)

    changed_files = detect_changed_files(
        before,
        [
            paths.registry_file,
            paths.state_file,
            paths.managed_config_file,
            paths.config_toml,
            paths.runtime_effective_mode_file,
        ],
    )
    state = read_json(paths.state_file, required=False)
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
    host, port, endpoint = get_endpoint(paths, effective_mode)
    listener_ok = socket_is_listening(host, port)
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)

    if result.returncode != 0:
        return build_command_payload(
            ok=False,
            human_message="Managed sync failed.",
            machine_error_code="SYNC_FAILED",
            liveness="down" if not listener_ok else "degraded",
            severity="recoverable",
            operator_action="retry",
            changed_files=changed_files,
            extra={
                "desired_mode": desired_mode,
                "effective_mode": reported_effective_mode,
                "endpoint": reported_endpoint,
                "last_error": state.get("last_error", result.stderr.strip()),
            },
            exit_code=result.returncode,
        )

    if not listener_ok:
        return build_command_payload(
            ok=False,
            human_message="Managed sync completed but managed listener is unavailable.",
            machine_error_code="SYNC_HEALTHCHECK_FAILED",
            liveness="down",
            severity="recoverable",
            operator_action="retry",
            changed_files=changed_files,
            extra={
                "desired_mode": desired_mode,
                "effective_mode": reported_effective_mode,
                "endpoint": reported_endpoint,
                "last_error": state.get("last_error", ""),
            },
            exit_code=1,
        )

    return build_command_payload(
        ok=True,
        human_message="Managed sync completed.",
        machine_error_code="OK",
        liveness="healthy" if listener_ok else "degraded",
        severity="recoverable",
        operator_action="none" if listener_ok else "retry",
        changed_files=changed_files,
        extra={
            "desired_mode": desired_mode,
            "effective_mode": reported_effective_mode,
            "endpoint": reported_endpoint,
            "last_error": state.get("last_error", ""),
        },
    )


def list_accounts(paths: RuntimePaths) -> dict[str, Any]:
    registry = read_json(paths.registry_file)
    return build_command_payload(
        ok=True,
        human_message="Account registry snapshot is available.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "accounts": registry.get("backends", []),
            "registry_identity": get_registry_identity(registry),
            "pool_policy": registry.get("pool_policy", {}),
            "stable_default_backend_id": registry.get("stable_default_backend_id"),
        },
    )


def run_accounts_command(
    paths: RuntimePaths,
    arguments: list[str],
    *,
    success_message: str,
    failure_message: str,
) -> dict[str, Any]:
    if not paths.accounts_bin.exists():
        raise RuntimeErrorInfo(
            f"Missing accounts command: {paths.accounts_bin}",
            machine_error_code="MISSING_ACCOUNTS_BIN",
            operator_action="user_action",
        )
    before = snapshot_known_files(paths)
    with serialized_lock(paths):
        result = subprocess.run(
            [str(paths.accounts_bin), *arguments],
            capture_output=True,
            text=True,
            env=sanitized_env(),
            check=False,
        )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.stdout:
        sys.stderr.write(result.stdout)

    changed_files = detect_changed_files(
        before,
        [paths.registry_file, paths.state_file, paths.runtime_effective_mode_file],
    )
    ok = result.returncode == 0
    return build_command_payload(
        ok=ok,
        human_message=success_message if ok else failure_message,
        machine_error_code="OK" if ok else "ACCOUNTS_COMMAND_FAILED",
        liveness="unknown",
        severity="recoverable",
        operator_action="none" if ok else "retry",
        changed_files=changed_files,
        extra={"command": arguments},
        exit_code=result.returncode if not ok else 0,
    )


def run_onboard(
    paths: RuntimePaths,
    *,
    auth_ref: str | None,
    skip_login: bool,
    no_sync: bool,
    non_interactive: bool,
) -> dict[str, Any]:
    if not paths.onboard_bin.exists():
        raise RuntimeErrorInfo(
            f"Missing onboarding command: {paths.onboard_bin}",
            machine_error_code="MISSING_ONBOARD_BIN",
            operator_action="user_action",
        )
    before = snapshot_known_files(paths)
    command = [str(paths.onboard_bin), "--once"]
    if auth_ref:
        command.extend(["--auth-ref", auth_ref])
    if skip_login:
        command.append("--skip-login")
    if no_sync:
        command.append("--no-sync")
    if non_interactive:
        command.append("--non-interactive")
    with serialized_lock(paths):
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=sanitized_env(),
            check=False,
        )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.stdout:
        sys.stderr.write(result.stdout)
    changed_files = detect_changed_files(
        before,
        [paths.registry_file, paths.state_file, paths.managed_config_file],
    )
    ok = result.returncode == 0
    return build_command_payload(
        ok=ok,
        human_message="Account onboarding completed." if ok else "Account onboarding failed.",
        machine_error_code="OK" if ok else "ONBOARD_FAILED",
        liveness="unknown",
        severity="recoverable",
        operator_action="none" if ok else "user_action",
        changed_files=changed_files,
        extra={"command": command[1:]},
        exit_code=result.returncode if not ok else 0,
    )


def export_diagnostics(paths: RuntimePaths) -> dict[str, Any]:
    registry = read_json(paths.registry_file)
    state = read_json(paths.state_file, required=False)
    export_dir = Path(tempfile.mkdtemp(prefix="wild-boar-proxy-diagnostics-"))

    redacted_registry = dict(registry)
    redacted_backends = []
    for backend in registry.get("backends", []):
        item = dict(backend)
        if "auth_ref" in item:
            item["auth_ref"] = Path(str(item["auth_ref"])).name
        if item.get("notes"):
            item["notes"] = "[redacted]"
        redacted_backends.append(item)
    redacted_registry["backends"] = redacted_backends

    (export_dir / "backend-registry.json").write_text(
        json.dumps(redacted_registry, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (export_dir / "supervisor-state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (export_dir / "runtime-mode.txt").write_text(
        read_text(paths.runtime_mode_file, default="stable") + "\n", encoding="utf-8"
    )
    (export_dir / "runtime-effective-mode.txt").write_text(
        read_text(paths.runtime_effective_mode_file, default="stable") + "\n",
        encoding="utf-8",
    )
    (export_dir / "metadata.json").write_text(
        json.dumps(
            {"generated_at_utc": now_iso(), "attestation_source": "diagnostics export --json"},
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return build_command_payload(
        ok=True,
        human_message="Diagnostics bundle exported.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[str(export_dir)],
        extra={"bundle_path": str(export_dir)},
    )
