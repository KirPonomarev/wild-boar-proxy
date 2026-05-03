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
    registry = read_json(paths.registry_file)
    state = read_json(paths.state_file, required=False)
    desired_mode = get_desired_mode(paths)
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
    health_payload = run_healthcheck(paths)

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
    models_ok = False
    responses_ok = False
    model_name = model or get_model(paths)
    error_detail = ""

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
            error_detail = f"HTTP {exc.code}"
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

    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=liveness,
        severity=severity,
        operator_action=operator_action,
        changed_files=[],
        extra={
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
        },
    )


def mode_get(paths: RuntimePaths) -> dict[str, Any]:
    state = read_json(paths.state_file, required=False)
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
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
            "effective_mode": effective_mode,
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
