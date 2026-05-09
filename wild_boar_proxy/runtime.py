# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager, nullcontext
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


DEFAULT_LAUNCHER_SCRIPT_NAME = "codex-custom-launch.sh"
REPO_MANAGED_DEFAULT_LAUNCHER_MARKER = "# WBP_REPO_MANAGED_DEFAULT_LAUNCHER=v1"
REPO_MANAGED_DEFAULT_LAUNCHER_DIGEST_PREFIX = (
    "# WBP_REPO_MANAGED_DEFAULT_LAUNCHER_SHA256="
)
CURRENT_PROXY_OWNER_PATH_LAUNCHER_MODE = "adopt-current-proxy-owner-path"
DETERMINISTIC_RUNTIME_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SYSTEM_OPEN_BIN = Path("/usr/bin/open")
ROTATION_EVIDENCE_SCHEMA_VERSION = 1
ROTATION_EVIDENCE_FRESHNESS_SECONDS = 15 * 60
SCALE_EVIDENCE_PACKET_SCHEMA_VERSION = 1
SCALE_EVIDENCE_FIELD_TARGET = "16"
SCALE_EVIDENCE_CLAIM_SCOPE = "field_evidence_observed_only"
SCALE_GATE_RUNTIME_ATTESTATION = "RUNTIME_ATTESTATION_GATE"
SCALE_GATE_STRICT_JSON_COMMAND_API = "STRICT_JSON_COMMAND_API_GATE"
SCALE_GATE_STATE_SERIALIZATION = "STATE_SERIALIZATION_GATE"
SCALE_GATE_FALLBACK_DRILL = "FALLBACK_DRILL_GATE"
SCALE_GATE_EVIDENCE_PACKET = "SCALE_EVIDENCE_PACKET_GATE"
SCALE_GATE_ORDER = [
    SCALE_GATE_RUNTIME_ATTESTATION,
    SCALE_GATE_STRICT_JSON_COMMAND_API,
    SCALE_GATE_STATE_SERIALIZATION,
    SCALE_GATE_FALLBACK_DRILL,
    SCALE_GATE_EVIDENCE_PACKET,
]
COMMAND_PAYLOAD_REQUIRED_FIELDS = [
    "status",
    "exit_code",
    "human_message",
    "machine_error_code",
    "changed_files",
    "next_action",
    "liveness",
    "severity",
    "operator_action",
]
SELECTED_BACKEND_SNAPSHOT_SCHEMA_VERSION = 1
SELECTED_BACKEND_SNAPSHOT_FIELD = "selected_backend_snapshot"
SELECTED_BACKEND_SNAPSHOT_KIND = "selected_backend_participation"
ROTATION_EVIDENCE_CLAIM_SCOPE = "bounded_local_participation_evidence_only"
BACKEND_REGISTRY_SCHEMA_VERSION = 2
VALID_BACKEND_REGISTRY_POOLS = {"active", "reserve", "retired"}
PROXY_REPROBE_MAX_CANDIDATES = 8
PROXY_REPROBE_CONCURRENCY_LIMIT = 1
PROXY_REPROBE_DEPTH = "shallow_socket_listener_only"
PROXY_REPROBE_STRATEGY = "sequential_first_success"
PROXY_REPROBE_CANDIDATE_SOURCE_ORDER = [
    "env.WBP_PROXY_REPROBE_CANDIDATES",
    "runtime_state.last_known_good_proxy_url",
    "runtime_state.current_proxy_url",
]
SELECTED_BACKEND_SNAPSHOT_ALLOWED_SOURCE_CLASSES = {
    "engine_observed",
    "runtime_observed",
    "supervisor_owner_observed",
    "external_owner_path_observed",
}
STAGED_POOL_POLICY_PACKETS: dict[str, dict[str, int]] = {
    "10": {"active_min": 10, "active_target": 10, "reserve_target": 0},
    "15": {"active_min": 15, "active_target": 15, "reserve_target": 0},
    "20": {"active_min": 20, "active_target": 20, "reserve_target": 0},
}
EXPERIMENTAL_PACKAGE_SCHEMA_VERSION = 1
EXPERIMENTAL_PACKAGE_ARTIFACT_NAME = "experimental-package.tar.gz"
EXPERIMENTAL_PACKAGE_MANIFEST_NAME = "experimental-package.manifest.json"
EXPERIMENTAL_PACKAGE_METADATA_NAME = "experimental-package.metadata.json"
EXPERIMENTAL_PACKAGE_ALLOWED_TOP_LEVEL_DIRS = {"wild_boar_proxy", "docs"}
EXPERIMENTAL_PACKAGE_ALLOWED_ROOT_SUFFIXES = {".md", ".txt"}
EXPERIMENTAL_PACKAGE_REPO_MARKER_FILE = "MASTER_PLAN.md"
EXPERIMENTAL_PACKAGE_REPO_MARKER_DIR = "wild_boar_proxy"
EXPERIMENTAL_PACKAGE_EXCLUDED_BASENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "auth.json",
    "auth.yaml",
    "auth.yml",
    "auth.toml",
    "backend-registry.json",
    "supervisor-state.json",
    "runtime-mode.txt",
    "runtime-effective-mode.txt",
    "stable-runtime-config.generated.yaml",
    "evidence-packet.json",
}
EXPERIMENTAL_PACKAGE_EXCLUDED_DIR_PARTS = {
    ".codex-custom-cli",
    "__pycache__",
    "cache",
    "caches",
    "log",
    "logs",
    "temp",
    "tmp",
}
EXPERIMENTAL_PACKAGE_EXCLUDED_FILE_SUFFIXES = {
    ".dump",
    ".dmp",
    ".key",
    ".lock",
    ".log",
    ".pid",
    ".secret",
    ".sqlite",
    ".sqlite3",
    ".temp",
    ".tmp",
    ".token",
}
EXPERIMENTAL_PACKAGE_EXCLUDED_STEM_TOKENS = {
    "dump",
    "dmp",
    "key",
    "private",
    "secret",
    "session",
    "temp",
    "tmp",
    "token",
}
SERIALIZED_LOCK_LOCAL_OWNERS: dict[str, dict[str, int]] = {}
SERIALIZED_LOCK_LOCAL_OWNERS_GUARD = threading.Lock()


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
    stable_runtime_generated_config_file: Path

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
                    "WBP_LAUNCHER_SCRIPT",
                    str(profile_dir / DEFAULT_LAUNCHER_SCRIPT_NAME),
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
            stable_runtime_generated_config_file=managed_dir
            / "stable-runtime-config.generated.yaml",
        )


@dataclass(frozen=True)
class StableRuntimeLaunchAttempt:
    desired_kind: str
    observed_path: Path
    activation_attempted: bool
    generated_config_regenerated: bool
    activation_method: str
    selected_config_file: str
    selected_source_kind: str
    selected_source_path: str
    launcher_exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CurrentProxyOwnerPathActivationAttempt:
    launcher_lane_eligibility: str
    launcher_readiness_status: str
    prerequisite_materialized: bool
    activation_attempted: bool
    activation_exit_code: int | None
    prior_current_proxy_url: str
    working_candidate: str
    rollback_surface_snapshots: dict[str, dict[str, Any]]


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
        CURRENT_PROXY_URL_HANDOFF_ENV,
    ):
        env.pop(key, None)
    env["PATH"] = DETERMINISTIC_RUNTIME_PATH
    env.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
    env.setdefault("no_proxy", env["NO_PROXY"])
    return env


def get_repo_owned_python_bin() -> str:
    candidate = Path(sys.executable).expanduser()
    if candidate.is_absolute() and candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return "/usr/bin/python3"


def build_launcher_subprocess_env(paths: RuntimePaths) -> dict[str, str]:
    env = sanitized_env()
    env["WBP_PYTHON_BIN"] = get_repo_owned_python_bin()
    env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
    env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
    env["WBP_STABLE_CONFIG"] = str(paths.stable_config)
    env["WBP_AUTH_FILE"] = str(paths.auth_file)
    env["WBP_CONFIG_TOML"] = str(paths.config_toml)
    env["WBP_RUNTIME_MODE_FILE"] = str(paths.runtime_mode_file)
    env["WBP_RUNTIME_EFFECTIVE_MODE_FILE"] = str(paths.runtime_effective_mode_file)
    env["WBP_REGISTRY_FILE"] = str(paths.registry_file)
    env["WBP_STATE_FILE"] = str(paths.state_file)
    env["WBP_MANAGED_CONFIG_FILE"] = str(paths.managed_config_file)
    env["WBP_LAUNCHER_SCRIPT"] = str(paths.launcher_script)
    env["WBP_SYNC_SCRIPT"] = str(paths.sync_script)
    env["WBP_LOCK_FILE"] = str(paths.lock_file)
    return env


def validate_launch_client_path(client_path_raw: str) -> tuple[Path, str]:
    candidate = Path(client_path_raw).expanduser()
    if not candidate.is_absolute():
        raise RuntimeErrorInfo(
            f"Client path must be absolute: {client_path_raw}",
            machine_error_code="CLIENT_PATH_NOT_ABSOLUTE",
            severity="recoverable",
            operator_action="user_action",
        )
    if not candidate.exists():
        raise RuntimeErrorInfo(
            f"Missing client path: {candidate}",
            machine_error_code="MISSING_CLIENT_PATH",
            severity="recoverable",
            operator_action="user_action",
        )
    if candidate.suffix == ".app" and candidate.is_dir():
        return candidate, "macos_app_bundle"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate, "executable"
    raise RuntimeErrorInfo(
        f"Unsupported client path shape: {candidate}",
        machine_error_code="CLIENT_PATH_INVALID",
        severity="recoverable",
        operator_action="user_action",
    )


def build_launch_client_profile_context(paths: RuntimePaths) -> dict[str, str]:
    return {
        "profile_dir": str(paths.profile_dir),
        "managed_dir": str(paths.managed_dir),
        "config_toml": str(paths.config_toml),
        "managed_config_file": str(paths.managed_config_file),
    }


def dispatch_external_client(
    paths: RuntimePaths, client_path: Path, client_path_kind: str
) -> dict[str, Any]:
    if client_path_kind == "macos_app_bundle":
        open_bin = str(SYSTEM_OPEN_BIN) if SYSTEM_OPEN_BIN.is_file() and os.access(SYSTEM_OPEN_BIN, os.X_OK) else None
        if not open_bin:
            raise RuntimeErrorInfo(
                "macOS app-bundle launch is unavailable because `open` is missing.",
                machine_error_code="CLIENT_LAUNCH_UNSUPPORTED_SHAPE",
                severity="recoverable",
                operator_action="user_action",
            )
        try:
            result = subprocess.run(
                [open_bin, "-a", str(client_path)],
                capture_output=True,
                text=True,
                env=sanitized_env(),
                check=False,
            )
        except OSError as exc:
            raise RuntimeErrorInfo(
                f"Host-client dispatch failed: {exc}",
                machine_error_code="CLIENT_LAUNCH_DISPATCH_FAILED",
                severity="recoverable",
                operator_action="retry",
            ) from exc
        return {
            "dispatch_method": "macos_open_app_bundle",
            "dispatch_observed": result.returncode == 0,
            "dispatch_exit_code": result.returncode,
            "stderr": result.stderr,
        }

    try:
        process = subprocess.Popen(
            [str(client_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=sanitized_env(),
            cwd=str(paths.profile_dir),
            start_new_session=True,
            text=False,
        )
    except OSError as exc:
        raise RuntimeErrorInfo(
            f"Host-client dispatch failed: {exc}",
            machine_error_code="CLIENT_LAUNCH_DISPATCH_FAILED",
            severity="recoverable",
            operator_action="retry",
        ) from exc
    return {
        "dispatch_method": "detached_executable_spawn",
        "dispatch_observed": True,
        "dispatch_exit_code": None,
        "stderr": "",
    }


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


def read_stable_proxy_url(paths: RuntimePaths) -> str:
    return read_yaml_value(paths.stable_config, "proxy-url")


def write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(value + "\n", encoding="utf-8")
    tmp_path.replace(path)


def write_executable_text_atomic(path: Path, value: str) -> None:
    write_text_atomic(path, value)
    path.chmod(0o755)


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


def is_transient_attestation_timeout_error(error_detail: str) -> bool:
    normalized = error_detail.strip().lower()
    return bool(normalized) and (
        "timed out" in normalized or "timeout" in normalized
    )


def get_rollout_attestation_retry_delay_seconds() -> float:
    raw = os.environ.get("WBP_ROLLOUT_ATTESTATION_RETRY_SECONDS", "0.5").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.5
    return value if value >= 0 else 0.5


def run_rollout_attestation_healthcheck(
    paths: RuntimePaths,
    *,
    allow_stable_fallback_write: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = run_healthcheck(
        paths,
        allow_recovery=False,
        allow_last_known_good_proxy_write=False,
        allow_current_proxy_auto_adoption=False,
        allow_stable_fallback_write=allow_stable_fallback_write,
    )
    last_error = str(payload.get("last_error", ""))
    retry_summary = {
        "status": "not_invoked",
        "attempted": False,
        "eligible": payload.get("machine_error_code") == "ATTESTATION_FAILED"
        and is_transient_attestation_timeout_error(last_error),
        "retry_delay_seconds": 0.0,
        "initial_status": str(payload.get("status", "")),
        "initial_machine_error_code": str(payload.get("machine_error_code", "")),
        "initial_last_error": last_error,
        "final_status": str(payload.get("status", "")),
        "final_machine_error_code": str(payload.get("machine_error_code", "")),
        "final_last_error": last_error,
        "outcome": "not_needed",
        "confirmation_basis": "",
        "guardrail_status": "not_invoked",
    }
    if not retry_summary["eligible"]:
        return payload, retry_summary

    retry_delay_seconds = get_rollout_attestation_retry_delay_seconds()
    retry_summary["status"] = "owner_path_emitted"
    retry_summary["attempted"] = True
    retry_summary["retry_delay_seconds"] = retry_delay_seconds
    retry_summary["outcome"] = "retry_failed"
    retry_summary["guardrail_status"] = "blocked"
    if retry_delay_seconds > 0:
        time.sleep(retry_delay_seconds)

    retried_payload = run_healthcheck(
        paths,
        allow_recovery=False,
        allow_last_known_good_proxy_write=False,
        allow_current_proxy_auto_adoption=False,
        allow_stable_fallback_write=allow_stable_fallback_write,
    )
    retried_last_error = str(retried_payload.get("last_error", ""))
    retry_summary["final_status"] = str(retried_payload.get("status", ""))
    retry_summary["final_machine_error_code"] = str(
        retried_payload.get("machine_error_code", "")
    )
    retry_summary["final_last_error"] = retried_last_error
    retry_summary["outcome"] = (
        "healthy_on_retry"
        if retried_payload.get("status") == "ok"
        and str(retried_payload.get("effective_mode")) == "managed"
        else "retry_failed"
    )
    if retry_summary["outcome"] == "healthy_on_retry":
        retry_summary["confirmation_basis"] = "retry_observation_only"
        retry_summary["guardrail_status"] = "observation_only"
    return retried_payload, retry_summary


def get_model(paths: RuntimePaths, fallback: str = "gpt-5.3-codex") -> str:
    return read_toml_string(paths.config_toml, "model") or fallback


def get_configured_proxy_url(paths: RuntimePaths, effective_mode: str) -> str:
    if effective_mode == "managed":
        return read_yaml_value(paths.managed_config_file, "proxy-url")
    return read_stable_proxy_url(paths)


def truth_drift_detail(
    *,
    configured_model: str,
    requested_model: str,
    model_match: bool,
    configured_proxy_url: str,
    current_proxy_url: str,
    proxy_url_match: bool,
) -> str:
    drift_parts: list[str] = []
    if not model_match:
        drift_parts.append(
            f"model drift: configured={configured_model or '<empty>'}, requested={requested_model or '<empty>'}"
        )
    if not proxy_url_match:
        drift_parts.append(
            f"proxy drift: configured={configured_proxy_url or '<empty>'}, current={current_proxy_url or '<empty>'}"
        )
    return "; ".join(drift_parts)


def build_launch_readiness_surface(
    *,
    owner_command_surface: str,
    delegated_from_status: bool,
    listener_ok: bool,
    models_ok: bool,
    responses_ok: bool,
    base_url_match: bool,
    effective_mode_match: bool,
    model_match: bool,
    proxy_url_match: bool,
    machine_error_code: str,
    error_detail: str,
    auth_pool_hygiene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if not listener_ok:
        failed_checks.append("listener_unreachable")
    if listener_ok and not models_ok:
        failed_checks.append("models_surface_unavailable_or_invalid")
    if listener_ok and models_ok and not responses_ok:
        failed_checks.append("responses_probe_failed")
    if not base_url_match:
        failed_checks.append("base_url_mismatch")
    if not effective_mode_match:
        failed_checks.append("effective_mode_truth_drift")
    if not model_match:
        failed_checks.append("model_truth_drift")
    if not proxy_url_match:
        failed_checks.append("proxy_truth_drift")
    auth_pool_hygiene_status = ""
    launch_capable_backend_count = None
    if isinstance(auth_pool_hygiene, dict):
        auth_pool_hygiene_status = str(auth_pool_hygiene.get("status", ""))
        launch_capable_backend_count = auth_pool_hygiene.get(
            "launch_capable_backend_count"
        )
        if (
            listener_ok
            and models_ok
            and not responses_ok
            and auth_pool_hygiene_status == "launch_capable_empty"
        ):
            failed_checks.insert(0, "usable_auth_pool_empty")
    gate_passed = not failed_checks
    return {
        "status": "ready" if gate_passed else "blocked",
        "owner_command_surface": owner_command_surface,
        "delegated_from_status": delegated_from_status,
        "real_inference_required": True,
        "listener_reachable": listener_ok,
        "models_surface_reachable": models_ok,
        "responses_proof_passed": responses_ok,
        "truth_alignment_passed": (
            base_url_match and effective_mode_match and model_match and proxy_url_match
        ),
        "base_url_match": base_url_match,
        "effective_mode_match": effective_mode_match,
        "model_match": model_match,
        "proxy_url_match": proxy_url_match,
        "gate_passed": gate_passed,
        "blocking_reason": "" if gate_passed else failed_checks[0],
        "failed_checks": failed_checks,
        "machine_error_code": machine_error_code,
        "last_error": error_detail,
        "auth_pool_hygiene_status": auth_pool_hygiene_status,
        "launch_capable_backend_count": launch_capable_backend_count,
    }


def build_runtime_guardrail_surface(
    paths: RuntimePaths,
    *,
    launch_readiness: dict[str, Any] | None,
    auth_pool_hygiene: dict[str, Any] | None,
    recovery_result: dict[str, Any] | None,
) -> dict[str, Any]:
    lock_preflight = get_lock_preflight(paths)
    failed_checks: list[str] = []
    lock_status = str(lock_preflight.get("status", "unknown"))
    if lock_status == "held":
        failed_checks.append("mutation_lock_held")
    elif lock_status == "stale":
        failed_checks.append("mutation_lock_stale")

    launch_status = ""
    launch_blocking_reason = ""
    if isinstance(launch_readiness, dict):
        launch_status = str(launch_readiness.get("status", ""))
        launch_blocking_reason = str(launch_readiness.get("blocking_reason", ""))
        if launch_status == "blocked" and launch_blocking_reason:
            failed_checks.append(launch_blocking_reason)

    auth_pool_status = ""
    auth_pool_blocking_reason = ""
    if isinstance(auth_pool_hygiene, dict):
        auth_pool_status = str(auth_pool_hygiene.get("status", ""))
        auth_pool_blocking_reason = str(auth_pool_hygiene.get("blocking_reason", ""))
        if auth_pool_status == "launch_capable_empty" and auth_pool_blocking_reason:
            if auth_pool_blocking_reason not in failed_checks:
                failed_checks.append(auth_pool_blocking_reason)

    recovery_guardrail_status = ""
    recovery_confirmation_basis = ""
    recovery_effectful_claim_allowed = None
    if isinstance(recovery_result, dict):
        recovery_guardrail_status = str(recovery_result.get("guardrail_status", ""))
        recovery_confirmation_basis = str(recovery_result.get("confirmation_basis", ""))
        recovery_effectful_claim_allowed = recovery_result.get("effectful_claim_allowed")
        if recovery_guardrail_status == "blocked":
            failed_checks.append("recovery_claim_blocked")

    if failed_checks:
        status = "blocked"
    elif recovery_guardrail_status == "observation_only":
        status = "caution"
    else:
        status = "clear"

    return {
        "status": status,
        "owner_command_surface": "healthcheck --json",
        "lock_status": lock_status,
        "launch_readiness_status": launch_status,
        "launch_blocking_reason": launch_blocking_reason,
        "auth_pool_hygiene_status": auth_pool_status,
        "auth_pool_blocking_reason": auth_pool_blocking_reason,
        "recovery_guardrail_status": recovery_guardrail_status,
        "recovery_confirmation_basis": recovery_confirmation_basis,
        "recovery_effectful_claim_allowed": recovery_effectful_claim_allowed,
        "failed_checks": failed_checks,
        "blocking_reason": "" if not failed_checks else failed_checks[0],
    }


def default_launcher_script_path(profile_dir: Path) -> Path:
    return profile_dir / DEFAULT_LAUNCHER_SCRIPT_NAME


def launcher_path_is_default(paths: RuntimePaths) -> bool:
    return paths.launcher_script == default_launcher_script_path(paths.profile_dir)


def compute_repo_managed_default_launcher_digest(script_payload: str) -> str:
    return hashlib.sha256(script_payload.encode("utf-8")).hexdigest()


def repo_managed_default_launcher_marker_present(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        header_lines = path.read_text(encoding="utf-8").splitlines()[:4]
    except OSError:
        return False
    return REPO_MANAGED_DEFAULT_LAUNCHER_MARKER in header_lines


def build_repo_owned_default_launcher_script_payload() -> str:
    return "\n".join(
        [
            "set -eu",
            'mode="${1:-}"',
            'if [ -n "${WBP_CURRENT_PROXY_URL:-}" ]; then',
            "  proxy_env() {",
            '    env HTTP_PROXY="$WBP_CURRENT_PROXY_URL"'
            ' HTTPS_PROXY="$WBP_CURRENT_PROXY_URL"'
            ' ALL_PROXY="$WBP_CURRENT_PROXY_URL"'
            ' http_proxy="$WBP_CURRENT_PROXY_URL"'
            ' https_proxy="$WBP_CURRENT_PROXY_URL"'
            ' all_proxy="$WBP_CURRENT_PROXY_URL" "$@"',
            "  }",
            "else",
            "  proxy_env() {",
            '    "$@"',
            "  }",
            "fi",
            'if [ "$mode" = "smoke" ]; then',
            '  printf "stable\\n" > "$WBP_RUNTIME_EFFECTIVE_MODE_FILE"',
            '  proxy_env "${WBP_PYTHON_BIN:?}" - <<\'PY\'',
            "import json",
            "import os",
            "from pathlib import Path",
            "state_path = Path(os.environ['WBP_STATE_FILE'])",
            "state = json.loads(state_path.read_text())",
            "stable_config = Path(os.environ['WBP_STABLE_CONFIG'])",
            "port = '8318'",
            "auth_dir = ''",
            "for raw_line in stable_config.read_text().splitlines():",
            "    line = raw_line.strip()",
            "    if line.startswith('port:'):",
            "        port = line.split(':', 1)[1].strip().strip('\"')",
            "    if line.startswith('auth-dir:'):",
            "        auth_dir = line.split(':', 1)[1].strip().strip('\"')",
            "state['effective_mode'] = 'stable'",
            "state['status'] = 'healthy'",
            "state['last_error'] = ''",
            "state['launcher_stable_config'] = str(stable_config)",
            "state['launcher_auth_dir'] = auth_dir",
            "state_path.write_text(json.dumps(state) + '\\n')",
            "config_path = Path(os.environ['WBP_CONFIG_TOML'])",
            "lines = config_path.read_text().splitlines()",
            "out = []",
            "for line in lines:",
            "    if line.strip().startswith('base_url = '):",
            "        out.append(f'base_url = \\\"http://127.0.0.1:{port}/v1\\\"')",
            "    else:",
            "        out.append(line)",
            "config_path.write_text('\\n'.join(out) + '\\n')",
            "PY",
            "  exit 0",
            "fi",
            f'if [ "$mode" = "{CURRENT_PROXY_OWNER_PATH_LAUNCHER_MODE}" ]; then',
            '  [ -n "${WBP_CURRENT_PROXY_URL:-}" ] || exit 8',
            '  proxy_env "${WBP_PYTHON_BIN:?}" - <<\'PY\'',
            "import json",
            "import os",
            "from pathlib import Path",
            "state_path = Path(os.environ['WBP_STATE_FILE'])",
            "state = json.loads(state_path.read_text())",
            "managed_config = Path(os.environ['WBP_MANAGED_CONFIG_FILE'])",
            "current_proxy_url = os.environ['WBP_CURRENT_PROXY_URL']",
            "port = '9999'",
            "for raw_line in managed_config.read_text().splitlines():",
            "    line = raw_line.strip()",
            "    if line.startswith('port:'):",
            "        port = line.split(':', 1)[1].strip().strip('\"')",
            "state['effective_mode'] = 'managed'",
            "state['status'] = 'healthy'",
            "state['last_error'] = ''",
            "state['current_proxy_url'] = current_proxy_url",
            "state_path.write_text(json.dumps(state) + '\\n')",
            "config_path = Path(os.environ['WBP_CONFIG_TOML'])",
            "lines = config_path.read_text().splitlines()",
            "out = []",
            "for line in lines:",
            "    if line.strip().startswith('base_url = '):",
            "        out.append(f'base_url = \\\"http://127.0.0.1:{port}/v1\\\"')",
            "    else:",
            "        out.append(line)",
            "config_path.write_text('\\n'.join(out) + '\\n')",
            "runtime_effective_mode_path = Path(os.environ['WBP_RUNTIME_EFFECTIVE_MODE_FILE'])",
            "runtime_effective_mode_path.write_text('managed\\n')",
            "PY",
            "  exit 0",
            "fi",
            "exit 7",
        ]
    )


def render_repo_owned_default_launcher_script_text(script_payload: str) -> str:
    return "\n".join(
        [
            "#!/bin/sh",
            REPO_MANAGED_DEFAULT_LAUNCHER_MARKER,
            (
                f"{REPO_MANAGED_DEFAULT_LAUNCHER_DIGEST_PREFIX}"
                f"{compute_repo_managed_default_launcher_digest(script_payload)}"
            ),
            script_payload,
        ]
    )


def build_repo_owned_default_launcher_script_text() -> str:
    return render_repo_owned_default_launcher_script_text(
        build_repo_owned_default_launcher_script_payload()
    )


def repo_managed_default_launcher_payload_if_valid(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if len(lines) < 4:
        return None
    if lines[0] != "#!/bin/sh" or lines[1] != REPO_MANAGED_DEFAULT_LAUNCHER_MARKER:
        return None
    digest_line = lines[2]
    if not digest_line.startswith(REPO_MANAGED_DEFAULT_LAUNCHER_DIGEST_PREFIX):
        return None
    expected_digest = digest_line.removeprefix(
        REPO_MANAGED_DEFAULT_LAUNCHER_DIGEST_PREFIX
    )
    script_payload = "\n".join(lines[3:])
    if expected_digest != compute_repo_managed_default_launcher_digest(script_payload):
        return None
    return script_payload


def repo_managed_default_launcher_signature_valid(path: Path) -> bool:
    return repo_managed_default_launcher_payload_if_valid(path) is not None


def repo_managed_default_launcher_payload_recognized(script_payload: str) -> bool:
    return script_payload == build_repo_owned_default_launcher_script_payload()


def repo_managed_default_launcher_recognized(path: Path) -> bool:
    script_payload = repo_managed_default_launcher_payload_if_valid(path)
    if script_payload is None:
        return False
    return repo_managed_default_launcher_payload_recognized(script_payload)


def ensure_repo_owned_default_launcher_consumer(paths: RuntimePaths) -> None:
    if not launcher_path_is_default(paths):
        return
    expected_text = build_repo_owned_default_launcher_script_text()
    if not paths.launcher_script.exists():
        write_executable_text_atomic(paths.launcher_script, expected_text)
        return
    if not repo_managed_default_launcher_recognized(paths.launcher_script):
        return
    current_text = paths.launcher_script.read_text(encoding="utf-8").rstrip("\n")
    if current_text != expected_text:
        write_executable_text_atomic(paths.launcher_script, expected_text)
        return
    if not os.access(paths.launcher_script, os.X_OK):
        paths.launcher_script.chmod(0o755)


def get_current_proxy_launcher_lane_status(
    paths: RuntimePaths, *, materialize_absent_default: bool
) -> dict[str, Any]:
    path_is_default = launcher_path_is_default(paths)
    prerequisite_materialized = False
    if materialize_absent_default and path_is_default and not paths.launcher_script.exists():
        ensure_repo_owned_default_launcher_consumer(paths)
        prerequisite_materialized = paths.launcher_script.exists()
    contract = build_current_proxy_adoption_contract(paths)
    path_surface = contract["external_launcher_path_surface"]
    readiness_status = str(contract["external_launcher_readiness_status"])
    path_kind = str(path_surface["path_kind"])
    repo_owned_default_consumer_provisioned = bool(
        contract["repo_owned_default_consumer_provisioned"]
    )
    eligibility = readiness_status
    if repo_owned_default_consumer_provisioned and path_kind == "default_owned_provisioning_target":
        eligibility = "eligible_recognized_repo_owned_default_lane"
    return {
        "eligible": eligibility == "eligible_recognized_repo_owned_default_lane",
        "eligibility": eligibility,
        "launcher_readiness_status": readiness_status,
        "path_kind": path_kind,
        "prerequisite_materialized": prerequisite_materialized,
    }


def run_current_proxy_owner_path_activation(
    paths: RuntimePaths, working_candidate: str
) -> CurrentProxyOwnerPathActivationAttempt:
    launcher_env = build_launcher_subprocess_env(paths)
    launcher_env[CURRENT_PROXY_URL_HANDOFF_ENV] = working_candidate
    with serialized_lock(paths):
        lane_status = get_current_proxy_launcher_lane_status(
            paths, materialize_absent_default=True
        )
        if not lane_status["eligible"]:
            return CurrentProxyOwnerPathActivationAttempt(
                launcher_lane_eligibility=str(lane_status["eligibility"]),
                launcher_readiness_status=str(lane_status["launcher_readiness_status"]),
                prerequisite_materialized=bool(
                    lane_status["prerequisite_materialized"]
                ),
                activation_attempted=False,
                activation_exit_code=None,
                prior_current_proxy_url="",
                working_candidate=working_candidate,
                rollback_surface_snapshots={},
            )
        prior_state = read_json(paths.state_file, required=False)
        rollback_surface_snapshots = snapshot_current_proxy_owner_path_runtime_surfaces(
            paths
        )
        result = subprocess.run(
            [str(paths.launcher_script), CURRENT_PROXY_OWNER_PATH_LAUNCHER_MODE],
            capture_output=True,
            text=True,
            env=launcher_env,
            check=False,
        )
    return CurrentProxyOwnerPathActivationAttempt(
        launcher_lane_eligibility=str(lane_status["eligibility"]),
        launcher_readiness_status=str(lane_status["launcher_readiness_status"]),
        prerequisite_materialized=bool(lane_status["prerequisite_materialized"]),
        activation_attempted=True,
        activation_exit_code=result.returncode,
        prior_current_proxy_url=str(prior_state.get("current_proxy_url", "")),
        working_candidate=working_candidate,
        rollback_surface_snapshots=rollback_surface_snapshots,
    )


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
    return get_selected_backend_ids_digest(ids)


def get_selected_backend_ids_digest(ids: Any) -> str:
    normalized_ids = normalize_selected_backend_ids(ids)
    encoded = json.dumps(normalized_ids, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_selected_backend_snapshot_payload(
    *,
    selected_backend_ids: list[str],
    observed_at_utc: str,
    source_class: str,
    source_name: str,
    source_run_id: str,
    producer_version: str,
) -> dict[str, Any]:
    return {
        "schema_version": SELECTED_BACKEND_SNAPSHOT_SCHEMA_VERSION,
        "snapshot_kind": SELECTED_BACKEND_SNAPSHOT_KIND,
        "source_class": source_class,
        "source_name": source_name,
        "source_run_id": source_run_id,
        "producer_version": producer_version,
        "observed_at_utc": observed_at_utc,
        "selected_backend_ids": list(selected_backend_ids),
        "selected_backends_digest": get_selected_backend_ids_digest(selected_backend_ids),
        "claim_scope": ROTATION_EVIDENCE_CLAIM_SCOPE,
    }


def materialize_selected_backend_snapshot_for_sync(paths: RuntimePaths) -> None:
    with serialized_lock(paths):
        state = read_json(paths.state_file, required=False)
        selected_backend_ids = normalize_selected_backend_ids(
            state.get("selected_backend_ids")
        )
        if not selected_backend_ids:
            if SELECTED_BACKEND_SNAPSHOT_FIELD in state:
                state.pop(SELECTED_BACKEND_SNAPSHOT_FIELD, None)
                write_json_atomic(paths.state_file, state)
            return

        # Refresh observation time on every successful owner-path materialization
        # so rotation evidence freshness can advance after each sync.
        observed_at_utc = now_iso()

        snapshot = build_selected_backend_snapshot_payload(
            selected_backend_ids=selected_backend_ids,
            observed_at_utc=observed_at_utc,
            source_class="supervisor_owner_observed",
            source_name="sync --json",
            source_run_id=f"sync:{observed_at_utc}",
            producer_version=str(
                state.get("version", state.get("schema_version", "unknown"))
            ),
        )
        state["selected_backend_ids_observed_at"] = observed_at_utc
        state[SELECTED_BACKEND_SNAPSHOT_FIELD] = snapshot
        write_json_atomic(paths.state_file, state)


def parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rotation_snapshot_observed_at(state: dict[str, Any]) -> str:
    explicit_value = state.get("selected_backend_ids_observed_at")
    if isinstance(explicit_value, str) and explicit_value.strip():
        return explicit_value.strip()
    return ""


def rotation_snapshot_freshness(state: dict[str, Any]) -> str:
    explicit_value = state.get("selected_backend_ids_observed_at")
    if not isinstance(explicit_value, str) or not explicit_value.strip():
        return "unknown"
    observed_at = parse_utc_datetime(explicit_value)
    current_time = parse_utc_datetime(now_iso())
    if observed_at is None or current_time is None:
        return "unknown"
    age_seconds = (current_time - observed_at).total_seconds()
    if age_seconds < 0:
        return "unknown"
    if age_seconds > ROTATION_EVIDENCE_FRESHNESS_SECONDS:
        return "stale"
    return "fresh"


def selected_backend_snapshot_freshness(observed_at_value: Any) -> str:
    if not isinstance(observed_at_value, str) or not observed_at_value.strip():
        return "unknown"
    observed_at = parse_utc_datetime(observed_at_value)
    current_time = parse_utc_datetime(now_iso())
    if observed_at is None or current_time is None:
        return "unknown"
    age_seconds = (current_time - observed_at).total_seconds()
    if age_seconds < 0:
        return "unknown"
    if age_seconds > ROTATION_EVIDENCE_FRESHNESS_SECONDS:
        return "stale"
    return "fresh"


def normalize_selected_backend_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value if isinstance(item, str) and item)


def get_rotation_selected_backend_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    snapshot = state.get(SELECTED_BACKEND_SNAPSHOT_FIELD)
    if isinstance(snapshot, dict):
        ids = normalize_selected_backend_ids(snapshot.get("selected_backend_ids"))
        observed_at = str(snapshot.get("observed_at_utc") or "").strip()
        source_class = str(snapshot.get("source_class") or "").strip()
        digest = str(snapshot.get("selected_backends_digest") or "").strip()
        expected_digest = get_selected_backend_ids_digest(ids)
        result = {
            "source": "runtime_state.selected_backend_snapshot",
            "source_layer": source_class,
            "source_class": source_class,
            "source_name": str(snapshot.get("source_name") or "").strip(),
            "source_run_id": str(snapshot.get("source_run_id") or "").strip(),
            "producer_version": str(snapshot.get("producer_version") or "").strip(),
            "selected_backend_ids": ids,
            "observed_at_utc": observed_at,
            "selected_backends_digest": digest,
            "expected_selected_backends_digest": expected_digest,
            "freshness": selected_backend_snapshot_freshness(observed_at),
            "validation_status": "valid",
            "validation_error": "",
            "compatibility": "nested_snapshot",
        }
        if snapshot.get("schema_version") != SELECTED_BACKEND_SNAPSHOT_SCHEMA_VERSION:
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_schema_unsupported"
        elif snapshot.get("snapshot_kind") != SELECTED_BACKEND_SNAPSHOT_KIND:
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_kind_invalid"
        elif source_class not in SELECTED_BACKEND_SNAPSHOT_ALLOWED_SOURCE_CLASSES:
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_source_class_invalid"
        elif (
            not result["source_name"]
            or not result["source_run_id"]
            or not result["producer_version"]
        ):
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_source_metadata_missing"
        elif not observed_at or result["freshness"] == "unknown":
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_observed_at_invalid"
        elif not ids:
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_ids_missing"
        elif not digest or digest != expected_digest:
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_digest_mismatch"
        elif snapshot.get("claim_scope") != ROTATION_EVIDENCE_CLAIM_SCOPE:
            result["validation_status"] = "invalid"
            result["validation_error"] = "selected_backend_snapshot_claim_scope_invalid"
        return result

    ids = selected_backend_ids_from_state(state)
    observed_at = rotation_snapshot_observed_at(state)
    return {
        "source": "runtime_state.selected_backend_ids",
        "source_layer": "legacy_flat_compatibility",
        "source_class": "legacy_flat_compatibility",
        "source_name": "",
        "source_run_id": "",
        "producer_version": "",
        "selected_backend_ids": ids,
        "observed_at_utc": observed_at,
        "selected_backends_digest": get_selected_backends_digest(state),
        "expected_selected_backends_digest": get_selected_backends_digest(state),
        "freshness": rotation_snapshot_freshness(state),
        "validation_status": "legacy",
        "validation_error": "",
        "compatibility": "legacy_flat",
    }


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


def get_auth_inventory_entries_digest(entries: list[str]) -> str:
    normalized = sorted(str(item) for item in entries)
    encoded = json.dumps(normalized, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def get_onboarding_auth_snapshot_before_login(paths: RuntimePaths) -> dict[str, Any]:
    stable_auth_dir, inventory_source = get_stable_auth_inventory_source(paths)
    if not stable_auth_dir.is_dir():
        return {
            "status": "source_unavailable",
            "count": 0,
            "digest": get_auth_inventory_entries_digest([]),
            "source": inventory_source,
        }
    entries = sorted(
        path.name
        for path in stable_auth_dir.glob("codex-*.json")
        if path.is_file()
    )
    return {
        "status": "ok",
        "count": len(entries),
        "digest": get_auth_inventory_entries_digest(entries),
        "source": inventory_source,
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
    invalid_backend_pools = []
    registry_schema_version = registry.get("schema_version")
    unsupported_schema_versions = []

    if registry_schema_version != BACKEND_REGISTRY_SCHEMA_VERSION:
        unsupported_schema_versions.append(
            "missing"
            if registry_schema_version is None
            else str(registry_schema_version)
        )

    for index, backend in enumerate(backends):
        backend_key = get_backend_identifier(backend, index)
        backend_id = backend.get("id")
        if backend_id:
            backend_ids.setdefault(str(backend_id), []).append(backend_key)
        observed_pool = str(backend.get("pool", ""))
        if observed_pool not in VALID_BACKEND_REGISTRY_POOLS:
            invalid_backend_pools.append(f"{backend_key}:{observed_pool or '<missing>'}")

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
        or invalid_backend_pools
        or unsupported_schema_versions
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
        "invalid_backend_pools": sorted(invalid_backend_pools),
        "registry_schema_version": registry_schema_version,
        "unsupported_schema_versions": unsupported_schema_versions,
        "claim_blockers": claim_blockers if ambiguous else [],
        "next_action": "inspect_registry_identity" if ambiguous else "none",
    }


def stable_repair_registry_identity_requires_block(
    registry_identity: dict[str, Any]
) -> bool:
    return any(
        registry_identity.get(field)
        for field in (
            "duplicate_backend_ids",
            "missing_auth_refs",
            "empty_auth_ref_backends",
            "invalid_auth_basenames",
            "invalid_backend_pools",
            "unsupported_schema_versions",
        )
    )


def backend_in_launch_candidate_universe(
    backend: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons = []
    if backend.get("enabled", True) is False:
        reasons.append("disabled")
    if backend.get("pool") != "active":
        reasons.append("pool_not_active")
    if bool(backend.get("manual_hold")):
        reasons.append("manual_hold")
    if not backend.get("auth_ref"):
        reasons.append("missing_auth_ref")
    if str(backend.get("status", "")).lower() in {"retired", "fatal"}:
        reasons.append("terminal_status")
    return not reasons, reasons


def classify_backend_runtime_eligibility(
    backend: dict[str, Any],
) -> tuple[str, list[str]]:
    eligible, reasons = backend_in_launch_candidate_universe(backend)
    if not eligible:
        return "excluded", reasons

    status = str(backend.get("status", "")).lower()
    last_error_class = str(backend.get("last_error_class", "")).lower()
    last_error = str(backend.get("last_error", "")).lower()
    cooldown_until = str(backend.get("cooldown_until") or "").strip()

    if (
        last_error_class == "auth"
        or "auth_unavailable" in last_error
        or "authentication token has been invalidated" in last_error
    ):
        return "auth_invalid", ["auth_invalid"]
    if (
        last_error_class == "quota"
        or "usage_limit_reached" in last_error
        or ("quota" in last_error and "model_cooldown" not in last_error)
    ):
        return "quota_exhausted", ["quota_exhausted"]
    if "model_cooldown" in last_error or (
        cooldown_until and status != "healthy" and not last_error_class
    ):
        return "cooldown_only", ["cooldown_only"]
    if status == "healthy" and not cooldown_until and not last_error_class and not last_error:
        return "live_capable", []
    return "unknown_unverified", ["unknown_unverified"]


def backend_in_stage_posture_candidate_universe(
    backend: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons = []
    if backend.get("enabled", True) is False:
        reasons.append("disabled")
    if bool(backend.get("manual_hold")):
        reasons.append("manual_hold")
    if not backend.get("auth_ref"):
        reasons.append("missing_auth_ref")
    if str(backend.get("status", "")).lower() in {"retired", "fatal"}:
        reasons.append("terminal_status")
    return not reasons, reasons


def classify_backend_stage_posture_eligibility(
    backend: dict[str, Any],
) -> tuple[str, list[str]]:
    eligible, reasons = backend_in_stage_posture_candidate_universe(backend)
    if not eligible:
        return "excluded", reasons

    status = str(backend.get("status", "")).lower()
    last_error_class = str(backend.get("last_error_class", "")).lower()
    last_error = str(backend.get("last_error", "")).lower()
    cooldown_until = str(backend.get("cooldown_until") or "").strip()

    if (
        last_error_class == "auth"
        or "auth_unavailable" in last_error
        or "authentication token has been invalidated" in last_error
    ):
        return "auth_invalid", ["auth_invalid"]
    if (
        last_error_class == "quota"
        or "usage_limit_reached" in last_error
        or ("quota" in last_error and "model_cooldown" not in last_error)
    ):
        return "quota_exhausted", ["quota_exhausted"]
    if "model_cooldown" in last_error or (
        cooldown_until and status != "healthy" and not last_error_class
    ):
        return "cooldown_only", ["cooldown_only"]
    if (
        status == "healthy"
        and not cooldown_until
        and not last_error_class
        and not last_error
    ):
        return "live_capable", []
    return "unknown_unverified", ["unknown_unverified"]


def get_launch_capable_backend_ids(registry: dict[str, Any]) -> list[str]:
    return sorted(
        str(item.get("id")).strip()
        for item in registry.get("backends", [])
        if str(item.get("id") or "").strip()
        and classify_backend_runtime_eligibility(item)[0] == "live_capable"
    )


def summarize_auth_pool_hygiene(
    registry: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    candidate_universe_backend_ids: list[str] = []
    class_backend_ids = {
        "live_capable": [],
        "quota_exhausted": [],
        "auth_invalid": [],
        "cooldown_only": [],
        "unknown_unverified": [],
    }
    for backend in registry.get("backends", []):
        backend_id = backend.get("id")
        if backend_id is None:
            continue
        eligibility_class, _ = classify_backend_runtime_eligibility(backend)
        if eligibility_class == "excluded":
            continue
        normalized_id = str(backend_id)
        candidate_universe_backend_ids.append(normalized_id)
        class_backend_ids.setdefault(eligibility_class, []).append(normalized_id)

    selected_backend_ids = sorted(
        str(item) for item in state.get("selected_backend_ids", []) or []
    )
    launch_capable_backend_ids = sorted(class_backend_ids["live_capable"])
    launch_capable_backend_id_set = set(launch_capable_backend_ids)
    selected_launch_capable_backend_ids = [
        backend_id
        for backend_id in selected_backend_ids
        if backend_id in launch_capable_backend_id_set
    ]
    selected_unusable_backend_ids = [
        backend_id
        for backend_id in selected_backend_ids
        if backend_id not in launch_capable_backend_id_set
    ]

    if launch_capable_backend_ids:
        status = "launch_capable_available"
        machine_error_code = "OK"
        blocking_reason = ""
    else:
        status = "launch_capable_empty"
        machine_error_code = "USABLE_AUTH_POOL_EMPTY"
        blocking_reason = "no_live_capable_active_backends"

    if selected_backend_ids and selected_unusable_backend_ids:
        selection_alignment_status = "selected_backend_outside_live_capable_lane"
    else:
        selection_alignment_status = "aligned"

    return {
        "status": status,
        "machine_error_code": machine_error_code,
        "blocking_reason": blocking_reason,
        "claim_scope": "bounded_runtime_auth_usability_only",
        "candidate_universe_backend_ids": sorted(candidate_universe_backend_ids),
        "launch_capable_backend_ids": launch_capable_backend_ids,
        "quota_exhausted_backend_ids": sorted(class_backend_ids["quota_exhausted"]),
        "auth_invalid_backend_ids": sorted(class_backend_ids["auth_invalid"]),
        "cooldown_only_backend_ids": sorted(class_backend_ids["cooldown_only"]),
        "unknown_unverified_backend_ids": sorted(
            class_backend_ids["unknown_unverified"]
        ),
        "launch_capable_backend_count": len(launch_capable_backend_ids),
        "candidate_universe_backend_count": len(candidate_universe_backend_ids),
        "selected_backend_ids_observed": selected_backend_ids,
        "selected_launch_capable_backend_ids": selected_launch_capable_backend_ids,
        "selected_unusable_backend_ids": selected_unusable_backend_ids,
        "selected_launch_capable_backend_count": len(selected_launch_capable_backend_ids),
        "selected_unusable_backend_count": len(selected_unusable_backend_ids),
        "selection_alignment_status": selection_alignment_status,
    }


def is_stable_auth_allowed(backend: dict[str, Any]) -> tuple[bool, list[str]]:
    eligibility_class, reasons = classify_backend_runtime_eligibility(backend)
    if eligibility_class == "live_capable":
        return True, []
    status = str(backend.get("status", "")).lower()
    if status in {"down", "degraded", "failed", "error"}:
        if "status_not_allowed" not in reasons:
            reasons = [*reasons, "status_not_allowed"]
        return False, reasons
    if eligibility_class == "excluded":
        return False, reasons
    return False, reasons or [eligibility_class]


def get_stable_policy_drift_for_inventory_source(
    registry: dict[str, Any],
    stable_auth_dir: Path,
    inventory_source: dict[str, Any],
) -> dict[str, Any]:
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


def get_stable_policy_drift(paths: RuntimePaths, registry: dict[str, Any]) -> dict[str, Any]:
    stable_auth_dir, inventory_source = get_stable_auth_inventory_source(paths)
    return get_stable_policy_drift_for_inventory_source(
        registry, stable_auth_dir, inventory_source
    )


def get_approved_target_inventory_source(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "source": "approved_repair_target",
        "path": str(paths.repair_target_inventory_dir),
        "path_resolution": "control_owned_inventory_path",
        "exists": paths.repair_target_inventory_dir.is_dir(),
    }


def snapshot_confirms_approved_target_activation(
    paths: RuntimePaths, state: dict[str, Any]
) -> bool:
    snapshot = get_valid_stable_runtime_consumer_snapshot(state)
    if snapshot is None:
        return False
    return (
        str(snapshot.get("activation_outcome"))
        == STABLE_RUNTIME_APPROVED_TARGET_ACTIVATION_OUTCOME
        and str(snapshot.get("selected_source_kind")) == "approved_repair_target"
        and Path(str(snapshot.get("selected_source_path")))
        == paths.repair_target_inventory_dir
        and str(snapshot.get("activation_method")) == "process_local_env_override"
        and str(snapshot.get("selected_config_file"))
        == str(paths.stable_runtime_generated_config_file)
    )


def should_use_approved_target_policy_drift(
    paths: RuntimePaths,
    registry: dict[str, Any],
    observed_policy_drift: dict[str, Any],
    state: dict[str, Any],
    *,
    require_live_stable_runtime: bool,
    health_payload: dict[str, Any] | None = None,
    stable_runtime_consumer: dict[str, Any] | None = None,
) -> bool:
    selection = get_stable_runtime_consumer_selection_context(
        paths, registry, observed_policy_drift
    )
    if not selection.get("approved_target_ready"):
        return False
    if not snapshot_confirms_approved_target_activation(paths, state):
        return False
    if not require_live_stable_runtime:
        return True
    if not (
        health_payload
        and health_payload.get("status") == "ok"
        and str(health_payload.get("effective_mode")) == "stable"
    ):
        return False
    if not isinstance(stable_runtime_consumer, dict):
        return False
    effective_source = stable_runtime_consumer.get(
        "effective_stable_runtime_consumer_source"
    )
    if not isinstance(effective_source, dict):
        return False
    return (
        str(effective_source.get("status"))
        == "approved_target_active_by_activation_evidence"
        and str(effective_source.get("source_kind")) == "approved_repair_target"
        and Path(str(effective_source.get("resolved_path")))
        == paths.repair_target_inventory_dir
    )


def get_active_routing_candidate_backend_ids(registry: dict[str, Any]) -> list[str]:
    return get_launch_capable_backend_ids(registry)


def summarize_registry_identity(registry_identity: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": registry_identity.get("status", "unknown"),
        "machine_error_code": registry_identity.get("machine_error_code", "UNKNOWN"),
    }


def coerce_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


def summarize_promotion_pool_policy(registry: dict[str, Any]) -> dict[str, Any]:
    policy = registry.get("pool_policy")
    if not isinstance(policy, dict):
        return {
            "status": "invalid",
            "machine_error_code": "POOL_POLICY_INVALID",
            "reason": "pool_policy_missing_or_not_object",
            "active_min": None,
            "active_target": None,
            "reserve_target": None,
        }

    active_min = coerce_nonnegative_int(policy.get("active_min"))
    active_target = coerce_nonnegative_int(policy.get("active_target"))
    reserve_target = coerce_nonnegative_int(policy.get("reserve_target"))
    if active_min is None or active_target is None or reserve_target is None:
        return {
            "status": "invalid",
            "machine_error_code": "POOL_POLICY_INVALID",
            "reason": "pool_policy_fields_invalid",
            "active_min": active_min,
            "active_target": active_target,
            "reserve_target": reserve_target,
        }
    if active_target < active_min:
        return {
            "status": "invalid",
            "machine_error_code": "POOL_POLICY_INVALID",
            "reason": "active_target_below_active_min",
            "active_min": active_min,
            "active_target": active_target,
            "reserve_target": reserve_target,
        }
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "reason": "pool_policy_valid",
        "active_min": active_min,
        "active_target": active_target,
        "reserve_target": reserve_target,
    }


def summarize_stage_pool_policy_mapping(stage_value: str) -> dict[str, Any]:
    stage = str(stage_value).strip()
    desired_policy = STAGED_POOL_POLICY_PACKETS.get(stage)
    if desired_policy is None:
        return {
            "status": "unsupported",
            "machine_error_code": "POOL_POLICY_STAGE_UNSUPPORTED",
            "requested_stage": stage,
            "mapped_pool_policy": None,
        }
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "requested_stage": stage,
        "mapped_pool_policy": dict(desired_policy),
    }


def pool_policy_matches_stage_packet(
    pool_policy: dict[str, Any], desired_policy: dict[str, int]
) -> bool:
    return (
        coerce_nonnegative_int(pool_policy.get("active_min")) == desired_policy["active_min"]
        and coerce_nonnegative_int(pool_policy.get("active_target"))
        == desired_policy["active_target"]
        and coerce_nonnegative_int(pool_policy.get("reserve_target"))
        == desired_policy["reserve_target"]
    )


def observe_current_stage_from_pool_policy(registry: dict[str, Any]) -> dict[str, Any]:
    policy_summary = summarize_promotion_pool_policy(registry)
    if policy_summary.get("status") != "ok":
        return {
            "status": "invalid",
            "machine_error_code": str(
                policy_summary.get("machine_error_code", "POOL_POLICY_INVALID")
            ),
            "observed_stage": "",
            "pool_policy_summary": policy_summary,
        }

    pool_policy = registry.get("pool_policy") or {}
    for stage, desired_policy in STAGED_POOL_POLICY_PACKETS.items():
        if pool_policy_matches_stage_packet(pool_policy, desired_policy):
            return {
                "status": "matched",
                "machine_error_code": "OK",
                "observed_stage": stage,
                "pool_policy_summary": policy_summary,
            }

    return {
        "status": "custom",
        "machine_error_code": "POOL_POLICY_STAGE_CUSTOM",
        "observed_stage": "",
        "pool_policy_summary": policy_summary,
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
STABLE_RUNTIME_GENERATED_CONFIG_METHOD = "control_owned_generated_config"
STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV = "WBP_STABLE_CONFIG"
CURRENT_PROXY_URL_HANDOFF_ENV = "WBP_CURRENT_PROXY_URL"
STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC = "stable_runtime_consumer_snapshot"
STABLE_RUNTIME_APPROVED_TARGET_ACTIVATION_OUTCOME = "approved_target_activated"
STABLE_RUNTIME_OBSERVED_SOURCE_SELECTED_OUTCOME = "observed_source_selected"
STABLE_RUNTIME_OBSERVED_SOURCE_FALLBACK_OUTCOME = "observed_source_fallback"
LAST_KNOWN_GOOD_PROXY_URL_FIELD = "last_known_good_proxy_url"
LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD = "last_known_good_proxy_observed_at"
STABLE_RUNTIME_CONSUMER_SNAPSHOT_REQUIRED_FIELDS = [
    "schema_version",
    "activation_method",
    "selected_config_file",
    "selected_source_kind",
    "selected_source_path",
    "activation_outcome",
    "fallback_reason",
    "observed_at_utc",
]


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
    return {
        "state": "file",
        "text": path.read_text(encoding="utf-8"),
        "mode": path.stat().st_mode & 0o777,
    }


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
    mode = snapshot.get("mode")
    if isinstance(mode, int):
        path.chmod(mode)


def restore_rollout_stage_advance_inventory_dir_state(
    path: Path, snapshot: dict[str, Any]
) -> None:
    state = snapshot.get("state")
    if state == "missing":
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
            return
        if path.is_dir():
            shutil.rmtree(path)
        return
    restore_path_state(path, snapshot)


def snapshot_current_proxy_owner_path_runtime_surfaces(
    paths: RuntimePaths,
) -> dict[str, dict[str, Any]]:
    return {
        "state_file": snapshot_path_state(paths.state_file),
        "config_toml": snapshot_path_state(paths.config_toml),
        "runtime_effective_mode_file": snapshot_path_state(
            paths.runtime_effective_mode_file
        ),
    }


def restore_current_proxy_owner_path_runtime_surfaces(
    paths: RuntimePaths, snapshots: dict[str, dict[str, Any]]
) -> None:
    restore_path_state(
        paths.state_file, snapshots.get("state_file", {"state": "missing"})
    )
    restore_path_state(
        paths.config_toml, snapshots.get("config_toml", {"state": "missing"})
    )
    restore_path_state(
        paths.runtime_effective_mode_file,
        snapshots.get("runtime_effective_mode_file", {"state": "missing"}),
    )


def managed_pid_matches_expected(paths: RuntimePaths, pid_text: str) -> bool:
    try:
        pid = int(pid_text.strip())
    except ValueError:
        return False
    command_line = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    expected = f"{paths.managed_config_file}"
    return bool(command_line) and expected in command_line


def snapshot_sync_current_proxy_recovery_runtime_surfaces(
    paths: RuntimePaths,
) -> dict[str, dict[str, Any]]:
    return {
        "state_file": snapshot_path_state(paths.state_file),
        "managed_config_file": snapshot_path_state(paths.managed_config_file),
        "config_toml": snapshot_path_state(paths.config_toml),
        "runtime_effective_mode_file": snapshot_path_state(
            paths.runtime_effective_mode_file
        ),
        "managed_pid_file": snapshot_path_state(managed_pid_path(paths)),
    }


def restore_sync_current_proxy_recovery_runtime_surfaces(
    paths: RuntimePaths, snapshots: dict[str, dict[str, Any]]
) -> None:
    current_pid_text = read_text(managed_pid_path(paths))
    snapshot_pid_text = str(
        snapshots.get("managed_pid_file", {}).get("text", "")
        if snapshots.get("managed_pid_file", {}).get("state") == "file"
        else ""
    ).strip()
    if (
        current_pid_text.strip()
        and current_pid_text.strip() != snapshot_pid_text
        and managed_pid_matches_expected(paths, current_pid_text)
        and process_is_alive(current_pid_text)
    ):
        try:
            os.kill(int(current_pid_text.strip()), signal.SIGTERM)
        except OSError:
            pass
    restore_path_state(
        paths.state_file, snapshots.get("state_file", {"state": "missing"})
    )
    restore_path_state(
        paths.managed_config_file,
        snapshots.get("managed_config_file", {"state": "missing"}),
    )
    restore_path_state(
        paths.config_toml, snapshots.get("config_toml", {"state": "missing"})
    )
    restore_path_state(
        paths.runtime_effective_mode_file,
        snapshots.get("runtime_effective_mode_file", {"state": "missing"}),
    )
    restore_path_state(
        managed_pid_path(paths),
        snapshots.get("managed_pid_file", {"state": "missing"}),
    )


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


def build_stable_runtime_generated_config_surface(
    paths: RuntimePaths,
    state: dict[str, Any],
) -> dict[str, Any]:
    generated_path = paths.stable_runtime_generated_config_file
    snapshot = get_valid_stable_runtime_consumer_snapshot(state)
    activation_snapshot_present = snapshot is not None
    activation_snapshot_observed_at_utc = ""
    activation_snapshot_freshness = "unknown"
    activation_snapshot_references_generated_config = False
    if snapshot is not None:
        activation_snapshot_observed_at_utc = str(
            snapshot.get("observed_at_utc") or ""
        ).strip()
        activation_snapshot_freshness = selected_backend_snapshot_freshness(
            activation_snapshot_observed_at_utc
        )
        activation_snapshot_references_generated_config = (
            str(snapshot.get("selected_config_file")) == str(generated_path)
        )
    if not generated_path.exists():
        status = "declared_not_materialized"
    elif (
        activation_snapshot_references_generated_config
        and activation_snapshot_freshness == "fresh"
    ):
        status = "materialized_with_fresh_activation_evidence"
    elif (
        activation_snapshot_references_generated_config
        and activation_snapshot_freshness == "stale"
    ):
        status = "materialized_with_stale_activation_evidence"
    else:
        status = "materialized_unactivated"
    return {
        "status": status,
        "config_file": str(generated_path),
        "ownership": "control_layer",
        "location_scope": "companion_managed_data",
        "artifact_kind": "generated_runtime_config",
        "truth_surface": False,
        "activation_method": STABLE_RUNTIME_GENERATED_CONFIG_METHOD,
        "exists": generated_path.exists(),
        "activation_snapshot_present": activation_snapshot_present,
        "activation_snapshot_observed_at_utc": activation_snapshot_observed_at_utc,
        "activation_snapshot_freshness": activation_snapshot_freshness,
        "activation_snapshot_references_generated_config": (
            activation_snapshot_references_generated_config
        ),
        "activation_snapshot_alone_sufficient": False,
    }


def build_stable_runtime_launcher_handoff_contract(
    paths: RuntimePaths,
) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "handoff_method": "process_local_env_override",
        "env_var": STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
        "generated_config_file": str(paths.stable_runtime_generated_config_file),
        "scope": "launcher_subprocess_only",
        "recovery_scope": "explicit_stable_runtime_recovery_only",
        "baseline_config_rewrite_forbidden": True,
        "generic_config_routing_forbidden": True,
    }


def build_stable_runtime_activation_evidence_surface(
    paths: RuntimePaths, state: dict[str, Any]
) -> dict[str, Any]:
    snapshot = state.get(STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC)
    snapshot_present = isinstance(snapshot, dict)
    snapshot_shape_valid = snapshot_present and all(
        field in snapshot for field in STABLE_RUNTIME_CONSUMER_SNAPSHOT_REQUIRED_FIELDS
    )
    snapshot_observed_at_utc = ""
    snapshot_freshness = "unknown"
    snapshot_references_generated_config = False
    if snapshot_shape_valid:
        snapshot_observed_at_utc = str(snapshot.get("observed_at_utc") or "").strip()
        snapshot_freshness = selected_backend_snapshot_freshness(snapshot_observed_at_utc)
        snapshot_references_generated_config = (
            str(snapshot.get("selected_config_file"))
            == str(paths.stable_runtime_generated_config_file)
        )
    if snapshot_shape_valid and snapshot_freshness == "stale":
        status = "snapshot_stale"
    elif snapshot_shape_valid:
        status = "snapshot_present"
    elif snapshot_present:
        status = "snapshot_shape_invalid"
    else:
        status = "declared_not_materialized"
    payload = {
        "status": status,
        "snapshot_file": str(paths.state_file),
        "snapshot_topic": STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC,
        "classification": "runtime_state_snapshot_evidence",
        "owner": "serialized_runtime_state_mutation_path",
        "final_truth_without_live_checks": False,
        "live_runtime_observation_required": True,
        "required_fields": STABLE_RUNTIME_CONSUMER_SNAPSHOT_REQUIRED_FIELDS,
        "snapshot_present": snapshot_present,
        "snapshot_shape_valid": snapshot_shape_valid,
        "snapshot_observed_at_utc": snapshot_observed_at_utc,
        "snapshot_freshness": snapshot_freshness,
        "snapshot_references_generated_config": snapshot_references_generated_config,
        "generated_config_file": str(paths.stable_runtime_generated_config_file),
        "snapshot_alone_sufficient": False,
    }
    if snapshot_present:
        payload["current_snapshot"] = snapshot
    return payload


def build_stable_runtime_effective_truth_contract() -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "truth_source": "live_runtime_observation_plus_snapshot_evidence",
        "desired_source_alone_sufficient": False,
        "generated_config_existence_alone_sufficient": False,
        "activation_evidence_snapshot_alone_sufficient": False,
        "live_runtime_observation_required": True,
        "baseline_config_is_observation_surface": True,
    }


def build_deterministic_stable_recovery_contract(
    paths: RuntimePaths,
) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "entry_owner": "healthcheck_live_attestation_path",
        "owner_command_surface": "healthcheck --json",
        "status_delegates_to_owner": True,
        "sync_hidden_owner_forbidden": True,
        "new_generic_cli_default": False,
        "eligible_failure_lanes": [
            "managed_preflight_failure",
            "stable_service_disabled",
            "explicit_stable_recovery_lane",
        ],
        "entry_lane_surface": {
            "status": "owner_path_emitted",
            "field": "deterministic_stable_recovery_result.entry_lane",
            "nested_recovery_surface": True,
            "top_level_machine_error_code_separate": True,
            "allowed_values": [
                "managed_preflight_failure",
                "stable_service_disabled",
                "explicit_stable_recovery_lane",
                "not_invoked",
            ],
        },
        "failure_taxonomy_redesign_forbidden": True,
        "shared_activation_mechanics": {
            "status": "owner_path_emitted",
            "reuse_existing_launch_smoke_activation_helper": True,
            "generated_config_file": str(paths.stable_runtime_generated_config_file),
            "handoff_env_var": STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
            "snapshot_topic": STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC,
            "owner_paths": ["healthcheck --json", "launch smoke --json"],
        },
        "generated_config_regeneration_status": "owner_path_emitted",
        "generated_config_regeneration_policy": "regenerate_each_recovery_attempt",
        "generated_config_derivation_source": (
            "current_baseline_stable_config_plus_current_approved_target_reference"
        ),
        "generated_config_regeneration_owner_paths": [
            "healthcheck --json",
            "launch smoke --json",
        ],
        "stale_generated_config_authoritative": False,
        "generated_config_existence_alone_sufficient": False,
        "snapshot_refresh_status": "owner_path_emitted",
        "snapshot_refresh_after_stable_live_outcome": True,
        "snapshot_refresh_owner_paths": ["healthcheck --json", "launch smoke --json"],
        "snapshot_schema_widening_required": False,
        "new_persisted_recovery_metadata_required": False,
        "stable_service_disabled_classification": {
            "status": "owner_path_emitted",
            "classification_surface": "deterministic_stable_recovery_result.entry_lane",
            "control_layer_classification": True,
            "persisted_engine_state_flag": False,
            "positive_evidence_required": True,
            "desired_mode_alone_sufficient": False,
            "generated_config_existence_alone_sufficient": False,
            "snapshot_presence_alone_sufficient": False,
            "bounded_reenable_lane_eligible_required": True,
            "proxy_path_failure_codes_separate": [
                "PROXY_PATH_BROKEN",
                "PROXY_REPROBE_FAILED",
            ],
            "generic_listener_down_fallback": "LISTENER_DOWN",
            "overclassification_forbidden": True,
        },
        "re_enable_method_contract": {
            "status": "owner_path_emitted",
            "owner_path_scope": "bounded_control_layer_recovery_action",
            "owner_command_surface": "healthcheck --json",
            "reuse_private_launch_smoke_helper_allowed": True,
            "launcher_protocol_widening_required": False,
            "launchd_integration_forbidden": True,
            "os_service_manager_integration_forbidden": True,
            "generic_service_supervision_forbidden": True,
        },
        "approved_target_recovery_outcome": "separate",
        "observed_source_fallback_recovery_outcome": "separate",
        "recovery_failure_outcome": "separate",
        "top_level_truth_boundaries": {
            "status": "contract_ready",
            "top_level_final_truth_fields": [
                "status",
                "machine_error_code",
                "liveness",
                "endpoint",
            ],
            "nested_recovery_surface": "deterministic_stable_recovery_result",
            "final_live_truth_separate": True,
            "launch_smoke_owner_lane_fields_forbidden": True,
            "status_second_owner_forbidden": True,
            "sync_owner_lane_forbidden": True,
        },
        "top_level_machine_error_code_rules": {
            "status": "owner_path_emitted",
            "stable_service_disabled_final_code": "STABLE_SERVICE_DISABLED",
            "stable_service_disabled_requires_final_unhealthy": True,
            "ok_after_successful_reenable": "OK",
            "generic_listener_down_fallback": "LISTENER_DOWN",
            "proxy_path_codes_remain_separate": True,
        },
        "live_runtime_observation_required": True,
        "mode_truth_redefinition_forbidden": True,
        "last_known_good_proxy_persistence_in_scope": False,
    }


def build_last_known_good_proxy_contract(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "owner_command_surface": "healthcheck --json",
        "status_delegates_to_owner": True,
        "sync_owner_forbidden": True,
        "launch_smoke_owner_forbidden": True,
        "launcher_lane_ineligible_sync_owner_recovery_surface": {
            "status": "available" if paths.sync_script.exists() else "unavailable",
            "command_surface": "sync --json",
            "owner_path_private": True,
            "allowed_when_launcher_lane_ineligible": True,
            "restart_scope": "managed_runtime_restart_with_proxy_refresh",
            "writes_managed_config_proxy_url": True,
            "reproof_required": True,
        },
        "state_file": str(paths.state_file),
        "state_fields": [
            LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD,
        ],
        "current_proxy_url_field": "current_proxy_url",
        "current_proxy_url_reuse_forbidden": True,
        "separate_metadata_file_default": False,
        "write_owner": "serialized_healthcheck_owner_path",
        "write_path_status": "owner_path_emitted",
        "refresh_requires_positive_managed_proxy_proof": True,
        "refresh_from_candidate_liveness_alone_forbidden": True,
        "refresh_from_current_proxy_url_alone_forbidden": True,
        "failed_reprobe_clears_persisted_value": False,
        "candidate_input_priority": [
            "WBP_PROXY_REPROBE_CANDIDATES",
            LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            "current_proxy_url",
        ],
        "candidate_inputs_bounded_local_only": True,
        "candidate_input_deduped_after_filter": True,
        "changed_files_visibility_required": True,
        "historical_truth_promotes_live_truth": False,
    }


def build_current_proxy_adoption_contract(paths: RuntimePaths) -> dict[str, Any]:
    launcher_path_exists = paths.launcher_script.exists()
    launcher_path_is_default_target = launcher_path_is_default(paths)
    repo_managed_marker_present = (
        launcher_path_exists
        and launcher_path_is_default_target
        and repo_managed_default_launcher_marker_present(paths.launcher_script)
    )
    repo_managed_signature_valid = (
        launcher_path_exists
        and launcher_path_is_default_target
        and repo_managed_default_launcher_signature_valid(paths.launcher_script)
    )
    repo_managed_payload_recognized = (
        launcher_path_exists
        and launcher_path_is_default_target
        and repo_managed_default_launcher_recognized(paths.launcher_script)
    )
    if launcher_path_is_default_target:
        if repo_managed_payload_recognized:
            external_launcher_readiness_status = "default_path_provisioned_repo_managed"
        elif repo_managed_signature_valid:
            external_launcher_readiness_status = (
                "default_path_present_repo_marker_unrecognized"
            )
        elif repo_managed_marker_present:
            external_launcher_readiness_status = "default_path_present_repo_marker_invalid"
        elif launcher_path_exists:
            external_launcher_readiness_status = (
                "default_path_present_ownership_unverified"
            )
        else:
            external_launcher_readiness_status = (
                "default_path_missing_repo_consumer_unprovisioned"
            )
    elif launcher_path_exists:
        external_launcher_readiness_status = (
            "external_script_path_present_consumer_capability_unverified"
        )
    else:
        external_launcher_readiness_status = (
            "external_script_path_missing_consumer_capability_unverified"
        )
    handoff_carrier_contract = {
        "status": "contract_ready",
        "env_var": CURRENT_PROXY_URL_HANDOFF_ENV,
        "surface_kind": "launcher_scoped_process_local_carrier",
        "current_proxy_truth_surface_field": "current_proxy_url",
        "persisted_truth_surface_forbidden": True,
        "working_candidate_truth_by_presence_forbidden": True,
        "top_level_runtime_truth_by_presence_forbidden": True,
        "ambient_authoritative_forbidden": True,
    }
    external_launcher_path_surface = {
        "status": "path_present" if launcher_path_exists else "path_missing",
        "env_var": "WBP_LAUNCHER_SCRIPT",
        "resolved_path": str(paths.launcher_script),
        "exists": launcher_path_exists,
        "role": "launcher_executable_path_surface",
        "path_kind": (
            "default_owned_provisioning_target"
            if launcher_path_is_default_target
            else "explicit_external_override"
        ),
        "default_owned_provisioning_target": str(
            default_launcher_script_path(paths.profile_dir)
        ),
        "repo_managed_marker_present": repo_managed_marker_present,
        "repo_managed_marker_valid": repo_managed_signature_valid,
        "repo_managed_marker_recognized": repo_managed_payload_recognized,
        "consumer_capability_by_path_presence_forbidden": True,
        "provisioning_ownership_by_path_presence_forbidden": True,
        "truth_surface": False,
    }
    launcher_consumer_contract = {
        "status": "repo_owned_default_consumer_provisioning_available",
        "launcher_protocol_scope": "bounded_launcher_smoke_seam",
        "consumer_kind": "bounded_launcher_script",
        "handoff_carrier_env_var": CURRENT_PROXY_URL_HANDOFF_ENV,
        "repo_owned_default_consumer_provisioned": repo_managed_payload_recognized,
        "external_launcher_readiness_status": external_launcher_readiness_status,
        "path_presence_not_capability_proof": True,
        "repo_managed_marker_required_for_refresh": True,
        "repo_managed_marker_present": repo_managed_marker_present,
        "repo_managed_marker_valid": repo_managed_signature_valid,
        "repo_managed_marker_recognized": repo_managed_payload_recognized,
        "default_path_non_clobber_required": True,
        "owner_controlled_activation_only": True,
    }
    engine_local_proxy_routing_contract = {
        "status": "contract_ready",
        "allowed": True,
        "routing_scope": "managed_runtime_child_process_only",
        "derived_from_handoff_carrier_only": True,
        "derived_proxy_env_keys": [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ],
        "derived_proxy_env_authoritative_for_control_plane_forbidden": True,
        "current_engine_consumption_claimed": False,
    }
    return {
        "status": "contract_ready",
        "owner_command_surface": "healthcheck --json",
        "status_delegates_to_owner": True,
        "sync_owner_forbidden": True,
        "launch_smoke_owner_forbidden": True,
        "launcher_lane_ineligible_sync_owner_recovery_surface": {
            "status": "available" if paths.sync_script.exists() else "unavailable",
            "command_surface": "sync --json",
            "owner_path_private": True,
            "allowed_when_launcher_lane_ineligible": True,
            "restart_scope": "managed_runtime_restart_with_proxy_refresh",
            "writes_managed_config_proxy_url": True,
            "reproof_required": True,
        },
        "state_file": str(paths.state_file),
        "activation_surface_status": "owner_path_private_launcher_activation_available",
        "activation_surface_kind": "repo_owned_handoff_env_var",
        "handoff_env_var": CURRENT_PROXY_URL_HANDOFF_ENV,
        "activation_value_source_field": "proxy_reprobe.working_candidate",
        "owner_activation_lane": "serialized_healthcheck_owner_path",
        "handoff_carrier_contract": handoff_carrier_contract,
        "external_launcher_path_surface": external_launcher_path_surface,
        "launcher_consumer_contract": launcher_consumer_contract,
        "engine_local_proxy_routing_contract": engine_local_proxy_routing_contract,
        "effectful_runtime_wiring_status": "bounded_private_launcher_lane_available",
        "managed_runtime_subprocess_only": True,
        "ambient_proxy_env_authoritative_forbidden": True,
        "control_plane_proxyless": True,
        "base_url_proxy_selection_surface_forbidden": True,
        "launcher_protocol_change_outside_repo_owned_handoff_forbidden": True,
        "managed_config_schema_widening_default": False,
        "config_toml_schema_widening_default": False,
        "absent_default_path_prerequisite_materialization_separate_from_eligibility": True,
        "launcher_consumer_status": launcher_consumer_contract["status"],
        "launcher_protocol_scope": launcher_consumer_contract[
            "launcher_protocol_scope"
        ],
        "engine_local_proxy_routing_allowed": engine_local_proxy_routing_contract[
            "allowed"
        ],
        "engine_local_proxy_routing_scope": engine_local_proxy_routing_contract[
            "routing_scope"
        ],
        "derived_proxy_env_authoritative_for_control_plane_forbidden": (
            engine_local_proxy_routing_contract[
                "derived_proxy_env_authoritative_for_control_plane_forbidden"
            ]
        ),
        "external_launcher_readiness_status": launcher_consumer_contract[
            "external_launcher_readiness_status"
        ],
        "repo_owned_default_consumer_provisioned": launcher_consumer_contract[
            "repo_owned_default_consumer_provisioned"
        ],
        "current_proxy_truth_surface": {
            "status": "contract_ready",
            "field": "current_proxy_url",
            "meaning": "current_live_outbound_proxy_truth",
            "persisted_last_known_good_separate": True,
            "working_candidate_separate": True,
        },
        "working_candidate_surface": {
            "status": "contract_ready",
            "field": "proxy_reprobe.working_candidate",
            "nested_evidence_only": True,
            "current_proxy_truth_by_presence_forbidden": True,
            "persisted_history_by_presence_forbidden": True,
        },
        "write_owner": "serialized_healthcheck_owner_path",
        "current_proxy_url_write_path_status": "owner_path_success_only_write_available",
        "candidate_probe_depth": PROXY_REPROBE_DEPTH,
        "candidate_probe_scope": "bounded_local_listener_reachability_only",
        "adoption_requires_same_owner_path_live_reproof": True,
        "post_adoption_runtime_validation_surface": "healthcheck.attestation",
        "separate_control_layer_deep_probe_surface_default": False,
        "adoption_from_candidate_liveness_alone_forbidden": True,
        "adoption_from_last_known_good_alone_forbidden": True,
        "adoption_from_working_candidate_alone_forbidden": True,
        "same_current_reconfirm_not_adoption": True,
        "candidate_existence_alone_not_ok": True,
        "top_level_ok_requires_live_runtime_reproof": True,
        "proxy_path_broken_remains_valid_without_live_reproof": True,
        "proxy_reprobe_failed_remains_valid_without_candidate": True,
        "changed_files_visibility_required": True,
        "new_persisted_adoption_metadata_default": False,
        "nested_adoption_result_surface": {
            "status": "owner_path_emitted",
            "field": "proxy_reprobe_adoption_result",
            "command_packet_only_default": True,
        },
    }


def build_last_known_good_proxy_surface(
    paths: RuntimePaths, state: dict[str, Any], current_proxy_url: str
) -> dict[str, Any]:
    proxy_url = str(state.get(LAST_KNOWN_GOOD_PROXY_URL_FIELD) or "")
    observed_at_utc = str(state.get(LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD) or "")
    materialized = bool(proxy_url or observed_at_utc)
    shape_valid = bool(proxy_url and observed_at_utc)
    bounded_local_candidate = bool(proxy_url) and parse_local_proxy_candidate(proxy_url) is not None
    if shape_valid and bounded_local_candidate:
        status = "materialized"
    elif materialized and shape_valid:
        status = "materialized_unusable"
    elif materialized:
        status = "materialized_shape_invalid"
    else:
        status = "declared_not_materialized"
    return {
        "status": status,
        "state_file": str(paths.state_file),
        "state_fields": [
            LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD,
        ],
        "proxy_url": proxy_url,
        "observed_at_utc": observed_at_utc,
        "matches_current_proxy_url": bool(proxy_url) and proxy_url == current_proxy_url,
        "eligible_for_bounded_reprobe": status == "materialized",
        "current_proxy_url_separate": True,
        "final_live_truth_without_live_checks": False,
    }


def refresh_last_known_good_proxy_from_healthcheck(
    paths: RuntimePaths,
    state: dict[str, Any],
    *,
    current_proxy_url: str,
    attestation_ok: bool,
    reported_effective_mode: str,
) -> dict[str, Any]:
    if not attestation_ok or reported_effective_mode != "managed":
        return state
    if parse_local_proxy_candidate(current_proxy_url) is None:
        return state

    refreshed_state = dict(state)
    refreshed_state[LAST_KNOWN_GOOD_PROXY_URL_FIELD] = current_proxy_url
    refreshed_state[LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD] = now_iso()

    # Refuse to persist if the attested current proxy drifted before the
    # serialized owner-path write lock was acquired.
    with serialized_lock(paths):
        live_state = read_json(paths.state_file, required=False)
        live_current_proxy_url = str(live_state.get("current_proxy_url") or "")
        if live_current_proxy_url != current_proxy_url:
            return state
        live_state[LAST_KNOWN_GOOD_PROXY_URL_FIELD] = current_proxy_url
        live_state[LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD] = refreshed_state[
            LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD
        ]
        write_json_atomic(paths.state_file, live_state)
    return refreshed_state


def get_reported_current_proxy_url(
    paths: RuntimePaths, state: dict[str, Any], reported_effective_mode: str
) -> str:
    current_proxy_url = str(state.get("current_proxy_url", ""))
    if reported_effective_mode != "stable":
        return current_proxy_url
    stable_proxy_url = str(read_stable_proxy_url(paths) or "")
    if parse_local_proxy_candidate(stable_proxy_url) is None:
        return current_proxy_url
    return stable_proxy_url


def get_stable_runtime_consumer_selection_context(
    paths: RuntimePaths,
    registry: dict[str, Any],
    policy_drift: dict[str, Any],
) -> dict[str, Any]:
    observed_path, observed_source = get_stable_auth_inventory_source(paths)
    approved_target = get_approved_repair_target_reference(paths)
    repair_plan = build_stable_repair_transaction_plan(
        paths,
        registry,
        policy_drift,
        {"status": "available", "machine_error_code": "OK", "holder_pid": None},
        mode="dry_run",
    )
    target_plan = repair_plan.get("target_reconciliation_plan", {})
    approved_target_ready = (
        approved_target.get("status") == "materialized_aligned"
        and not target_plan.get("target_would_add")
        and not target_plan.get("target_would_prune")
    )
    desired_path = (
        paths.repair_target_inventory_dir if approved_target_ready else observed_path
    )
    desired_kind = (
        "approved_repair_target"
        if approved_target_ready
        else "observed_stable_inventory_source"
    )
    desired_status = (
        "approved_target_selected"
        if approved_target_ready
        else "observed_source_selected"
    )
    desired_reason = (
        "approved_target_materialized_and_reconciled"
        if approved_target_ready
        else "approved_target_not_ready_for_runtime_consumption"
    )
    return {
        "observed_path": observed_path,
        "observed_source": observed_source,
        "approved_target": approved_target,
        "target_plan": target_plan,
        "approved_target_ready": approved_target_ready,
        "desired_path": desired_path,
        "desired_kind": desired_kind,
        "desired_status": desired_status,
        "desired_reason": desired_reason,
    }


def get_valid_stable_runtime_consumer_snapshot(
    state: dict[str, Any],
) -> dict[str, Any] | None:
    snapshot = state.get(STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC)
    if not isinstance(snapshot, dict):
        return None
    if not all(field in snapshot for field in STABLE_RUNTIME_CONSUMER_SNAPSHOT_REQUIRED_FIELDS):
        return None
    return snapshot


def build_stable_runtime_consumer_contract(
    paths: RuntimePaths,
    registry: dict[str, Any],
    policy_drift: dict[str, Any],
    state: dict[str, Any],
    health_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selection = get_stable_runtime_consumer_selection_context(paths, registry, policy_drift)
    observed_path = Path(selection["observed_path"])
    observed_source = dict(selection["observed_source"])
    approved_target = dict(selection["approved_target"])
    desired_path = Path(selection["desired_path"])
    desired_kind = str(selection["desired_kind"])
    desired_status = str(selection["desired_status"])
    desired_reason = str(selection["desired_reason"])
    approved_target_ready = bool(selection["approved_target_ready"])
    effective_kind = "observed_stable_inventory_source"
    effective_path = observed_path
    effective_status = "observed_source_active"
    effective_reason = "stable_runtime_observation_still_points_to_observed_source"
    effective_matches_approved_target = (
        approved_target_ready and observed_path == paths.repair_target_inventory_dir
    )
    if effective_matches_approved_target:
        effective_kind = "approved_repair_target"
        effective_path = paths.repair_target_inventory_dir
        effective_status = "approved_target_active_by_observation"
        effective_reason = "stable_runtime_observation_matches_approved_target"
    live_stable_runtime_ok = bool(health_payload) and (
        health_payload.get("status") == "ok"
        and str(health_payload.get("effective_mode")) == "stable"
    )
    snapshot = get_valid_stable_runtime_consumer_snapshot(state)
    snapshot_freshness = (
        selected_backend_snapshot_freshness(snapshot.get("observed_at_utc"))
        if snapshot
        else "unknown"
    )
    if live_stable_runtime_ok and snapshot and snapshot_freshness == "fresh":
        snapshot_selected_kind = str(snapshot.get("selected_source_kind"))
        snapshot_selected_path = Path(str(snapshot.get("selected_source_path")))
        snapshot_outcome = str(snapshot.get("activation_outcome"))
        if (
            snapshot_outcome == STABLE_RUNTIME_APPROVED_TARGET_ACTIVATION_OUTCOME
            and snapshot_selected_kind == "approved_repair_target"
            and snapshot_selected_path == paths.repair_target_inventory_dir
            and str(snapshot.get("activation_method")) == "process_local_env_override"
            and str(snapshot.get("selected_config_file"))
            == str(paths.stable_runtime_generated_config_file)
        ):
            effective_kind = "approved_repair_target"
            effective_path = paths.repair_target_inventory_dir
            effective_status = "approved_target_active_by_activation_evidence"
            effective_reason = (
                "live_runtime_ok_and_activation_evidence_confirm_approved_target"
            )
        elif snapshot_selected_kind == "observed_stable_inventory_source" and snapshot_outcome in {
            STABLE_RUNTIME_OBSERVED_SOURCE_SELECTED_OUTCOME,
            STABLE_RUNTIME_OBSERVED_SOURCE_FALLBACK_OUTCOME,
        }:
            effective_kind = "observed_stable_inventory_source"
            effective_path = snapshot_selected_path
            if snapshot_outcome == STABLE_RUNTIME_OBSERVED_SOURCE_FALLBACK_OUTCOME:
                effective_status = "observed_source_active_by_fallback_evidence"
                effective_reason = "live_runtime_ok_and_fallback_evidence_confirm_observed_source"
            else:
                effective_status = "observed_source_active_by_selection_evidence"
                effective_reason = "live_runtime_ok_and_selection_evidence_confirm_observed_source"
    desired_matches_effective = (
        desired_kind == effective_kind and desired_path == effective_path
    )
    if desired_matches_effective:
        readiness_status = "aligned"
        readiness_code = "OK"
        readiness_reason = "desired_consumer_source_matches_effective_observation"
        readiness_next_step = "none"
    elif (
        snapshot
        and str(snapshot.get("activation_outcome"))
        == STABLE_RUNTIME_OBSERVED_SOURCE_FALLBACK_OUTCOME
        and effective_kind == "observed_stable_inventory_source"
    ):
        readiness_status = "fallback_active"
        readiness_code = "STABLE_RUNTIME_CONSUMER_FALLBACK_ACTIVE"
        readiness_reason = "approved_target_activation_did_not_complete_and_observed_source_fallback_is_active"
        readiness_next_step = "investigate_activation_gap"
    elif desired_kind == "approved_repair_target":
        readiness_status = "activation_pending"
        readiness_code = "STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING"
        readiness_reason = "desired_consumer_source_differs_from_effective_observation"
        readiness_next_step = "activation_contour"
    else:
        readiness_status = "mismatch"
        readiness_code = "STABLE_RUNTIME_CONSUMER_EFFECTIVE_DESIRED_MISMATCH"
        readiness_reason = "effective_consumer_source_differs_from_current_desired_selection"
        readiness_next_step = "inspect_runtime_consumer_state"
    return {
        "status": "contract_ready",
        "observed_stable_inventory_source": observed_source,
        "approved_repair_target_reference": approved_target,
        "desired_stable_runtime_consumer_source": {
            "status": desired_status,
            "source_kind": desired_kind,
            "resolved_path": str(desired_path),
            "selection_reason": desired_reason,
        },
        "effective_stable_runtime_consumer_source": {
            "status": effective_status,
            "source_kind": effective_kind,
            "resolved_path": str(effective_path),
            "observation_reason": effective_reason,
            "matches_desired": desired_matches_effective,
        },
        "derived_stable_runtime_config_surface": (
            build_stable_runtime_generated_config_surface(paths, state)
        ),
        "launcher_handoff_contract": build_stable_runtime_launcher_handoff_contract(
            paths
        ),
        "activation_evidence_surface": build_stable_runtime_activation_evidence_surface(
            paths, state
        ),
        "effective_truth_contract": build_stable_runtime_effective_truth_contract(),
        "baseline_stable_config_surface": {
            "config_file": str(paths.stable_config),
            "ownership": "engine_adjacent",
            "role": "observed_source_discovery_surface",
        },
        "fallback_contract": {
            "status": "contract_ready",
            "fallback_allowed": True,
            "fallback_source_kind": "observed_stable_inventory_source",
            "silent_fallback_forbidden": True,
            "desired_source_remains_visible": True,
            "effective_source_must_report_fallback": True,
        },
        "deterministic_stable_recovery_contract": (
            build_deterministic_stable_recovery_contract(paths)
        ),
        "consumer_activation_readiness": {
            "status": readiness_status,
            "machine_error_code": readiness_code,
            "reason": readiness_reason,
            "next_step": readiness_next_step,
        },
    }


def build_generated_stable_runtime_config_text(paths: RuntimePaths) -> str:
    if not paths.stable_config.exists():
        raise RuntimeErrorInfo(
            f"Missing stable config: {paths.stable_config}",
            machine_error_code="MISSING_STABLE_CONFIG",
            operator_action="user_action",
        )
    auth_dir_line = f'auth-dir: "{paths.repair_target_inventory_dir}"'
    lines = paths.stable_config.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    replaced = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("auth-dir:"):
            rewritten.append(auth_dir_line)
            replaced = True
        else:
            rewritten.append(raw_line)
    if not replaced:
        rewritten.append(auth_dir_line)
    return "\n".join(rewritten)


def write_stable_runtime_consumer_snapshot(
    paths: RuntimePaths,
    snapshot: dict[str, Any],
    *,
    lock_acquired: bool = False,
) -> None:
    mutation_lock = nullcontext() if lock_acquired else serialized_lock(paths)
    with mutation_lock:
        state = read_json(paths.state_file, required=False)
        state[STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC] = snapshot
        write_json_atomic(paths.state_file, state)


def build_stable_runtime_consumer_snapshot_payload(
    *,
    activation_method: str,
    selected_config_file: str,
    selected_source_kind: str,
    selected_source_path: str,
    activation_outcome: str,
    fallback_reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "activation_method": activation_method,
        "selected_config_file": selected_config_file,
        "selected_source_kind": selected_source_kind,
        "selected_source_path": selected_source_path,
        "activation_outcome": activation_outcome,
        "fallback_reason": fallback_reason,
        "observed_at_utc": now_iso(),
    }


def emit_subprocess_output(*, stdout: str, stderr: str) -> None:
    if stderr:
        sys.stderr.write(stderr)
    if stdout:
        sys.stderr.write(stdout)


def runtime_write_surface_candidates(paths: RuntimePaths) -> list[Path]:
    return [
        paths.registry_file,
        paths.managed_config_file,
        paths.config_toml,
        paths.state_file,
        paths.runtime_effective_mode_file,
        paths.stable_runtime_generated_config_file,
        paths.launcher_script,
        managed_pid_path(paths),
    ]


def run_stable_runtime_launcher_attempt(
    paths: RuntimePaths,
    selection: dict[str, Any],
) -> StableRuntimeLaunchAttempt:
    desired_kind = str(selection["desired_kind"])
    observed_path = Path(selection["observed_path"])
    launcher_env = build_launcher_subprocess_env(paths)
    launcher_env[STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV] = str(paths.stable_config)
    activation_attempted = False
    generated_config_regenerated = False
    activation_method = "baseline_stable_config"
    selected_config_file = str(paths.stable_config)
    selected_source_kind = "observed_stable_inventory_source"
    selected_source_path = str(observed_path)
    with serialized_lock(paths):
        if desired_kind == "approved_repair_target":
            write_text_atomic(
                paths.stable_runtime_generated_config_file,
                build_generated_stable_runtime_config_text(paths),
            )
            launcher_env[STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV] = str(
                paths.stable_runtime_generated_config_file
            )
            activation_attempted = True
            generated_config_regenerated = True
            activation_method = "process_local_env_override"
            selected_config_file = str(paths.stable_runtime_generated_config_file)
            selected_source_kind = "approved_repair_target"
            selected_source_path = str(paths.repair_target_inventory_dir)
        result = subprocess.run(
            [str(paths.launcher_script), "smoke"],
            capture_output=True,
            text=True,
            env=launcher_env,
            check=False,
        )
    return StableRuntimeLaunchAttempt(
        desired_kind=desired_kind,
        observed_path=observed_path,
        activation_attempted=activation_attempted,
        generated_config_regenerated=generated_config_regenerated,
        activation_method=activation_method,
        selected_config_file=selected_config_file,
        selected_source_kind=selected_source_kind,
        selected_source_path=selected_source_path,
        launcher_exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def build_deterministic_stable_recovery_result(
    *,
    delegated_from_status: bool,
    attempted: bool,
    entry_lane: str,
    outcome: str,
    re_enable_method: str,
    selected_source_kind: str,
    selected_source_path: str,
    generated_config_regenerated: bool,
    snapshot_refreshed: bool,
    fallback_reason: str,
    live_runtime_observation_confirmed: bool,
    confirmation_basis: str,
    effectful_claim_allowed: bool,
) -> dict[str, Any]:
    if not attempted:
        status = "not_invoked"
        guardrail_status = "not_invoked"
    elif outcome == "recovery_failed_before_stable_healthy":
        status = "failed"
        guardrail_status = "blocked"
    elif effectful_claim_allowed:
        status = "completed"
        guardrail_status = "confirmed"
    else:
        status = "completed"
        guardrail_status = "observation_only"
    return {
        "status": status,
        "owner_command_surface": "healthcheck --json",
        "delegated_from_status": delegated_from_status,
        "attempted": attempted,
        "entry_lane": entry_lane,
        "outcome": outcome,
        "re_enable_method": re_enable_method,
        "selected_source_kind": selected_source_kind,
        "selected_source_path": selected_source_path,
        "generated_config_regenerated": generated_config_regenerated,
        "snapshot_refreshed": snapshot_refreshed,
        "fallback_reason": fallback_reason,
        "live_runtime_observation_confirmed": live_runtime_observation_confirmed,
        "confirmation_basis": confirmation_basis,
        "effectful_claim_allowed": effectful_claim_allowed,
        "guardrail_status": guardrail_status,
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


def build_stable_repair_apply_authority(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "source_of_copy_authority": {
            "source_kind": "eligible_registry_auth_refs",
            "policy_input_surface": "backend-registry.json",
            "source_files_mutable": False,
            "registry_auth_ref_source_mutation_authority": False,
            "observed_source_delete_authority": False,
            "engine_owned_delete_authority": False,
        },
        "target_mutation_authority": {
            "target_identity": APPROVED_REPAIR_TARGET_IDENTITY,
            "target_kind": APPROVED_REPAIR_TARGET_KIND,
            "inventory_dir": str(paths.repair_target_inventory_dir),
            "write_scope": "approved_target_inventory_only",
            "exactness": "exact_approved_set",
            "prune_authority": "control_owned_target_entries_only",
        },
        "field_mapping": {
            "observed_source_fields": [
                "observed_source_matching_allowed_auths",
                "observed_source_disallowed_auths",
                "observed_source_missing_allowed_auths",
                "observed_source_unknown_auths",
            ],
            "target_reconciliation_fields": [
                "target_would_add",
                "target_would_prune",
                "target_would_keep",
            ],
        },
    }


def build_repair_target_contract_surface(paths: RuntimePaths) -> dict[str, Any]:
    return {
        "approved_repair_target_reference": get_approved_repair_target_reference(paths),
        "target_switch_transaction_metadata_surface": (
            get_target_switch_transaction_metadata_surface(paths)
        ),
    }


def build_registry_source_input_item(backend: dict[str, Any]) -> dict[str, Any]:
    auth_ref = Path(str(backend.get("auth_ref"))).expanduser()
    return {
        "backend_id": backend.get("id"),
        "auth_basename": get_auth_basename(backend.get("auth_ref")),
        "auth_ref": str(auth_ref),
        "source_exists": auth_ref.is_file(),
        "pool": backend.get("pool"),
        "status": backend.get("status"),
    }


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_experimental_package_repo_root() -> Path:
    module_dir = Path(__file__).resolve().parent
    for candidate in (module_dir, *module_dir.parents):
        if (
            (candidate / EXPERIMENTAL_PACKAGE_REPO_MARKER_FILE).is_file()
            and (candidate / EXPERIMENTAL_PACKAGE_REPO_MARKER_DIR).is_dir()
        ):
            return candidate
    raise RuntimeErrorInfo(
        (
            "Failed to determine experimental package source root from module location. "
            "Set WBP_PACKAGE_SOURCE_ROOT explicitly."
        ),
        machine_error_code="PACKAGE_SOURCE_ROOT_UNRESOLVED",
        severity="recoverable",
        operator_action="user_action",
    )


def get_experimental_package_source_root() -> Path:
    configured_root = os.environ.get("WBP_PACKAGE_SOURCE_ROOT")
    source_root = (
        Path(configured_root).expanduser().resolve()
        if configured_root
        else discover_experimental_package_repo_root()
    )
    if not source_root.exists() or not source_root.is_dir():
        raise RuntimeErrorInfo(
            f"Experimental package source root is not a directory: {source_root}",
            machine_error_code="PACKAGE_SOURCE_ROOT_INVALID",
            severity="recoverable",
            operator_action="user_action",
        )
    return source_root


def is_experimental_package_root_file_allowed(relative_path: Path) -> bool:
    return (
        len(relative_path.parts) == 1
        and relative_path.suffix.lower() in EXPERIMENTAL_PACKAGE_ALLOWED_ROOT_SUFFIXES
    )


def is_experimental_package_path_excluded(relative_path: Path) -> bool:
    lowered_parts = [part.lower() for part in relative_path.parts]
    basename = relative_path.name.lower()
    if basename.startswith("."):
        return True
    if any(part.startswith(".") for part in lowered_parts):
        return True
    if basename in EXPERIMENTAL_PACKAGE_EXCLUDED_BASENAMES:
        return True
    if any(part in EXPERIMENTAL_PACKAGE_EXCLUDED_DIR_PARTS for part in lowered_parts):
        return True
    suffixes = {suffix.lower() for suffix in relative_path.suffixes}
    if suffixes.intersection(EXPERIMENTAL_PACKAGE_EXCLUDED_FILE_SUFFIXES):
        return True
    stem_tokens = {
        token for token in re.split(r"[^a-z0-9]+", relative_path.stem.lower()) if token
    }
    if stem_tokens.intersection(EXPERIMENTAL_PACKAGE_EXCLUDED_STEM_TOKENS):
        return True
    return False


def list_experimental_package_files(source_root: Path, output_dir: Path) -> list[Path]:
    package_files: list[Path] = []
    for root_entry in sorted(source_root.iterdir(), key=lambda item: item.name):
        if root_entry.name.startswith("."):
            continue
        if root_entry.resolve() == output_dir:
            continue
        if root_entry.is_file():
            relative_path = root_entry.relative_to(source_root)
            if is_experimental_package_root_file_allowed(relative_path):
                package_files.append(root_entry)
            continue
        if not root_entry.is_dir():
            continue
        if root_entry.name not in EXPERIMENTAL_PACKAGE_ALLOWED_TOP_LEVEL_DIRS:
            continue
        for entry in sorted(root_entry.rglob("*")):
            if not entry.is_file() or entry.is_symlink():
                continue
            if "__pycache__" in entry.parts:
                continue
            if output_dir in entry.parents:
                continue
            if is_experimental_package_path_excluded(entry.relative_to(source_root)):
                continue
            package_files.append(entry)
    return package_files


def read_experimental_plan_metadata(source_root: Path) -> dict[str, str]:
    plan_path = source_root / "MASTER_PLAN.md"
    if not plan_path.is_file():
        return {}
    plan_version = ""
    plan_date = ""
    for raw_line in plan_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("PLAN_VERSION:"):
            plan_version = line.split(":", 1)[1].strip()
        if line.startswith("PLAN_DATE:"):
            plan_date = line.split(":", 1)[1].strip()
    metadata: dict[str, str] = {}
    if plan_version:
        metadata["plan_version"] = plan_version
    if plan_date:
        metadata["plan_date"] = plan_date
    return metadata


def run_package_experimental_build(
    _paths: RuntimePaths, output_dir_raw: str
) -> dict[str, Any]:
    output_dir = Path(output_dir_raw).expanduser().resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeErrorInfo(
            f"Failed to prepare output directory: {output_dir} ({exc})",
            machine_error_code="PACKAGE_OUTPUT_DIR_INVALID",
            severity="recoverable",
            operator_action="user_action",
        ) from exc

    source_root = get_experimental_package_source_root()
    package_files = list_experimental_package_files(source_root, output_dir)
    artifact_path = output_dir / EXPERIMENTAL_PACKAGE_ARTIFACT_NAME
    manifest_path = output_dir / EXPERIMENTAL_PACKAGE_MANIFEST_NAME
    metadata_path = output_dir / EXPERIMENTAL_PACKAGE_METADATA_NAME

    try:
        with tarfile.open(artifact_path, "w:gz") as archive:
            for file_path in package_files:
                archive.add(file_path, arcname=str(file_path.relative_to(source_root)))
        artifact_sha256 = hash_file(artifact_path)
        metadata = {
            "schema_version": EXPERIMENTAL_PACKAGE_SCHEMA_VERSION,
            "created_at_utc": now_iso(),
            "source_root": str(source_root),
            "allowlist": {
                "top_level_dirs": sorted(EXPERIMENTAL_PACKAGE_ALLOWED_TOP_LEVEL_DIRS),
                "root_file_suffixes": sorted(EXPERIMENTAL_PACKAGE_ALLOWED_ROOT_SUFFIXES),
            },
            "included_file_count": len(package_files),
            "included_files": [
                str(path.relative_to(source_root)) for path in package_files
            ],
            **read_experimental_plan_metadata(source_root),
        }
        manifest = {
            "schema_version": EXPERIMENTAL_PACKAGE_SCHEMA_VERSION,
            "created_at_utc": now_iso(),
            "artifact_path": artifact_path.name,
            "artifact_sha256": artifact_sha256,
            "artifact_format": "tar.gz",
            "metadata_path": metadata_path.name,
        }
        write_json_artifact(metadata_path, metadata)
        write_json_artifact(manifest_path, manifest)
    except OSError as exc:
        raise RuntimeErrorInfo(
            f"Failed to build experimental package: {exc}",
            machine_error_code="PACKAGE_BUILD_FAILED",
            severity="recoverable",
            operator_action="retry",
        ) from exc

    changed_files = [str(artifact_path), str(manifest_path), str(metadata_path)]
    return build_command_payload(
        ok=True,
        human_message=(
            f"Experimental package built with {len(package_files)} allowlisted files."
        ),
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=changed_files,
        extra={
            "package_result": {
                "status": "built",
                "source_root": str(source_root),
                "artifact_path": str(artifact_path),
                "manifest_path": str(manifest_path),
                "metadata_path": str(metadata_path),
                "artifact_sha256": artifact_sha256,
                "included_file_count": len(package_files),
            }
        },
    )


def run_package_experimental_verify(
    _paths: RuntimePaths, manifest_raw: str
) -> dict[str, Any]:
    manifest_path = Path(manifest_raw).expanduser().resolve()
    if not manifest_path.is_file():
        raise RuntimeErrorInfo(
            f"Missing experimental package manifest: {manifest_path}",
            machine_error_code="PACKAGE_MANIFEST_MISSING",
            severity="recoverable",
            operator_action="user_action",
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeErrorInfo(
            f"Invalid experimental package manifest JSON: {exc}",
            machine_error_code="PACKAGE_MANIFEST_INVALID",
            severity="recoverable",
            operator_action="user_action",
        ) from exc
    if not isinstance(manifest, dict):
        raise RuntimeErrorInfo(
            "Experimental package manifest must be a JSON object.",
            machine_error_code="PACKAGE_MANIFEST_INVALID",
            severity="recoverable",
            operator_action="user_action",
        )
    artifact_path_raw = manifest.get("artifact_path")
    expected_sha256 = manifest.get("artifact_sha256")
    if not artifact_path_raw or not expected_sha256:
        raise RuntimeErrorInfo(
            "Experimental package manifest is missing required checksum fields.",
            machine_error_code="PACKAGE_MANIFEST_INVALID",
            severity="recoverable",
            operator_action="user_action",
        )
    artifact_path_candidate = Path(str(artifact_path_raw))
    artifact_path = (
        artifact_path_candidate
        if artifact_path_candidate.is_absolute()
        else (manifest_path.parent / artifact_path_candidate).resolve()
    )
    if not artifact_path.is_file():
        raise RuntimeErrorInfo(
            f"Missing experimental package artifact: {artifact_path}",
            machine_error_code="PACKAGE_ARTIFACT_MISSING",
            severity="recoverable",
            operator_action="user_action",
        )
    observed_sha256 = hash_file(artifact_path)
    checksum_match = observed_sha256 == str(expected_sha256)
    if not checksum_match:
        return build_command_payload(
            ok=False,
            human_message="Experimental package checksum verification failed.",
            machine_error_code="PACKAGE_CHECKSUM_MISMATCH",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "package_result": {
                    "status": "checksum_mismatch",
                    "manifest_path": str(manifest_path),
                    "artifact_path": str(artifact_path),
                    "artifact_sha256_expected": str(expected_sha256),
                    "artifact_sha256_observed": observed_sha256,
                    "checksum_match": False,
                }
            },
        )
    return build_command_payload(
        ok=True,
        human_message="Experimental package checksum verification passed.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "package_result": {
                "status": "verified",
                "manifest_path": str(manifest_path),
                "artifact_path": str(artifact_path),
                "artifact_sha256_expected": str(expected_sha256),
                "artifact_sha256_observed": observed_sha256,
                "checksum_match": True,
            }
        },
    )


def list_target_inventory_entries(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return sorted(entry.name for entry in path.iterdir())


def snapshot_target_inventory_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "entries": {}, "non_auth_entries": []}
    if not path.is_dir():
        return {"exists": True, "kind": "not_dir", "entries": {}, "non_auth_entries": []}
    entries = {}
    non_auth_entries = []
    for entry in sorted(path.iterdir(), key=lambda item: item.name):
        if entry.is_file() and entry.name.startswith("codex-") and entry.suffix == ".json":
            entries[entry.name] = hash_file(entry)
        else:
            non_auth_entries.append(entry.name)
    return {"exists": True, "kind": "dir", "entries": entries, "non_auth_entries": non_auth_entries}


def detect_target_inventory_changed_files(
    before: dict[str, Any], after: dict[str, Any], target_dir: Path
) -> list[str]:
    changed: list[str] = []
    if before.get("exists") != after.get("exists"):
        changed.append(str(target_dir))
    before_entries = before.get("entries", {})
    after_entries = after.get("entries", {})
    for name in sorted(set(before_entries) | set(after_entries)):
        if before_entries.get(name) != after_entries.get(name):
            changed.append(str(target_dir / name))
    for name in sorted(set(before.get("non_auth_entries", [])) | set(after.get("non_auth_entries", []))):
        changed.append(str(target_dir / name))
    return changed


def snapshot_stable_repair_guard_surfaces(
    paths: RuntimePaths, source_paths: list[Path]
) -> dict[str, Any]:
    stable_auth_dir, inventory_source = get_stable_auth_inventory_source(paths)
    observed_inventory = {}
    if stable_auth_dir.is_dir():
        observed_inventory = {
            path.name: hash_file(path)
            for path in sorted(stable_auth_dir.glob("codex-*.json"))
        }
    source_file_digests = {
        str(path): hash_file(path)
        for path in sorted(source_paths, key=lambda item: str(item))
        if path.is_file()
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
        "approved_repair_target_reference": snapshot_path_state(
            paths.repair_target_reference_file
        ),
        "target_switch_transaction_metadata": snapshot_path_state(
            paths.target_switch_transaction_file
        ),
        "observed_inventory_source": inventory_source,
        "observed_inventory": observed_inventory,
        "source_file_digests": source_file_digests,
    }


def build_stable_repair_source_map(
    transaction_plan: dict[str, Any],
) -> dict[str, Path]:
    source_inputs = transaction_plan.get("registry_source_inputs", {}).get(
        "eligible_registry_auth_refs", []
    )
    missing_inputs = transaction_plan.get("registry_source_inputs", {}).get(
        "source_copy_missing_auth_refs", []
    )
    collision_inputs = transaction_plan.get("registry_source_inputs", {}).get(
        "source_copy_basename_collisions", []
    )
    if missing_inputs:
        raise RuntimeErrorInfo(
            "Stable repair apply blocked by missing eligible source auth file.",
            machine_error_code="REPAIR_SOURCE_AUTH_REF_MISSING",
            severity="recoverable",
            operator_action="user_action",
        )
    if collision_inputs:
        raise RuntimeErrorInfo(
            "Stable repair apply blocked by source basename collision.",
            machine_error_code="REPAIR_SOURCE_BASENAME_COLLISION",
            severity="recoverable",
            operator_action="user_action",
        )

    return {
        str(item.get("auth_basename")): Path(str(item.get("auth_ref"))).expanduser()
        for item in source_inputs
    }


def verify_stable_repair_target_inventory(
    target_dir: Path, source_map: dict[str, Path]
) -> None:
    if not target_dir.is_dir():
        raise RuntimeErrorInfo(
            "Stable repair apply verification failed because the target inventory is missing.",
            machine_error_code="STABLE_REPAIR_VERIFICATION_FAILED",
            severity="recoverable",
            operator_action="user_action",
        )
    unexpected_entries = [
        entry.name
        for entry in sorted(target_dir.iterdir(), key=lambda item: item.name)
        if not (entry.is_file() and entry.name in source_map)
    ]
    if unexpected_entries:
        raise RuntimeErrorInfo(
            "Stable repair apply verification failed because target inventory contains unexpected entries.",
            machine_error_code="STABLE_REPAIR_VERIFICATION_FAILED",
            severity="recoverable",
            operator_action="user_action",
        )
    actual_names = sorted(path.name for path in target_dir.glob("codex-*.json"))
    expected_names = sorted(source_map)
    if actual_names != expected_names:
        raise RuntimeErrorInfo(
            "Stable repair apply verification failed because target inventory set is not exact.",
            machine_error_code="STABLE_REPAIR_VERIFICATION_FAILED",
            severity="recoverable",
            operator_action="user_action",
        )
    for basename, source_path in source_map.items():
        if (target_dir / basename).read_bytes() != source_path.read_bytes():
            raise RuntimeErrorInfo(
                "Stable repair apply verification failed because a target file does not match its source bytes.",
                machine_error_code="STABLE_REPAIR_VERIFICATION_FAILED",
                severity="recoverable",
                operator_action="user_action",
            )


def verify_stable_repair_apply_result(
    paths: RuntimePaths, source_map: dict[str, Path], guard_before: dict[str, Any]
) -> None:
    verify_stable_repair_target_inventory(paths.repair_target_inventory_dir, source_map)
    if snapshot_stable_repair_guard_surfaces(paths, list(source_map.values())) != guard_before:
        raise RuntimeErrorInfo(
            "Stable repair apply verification failed because forbidden or source surfaces changed.",
            machine_error_code="STABLE_REPAIR_VERIFICATION_FAILED",
            severity="recoverable",
            operator_action="user_action",
        )


def stage_stable_repair_inventory(stage_dir: Path, source_map: dict[str, Path]) -> None:
    for basename, source_path in source_map.items():
        shutil.copy2(source_path, stage_dir / basename)


def remove_tree_if_exists(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)


def rollback_stable_repair_apply(
    *,
    target_dir: Path,
    stage_dir: Path,
    backup_dir: Path | None,
) -> None:
    remove_tree_if_exists(stage_dir)
    if backup_dir and backup_dir.exists():
        remove_tree_if_exists(target_dir)
        backup_dir.replace(target_dir)
        return
    remove_tree_if_exists(target_dir)


def build_stable_repair_transaction_plan(
    paths: RuntimePaths,
    registry: dict[str, Any],
    policy_drift: dict[str, Any],
    lock_preflight: dict[str, Any],
    *,
    mode: str = "dry_run",
) -> dict[str, Any]:
    backends = registry.get("backends") or []
    stable_auth_dir, _ = get_stable_auth_inventory_source(paths)
    observed_inventory = (
        sorted(path.name for path in stable_auth_dir.glob("codex-*.json"))
        if stable_auth_dir.is_dir()
        else []
    )
    observed_inventory_set = set(observed_inventory)
    target_inventory = (
        sorted(path.name for path in paths.repair_target_inventory_dir.glob("codex-*.json"))
        if paths.repair_target_inventory_dir.is_dir()
        else []
    )
    target_inventory_set = set(target_inventory)
    eligible_registry_auth_refs = []
    observed_source_matching_allowed_auths = []
    for backend in backends:
        auth_basename = get_auth_basename(backend.get("auth_ref"))
        if not auth_basename:
            continue
        allowed, _ = is_stable_auth_allowed(backend)
        if not allowed:
            continue
        item = build_registry_source_input_item(backend)
        eligible_registry_auth_refs.append(item)
        if auth_basename in observed_inventory_set:
            observed_source_matching_allowed_auths.append(item)

    observed_source_unknown_auths = [
        {
            "auth_basename": auth_basename,
            "reason": "auth_not_in_registry",
        }
        for auth_basename in policy_drift.get("unknown_auths", [])
    ]
    observed_source_disallowed_auths = [
        {
            "backend_id": item.get("backend_id"),
            "auth_basename": item.get("auth_basename"),
            "pool": item.get("pool"),
            "manual_hold": item.get("manual_hold"),
            "status": item.get("status"),
            "enabled": item.get("enabled", True),
            "reason": item.get("reason", "auth_not_allowed_by_registry_policy"),
        }
        for item in policy_drift.get("disallowed_configured_auths", [])
    ]
    observed_source_missing_allowed_auths = [
        {
            "backend_id": item.get("backend_id"),
            "auth_basename": item.get("auth_basename"),
            "pool": item.get("pool"),
            "manual_hold": item.get("manual_hold"),
            "status": item.get("status"),
            "enabled": item.get("enabled", True),
            "reason": item.get("reason", "auth_ref_not_in_stable_inventory"),
        }
        for item in policy_drift.get("missing_auths", [])
    ]
    source_copy_missing_auth_refs = [
        {
            "backend_id": item.get("backend_id"),
            "auth_basename": item.get("auth_basename"),
            "auth_ref": item.get("auth_ref"),
            "reason": "eligible_registry_auth_ref_missing_on_disk",
        }
        for item in eligible_registry_auth_refs
        if item.get("source_exists") is False
    ]
    target_would_keep = [
        item
        for item in eligible_registry_auth_refs
        if item.get("auth_basename") in target_inventory_set
    ]
    target_would_add = [
        {
            **item,
            "reason": "eligible_registry_auth_ref_missing_from_target_inventory",
        }
        for item in eligible_registry_auth_refs
        if item.get("auth_basename") not in target_inventory_set
    ]
    eligible_target_auths = {
        item.get("auth_basename")
        for item in eligible_registry_auth_refs
        if item.get("auth_basename")
    }
    target_would_prune = [
        {
            "auth_basename": auth_basename,
            "reason": "not_authorized_for_control_owned_target",
        }
        for auth_basename in target_inventory
        if auth_basename not in eligible_target_auths
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
                "machine_error_code": (
                    "STABLE_REPAIR_APPLY_BLOCKED"
                    if mode == "apply"
                    else "STABLE_REPAIR_DRY_RUN_BLOCKED"
                ),
                "reason": "stale_lock_file_present",
                "holder_pid": lock_preflight.get("holder_pid"),
            }
        )
    blocked_reasons.extend(
        {
            "machine_error_code": "REPAIR_SOURCE_AUTH_REF_MISSING",
            "backend_id": item.get("backend_id"),
            "auth_basename": item.get("auth_basename"),
                "reason": item.get("reason"),
            }
        for item in source_copy_missing_auth_refs
    )
    source_copy_basename_collisions = []
    source_collision_map: dict[str, list[dict[str, Any]]] = {}
    for item in eligible_registry_auth_refs:
        basename = str(item.get("auth_basename") or "")
        if basename:
            source_collision_map.setdefault(basename, []).append(item)
    for auth_basename, items in sorted(source_collision_map.items()):
        if len(items) < 2:
            continue
        source_copy_basename_collisions.append(
            {
                "auth_basename": auth_basename,
                "backend_ids": [item.get("backend_id") for item in items],
                "auth_refs": [item.get("auth_ref") for item in items],
                "reason": "eligible_registry_auth_ref_basename_collision",
            }
        )
    blocked_reasons.extend(
        {
            "machine_error_code": "REPAIR_SOURCE_BASENAME_COLLISION",
            "auth_basename": item.get("auth_basename"),
            "reason": item.get("reason"),
        }
        for item in source_copy_basename_collisions
    )

    return {
        "mode": mode,
        "snapshot_required": True,
        "lock_required": True,
        "lock_preflight": lock_preflight,
        "repair_apply_authority": build_stable_repair_apply_authority(paths),
        "registry_source_inputs": {
            "eligible_registry_auth_refs": eligible_registry_auth_refs,
            "source_copy_missing_auth_refs": source_copy_missing_auth_refs,
            "source_copy_basename_collisions": source_copy_basename_collisions,
        },
        "repair_observation": {
            "status": policy_drift.get("status", "unknown"),
            "machine_error_code": policy_drift.get("machine_error_code", "UNKNOWN"),
            "stable_auth_inventory_source": policy_drift.get(
                "stable_auth_inventory_source", {}
            ),
            "observed_source_matching_allowed_auths": observed_source_matching_allowed_auths,
            "observed_source_disallowed_auths": observed_source_disallowed_auths,
            "observed_source_missing_allowed_auths": (
                observed_source_missing_allowed_auths
            ),
            "observed_source_unknown_auths": observed_source_unknown_auths,
        },
        "repair_target_contract_surface": build_repair_target_contract_surface(paths),
        "target_reconciliation_plan": {
            "target_exactness": "exact_approved_set",
            "target_inventory_dir": str(paths.repair_target_inventory_dir),
            "target_inventory_entries": target_inventory,
            "target_would_add": target_would_add,
            "target_would_prune": target_would_prune,
            "target_would_keep": target_would_keep,
        },
        "blocked_reasons": blocked_reasons,
    }


def run_stable_repair_apply(paths: RuntimePaths) -> dict[str, Any]:
    registry = read_json(paths.registry_file)
    registry_identity = get_registry_identity(registry)
    policy_drift = get_stable_policy_drift(paths, registry)
    lock_preflight = get_lock_preflight(paths)
    transaction_plan = build_stable_repair_transaction_plan(
        paths, registry, policy_drift, lock_preflight, mode="apply"
    )

    if stable_repair_registry_identity_requires_block(registry_identity):
        transaction_plan["blocked_reasons"].append(
            {
                "machine_error_code": "REGISTRY_IDENTITY_AMBIGUOUS",
                "reason": "registry_identity_ambiguous",
            }
        )
        return build_command_payload(
            ok=False,
            human_message="Stable repair apply blocked by ambiguous registry identity.",
            machine_error_code="REGISTRY_IDENTITY_AMBIGUOUS",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_registry_identity",
            },
        )

    if lock_preflight.get("status") == "held":
        return build_command_payload(
            ok=False,
            human_message="Stable repair apply blocked by mutation lock.",
            machine_error_code="LOCK_HELD",
            liveness="unknown",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "retry_after_lock_released",
            },
        )

    if lock_preflight.get("status") == "stale":
        return build_command_payload(
            ok=False,
            human_message="Stable repair apply blocked by stale mutation lock.",
            machine_error_code="STABLE_REPAIR_APPLY_BLOCKED",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_stale_lock",
            },
        )

    target_surface = transaction_plan.get("repair_target_contract_surface", {})
    approved_target = target_surface.get("approved_repair_target_reference", {})
    if approved_target.get("status") != "materialized_aligned":
        return build_command_payload(
            ok=False,
            human_message="Stable repair apply blocked because the approved repair target is not active.",
            machine_error_code="STABLE_REPAIR_TARGET_NOT_READY",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_target_switch_contract",
            },
        )

    if paths.repair_target_inventory_dir.exists() and not paths.repair_target_inventory_dir.is_dir():
        return build_command_payload(
            ok=False,
            human_message="Stable repair apply blocked by invalid target inventory directory.",
            machine_error_code="STABLE_REPAIR_INVALID_TARGET_DIR",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_target_inventory",
            },
        )

    before_target = snapshot_target_inventory_state(paths.repair_target_inventory_dir)
    if before_target.get("non_auth_entries"):
        return build_command_payload(
            ok=False,
            human_message="Stable repair apply blocked by unexpected non-auth target inventory entries.",
            machine_error_code="STABLE_REPAIR_UNEXPECTED_TARGET_ENTRY",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_target_inventory",
            },
        )

    target_plan = transaction_plan.get("target_reconciliation_plan", {})
    target_would_add = target_plan.get("target_would_add", [])
    target_would_prune = target_plan.get("target_would_prune", [])
    if not target_would_add and not target_would_prune:
        return build_command_payload(
            ok=True,
            human_message="Stable repair apply found the approved target inventory already aligned.",
            machine_error_code="STABLE_REPAIR_ALREADY_ALIGNED",
            liveness="unknown",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
            },
        )

    try:
        source_map = build_stable_repair_source_map(transaction_plan)
    except RuntimeErrorInfo as exc:
        return build_command_payload(
            ok=False,
            human_message=exc.message,
            machine_error_code=exc.machine_error_code,
            liveness="unknown",
            severity=exc.severity,
            operator_action=exc.operator_action,
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_transaction_plan",
            },
            exit_code=exc.exit_code,
        )

    guard_before = snapshot_stable_repair_guard_surfaces(paths, list(source_map.values()))
    stage_dir = Path(
        tempfile.mkdtemp(prefix=".stable-repair-stage-", dir=str(paths.managed_dir))
    )
    backup_dir: Path | None = None
    try:
        with serialized_lock(paths):
            stage_stable_repair_inventory(stage_dir, source_map)
            verify_stable_repair_target_inventory(stage_dir, source_map)
            if paths.repair_target_inventory_dir.exists():
                backup_dir = paths.managed_dir / (
                    f".stable-repair-backup-{os.getpid()}-{time.time_ns()}"
                )
                paths.repair_target_inventory_dir.replace(backup_dir)
            stage_dir.replace(paths.repair_target_inventory_dir)
            verify_stable_repair_apply_result(paths, source_map, guard_before)
    except Exception as exc:
        rollback_stable_repair_apply(
            target_dir=paths.repair_target_inventory_dir,
            stage_dir=stage_dir,
            backup_dir=backup_dir,
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
                    "command_mode": "apply",
                    "would_change": False,
                    "transaction_plan": transaction_plan,
                    "next_action": "inspect_transaction_plan",
                },
                exit_code=exc.exit_code,
            )
        return build_command_payload(
            ok=False,
            human_message=f"Stable repair apply failed: {exc}",
            machine_error_code="STABLE_REPAIR_APPLY_FAILED",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "command_mode": "apply",
                "would_change": False,
                "transaction_plan": transaction_plan,
                "next_action": "inspect_transaction_plan",
            },
        )
    finally:
        remove_tree_if_exists(stage_dir)
        if backup_dir and backup_dir.exists():
            remove_tree_if_exists(backup_dir)

    after_target = snapshot_target_inventory_state(paths.repair_target_inventory_dir)
    changed_files = detect_target_inventory_changed_files(
        before_target, after_target, paths.repair_target_inventory_dir
    )
    post_apply_plan = build_stable_repair_transaction_plan(
        paths,
        registry,
        get_stable_policy_drift(paths, registry),
        get_lock_preflight(paths),
        mode="apply",
    )
    return build_command_payload(
        ok=True,
        human_message="Stable repair apply completed on the approved target inventory.",
        machine_error_code="STABLE_REPAIR_APPLIED",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=changed_files,
        extra={
            "command_mode": "apply",
            "would_change": False,
            "transaction_plan": post_apply_plan,
            "next_action": "none",
        },
    )


def run_stable_repair_dry_run(paths: RuntimePaths) -> dict[str, Any]:
    registry = read_json(paths.registry_file)
    registry_identity = get_registry_identity(registry)
    policy_drift = get_stable_policy_drift(paths, registry)
    lock_preflight = get_lock_preflight(paths)
    transaction_plan = build_stable_repair_transaction_plan(
        paths, registry, policy_drift, lock_preflight
    )

    if stable_repair_registry_identity_requires_block(registry_identity):
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

    target_plan = transaction_plan.get("target_reconciliation_plan", {})
    target_would_add = target_plan.get("target_would_add", [])
    target_would_prune = target_plan.get("target_would_prune", [])
    if not target_would_add and not target_would_prune:
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


def classify_http_failure_machine_error(error_detail: str) -> str | None:
    lowered = error_detail.lower()
    if "auth_unavailable" in lowered:
        return "AUTH_UNAVAILABLE"
    if "model_cooldown" in lowered:
        return "MODEL_COOLDOWN"
    if "usage_limit_reached" in lowered or "quota" in lowered:
        return "QUOTA_EXHAUSTED"
    if (
        "model_unavailable" in lowered
        or "model_not_found" in lowered
        or "model not found" in lowered
        or "does not exist" in lowered
    ):
        return "MODEL_UNAVAILABLE"
    return None


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
    raw_candidates.append(str(state.get(LAST_KNOWN_GOOD_PROXY_URL_FIELD) or ""))
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
        if len(candidates) >= PROXY_REPROBE_MAX_CANDIDATES:
            break
    return candidates


def probe_proxy_candidate(candidate: str) -> bool:
    parsed = parse_local_proxy_candidate(candidate)
    if parsed is None:
        return False
    host, port = parsed
    return socket_is_listening(host, port)


def build_proxy_reprobe_result(
    candidates: list[str],
    *,
    found_candidate: bool,
    working_candidate: str | None,
    probed_candidate_count: int,
) -> dict[str, Any]:
    return {
        "attempted": bool(candidates),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "found_candidate": found_candidate,
        "working_candidate": working_candidate,
        "probed_candidate_count": probed_candidate_count,
        "candidate_budget": PROXY_REPROBE_MAX_CANDIDATES,
        "probe_concurrency_limit": PROXY_REPROBE_CONCURRENCY_LIMIT,
        "probe_depth": PROXY_REPROBE_DEPTH,
        "probe_strategy": PROXY_REPROBE_STRATEGY,
        "candidate_source_order": list(PROXY_REPROBE_CANDIDATE_SOURCE_ORDER),
    }


def run_proxy_reprobe(state: dict[str, Any]) -> dict[str, Any]:
    candidates = get_proxy_reprobe_candidates(state)
    probed_candidate_count = 0
    for candidate in candidates:
        probed_candidate_count += 1
        if probe_proxy_candidate(candidate):
            return build_proxy_reprobe_result(
                candidates,
                found_candidate=True,
                working_candidate=candidate,
                probed_candidate_count=probed_candidate_count,
            )
    return build_proxy_reprobe_result(
        candidates,
        found_candidate=False,
        working_candidate=None,
        probed_candidate_count=probed_candidate_count,
    )


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


def reconcile_stable_recovery_success(
    paths: RuntimePaths,
    state: dict[str, Any],
    *,
    stable_endpoint: str,
) -> dict[str, Any]:
    stable_state = dict(state)
    stable_state["status"] = "healthy"
    stable_state["last_error"] = ""
    stable_state["effective_mode"] = "stable"
    stable_state["selected_backend_ids"] = []
    stable_state["healthy_count"] = 1
    stable_state["degraded_count"] = 0
    stable_state["down_count"] = 0
    stable_state["last_sync_at"] = now_iso()

    with serialized_lock(paths):
        write_json_atomic(paths.state_file, stable_state)
        write_text_atomic(paths.runtime_effective_mode_file, "stable")
        write_toml_string_atomic(paths.config_toml, "base_url", stable_endpoint)
        managed_pid_path(paths).unlink(missing_ok=True)

    return read_json(paths.state_file, required=False)


@contextmanager
def serialized_lock(paths: RuntimePaths):
    lock_key = str(paths.lock_file.expanduser().resolve())
    owner_pid = os.getpid()
    owner_thread_id = threading.get_ident()
    created_lock_file = False
    reentrant = False

    # Nested owner-surface calls inside one composite execution path may
    # reenter the lock, but cross-thread attempts must still observe LOCK_HELD.
    with SERIALIZED_LOCK_LOCAL_OWNERS_GUARD:
        local_owner = SERIALIZED_LOCK_LOCAL_OWNERS.get(lock_key)
        if (
            isinstance(local_owner, dict)
            and local_owner.get("pid") == owner_pid
            and local_owner.get("thread_id") == owner_thread_id
        ):
            local_owner["depth"] = int(local_owner.get("depth", 1)) + 1
            reentrant = True

    if reentrant:
        try:
            yield
        finally:
            with SERIALIZED_LOCK_LOCAL_OWNERS_GUARD:
                nested_owner = SERIALIZED_LOCK_LOCAL_OWNERS.get(lock_key)
                if (
                    isinstance(nested_owner, dict)
                    and nested_owner.get("pid") == owner_pid
                    and nested_owner.get("thread_id") == owner_thread_id
                ):
                    nested_owner["depth"] = max(
                        0, int(nested_owner.get("depth", 1)) - 1
                    )
                    if nested_owner["depth"] == 0:
                        SERIALIZED_LOCK_LOCAL_OWNERS.pop(lock_key, None)
        return

    paths.lock_file.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(paths.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            created_lock_file = True
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
        with SERIALIZED_LOCK_LOCAL_OWNERS_GUARD:
            SERIALIZED_LOCK_LOCAL_OWNERS[lock_key] = {
                "pid": owner_pid,
                "thread_id": owner_thread_id,
                "depth": 1,
            }
        yield
    finally:
        release_lock_file = False
        with SERIALIZED_LOCK_LOCAL_OWNERS_GUARD:
            local_owner = SERIALIZED_LOCK_LOCAL_OWNERS.get(lock_key)
            if (
                isinstance(local_owner, dict)
                and local_owner.get("pid") == owner_pid
                and local_owner.get("thread_id") == owner_thread_id
            ):
                local_owner["depth"] = max(0, int(local_owner.get("depth", 1)) - 1)
                if local_owner["depth"] == 0:
                    SERIALIZED_LOCK_LOCAL_OWNERS.pop(lock_key, None)
                    release_lock_file = True
            elif created_lock_file:
                release_lock_file = True
        if release_lock_file:
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


def summarize_status(
    paths: RuntimePaths, health_payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    desired_mode = get_desired_mode(paths)
    health_payload = health_payload or run_healthcheck(paths)
    registry = read_json(paths.registry_file)
    pool_counts = summarize_registry_pool_counts(registry)
    policy_drift_observed = get_stable_policy_drift(paths, registry)
    state = read_json(paths.state_file, required=False)
    stable_runtime_consumer = build_stable_runtime_consumer_contract(
        paths, registry, policy_drift_observed, state, health_payload
    )
    if should_use_approved_target_policy_drift(
        paths,
        registry,
        policy_drift_observed,
        state,
        require_live_stable_runtime=True,
        health_payload=health_payload,
        stable_runtime_consumer=stable_runtime_consumer,
    ):
        policy_drift = get_stable_policy_drift_for_inventory_source(
            registry,
            paths.repair_target_inventory_dir,
            get_approved_target_inventory_source(paths),
        )
    else:
        policy_drift = policy_drift_observed
    recovery_result = health_payload.get("deterministic_stable_recovery_result")
    if isinstance(recovery_result, dict):
        stable_runtime_consumer = dict(stable_runtime_consumer)
        stable_runtime_consumer["deterministic_stable_recovery_result"] = {
            **recovery_result,
            "delegated_from_status": True,
        }
    registry_identity = get_registry_identity(registry)
    current_proxy_url = str(
        health_payload.get("current_proxy_url", state.get("current_proxy_url", ""))
    )
    current_proxy_adoption_contract = health_payload.get("current_proxy_adoption_contract")
    if not isinstance(current_proxy_adoption_contract, dict):
        current_proxy_adoption_contract = build_current_proxy_adoption_contract(paths)
    last_known_good_proxy_contract = health_payload.get("last_known_good_proxy_contract")
    if not isinstance(last_known_good_proxy_contract, dict):
        last_known_good_proxy_contract = build_last_known_good_proxy_contract(paths)
    last_known_good_proxy = health_payload.get("last_known_good_proxy")
    if not isinstance(last_known_good_proxy, dict):
        last_known_good_proxy = build_last_known_good_proxy_surface(
            paths, state, current_proxy_url
        )
    proxy_reprobe_adoption_result = health_payload.get("proxy_reprobe_adoption_result")
    if not isinstance(proxy_reprobe_adoption_result, dict):
        proxy_reprobe_adoption_result = None
    pool_summary = {
        "active": int(pool_counts.get("active", 0) or 0),
        "reserve": int(pool_counts.get("reserve", 0) or 0),
        "retired": int(pool_counts.get("retired", 0) or 0),
        "healthy": int(state.get("healthy_count", 0) or 0),
        "degraded": int(state.get("degraded_count", 0) or 0),
        "down": int(state.get("down_count", 0) or 0),
        "selected_backend_ids": state.get("selected_backend_ids") or [],
        "backend_count": len(registry.get("backends") or []),
    }
    auth_pool_hygiene = health_payload.get("auth_pool_hygiene")
    if isinstance(auth_pool_hygiene, dict):
        auth_pool_hygiene = {
            **auth_pool_hygiene,
            "delegated_from_status": True,
        }
    else:
        auth_pool_hygiene = summarize_auth_pool_hygiene(registry, state)
        auth_pool_hygiene["delegated_from_status"] = False
    launch_readiness = health_payload.get("launch_readiness")
    if isinstance(launch_readiness, dict):
        launch_readiness = {
            **launch_readiness,
            "delegated_from_status": True,
        }
    runtime_guardrails = health_payload.get("runtime_guardrails")
    if isinstance(runtime_guardrails, dict):
        runtime_guardrails = {
            **runtime_guardrails,
            "delegated_from_status": True,
            "owner_command_surface": "status --json",
        }
    else:
        runtime_guardrails = build_runtime_guardrail_surface(
            paths,
            launch_readiness=launch_readiness if isinstance(launch_readiness, dict) else None,
            auth_pool_hygiene=auth_pool_hygiene if isinstance(auth_pool_hygiene, dict) else None,
            recovery_result=recovery_result if isinstance(recovery_result, dict) else None,
        )
        runtime_guardrails["delegated_from_status"] = False
        runtime_guardrails["owner_command_surface"] = "status --json"

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
        changed_files=list(health_payload.get("changed_files") or []),
        exit_code=int(health_payload["exit_code"]),
        extra={
            "desired_mode": desired_mode,
            "effective_mode": health_payload["effective_mode"],
            "endpoint": health_payload["endpoint"],
            "configured_model": health_payload.get("configured_model"),
            "requested_model": health_payload.get("requested_model"),
            "configured_proxy_url": health_payload.get("configured_proxy_url"),
            "current_proxy_url": current_proxy_url,
            "current_proxy_adoption_contract": current_proxy_adoption_contract,
            "last_known_good_proxy_contract": last_known_good_proxy_contract,
            "last_known_good_proxy": last_known_good_proxy,
            **(
                {
                    "proxy_reprobe_adoption_result": proxy_reprobe_adoption_result,
                }
                if proxy_reprobe_adoption_result is not None
                else {}
            ),
            "pool_summary": pool_summary,
            "auth_pool_hygiene": auth_pool_hygiene,
            "policy_drift": policy_drift,
            "policy_drift_observed": policy_drift_observed,
            "stable_runtime_consumer": stable_runtime_consumer,
            **(
                {
                    "launch_readiness": launch_readiness,
                }
                if isinstance(launch_readiness, dict)
                else {}
            ),
            **(
                {
                    "runtime_guardrails": runtime_guardrails,
                }
                if isinstance(runtime_guardrails, dict)
                else {}
            ),
            "registry_identity_summary": summarize_registry_identity(registry_identity),
            "claim_gate": get_claim_gate(policy_drift, registry_identity),
            "last_error": (
                ""
                if health_payload["status"] == "ok"
                else health_payload.get("last_error", state.get("last_error", ""))
            ),
            "attestation_summary": {
                "status": health_payload["status"],
                "machine_error_code": health_payload["machine_error_code"],
                "attestation_source": health_payload["attestation"]["attestation_source"],
                "observed_at_utc": health_payload["attestation"]["observed_at_utc"],
            },
        },
    )


def observe_runtime_precondition_for_launch_client(
    paths: RuntimePaths, model: str | None = None
) -> dict[str, Any]:
    state = read_json(paths.state_file, required=False)
    registry = read_json(paths.registry_file)
    auth_pool_hygiene = summarize_auth_pool_hygiene(registry, state)
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
    host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
    configured_base_url = read_toml_string(paths.config_toml, "base_url")
    configured_model = get_model(paths)
    listener_ok = socket_is_listening(host, port)
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
    model_name = model or configured_model
    models_ok = False
    responses_ok = False
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
    expected_base_url = reported_endpoint
    base_url_match = configured_base_url == expected_base_url
    current_proxy_url = str(state.get("current_proxy_url", ""))
    configured_proxy_url = get_configured_proxy_url(paths, reported_effective_mode)
    model_match = model_name == configured_model
    proxy_url_match = (
        not configured_proxy_url
        or not current_proxy_url
        or configured_proxy_url == current_proxy_url
    )
    effective_mode_match = (
        state_effective_mode in {None, "", reported_effective_mode}
        and effective_mode_artifact == reported_effective_mode
    )
    if not error_detail:
        error_detail = truth_drift_detail(
            configured_model=configured_model,
            requested_model=model_name,
            model_match=model_match,
            configured_proxy_url=configured_proxy_url,
            current_proxy_url=current_proxy_url,
            proxy_url_match=proxy_url_match,
        )
    attestation = {
        "configured_model": configured_model,
        "requested_model": model_name,
        "model_match": model_match,
        "listener_ok": listener_ok,
        "models_ok": models_ok,
        "responses_ok": responses_ok,
        "effective_mode_match": effective_mode_match,
        "base_url_match": base_url_match,
        "configured_proxy_url": configured_proxy_url,
        "current_proxy_url": current_proxy_url,
        "proxy_url_match": proxy_url_match,
        "selected_backends_digest": get_selected_backends_digest(state),
        "observed_at_utc": now_iso(),
        "runtime_version": str(
            state.get("version", state.get("schema_version", "unknown"))
        ),
        "attestation_source": "launch client precondition",
    }

    if not listener_ok:
        machine_error_code = "LISTENER_DOWN"
    elif (
        models_ok
        and responses_ok
        and base_url_match
        and effective_mode_match
        and model_match
        and proxy_url_match
    ):
        machine_error_code = "OK"
    else:
        machine_error_code = (
            classify_http_failure_machine_error(error_detail) or "ATTESTATION_FAILED"
        )
    launch_readiness = build_launch_readiness_surface(
        owner_command_surface="launch client precondition",
        delegated_from_status=False,
        listener_ok=listener_ok,
        models_ok=models_ok,
        responses_ok=responses_ok,
        base_url_match=base_url_match,
        effective_mode_match=effective_mode_match,
        model_match=model_match,
        proxy_url_match=proxy_url_match,
        machine_error_code=machine_error_code,
        error_detail=error_detail,
        auth_pool_hygiene=auth_pool_hygiene,
    )

    if not listener_ok:
        return build_command_payload(
            ok=False,
            human_message=f"Listener is not reachable at {attestation_endpoint}.",
            machine_error_code=machine_error_code,
            liveness="down",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={
                "desired_mode": desired_mode,
                "effective_mode": reported_effective_mode,
                "endpoint": reported_endpoint,
                "attestation": attestation,
                "auth_pool_hygiene": auth_pool_hygiene,
                "launch_readiness": launch_readiness,
                "last_error": error_detail
                or f"Listener is not reachable at {attestation_endpoint}.",
            },
        )

    if (
        models_ok
        and responses_ok
        and base_url_match
        and effective_mode_match
        and model_match
        and proxy_url_match
    ):
        return build_command_payload(
            ok=True,
            human_message="Runtime precondition passed for host-client launch.",
            machine_error_code=machine_error_code,
            liveness="healthy",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            extra={
                "desired_mode": desired_mode,
                "effective_mode": reported_effective_mode,
                "endpoint": reported_endpoint,
                "attestation": attestation,
                "auth_pool_hygiene": auth_pool_hygiene,
                "launch_readiness": launch_readiness,
                "last_error": "",
            },
        )

    return build_command_payload(
        ok=False,
        human_message="Runtime precondition failed one or more attestation checks.",
        machine_error_code="ATTESTATION_FAILED",
        liveness="degraded",
        severity="recoverable",
        operator_action="retry",
        changed_files=[],
        extra={
            "desired_mode": desired_mode,
            "effective_mode": reported_effective_mode,
            "endpoint": reported_endpoint,
            "attestation": attestation,
            "auth_pool_hygiene": auth_pool_hygiene,
            "launch_readiness": launch_readiness,
            "last_error": error_detail or "Runtime precondition failed one or more checks.",
        },
    )


def run_healthcheck(
    paths: RuntimePaths,
    model: str | None = None,
    *,
    allow_recovery: bool = True,
    allow_last_known_good_proxy_write: bool = True,
    allow_current_proxy_auto_adoption: bool = True,
    allow_stable_fallback_write: bool = True,
) -> dict[str, Any]:
    before = snapshot_known_files(paths)
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
    successful_reconcile_detail = ""
    managed_preflight_failure_candidate = effective_mode == "managed" and not listener_ok

    stale_managed_residue = (
        state_effective_mode not in {None, "", "stable"}
        or bool(state.get("selected_backend_ids"))
        or managed_pid_path(paths).exists()
        or configured_base_url != reported_endpoint
    )
    if (
        allow_stable_fallback_write
        and reported_effective_mode == "stable"
        and stale_managed_residue
    ):
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
        successful_reconcile_detail = str(state.get("last_error", ""))
        effective_mode = get_effective_mode(paths, state)
        host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
        configured_base_url = read_toml_string(paths.config_toml, "base_url")
        listener_ok = socket_is_listening(host, port)

    recovery_result: dict[str, Any] | None = None
    if allow_recovery:
        recovery_result = build_deterministic_stable_recovery_result(
            delegated_from_status=False,
            attempted=False,
            entry_lane="not_invoked",
            outcome="not_invoked",
            re_enable_method="",
            selected_source_kind="",
            selected_source_path="",
            generated_config_regenerated=False,
            snapshot_refreshed=False,
            fallback_reason="",
            live_runtime_observation_confirmed=False,
            confirmation_basis="",
            effectful_claim_allowed=False,
        )
    recovery_attempt: StableRuntimeLaunchAttempt | None = None
    if allow_recovery:
        reported_effective_mode = reconcile_effective_mode_for_reporting(
            effective_mode, listener_ok=listener_ok
        )
        _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
        if reported_effective_mode == "stable" and not listener_ok:
            registry = read_json(paths.registry_file)
            policy_drift = get_stable_policy_drift(paths, registry)
            selection = get_stable_runtime_consumer_selection_context(
                paths, registry, policy_drift
            )
            recovery_attempt = run_stable_runtime_launcher_attempt(paths, selection)
            emit_subprocess_output(
                stdout=recovery_attempt.stdout, stderr=recovery_attempt.stderr
            )
            state = read_json(paths.state_file, required=False)
            effective_mode = get_effective_mode(paths, state)
            host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
            configured_base_url = read_toml_string(paths.config_toml, "base_url")
            listener_ok = socket_is_listening(host, port)
            reported_effective_mode = reconcile_effective_mode_for_reporting(
                effective_mode, listener_ok=listener_ok
            )
            _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
            if reported_effective_mode == "stable" and not listener_ok:
                error_message = state.get("last_error", "")
                if not error_message:
                    if recovery_attempt.launcher_exit_code != 0:
                        error_message = (
                            "Deterministic stable recovery launcher exited "
                            f"{recovery_attempt.launcher_exit_code}; listener is not "
                            f"reachable at {reported_endpoint}."
                        )
                    else:
                        error_message = (
                            "Listener is not reachable at "
                            f"{reported_endpoint} after deterministic stable recovery attempt."
                        )
                state = reconcile_stable_fallback(
                    paths,
                    state,
                    stable_endpoint=reported_endpoint,
                    error_message=error_message,
                    stable_listener_ok=False,
                )
                effective_mode = get_effective_mode(paths, state)
                host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
                configured_base_url = read_toml_string(paths.config_toml, "base_url")
                listener_ok = socket_is_listening(host, port)

    models_ok = False
    responses_ok = False
    configured_model = get_model(paths)
    model_name = model or configured_model
    error_detail = ""
    registry = read_json(paths.registry_file)
    auth_pool_hygiene = summarize_auth_pool_hygiene(registry, state)
    current_proxy_url = str(state.get("current_proxy_url", ""))
    proxy_reprobe: dict[str, Any] | None = None
    proxy_reprobe_adoption_result: dict[str, Any] | None = None

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
    configured_proxy_url = get_configured_proxy_url(paths, reported_effective_mode)
    current_proxy_truth_url = get_reported_current_proxy_url(
        paths, state, reported_effective_mode
    )
    model_match = model_name == configured_model
    proxy_url_match = (
        not configured_proxy_url
        or not current_proxy_truth_url
        or configured_proxy_url == current_proxy_truth_url
    )
    effective_mode_match = (
        state_effective_mode in {None, "", reported_effective_mode}
        and effective_mode_artifact == reported_effective_mode
    )
    if not error_detail:
        error_detail = truth_drift_detail(
            configured_model=configured_model,
            requested_model=model_name,
            model_match=model_match,
            configured_proxy_url=configured_proxy_url,
            current_proxy_url=current_proxy_truth_url,
            proxy_url_match=proxy_url_match,
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
    elif (
        models_ok
        and responses_ok
        and base_url_match
        and effective_mode_match
        and model_match
        and proxy_url_match
    ):
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
            last_known_good_proxy = build_last_known_good_proxy_surface(
                paths, state, str(state.get("current_proxy_url", ""))
            )
            if proxy_reprobe["found_candidate"]:
                machine_error_code = "PROXY_PATH_BROKEN"
                human_message = (
                    "Runtime attestation failed because the outbound proxy path is broken; "
                    "a local proxy candidate is reachable."
                )
            elif last_known_good_proxy["status"] == "materialized":
                machine_error_code = "PROXY_PATH_BROKEN"
                human_message = (
                    "Runtime attestation failed because the outbound proxy path is broken; "
                    "a previously materialized local proxy snapshot is preserved, but "
                    "no bounded live candidate is currently reachable."
                )
            else:
                machine_error_code = "PROXY_REPROBE_FAILED"
                human_message = (
                    "Runtime attestation failed because the outbound proxy path is broken; "
                    "no bounded local proxy candidate is reachable."
                )
        else:
            machine_error_code = (
                classify_http_failure_machine_error(error_detail)
                or "ATTESTATION_FAILED"
            )
            human_message = "Runtime attestation failed one or more checks."
        ok = False

    if (
        not ok
        and allow_current_proxy_auto_adoption
        and proxy_reprobe is not None
        and proxy_reprobe["found_candidate"]
    ):
        working_candidate = str(proxy_reprobe["working_candidate"] or "")
        # Keep activation and immediate reproof inside one serialized owner
        # window so cross-thread mutations cannot interleave between them.
        with serialized_lock(paths):
            activation_attempt = run_current_proxy_owner_path_activation(
                paths, working_candidate
            )
            proxy_reprobe_adoption_result = {
                "status": "owner_path_emitted",
                "attempted": activation_attempt.activation_attempted,
                "working_candidate": working_candidate,
                "launcher_lane_eligibility": activation_attempt.launcher_lane_eligibility,
                "launcher_readiness_status": activation_attempt.launcher_readiness_status,
                "handoff_env_var": CURRENT_PROXY_URL_HANDOFF_ENV,
                "prerequisite_materialized": activation_attempt.prerequisite_materialized,
                "activation_attempted": activation_attempt.activation_attempted,
                "activation_exit_code": activation_attempt.activation_exit_code,
                "adoption_outcome": (
                    "launcher_lane_ineligible"
                    if not activation_attempt.activation_attempted
                    else "activation_failed"
                ),
                "current_proxy_url_rewritten": False,
                "live_runtime_observation_confirmed": False,
                "last_known_good_refreshed": False,
            }
            if (
                activation_attempt.activation_attempted
                and activation_attempt.activation_exit_code == 0
            ):
                reproof_payload = run_healthcheck(
                    paths,
                    model=model,
                    allow_recovery=False,
                    allow_last_known_good_proxy_write=False,
                    allow_current_proxy_auto_adoption=False,
                )
                reproof_ok = (
                    reproof_payload["status"] == "ok"
                    and str(reproof_payload["effective_mode"]) == "managed"
                )
                state = read_json(paths.state_file, required=False)
                reproof_current_proxy_url = str(state.get("current_proxy_url", ""))
                same_current_reconfirmed = (
                    activation_attempt.prior_current_proxy_url == working_candidate
                    and reproof_ok
                    and reproof_current_proxy_url == working_candidate
                )
                candidate_adopted = (
                    activation_attempt.prior_current_proxy_url != working_candidate
                    and reproof_ok
                    and reproof_current_proxy_url == working_candidate
                )
                if same_current_reconfirmed or candidate_adopted:
                    attestation = reproof_payload["attestation"]
                    listener_ok = bool(attestation["listener_ok"])
                    models_ok = bool(attestation["models_ok"])
                    responses_ok = bool(attestation["responses_ok"])
                    effective_mode_match = bool(attestation["effective_mode_match"])
                    base_url_match = bool(attestation["base_url_match"])
                    error_detail = str(reproof_payload.get("last_error", ""))
                    effective_mode = str(reproof_payload["effective_mode"])
                    reported_effective_mode = effective_mode
                    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
                    host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
                    configured_base_url = read_toml_string(paths.config_toml, "base_url")
                    liveness = str(reproof_payload["liveness"])
                    severity = str(reproof_payload["severity"])
                    operator_action = str(reproof_payload["operator_action"])
                    machine_error_code = str(reproof_payload["machine_error_code"])
                    human_message = str(reproof_payload["human_message"])
                    ok = True
                    proxy_reprobe_adoption_result["adoption_outcome"] = (
                        "same_current_reconfirmed"
                        if same_current_reconfirmed
                        else "candidate_adopted"
                    )
                    proxy_reprobe_adoption_result["current_proxy_url_rewritten"] = (
                        candidate_adopted
                    )
                    proxy_reprobe_adoption_result[
                        "live_runtime_observation_confirmed"
                    ] = True
                else:
                    restore_current_proxy_owner_path_runtime_surfaces(
                        paths, activation_attempt.rollback_surface_snapshots
                    )
                    state = read_json(paths.state_file, required=False)
                    error_detail = str(reproof_payload.get("last_error", error_detail))
                    proxy_reprobe_adoption_result["adoption_outcome"] = (
                        "live_reproof_failed"
                    )
            elif (
                paths.sync_script.exists()
                and activation_attempt.launcher_lane_eligibility
                not in {
                    "default_path_present_repo_marker_invalid",
                    "default_path_present_repo_marker_unrecognized",
                }
            ):
                sync_recovery_result, sync_reproof_payload = (
                    attempt_sync_current_proxy_recovery_under_lock(
                        paths,
                        working_candidate=working_candidate,
                        prior_current_proxy_url=current_proxy_url,
                    )
                )
                proxy_reprobe_adoption_result.update(sync_recovery_result)
                if sync_reproof_payload is not None:
                    state = read_json(paths.state_file, required=False)
                    attestation = sync_reproof_payload["attestation"]
                    listener_ok = bool(attestation["listener_ok"])
                    models_ok = bool(attestation["models_ok"])
                    responses_ok = bool(attestation["responses_ok"])
                    effective_mode_match = bool(attestation["effective_mode_match"])
                    base_url_match = bool(attestation["base_url_match"])
                    error_detail = str(sync_reproof_payload.get("last_error", ""))
                    effective_mode = str(sync_reproof_payload["effective_mode"])
                    reported_effective_mode = effective_mode
                    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
                    host, port, attestation_endpoint = get_endpoint(paths, effective_mode)
                    configured_base_url = read_toml_string(paths.config_toml, "base_url")
                    liveness = str(sync_reproof_payload["liveness"])
                    severity = str(sync_reproof_payload["severity"])
                    operator_action = str(sync_reproof_payload["operator_action"])
                    machine_error_code = str(sync_reproof_payload["machine_error_code"])
                    human_message = str(sync_reproof_payload["human_message"])
                    ok = True

    snapshot_payload: dict[str, Any] | None = None
    if recovery_attempt is not None:
        recovery_entry_lane = (
            "managed_preflight_failure"
            if managed_preflight_failure_candidate
            else "stable_service_disabled"
        )
        recovery_outcome = "recovery_failed_before_stable_healthy"
        re_enable_method = "bounded_healthcheck_owner_retry"
        recovery_selected_kind = (
            "approved_repair_target"
            if recovery_attempt.activation_attempted
            else "observed_stable_inventory_source"
        )
        recovery_selected_path = (
            str(paths.repair_target_inventory_dir)
            if recovery_attempt.activation_attempted
            else str(recovery_attempt.observed_path)
        )
        fallback_reason = ""
        snapshot_refreshed = False
        live_runtime_observation_confirmed = ok and reported_effective_mode == "stable"
        confirmation_basis = ""
        effectful_claim_allowed = False
        if live_runtime_observation_confirmed:
            state = reconcile_stable_recovery_success(
                paths, state, stable_endpoint=reported_endpoint
            )
            if (
                recovery_attempt.activation_attempted
                and recovery_attempt.launcher_exit_code == 0
            ):
                recovery_outcome = "approved_target_recovered"
                confirmation_basis = (
                    "approved_target_activation_plus_live_runtime_observation"
                )
                effectful_claim_allowed = True
                snapshot_payload = build_stable_runtime_consumer_snapshot_payload(
                    activation_method="process_local_env_override",
                    selected_config_file=str(paths.stable_runtime_generated_config_file),
                    selected_source_kind="approved_repair_target",
                    selected_source_path=str(paths.repair_target_inventory_dir),
                    activation_outcome=STABLE_RUNTIME_APPROVED_TARGET_ACTIVATION_OUTCOME,
                    fallback_reason="",
                )
                recovery_selected_kind = "approved_repair_target"
                recovery_selected_path = str(paths.repair_target_inventory_dir)
            else:
                recovery_outcome = "observed_source_live_recovered"
                if recovery_attempt.activation_attempted:
                    confirmation_basis = (
                        "observed_source_live_runtime_observation_after_activation_attempt"
                    )
                else:
                    confirmation_basis = "observed_source_live_runtime_observation"
                if recovery_attempt.activation_attempted:
                    fallback_reason = (
                        "launcher_exit_nonzero"
                        if recovery_attempt.launcher_exit_code != 0
                        else "approved_target_recovery_unproven"
                    )
                    snapshot_payload = build_stable_runtime_consumer_snapshot_payload(
                        activation_method="process_local_env_override",
                        selected_config_file=str(
                            paths.stable_runtime_generated_config_file
                        ),
                        selected_source_kind="observed_stable_inventory_source",
                        selected_source_path=str(recovery_attempt.observed_path),
                        activation_outcome=STABLE_RUNTIME_OBSERVED_SOURCE_FALLBACK_OUTCOME,
                        fallback_reason=fallback_reason,
                    )
                else:
                    snapshot_payload = build_stable_runtime_consumer_snapshot_payload(
                        activation_method="baseline_stable_config",
                        selected_config_file=str(paths.stable_config),
                        selected_source_kind="observed_stable_inventory_source",
                        selected_source_path=str(recovery_attempt.observed_path),
                        activation_outcome=STABLE_RUNTIME_OBSERVED_SOURCE_SELECTED_OUTCOME,
                        fallback_reason="",
                    )
                recovery_selected_kind = "observed_stable_inventory_source"
                recovery_selected_path = str(recovery_attempt.observed_path)
            if snapshot_payload is not None:
                write_stable_runtime_consumer_snapshot(paths, snapshot_payload)
                snapshot_refreshed = True
        else:
            fallback_reason = (
                "launcher_exit_nonzero"
                if recovery_attempt.launcher_exit_code != 0
                else "stable_listener_unreachable_after_recovery"
            )
            confirmation_basis = "live_runtime_observation_not_confirmed"
        recovery_result = build_deterministic_stable_recovery_result(
            delegated_from_status=False,
            attempted=True,
            entry_lane=recovery_entry_lane,
            outcome=recovery_outcome,
            re_enable_method=re_enable_method,
            selected_source_kind=recovery_selected_kind,
            selected_source_path=recovery_selected_path,
            generated_config_regenerated=recovery_attempt.generated_config_regenerated,
            snapshot_refreshed=snapshot_refreshed,
            fallback_reason=fallback_reason,
            live_runtime_observation_confirmed=live_runtime_observation_confirmed,
            confirmation_basis=confirmation_basis,
            effectful_claim_allowed=effectful_claim_allowed,
        )
        if (
            not live_runtime_observation_confirmed
            and recovery_entry_lane == "stable_service_disabled"
            and not listener_ok
            and machine_error_code == "LISTENER_DOWN"
        ):
            machine_error_code = "STABLE_SERVICE_DISABLED"
            human_message = (
                "Stable service did not re-enable through the bounded healthcheck "
                f"recovery lane; listener is not reachable at {reported_endpoint}."
            )

    current_proxy_url = str(state.get("current_proxy_url", ""))
    previous_last_known_good_proxy_url = str(
        state.get(LAST_KNOWN_GOOD_PROXY_URL_FIELD) or ""
    )
    previous_last_known_good_proxy_observed_at = str(
        state.get(LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD) or ""
    )
    if allow_last_known_good_proxy_write:
        state = refresh_last_known_good_proxy_from_healthcheck(
            paths,
            state,
            current_proxy_url=current_proxy_url,
            attestation_ok=ok,
            reported_effective_mode=reported_effective_mode,
        )
    current_proxy_url = get_reported_current_proxy_url(
        paths, state, reported_effective_mode
    )
    if proxy_reprobe_adoption_result is not None:
        proxy_reprobe_adoption_result["last_known_good_refreshed"] = (
            str(state.get(LAST_KNOWN_GOOD_PROXY_URL_FIELD) or "")
            != previous_last_known_good_proxy_url
            or str(state.get(LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD) or "")
            != previous_last_known_good_proxy_observed_at
        )
    attestation = {
        "configured_model": configured_model,
        "requested_model": model_name,
        "model_match": model_match,
        "listener_ok": listener_ok,
        "models_ok": models_ok,
        "responses_ok": responses_ok,
        "effective_mode_match": effective_mode_match,
        "base_url_match": base_url_match,
        "configured_proxy_url": configured_proxy_url,
        "current_proxy_url": current_proxy_url,
        "proxy_url_match": proxy_url_match,
        "selected_backends_digest": get_selected_backends_digest(state),
        "observed_at_utc": now_iso(),
        "runtime_version": str(state.get("version", state.get("schema_version", "unknown"))),
        "attestation_source": "healthcheck --json",
    }
    launch_readiness = build_launch_readiness_surface(
        owner_command_surface="healthcheck --json",
        delegated_from_status=False,
        listener_ok=listener_ok,
        models_ok=models_ok,
        responses_ok=responses_ok,
        base_url_match=base_url_match,
        effective_mode_match=effective_mode_match,
        model_match=model_match,
        proxy_url_match=proxy_url_match,
        machine_error_code=machine_error_code,
        error_detail=(
            ""
            if ok
            else error_detail
            or (
                "Missing or invalid runtime-effective-mode.txt"
                if not effective_mode_artifact
                else state.get("last_error", "")
            )
        ),
        auth_pool_hygiene=auth_pool_hygiene,
    )
    runtime_guardrails = build_runtime_guardrail_surface(
        paths,
        launch_readiness=launch_readiness,
        auth_pool_hygiene=auth_pool_hygiene,
        recovery_result=recovery_result,
    )
    reported_last_error = (
        successful_reconcile_detail
        if ok and successful_reconcile_detail
        else (
            ""
            if ok
            else error_detail
            or (
                "Missing or invalid runtime-effective-mode.txt"
                if not effective_mode_artifact
                else state.get("last_error", "")
            )
        )
    )
    extra = {
        "desired_mode": desired_mode,
        "effective_mode": reported_effective_mode,
        "endpoint": reported_endpoint,
        "configured_model": configured_model,
        "requested_model": model_name,
        "configured_proxy_url": configured_proxy_url,
        "current_proxy_url": current_proxy_url,
        "auth_pool_hygiene": auth_pool_hygiene,
        "attestation": attestation,
        "launch_readiness": launch_readiness,
        "runtime_guardrails": runtime_guardrails,
        "last_error": reported_last_error,
    }
    if proxy_reprobe is not None:
        extra["proxy_reprobe"] = proxy_reprobe
    if proxy_reprobe_adoption_result is not None:
        extra["proxy_reprobe_adoption_result"] = proxy_reprobe_adoption_result
    extra["current_proxy_adoption_contract"] = build_current_proxy_adoption_contract(paths)
    extra["last_known_good_proxy_contract"] = build_last_known_good_proxy_contract(paths)
    extra["last_known_good_proxy"] = build_last_known_good_proxy_surface(
        paths, state, current_proxy_url
    )
    extra["deterministic_stable_recovery_contract"] = (
        build_deterministic_stable_recovery_contract(paths)
    )
    if recovery_result is not None:
        extra["deterministic_stable_recovery_result"] = recovery_result

    changed_files = detect_changed_files(before, runtime_write_surface_candidates(paths))

    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness=liveness,
        severity=severity,
        operator_action=operator_action,
        changed_files=changed_files,
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


def snapshot_known_files(paths: RuntimePaths) -> dict[Path, tuple[int, int]]:
    candidates = [
        paths.registry_file,
        paths.state_file,
        paths.managed_config_file,
        paths.config_toml,
        paths.runtime_mode_file,
        paths.runtime_effective_mode_file,
        paths.stable_runtime_generated_config_file,
        paths.launcher_script,
        managed_pid_path(paths),
    ]
    result: dict[Path, tuple[int, int]] = {}
    for candidate in candidates:
        if candidate.exists():
            stat_result = candidate.stat()
            result[candidate] = (stat_result.st_mtime_ns, stat_result.st_mode)
    return result


def snapshot_path_states(candidates: list[Path]) -> dict[Path, dict[str, Any]]:
    return {candidate: snapshot_path_state(candidate) for candidate in candidates}


def detect_changed_files(
    before: dict[Path, tuple[int, int]], after_paths: list[Path]
) -> list[str]:
    changed: list[str] = []
    for candidate in after_paths:
        if not candidate.exists():
            if candidate in before:
                changed.append(str(candidate))
            continue
        stat_result = candidate.stat()
        after = (stat_result.st_mtime_ns, stat_result.st_mode)
        if before.get(candidate) != after:
            changed.append(str(candidate))
    return changed


def detect_changed_files_by_state(
    before: dict[Path, dict[str, Any]], after_paths: list[Path]
) -> list[str]:
    changed: list[str] = []
    for candidate in after_paths:
        if before.get(candidate) != snapshot_path_state(candidate):
            changed.append(str(candidate))
    return changed


def get_launch_stabilization_seconds() -> float:
    raw = os.environ.get("WBP_LAUNCH_STABILIZATION_SECONDS", "1")
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return value if value >= 0 else 1.0


def run_launch_smoke(
    paths: RuntimePaths,
    *,
    lock_acquired: bool = False,
) -> dict[str, Any]:
    before = snapshot_known_files(paths)
    ensure_repo_owned_default_launcher_consumer(paths)
    if not paths.launcher_script.exists():
        raise RuntimeErrorInfo(
            f"Missing launcher script: {paths.launcher_script}",
            machine_error_code="MISSING_LAUNCHER_SCRIPT",
            operator_action="user_action",
        )
    registry = read_json(paths.registry_file)
    policy_drift = get_stable_policy_drift(paths, registry)
    selection = get_stable_runtime_consumer_selection_context(
        paths, registry, policy_drift
    )
    attempt = run_stable_runtime_launcher_attempt(paths, selection)
    emit_subprocess_output(stdout=attempt.stdout, stderr=attempt.stderr)
    stabilization_seconds = get_launch_stabilization_seconds()
    health_payload = run_healthcheck(
        paths,
        allow_recovery=False,
        allow_last_known_good_proxy_write=False,
        allow_current_proxy_auto_adoption=False,
    )
    if (
        attempt.launcher_exit_code == 0
        and health_payload["status"] == "ok"
        and str(health_payload["effective_mode"]) == "managed"
        and stabilization_seconds > 0
    ):
        time.sleep(stabilization_seconds)
        health_payload = run_healthcheck(
            paths,
            allow_recovery=False,
            allow_last_known_good_proxy_write=False,
            allow_current_proxy_auto_adoption=False,
        )
        if (
            health_payload["status"] != "ok"
            and str(health_payload["effective_mode"]) == "managed"
        ):
            time.sleep(min(0.1, stabilization_seconds))
            health_payload = run_healthcheck(
                paths,
                allow_recovery=False,
                allow_last_known_good_proxy_write=False,
                allow_current_proxy_auto_adoption=False,
            )
    snapshot_payload: dict[str, Any] | None = None
    if (
        health_payload["status"] == "ok"
        and str(health_payload["effective_mode"]) == "stable"
    ):
        if attempt.activation_attempted and attempt.launcher_exit_code == 0:
            snapshot_payload = build_stable_runtime_consumer_snapshot_payload(
                activation_method="process_local_env_override",
                selected_config_file=str(paths.stable_runtime_generated_config_file),
                selected_source_kind="approved_repair_target",
                selected_source_path=str(paths.repair_target_inventory_dir),
                activation_outcome=STABLE_RUNTIME_APPROVED_TARGET_ACTIVATION_OUTCOME,
                fallback_reason="",
            )
        elif attempt.activation_attempted:
            snapshot_payload = build_stable_runtime_consumer_snapshot_payload(
                activation_method="process_local_env_override",
                selected_config_file=str(paths.stable_runtime_generated_config_file),
                selected_source_kind="observed_stable_inventory_source",
                selected_source_path=str(attempt.observed_path),
                activation_outcome=STABLE_RUNTIME_OBSERVED_SOURCE_FALLBACK_OUTCOME,
                fallback_reason=(
                    "launcher_exit_nonzero"
                    if attempt.launcher_exit_code != 0
                    else "approved_target_activation_unproven"
                ),
            )
        else:
            snapshot_payload = build_stable_runtime_consumer_snapshot_payload(
                activation_method="baseline_stable_config",
                selected_config_file=str(paths.stable_config),
                selected_source_kind="observed_stable_inventory_source",
                selected_source_path=str(attempt.observed_path),
                activation_outcome=STABLE_RUNTIME_OBSERVED_SOURCE_SELECTED_OUTCOME,
                fallback_reason="",
            )
    if snapshot_payload is not None:
        write_stable_runtime_consumer_snapshot(
            paths, snapshot_payload, lock_acquired=lock_acquired
        )
    changed_files = detect_changed_files(
        before,
        runtime_write_surface_candidates(paths),
    )
    status_payload = summarize_status(paths, health_payload=health_payload)
    desired_mode = str(status_payload["desired_mode"])
    effective_mode = str(status_payload["effective_mode"])
    launch_ok = attempt.launcher_exit_code == 0 and status_payload["status"] == "ok"
    if launch_ok:
        machine_error_code = "OK"
        human_message = "Launcher smoke completed."
    elif attempt.launcher_exit_code != 0:
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
            "stable_runtime_consumer": status_payload.get(
                "stable_runtime_consumer", {}
            ),
            "auth_pool_hygiene": status_payload.get("auth_pool_hygiene", {}),
            "launch_readiness": status_payload.get("launch_readiness", {}),
            "runtime_guardrails": status_payload.get("runtime_guardrails", {}),
            "attestation_summary": status_payload.get("attestation_summary", {}),
            "last_error": status_payload.get("last_error", ""),
            "launch_mode": "smoke",
            "launcher_exit_code": attempt.launcher_exit_code,
            "stabilization_seconds": stabilization_seconds,
        },
        exit_code=(
            attempt.launcher_exit_code
            if attempt.launcher_exit_code != 0
            else status_payload["exit_code"]
        ),
    )


def run_launch_client(paths: RuntimePaths, client_path_raw: str) -> dict[str, Any]:
    before = snapshot_known_files(paths)
    profile_context = build_launch_client_profile_context(paths)
    try:
        client_path, client_path_kind = validate_launch_client_path(client_path_raw)
    except RuntimeErrorInfo as exc:
        return build_command_payload(
            ok=False,
            human_message=exc.message,
            machine_error_code=exc.machine_error_code,
            liveness="unknown",
            severity=exc.severity,
            operator_action=exc.operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra={
                "client_launch_result": {
                    "status": "client_path_invalid",
                    "attempted": True,
                    "client_path": str(Path(client_path_raw).expanduser()),
                    "client_path_kind": "unresolved",
                    "runtime_precondition_checked": False,
                    "runtime_precondition_status": "not_checked",
                    "effective_mode_observed": "",
                    "endpoint_observed": "",
                    "profile_context": profile_context,
                    "env_sanitized": True,
                    "dispatch_method": "",
                    "dispatch_attempted": False,
                    "dispatch_observed": False,
                    "dispatch_exit_code": None,
                    "launch_claim_scope": "os_dispatch_only",
                    "final_outcome": (
                        "client_path_missing"
                        if exc.machine_error_code == "MISSING_CLIENT_PATH"
                        else "client_path_invalid"
                    ),
                }
            },
            exit_code=exc.exit_code,
        )

    try:
        status_payload = observe_runtime_precondition_for_launch_client(paths)
    except RuntimeErrorInfo as exc:
        return build_command_payload(
            ok=False,
            human_message=exc.message,
            machine_error_code=exc.machine_error_code,
            liveness="unknown",
            severity=exc.severity,
            operator_action=exc.operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra={
                "client_launch_result": {
                    "status": "runtime_precondition_error",
                    "attempted": True,
                    "client_path": str(client_path),
                    "client_path_kind": client_path_kind,
                    "runtime_precondition_checked": True,
                    "runtime_precondition_status": "failed",
                    "effective_mode_observed": "",
                    "endpoint_observed": "",
                    "profile_context": profile_context,
                    "env_sanitized": True,
                    "dispatch_method": "",
                    "dispatch_attempted": False,
                    "dispatch_observed": False,
                    "dispatch_exit_code": None,
                    "launch_claim_scope": "os_dispatch_only",
                    "final_outcome": "runtime_precondition_failed",
                }
            },
            exit_code=exc.exit_code,
        )
    status_observed = summarize_owner_path_status_observation(status_payload)
    launch_readiness = status_payload.get("launch_readiness")
    auth_pool_hygiene = status_payload.get("auth_pool_hygiene")
    runtime_guardrails = status_payload.get("runtime_guardrails")
    if not isinstance(runtime_guardrails, dict):
        recovery_result = None
        stable_runtime_consumer = status_payload.get("stable_runtime_consumer")
        if isinstance(stable_runtime_consumer, dict):
            nested_recovery = stable_runtime_consumer.get(
                "deterministic_stable_recovery_result"
            )
            if isinstance(nested_recovery, dict):
                recovery_result = nested_recovery
        runtime_guardrails = build_runtime_guardrail_surface(
            paths,
            launch_readiness=launch_readiness if isinstance(launch_readiness, dict) else None,
            auth_pool_hygiene=auth_pool_hygiene if isinstance(auth_pool_hygiene, dict) else None,
            recovery_result=recovery_result,
        )
        runtime_guardrails["delegated_from_status"] = False
        runtime_guardrails["owner_command_surface"] = "launch client --json"
    runtime_precondition_status = (
        str(launch_readiness.get("status"))
        if isinstance(launch_readiness, dict)
        else ("ready" if status_payload["status"] == "ok" else "blocked")
    )
    client_launch_result: dict[str, Any] = {
        "status": "runtime_precondition_checked",
        "attempted": True,
        "client_path": str(client_path),
        "client_path_kind": client_path_kind,
        "runtime_precondition_checked": True,
        "runtime_precondition_status": runtime_precondition_status,
        "effective_mode_observed": str(status_payload.get("effective_mode", "")),
        "endpoint_observed": str(status_payload.get("endpoint", "")),
        "profile_context": profile_context,
        "env_sanitized": True,
        "dispatch_method": "",
        "dispatch_attempted": False,
        "dispatch_observed": False,
        "dispatch_exit_code": None,
        "launch_claim_scope": "os_dispatch_only",
        "final_outcome": "runtime_precondition_failed",
    }

    changed_files = detect_changed_files(before, runtime_write_surface_candidates(paths))
    if status_payload["status"] != "ok":
        return build_command_payload(
            ok=False,
            human_message=(
                "Host-client launch blocked because runtime precondition is unhealthy."
            ),
            machine_error_code="CLIENT_LAUNCH_RUNTIME_PRECONDITION_FAILED",
            liveness=str(status_payload.get("liveness", "unknown")),
            severity=str(status_payload.get("severity", "recoverable")),
            operator_action=str(status_payload.get("operator_action", "retry")),
            changed_files=changed_files,
            extra={
                "desired_mode": str(status_payload.get("desired_mode", "")),
                "effective_mode": str(status_payload.get("effective_mode", "")),
                "endpoint": str(status_payload.get("endpoint", "")),
                "client_launch_result": client_launch_result,
                "status_observed": status_observed,
                **(
                    {
                        "auth_pool_hygiene": auth_pool_hygiene,
                    }
                    if isinstance(auth_pool_hygiene, dict)
                    else {}
                ),
                **(
                    {
                        "launch_readiness": launch_readiness,
                    }
                    if isinstance(launch_readiness, dict)
                    else {}
                ),
                **(
                    {
                        "runtime_guardrails": runtime_guardrails,
                    }
                    if isinstance(runtime_guardrails, dict)
                    else {}
                ),
            },
            exit_code=int(status_payload.get("exit_code", 1) or 1),
        )

    try:
        dispatch_result = dispatch_external_client(paths, client_path, client_path_kind)
    except RuntimeErrorInfo as exc:
        unsupported_shape = exc.machine_error_code == "CLIENT_LAUNCH_UNSUPPORTED_SHAPE"
        final_outcome = (
            "unsupported_launch_shape" if unsupported_shape else "dispatch_failed"
        )
        client_launch_result.update(
            {
                "status": "dispatch_failed",
                "dispatch_method": (
                    ""
                    if unsupported_shape
                    else (
                        "macos_open_app_bundle"
                        if client_path_kind == "macos_app_bundle"
                        else "detached_executable_spawn"
                    )
                ),
                "dispatch_attempted": not unsupported_shape,
                "dispatch_observed": False,
                "dispatch_exit_code": None,
                "final_outcome": final_outcome,
            }
        )
        return build_command_payload(
            ok=False,
            human_message=exc.message,
            machine_error_code=exc.machine_error_code,
            liveness=str(status_payload.get("liveness", "unknown")),
            severity=exc.severity,
            operator_action=exc.operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra={
                "desired_mode": str(status_payload.get("desired_mode", "")),
                "effective_mode": str(status_payload.get("effective_mode", "")),
                "endpoint": str(status_payload.get("endpoint", "")),
                "client_launch_result": client_launch_result,
                "status_observed": status_observed,
                **(
                    {
                        "auth_pool_hygiene": auth_pool_hygiene,
                    }
                    if isinstance(auth_pool_hygiene, dict)
                    else {}
                ),
                **(
                    {
                        "launch_readiness": launch_readiness,
                    }
                    if isinstance(launch_readiness, dict)
                    else {}
                ),
                **(
                    {
                        "runtime_guardrails": runtime_guardrails,
                    }
                    if isinstance(runtime_guardrails, dict)
                    else {}
                ),
            },
            exit_code=exc.exit_code,
        )
    if dispatch_result["stderr"]:
        sys.stderr.write(str(dispatch_result["stderr"]))
    client_launch_result.update(
        {
            "status": (
                "dispatch_observed"
                if dispatch_result["dispatch_observed"]
                else "dispatch_failed"
            ),
            "dispatch_method": str(dispatch_result["dispatch_method"]),
            "dispatch_attempted": True,
            "dispatch_observed": bool(dispatch_result["dispatch_observed"]),
            "dispatch_exit_code": dispatch_result["dispatch_exit_code"],
            "final_outcome": (
                "dispatch_requested"
                if dispatch_result["dispatch_observed"]
                else "dispatch_failed"
            ),
        }
    )
    changed_files = detect_changed_files(before, runtime_write_surface_candidates(paths))
    if not dispatch_result["dispatch_observed"]:
        dispatch_exit_code = dispatch_result["dispatch_exit_code"]
        return build_command_payload(
            ok=False,
            human_message="Host-client dispatch failed.",
            machine_error_code="CLIENT_LAUNCH_DISPATCH_FAILED",
            liveness=str(status_payload.get("liveness", "unknown")),
            severity="recoverable",
            operator_action="retry",
            changed_files=changed_files,
            extra={
                "desired_mode": str(status_payload.get("desired_mode", "")),
                "effective_mode": str(status_payload.get("effective_mode", "")),
                "endpoint": str(status_payload.get("endpoint", "")),
                "client_launch_result": client_launch_result,
                "status_observed": status_observed,
                **(
                    {
                        "auth_pool_hygiene": auth_pool_hygiene,
                    }
                    if isinstance(auth_pool_hygiene, dict)
                    else {}
                ),
                **(
                    {
                        "runtime_guardrails": runtime_guardrails,
                    }
                    if isinstance(runtime_guardrails, dict)
                    else {}
                ),
            },
            exit_code=(
                int(dispatch_exit_code) if isinstance(dispatch_exit_code, int) else 1
            ),
        )

    return build_command_payload(
        ok=True,
        human_message="Host-client dispatch request completed.",
        machine_error_code="OK",
        liveness=str(status_payload.get("liveness", "healthy")),
        severity="recoverable",
        operator_action="none",
        changed_files=detect_changed_files(before, runtime_write_surface_candidates(paths)),
        extra={
            "desired_mode": str(status_payload.get("desired_mode", "")),
            "effective_mode": str(status_payload.get("effective_mode", "")),
            "endpoint": str(status_payload.get("endpoint", "")),
            "client_launch_result": client_launch_result,
            "status_observed": status_observed,
            **(
                {
                    "auth_pool_hygiene": auth_pool_hygiene,
                }
                if isinstance(auth_pool_hygiene, dict)
                else {}
            ),
            **(
                {
                    "launch_readiness": launch_readiness,
                }
                if isinstance(launch_readiness, dict)
                else {}
            ),
            **(
                {
                    "runtime_guardrails": runtime_guardrails,
                }
                if isinstance(runtime_guardrails, dict)
                else {}
            ),
        },
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

    changed_surface_candidates = [
        paths.registry_file,
        paths.state_file,
        paths.managed_config_file,
        paths.config_toml,
        paths.runtime_effective_mode_file,
        managed_pid_path(paths),
    ]
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
        changed_files = detect_changed_files(before, changed_surface_candidates)
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
        changed_files = detect_changed_files(before, changed_surface_candidates)
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

    materialize_selected_backend_snapshot_for_sync(paths)
    state = read_json(paths.state_file, required=False)
    changed_files = detect_changed_files(before, changed_surface_candidates)
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


def run_rollout_rotation_inspect(
    paths: RuntimePaths,
    *,
    lock_acquired: bool = False,
) -> dict[str, Any]:
    evidence_result: dict[str, Any] = {
        "schema_version": ROTATION_EVIDENCE_SCHEMA_VERSION,
        "status": "owner_path_emitted",
        "attempted": True,
        "requested_scope": "expanded-active-pool",
        "observed_at_utc": "",
        "evidence_status": "pending_observation",
        "evidence_strength": "none",
        "evidence_reason": "pending",
        "evidence_source": "runtime_state.selected_backend_ids",
        "evidence_source_layer": "legacy_flat_compatibility",
        "evidence_source_class": "legacy_flat_compatibility",
        "evidence_source_name": "",
        "evidence_source_run_id": "",
        "evidence_producer_version": "",
        "evidence_freshness": "unknown",
        "selected_backend_snapshot_validation_status": "pending",
        "selected_backend_snapshot_validation_error": "",
        "selected_backend_snapshot_compatibility": "legacy_flat",
        "selected_backend_snapshot_present": False,
        "selected_backend_ids": [],
        "selected_backends_digest": get_selected_backends_digest({}),
        "expected_selected_backends_digest": get_selected_backends_digest({}),
        "selected_backend_ids_observed": [],
        "active_pool_count_observed": 0,
        "runtime_active_pool_count_observed": None,
        "registry_active_pool_count_observed": 0,
        "active_routing_candidate_ids_observed": [],
        "active_pool_count_agreement_status": "pending",
        "stable_inventory_status": "pending",
        "policy_drift_status": "pending",
        "policy_drift_observed_status": "pending",
        "policy_drift_claim_surface_source": "pending",
        "registry_identity_status": "pending",
        "evidence_sources": [
            "runtime_state.selected_backend_snapshot",
            "runtime_state.selected_backend_ids",
            "runtime_state.active_count",
            "backend_registry.active_pool",
            "backend_registry.routing_candidate_backends",
            "stable_policy_drift",
            "registry_identity",
        ],
        "participation_status": "pending",
        "participation_summary": {},
        "blocker_type": "none",
        "claim_scope": "bounded_local_participation_evidence_only",
        "final_outcome": "pending_observation",
    }

    observation_lock = nullcontext() if lock_acquired else serialized_lock(paths)
    with observation_lock:
        registry = read_json(paths.registry_file)
        state = read_json(paths.state_file, required=False)
        registry_identity = get_registry_identity(registry)
        policy_drift_observed = get_stable_policy_drift(paths, registry)
        if should_use_approved_target_policy_drift(
            paths,
            registry,
            policy_drift_observed,
            state,
            require_live_stable_runtime=False,
        ):
            policy_drift = get_stable_policy_drift_for_inventory_source(
                registry,
                paths.repair_target_inventory_dir,
                get_approved_target_inventory_source(paths),
            )
        else:
            policy_drift = policy_drift_observed
        pool_counts = summarize_registry_pool_counts(registry)
        selected_snapshot = get_rotation_selected_backend_snapshot(state)
        selected_backend_ids = selected_snapshot["selected_backend_ids"]
        selected_snapshot_observed_at = selected_snapshot["observed_at_utc"]
        selected_snapshot_freshness = selected_snapshot["freshness"]
        selected_backends_digest = selected_snapshot["selected_backends_digest"]
        active_routing_candidate_ids = get_active_routing_candidate_backend_ids(registry)
        runtime_active_pool_count_observed = coerce_nonnegative_int(
            state.get("active_count")
        )
        registry_active_pool_count_observed = int(pool_counts.get("active", 0) or 0)
        stable_inventory_source = policy_drift.get("stable_auth_inventory_source", {})
        stable_inventory_status = (
            "available"
            if bool(stable_inventory_source.get("exists"))
            else "missing"
        )

    evidence_result["observed_at_utc"] = selected_snapshot_observed_at
    evidence_result["evidence_source"] = selected_snapshot["source"]
    evidence_result["evidence_source_layer"] = selected_snapshot["source_layer"]
    evidence_result["evidence_source_class"] = selected_snapshot["source_class"]
    evidence_result["evidence_source_name"] = selected_snapshot["source_name"]
    evidence_result["evidence_source_run_id"] = selected_snapshot["source_run_id"]
    evidence_result["evidence_producer_version"] = selected_snapshot["producer_version"]
    evidence_result["evidence_freshness"] = selected_snapshot_freshness
    evidence_result["selected_backend_snapshot_present"] = (
        selected_snapshot["compatibility"] == "nested_snapshot"
        or bool(selected_backend_ids)
    )
    evidence_result["selected_backend_snapshot_validation_status"] = selected_snapshot[
        "validation_status"
    ]
    evidence_result["selected_backend_snapshot_validation_error"] = selected_snapshot[
        "validation_error"
    ]
    evidence_result["selected_backend_snapshot_compatibility"] = selected_snapshot[
        "compatibility"
    ]
    evidence_result["selected_backend_ids"] = selected_backend_ids
    evidence_result["selected_backends_digest"] = selected_backends_digest
    evidence_result["expected_selected_backends_digest"] = selected_snapshot[
        "expected_selected_backends_digest"
    ]
    evidence_result["selected_backend_ids_observed"] = selected_backend_ids
    evidence_result["runtime_active_pool_count_observed"] = (
        runtime_active_pool_count_observed
    )
    evidence_result["registry_active_pool_count_observed"] = (
        registry_active_pool_count_observed
    )
    evidence_result["active_pool_count_observed"] = registry_active_pool_count_observed
    evidence_result["active_routing_candidate_ids_observed"] = (
        active_routing_candidate_ids
    )
    evidence_result["stable_inventory_status"] = stable_inventory_status
    evidence_result["policy_drift_status"] = str(policy_drift.get("status", "unknown"))
    evidence_result["policy_drift_observed_status"] = str(
        policy_drift_observed.get("status", "unknown")
    )
    evidence_result["policy_drift_claim_surface_source"] = str(
        (policy_drift.get("stable_auth_inventory_source") or {}).get("source", "unknown")
    )
    evidence_result["registry_identity_status"] = str(
        registry_identity.get("status", "unknown")
    )
    if runtime_active_pool_count_observed is None:
        evidence_result["active_pool_count_agreement_status"] = (
            "runtime_missing_or_invalid"
        )
    elif runtime_active_pool_count_observed != registry_active_pool_count_observed:
        evidence_result["active_pool_count_agreement_status"] = "mismatched"
    else:
        evidence_result["active_pool_count_agreement_status"] = "matched"

    selected_backend_id_set = set(selected_backend_ids)
    active_routing_candidate_id_set = set(active_routing_candidate_ids)

    if evidence_result["registry_identity_status"] != "clear":
        machine_error_code = "ROTATION_EVIDENCE_CONTRADICTED"
        human_message = (
            "Rotation participation evidence is contradicted because registry identity is ambiguous."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "registry_identity_ambiguous"
        evidence_result["participation_status"] = "contradicted"
        evidence_result["evidence_status"] = "participation_evidence_contradicted"
        evidence_result["blocker_type"] = "contradicted_state"
        evidence_result["final_outcome"] = "participation_evidence_contradicted"
        ok = False
    elif stable_inventory_status != "available":
        machine_error_code = "ROTATION_EVIDENCE_UNAVAILABLE"
        human_message = (
            "Rotation participation evidence is unknown because the stable inventory is not locally available."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "stable_inventory_missing"
        evidence_result["participation_status"] = "unknown"
        evidence_result["evidence_status"] = "participation_evidence_unavailable"
        evidence_result["blocker_type"] = "observability"
        evidence_result["final_outcome"] = "participation_evidence_unknown"
        ok = False
    elif evidence_result["policy_drift_status"] != "clear":
        machine_error_code = "ROTATION_EVIDENCE_CONTRADICTED"
        human_message = (
            "Rotation participation evidence is contradicted because stable policy drift is still detected."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "policy_drift_detected"
        evidence_result["participation_status"] = "contradicted"
        evidence_result["evidence_status"] = "participation_evidence_contradicted"
        evidence_result["blocker_type"] = "contradicted_state"
        evidence_result["final_outcome"] = "participation_evidence_contradicted"
        ok = False
    elif evidence_result["active_pool_count_agreement_status"] == "runtime_missing_or_invalid":
        machine_error_code = "ROTATION_EVIDENCE_UNKNOWN"
        human_message = (
            "Rotation participation evidence is unknown because runtime active-pool count is missing or invalid."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "runtime_active_count_missing_or_invalid"
        evidence_result["participation_status"] = "unknown"
        evidence_result["evidence_status"] = "participation_evidence_unknown"
        evidence_result["blocker_type"] = "schema_gap"
        evidence_result["final_outcome"] = "participation_evidence_unknown"
        ok = False
    elif evidence_result["active_pool_count_agreement_status"] == "mismatched":
        machine_error_code = "ROTATION_EVIDENCE_CONTRADICTED"
        human_message = (
            "Rotation participation evidence is contradicted because runtime and registry active-pool counts do not agree."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "active_pool_count_mismatched"
        evidence_result["participation_status"] = "contradicted"
        evidence_result["evidence_status"] = "participation_evidence_contradicted"
        evidence_result["blocker_type"] = "contradicted_state"
        evidence_result["final_outcome"] = "participation_evidence_contradicted"
        ok = False
    elif registry_active_pool_count_observed < 2:
        machine_error_code = "ROTATION_EVIDENCE_INSUFFICIENT"
        human_message = (
            "Rotation participation evidence is insufficient because the active pool is not yet observably expanded."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "active_pool_not_expanded"
        evidence_result["participation_status"] = "insufficient"
        evidence_result["evidence_status"] = "participation_evidence_insufficient"
        evidence_result["blocker_type"] = "observability"
        evidence_result["final_outcome"] = "participation_evidence_insufficient"
        ok = False
    elif len(active_routing_candidate_ids) < 2:
        machine_error_code = "ROTATION_EVIDENCE_INSUFFICIENT"
        human_message = (
            "Rotation participation evidence is insufficient because routing-eligible active candidates are not yet observably expanded."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "active_routing_candidates_not_expanded"
        evidence_result["participation_status"] = "insufficient"
        evidence_result["evidence_status"] = "participation_evidence_insufficient"
        evidence_result["blocker_type"] = "observability"
        evidence_result["final_outcome"] = "participation_evidence_insufficient"
        ok = False
    elif selected_snapshot["validation_status"] == "invalid":
        validation_error = selected_snapshot["validation_error"]
        if validation_error == "selected_backend_snapshot_digest_mismatch":
            machine_error_code = "ROTATION_EVIDENCE_CONTRADICTED"
            human_message = (
                "Rotation participation evidence is contradicted because the selected backend snapshot digest does not match its ids."
            )
            evidence_result["evidence_status"] = "participation_evidence_contradicted"
            evidence_result["participation_status"] = "contradicted"
            evidence_result["blocker_type"] = "contradicted_state"
            evidence_result["final_outcome"] = "participation_evidence_contradicted"
        else:
            machine_error_code = "ROTATION_EVIDENCE_UNKNOWN"
            human_message = (
                "Rotation participation evidence is unknown because the selected backend snapshot contract is not valid."
            )
            evidence_result["evidence_status"] = "participation_evidence_unknown"
            evidence_result["participation_status"] = "unknown"
            evidence_result["blocker_type"] = (
                "observability"
                if validation_error
                in {
                    "selected_backend_snapshot_observed_at_invalid",
                    "selected_backend_snapshot_ids_missing",
                }
                else "schema_gap"
            )
            evidence_result["final_outcome"] = "participation_evidence_unknown"
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = validation_error
        ok = False
    elif not selected_backend_ids:
        machine_error_code = "ROTATION_EVIDENCE_UNKNOWN"
        human_message = (
            "Rotation participation evidence is unknown because no selected backend snapshot is currently materialized."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "none"
        evidence_result["evidence_reason"] = "selected_backend_snapshot_missing"
        evidence_result["participation_status"] = "unknown"
        evidence_result["evidence_status"] = "participation_evidence_unknown"
        evidence_result["blocker_type"] = "observability"
        evidence_result["final_outcome"] = "participation_evidence_unknown"
        ok = False
    elif not selected_snapshot_observed_at or selected_snapshot_freshness == "unknown":
        machine_error_code = "ROTATION_EVIDENCE_UNKNOWN"
        human_message = (
            "Rotation participation evidence is unknown because selected backend ids lack a same-event observation timestamp."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "partial"
        evidence_result["evidence_reason"] = (
            "selected_backend_snapshot_observation_time_missing_or_invalid"
        )
        evidence_result["participation_status"] = "unknown"
        evidence_result["evidence_status"] = "participation_evidence_unknown"
        evidence_result["blocker_type"] = "observability"
        evidence_result["final_outcome"] = "participation_evidence_unknown"
        ok = False
    elif selected_snapshot_freshness == "stale":
        machine_error_code = "ROTATION_EVIDENCE_STALE"
        human_message = (
            "Rotation participation evidence is stale because the selected backend snapshot is outside the freshness window."
        )
        operator_action = "retry"
        evidence_result["evidence_strength"] = "partial"
        evidence_result["evidence_reason"] = "selected_backend_snapshot_stale"
        evidence_result["participation_status"] = "stale"
        evidence_result["evidence_status"] = "participation_evidence_stale"
        evidence_result["blocker_type"] = "stale_state"
        evidence_result["final_outcome"] = "participation_evidence_stale"
        ok = False
    elif not selected_backend_id_set.issubset(active_routing_candidate_id_set):
        machine_error_code = "ROTATION_EVIDENCE_CONTRADICTED"
        human_message = (
            "Rotation participation evidence is contradicted because selected backends do not match routing-eligible active candidates."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "partial"
        evidence_result["evidence_reason"] = "selected_backend_outside_active_candidates"
        evidence_result["participation_status"] = "contradicted"
        evidence_result["evidence_status"] = "participation_evidence_contradicted"
        evidence_result["blocker_type"] = "contradicted_state"
        evidence_result["final_outcome"] = "participation_evidence_contradicted"
        ok = False
    elif len(selected_backend_id_set) < 2:
        machine_error_code = "ROTATION_EVIDENCE_INSUFFICIENT"
        human_message = (
            "Rotation participation evidence is insufficient because only a single selected backend is visible in the bounded local snapshot."
        )
        operator_action = "user_action"
        evidence_result["evidence_strength"] = "partial"
        evidence_result["evidence_reason"] = "single_backend_snapshot_only"
        evidence_result["participation_status"] = "insufficient"
        evidence_result["evidence_status"] = "participation_evidence_insufficient"
        evidence_result["blocker_type"] = "observability"
        evidence_result["final_outcome"] = "participation_evidence_insufficient"
        ok = False
    else:
        machine_error_code = "OK"
        human_message = (
            "Bounded local rotation participation evidence is available."
        )
        operator_action = "none"
        evidence_result["evidence_strength"] = "partial"
        evidence_result["evidence_reason"] = "multi_backend_snapshot"
        evidence_result["participation_status"] = "available"
        evidence_result["evidence_status"] = "participation_evidence_present"
        evidence_result["blocker_type"] = "none"
        evidence_result["final_outcome"] = "participation_evidence_available"
        ok = True

    evidence_result["participation_summary"] = {
        "status": evidence_result["participation_status"],
        "final_outcome": evidence_result["final_outcome"],
        "selected_backend_count": len(selected_backend_ids),
        "active_routing_candidate_count": len(active_routing_candidate_ids),
        "registry_active_pool_count": registry_active_pool_count_observed,
        "runtime_active_pool_count": runtime_active_pool_count_observed,
        "active_pool_count_agreement_status": evidence_result[
            "active_pool_count_agreement_status"
        ],
    }

    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness="unknown",
        severity="recoverable",
        operator_action=operator_action,
        changed_files=[],
        extra={
            "rotation_evidence_result": evidence_result,
            "delegated_evidence": {
                "pool_summary": {
                    "active": registry_active_pool_count_observed,
                    "runtime_active_count": runtime_active_pool_count_observed,
                    "selected_backend_ids": selected_backend_ids,
                    "backend_count": len(registry.get("backends") or []),
                },
                "policy_drift_summary": {
                    "status": policy_drift.get("status"),
                    "machine_error_code": policy_drift.get("machine_error_code"),
                    "configured_active_count": policy_drift.get(
                        "configured_active_count"
                    ),
                    "allowed_stable_auth_count": policy_drift.get(
                        "allowed_stable_auth_count"
                    ),
                    "stable_auth_inventory_count": policy_drift.get(
                        "stable_auth_inventory_count"
                    ),
                    "stable_auth_inventory_source": stable_inventory_source,
                },
                "registry_identity_summary": summarize_registry_identity(
                    registry_identity
                ),
            },
        },
    )


def summarize_stable_10_rollback_readiness(
    health_payload: dict[str, Any], status_payload: dict[str, Any]
) -> dict[str, Any]:
    recovery_contract = health_payload.get("deterministic_stable_recovery_contract")
    last_known_good_contract = health_payload.get("last_known_good_proxy_contract")
    consumer = status_payload.get("stable_runtime_consumer")
    if not isinstance(recovery_contract, dict):
        return {
            "status": "failed",
            "machine_error_code": "STAGE_PROOF_ROLLBACK_READINESS_FAILED",
            "reason": "deterministic_recovery_contract_missing",
        }
    if not isinstance(last_known_good_contract, dict):
        return {
            "status": "failed",
            "machine_error_code": "STAGE_PROOF_ROLLBACK_READINESS_FAILED",
            "reason": "last_known_good_contract_missing",
        }
    if not isinstance(consumer, dict):
        return {
            "status": "failed",
            "machine_error_code": "STAGE_PROOF_ROLLBACK_READINESS_FAILED",
            "reason": "stable_runtime_consumer_missing",
        }

    fallback_contract = consumer.get("fallback_contract")
    readiness = consumer.get("consumer_activation_readiness")
    if not isinstance(fallback_contract, dict) or not isinstance(readiness, dict):
        return {
            "status": "failed",
            "machine_error_code": "STAGE_PROOF_ROLLBACK_READINESS_FAILED",
            "reason": "fallback_or_readiness_surface_missing",
        }

    recovery_contract_ready = (
        recovery_contract.get("status") == "contract_ready"
        and recovery_contract.get("owner_command_surface") == "healthcheck --json"
        and recovery_contract.get("entry_owner") == "healthcheck_live_attestation_path"
        and bool(recovery_contract.get("status_delegates_to_owner"))
    )
    last_known_good_ready = (
        last_known_good_contract.get("status") == "contract_ready"
        and last_known_good_contract.get("owner_command_surface") == "healthcheck --json"
        and bool(last_known_good_contract.get("status_delegates_to_owner"))
        and bool(last_known_good_contract.get("changed_files_visibility_required"))
    )
    fallback_contract_ready = (
        fallback_contract.get("status") == "contract_ready"
        and bool(fallback_contract.get("fallback_allowed"))
        and bool(fallback_contract.get("silent_fallback_forbidden"))
        and bool(fallback_contract.get("desired_source_remains_visible"))
        and bool(fallback_contract.get("effective_source_must_report_fallback"))
    )
    readiness_machine_error_code = str(readiness.get("machine_error_code", ""))
    readiness_ok = readiness_machine_error_code == "OK"
    managed_runtime_with_pending_stable_consumer = (
        str(health_payload.get("status")) == "ok"
        and str(status_payload.get("effective_mode")) == "managed"
        and readiness_machine_error_code
        in {
            "STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING",
            "STABLE_RUNTIME_CONSUMER_FALLBACK_ACTIVE",
        }
    )
    fallback_readiness_ok = (
        readiness_ok or managed_runtime_with_pending_stable_consumer
    )

    if (
        recovery_contract_ready
        and last_known_good_ready
        and fallback_contract_ready
        and fallback_readiness_ok
    ):
        return {
            "status": "ready",
            "machine_error_code": "OK",
            "reason": (
                "bounded_fallback_and_recovery_contracts_ready"
                if readiness_ok
                else "bounded_fallback_and_recovery_contracts_ready_while_managed_runtime_pending_stable_consumer_activation"
            ),
        }

    if not recovery_contract_ready:
        reason = "deterministic_recovery_contract_not_ready"
    elif not last_known_good_ready:
        reason = "last_known_good_contract_not_ready"
    elif not fallback_contract_ready:
        reason = "fallback_contract_not_ready"
    else:
        reason = "consumer_activation_readiness_not_ok"
    return {
        "status": "failed",
        "machine_error_code": "STAGE_PROOF_ROLLBACK_READINESS_FAILED",
        "reason": reason,
    }


def get_repo_commit_hash() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if result.returncode != 0:
        return ""
    commit_hash = result.stdout.strip()
    return commit_hash if re.fullmatch(r"[0-9a-fA-F]{40}", commit_hash) else ""


def redact_url_credentials(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc or "@" not in parsed.netloc:
        return value
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    redacted_netloc = f"[redacted]@{host}{port}"
    return urllib.parse.urlunsplit(
        (parsed.scheme, redacted_netloc, parsed.path, parsed.query, parsed.fragment)
    )


def redact_sensitive_string(value: str) -> str:
    value = redact_url_credentials(value)
    value = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted-token]", value)
    value = re.sub(
        r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]+",
        "[redacted-header]",
        value,
    )
    value = re.sub(
        r"(?i)\b(password|secret|token|cookie|api[_-]?key)\b\s*([:=])\s*[^\s;,]+",
        lambda match: f"{match.group(1)}{match.group(2)}[redacted]",
        value,
    )
    return value


def redact_evidence_value(value: Any, key: str = "") -> Any:
    normalized_key = key.lower()
    if normalized_key == "auth_ref":
        return Path(str(value or "")).name
    if normalized_key == "notes" and value:
        return "[redacted]"
    if any(
        token in normalized_key
        for token in (
            "api_key",
            "apikey",
            "authorization",
            "bearer",
            "password",
            "secret",
            "token",
            "cookie",
        )
    ):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(item_key): redact_evidence_value(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_evidence_value(item, key) for item in value]
    if isinstance(value, str):
        return redact_sensitive_string(value)
    return value


def redacted_json_has_secret_leak(payload: Any) -> bool:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    forbidden_patterns = [
        r"sk-[A-Za-z0-9_-]+",
        r"OPENAI_API_KEY",
        r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]+",
        r"://[^/\\s:@]+:[^/\\s@]+@",
    ]
    return any(re.search(pattern, encoded) for pattern in forbidden_patterns)


def write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def export_scale_evidence_bundle(
    paths: RuntimePaths,
    *,
    packet_result: dict[str, Any],
    registry: dict[str, Any],
    state: dict[str, Any],
    health_payload: dict[str, Any],
    status_payload: dict[str, Any],
    accounts_payload: dict[str, Any],
    rotation_payload: dict[str, Any],
    fallback_readiness: dict[str, Any],
) -> dict[str, Any]:
    export_dir = Path(tempfile.mkdtemp(prefix="wild-boar-proxy-scale-evidence-"))
    redacted_registry = redact_evidence_value(registry)
    redacted_state = redact_evidence_value(state)
    redacted_packet = redact_evidence_value(packet_result)
    redacted_evidence = redact_evidence_value(
        {
            "healthcheck_summary": health_payload,
            "status_summary": status_payload,
            "accounts_summary": accounts_payload,
            "rotation_summary": rotation_payload,
            "fallback_readiness_summary": fallback_readiness,
        }
    )
    metadata = {
        "schema_version": SCALE_EVIDENCE_PACKET_SCHEMA_VERSION,
        "generated_at_utc": now_iso(),
        "attestation_source": "rollout evidence capture 16 --json",
        "claim_scope": SCALE_EVIDENCE_CLAIM_SCOPE,
    }
    bundle_payload = {
        "packet": redacted_packet,
        "registry": redacted_registry,
        "state": redacted_state,
        "evidence": redacted_evidence,
        "metadata": metadata,
    }
    redaction_ok = not redacted_json_has_secret_leak(bundle_payload)

    registry_artifact = export_dir / "backend-registry.redacted.json"
    state_artifact = export_dir / "supervisor-state.redacted.json"
    evidence_artifact = export_dir / "evidence-summary.redacted.json"
    metadata_artifact = export_dir / "metadata.json"
    packet_artifact = export_dir / "evidence-packet.json"
    runtime_mode_artifact = export_dir / "runtime-mode.txt"
    runtime_effective_mode_artifact = export_dir / "runtime-effective-mode.txt"
    write_json_artifact(registry_artifact, redacted_registry)
    write_json_artifact(state_artifact, redacted_state)
    write_json_artifact(evidence_artifact, redacted_evidence)
    write_json_artifact(metadata_artifact, metadata)
    write_json_artifact(packet_artifact, redacted_packet)
    runtime_mode_artifact.write_text(
        read_text(paths.runtime_mode_file, default="stable") + "\n", encoding="utf-8"
    )
    runtime_effective_mode_artifact.write_text(
        read_text(paths.runtime_effective_mode_file, default="stable") + "\n",
        encoding="utf-8",
    )
    artifact_paths = [
        registry_artifact,
        state_artifact,
        evidence_artifact,
        metadata_artifact,
        packet_artifact,
        runtime_mode_artifact,
        runtime_effective_mode_artifact,
    ]

    return {
        "status": "exported" if redaction_ok else "redaction_failed",
        "bundle_path": str(export_dir),
        "artifact_paths": [str(path) for path in artifact_paths],
        "file_count": len(list(export_dir.iterdir())),
        "redaction_status": "passed" if redaction_ok else "failed",
        "forbidden_content_detected": not redaction_ok,
    }


def summarize_scale_evidence_accounts(accounts_payload: dict[str, Any]) -> dict[str, Any]:
    accounts = accounts_payload.get("accounts") or []
    lifecycle_counts = {"active": 0, "reserve": 0, "retired": 0}
    status_counts: dict[str, int] = {}
    for account in accounts:
        if not isinstance(account, dict):
            continue
        pool = str(account.get("pool", ""))
        if pool in lifecycle_counts:
            lifecycle_counts[pool] += 1
        status = str(account.get("status", "unknown") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    registry_identity = accounts_payload.get("registry_identity", {})
    return {
        "account_count": len(accounts),
        "lifecycle_counts": lifecycle_counts,
        "status_counts": status_counts,
        "registry_identity_status": (
            registry_identity.get("status")
            if isinstance(registry_identity, dict)
            else "unknown"
        ),
    }


def has_command_payload_shape(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(field in payload for field in COMMAND_PAYLOAD_REQUIRED_FIELDS)


def evaluate_scale_evidence_strict_json_contract(
    command_payloads: dict[str, Any],
) -> dict[str, Any]:
    invalid_payload_surfaces = [
        surface
        for surface, payload in command_payloads.items()
        if not has_command_payload_shape(payload)
    ]
    status = "passed" if not invalid_payload_surfaces else "failed"
    return {
        "status": status,
        "machine_error_code": (
            "OK" if status == "passed" else "STRICT_JSON_COMMAND_API_GATE_FAILED"
        ),
        "invalid_payload_surfaces": invalid_payload_surfaces,
    }


def build_scale_gate_summary(
    *,
    runtime_attestation_status: str,
    strict_json_contract: dict[str, Any],
    runtime_changed_files: list[str],
    fallback_readiness: dict[str, Any],
    packet_status: str,
    packet_machine_error_code: str,
) -> dict[str, Any]:
    fallback_status = str(fallback_readiness.get("status", "failed"))
    strict_json_status = str(strict_json_contract.get("status", "failed"))
    gates = {
        SCALE_GATE_RUNTIME_ATTESTATION: {
            "status": "passed" if runtime_attestation_status == "passed" else "failed",
            "machine_error_code": (
                "OK"
                if runtime_attestation_status == "passed"
                else "RUNTIME_ATTESTATION_GATE_FAILED"
            ),
        },
        SCALE_GATE_STRICT_JSON_COMMAND_API: {
            "status": "passed" if strict_json_status == "passed" else "failed",
            "machine_error_code": str(
                strict_json_contract.get("machine_error_code", "UNKNOWN")
            ),
            "invalid_payload_surfaces": list(
                strict_json_contract.get("invalid_payload_surfaces") or []
            ),
        },
        SCALE_GATE_STATE_SERIALIZATION: {
            "status": "passed" if not runtime_changed_files else "failed",
            "machine_error_code": (
                "OK" if not runtime_changed_files else "STATE_SERIALIZATION_GATE_FAILED"
            ),
            "runtime_changed_files": list(runtime_changed_files),
        },
        SCALE_GATE_FALLBACK_DRILL: {
            "status": "passed" if fallback_status == "ready" else "failed",
            "machine_error_code": (
                "OK"
                if fallback_status == "ready"
                else str(
                    fallback_readiness.get(
                        "machine_error_code", "FALLBACK_DRILL_GATE_FAILED"
                    )
                )
            ),
        },
        SCALE_GATE_EVIDENCE_PACKET: {
            "status": "passed" if packet_status == "complete" else "failed",
            "machine_error_code": (
                "OK"
                if packet_status == "complete"
                else (
                    packet_machine_error_code
                    if packet_machine_error_code != "OK"
                    else "SCALE_EVIDENCE_PACKET_GATE_FAILED"
                )
            ),
            "packet_status": packet_status,
        },
    }
    blocked_gate_names = [
        gate_name
        for gate_name in SCALE_GATE_ORDER
        if str(gates.get(gate_name, {}).get("status", "failed")) != "passed"
    ]
    return {
        "status": "derived_view",
        "derived_only": True,
        "source_of_truth": False,
        "truth_sources": [
            "runtime_attestation_status",
            "strict_json_command_api_status",
            "state_serialization_status",
            "fallback_readiness_status",
            "packet_status",
        ],
        "gates": gates,
        "all_gates_passed": not blocked_gate_names,
        "blocked_gate_names": blocked_gate_names,
    }


def run_rollout_evidence_capture(paths: RuntimePaths, target: str) -> dict[str, Any]:
    if target != SCALE_EVIDENCE_FIELD_TARGET:
        return build_command_payload(
            ok=False,
            human_message=f"Scale evidence capture target {target} is not supported.",
            machine_error_code="SCALE_EVIDENCE_TARGET_UNSUPPORTED",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={
                "scale_evidence_packet_result": {
                    "schema_version": SCALE_EVIDENCE_PACKET_SCHEMA_VERSION,
                    "claim_target": str(target),
                    "claim_scope": SCALE_EVIDENCE_CLAIM_SCOPE,
                    "packet_status": "unsafe_to_claim",
                    "scale_gate_summary": {
                        "status": "derived_view",
                        "derived_only": True,
                        "source_of_truth": False,
                        "truth_sources": [],
                        "gates": {},
                        "all_gates_passed": False,
                        "blocked_gate_names": [SCALE_GATE_EVIDENCE_PACKET],
                    },
                    "observed_at_utc": now_iso(),
                    "blocked_reasons": [
                        {
                            "machine_error_code": "SCALE_EVIDENCE_TARGET_UNSUPPORTED",
                            "reason": "unsupported_claim_target",
                        }
                    ],
                    "final_outcome": "field_evidence_packet_unsafe_to_claim",
                }
            },
        )

    write_candidates = runtime_write_surface_candidates(paths) + [paths.runtime_mode_file]
    before = snapshot_path_states(write_candidates)
    registry = read_json(paths.registry_file)
    state = read_json(paths.state_file, required=False)
    observed_at_utc = now_iso()
    health_payload, healthcheck_retry = run_rollout_attestation_healthcheck(
        paths, allow_stable_fallback_write=False
    )
    status_payload = summarize_status(paths, health_payload=health_payload)
    accounts_payload = list_accounts(paths)
    rotation_payload = run_rollout_rotation_inspect(paths)
    fallback_readiness = summarize_stable_10_rollback_readiness(
        health_payload, status_payload
    )
    strict_json_contract = evaluate_scale_evidence_strict_json_contract(
        {
            "healthcheck": health_payload,
            "status": status_payload,
            "accounts_list": accounts_payload,
            "rotation_inspect": rotation_payload,
        }
    )
    runtime_changed_files = detect_changed_files_by_state(before, write_candidates)
    pool_counts = summarize_registry_pool_counts(registry)
    accounts_summary = summarize_scale_evidence_accounts(accounts_payload)
    rotation_result = rotation_payload.get("rotation_evidence_result", {})
    selected_snapshot_status = str(
        rotation_result.get("selected_backend_snapshot_validation_status", "unknown")
    )
    selected_snapshot_compatibility = str(
        rotation_result.get("selected_backend_snapshot_compatibility", "unknown")
    )
    rotation_status = str(rotation_result.get("participation_status", "unknown"))
    runtime_attestation_status = (
        "passed" if health_payload.get("status") == "ok" else "failed"
    )
    strict_json_status = str(strict_json_contract.get("status", "failed"))
    state_serialization_status = "passed" if not runtime_changed_files else "failed"
    fallback_readiness_status = str(fallback_readiness.get("status", "failed"))
    pool_counts_status = (
        "matched_16"
        if int(pool_counts.get("active", 0) or 0) == 16
        and coerce_nonnegative_int(state.get("active_count")) == 16
        else "not_matched_16"
    )
    registry_identity_status = str(
        accounts_summary.get("registry_identity_status", "unknown")
    )
    if registry_identity_status == "clear":
        accounts_summary_status = "clear"
    elif registry_identity_status == "ambiguous":
        accounts_summary_status = "ambiguous"
    else:
        accounts_summary_status = "unknown"
    commit_hash = get_repo_commit_hash()
    runtime_version = str(state.get("version", state.get("schema_version", "unknown")))

    blocked_reasons: list[dict[str, Any]] = []
    if runtime_changed_files:
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_RUNTIME_MUTATION_DETECTED",
                "reason": "runtime_write_surface_changed",
                "changed_files": runtime_changed_files,
            }
        )
    if strict_json_status != "passed":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_STRICT_JSON_INCOMPLETE",
                "reason": "strict_json_command_api_gate_failed",
                "invalid_payload_surfaces": list(
                    strict_json_contract.get("invalid_payload_surfaces") or []
                ),
            }
        )
    if runtime_attestation_status != "passed":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_ATTESTATION_INCOMPLETE",
                "reason": "runtime_attestation_not_passed",
            }
        )
    if rotation_status == "contradicted":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_ROTATION_CONTRADICTED",
                "reason": "rotation_evidence_contradicted",
            }
        )
    elif rotation_status != "available":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_ROTATION_INCOMPLETE",
                "reason": f"rotation_evidence_{rotation_status}",
            }
        )
    if fallback_readiness_status != "ready":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_FALLBACK_INCOMPLETE",
                "reason": "fallback_readiness_not_ready",
            }
        )
    if pool_counts_status != "matched_16":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_POOL_COUNTS_INCOMPLETE",
                "reason": "active_pool_not_observed_as_16",
            }
        )
    if accounts_summary_status != "clear":
        if accounts_summary_status == "ambiguous":
            blocked_reasons.append(
                {
                    "machine_error_code": "SCALE_EVIDENCE_REGISTRY_CONTRADICTED",
                    "reason": "registry_identity_not_clear",
                }
            )
        else:
            blocked_reasons.append(
                {
                    "machine_error_code": "SCALE_EVIDENCE_ACCOUNTS_SUMMARY_INCOMPLETE",
                    "reason": "accounts_summary_not_machine_complete",
                }
            )
    if selected_snapshot_status not in {"valid", "legacy"}:
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_SELECTED_SNAPSHOT_INCOMPLETE",
                "reason": "selected_backend_snapshot_not_valid_or_legacy_compatible",
            }
        )
    if not commit_hash:
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_COMMIT_HASH_MISSING",
                "reason": "commit_hash_unavailable",
            }
        )

    packet_result: dict[str, Any] = {
        "schema_version": SCALE_EVIDENCE_PACKET_SCHEMA_VERSION,
        "claim_target": SCALE_EVIDENCE_FIELD_TARGET,
        "claim_scope": SCALE_EVIDENCE_CLAIM_SCOPE,
        "packet_status": "pending",
        "observed_at_utc": observed_at_utc,
        "commit_hash": commit_hash,
        "runtime_version": runtime_version,
        "environment_note": "local_mac_control_layer_evidence_packet",
        "runtime_attestation_status": runtime_attestation_status,
        "runtime_attestation_retry_summary": healthcheck_retry,
        "strict_json_command_api_status": strict_json_status,
        "state_serialization_status": state_serialization_status,
        "rotation_evidence_status": rotation_status,
        "fallback_readiness_status": fallback_readiness_status,
        "pool_counts_status": pool_counts_status,
        "diagnostics_redaction_status": "pending",
        "selected_backend_snapshot_status": selected_snapshot_status,
        "accounts_summary_status": accounts_summary_status,
        "pool_counts": pool_counts,
        "selected_backend_snapshot_summary": {
            "status": selected_snapshot_status,
            "compatibility": selected_snapshot_compatibility,
            "source": rotation_result.get("evidence_source"),
            "source_class": rotation_result.get("evidence_source_class"),
            "freshness": rotation_result.get("evidence_freshness"),
            "selected_backends_digest": rotation_result.get("selected_backends_digest"),
            "selected_backend_count": len(rotation_result.get("selected_backend_ids") or []),
        },
        "accounts_summary": accounts_summary,
        "runtime_attestation_summary": {
            "status": health_payload.get("status"),
            "machine_error_code": health_payload.get("machine_error_code"),
            "effective_mode": health_payload.get("effective_mode"),
            "attestation": health_payload.get("attestation", {}),
        },
        "rotation_evidence_summary": {
            "status": rotation_payload.get("status"),
            "machine_error_code": rotation_payload.get("machine_error_code"),
            "participation_status": rotation_status,
            "evidence_status": rotation_result.get("evidence_status"),
            "evidence_reason": rotation_result.get("evidence_reason"),
            "active_pool_count_agreement_status": rotation_result.get(
                "active_pool_count_agreement_status"
            ),
        },
        "fallback_readiness_summary": fallback_readiness,
        "diagnostics_bundle_summary": {},
        "blocked_reasons": blocked_reasons,
        "scale_gate_summary": {},
        "final_outcome": "pending",
    }

    bundle_summary = export_scale_evidence_bundle(
        paths,
        packet_result=packet_result,
        registry=registry,
        state=state,
        health_payload=health_payload,
        status_payload=status_payload,
        accounts_payload=accounts_payload,
        rotation_payload=rotation_payload,
        fallback_readiness=fallback_readiness,
    )
    packet_result["diagnostics_redaction_status"] = str(
        bundle_summary.get("redaction_status", "failed")
    )
    packet_result["diagnostics_bundle_summary"] = bundle_summary
    if packet_result["diagnostics_redaction_status"] != "passed":
        blocked_reasons.append(
            {
                "machine_error_code": "SCALE_EVIDENCE_REDACTION_FAILED",
                "reason": "diagnostics_bundle_redaction_failed",
            }
        )

    if any(
        reason.get("machine_error_code")
        in {
            "SCALE_EVIDENCE_RUNTIME_MUTATION_DETECTED",
            "SCALE_EVIDENCE_REDACTION_FAILED",
        }
        for reason in blocked_reasons
    ):
        packet_status = "unsafe_to_claim"
        final_outcome = "field_evidence_packet_unsafe_to_claim"
        machine_error_code = "SCALE_EVIDENCE_UNSAFE_TO_CLAIM"
    elif any(
        reason.get("machine_error_code")
        in {
            "SCALE_EVIDENCE_ROTATION_CONTRADICTED",
            "SCALE_EVIDENCE_REGISTRY_CONTRADICTED",
        }
        for reason in blocked_reasons
    ):
        packet_status = "contradicted"
        final_outcome = "field_evidence_packet_contradicted"
        machine_error_code = "SCALE_EVIDENCE_CONTRADICTED"
    elif blocked_reasons:
        packet_status = "incomplete"
        final_outcome = "field_evidence_packet_incomplete"
        machine_error_code = "SCALE_EVIDENCE_INCOMPLETE"
    else:
        packet_status = "complete"
        final_outcome = "field_evidence_packet_complete"
        machine_error_code = "OK"

    packet_result["packet_status"] = packet_status
    packet_result["final_outcome"] = final_outcome
    packet_result["scale_gate_summary"] = build_scale_gate_summary(
        runtime_attestation_status=runtime_attestation_status,
        strict_json_contract=strict_json_contract,
        runtime_changed_files=runtime_changed_files,
        fallback_readiness=fallback_readiness,
        packet_status=packet_status,
        packet_machine_error_code=machine_error_code,
    )
    packet_artifact_path = Path(str(bundle_summary["bundle_path"])) / "evidence-packet.json"
    write_json_artifact(
        packet_artifact_path,
        redact_evidence_value(packet_result),
    )
    artifact_paths = list(bundle_summary.get("artifact_paths") or [])
    if str(packet_artifact_path) not in artifact_paths:
        artifact_paths.append(str(packet_artifact_path))
    bundle_summary["artifact_paths"] = artifact_paths

    ok = packet_status == "complete"
    return build_command_payload(
        ok=ok,
        human_message=(
            "16-account field evidence packet is complete."
            if ok
            else "16-account field evidence packet is not complete."
        ),
        machine_error_code=machine_error_code,
        liveness="unknown",
        severity="recoverable",
        operator_action="none" if ok else "user_action",
        changed_files=artifact_paths,
        extra={"scale_evidence_packet_result": packet_result},
    )


def summarize_rollout_posture_candidate_classes(
    registry: dict[str, Any],
) -> dict[str, list[str]]:
    classes: dict[str, list[str]] = {
        "active_live_capable": [],
        "reserve_live_capable": [],
        "active_quota_exhausted": [],
        "reserve_quota_exhausted": [],
        "active_auth_invalid": [],
        "reserve_auth_invalid": [],
        "active_cooldown_only": [],
        "reserve_cooldown_only": [],
        "active_unknown_unverified": [],
        "reserve_unknown_unverified": [],
        "active_excluded": [],
        "reserve_excluded": [],
    }
    for backend in registry.get("backends", []):
        backend_id = str(backend.get("id") or "").strip()
        if not backend_id:
            continue
        pool = str(backend.get("pool", ""))
        if pool not in {"active", "reserve"}:
            continue
        eligibility_class, _ = classify_backend_stage_posture_eligibility(backend)
        bucket = f"{pool}_{eligibility_class}"
        if bucket in classes:
            classes[bucket].append(backend_id)
    for backend_ids in classes.values():
        backend_ids.sort()
    return classes


def summarize_rollout_posture_runtime_truth(
    paths: RuntimePaths,
    state: dict[str, Any],
) -> dict[str, Any]:
    desired_mode = get_desired_mode(paths)
    effective_mode = get_effective_mode(paths, state)
    host, port, endpoint = get_endpoint(paths, effective_mode)
    listener_ok = socket_is_listening(host, port)
    reported_effective_mode = reconcile_effective_mode_for_reporting(
        effective_mode, listener_ok=listener_ok
    )
    _, _, reported_endpoint = get_endpoint(paths, reported_effective_mode)
    configured_base_url = read_toml_string(paths.config_toml, "base_url")
    selected_backend_ids = sorted(
        str(item).strip()
        for item in state.get("selected_backend_ids", []) or []
        if str(item).strip()
    )
    return {
        "surface": "rollout posture inspect",
        "read_only": True,
        "live_attestation_checked": False,
        "desired_mode": desired_mode,
        "state_effective_mode": str(state.get("effective_mode", "unknown")),
        "effective_mode": reported_effective_mode,
        "endpoint": reported_endpoint,
        "configured_base_url": configured_base_url,
        "base_url_match": configured_base_url == reported_endpoint,
        "listener_host": host,
        "listener_port": port,
        "listener_ok": listener_ok,
        "state_status": str(state.get("status", "unknown")),
        "state_active_count": coerce_nonnegative_int(state.get("active_count")),
        "state_reserve_count": coerce_nonnegative_int(state.get("reserve_count")),
        "selected_backend_ids": selected_backend_ids,
        "state_last_error_present": bool(str(state.get("last_error", "")).strip()),
        "required_live_prechecks": [
            "status --json",
            "healthcheck --json",
            "rollout rotation inspect --json",
        ],
    }


def run_rollout_posture_inspect(paths: RuntimePaths, stage: str) -> dict[str, Any]:
    requested_stage = str(stage).strip()
    stage_advance_config = {
        "15": {"source_stage": "10"},
        "20": {"source_stage": "15"},
    }
    posture_result: dict[str, Any] = {
        "schema_version": 1,
        "status": "owner_path_emitted",
        "attempted": True,
        "requested_stage": requested_stage,
        "source_stage": "",
        "classification": "pending",
        "blocker_code": "PENDING",
        "pool_count_summary": {},
        "candidate_summary": {},
        "runtime_truth_summary": {},
        "policy_stage_summary": {},
        "rotation_summary": {},
        "normalization_decision_packet": {},
        "final_outcome": "pending_observation",
    }

    def build_posture_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        operator_action: str = "none",
        severity: str = "recoverable",
        exit_code: int | None = None,
    ) -> dict[str, Any]:
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness="unknown",
            severity=severity,
            operator_action=operator_action,
            changed_files=[],
            extra={"rollout_posture_result": posture_result},
            exit_code=exit_code,
        )

    config = stage_advance_config.get(requested_stage)
    if config is None:
        posture_result["classification"] = "UNSUPPORTED_TARGET_STAGE"
        posture_result["blocker_code"] = "STAGE_ADVANCE_UNSUPPORTED_STAGE"
        posture_result["final_outcome"] = "unsupported_target_stage"
        return build_posture_payload(
            ok=False,
            human_message="Rollout posture inspect supports target stages 15 and 20.",
            machine_error_code="STAGE_ADVANCE_UNSUPPORTED_STAGE",
            operator_action="user_action",
        )

    source_stage = str(config["source_stage"])
    posture_result["source_stage"] = source_stage
    source_policy = dict(STAGED_POOL_POLICY_PACKETS[source_stage])
    target_policy = dict(STAGED_POOL_POLICY_PACKETS[requested_stage])
    source_active_target = int(source_policy["active_target"])
    source_reserve_target = int(source_policy["reserve_target"])
    target_active_target = int(target_policy["active_target"])
    target_reserve_target = int(target_policy["reserve_target"])

    registry = read_json(paths.registry_file)
    state = read_json(paths.state_file, required=False)
    observed_stage = observe_current_stage_from_pool_policy(registry)
    current_stage = str(observed_stage.get("observed_stage", ""))
    pool_counts = summarize_registry_pool_counts(registry)
    active_count = int(pool_counts.get("active", 0) or 0)
    reserve_count = int(pool_counts.get("reserve", 0) or 0)
    retired_count = int(pool_counts.get("retired", 0) or 0)
    managed_pool_count = active_count + reserve_count + retired_count
    candidate_classes = summarize_rollout_posture_candidate_classes(registry)
    active_live_capable_ids = list(candidate_classes["active_live_capable"])
    reserve_live_capable_ids = list(candidate_classes["reserve_live_capable"])
    active_overflow_live_capable_ids = (
        active_live_capable_ids[source_active_target:]
        if len(active_live_capable_ids) > source_active_target
        else []
    )
    reserve_candidate_id = (
        reserve_live_capable_ids[0]
        if reserve_live_capable_ids
        else (active_overflow_live_capable_ids[0] if active_overflow_live_capable_ids else "")
    )
    selected_backend_ids = sorted(
        str(item).strip()
        for item in state.get("selected_backend_ids", []) or []
        if str(item).strip()
    )
    rotation_payload = run_rollout_rotation_inspect(paths)
    rotation_result = rotation_payload.get("rotation_evidence_result", {})
    rotation_status = str(rotation_result.get("participation_status", "unknown"))
    protected_active = active_live_capable_ids[:source_active_target]
    hold_set = sorted(
        set(candidate_classes["active_quota_exhausted"])
        | set(candidate_classes["active_auth_invalid"])
        | set(candidate_classes["active_cooldown_only"])
        | set(candidate_classes["active_unknown_unverified"])
    )
    do_not_touch = sorted(set(protected_active) | set(selected_backend_ids))

    posture_result["pool_count_summary"] = {
        "active_count": active_count,
        "reserve_count": reserve_count,
        "retired_count": retired_count,
        "managed_pool_count": managed_pool_count,
        "source_active_target": source_active_target,
        "source_reserve_target": source_reserve_target,
        "target_active_target": target_active_target,
        "target_reserve_target": target_reserve_target,
    }
    posture_result["candidate_summary"] = {
        **candidate_classes,
        "active_live_capable_count": len(active_live_capable_ids),
        "reserve_live_capable_count": len(reserve_live_capable_ids),
        "active_overflow_live_capable_ids": active_overflow_live_capable_ids,
        "selected_backend_ids": selected_backend_ids,
        "reserve_candidate_id": reserve_candidate_id,
    }
    posture_result["runtime_truth_summary"] = summarize_rollout_posture_runtime_truth(
        paths, state
    )
    posture_result["policy_stage_summary"] = {
        **observed_stage,
        "source_stage": source_stage,
        "requested_stage": requested_stage,
        "source_policy": source_policy,
        "target_policy": target_policy,
    }
    posture_result["rotation_summary"] = {
        "status": rotation_payload.get("status"),
        "machine_error_code": rotation_payload.get("machine_error_code"),
        "participation_status": rotation_status,
        "evidence_status": rotation_result.get("evidence_status"),
        "evidence_reason": rotation_result.get("evidence_reason"),
        "selected_backend_snapshot_present": rotation_result.get(
            "selected_backend_snapshot_present"
        ),
        "selected_backend_snapshot_validation_status": rotation_result.get(
            "selected_backend_snapshot_validation_status"
        ),
        "selected_backend_ids_observed": rotation_result.get(
            "selected_backend_ids_observed", []
        ),
        "active_routing_candidate_ids_observed": rotation_result.get(
            "active_routing_candidate_ids_observed", []
        ),
    }
    posture_result["normalization_decision_packet"] = {
        "protected_active": protected_active,
        "reserve_candidate": reserve_candidate_id,
        "reserve_set": active_overflow_live_capable_ids,
        "hold_set": hold_set,
        "retire_set": [],
        "do_not_touch": do_not_touch,
        "expected_source_posture_after_normalization": {
            "active_window_target": source_active_target,
            "reserve_target": source_reserve_target,
            "explicit_reserve_candidate_required": True,
        },
        "expected_target_posture_after_stage_advance": {
            "active_window_target": target_active_target,
            "reserve_target": target_reserve_target,
            "stage_advance_candidate": reserve_candidate_id,
        },
    }

    if observed_stage.get("status") != "matched" or current_stage not in {
        source_stage,
        requested_stage,
    }:
        posture_result["classification"] = "POLICY_STAGE_NOT_CANONICAL"
        posture_result["blocker_code"] = "STAGE_ADVANCE_POLICY_STAGE_NOT_CANONICAL"
        posture_result["final_outcome"] = "blocked_by_policy_stage"
        return build_posture_payload(
            ok=False,
            human_message=(
                "Rollout posture is blocked because policy stage is not canonical "
                "for the requested advance target."
            ),
            machine_error_code="STAGE_ADVANCE_POLICY_STAGE_NOT_CANONICAL",
            operator_action="user_action",
        )

    if current_stage == requested_stage:
        if active_count == target_active_target and reserve_count == target_reserve_target:
            posture_result["classification"] = "READY_ALREADY_ON_TARGET"
            posture_result["blocker_code"] = "OK"
            posture_result["final_outcome"] = "target_stage_already_satisfied"
            return build_posture_payload(
                ok=True,
                human_message="Rollout posture is already on the requested target stage.",
                machine_error_code="OK",
            )
        posture_result["classification"] = "LIVE_POSTURE_DRIFT_ONLY"
        posture_result["blocker_code"] = "LIVE_POSTURE_DRIFT_ONLY"
        posture_result["final_outcome"] = "target_stage_posture_needs_normalization"
        return build_posture_payload(
            ok=False,
            human_message=(
                "Rollout posture is on the requested target stage but lifecycle "
                "posture is not aligned with the canonical target window."
            ),
            machine_error_code="LIVE_POSTURE_DRIFT_ONLY",
            operator_action="user_action",
        )

    if len(active_live_capable_ids) < source_active_target:
        posture_result["classification"] = "INSUFFICIENT_ELIGIBLE_POOL"
        posture_result["blocker_code"] = "INSUFFICIENT_ELIGIBLE_POOL"
        posture_result["final_outcome"] = "insufficient_source_stage_live_capable_pool"
        return build_posture_payload(
            ok=False,
            human_message=(
                "Rollout posture is blocked because source-stage live-capable active "
                "pool is insufficient."
            ),
            machine_error_code="INSUFFICIENT_ELIGIBLE_POOL",
            operator_action="user_action",
        )

    if active_count > source_active_target:
        posture_result["classification"] = "LIVE_POSTURE_DRIFT_ONLY"
        posture_result["blocker_code"] = "LIVE_POSTURE_DRIFT_ONLY"
        posture_result["final_outcome"] = "source_stage_overfull_but_normalizable"
        return build_posture_payload(
            ok=False,
            human_message=(
                "Rollout posture has enough eligible inventory, but active posture "
                "is over the source active window and needs normalization first."
            ),
            machine_error_code="LIVE_POSTURE_DRIFT_ONLY",
            operator_action="user_action",
        )

    if not reserve_candidate_id:
        posture_result["classification"] = "RESERVE_CANDIDATE_NOT_IDENTIFIED"
        posture_result["blocker_code"] = "RESERVE_CANDIDATE_NOT_IDENTIFIED"
        posture_result["final_outcome"] = "reserve_candidate_missing"
        return build_posture_payload(
            ok=False,
            human_message=(
                "Rollout posture is blocked because no explicit live-capable reserve "
                "candidate is available."
            ),
            machine_error_code="RESERVE_CANDIDATE_NOT_IDENTIFIED",
            operator_action="user_action",
        )

    if rotation_status != "available":
        posture_result["classification"] = "ROTATION_EVIDENCE_INSUFFICIENT"
        posture_result["blocker_code"] = "ROTATION_EVIDENCE_INSUFFICIENT"
        posture_result["final_outcome"] = "rotation_evidence_not_available"
        return build_posture_payload(
            ok=False,
            human_message=(
                "Rollout posture is blocked because bounded rotation evidence is "
                "not available."
            ),
            machine_error_code="ROTATION_EVIDENCE_INSUFFICIENT",
            operator_action="user_action",
        )

    posture_result["classification"] = "READY_FOR_STAGE_ADVANCE"
    posture_result["blocker_code"] = "OK"
    posture_result["final_outcome"] = "ready_for_explicit_reserve_stage_advance"
    return build_posture_payload(
        ok=True,
        human_message=(
            "Rollout posture is ready for one explicit reserve-first stage advance."
        ),
        machine_error_code="OK",
    )


def run_rollout_stage_prove(
    paths: RuntimePaths,
    stage: str,
    *,
    lock_acquired: bool = False,
) -> dict[str, Any]:
    before = snapshot_known_files(paths)
    requested_stage_label = str(stage).strip()
    stage_proof_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "requested_stage": requested_stage_label,
        "policy_stage_status": "pending",
        "policy_stage_observed": "",
        "policy_mapping_status": "pending",
        "active_pool_count_observed": 0,
        "reserve_pool_count_observed": 0,
        "rotation_evidence_status": "pending",
        "runtime_attestation_status": "not_checked",
        "runtime_smoke_status": "not_invoked",
        "rollback_readiness_status": "not_checked",
        "delegated_evidence": {},
        "proof_gate_status": "pending",
        "final_outcome": "pending_observation",
    }

    def build_stage_proof_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        operator_action: str = "none",
        severity: str = "recoverable",
        exit_code: int | None = None,
    ) -> dict[str, Any]:
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness="unknown",
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra={
                "requested_stage": stage_proof_result["requested_stage"],
                "stage_proof_result": stage_proof_result,
            },
            exit_code=exit_code,
        )

    requested_stage = stage_proof_result["requested_stage"]
    stable_stage_label = f"Stable-{requested_stage}"
    if requested_stage not in {"10", "15"}:
        stage_proof_result["policy_stage_status"] = "unsupported_stage"
        stage_proof_result["proof_gate_status"] = "blocked_by_requested_stage"
        stage_proof_result["final_outcome"] = "proof_blocked"
        stage_proof_result["delegated_evidence"] = {
            "stage_mapping_summary": {
                "status": "unowned_stage",
                "machine_error_code": "STAGE_PROOF_STAGE_UNOWNED",
                "requested_stage": requested_stage,
            }
        }
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because this stage does not yet own a proof surface."
            ),
            machine_error_code="STAGE_PROOF_STAGE_UNOWNED",
            operator_action="user_action",
        )
    stage_mapping = summarize_stage_pool_policy_mapping(requested_stage)
    stage_proof_result["policy_mapping_status"] = str(
        stage_mapping.get("status", "unsupported")
    )
    if stage_mapping.get("status") != "ok":
        stage_proof_result["policy_stage_status"] = "unsupported_stage"
        stage_proof_result["proof_gate_status"] = "blocked_by_requested_stage"
        stage_proof_result["final_outcome"] = "proof_blocked"
        stage_proof_result["delegated_evidence"] = {
            "stage_mapping_summary": stage_mapping,
        }
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because the requested stage is not supported."
            ),
            machine_error_code=str(
                stage_mapping.get("machine_error_code", "POOL_POLICY_STAGE_UNSUPPORTED")
            ),
            operator_action="user_action",
        )

    registry = read_json(paths.registry_file)
    observed_stage = observe_current_stage_from_pool_policy(registry)
    stage_proof_result["policy_stage_observed"] = str(
        observed_stage.get("observed_stage", "")
    )
    stage_proof_result["policy_stage_status"] = str(observed_stage.get("status", "invalid"))

    stage_proof_result["delegated_evidence"] = {
        "stage_mapping_summary": stage_mapping,
        "policy_stage_summary": observed_stage,
    }
    if (
        observed_stage.get("status") != "matched"
        or observed_stage.get("observed_stage") != requested_stage
    ):
        stage_proof_result["proof_gate_status"] = "blocked_by_stage_policy_mismatch"
        stage_proof_result["final_outcome"] = "stage_policy_mismatch"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because current staged policy does not match canonical stage {requested_stage}."
            ),
            machine_error_code="STAGE_PROOF_POLICY_MISMATCH",
            operator_action="user_action",
        )

    rotation_payload = run_rollout_rotation_inspect(
        paths, lock_acquired=lock_acquired
    )
    rotation_result = rotation_payload.get("rotation_evidence_result", {})
    rotation_status = str(rotation_result.get("participation_status", "unknown"))
    active_pool_count_observed = coerce_nonnegative_int(
        rotation_result.get("registry_active_pool_count_observed")
    )
    desired_policy = dict(stage_mapping.get("mapped_pool_policy") or {})
    active_target = coerce_nonnegative_int(desired_policy.get("active_target"))
    reserve_target = coerce_nonnegative_int(desired_policy.get("reserve_target"))

    stage_proof_result["active_pool_count_observed"] = active_pool_count_observed or 0
    stage_proof_result["rotation_evidence_status"] = rotation_status
    stage_proof_result["delegated_evidence"] = {
        "stage_mapping_summary": stage_mapping,
        "policy_stage_summary": observed_stage,
        "rotation_summary": {
            "status": rotation_payload.get("status"),
            "machine_error_code": rotation_payload.get("machine_error_code"),
            "human_message": rotation_payload.get("human_message"),
            "rotation_evidence_result": rotation_result,
        },
    }

    if (
        active_target is None
        or active_pool_count_observed is None
        or active_pool_count_observed != active_target
    ):
        stage_proof_result["proof_gate_status"] = "blocked_by_active_pool_alignment"
        stage_proof_result["final_outcome"] = (
            "insufficient_active_pool"
            if active_pool_count_observed is not None
            and active_target is not None
            and active_pool_count_observed < active_target
            else "proof_blocked"
        )
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because observed pool counts are not aligned with canonical stage {requested_stage} targets."
            ),
            machine_error_code="STAGE_PROOF_ACTIVE_POOL_MISMATCH",
            operator_action="user_action",
        )

    if rotation_status == "contradicted":
        stage_proof_result["proof_gate_status"] = "blocked_by_rotation_contradiction"
        stage_proof_result["final_outcome"] = "rotation_evidence_contradicted"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because bounded rotation evidence is contradicted."
            ),
            machine_error_code="STAGE_PROOF_ROTATION_CONTRADICTED",
            operator_action="user_action",
        )
    if rotation_status == "insufficient":
        stage_proof_result["proof_gate_status"] = "blocked_by_rotation_insufficiency"
        stage_proof_result["final_outcome"] = "rotation_evidence_insufficient"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because bounded rotation evidence is insufficient."
            ),
            machine_error_code="STAGE_PROOF_ROTATION_INSUFFICIENT",
            operator_action="user_action",
        )
    if rotation_status != "available":
        stage_proof_result["proof_gate_status"] = "blocked_by_rotation_unknown"
        stage_proof_result["final_outcome"] = "proof_blocked"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because bounded rotation evidence is not available."
            ),
            machine_error_code="STAGE_PROOF_ROTATION_UNKNOWN",
            operator_action="user_action",
        )

    pre_health_payload, pre_healthcheck_retry = run_rollout_attestation_healthcheck(
        paths
    )
    pre_status_payload = summarize_status(paths, health_payload=pre_health_payload)
    pre_pool_summary = pre_status_payload.get("pool_summary", {})
    reserve_pool_count_observed = coerce_nonnegative_int(pre_pool_summary.get("reserve"))
    stage_proof_result["reserve_pool_count_observed"] = reserve_pool_count_observed or 0

    pre_attestation_ok = (
        pre_health_payload.get("status") == "ok"
        and str(pre_health_payload.get("effective_mode")) == "managed"
    )
    pre_rollback_readiness = summarize_stable_10_rollback_readiness(
        pre_health_payload, pre_status_payload
    )
    stage_proof_result["runtime_attestation_status"] = (
        "passed" if pre_attestation_ok else "failed"
    )
    stage_proof_result["rollback_readiness_status"] = str(
        pre_rollback_readiness.get("status", "failed")
    )
    stage_proof_result["delegated_evidence"].update(
        {
            "pre_smoke_healthcheck_summary": {
                "status": pre_health_payload.get("status"),
                "machine_error_code": pre_health_payload.get("machine_error_code"),
                "effective_mode": pre_health_payload.get("effective_mode"),
                "attestation": pre_health_payload.get("attestation", {}),
                "deterministic_stable_recovery_contract": pre_health_payload.get(
                    "deterministic_stable_recovery_contract", {}
                ),
                "last_known_good_proxy_contract": pre_health_payload.get(
                    "last_known_good_proxy_contract", {}
                ),
                "last_known_good_proxy": pre_health_payload.get(
                    "last_known_good_proxy", {}
                ),
            },
            "pre_smoke_healthcheck_retry_summary": pre_healthcheck_retry,
            "pre_smoke_status_summary": {
                "status": pre_status_payload.get("status"),
                "machine_error_code": pre_status_payload.get("machine_error_code"),
                "pool_summary": pre_pool_summary,
                "attestation_summary": pre_status_payload.get("attestation_summary", {}),
                "stable_runtime_consumer": pre_status_payload.get(
                    "stable_runtime_consumer", {}
                ),
            },
            "pre_smoke_rollback_readiness_summary": pre_rollback_readiness,
        }
    )

    if (
        reserve_target is None
        or reserve_pool_count_observed is None
        or reserve_pool_count_observed != reserve_target
    ):
        stage_proof_result["proof_gate_status"] = "blocked_by_reserve_pool_alignment"
        stage_proof_result["final_outcome"] = "reserve_posture_mismatch"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because reserve pool posture is not aligned with canonical stage {requested_stage} targets."
            ),
            machine_error_code="STAGE_PROOF_RESERVE_POSTURE_MISMATCH",
            operator_action="user_action",
        )

    if not pre_attestation_ok:
        stage_proof_result["proof_gate_status"] = "blocked_by_runtime_attestation"
        stage_proof_result["final_outcome"] = "runtime_attestation_failed"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because live managed runtime attestation did not pass."
            ),
            machine_error_code="STAGE_PROOF_ATTESTATION_FAILED",
            operator_action="retry",
        )

    if pre_rollback_readiness.get("status") != "ready":
        stage_proof_result["proof_gate_status"] = "blocked_by_rollback_readiness"
        stage_proof_result["final_outcome"] = "rollback_readiness_failed"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because rollback readiness is not available."
            ),
            machine_error_code=str(
                pre_rollback_readiness.get(
                    "machine_error_code", "STAGE_PROOF_ROLLBACK_READINESS_FAILED"
                )
            ),
            operator_action="user_action",
        )

    smoke_payload = run_launch_smoke(paths, lock_acquired=lock_acquired)
    stage_proof_result["runtime_smoke_status"] = (
        "passed" if smoke_payload.get("status") == "ok" else "failed"
    )
    stage_proof_result["delegated_evidence"]["runtime_smoke_summary"] = {
        "status": smoke_payload.get("status"),
        "machine_error_code": smoke_payload.get("machine_error_code"),
        "effective_mode": smoke_payload.get("effective_mode"),
        "launcher_exit_code": smoke_payload.get("launcher_exit_code"),
        "attestation_summary": smoke_payload.get("attestation_summary", {}),
        "stable_runtime_consumer": smoke_payload.get("stable_runtime_consumer", {}),
    }

    if smoke_payload.get("status") != "ok":
        stage_proof_result["proof_gate_status"] = "blocked_by_runtime_smoke"
        stage_proof_result["final_outcome"] = "runtime_smoke_failed"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because bounded runtime smoke did not pass."
            ),
            machine_error_code="STAGE_PROOF_SMOKE_FAILED",
            operator_action="retry",
            exit_code=int(smoke_payload.get("exit_code", 1) or 1),
        )

    post_health_payload, post_healthcheck_retry = (
        run_rollout_attestation_healthcheck(paths)
    )
    post_status_payload = summarize_status(paths, health_payload=post_health_payload)
    post_rollback_readiness = summarize_stable_10_rollback_readiness(
        post_health_payload, post_status_payload
    )
    post_attestation_ok = (
        post_health_payload.get("status") == "ok"
        and str(post_health_payload.get("effective_mode")) == "managed"
    )
    stage_proof_result["runtime_attestation_status"] = (
        "passed" if post_attestation_ok else "failed"
    )
    stage_proof_result["rollback_readiness_status"] = str(
        post_rollback_readiness.get("status", "failed")
    )
    stage_proof_result["delegated_evidence"]["post_smoke_healthcheck_summary"] = {
        "status": post_health_payload.get("status"),
        "machine_error_code": post_health_payload.get("machine_error_code"),
        "effective_mode": post_health_payload.get("effective_mode"),
        "attestation": post_health_payload.get("attestation", {}),
        "deterministic_stable_recovery_contract": post_health_payload.get(
            "deterministic_stable_recovery_contract", {}
        ),
        "last_known_good_proxy_contract": post_health_payload.get(
            "last_known_good_proxy_contract", {}
        ),
        "last_known_good_proxy": post_health_payload.get("last_known_good_proxy", {}),
    }
    stage_proof_result["delegated_evidence"]["post_smoke_healthcheck_retry_summary"] = (
        post_healthcheck_retry
    )
    stage_proof_result["delegated_evidence"]["post_smoke_status_summary"] = {
        "status": post_status_payload.get("status"),
        "machine_error_code": post_status_payload.get("machine_error_code"),
        "pool_summary": post_status_payload.get("pool_summary", {}),
        "attestation_summary": post_status_payload.get("attestation_summary", {}),
        "stable_runtime_consumer": post_status_payload.get("stable_runtime_consumer", {}),
    }
    stage_proof_result["delegated_evidence"]["post_smoke_rollback_readiness_summary"] = (
        post_rollback_readiness
    )

    if not post_attestation_ok:
        stage_proof_result["runtime_smoke_status"] = "failed"
        stage_proof_result["proof_gate_status"] = "blocked_by_post_smoke_reproof"
        stage_proof_result["final_outcome"] = "runtime_smoke_failed"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because bounded runtime smoke did not preserve a healthy managed runtime proof surface."
            ),
            machine_error_code="STAGE_PROOF_SMOKE_FAILED",
            operator_action="retry",
        )

    if post_rollback_readiness.get("status") != "ready":
        stage_proof_result["proof_gate_status"] = "blocked_by_rollback_readiness"
        stage_proof_result["final_outcome"] = "rollback_readiness_failed"
        return build_stage_proof_payload(
            ok=False,
            human_message=(
                f"{stable_stage_label} proof is blocked because rollback readiness is not available."
            ),
            machine_error_code=str(
                post_rollback_readiness.get(
                    "machine_error_code", "STAGE_PROOF_ROLLBACK_READINESS_FAILED"
                )
            ),
            operator_action="user_action",
        )

    stage_proof_result["proof_gate_status"] = f"stable_{requested_stage}_gate_closed"
    stage_proof_result["final_outcome"] = f"stable_{requested_stage}_proved"
    return build_stage_proof_payload(
        ok=True,
        human_message=(
            f"{stable_stage_label} proof gate is closed with bounded delegated evidence."
        ),
        machine_error_code="OK",
    )


def summarize_rollout_stage_advance_preflight(
    paths: RuntimePaths,
    *,
    lock_acquired: bool = False,
) -> tuple[bool, str, str, dict[str, Any]]:
    health_payload, healthcheck_retry = run_rollout_attestation_healthcheck(paths)
    status_payload = summarize_status(paths, health_payload=health_payload)
    rotation_payload = run_rollout_rotation_inspect(
        paths, lock_acquired=lock_acquired
    )
    rotation_result = rotation_payload.get("rotation_evidence_result", {})

    attestation_ok = (
        health_payload.get("status") == "ok"
        and str(health_payload.get("effective_mode")) == "managed"
    )
    rotation_status = str(rotation_result.get("participation_status", "unknown"))
    consumer = status_payload.get("stable_runtime_consumer", {})
    readiness = summarize_stable_10_rollback_readiness(health_payload, status_payload)
    readiness_ok = readiness.get("status") == "ready"

    summary = {
        "attestation_status": "passed" if attestation_ok else "failed",
        "rotation_status": rotation_status,
        "readiness_status": "ready" if readiness_ok else "failed",
        "healthcheck_summary": {
            "status": health_payload.get("status"),
            "machine_error_code": health_payload.get("machine_error_code"),
            "effective_mode": health_payload.get("effective_mode"),
            "liveness": health_payload.get("liveness"),
        },
        "healthcheck_retry_summary": healthcheck_retry,
        "status_summary": summarize_owner_path_status_observation(status_payload),
        "rotation_summary": {
            "status": rotation_payload.get("status"),
            "machine_error_code": rotation_payload.get("machine_error_code"),
            "rotation_evidence_result": rotation_result,
        },
        "readiness_summary": readiness,
    }

    if not attestation_ok:
        return (
            False,
            "STAGE_ADVANCE_PREFLIGHT_ATTESTATION_FAILED",
            "retry",
            summary,
        )
    if rotation_status != "available":
        return False, "STAGE_ADVANCE_PREFLIGHT_ROTATION_FAILED", "user_action", summary
    if not readiness_ok:
        return False, "STAGE_ADVANCE_PREFLIGHT_READINESS_FAILED", "user_action", summary
    return True, "OK", "none", summary


def materialize_rollout_stage_advance_stable_auth(
    paths: RuntimePaths,
    backend: dict[str, Any],
) -> dict[str, Any]:
    auth_ref = Path(str(backend.get("auth_ref") or "")).expanduser()
    auth_basename = get_auth_basename(backend.get("auth_ref"))
    if not auth_basename:
        raise RuntimeErrorInfo(
            "Rollout stage advance cannot materialize stable inventory because the promoted backend auth basename is invalid.",
            machine_error_code="STAGE_ADVANCE_AUTH_BASENAME_INVALID",
            severity="recoverable",
            operator_action="user_action",
        )
    if not auth_ref.is_file():
        raise RuntimeErrorInfo(
            "Rollout stage advance cannot materialize stable inventory because the promoted backend auth source is missing.",
            machine_error_code="STAGE_ADVANCE_AUTH_SOURCE_MISSING",
            severity="recoverable",
            operator_action="user_action",
        )
    stable_auth_dir, inventory_source = get_stable_auth_inventory_source(paths)
    stable_auth_dir.mkdir(parents=True, exist_ok=True)
    target_path = stable_auth_dir / auth_basename
    if auth_ref.resolve() != target_path.resolve():
        shutil.copy2(auth_ref, target_path)
    if target_path.read_bytes() != auth_ref.read_bytes():
        raise RuntimeErrorInfo(
            "Rollout stage advance stable inventory verification failed after copying the promoted auth.",
            machine_error_code="STAGE_ADVANCE_STABLE_INVENTORY_VERIFY_FAILED",
            severity="recoverable",
            operator_action="retry",
        )
    return {
        "auth_basename": auth_basename,
        "source_auth_ref": str(auth_ref),
        "target_path": str(target_path),
        "target_dir": str(stable_auth_dir),
        "inventory_source": inventory_source,
    }


def summarize_rollout_stage_advance_postflight(
    paths: RuntimePaths,
    *,
    expected_stage: str,
    backend_id: str,
    active_pool_count_before: int,
    lock_acquired: bool = False,
) -> tuple[bool, str, str, dict[str, Any]]:
    registry = read_json(paths.registry_file)
    observed_stage = observe_current_stage_from_pool_policy(registry)
    pool_counts = summarize_registry_pool_counts(registry)
    backend_matches = get_registry_backends_by_id(registry, backend_id)
    promoted_backend = backend_matches[0] if len(backend_matches) == 1 else None
    health_payload, healthcheck_retry = run_rollout_attestation_healthcheck(paths)
    status_payload = summarize_status(paths, health_payload=health_payload)
    rotation_payload = run_rollout_rotation_inspect(
        paths, lock_acquired=lock_acquired
    )
    rotation_result = rotation_payload.get("rotation_evidence_result", {})
    readiness = summarize_stable_10_rollback_readiness(health_payload, status_payload)

    desired_policy = STAGED_POOL_POLICY_PACKETS.get(expected_stage, {})
    active_target = coerce_nonnegative_int(desired_policy.get("active_target"))
    reserve_target = coerce_nonnegative_int(desired_policy.get("reserve_target"))
    active_pool_count_after = int(pool_counts.get("active", 0) or 0)
    reserve_pool_count_after = int(pool_counts.get("reserve", 0) or 0)
    policy_ok = (
        observed_stage.get("status") == "matched"
        and str(observed_stage.get("observed_stage", "")) == expected_stage
    )
    backend_promoted_ok = bool(
        isinstance(promoted_backend, dict)
        and str(promoted_backend.get("pool", "")) == "active"
        and not bool(promoted_backend.get("manual_hold", False))
    )
    active_step_ok = (
        active_pool_count_after == active_pool_count_before + 1
        and (active_target is None or active_pool_count_after <= active_target)
    )
    reserve_step_ok = (
        reserve_target is None or reserve_pool_count_after == reserve_target
    )
    attestation_ok = (
        health_payload.get("status") == "ok"
        and str(health_payload.get("effective_mode")) == "managed"
    )
    rotation_status = str(rotation_result.get("participation_status", "unknown"))
    readiness_ok = readiness.get("status") == "ready"
    summary = {
        "policy_stage_status": (
            "matched" if policy_ok else str(observed_stage.get("status", "invalid"))
        ),
        "policy_stage_observed": str(observed_stage.get("observed_stage", "")),
        "promotion_verification_status": "passed"
        if backend_promoted_ok and active_step_ok and reserve_step_ok
        else "failed",
        "active_pool_count_before": active_pool_count_before,
        "active_pool_count_after": active_pool_count_after,
        "active_target": active_target,
        "reserve_pool_count_after": reserve_pool_count_after,
        "reserve_target": reserve_target,
        "backend_verification": {
            "backend_id": backend_id,
            "backend_match_count": len(backend_matches),
            "backend_pool_observed": (
                str(promoted_backend.get("pool", ""))
                if isinstance(promoted_backend, dict)
                else ""
            ),
            "backend_manual_hold_observed": (
                bool(promoted_backend.get("manual_hold", False))
                if isinstance(promoted_backend, dict)
                else False
            ),
        },
        "attestation_status": "passed" if attestation_ok else "failed",
        "rotation_status": rotation_status,
        "readiness_status": "ready" if readiness_ok else "failed",
        "healthcheck_summary": {
            "status": health_payload.get("status"),
            "machine_error_code": health_payload.get("machine_error_code"),
            "effective_mode": health_payload.get("effective_mode"),
            "liveness": health_payload.get("liveness"),
        },
        "healthcheck_retry_summary": healthcheck_retry,
        "status_summary": summarize_owner_path_status_observation(status_payload),
        "rotation_summary": {
            "status": rotation_payload.get("status"),
            "machine_error_code": rotation_payload.get("machine_error_code"),
            "rotation_evidence_result": rotation_result,
        },
        "readiness_summary": readiness,
    }

    if not policy_ok:
        return False, "STAGE_ADVANCE_POSTFLIGHT_POLICY_FAILED", "user_action", summary
    if not backend_promoted_ok or not active_step_ok or not reserve_step_ok:
        return False, "STAGE_ADVANCE_POSTFLIGHT_PROMOTION_FAILED", "user_action", summary
    if not attestation_ok:
        return False, "STAGE_ADVANCE_POSTFLIGHT_ATTESTATION_FAILED", "retry", summary
    if rotation_status != "available":
        return False, "STAGE_ADVANCE_POSTFLIGHT_ROTATION_FAILED", "user_action", summary
    if not readiness_ok:
        return False, "STAGE_ADVANCE_POSTFLIGHT_READINESS_FAILED", "user_action", summary
    return True, "OK", "none", summary


def allow_stage_advance_source_proof_with_one_explicit_reserve_candidate(
    *,
    proof_payload: dict[str, Any],
    proof_result: dict[str, Any],
    source_stage: str,
    backend_precondition_status: str,
    active_count_before: int,
    reserve_count_before: int,
) -> bool:
    source_policy = STAGED_POOL_POLICY_PACKETS.get(source_stage, {})
    source_active_target = coerce_nonnegative_int(source_policy.get("active_target"))
    source_reserve_target = coerce_nonnegative_int(source_policy.get("reserve_target"))
    active_pool_count_observed = coerce_nonnegative_int(
        proof_result.get("active_pool_count_observed")
    )
    reserve_pool_count_observed = coerce_nonnegative_int(
        proof_result.get("reserve_pool_count_observed")
    )
    return bool(
        proof_payload.get("status") != "ok"
        and proof_payload.get("machine_error_code")
        == "STAGE_PROOF_RESERVE_POSTURE_MISMATCH"
        and backend_precondition_status == "eligible_reserve_backend"
        and source_active_target is not None
        and source_reserve_target is not None
        and active_count_before == source_active_target
        and reserve_count_before == source_reserve_target + 1
        and active_pool_count_observed == source_active_target
        and reserve_pool_count_observed == source_reserve_target + 1
        and str(proof_result.get("rotation_evidence_status", "unknown")) == "available"
        and str(proof_result.get("runtime_attestation_status", "failed")) == "passed"
        and str(proof_result.get("rollback_readiness_status", "failed")) == "ready"
    )


def run_rollout_stage_advance(
    paths: RuntimePaths, stage: str, backend_id: str
) -> dict[str, Any]:
    before = snapshot_known_files(paths)
    extra_write_surfaces: list[Path] = []
    stateful_write_surfaces = runtime_write_surface_candidates(paths)
    before_stateful = snapshot_path_states(stateful_write_surfaces)
    before_extra_states: dict[Path, dict[str, Any]] = {}
    stage_advancement_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "requested_stage": str(stage).strip(),
        "requested_backend_id": str(backend_id).strip(),
        "preflight_stage10_proof_status": "not_invoked",
        "preflight_stage15_proof_status": "not_invoked",
        "preflight_policy_status": "pending",
        "policy_transition_status": "not_invoked",
        "promotion_status": "not_invoked",
        "postflight_attestation_status": "not_checked",
        "postflight_rotation_status": "not_checked",
        "rollback_readiness_status": "not_checked",
        "rollback_attempted": False,
        "rollback_outcome": "not_attempted",
        "delegated_evidence": {},
        "final_outcome": "pending_preconditions",
    }
    composite_owner_lock_acquired = False

    def build_stage_advance_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        operator_action: str = "none",
        severity: str = "recoverable",
        exit_code: int | None = None,
    ) -> dict[str, Any]:
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness="unknown",
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files_by_state(
                before_stateful | before_extra_states,
                stateful_write_surfaces + extra_write_surfaces,
            ),
            extra={
                "requested_stage": stage_advancement_result["requested_stage"],
                "requested_backend_id": stage_advancement_result["requested_backend_id"],
                "stage_advancement_result": stage_advancement_result,
            },
            exit_code=exit_code,
        )

    def rollback_after_failed_step(
        *,
        human_message: str,
        machine_error_code: str,
        operator_action: str,
        exit_code: int | None = None,
        snapshots: dict[str, dict[str, Any]] | None,
        severity: str = "recoverable",
        final_outcome: str = "rollback_completed_after_failed_step",
    ) -> dict[str, Any]:
        if snapshots is None:
            stage_advancement_result["final_outcome"] = final_outcome
            return build_stage_advance_payload(
                ok=False,
                human_message=human_message,
                machine_error_code=machine_error_code,
                operator_action=operator_action,
                exit_code=exit_code,
                severity=severity,
            )

        stage_advancement_result["rollback_attempted"] = True
        try:
            if composite_owner_lock_acquired:
                restore_promotion_owner_path_runtime_surfaces(paths, snapshots)
                stable_auth_entry_snapshot = snapshots.get("stable_auth_entry_file")
                stable_auth_entry_path = snapshots.get("stable_auth_entry_path")
                stable_auth_dir_snapshot = snapshots.get("stable_auth_dir")
                stable_auth_dir_path = snapshots.get("stable_auth_dir_path")
                if isinstance(stable_auth_entry_snapshot, dict) and isinstance(
                    stable_auth_entry_path, str
                ):
                    restore_path_state(
                        Path(stable_auth_entry_path), stable_auth_entry_snapshot
                    )
                if isinstance(stable_auth_dir_snapshot, dict) and isinstance(
                    stable_auth_dir_path, str
                ):
                    restore_rollout_stage_advance_inventory_dir_state(
                        Path(stable_auth_dir_path), stable_auth_dir_snapshot
                    )
            else:
                with serialized_lock(paths):
                    restore_promotion_owner_path_runtime_surfaces(paths, snapshots)
                    stable_auth_entry_snapshot = snapshots.get("stable_auth_entry_file")
                    stable_auth_entry_path = snapshots.get("stable_auth_entry_path")
                    stable_auth_dir_snapshot = snapshots.get("stable_auth_dir")
                    stable_auth_dir_path = snapshots.get("stable_auth_dir_path")
                    if isinstance(stable_auth_entry_snapshot, dict) and isinstance(
                        stable_auth_entry_path, str
                    ):
                        restore_path_state(
                            Path(stable_auth_entry_path), stable_auth_entry_snapshot
                        )
                    if isinstance(stable_auth_dir_snapshot, dict) and isinstance(
                        stable_auth_dir_path, str
                    ):
                        restore_rollout_stage_advance_inventory_dir_state(
                            Path(stable_auth_dir_path), stable_auth_dir_snapshot
                        )
            stage_advancement_result["rollback_outcome"] = "completed"
            stage_advancement_result["final_outcome"] = final_outcome
            return build_stage_advance_payload(
                ok=False,
                human_message=human_message,
                machine_error_code=machine_error_code,
                operator_action=operator_action,
                exit_code=exit_code,
                severity=severity,
            )
        except Exception as exc:  # noqa: BLE001
            stage_advancement_result["rollback_outcome"] = "failed"
            stage_advancement_result["final_outcome"] = "rollback_failed"
            stage_advancement_result["delegated_evidence"]["rollback_error"] = str(exc)
            return build_stage_advance_payload(
                ok=False,
                human_message=(
                    f"{human_message} Rollback of rollout advancement state failed."
                ),
                machine_error_code="STAGE_ADVANCE_ROLLBACK_FAILED",
                operator_action="stop",
                exit_code=1,
                severity="fatal",
            )

    requested_stage = stage_advancement_result["requested_stage"]
    requested_backend_id = stage_advancement_result["requested_backend_id"]
    stage_advance_config = {
        "15": {
            "source_stage": "10",
            "preflight_status_field": "preflight_stage10_proof_status",
            "already_target_outcome": "already_at_stage_15_target",
            "proof_failure_outcome": "stable_10_proof_failed",
        },
        "20": {
            "source_stage": "15",
            "preflight_status_field": "preflight_stage15_proof_status",
            "already_target_outcome": "already_at_stage_20_target",
            "proof_failure_outcome": "stable_15_proof_failed",
        },
    }
    config = stage_advance_config.get(requested_stage)
    if config is None:
        stage_advancement_result["final_outcome"] = "unsupported_target_stage"
        return build_stage_advance_payload(
            ok=False,
            human_message="Rollout stage advance supports only target stages 15 and 20.",
            machine_error_code="STAGE_ADVANCE_UNSUPPORTED_STAGE",
            operator_action="user_action",
        )
    source_stage = str(config["source_stage"])
    preflight_status_field = str(config["preflight_status_field"])
    already_target_outcome = str(config["already_target_outcome"])
    proof_failure_outcome = str(config["proof_failure_outcome"])
    if not requested_backend_id:
        stage_advancement_result["final_outcome"] = "backend_not_eligible"
        return build_stage_advance_payload(
            ok=False,
            human_message="Rollout stage advance requires an explicit backend id.",
            machine_error_code="STAGE_ADVANCE_BACKEND_ID_REQUIRED",
            operator_action="user_action",
        )

    stage_mapping = summarize_stage_pool_policy_mapping(requested_stage)
    stage_advancement_result["delegated_evidence"]["stage_mapping_summary"] = stage_mapping
    if stage_mapping.get("status") != "ok":
        stage_advancement_result["final_outcome"] = "invalid_stage_policy"
        return build_stage_advance_payload(
            ok=False,
            human_message="Rollout stage advance target is not canonically supported.",
            machine_error_code=str(
                stage_mapping.get("machine_error_code", "POOL_POLICY_STAGE_UNSUPPORTED")
            ),
            operator_action="user_action",
        )

    with serialized_lock(paths):
        composite_owner_lock_acquired = True
        registry = read_json(paths.registry_file)
        observed_stage = observe_current_stage_from_pool_policy(registry)
        stage_advancement_result["preflight_policy_status"] = str(
            observed_stage.get("status", "invalid")
        )
        stage_advancement_result["delegated_evidence"]["policy_stage_summary"] = observed_stage
        if observed_stage.get("status") != "matched":
            stage_advancement_result["final_outcome"] = "invalid_stage_policy"
            return build_stage_advance_payload(
                ok=False,
                human_message="Rollout stage advance is blocked because policy stage is not canonical.",
                machine_error_code="STAGE_ADVANCE_POLICY_STAGE_NOT_CANONICAL",
                operator_action="user_action",
            )

        current_stage = str(observed_stage.get("observed_stage", ""))
        desired_policy = STAGED_POOL_POLICY_PACKETS[requested_stage]
        pool_counts = summarize_registry_pool_counts(registry)
        active_count_before = int(pool_counts.get("active", 0) or 0)
        reserve_count_before = int(pool_counts.get("reserve", 0) or 0)
        active_target = int(desired_policy["active_target"])
        reserve_target = int(desired_policy["reserve_target"])
        target_already_satisfied = (
            current_stage == requested_stage
            and active_count_before == active_target
            and reserve_count_before == reserve_target
        )
        stage_advancement_result["delegated_evidence"]["pool_count_summary_before"] = {
            "active_count_observed": active_count_before,
            "reserve_count_observed": reserve_count_before,
            "active_target": active_target,
            "reserve_target": reserve_target,
        }

        if current_stage not in {source_stage, requested_stage}:
            stage_advancement_result["final_outcome"] = "invalid_stage_policy"
            return build_stage_advance_payload(
                ok=False,
                human_message=(
                    f"Rollout stage advance requires canonical source stage {source_stage} "
                    f"or in-progress stage {requested_stage}."
                ),
                machine_error_code="STAGE_ADVANCE_SOURCE_STAGE_UNSUPPORTED",
                operator_action="user_action",
            )

        backend_matches = get_registry_backends_by_id(registry, requested_backend_id)
        selected_backend = backend_matches[0] if len(backend_matches) == 1 else None
        selected_backend_auth_basename = (
            get_auth_basename(selected_backend.get("auth_ref"))
            if isinstance(selected_backend, dict)
            else None
        )
        backend_precondition_status = "eligible_reserve_backend"
        if not backend_matches:
            backend_precondition_status = "backend_missing"
        elif len(backend_matches) > 1:
            backend_precondition_status = "ambiguous_backend_id"
        elif bool(selected_backend.get("manual_hold", False)):
            backend_precondition_status = "backend_on_hold"
        elif str(selected_backend.get("pool", "")) == "retired":
            backend_precondition_status = "backend_retired"
        elif target_already_satisfied:
            backend_precondition_status = "valid_existing_backend"
        elif str(selected_backend.get("pool", "")) != "reserve":
            backend_precondition_status = "backend_not_reserve"
        stage_advancement_result["delegated_evidence"]["backend_precondition_summary"] = {
            "backend_id": requested_backend_id,
            "precondition_status": backend_precondition_status,
            "match_count": len(backend_matches),
            "observed_pool": (
                str(selected_backend.get("pool", ""))
                if isinstance(selected_backend, dict)
                else ""
            ),
            "observed_manual_hold": (
                bool(selected_backend.get("manual_hold", False))
                if isinstance(selected_backend, dict)
                else False
            ),
        }
        if backend_precondition_status not in {
            "eligible_reserve_backend",
            "valid_existing_backend",
        }:
            stage_advancement_result["final_outcome"] = "backend_not_eligible"
            return build_stage_advance_payload(
                ok=False,
                human_message="Rollout stage advance requires one explicit eligible reserve backend id.",
                machine_error_code="STAGE_ADVANCE_BACKEND_NOT_ELIGIBLE",
                operator_action="user_action",
            )

        if target_already_satisfied:
            stage_advancement_result["policy_transition_status"] = "already_on_stage"
            stage_advancement_result["promotion_status"] = "not_needed"
            stage_advancement_result["final_outcome"] = already_target_outcome
            return build_stage_advance_payload(
                ok=True,
                human_message=(
                    f"Rollout stage advance found canonical stage-{requested_stage} "
                    "target already satisfied."
                ),
                machine_error_code="OK",
            )

        step_snapshots: dict[str, dict[str, Any]] | None = None
        if current_stage == source_stage:
            step_snapshots = snapshot_promotion_owner_path_runtime_surfaces(paths)
            if selected_backend_auth_basename:
                stable_auth_dir, _ = get_stable_auth_inventory_source(paths)
                stable_auth_entry_path = stable_auth_dir / selected_backend_auth_basename
                extra_write_surfaces.append(stable_auth_entry_path)
                before_extra_states.setdefault(
                    stable_auth_entry_path, snapshot_path_state(stable_auth_entry_path)
                )
                if stable_auth_dir not in extra_write_surfaces:
                    extra_write_surfaces.append(stable_auth_dir)
                before_extra_states.setdefault(
                    stable_auth_dir, snapshot_path_state(stable_auth_dir)
                )
                step_snapshots["stable_auth_entry_file"] = snapshot_path_state(
                    stable_auth_entry_path
                )
                step_snapshots["stable_auth_entry_path"] = str(stable_auth_entry_path)
                step_snapshots["stable_auth_dir"] = snapshot_path_state(stable_auth_dir)
                step_snapshots["stable_auth_dir_path"] = str(stable_auth_dir)
            proof_payload = run_rollout_stage_prove(
                paths, source_stage, lock_acquired=True
            )
            proof_result = proof_payload.get("stage_proof_result", {})
            stage_advancement_result["delegated_evidence"][
                f"stable_{source_stage}_proof_summary"
            ] = {
                "status": proof_payload.get("status"),
                "machine_error_code": proof_payload.get("machine_error_code"),
                "exit_code": proof_payload.get("exit_code"),
                "proof_gate_status": proof_result.get("proof_gate_status"),
                "final_outcome": proof_result.get("final_outcome"),
            }
            if proof_payload.get("status") != "ok":
                if allow_stage_advance_source_proof_with_one_explicit_reserve_candidate(
                    proof_payload=proof_payload,
                    proof_result=proof_result,
                    source_stage=source_stage,
                    backend_precondition_status=backend_precondition_status,
                    active_count_before=active_count_before,
                    reserve_count_before=reserve_count_before,
                ):
                    stage_advancement_result["delegated_evidence"][
                        f"stable_{source_stage}_proof_summary"
                    ]["reserve_candidate_override_status"] = (
                        "accepted_single_explicit_reserve_candidate"
                    )
                else:
                    stage_advancement_result[preflight_status_field] = "failed"
                    return rollback_after_failed_step(
                        human_message=(
                            f"Rollout stage advance is blocked because stable-{source_stage} "
                            "proof is not satisfied."
                        ),
                        machine_error_code=str(
                            proof_payload.get(
                                "machine_error_code", "STAGE_ADVANCE_PROOF_FAILED"
                            )
                        ),
                        operator_action=str(
                            proof_payload.get("operator_action", "user_action")
                        ),
                        exit_code=int(proof_payload.get("exit_code", 1) or 1),
                        snapshots=step_snapshots,
                        final_outcome=proof_failure_outcome,
                    )
            stage_advancement_result[preflight_status_field] = "passed"

            policy_payload = run_policy_stage_set(
                paths, requested_stage, lock_acquired=True
            )
            policy_result = policy_payload.get("pool_policy_update_result", {})
            stage_advancement_result["delegated_evidence"]["policy_transition_summary"] = {
                "status": policy_payload.get("status"),
                "machine_error_code": policy_payload.get("machine_error_code"),
                "exit_code": policy_payload.get("exit_code"),
                "final_outcome": policy_result.get("final_outcome"),
            }
            if policy_payload.get("status") != "ok":
                stage_advancement_result["policy_transition_status"] = "failed"
                return rollback_after_failed_step(
                    human_message=(
                        "Rollout stage advance failed while updating policy stage to "
                        f"{requested_stage}."
                    ),
                    machine_error_code=str(
                        policy_payload.get(
                            "machine_error_code", "POOL_POLICY_UPDATE_FAILED"
                        )
                    ),
                    operator_action=str(policy_payload.get("operator_action", "retry")),
                    exit_code=int(policy_payload.get("exit_code", 1) or 1),
                    snapshots=step_snapshots,
                    final_outcome="policy_transition_failed",
                )
            stage_advancement_result["policy_transition_status"] = str(
                policy_result.get("final_outcome", "updated")
            )
        else:
            step_snapshots = snapshot_promotion_owner_path_runtime_surfaces(paths)
            if selected_backend_auth_basename:
                stable_auth_dir, _ = get_stable_auth_inventory_source(paths)
                stable_auth_entry_path = stable_auth_dir / selected_backend_auth_basename
                extra_write_surfaces.append(stable_auth_entry_path)
                before_extra_states.setdefault(
                    stable_auth_entry_path, snapshot_path_state(stable_auth_entry_path)
                )
                if stable_auth_dir not in extra_write_surfaces:
                    extra_write_surfaces.append(stable_auth_dir)
                before_extra_states.setdefault(
                    stable_auth_dir, snapshot_path_state(stable_auth_dir)
                )
                step_snapshots["stable_auth_entry_file"] = snapshot_path_state(
                    stable_auth_entry_path
                )
                step_snapshots["stable_auth_entry_path"] = str(stable_auth_entry_path)
                step_snapshots["stable_auth_dir"] = snapshot_path_state(stable_auth_dir)
                step_snapshots["stable_auth_dir_path"] = str(stable_auth_dir)
            preflight_ok, preflight_code, preflight_action, preflight_summary = (
                summarize_rollout_stage_advance_preflight(paths, lock_acquired=True)
            )
            stage_advancement_result["delegated_evidence"][
                "preflight_summary"
            ] = preflight_summary
            if not preflight_ok:
                stage_advancement_result[preflight_status_field] = "not_required"
                stage_advancement_result["postflight_attestation_status"] = str(
                    preflight_summary.get("attestation_status", "failed")
                )
                stage_advancement_result["postflight_rotation_status"] = str(
                    preflight_summary.get("rotation_status", "unknown")
                )
                stage_advancement_result["rollback_readiness_status"] = str(
                    preflight_summary.get("readiness_status", "failed")
                )
                return rollback_after_failed_step(
                    human_message=(
                        "Rollout stage advance is blocked because current "
                        f"stage-{requested_stage} rollout posture fails bounded "
                        "preflight verification."
                    ),
                    machine_error_code=preflight_code,
                    operator_action=preflight_action,
                    snapshots=step_snapshots,
                    final_outcome="preflight_verification_failed",
                )
            stage_advancement_result[preflight_status_field] = "not_required"
            stage_advancement_result["policy_transition_status"] = "already_on_stage"

        promote_payload = run_promote(
            paths, requested_backend_id, lock_acquired=True
        )
        promote_result = promote_payload.get("promotion_result", {})
        stage_advancement_result["delegated_evidence"]["promotion_summary"] = {
            "status": promote_payload.get("status"),
            "machine_error_code": promote_payload.get("machine_error_code"),
            "exit_code": promote_payload.get("exit_code"),
            "precondition_status": promote_result.get("precondition_status"),
            "final_outcome": promote_result.get("final_outcome"),
        }
        if promote_payload.get("status") != "ok":
            stage_advancement_result["promotion_status"] = "failed"
            return rollback_after_failed_step(
                human_message="Rollout stage advance failed while promoting the explicit backend id.",
                machine_error_code=str(
                    promote_payload.get("machine_error_code", "PROMOTION_FAILED")
                ),
                operator_action=str(promote_payload.get("operator_action", "user_action")),
                exit_code=int(promote_payload.get("exit_code", 1) or 1),
                snapshots=step_snapshots,
            )
        stage_advancement_result["promotion_status"] = "promoted"
        updated_registry = read_json(paths.registry_file)
        promoted_backend_matches = get_registry_backends_by_id(
            updated_registry, requested_backend_id
        )
        promoted_backend = (
            promoted_backend_matches[0] if len(promoted_backend_matches) == 1 else None
        )
        if not isinstance(promoted_backend, dict):
            return rollback_after_failed_step(
                human_message=(
                    "Rollout stage advance could not verify a uniquely identifiable promoted backend before stable inventory materialization."
                ),
                machine_error_code="STAGE_ADVANCE_POSTFLIGHT_PROMOTION_FAILED",
                operator_action="user_action",
                snapshots=step_snapshots,
            )
        try:
            stable_auth_materialization = materialize_rollout_stage_advance_stable_auth(
                paths, promoted_backend
            )
        except RuntimeErrorInfo as exc:
            stage_advancement_result["delegated_evidence"][
                "stable_auth_materialization_summary"
            ] = {
                "status": "failed",
                "machine_error_code": exc.machine_error_code,
                "operator_action": exc.operator_action,
            }
            return rollback_after_failed_step(
                human_message=(
                    "Rollout stage advance failed while materializing the promoted backend into stable auth inventory."
                ),
                machine_error_code=exc.machine_error_code,
                operator_action=exc.operator_action,
                exit_code=exc.exit_code,
                snapshots=step_snapshots,
            )
        stage_advancement_result["delegated_evidence"][
            "stable_auth_materialization_summary"
        ] = {
            "status": "materialized",
            "machine_error_code": "OK",
            **stable_auth_materialization,
        }

        postflight_ok, postflight_code, postflight_action, postflight_summary = (
            summarize_rollout_stage_advance_postflight(
                paths,
                expected_stage=requested_stage,
                backend_id=requested_backend_id,
                active_pool_count_before=active_count_before,
                lock_acquired=True,
            )
        )
        stage_advancement_result["postflight_attestation_status"] = str(
            postflight_summary.get("attestation_status", "failed")
        )
        stage_advancement_result["postflight_rotation_status"] = str(
            postflight_summary.get("rotation_status", "unknown")
        )
        stage_advancement_result["rollback_readiness_status"] = str(
            postflight_summary.get("readiness_status", "failed")
        )
        stage_advancement_result["delegated_evidence"][
            "postflight_summary"
        ] = postflight_summary
        if not postflight_ok:
            return rollback_after_failed_step(
                human_message=(
                    "Rollout stage advance step completed, but postflight checks detected a contradiction or readiness gap."
                ),
                machine_error_code=postflight_code,
                operator_action=postflight_action,
                snapshots=step_snapshots,
            )

        updated_registry = read_json(paths.registry_file)
        updated_counts = summarize_registry_pool_counts(updated_registry)
        stage_advancement_result["delegated_evidence"][
            "pool_count_summary_after_step"
        ] = {
            "active_count_observed": int(updated_counts.get("active", 0) or 0),
            "reserve_count_observed": int(updated_counts.get("reserve", 0) or 0),
            "active_target": STAGED_POOL_POLICY_PACKETS[requested_stage]["active_target"],
            "reserve_target": STAGED_POOL_POLICY_PACKETS[requested_stage]["reserve_target"],
        }
        stage_advancement_result["rollback_outcome"] = "not_needed"
        stage_advancement_result["final_outcome"] = "advanced_one_step"
        return build_stage_advance_payload(
            ok=True,
            human_message=(
                "Rollout stage advance completed one controlled promotion step "
                f"toward canonical stage {requested_stage}."
            ),
            machine_error_code="OK",
        )


def run_policy_stage_set(
    paths: RuntimePaths,
    stage: str,
    *,
    lock_acquired: bool = False,
) -> dict[str, Any]:
    before = snapshot_known_files(paths)
    policy_update_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "requested_stage": str(stage).strip(),
        "mapped_pool_policy": None,
        "previous_pool_policy": None,
        "next_pool_policy": None,
        "policy_validation_status": "pending",
        "stage_mapping_status": "pending",
        "rollback_point_captured": False,
        "write_attempted": False,
        "write_observed": False,
        "rollback_attempted": False,
        "rollback_outcome": "not_attempted",
        "final_outcome": "pending_preconditions",
    }

    def build_policy_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        operator_action: str = "none",
        severity: str = "recoverable",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_extra = {
            "requested_stage": policy_update_result["requested_stage"],
            "pool_policy_update_result": policy_update_result,
        }
        if extra:
            payload_extra.update(extra)
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness="unknown",
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(before, [paths.registry_file]),
            extra=payload_extra,
            exit_code=exit_code,
        )

    mutation_lock = nullcontext() if lock_acquired else serialized_lock(paths)
    with mutation_lock:
        registry = read_json(paths.registry_file)
        current_pool_policy = registry.get("pool_policy")
        policy_update_result["previous_pool_policy"] = current_pool_policy
        policy_summary = summarize_promotion_pool_policy(registry)
        policy_update_result["policy_validation_status"] = str(
            policy_summary.get("status", "invalid")
        )
        if policy_summary.get("status") != "ok":
            policy_update_result["final_outcome"] = "policy_invalid"
            return build_policy_payload(
                ok=False,
                human_message="Stage policy update blocked because the current pool policy is invalid.",
                machine_error_code=str(
                    policy_summary.get("machine_error_code", "POOL_POLICY_INVALID")
                ),
                operator_action="user_action",
            )

        stage_mapping = summarize_stage_pool_policy_mapping(stage)
        policy_update_result["requested_stage"] = str(
            stage_mapping.get("requested_stage", policy_update_result["requested_stage"])
        )
        policy_update_result["stage_mapping_status"] = str(
            stage_mapping.get("status", "unsupported")
        )
        if stage_mapping.get("status") != "ok":
            policy_update_result["final_outcome"] = "unsupported_stage"
            return build_policy_payload(
                ok=False,
                human_message="Requested stage is not supported by the canonical staged policy sequence.",
                machine_error_code=str(
                    stage_mapping.get(
                        "machine_error_code", "POOL_POLICY_STAGE_UNSUPPORTED"
                    )
                ),
                operator_action="user_action",
            )

        desired_policy = dict(stage_mapping["mapped_pool_policy"])
        policy_update_result["mapped_pool_policy"] = dict(desired_policy)
        next_pool_policy = dict(current_pool_policy)
        next_pool_policy.update(desired_policy)
        policy_update_result["next_pool_policy"] = next_pool_policy

        if pool_policy_matches_stage_packet(current_pool_policy, desired_policy):
            policy_update_result["rollback_outcome"] = "not_needed"
            policy_update_result["final_outcome"] = "already_on_stage"
            return build_policy_payload(
                ok=True,
                human_message=(
                    f"Pool policy already matches canonical stage {policy_update_result['requested_stage']}."
                ),
                machine_error_code="OK",
            )

        registry_snapshot = snapshot_path_state(paths.registry_file)
        policy_update_result["rollback_point_captured"] = True
        try:
            updated_registry = dict(registry)
            updated_registry["pool_policy"] = next_pool_policy
            updated_registry["updated_at"] = now_iso()
            policy_update_result["write_attempted"] = True
            write_json_atomic(paths.registry_file, updated_registry)

            observed_registry = read_json(paths.registry_file)
            observed_pool_policy = observed_registry.get("pool_policy")
            policy_update_result["write_observed"] = observed_pool_policy == next_pool_policy
            observed_summary = summarize_promotion_pool_policy(observed_registry)
            if (
                observed_summary.get("status") != "ok"
                or observed_pool_policy != next_pool_policy
                or not pool_policy_matches_stage_packet(observed_pool_policy, desired_policy)
            ):
                raise RuntimeErrorInfo(
                    "Pool policy verification failed after stage update.",
                    machine_error_code="POOL_POLICY_UPDATE_FAILED",
                    severity="recoverable",
                    operator_action="retry",
                )
        except Exception as exc:  # noqa: BLE001
            policy_update_result["rollback_attempted"] = True
            try:
                restore_path_state(paths.registry_file, registry_snapshot)
                policy_update_result["rollback_outcome"] = "completed"
                policy_update_result["final_outcome"] = (
                    "rollback_completed_after_failed_verification"
                )
                error_code = (
                    exc.machine_error_code
                    if isinstance(exc, RuntimeErrorInfo)
                    else "POOL_POLICY_UPDATE_FAILED"
                )
                return build_policy_payload(
                    ok=False,
                    human_message=(
                        "Stage policy update failed verification and previous pool policy was restored."
                    ),
                    machine_error_code=str(error_code),
                    operator_action=(
                        exc.operator_action
                        if isinstance(exc, RuntimeErrorInfo)
                        else "retry"
                    ),
                    extra={"update_error": str(exc)}
                    if not isinstance(exc, RuntimeErrorInfo)
                    else None,
                )
            except Exception as rollback_exc:  # noqa: BLE001
                policy_update_result["rollback_outcome"] = "failed"
                policy_update_result["final_outcome"] = "rollback_failed"
                return build_policy_payload(
                    ok=False,
                    human_message=(
                        "Stage policy update failed verification and rollback of the previous pool policy failed."
                    ),
                    machine_error_code="POOL_POLICY_UPDATE_ROLLBACK_FAILED",
                    operator_action="stop",
                    severity="fatal",
                    extra={
                        "update_error": str(exc),
                        "rollback_error": str(rollback_exc),
                    },
                )

    policy_update_result["rollback_outcome"] = "not_needed"
    policy_update_result["final_outcome"] = "stage_policy_updated"
    return build_policy_payload(
        ok=True,
        human_message=(
            f"Pool policy updated to canonical stage {policy_update_result['requested_stage']}."
        ),
        machine_error_code="OK",
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


def selected_backend_ids_from_state(state: dict[str, Any]) -> list[str]:
    return sorted(str(item) for item in state.get("selected_backend_ids", []) or [])


def run_sync_for_owner_path_under_lock(paths: RuntimePaths) -> dict[str, Any]:
    if not paths.sync_script.exists():
        raise RuntimeErrorInfo(
            f"Missing sync script: {paths.sync_script}",
            machine_error_code="MISSING_SYNC_SCRIPT",
            operator_action="user_action",
        )
    sync_result = subprocess.run(
        [str(paths.sync_script), get_model(paths)],
        capture_output=True,
        text=True,
        env=sanitized_env(),
        check=False,
    )
    emit_subprocess_output(stdout=sync_result.stdout, stderr=sync_result.stderr)
    sync_state = read_json(paths.state_file, required=False)
    sync_effective_mode = get_effective_mode(paths, sync_state)
    sync_host, sync_port, _ = get_endpoint(paths, sync_effective_mode)
    sync_listener_ok = socket_is_listening(sync_host, sync_port)
    sync_reported_effective_mode = reconcile_effective_mode_for_reporting(
        sync_effective_mode, listener_ok=sync_listener_ok
    )
    _, _, sync_reported_endpoint = get_endpoint(paths, sync_reported_effective_mode)
    if sync_result.returncode != 0:
        return {
            "status": "error",
            "machine_error_code": "SYNC_FAILED",
            "exit_code": sync_result.returncode,
            "liveness": "down" if not sync_listener_ok else "degraded",
            "operator_action": "retry",
            "effective_mode": sync_reported_effective_mode,
            "endpoint": sync_reported_endpoint,
        }
    if not sync_listener_ok:
        return {
            "status": "error",
            "machine_error_code": "SYNC_HEALTHCHECK_FAILED",
            "exit_code": 1,
            "liveness": "down",
            "operator_action": "retry",
            "effective_mode": sync_reported_effective_mode,
            "endpoint": sync_reported_endpoint,
        }
    return {
        "status": "ok",
        "machine_error_code": "OK",
        "exit_code": 0,
        "liveness": "healthy",
        "operator_action": "none",
        "effective_mode": sync_reported_effective_mode,
        "endpoint": sync_reported_endpoint,
    }


def attempt_sync_current_proxy_recovery_under_lock(
    paths: RuntimePaths,
    *,
    working_candidate: str,
    prior_current_proxy_url: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rollback_surface_snapshots = snapshot_sync_current_proxy_recovery_runtime_surfaces(
        paths
    )
    result = {
        "status": "owner_path_emitted",
        "attempted": True,
        "working_candidate": working_candidate,
        "activation_surface_kind": "sync_owner_path_restart",
        "activation_command_surface": "sync --json",
        "adoption_outcome": "sync_owner_path_failed",
        "current_proxy_url_rewritten": False,
        "live_runtime_observation_confirmed": False,
        "sync_result_status": "not_run",
        "sync_result_machine_error_code": "",
        "sync_result_exit_code": None,
        "selected_proxy_url": "",
        "rollback_restored": False,
    }
    sync_payload = run_sync_for_owner_path_under_lock(paths)
    result["sync_result_status"] = str(sync_payload["status"])
    result["sync_result_machine_error_code"] = str(
        sync_payload["machine_error_code"]
    )
    result["sync_result_exit_code"] = sync_payload["exit_code"]
    if sync_payload["status"] != "ok":
        restore_sync_current_proxy_recovery_runtime_surfaces(
            paths, rollback_surface_snapshots
        )
        result["rollback_restored"] = True
        return result, None
    reproof_payload = run_healthcheck(
        paths,
        allow_recovery=False,
        allow_last_known_good_proxy_write=False,
        allow_current_proxy_auto_adoption=False,
    )
    reproof_ok = (
        reproof_payload["status"] == "ok"
        and str(reproof_payload["effective_mode"]) == "managed"
    )
    state = read_json(paths.state_file, required=False)
    reproof_current_proxy_url = str(state.get("current_proxy_url", ""))
    result["selected_proxy_url"] = reproof_current_proxy_url
    same_current_reconfirmed = (
        prior_current_proxy_url == working_candidate
        and reproof_ok
        and reproof_current_proxy_url == working_candidate
    )
    candidate_adopted = (
        prior_current_proxy_url != working_candidate
        and reproof_ok
        and reproof_current_proxy_url == working_candidate
    )
    if same_current_reconfirmed or candidate_adopted:
        if same_current_reconfirmed:
            result["adoption_outcome"] = "sync_owner_path_same_current_reconfirmed"
        else:
            result["adoption_outcome"] = "sync_owner_path_candidate_adopted"
        result["current_proxy_url_rewritten"] = (
            reproof_current_proxy_url != prior_current_proxy_url
        )
        result["live_runtime_observation_confirmed"] = True
        return result, reproof_payload
    restore_sync_current_proxy_recovery_runtime_surfaces(
        paths, rollback_surface_snapshots
    )
    result["rollback_restored"] = True
    result["adoption_outcome"] = "sync_owner_path_live_reproof_failed"
    return result, None


def observe_status_proof_for_owner_path_under_lock(
    paths: RuntimePaths,
) -> tuple[dict[str, Any], dict[str, Any]]:
    health_payload = run_healthcheck(
        paths,
        allow_recovery=False,
        allow_last_known_good_proxy_write=False,
        allow_current_proxy_auto_adoption=False,
    )
    status_payload = summarize_status(paths, health_payload=health_payload)
    return status_payload, summarize_owner_path_status_observation(status_payload)


def run_hold(paths: RuntimePaths, backend_id: str, reason: str | None) -> dict[str, Any]:
    return run_protective_lifecycle_owner_path(
        paths,
        backend_id,
        action="hold",
        reason=reason,
    )


def run_release(paths: RuntimePaths, backend_id: str) -> dict[str, Any]:
    return run_protective_lifecycle_owner_path(paths, backend_id, action="release")


def run_demote(paths: RuntimePaths, backend_id: str) -> dict[str, Any]:
    if not paths.accounts_bin.exists():
        raise RuntimeErrorInfo(
            f"Missing accounts command: {paths.accounts_bin}",
            machine_error_code="MISSING_ACCOUNTS_BIN",
            operator_action="user_action",
        )

    before = snapshot_known_files(paths)
    command = ["demote", backend_id]
    demote_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "backend_id": backend_id,
        "precondition_status": "pending",
        "previous_pool": "",
        "previous_manual_hold": False,
        "requested_transition": "demote_to_reserve",
        "rollback_point_captured": False,
        "routing_change_attempted": False,
        "routing_change_observed": False,
        "sync_attempted": False,
        "sync_outcome": "not_attempted",
        "status_observed": None,
        "rollback_attempted": False,
        "rollback_outcome": "not_attempted",
        "external_command_exit_code": None,
        "external_command_status": "not_invoked",
        "reserve_return_confirmed": False,
        "final_outcome": "pending_preconditions",
    }

    def build_demote_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        liveness: str = "unknown",
        severity: str = "recoverable",
        operator_action: str = "none",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_extra = {
            "command": command,
            "demote_result": demote_result,
        }
        if extra:
            payload_extra.update(extra)
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness=liveness,
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra=payload_extra,
            exit_code=exit_code,
        )

    with serialized_lock(paths):
        before_registry = read_json(paths.registry_file)
        before_state = read_json(paths.state_file, required=False)
        before_routing_ids = routing_eligible_active_backend_ids(before_registry)
        before_selected_backend_ids = selected_backend_ids_from_state(before_state)
        backend_matches = get_registry_backends_by_id(before_registry, backend_id)
        selected_backend = backend_matches[0] if len(backend_matches) == 1 else None
        previous_pool = (
            str(selected_backend.get("pool")) if isinstance(selected_backend, dict) else ""
        )
        previous_manual_hold = bool(
            selected_backend.get("manual_hold", False)
            if isinstance(selected_backend, dict)
            else False
        )
        demote_result["previous_pool"] = previous_pool
        demote_result["previous_manual_hold"] = previous_manual_hold

        def rollback_after_failed_verification(
            *,
            human_message: str,
            machine_error_code: str,
            liveness: str,
            operator_action: str,
            exit_code: int | None,
            extra: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            demote_result["rollback_attempted"] = True
            try:
                restore_lifecycle_owner_path_runtime_surfaces(paths, rollback_snapshots)
                demote_result["rollback_outcome"] = "completed"
                demote_result["final_outcome"] = (
                    "rollback_completed_after_failed_verification"
                )
                return build_demote_payload(
                    ok=False,
                    human_message=human_message,
                    machine_error_code=machine_error_code,
                    liveness=liveness,
                    severity="recoverable",
                    operator_action=operator_action,
                    exit_code=exit_code,
                    extra=extra,
                )
            except Exception as exc:  # noqa: BLE001
                demote_result["rollback_outcome"] = "failed"
                demote_result["final_outcome"] = "rollback_failed"
                payload_extra = dict(extra or {})
                payload_extra["rollback_error"] = str(exc)
                return build_demote_payload(
                    ok=False,
                    human_message=f"{human_message} Rollback of control-layer demotion state failed.",
                    machine_error_code="DEMOTE_ROLLBACK_FAILED",
                    liveness=liveness,
                    severity="fatal",
                    operator_action="stop",
                    exit_code=1,
                    extra=payload_extra,
                )

        if not backend_matches:
            demote_result["precondition_status"] = "backend_missing"
            demote_result["final_outcome"] = "precondition_failed"
            return build_demote_payload(
                ok=False,
                human_message="Demotion target backend does not exist.",
                machine_error_code="DEMOTE_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if len(backend_matches) > 1:
            demote_result["precondition_status"] = "ambiguous_backend_id"
            demote_result["final_outcome"] = "precondition_failed"
            return build_demote_payload(
                ok=False,
                human_message="Demotion target backend is ambiguous.",
                machine_error_code="DEMOTE_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if previous_manual_hold:
            demote_result["precondition_status"] = "backend_held"
            demote_result["final_outcome"] = "precondition_failed"
            return build_demote_payload(
                ok=False,
                human_message="Held backend must use release, not demote.",
                machine_error_code="DEMOTE_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if previous_pool == "retired":
            demote_result["precondition_status"] = "backend_retired"
            demote_result["final_outcome"] = "precondition_failed"
            return build_demote_payload(
                ok=False,
                human_message="Retired backend is not eligible for demotion.",
                machine_error_code="DEMOTE_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if previous_pool == "reserve":
            demote_result["precondition_status"] = "already_reserve"
            demote_result["reserve_return_confirmed"] = bool(
                backend_id not in set(before_routing_ids)
                and backend_id not in set(before_selected_backend_ids)
            )
            if not demote_result["reserve_return_confirmed"]:
                demote_result["final_outcome"] = "precondition_failed"
                return build_demote_payload(
                    ok=False,
                    human_message="Reserve backend does not satisfy reserve-only routing proof.",
                    machine_error_code="DEMOTE_STATUS_FAILED",
                    operator_action="user_action",
                )
            demote_result["rollback_outcome"] = "not_needed"
            demote_result["final_outcome"] = "already_reserve"
            return build_demote_payload(
                ok=True,
                human_message="Backend is already reserve with reserve-only routing proof.",
                machine_error_code="OK",
                operator_action="none",
            )

        if previous_pool != "active":
            demote_result["precondition_status"] = "backend_not_active"
            demote_result["final_outcome"] = "precondition_failed"
            return build_demote_payload(
                ok=False,
                human_message="Only active backends are eligible for demotion.",
                machine_error_code="DEMOTE_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        demote_result["precondition_status"] = "eligible_active_backend_for_demote"
        rollback_snapshots = snapshot_lifecycle_owner_path_runtime_surfaces(paths)
        demote_result["rollback_point_captured"] = True
        try:
            result = subprocess.run(
                [str(paths.accounts_bin), *command],
                capture_output=True,
                text=True,
                env=sanitized_env(),
                check=False,
            )
        except OSError as exc:
            demote_result["external_command_status"] = "exec_error"
            demote_result["final_outcome"] = "demote_command_failed"
            return build_demote_payload(
                ok=False,
                human_message="Demotion command could not be executed.",
                machine_error_code="DEMOTE_COMMAND_EXEC_FAILED",
                operator_action="user_action",
                exit_code=1,
                extra={"command_error": str(exc)},
            )
        emit_subprocess_output(stdout=result.stdout, stderr=result.stderr)
        demote_result["external_command_exit_code"] = int(result.returncode)
        demote_result["external_command_status"] = (
            "ok" if result.returncode == 0 else "nonzero"
        )

        try:
            after_command_registry = read_json(paths.registry_file)
            after_command_state = read_json(paths.state_file, required=False)
        except Exception as exc:  # noqa: BLE001
            demote_result["final_outcome"] = "demote_command_failed"
            return rollback_after_failed_verification(
                human_message=(
                    "Demotion command left unreadable control-layer state."
                ),
                machine_error_code="DEMOTE_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
                extra={"command_error": str(exc)},
            )

        after_command_matches = get_registry_backends_by_id(
            after_command_registry, backend_id
        )
        after_command_backend = (
            after_command_matches[0] if len(after_command_matches) == 1 else None
        )
        after_routing_ids = routing_eligible_active_backend_ids(after_command_registry)
        after_selected_backend_ids = selected_backend_ids_from_state(after_command_state)
        after_command_pool = (
            str(after_command_backend.get("pool", ""))
            if isinstance(after_command_backend, dict)
            else ""
        )
        demote_result["routing_change_attempted"] = bool(
            before_routing_ids != after_routing_ids
            or before_selected_backend_ids != after_selected_backend_ids
            or (previous_pool == "active" and after_command_pool != "active")
            or (previous_pool != "active" and after_command_pool == "active")
        )

        def fail_after_command(
            *,
            human_message: str,
            machine_error_code: str,
            liveness: str,
            operator_action: str,
            exit_code: int | None,
            extra: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return rollback_after_failed_verification(
                human_message=human_message,
                machine_error_code=machine_error_code,
                liveness=liveness,
                operator_action=operator_action,
                exit_code=exit_code,
                extra=extra,
            )

        if len(after_command_matches) != 1:
            demote_result["final_outcome"] = "demote_command_failed"
            return fail_after_command(
                human_message=(
                    "Demotion did not leave a uniquely identifiable backend state."
                ),
                machine_error_code="DEMOTE_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        after_command_hold = bool(after_command_backend.get("manual_hold", False))
        lifecycle_verified = not after_command_hold and after_command_pool == "reserve"
        if not lifecycle_verified:
            demote_result["final_outcome"] = "demote_command_failed"
            return fail_after_command(
                human_message="Demotion command did not return the backend to reserve.",
                machine_error_code="DEMOTE_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )
        if not demote_result["routing_change_attempted"]:
            demote_result["reserve_return_confirmed"] = bool(
                backend_id not in set(after_routing_ids)
                and backend_id not in set(after_selected_backend_ids)
            )

        sync_payload: dict[str, Any] | None = None
        status_payload: dict[str, Any] | None = None
        if demote_result["routing_change_attempted"]:
            demote_result["sync_attempted"] = True
            try:
                sync_payload = run_sync_for_owner_path_under_lock(paths)
                demote_result["sync_outcome"] = (
                    "ok" if sync_payload["status"] == "ok" else "failed"
                )
                if sync_payload["status"] != "ok":
                    return rollback_after_failed_verification(
                        human_message=(
                            "Demotion changed routing inputs, but managed sync verification failed."
                        ),
                        machine_error_code="DEMOTE_SYNC_FAILED",
                        liveness=str(sync_payload.get("liveness", "unknown")),
                        operator_action=str(
                            sync_payload.get("operator_action", "retry")
                        ),
                        exit_code=int(sync_payload.get("exit_code", 1) or 1),
                        extra={
                            "sync_result": {
                                "command_status": sync_payload["status"],
                                "machine_error_code": sync_payload["machine_error_code"],
                                "exit_code": sync_payload["exit_code"],
                            }
                        },
                    )

                status_payload, status_observed = (
                    observe_status_proof_for_owner_path_under_lock(paths)
                )
                demote_result["status_observed"] = status_observed
                verified_registry = read_json(paths.registry_file)
                verified_state = read_json(paths.state_file, required=False)
                verified_matches = get_registry_backends_by_id(
                    verified_registry, backend_id
                )
                verified_backend = (
                    verified_matches[0] if len(verified_matches) == 1 else None
                )
                verified_selected_backend_ids = set(
                    selected_backend_ids_from_state(verified_state)
                )
                verified_routing_ids = set(
                    routing_eligible_active_backend_ids(verified_registry)
                )
                demote_result["routing_change_observed"] = bool(
                    status_payload["status"] == "ok"
                    and isinstance(verified_backend, dict)
                    and not bool(verified_backend.get("manual_hold", False))
                    and str(verified_backend.get("pool", "")) == "reserve"
                    and backend_id not in verified_routing_ids
                    and backend_id not in verified_selected_backend_ids
                )
                demote_result["reserve_return_confirmed"] = demote_result[
                    "routing_change_observed"
                ]
                if (
                    status_payload["status"] != "ok"
                    or not demote_result["routing_change_observed"]
                ):
                    return rollback_after_failed_verification(
                        human_message=(
                            "Demotion did not produce verified reserve-only routing removal after status proof."
                        ),
                        machine_error_code="DEMOTE_STATUS_FAILED",
                        liveness=str(status_payload.get("liveness", "unknown")),
                        operator_action=str(
                            status_payload.get("operator_action", "retry")
                        ),
                        exit_code=int(status_payload.get("exit_code", 1) or 1),
                        extra={
                            "sync_result": {
                                "command_status": sync_payload["status"],
                                "machine_error_code": sync_payload["machine_error_code"],
                                "exit_code": sync_payload["exit_code"],
                            }
                        },
                    )
            except RuntimeErrorInfo as exc:
                return rollback_after_failed_verification(
                    human_message=(
                        "Demotion post-command verification raised a runtime error."
                    ),
                    machine_error_code="DEMOTE_SYNC_FAILED",
                    liveness="unknown",
                    operator_action=exc.operator_action,
                    exit_code=exc.exit_code,
                    extra={"verification_error": str(exc)},
                )
            except Exception as exc:  # noqa: BLE001
                return rollback_after_failed_verification(
                    human_message=(
                        "Demotion post-command verification raised an unexpected error."
                    ),
                    machine_error_code="DEMOTE_STATUS_FAILED",
                    liveness="unknown",
                    operator_action="retry",
                    exit_code=1,
                    extra={"verification_error": str(exc)},
                )

        demote_result["rollback_outcome"] = "not_needed"
        demote_result["final_outcome"] = "backend_demoted_to_reserve"
        success_extra: dict[str, Any] = {}
        if sync_payload is not None:
            success_extra["sync_result"] = {
                "command_status": sync_payload["status"],
                "machine_error_code": sync_payload["machine_error_code"],
                "exit_code": sync_payload["exit_code"],
            }
        return build_demote_payload(
            ok=True,
            human_message=(
                "Account demotion completed with rollback-safe reserve-only proof."
                if result.returncode == 0 and demote_result["routing_change_attempted"]
                else "Account demotion completed."
                if result.returncode == 0
                else "Account demotion completed with reserve-only proof after external demote exit non-zero."
            ),
            machine_error_code="OK",
            liveness=(
                str(status_payload.get("liveness", "unknown"))
                if status_payload is not None
                else "unknown"
            ),
            severity="recoverable",
            operator_action="none",
            extra=success_extra or None,
        )

def run_retire(paths: RuntimePaths, backend_id: str) -> dict[str, Any]:
    if not paths.accounts_bin.exists():
        raise RuntimeErrorInfo(
            f"Missing accounts command: {paths.accounts_bin}",
            machine_error_code="MISSING_ACCOUNTS_BIN",
            operator_action="user_action",
        )

    before = snapshot_known_files(paths)
    before_registry = read_json(paths.registry_file)
    before_state = read_json(paths.state_file, required=False)
    before_routing_ids = routing_eligible_active_backend_ids(before_registry)
    before_selected_backend_ids = selected_backend_ids_from_state(before_state)
    command = ["retire", backend_id]
    backend_matches = get_registry_backends_by_id(before_registry, backend_id)
    selected_backend = backend_matches[0] if len(backend_matches) == 1 else None
    previous_pool = (
        str(selected_backend.get("pool")) if isinstance(selected_backend, dict) else ""
    )
    previous_manual_hold = bool(
        selected_backend.get("manual_hold", False)
        if isinstance(selected_backend, dict)
        else False
    )
    retire_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "backend_id": backend_id,
        "precondition_status": "pending",
        "previous_pool": previous_pool,
        "previous_manual_hold": previous_manual_hold,
        "requested_transition": "retire_terminal",
        "rollback_point_captured": False,
        "routing_change_attempted": False,
        "routing_change_observed": False,
        "sync_attempted": False,
        "sync_outcome": "not_attempted",
        "status_observed": None,
        "rollback_attempted": False,
        "rollback_outcome": "not_attempted",
        "external_command_exit_code": None,
        "external_command_status": "not_invoked",
        "terminal_no_return_confirmed": False,
        "final_outcome": "pending_preconditions",
    }

    def build_retire_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        liveness: str = "unknown",
        severity: str = "recoverable",
        operator_action: str = "none",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_extra = {
            "command": command,
            "retire_result": retire_result,
        }
        if extra:
            payload_extra.update(extra)
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness=liveness,
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra=payload_extra,
            exit_code=exit_code,
        )

    def rollback_after_failed_verification(
        *,
        human_message: str,
        machine_error_code: str,
        liveness: str,
        operator_action: str,
        exit_code: int | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        retire_result["rollback_attempted"] = True
        try:
            restore_lifecycle_owner_path_runtime_surfaces(paths, rollback_snapshots)
            retire_result["rollback_outcome"] = "completed"
            retire_result["final_outcome"] = (
                "rollback_completed_after_failed_verification"
            )
            return build_retire_payload(
                ok=False,
                human_message=human_message,
                machine_error_code=machine_error_code,
                liveness=liveness,
                severity="recoverable",
                operator_action=operator_action,
                exit_code=exit_code,
                extra=extra,
            )
        except Exception as exc:  # noqa: BLE001
            retire_result["rollback_outcome"] = "failed"
            retire_result["final_outcome"] = "rollback_failed"
            payload_extra = dict(extra or {})
            payload_extra["rollback_error"] = str(exc)
            return build_retire_payload(
                ok=False,
                human_message=(
                    f"{human_message} Rollback of control-layer retirement state failed."
                ),
                machine_error_code="RETIRE_ROLLBACK_FAILED",
                liveness=liveness,
                severity="fatal",
                operator_action="stop",
                exit_code=1,
                extra=payload_extra,
            )

    if not backend_matches:
        retire_result["precondition_status"] = "backend_missing"
        retire_result["final_outcome"] = "precondition_failed"
        return build_retire_payload(
            ok=False,
            human_message="Retirement target backend does not exist.",
            machine_error_code="RETIRE_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    if len(backend_matches) > 1:
        retire_result["precondition_status"] = "ambiguous_backend_id"
        retire_result["final_outcome"] = "precondition_failed"
        return build_retire_payload(
            ok=False,
            human_message="Retirement target backend is ambiguous.",
            machine_error_code="RETIRE_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    if previous_pool == "retired":
        retire_result["precondition_status"] = "already_retired"
        retire_result["terminal_no_return_confirmed"] = bool(
            backend_id not in set(before_routing_ids)
            and backend_id not in set(before_selected_backend_ids)
            and not previous_manual_hold
        )
        if not retire_result["terminal_no_return_confirmed"]:
            retire_result["final_outcome"] = "precondition_failed"
            return build_retire_payload(
                ok=False,
                human_message="Retired backend does not satisfy terminal no-return proof.",
                machine_error_code="RETIRE_STATUS_FAILED",
                operator_action="user_action",
            )
        retire_result["final_outcome"] = "already_retired"
        retire_result["rollback_outcome"] = "not_needed"
        return build_retire_payload(
            ok=True,
            human_message="Backend is already retired with terminal no-return proof.",
            machine_error_code="OK",
            operator_action="none",
        )

    if previous_pool not in {"active", "reserve"}:
        retire_result["precondition_status"] = "backend_not_retirable_pool"
        retire_result["final_outcome"] = "precondition_failed"
        return build_retire_payload(
            ok=False,
            human_message="Only active or reserve backends are eligible for retirement.",
            machine_error_code="RETIRE_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    retire_result["precondition_status"] = (
        "eligible_active_backend_for_retire"
        if previous_pool == "active"
        else "eligible_reserve_backend_for_retire"
    )

    with serialized_lock(paths):
        rollback_snapshots = snapshot_lifecycle_owner_path_runtime_surfaces(paths)
        retire_result["rollback_point_captured"] = True
        try:
            result = subprocess.run(
                [str(paths.accounts_bin), *command],
                capture_output=True,
                text=True,
                env=sanitized_env(),
                check=False,
            )
        except OSError as exc:
            retire_result["external_command_status"] = "exec_error"
            retire_result["final_outcome"] = "retire_command_failed"
            return build_retire_payload(
                ok=False,
                human_message="Retirement command could not be executed.",
                machine_error_code="RETIRE_COMMAND_EXEC_FAILED",
                operator_action="user_action",
                exit_code=1,
                extra={"command_error": str(exc)},
            )
        emit_subprocess_output(stdout=result.stdout, stderr=result.stderr)
        retire_result["external_command_exit_code"] = int(result.returncode)
        retire_result["external_command_status"] = (
            "ok" if result.returncode == 0 else "nonzero"
        )

        after_command_registry = read_json(paths.registry_file)
        after_command_state = read_json(paths.state_file, required=False)
        after_command_matches = get_registry_backends_by_id(
            after_command_registry, backend_id
        )
        after_command_backend = (
            after_command_matches[0] if len(after_command_matches) == 1 else None
        )
        after_routing_ids = routing_eligible_active_backend_ids(after_command_registry)
        after_selected_backend_ids = selected_backend_ids_from_state(after_command_state)
        after_command_pool = (
            str(after_command_backend.get("pool", ""))
            if isinstance(after_command_backend, dict)
            else ""
        )
        retire_result["routing_change_attempted"] = bool(
            before_routing_ids != after_routing_ids
            or before_selected_backend_ids != after_selected_backend_ids
            or (previous_pool == "active" and after_command_pool != "active")
            or (previous_pool != "active" and after_command_pool == "active")
        )

        def fail_after_command(
            *,
            human_message: str,
            machine_error_code: str,
            liveness: str,
            operator_action: str,
            exit_code: int | None,
            extra: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return rollback_after_failed_verification(
                human_message=human_message,
                machine_error_code=machine_error_code,
                liveness=liveness,
                operator_action=operator_action,
                exit_code=exit_code,
                extra=extra,
            )

        if len(after_command_matches) != 1:
            retire_result["final_outcome"] = "retire_command_failed"
            return fail_after_command(
                human_message=(
                    "Retirement did not leave a uniquely identifiable backend state."
                ),
                machine_error_code="RETIRE_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        after_command_hold = bool(after_command_backend.get("manual_hold", False))
        terminal_pool_verified = after_command_pool == "retired" and not after_command_hold
        if retire_result["routing_change_attempted"]:
            lifecycle_verified = terminal_pool_verified
            retire_result["terminal_no_return_confirmed"] = False
        else:
            lifecycle_verified = bool(
                terminal_pool_verified
                and backend_id not in set(after_routing_ids)
                and backend_id not in set(after_selected_backend_ids)
            )
            retire_result["terminal_no_return_confirmed"] = lifecycle_verified
        if not lifecycle_verified:
            retire_result["final_outcome"] = "retire_command_failed"
            return fail_after_command(
                human_message=(
                    "Retirement command did not leave the backend in terminal retired state."
                ),
                machine_error_code="RETIRE_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        sync_payload: dict[str, Any] | None = None
        status_payload: dict[str, Any] | None = None
        if retire_result["routing_change_attempted"]:
            retire_result["sync_attempted"] = True
            try:
                sync_payload = run_sync_for_owner_path_under_lock(paths)
                retire_result["sync_outcome"] = (
                    "ok" if sync_payload["status"] == "ok" else "failed"
                )
                if sync_payload["status"] != "ok":
                    return rollback_after_failed_verification(
                        human_message=(
                            "Retirement changed routing inputs, but managed sync verification failed."
                        ),
                        machine_error_code="RETIRE_SYNC_FAILED",
                        liveness=str(sync_payload.get("liveness", "unknown")),
                        operator_action=str(
                            sync_payload.get("operator_action", "retry")
                        ),
                        exit_code=int(sync_payload.get("exit_code", 1) or 1),
                        extra={
                            "sync_result": {
                                "command_status": sync_payload["status"],
                                "machine_error_code": sync_payload["machine_error_code"],
                                "exit_code": sync_payload["exit_code"],
                            }
                        },
                    )

                status_payload, status_observed = (
                    observe_status_proof_for_owner_path_under_lock(paths)
                )
                retire_result["status_observed"] = status_observed
                verified_registry = read_json(paths.registry_file)
                verified_state = read_json(paths.state_file, required=False)
                verified_matches = get_registry_backends_by_id(
                    verified_registry, backend_id
                )
                verified_backend = (
                    verified_matches[0] if len(verified_matches) == 1 else None
                )
                verified_selected_backend_ids = set(
                    selected_backend_ids_from_state(verified_state)
                )
                verified_routing_ids = set(
                    routing_eligible_active_backend_ids(verified_registry)
                )
                retire_result["routing_change_observed"] = bool(
                    status_payload["status"] == "ok"
                    and isinstance(verified_backend, dict)
                    and str(verified_backend.get("pool", "")) == "retired"
                    and not bool(verified_backend.get("manual_hold", False))
                    and backend_id not in verified_routing_ids
                    and backend_id not in verified_selected_backend_ids
                )
                retire_result["terminal_no_return_confirmed"] = retire_result[
                    "routing_change_observed"
                ]
                if (
                    status_payload["status"] != "ok"
                    or not retire_result["routing_change_observed"]
                ):
                    return rollback_after_failed_verification(
                        human_message=(
                            "Retirement did not produce verified terminal routing removal after status proof."
                        ),
                        machine_error_code="RETIRE_STATUS_FAILED",
                        liveness=str(status_payload.get("liveness", "unknown")),
                        operator_action=str(
                            status_payload.get("operator_action", "retry")
                        ),
                        exit_code=int(status_payload.get("exit_code", 1) or 1),
                        extra={
                            "sync_result": {
                                "command_status": sync_payload["status"],
                                "machine_error_code": sync_payload["machine_error_code"],
                                "exit_code": sync_payload["exit_code"],
                            }
                        },
                    )
            except RuntimeErrorInfo as exc:
                return rollback_after_failed_verification(
                    human_message=(
                        "Retirement post-command verification raised a runtime error."
                    ),
                    machine_error_code="RETIRE_SYNC_FAILED",
                    liveness="unknown",
                    operator_action=exc.operator_action,
                    exit_code=exc.exit_code,
                    extra={"verification_error": str(exc)},
                )
            except Exception as exc:  # noqa: BLE001
                return rollback_after_failed_verification(
                    human_message=(
                        "Retirement post-command verification raised an unexpected error."
                    ),
                    machine_error_code="RETIRE_STATUS_FAILED",
                    liveness="unknown",
                    operator_action="retry",
                    exit_code=1,
                    extra={"verification_error": str(exc)},
                )

        retire_result["rollback_outcome"] = "not_needed"
        retire_result["final_outcome"] = "backend_retired"
        success_extra: dict[str, Any] = {}
        if sync_payload is not None:
            success_extra["sync_result"] = {
                "command_status": sync_payload["status"],
                "machine_error_code": sync_payload["machine_error_code"],
                "exit_code": sync_payload["exit_code"],
            }
        return build_retire_payload(
            ok=True,
            human_message=(
                "Account retirement completed with rollback-safe terminal proof."
                if result.returncode == 0 and retire_result["routing_change_attempted"]
                else "Account retirement completed."
                if result.returncode == 0
                else "Account retirement completed with terminal proof after external retire exit non-zero."
            ),
            machine_error_code="OK",
            liveness=(
                str(status_payload.get("liveness", "unknown"))
                if status_payload is not None
                else "unknown"
            ),
            severity="recoverable",
            operator_action="none",
            extra=success_extra or None,
        )


def run_protective_lifecycle_owner_path(
    paths: RuntimePaths,
    backend_id: str,
    *,
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    if not paths.accounts_bin.exists():
        raise RuntimeErrorInfo(
            f"Missing accounts command: {paths.accounts_bin}",
            machine_error_code="MISSING_ACCOUNTS_BIN",
            operator_action="user_action",
        )

    before = snapshot_known_files(paths)
    before_registry = read_json(paths.registry_file)
    before_state = read_json(paths.state_file, required=False)
    before_routing_ids = routing_eligible_active_backend_ids(before_registry)
    before_selected_backend_ids = selected_backend_ids_from_state(before_state)
    command = [action, backend_id]
    if action == "hold" and reason:
        command.append(reason)

    result_key = "hold_result" if action == "hold" else "release_result"
    success_outcome = (
        "backend_held" if action == "hold" else "backend_released_to_reserve"
    )
    failure_prefix = action.upper()
    backend_matches = get_registry_backends_by_id(before_registry, backend_id)
    selected_backend = backend_matches[0] if len(backend_matches) == 1 else None
    previous_pool = (
        str(selected_backend.get("pool")) if isinstance(selected_backend, dict) else ""
    )
    previous_manual_hold = bool(
        selected_backend.get("manual_hold", False)
        if isinstance(selected_backend, dict)
        else False
    )
    transition_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "backend_id": backend_id,
        "precondition_status": "pending",
        "previous_pool": previous_pool,
        "previous_manual_hold": previous_manual_hold,
        "requested_transition": "protective_hold" if action == "hold" else "release_to_reserve",
        "rollback_point_captured": False,
        "routing_change_attempted": False,
        "routing_change_observed": False,
        "sync_attempted": False,
        "sync_outcome": "not_attempted",
        "status_observed": None,
        "rollback_attempted": False,
        "rollback_outcome": "not_attempted",
        "external_command_exit_code": None,
        "external_command_status": "not_invoked",
        "final_outcome": "pending_preconditions",
    }

    def build_transition_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        liveness: str = "unknown",
        severity: str = "recoverable",
        operator_action: str = "none",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_extra = {
            "command": command,
            result_key: transition_result,
        }
        if extra:
            payload_extra.update(extra)
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness=liveness,
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra=payload_extra,
            exit_code=exit_code,
        )

    def rollback_after_failed_verification(
        *,
        human_message: str,
        machine_error_code: str,
        liveness: str,
        operator_action: str,
        exit_code: int | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        transition_result["rollback_attempted"] = True
        try:
            restore_lifecycle_owner_path_runtime_surfaces(paths, rollback_snapshots)
            transition_result["rollback_outcome"] = "completed"
            transition_result["final_outcome"] = (
                "rollback_completed_after_failed_verification"
            )
            return build_transition_payload(
                ok=False,
                human_message=human_message,
                machine_error_code=machine_error_code,
                liveness=liveness,
                severity="recoverable",
                operator_action=operator_action,
                exit_code=exit_code,
                extra=extra,
            )
        except Exception as exc:  # noqa: BLE001
            transition_result["rollback_outcome"] = "failed"
            transition_result["final_outcome"] = "rollback_failed"
            payload_extra = dict(extra or {})
            payload_extra["rollback_error"] = str(exc)
            return build_transition_payload(
                ok=False,
                human_message=(
                    f"{human_message} Rollback of control-layer lifecycle state failed."
                ),
                machine_error_code=f"{failure_prefix}_ROLLBACK_FAILED",
                liveness=liveness,
                severity="fatal",
                operator_action="stop",
                exit_code=1,
                extra=payload_extra,
            )

    if not backend_matches:
        transition_result["precondition_status"] = "backend_missing"
        transition_result["final_outcome"] = "precondition_failed"
        return build_transition_payload(
            ok=False,
            human_message="Lifecycle target backend does not exist.",
            machine_error_code=f"{failure_prefix}_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    if len(backend_matches) > 1:
        transition_result["precondition_status"] = "ambiguous_backend_id"
        transition_result["final_outcome"] = "precondition_failed"
        return build_transition_payload(
            ok=False,
            human_message="Lifecycle target backend is ambiguous.",
            machine_error_code=f"{failure_prefix}_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    if previous_pool == "retired":
        transition_result["precondition_status"] = "backend_retired"
        transition_result["final_outcome"] = "precondition_failed"
        return build_transition_payload(
            ok=False,
            human_message="Retired backend is not eligible for this lifecycle transition.",
            machine_error_code=f"{failure_prefix}_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    if action == "hold" and previous_manual_hold:
        transition_result["precondition_status"] = "already_held"
        transition_result["final_outcome"] = "already_held"
        return build_transition_payload(
            ok=True,
            human_message="Backend is already on protective hold.",
            machine_error_code="OK",
            operator_action="none",
        )

    if action == "release" and not previous_manual_hold:
        transition_result["precondition_status"] = "not_on_hold"
        transition_result["final_outcome"] = "not_on_hold"
        return build_transition_payload(
            ok=False,
            human_message="Backend is not currently on hold.",
            machine_error_code=f"{failure_prefix}_PRECONDITION_FAILED",
            operator_action="user_action",
        )

    transition_result["precondition_status"] = (
        "eligible_backend_for_hold"
        if action == "hold"
        else "eligible_backend_for_release"
    )

    with serialized_lock(paths):
        rollback_snapshots = snapshot_lifecycle_owner_path_runtime_surfaces(paths)
        transition_result["rollback_point_captured"] = True
        try:
            result = subprocess.run(
                [str(paths.accounts_bin), *command],
                capture_output=True,
                text=True,
                env=sanitized_env(),
                check=False,
            )
        except OSError as exc:
            transition_result["external_command_status"] = "exec_error"
            transition_result["final_outcome"] = (
                "hold_command_failed"
                if action == "hold"
                else "release_command_failed"
            )
            return build_transition_payload(
                ok=False,
                human_message="Protective lifecycle command could not be executed.",
                machine_error_code=f"{failure_prefix}_COMMAND_EXEC_FAILED",
                operator_action="user_action",
                exit_code=1,
                extra={"command_error": str(exc)},
            )
        emit_subprocess_output(stdout=result.stdout, stderr=result.stderr)
        transition_result["external_command_exit_code"] = int(result.returncode)
        transition_result["external_command_status"] = (
            "ok" if result.returncode == 0 else "nonzero"
        )

        after_command_registry = read_json(paths.registry_file)
        after_command_state = read_json(paths.state_file, required=False)
        after_command_matches = get_registry_backends_by_id(
            after_command_registry, backend_id
        )
        after_command_backend = (
            after_command_matches[0] if len(after_command_matches) == 1 else None
        )
        after_routing_ids = routing_eligible_active_backend_ids(after_command_registry)
        after_selected_backend_ids = selected_backend_ids_from_state(after_command_state)
        after_command_pool = (
            str(after_command_backend.get("pool", ""))
            if isinstance(after_command_backend, dict)
            else ""
        )
        transition_result["routing_change_attempted"] = bool(
            before_routing_ids != after_routing_ids
            or before_selected_backend_ids != after_selected_backend_ids
            or (
                previous_pool == "active"
                and after_command_pool != "active"
            )
            or (
                previous_pool != "active"
                and after_command_pool == "active"
            )
        )

        def fail_after_command(
            *,
            human_message: str,
            machine_error_code: str,
            liveness: str,
            operator_action: str,
            exit_code: int | None,
            extra: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return rollback_after_failed_verification(
                human_message=human_message,
                machine_error_code=machine_error_code,
                liveness=liveness,
                operator_action=operator_action,
                exit_code=exit_code,
                extra=extra,
            )

        if len(after_command_matches) != 1:
            transition_result["final_outcome"] = (
                f"{action}_command_failed"
                if action == "hold"
                else "release_command_failed"
            )
            return fail_after_command(
                human_message=(
                    "Lifecycle transition did not leave a uniquely identifiable backend state."
                ),
                machine_error_code=f"{failure_prefix}_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        after_command_hold = bool(after_command_backend.get("manual_hold", False))
        if action == "hold":
            lifecycle_verified = (
                after_command_hold and after_command_pool in {"active", "reserve"}
            )
        else:
            lifecycle_verified = not after_command_hold and after_command_pool == "reserve"
        if not lifecycle_verified:
            transition_result["final_outcome"] = (
                "hold_command_failed"
                if action == "hold"
                else "release_command_failed"
            )
            return fail_after_command(
                human_message=(
                    "Protective hold command did not leave the backend in held state."
                    if action == "hold"
                    else "Release command did not return the backend to reserve."
                ),
                machine_error_code=f"{failure_prefix}_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        sync_payload: dict[str, Any] | None = None
        status_payload: dict[str, Any] | None = None
        if transition_result["routing_change_attempted"]:
            transition_result["sync_attempted"] = True
            try:
                sync_payload = run_sync_for_owner_path_under_lock(paths)
                transition_result["sync_outcome"] = (
                    "ok" if sync_payload["status"] == "ok" else "failed"
                )
                if sync_payload["status"] != "ok":
                    return rollback_after_failed_verification(
                        human_message=(
                            "Protective lifecycle transition changed routing inputs, but managed sync verification failed."
                        ),
                        machine_error_code=f"{failure_prefix}_SYNC_FAILED",
                        liveness=str(sync_payload.get("liveness", "unknown")),
                        operator_action=str(
                            sync_payload.get("operator_action", "retry")
                        ),
                        exit_code=int(sync_payload.get("exit_code", 1) or 1),
                        extra={
                            "sync_result": {
                                "command_status": sync_payload["status"],
                                "machine_error_code": sync_payload["machine_error_code"],
                                "exit_code": sync_payload["exit_code"],
                            }
                        },
                    )

                status_payload, status_observed = (
                    observe_status_proof_for_owner_path_under_lock(paths)
                )
                transition_result["status_observed"] = status_observed
                verified_registry = read_json(paths.registry_file)
                verified_state = read_json(paths.state_file, required=False)
                verified_matches = get_registry_backends_by_id(
                    verified_registry, backend_id
                )
                verified_backend = (
                    verified_matches[0] if len(verified_matches) == 1 else None
                )
                verified_selected_backend_ids = set(
                    selected_backend_ids_from_state(verified_state)
                )
                verified_routing_ids = set(
                    routing_eligible_active_backend_ids(verified_registry)
                )
                if action == "hold":
                    transition_result["routing_change_observed"] = bool(
                        status_payload["status"] == "ok"
                        and isinstance(verified_backend, dict)
                        and bool(verified_backend.get("manual_hold", False))
                        and backend_id not in verified_routing_ids
                        and backend_id not in verified_selected_backend_ids
                    )
                else:
                    transition_result["routing_change_observed"] = bool(
                        status_payload["status"] == "ok"
                        and isinstance(verified_backend, dict)
                        and not bool(verified_backend.get("manual_hold", False))
                        and str(verified_backend.get("pool", "")) == "reserve"
                        and backend_id not in verified_routing_ids
                        and backend_id not in verified_selected_backend_ids
                    )
                if (
                    status_payload["status"] != "ok"
                    or not transition_result["routing_change_observed"]
                ):
                    return rollback_after_failed_verification(
                        human_message=(
                            "Protective hold did not produce verified routing isolation after status proof."
                            if action == "hold"
                            else "Release did not produce verified reserve-only state after status proof."
                        ),
                        machine_error_code=f"{failure_prefix}_STATUS_FAILED",
                        liveness=str(status_payload.get("liveness", "unknown")),
                        operator_action=str(
                            status_payload.get("operator_action", "retry")
                        ),
                        exit_code=int(status_payload.get("exit_code", 1) or 1),
                        extra=(
                            {
                                "sync_result": {
                                    "command_status": sync_payload["status"],
                                    "machine_error_code": sync_payload["machine_error_code"],
                                    "exit_code": sync_payload["exit_code"],
                                }
                            }
                            if sync_payload is not None
                            else None
                        ),
                    )
            except RuntimeErrorInfo as exc:
                return rollback_after_failed_verification(
                    human_message=(
                        "Protective lifecycle post-command verification raised a runtime error."
                    ),
                    machine_error_code=f"{failure_prefix}_SYNC_FAILED",
                    liveness="unknown",
                    operator_action=exc.operator_action,
                    exit_code=exc.exit_code,
                    extra={"verification_error": str(exc)},
                )
            except Exception as exc:  # noqa: BLE001
                return rollback_after_failed_verification(
                    human_message=(
                        "Protective lifecycle post-command verification raised an unexpected error."
                    ),
                    machine_error_code=f"{failure_prefix}_STATUS_FAILED",
                    liveness="unknown",
                    operator_action="retry",
                    exit_code=1,
                    extra={"verification_error": str(exc)},
                )

        transition_result["rollback_outcome"] = "not_needed"
        transition_result["final_outcome"] = success_outcome
        success_extra: dict[str, Any] = {}
        if sync_payload is not None:
            success_extra["sync_result"] = {
                "command_status": sync_payload["status"],
                "machine_error_code": sync_payload["machine_error_code"],
                "exit_code": sync_payload["exit_code"],
            }
        return build_transition_payload(
            ok=True,
            human_message=(
                "Protective hold completed with verified routing isolation."
                if action == "hold" and transition_result["routing_change_attempted"]
                else "Protective hold completed."
                if action == "hold"
                else "Release completed with verified reserve-only routing proof."
                if transition_result["routing_change_attempted"]
                else "Release completed and backend remains reserve-only."
            )
            if result.returncode == 0
            else (
                "Protective hold completed after external hold exit non-zero."
                if action == "hold"
                else "Release completed after external release exit non-zero."
            ),
            machine_error_code="OK",
            liveness=(
                str(status_payload.get("liveness", "unknown"))
                if status_payload is not None
                else "unknown"
            ),
            severity="recoverable",
            operator_action="none",
            extra=success_extra or None,
        )


def run_promote(
    paths: RuntimePaths,
    backend_id: str,
    *,
    lock_acquired: bool = False,
) -> dict[str, Any]:
    if not paths.accounts_bin.exists():
        raise RuntimeErrorInfo(
            f"Missing accounts command: {paths.accounts_bin}",
            machine_error_code="MISSING_ACCOUNTS_BIN",
            operator_action="user_action",
        )
    before = snapshot_known_files(paths)
    command = ["promote", backend_id]
    promotion_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "backend_id": backend_id,
        "precondition_status": "pending",
        "previous_pool": "",
        "requested_pool": "active",
        "pool_policy_status": "pending",
        "pool_policy_observed": None,
        "active_pool_count_before": None,
        "active_target_observed": None,
        "reserve_count_before": None,
        "reserve_target_observed": None,
        "active_pool_count_after": None,
        "reserve_count_after": None,
        "policy_verification_status": "not_verified",
        "rollback_point_captured": False,
        "routing_change_attempted": False,
        "routing_change_observed": False,
        "validate_attempted": False,
        "validate_outcome": "not_attempted",
        "sync_attempted": False,
        "sync_outcome": "not_attempted",
        "status_observed": None,
        "rollback_attempted": False,
        "rollback_outcome": "not_attempted",
        "external_command_exit_code": None,
        "external_command_status": "not_invoked",
        "final_outcome": "pending_preconditions",
    }

    def build_promote_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        liveness: str = "unknown",
        severity: str = "recoverable",
        operator_action: str = "none",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_extra = {
            "command": command,
            "promotion_result": promotion_result,
        }
        if extra:
            payload_extra.update(extra)
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness=liveness,
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra=payload_extra,
            exit_code=exit_code,
        )

    def rollback_after_failed_verification(
        *,
        human_message: str,
        machine_error_code: str,
        liveness: str,
        operator_action: str,
        exit_code: int | None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        promotion_result["rollback_attempted"] = True
        try:
            restore_promotion_owner_path_runtime_surfaces(paths, rollback_snapshots)
            promotion_result["rollback_outcome"] = "completed"
            promotion_result["final_outcome"] = (
                "rollback_completed_after_failed_verification"
            )
            return build_promote_payload(
                ok=False,
                human_message=human_message,
                machine_error_code=machine_error_code,
                liveness=liveness,
                severity="recoverable",
                operator_action=operator_action,
                exit_code=exit_code,
                extra=extra,
            )
        except Exception as exc:  # noqa: BLE001
            promotion_result["rollback_outcome"] = "failed"
            promotion_result["final_outcome"] = "rollback_failed"
            payload_extra = dict(extra or {})
            payload_extra["rollback_error"] = str(exc)
            return build_promote_payload(
                ok=False,
                human_message=(
                    f"{human_message} Rollback of control-layer promotion state failed."
                ),
                machine_error_code="PROMOTION_ROLLBACK_FAILED",
                liveness=liveness,
                severity="fatal",
                operator_action="stop",
                exit_code=1,
                extra=payload_extra,
            )

    mutation_lock = nullcontext() if lock_acquired else serialized_lock(paths)
    with mutation_lock:
        before_registry = read_json(paths.registry_file)
        before_state = read_json(paths.state_file, required=False)
        backend_matches = get_registry_backends_by_id(before_registry, backend_id)
        selected_backend = backend_matches[0] if len(backend_matches) == 1 else None
        previous_pool = (
            str(selected_backend.get("pool")) if isinstance(selected_backend, dict) else ""
        )
        promotion_result["previous_pool"] = previous_pool

        if not backend_matches:
            promotion_result["precondition_status"] = "backend_missing"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Promotion target backend does not exist.",
                machine_error_code="PROMOTION_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if len(backend_matches) > 1:
            promotion_result["precondition_status"] = "ambiguous_backend_id"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Promotion target backend is ambiguous.",
                machine_error_code="PROMOTION_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if bool(selected_backend.get("manual_hold", False)):
            promotion_result["precondition_status"] = "backend_on_hold"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Held backend cannot be promoted directly.",
                machine_error_code="PROMOTION_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if previous_pool == "retired":
            promotion_result["precondition_status"] = "backend_retired"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Retired backend cannot be promoted.",
                machine_error_code="PROMOTION_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        if previous_pool != "reserve":
            promotion_result["precondition_status"] = "backend_not_reserve"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Only reserve backends are eligible for promotion.",
                machine_error_code="PROMOTION_PRECONDITION_FAILED",
                operator_action="user_action",
            )

        pool_policy = summarize_promotion_pool_policy(before_registry)
        promotion_result["pool_policy_status"] = str(pool_policy.get("status", "invalid"))
        promotion_result["pool_policy_observed"] = pool_policy
        promotion_result["active_target_observed"] = pool_policy.get("active_target")
        promotion_result["reserve_target_observed"] = pool_policy.get("reserve_target")
        pool_counts_before = summarize_registry_pool_counts(before_registry)
        promotion_result["active_pool_count_before"] = pool_counts_before.get("active", 0)
        promotion_result["reserve_count_before"] = pool_counts_before.get("reserve", 0)
        if pool_policy.get("status") != "ok":
            promotion_result["precondition_status"] = "pool_policy_invalid"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Promotion blocked because pool policy is invalid.",
                machine_error_code="PROMOTION_POLICY_INVALID",
                operator_action="user_action",
            )

        active_pool_count_before = int(promotion_result["active_pool_count_before"] or 0)
        reserve_count_before = int(promotion_result["reserve_count_before"] or 0)
        active_target = int(pool_policy["active_target"])
        reserve_target = int(pool_policy["reserve_target"])
        if active_pool_count_before >= active_target:
            promotion_result["precondition_status"] = "active_target_reached"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Promotion blocked because the staged active-pool target is already reached.",
                machine_error_code="PROMOTION_POLICY_LIMIT_REACHED",
                operator_action="user_action",
            )

        if reserve_count_before - 1 < reserve_target:
            promotion_result["precondition_status"] = "reserve_target_would_be_violated"
            promotion_result["final_outcome"] = "precondition_failed"
            return build_promote_payload(
                ok=False,
                human_message="Promotion blocked because it would drop reserve below the staged reserve target.",
                machine_error_code="PROMOTION_POLICY_LIMIT_REACHED",
                operator_action="user_action",
            )

        promotion_result["precondition_status"] = "eligible_reserve_backend"
        validate_result = subprocess.run(
            [str(paths.accounts_bin), "validate", backend_id],
            capture_output=True,
            text=True,
            env=sanitized_env(),
            check=False,
        )
        emit_subprocess_output(
            stdout=validate_result.stdout, stderr=validate_result.stderr
        )
        validate_payload = {
            "status": "ok" if validate_result.returncode == 0 else "error",
            "machine_error_code": (
                "OK" if validate_result.returncode == 0 else "ACCOUNTS_COMMAND_FAILED"
            ),
            "exit_code": 0 if validate_result.returncode == 0 else validate_result.returncode,
        }
        promotion_result["validate_attempted"] = True
        promotion_result["validate_outcome"] = (
            "ok" if validate_payload["status"] == "ok" else "failed"
        )
        if validate_payload["status"] != "ok":
            promotion_result["final_outcome"] = "validate_failed"
            return build_promote_payload(
                ok=False,
                human_message="Promotion preflight validation failed.",
                machine_error_code="PROMOTION_VALIDATE_FAILED",
                operator_action="user_action",
                exit_code=int(validate_payload.get("exit_code", 1) or 1),
                extra={
                    "validate_result": {
                        "command_status": validate_payload["status"],
                        "machine_error_code": validate_payload["machine_error_code"],
                        "exit_code": validate_payload["exit_code"],
                    }
                },
            )

        rollback_snapshots = snapshot_promotion_owner_path_runtime_surfaces(paths)
        promotion_result["rollback_point_captured"] = True
        result = subprocess.run(
            [str(paths.accounts_bin), *command],
            capture_output=True,
            text=True,
            env=sanitized_env(),
            check=False,
        )
        emit_subprocess_output(stdout=result.stdout, stderr=result.stderr)
        promotion_result["external_command_exit_code"] = int(result.returncode)
        promotion_result["external_command_status"] = (
            "ok" if result.returncode == 0 else "nonzero"
        )

        after_command_registry = read_json(paths.registry_file)
        after_command_state = read_json(paths.state_file, required=False)
        after_command_matches = get_registry_backends_by_id(
            after_command_registry, backend_id
        )
        after_command_backend = (
            after_command_matches[0] if len(after_command_matches) == 1 else None
        )
        before_selected_backend_ids = sorted(
            str(item) for item in before_state.get("selected_backend_ids", []) or []
        )
        after_command_selected_backend_ids = sorted(
            str(item) for item in after_command_state.get("selected_backend_ids", []) or []
        )
        promotion_result["routing_change_attempted"] = bool(
            (
                isinstance(after_command_backend, dict)
                and str(after_command_backend.get("pool", "")) != previous_pool
            )
            or before_selected_backend_ids != after_command_selected_backend_ids
        )

        if len(after_command_matches) != 1:
            promotion_result["final_outcome"] = "promotion_command_failed"
            return rollback_after_failed_verification(
                human_message=(
                    "Promotion did not leave a uniquely identifiable backend state."
                ),
                machine_error_code="PROMOTION_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        if bool(after_command_backend.get("manual_hold", False)) or str(
            after_command_backend.get("pool", "")
        ) != "active":
            promotion_result["final_outcome"] = "promotion_command_failed"
            return rollback_after_failed_verification(
                human_message="Promotion command did not place the backend into active.",
                machine_error_code="PROMOTION_COMMAND_FAILED",
                liveness="unknown",
                operator_action="user_action",
                exit_code=result.returncode if result.returncode != 0 else 1,
            )

        promotion_result["sync_attempted"] = True
        try:
            if not paths.sync_script.exists():
                raise RuntimeErrorInfo(
                    f"Missing sync script: {paths.sync_script}",
                    machine_error_code="MISSING_SYNC_SCRIPT",
                    operator_action="user_action",
                )
            sync_result = subprocess.run(
                [str(paths.sync_script), get_model(paths)],
                capture_output=True,
                text=True,
                env=sanitized_env(),
                check=False,
            )
            emit_subprocess_output(stdout=sync_result.stdout, stderr=sync_result.stderr)
            sync_state = read_json(paths.state_file, required=False)
            sync_effective_mode = get_effective_mode(paths, sync_state)
            sync_host, sync_port, _ = get_endpoint(paths, sync_effective_mode)
            sync_listener_ok = socket_is_listening(sync_host, sync_port)
            sync_reported_effective_mode = reconcile_effective_mode_for_reporting(
                sync_effective_mode, listener_ok=sync_listener_ok
            )
            _, _, sync_reported_endpoint = get_endpoint(
                paths, sync_reported_effective_mode
            )
            if sync_result.returncode != 0:
                sync_payload = {
                    "status": "error",
                    "machine_error_code": "SYNC_FAILED",
                    "exit_code": sync_result.returncode,
                    "liveness": "down" if not sync_listener_ok else "degraded",
                    "operator_action": "retry",
                    "effective_mode": sync_reported_effective_mode,
                    "endpoint": sync_reported_endpoint,
                }
            elif not sync_listener_ok:
                sync_payload = {
                    "status": "error",
                    "machine_error_code": "SYNC_HEALTHCHECK_FAILED",
                    "exit_code": 1,
                    "liveness": "down",
                    "operator_action": "retry",
                    "effective_mode": sync_reported_effective_mode,
                    "endpoint": sync_reported_endpoint,
                }
            else:
                sync_payload = {
                    "status": "ok",
                    "machine_error_code": "OK",
                    "exit_code": 0,
                    "liveness": "healthy",
                    "operator_action": "none",
                    "effective_mode": sync_reported_effective_mode,
                    "endpoint": sync_reported_endpoint,
                }
            promotion_result["sync_outcome"] = (
                "ok" if sync_payload["status"] == "ok" else "failed"
            )
            if sync_payload["status"] != "ok":
                promotion_result["status_observed"] = None
                return rollback_after_failed_verification(
                    human_message=(
                        "Promotion changed routing inputs, but managed sync verification failed."
                    ),
                    machine_error_code="PROMOTION_SYNC_FAILED",
                    liveness=str(sync_payload.get("liveness", "unknown")),
                    operator_action=str(sync_payload.get("operator_action", "retry")),
                    exit_code=int(sync_payload.get("exit_code", 1) or 1),
                    extra={
                        "sync_result": {
                            "command_status": sync_payload["status"],
                            "machine_error_code": sync_payload["machine_error_code"],
                            "exit_code": sync_payload["exit_code"],
                        }
                    },
                )

            health_payload = run_healthcheck(
                paths,
                allow_recovery=False,
                allow_last_known_good_proxy_write=False,
                allow_current_proxy_auto_adoption=False,
            )
            status_payload = summarize_status(paths, health_payload=health_payload)
            promotion_result["status_observed"] = summarize_owner_path_status_observation(
                status_payload
            )
            verified_registry = read_json(paths.registry_file)
            verified_state = read_json(paths.state_file, required=False)
            verified_matches = get_registry_backends_by_id(verified_registry, backend_id)
            verified_backend = (
                verified_matches[0] if len(verified_matches) == 1 else None
            )
            verified_pool_counts = summarize_registry_pool_counts(verified_registry)
            verified_selected_backend_ids = {
                str(item) for item in verified_state.get("selected_backend_ids", []) or []
            }
            active_pool_count_after = int(verified_pool_counts.get("active", 0) or 0)
            reserve_count_after = int(verified_pool_counts.get("reserve", 0) or 0)
            promotion_result["active_pool_count_after"] = active_pool_count_after
            promotion_result["reserve_count_after"] = reserve_count_after
            if lock_acquired:
                promotion_policy_verified = True
                promotion_result["policy_verification_status"] = "delegated_to_caller"
            else:
                promotion_policy_verified = bool(
                    active_pool_count_after == active_pool_count_before + 1
                    and active_pool_count_after <= active_target
                    and reserve_count_after == reserve_target
                )
                promotion_result["policy_verification_status"] = (
                    "passed" if promotion_policy_verified else "failed"
                )
            promotion_result["routing_change_observed"] = bool(
                status_payload["status"] == "ok"
                and isinstance(verified_backend, dict)
                and str(verified_backend.get("pool", "")) == "active"
                and not bool(verified_backend.get("manual_hold", False))
                and backend_id in verified_selected_backend_ids
                and promotion_policy_verified
            )
            if status_payload["status"] != "ok" or not promotion_result["routing_change_observed"]:
                failure_message = (
                    "Promotion did not preserve staged reserve/active pool policy after status proof."
                    if status_payload["status"] == "ok" and not promotion_policy_verified
                    else "Promotion did not produce verified active routing after status proof."
                )
                return rollback_after_failed_verification(
                    human_message=failure_message,
                    machine_error_code="PROMOTION_STATUS_FAILED",
                    liveness=str(status_payload.get("liveness", "unknown")),
                    operator_action=str(status_payload.get("operator_action", "retry")),
                    exit_code=int(status_payload.get("exit_code", 1) or 1),
                    extra={
                        "sync_result": {
                            "command_status": sync_payload["status"],
                            "machine_error_code": sync_payload["machine_error_code"],
                            "exit_code": sync_payload["exit_code"],
                        }
                    },
                )
        except RuntimeErrorInfo as exc:
            return rollback_after_failed_verification(
                human_message="Promotion post-command verification raised a runtime error.",
                machine_error_code="PROMOTION_SYNC_FAILED",
                liveness="unknown",
                operator_action=exc.operator_action,
                exit_code=exc.exit_code,
                extra={"verification_error": str(exc)},
            )
        except Exception as exc:  # noqa: BLE001
            return rollback_after_failed_verification(
                human_message="Promotion post-command verification raised an unexpected error.",
                machine_error_code="PROMOTION_STATUS_FAILED",
                liveness="unknown",
                operator_action="retry",
                exit_code=1,
                extra={"verification_error": str(exc)},
            )

        promotion_result["rollback_outcome"] = "not_needed"
        promotion_result["final_outcome"] = "promoted_to_active"
        return build_promote_payload(
            ok=True,
            human_message=(
                "Account promotion completed with rollback-safe active proof."
                if result.returncode == 0
                else "Account promotion completed with rollback-safe active proof after external promote exit non-zero."
            ),
            machine_error_code="OK",
            liveness=str(status_payload.get("liveness", "unknown")),
            severity="recoverable",
            operator_action="none",
            extra={
                "validate_result": {
                    "command_status": validate_payload["status"],
                    "machine_error_code": validate_payload["machine_error_code"],
                    "exit_code": validate_payload["exit_code"],
                },
                "sync_result": {
                    "command_status": sync_payload["status"],
                    "machine_error_code": sync_payload["machine_error_code"],
                    "exit_code": sync_payload["exit_code"],
                },
            },
        )


def summarize_owner_path_status_observation(status_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_status": str(status_payload.get("status", "error")),
        "exit_code": int(status_payload.get("exit_code", 1)),
        "machine_error_code": str(
            status_payload.get("machine_error_code", "STATUS_UNKNOWN")
        ),
        "liveness": str(status_payload.get("liveness", "unknown")),
        "effective_mode": str(status_payload.get("effective_mode", "unknown")),
        "endpoint": str(status_payload.get("endpoint", "")),
    }


def summarize_onboarding_status_observation(status_payload: dict[str, Any]) -> dict[str, Any]:
    return summarize_owner_path_status_observation(status_payload)


def summarize_registry_pool_counts(registry: dict[str, Any]) -> dict[str, int]:
    counts = {"active": 0, "reserve": 0, "retired": 0}
    for backend in registry.get("backends", []):
        pool = str(backend.get("pool", ""))
        if pool in counts:
            counts[pool] += 1
    return counts


def get_registry_backends_by_id(
    registry: dict[str, Any], backend_id: str
) -> list[dict[str, Any]]:
    return [
        item
        for item in registry.get("backends", [])
        if str(item.get("id")) == backend_id
    ]


def routing_eligible_active_backend_ids(registry: dict[str, Any]) -> list[str]:
    return get_launch_capable_backend_ids(registry)


def auth_ref_matches(expected_auth_ref: str, backend_auth_ref: Any) -> bool:
    expected_path = Path(str(expected_auth_ref)).expanduser().resolve(strict=False)
    backend_path = Path(str(backend_auth_ref)).expanduser().resolve(strict=False)
    return expected_path == backend_path


def snapshot_promotion_owner_path_runtime_surfaces(
    paths: RuntimePaths,
) -> dict[str, dict[str, Any]]:
    return {
        "registry_file": snapshot_path_state(paths.registry_file),
        "state_file": snapshot_path_state(paths.state_file),
        "managed_config_file": snapshot_path_state(paths.managed_config_file),
        "config_toml": snapshot_path_state(paths.config_toml),
        "runtime_effective_mode_file": snapshot_path_state(
            paths.runtime_effective_mode_file
        ),
        "launcher_script": snapshot_path_state(paths.launcher_script),
        "stable_runtime_generated_config_file": snapshot_path_state(
            paths.stable_runtime_generated_config_file
        ),
        "managed_pid_file": snapshot_path_state(managed_pid_path(paths)),
    }


def restore_promotion_owner_path_runtime_surfaces(
    paths: RuntimePaths, snapshots: dict[str, dict[str, Any]]
) -> None:
    restore_path_state(
        paths.registry_file, snapshots.get("registry_file", {"state": "missing"})
    )
    restore_path_state(
        paths.state_file, snapshots.get("state_file", {"state": "missing"})
    )
    restore_path_state(
        paths.managed_config_file,
        snapshots.get("managed_config_file", {"state": "missing"}),
    )
    restore_path_state(
        paths.config_toml, snapshots.get("config_toml", {"state": "missing"})
    )
    restore_path_state(
        paths.runtime_effective_mode_file,
        snapshots.get("runtime_effective_mode_file", {"state": "missing"}),
    )
    restore_path_state(
        paths.launcher_script, snapshots.get("launcher_script", {"state": "missing"})
    )
    restore_path_state(
        paths.stable_runtime_generated_config_file,
        snapshots.get("stable_runtime_generated_config_file", {"state": "missing"}),
    )
    restore_path_state(
        managed_pid_path(paths),
        snapshots.get("managed_pid_file", {"state": "missing"}),
    )


def snapshot_lifecycle_owner_path_runtime_surfaces(
    paths: RuntimePaths,
) -> dict[str, dict[str, Any]]:
    return snapshot_promotion_owner_path_runtime_surfaces(paths)


def restore_lifecycle_owner_path_runtime_surfaces(
    paths: RuntimePaths, snapshots: dict[str, dict[str, Any]]
) -> None:
    restore_promotion_owner_path_runtime_surfaces(paths, snapshots)


def classify_onboarded_backend_selection(
    *,
    before_registry: dict[str, Any],
    after_registry: dict[str, Any],
    explicit_auth_ref: str | None,
) -> tuple[list[str], dict[str, Any] | None, str]:
    before_backend_ids = {
        str(item.get("id"))
        for item in before_registry.get("backends", [])
        if item.get("id") is not None
    }
    added_backends = [
        item
        for item in after_registry.get("backends", [])
        if str(item.get("id")) not in before_backend_ids
    ]
    added_backend_ids = sorted(str(item.get("id")) for item in added_backends)
    if explicit_auth_ref:
        matching_backends = [
            item
            for item in added_backends
            if auth_ref_matches(explicit_auth_ref, item.get("auth_ref"))
        ]
        if len(matching_backends) == 1:
            return added_backend_ids, matching_backends[0], "selected_unique_backend"
        if len(matching_backends) > 1:
            return added_backend_ids, None, "ambiguous_new_backend_selection"
        if len(added_backends) == 1:
            return added_backend_ids, None, "explicit_auth_ref_mismatch"
        if not added_backends:
            return added_backend_ids, None, "no_new_backend_detected"
        return added_backend_ids, None, "ambiguous_new_backend_selection"
    if len(added_backends) == 1:
        return added_backend_ids, added_backends[0], "selected_unique_backend"
    if not added_backends:
        return added_backend_ids, None, "no_new_backend_detected"
    return added_backend_ids, None, "ambiguous_new_backend_selection"


def run_onboard(
    paths: RuntimePaths,
    *,
    auth_ref: str | None,
    loop: bool,
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
    before_registry = read_json(paths.registry_file)
    before_state = read_json(paths.state_file, required=False)
    auth_snapshot_before_login = get_onboarding_auth_snapshot_before_login(paths)
    command = [str(paths.onboard_bin), "--loop" if loop else "--once"]
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
    after_registry = read_json(paths.registry_file)
    after_state = read_json(paths.state_file, required=False)
    input_mode = "explicit_auth_ref" if auth_ref else "detected_new_auth"
    added_backend_ids, selected_backend, selection_status = (
        classify_onboarded_backend_selection(
            before_registry=before_registry,
            after_registry=after_registry,
            explicit_auth_ref=auth_ref,
        )
    )
    selected_backend_id = (
        str(selected_backend.get("id")) if isinstance(selected_backend, dict) else ""
    )
    selected_backend_pool = (
        str(selected_backend.get("pool")) if isinstance(selected_backend, dict) else ""
    )
    before_active_backend_ids = routing_eligible_active_backend_ids(before_registry)
    after_active_backend_ids = routing_eligible_active_backend_ids(after_registry)
    before_selected_backend_ids = sorted(
        str(item) for item in before_state.get("selected_backend_ids", []) or []
    )
    after_selected_backend_ids = sorted(
        str(item) for item in after_state.get("selected_backend_ids", []) or []
    )
    active_routing_changed = (
        before_active_backend_ids != after_active_backend_ids
        or selected_backend_pool == "active"
        or before_selected_backend_ids != after_selected_backend_ids
        or (
            selected_backend_id
            and selected_backend_id in set(after_selected_backend_ids)
            and selected_backend_id not in set(before_selected_backend_ids)
        )
    )
    reserve_first_enforced = bool(selected_backend) and selected_backend_pool == "reserve"
    onboarding_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "input_mode": input_mode,
        "explicit_auth_ref": auth_ref or "",
        "new_backend_ids": added_backend_ids,
        "selected_backend_id": selected_backend_id,
        "selection_status": selection_status,
        "reserve_first_enforced": reserve_first_enforced,
        "auth_snapshot_before_login_status": str(
            auth_snapshot_before_login.get("status", "source_unavailable")
        ),
        "auth_snapshot_before_login_count": int(
            auth_snapshot_before_login.get("count", 0) or 0
        ),
        "auth_snapshot_before_login_digest": str(
            auth_snapshot_before_login.get(
                "digest", get_auth_inventory_entries_digest([])
            )
        ),
        "auth_snapshot_before_login_source": auth_snapshot_before_login.get("source", {}),
        "pool_after_onboarding": summarize_registry_pool_counts(after_registry),
        "validate_attempted": False,
        "validate_outcome": "not_attempted",
        "sync_attempted": False,
        "sync_outcome": "not_attempted",
        "status_observed": None,
        "external_command_exit_code": int(result.returncode),
        "external_command_status": "ok" if result.returncode == 0 else "nonzero",
        "active_routing_changed": active_routing_changed,
        "final_outcome": "pending_post_proof",
    }
    def build_onboard_payload(
        *,
        ok: bool,
        human_message: str,
        machine_error_code: str,
        liveness: str = "unknown",
        severity: str = "recoverable",
        operator_action: str = "none",
        exit_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload_extra = {
            "command": command[1:],
            "onboarding_result": onboarding_result,
        }
        if extra:
            payload_extra.update(extra)
        return build_command_payload(
            ok=ok,
            human_message=human_message,
            machine_error_code=machine_error_code,
            liveness=liveness,
            severity=severity,
            operator_action=operator_action,
            changed_files=detect_changed_files(
                before, runtime_write_surface_candidates(paths)
            ),
            extra=payload_extra,
            exit_code=exit_code,
        )

    if selection_status == "no_new_backend_detected":
        onboarding_result["final_outcome"] = (
            "import_failed" if result.returncode != 0 else "no_new_auth_detected"
        )
        return build_onboard_payload(
            ok=False,
            human_message=(
                "Account onboarding failed without producing a detectable new backend."
                if result.returncode != 0
                else "Onboarding did not produce a uniquely detectable new backend."
            ),
            machine_error_code=(
                "ONBOARD_FAILED"
                if result.returncode != 0
                else "ONBOARD_NO_NEW_BACKEND"
            ),
            operator_action="user_action",
            exit_code=result.returncode if result.returncode != 0 else None,
        )

    if selection_status != "selected_unique_backend":
        onboarding_result["final_outcome"] = "ambiguous_new_auth_detection"
        return build_onboard_payload(
            ok=False,
            human_message="Onboarding outcome is ambiguous and needs operator review.",
            machine_error_code="ONBOARD_AMBIGUOUS_BACKEND_SELECTION",
            operator_action="user_action",
        )

    if active_routing_changed:
        onboarding_result["final_outcome"] = "active_routing_changed"
        return build_onboard_payload(
            ok=False,
            human_message="Onboarding changed active routing, which is forbidden in the reserve-first lane.",
            machine_error_code="ONBOARD_ACTIVE_ROUTING_CHANGED",
            severity="fatal",
            operator_action="stop",
        )

    if not reserve_first_enforced:
        onboarding_result["final_outcome"] = "import_failed"
        return build_onboard_payload(
            ok=False,
            human_message="Onboarding did not leave the selected backend in reserve.",
            machine_error_code="ONBOARD_RESERVE_FIRST_VIOLATION",
            severity="fatal",
            operator_action="stop",
        )

    validate_payload = run_accounts_command(
        paths,
        ["validate", selected_backend_id],
        success_message="Account validation completed.",
        failure_message="Account validation failed.",
    )
    onboarding_result["validate_attempted"] = True
    onboarding_result["validate_outcome"] = (
        "ok" if validate_payload["status"] == "ok" else "failed"
    )
    if validate_payload["status"] != "ok":
        onboarding_result["final_outcome"] = "validate_failed"
        return build_onboard_payload(
            ok=False,
            human_message="Onboarding admitted the backend to reserve, but validate failed.",
            machine_error_code="ONBOARD_VALIDATE_FAILED",
            operator_action="user_action",
            exit_code=int(validate_payload.get("exit_code", 1) or 1),
            extra={
                "validate_result": {
                    "command_status": validate_payload["status"],
                    "machine_error_code": validate_payload["machine_error_code"],
                    "exit_code": validate_payload["exit_code"],
                }
            },
        )

    sync_payload: dict[str, Any] | None = None
    if no_sync:
        onboarding_result["sync_outcome"] = "skipped_by_flag"
    else:
        onboarding_result["sync_attempted"] = True
        sync_payload = run_sync(paths)
        onboarding_result["sync_outcome"] = (
            "ok" if sync_payload["status"] == "ok" else "failed"
        )
        if sync_payload["status"] != "ok":
            try:
                status_payload = summarize_status(paths)
                onboarding_result["status_observed"] = (
                    summarize_onboarding_status_observation(status_payload)
                )
            except RuntimeErrorInfo:
                onboarding_result["status_observed"] = None
            onboarding_result["final_outcome"] = "sync_failed"
            return build_onboard_payload(
                ok=False,
                human_message="Onboarding admitted the backend to reserve, but managed sync failed.",
                machine_error_code="ONBOARD_SYNC_FAILED",
                liveness=str(sync_payload.get("liveness", "unknown")),
                operator_action=str(sync_payload.get("operator_action", "retry")),
                exit_code=int(sync_payload.get("exit_code", 1) or 1),
                extra={
                    "sync_result": {
                        "command_status": sync_payload["status"],
                        "machine_error_code": sync_payload["machine_error_code"],
                        "exit_code": sync_payload["exit_code"],
                    }
                },
            )

    try:
        status_payload = summarize_status(paths)
        onboarding_result["status_observed"] = summarize_onboarding_status_observation(
            status_payload
        )
    except RuntimeErrorInfo as exc:
        onboarding_result["final_outcome"] = "status_failed"
        return build_onboard_payload(
            ok=False,
            human_message="Onboarding completed reserve admission, but status proof failed.",
            machine_error_code="ONBOARD_STATUS_FAILED",
            operator_action="retry",
            exit_code=exc.exit_code,
        )

    onboarding_result["final_outcome"] = (
        "explicit_auth_imported_to_reserve"
        if auth_ref
        else "reserve_only_success"
    )
    observed = onboarding_result["status_observed"] or {}
    return build_onboard_payload(
        ok=True,
        human_message=(
            "Account onboarding completed with reserve-first proof."
            if result.returncode == 0
            else "Account onboarding completed with reserve-first proof after external onboard exit non-zero."
        ),
        machine_error_code="OK",
        liveness=str(observed.get("liveness", "unknown")),
        severity="recoverable",
        operator_action="none",
        extra={
            "validate_result": {
                "command_status": validate_payload["status"],
                "machine_error_code": validate_payload["machine_error_code"],
                "exit_code": validate_payload["exit_code"],
            },
            "sync_result": (
                {
                    "command_status": sync_payload["status"],
                    "machine_error_code": sync_payload["machine_error_code"],
                    "exit_code": sync_payload["exit_code"],
                }
                if sync_payload is not None
                else {
                    "command_status": "skipped",
                    "machine_error_code": "ONBOARD_SYNC_SKIPPED",
                    "exit_code": 0,
                }
            ),
        },
    )


def export_diagnostics(paths: RuntimePaths) -> dict[str, Any]:
    registry = read_json(paths.registry_file)
    state = read_json(paths.state_file, required=False)
    export_dir = Path(tempfile.mkdtemp(prefix="wild-boar-proxy-diagnostics-"))
    redacted_registry = redact_evidence_value(registry)
    redacted_state = redact_evidence_value(state)

    (export_dir / "backend-registry.json").write_text(
        json.dumps(redacted_registry, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (export_dir / "supervisor-state.json").write_text(
        json.dumps(redacted_state, indent=2, ensure_ascii=True) + "\n",
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


def build_installer_default_registry_payload() -> dict[str, Any]:
    return {
        "schema_version": BACKEND_REGISTRY_SCHEMA_VERSION,
        "version": BACKEND_REGISTRY_SCHEMA_VERSION,
        "updated_at": now_iso(),
        "stable_default_backend_id": "",
        "pool_policy": {"active_min": 0, "active_target": 0, "reserve_target": 0},
        "backends": [],
    }


def build_installer_default_state_payload() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "version": 2,
        "status": "unknown",
        "effective_mode": "stable",
        "last_sync_at": "",
        "last_error": "",
        "selected_backend_ids": [],
        "managed_port": 8320,
        "current_proxy_url": "",
        "stable_default_backend_id": "",
        "active_count": 0,
        "reserve_count": 0,
        "retired_count": 0,
        "healthy_count": 0,
        "degraded_count": 0,
        "down_count": 0,
    }


def run_installer_init(paths: RuntimePaths) -> dict[str, Any]:
    before_state = snapshot_path_states(
        [
            paths.profile_dir,
            paths.managed_dir,
            paths.managed_dir / "bin",
            paths.registry_file,
            paths.state_file,
            paths.config_toml,
            paths.runtime_mode_file,
            paths.runtime_effective_mode_file,
        ]
    )
    with serialized_lock(paths):
        paths.profile_dir.mkdir(parents=True, exist_ok=True)
        paths.managed_dir.mkdir(parents=True, exist_ok=True)
        (paths.managed_dir / "bin").mkdir(parents=True, exist_ok=True)
        if not paths.runtime_mode_file.exists():
            write_text_atomic(paths.runtime_mode_file, "stable")
        if not paths.runtime_effective_mode_file.exists():
            write_text_atomic(paths.runtime_effective_mode_file, "stable")
        if not paths.registry_file.exists():
            write_json_atomic(paths.registry_file, build_installer_default_registry_payload())
        if not paths.state_file.exists():
            write_json_atomic(paths.state_file, build_installer_default_state_payload())
        if not paths.config_toml.exists():
            write_text_atomic(paths.config_toml, 'model = "gpt-5.3-codex"\nbase_url = "http://127.0.0.1:8318/v1"')
    changed_files = detect_changed_files_by_state(before_state, list(before_state.keys()))
    return build_command_payload(
        ok=True,
        human_message="Installer baseline initialization completed.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=changed_files,
        extra={
            "installer_result": {
                "status": "owner_path_emitted",
                "final_outcome": "baseline_initialized",
            }
        },
    )


def run_legacy_import(paths: RuntimePaths, source_dir_raw: str) -> dict[str, Any]:
    source_dir = Path(source_dir_raw).expanduser()
    write_targets = [
        paths.registry_file,
        paths.state_file,
        paths.config_toml,
        paths.runtime_mode_file,
        paths.runtime_effective_mode_file,
    ]
    before_state = snapshot_path_states(write_targets)
    legacy_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "source_dir": str(source_dir),
        "transaction_phase": "snapshot",
        "rollback_attempted": False,
        "rollback_outcome": "not_needed",
        "final_outcome": "pending",
    }
    if not source_dir.exists() or not source_dir.is_dir():
        legacy_result["final_outcome"] = "source_missing"
        return build_command_payload(
            ok=False,
            human_message="Legacy import source directory is missing.",
            machine_error_code="LEGACY_IMPORT_SOURCE_MISSING",
            liveness="unknown",
            severity="recoverable",
            operator_action="user_action",
            changed_files=[],
            extra={"legacy_import_result": legacy_result},
        )
    try:
        with serialized_lock(paths):
            legacy_result["transaction_phase"] = "stage"
            staged_registry = read_json(source_dir / "backend-registry.json")
            staged_state = read_json(source_dir / "supervisor-state.json")
            staged_config = read_text(source_dir / "config.toml")
            staged_mode = read_text(source_dir / "runtime-mode.txt", default="stable")
            staged_effective = read_text(
                source_dir / "runtime-effective-mode.txt", default=staged_mode
            )

            legacy_result["transaction_phase"] = "verify"
            if not isinstance(staged_registry.get("backends"), list):
                raise RuntimeErrorInfo(
                    "Legacy import registry backends must be a list.",
                    machine_error_code="LEGACY_IMPORT_VERIFY_FAILED",
                    operator_action="user_action",
                )
            if not isinstance(staged_state, dict):
                raise RuntimeErrorInfo(
                    "Legacy import state must be a JSON object.",
                    machine_error_code="LEGACY_IMPORT_VERIFY_FAILED",
                    operator_action="user_action",
                )

            legacy_result["transaction_phase"] = "switch"
            write_json_atomic(paths.registry_file, staged_registry)
            write_json_atomic(paths.state_file, staged_state)
            if staged_config:
                write_text_atomic(paths.config_toml, staged_config)
            write_text_atomic(paths.runtime_mode_file, staged_mode or "stable")
            write_text_atomic(paths.runtime_effective_mode_file, staged_effective or "stable")
    except RuntimeErrorInfo as exc:
        legacy_result["rollback_attempted"] = True
        legacy_result["transaction_phase"] = "rollback"
        for path, snapshot in before_state.items():
            restore_path_state(path, snapshot)
        legacy_result["rollback_outcome"] = "completed"
        legacy_result["final_outcome"] = "rollback_completed_after_failed_import"
        return build_command_payload(
            ok=False,
            human_message=exc.message,
            machine_error_code=exc.machine_error_code,
            liveness="unknown",
            severity=exc.severity,
            operator_action=exc.operator_action,
            changed_files=detect_changed_files_by_state(before_state, write_targets),
            extra={"legacy_import_result": legacy_result},
            exit_code=exc.exit_code,
        )
    legacy_result["final_outcome"] = "import_completed"
    return build_command_payload(
        ok=True,
        human_message="Legacy import completed.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=detect_changed_files_by_state(before_state, write_targets),
        extra={"legacy_import_result": legacy_result},
    )


def run_companion_reset(paths: RuntimePaths, *, uninstall: bool = False) -> dict[str, Any]:
    targets = [
        paths.managed_dir,
        paths.registry_file,
        paths.state_file,
        paths.managed_config_file,
        paths.config_toml,
        paths.runtime_mode_file,
        paths.runtime_effective_mode_file,
        paths.stable_runtime_generated_config_file,
        paths.launcher_script,
    ]
    before_state = snapshot_path_states(targets)
    reset_result: dict[str, Any] = {
        "status": "owner_path_emitted",
        "attempted": True,
        "uninstall_mode": uninstall,
        "auth_file_preserved": bool(paths.auth_file.exists()),
        "final_outcome": "pending",
    }
    with serialized_lock(paths):
        if paths.managed_dir.exists():
            shutil.rmtree(paths.managed_dir)
        for file_path in (
            paths.config_toml,
            paths.runtime_mode_file,
            paths.runtime_effective_mode_file,
            paths.stable_runtime_generated_config_file,
            paths.launcher_script,
        ):
            if file_path.exists():
                file_path.unlink()
        if uninstall and paths.profile_dir.exists() and paths.profile_dir.is_dir():
            try:
                next(paths.profile_dir.iterdir())
            except StopIteration:
                paths.profile_dir.rmdir()
    reset_result["auth_file_preserved"] = bool(paths.auth_file.exists())
    reset_result["final_outcome"] = "companion_data_removed"
    return build_command_payload(
        ok=True,
        human_message=(
            "Companion uninstall completed."
            if uninstall
            else "Companion reset completed."
        ),
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=detect_changed_files_by_state(before_state, targets),
        extra={"reset_result": reset_result},
    )
