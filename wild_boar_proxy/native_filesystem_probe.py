# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Owner-side helper for native filesystem isolation proof contours.

This module is intentionally narrow. It supports bounded evidence capture for
native custom-launch filesystem isolation without claiming window or routing
success.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .runtime import (
    RuntimePaths,
    build_repo_owned_default_launcher_script_text,
    write_text_atomic,
)
from .token_command import emit_local_token


DEFAULT_SHA256_SIZE_LIMIT = 5_000_000
DEFAULT_STARTUP_WAIT_SECONDS = 20.0
DEFAULT_SHUTDOWN_WAIT_SECONDS = 15.0
DEFAULT_IDLE_WINDOW_SECONDS = 3.0
DEFAULT_DEFAULT_USER_DATA_DIR = str(
    Path.home() / "Library" / "Application Support" / "Codex"
)
DEFAULT_CODEX_PROCESS_PATTERNS = (
    "/Applications/Codex.app/Contents/MacOS/Codex",
    "Codex Helper",
    "Contents/Resources/codex app-server",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _host_process_chain_contains_protected_codex(
    host_process_chain: list[dict[str, Any]],
) -> tuple[bool, bool]:
    codex_app_detected = any(
        "/Applications/Codex.app/Contents/MacOS/Codex" in entry.get("command", "")
        for entry in host_process_chain
    )
    codex_app_server_detected = any(
        "codex app-server" in entry.get("command", "") for entry in host_process_chain
    )
    return codex_app_detected, codex_app_server_detected


def classify_protected_codex_host_negative(
    host_process_chain: list[dict[str, Any]],
) -> dict[str, Any]:
    if not host_process_chain:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "HOST_CHAIN_UNPROVEN",
            "hosted_by_protected_codex_session": None,
            "protected_codex_ancestry_disproven": False,
            "codex_app_parent_detected": False,
            "codex_app_server_parent_detected": False,
            "host_process_chain_length": 0,
            "verdict": "protected_codex_host_chain_missing",
        }
    codex_app_detected, codex_app_server_detected = _host_process_chain_contains_protected_codex(
        host_process_chain
    )
    hosted_by_codex = codex_app_detected or codex_app_server_detected
    return {
        "captured_at_utc": utc_now(),
        "status": "ok" if not hosted_by_codex else "blocked",
        "reason_class": "" if not hosted_by_codex else "PROTECTED_CODEX_SESSION_DETECTED",
        "hosted_by_protected_codex_session": hosted_by_codex,
        "protected_codex_ancestry_disproven": not hosted_by_codex,
        "codex_app_parent_detected": codex_app_detected,
        "codex_app_server_parent_detected": codex_app_server_detected,
        "host_process_chain_length": len(host_process_chain),
        "executor_pid": host_process_chain[0].get("pid"),
        "executor_command": host_process_chain[0].get("command", ""),
        "verdict": (
            "protected_codex_host_negative_proven"
            if not hosted_by_codex
            else "protected_codex_host_detected"
        ),
    }


def collect_ambient_env_context(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    proxy_keys = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    )
    ambient_proxy_keys_present = {key: bool(env.get(key)) for key in proxy_keys}
    authority_keys = [
        key
        for key in (
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_ORG_ID",
            "WBP_AUTH_COMMAND_STAMP",
        )
        if env.get(key)
    ]
    wbp_token_command_path = env.get("WBP_AUTH_COMMAND_PATH", "")
    unexplained_authority_present = bool(
        env.get("OPENAI_API_KEY")
        or any(ambient_proxy_keys_present.values())
        or env.get("OPENAI_BASE_URL")
        or env.get("OPENAI_ORG_ID")
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "ambient_env_context",
        "status": "ok" if not unexplained_authority_present else "blocked",
        "reason_class": "" if not unexplained_authority_present else "AMBIENT_ENV_AUTHORITY_UNEXPLAINED",
        "ambient_codex_home": env.get("CODEX_HOME", ""),
        "ambient_home": env.get("HOME", ""),
        "ambient_openai_api_key_present": bool(env.get("OPENAI_API_KEY")),
        "ambient_proxy_keys_present": ambient_proxy_keys_present,
        "ambient_authority_keys_present": authority_keys,
        "wbp_token_command_path": wbp_token_command_path,
        "browser_authority_used": False,
        "consumer_launch_performed": False,
        "secret_value_recorded": False,
        "unexplained_authority_present": unexplained_authority_present,
    }


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "OPENAI_API_KEY",
    ):
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost,::1"
    env["no_proxy"] = "127.0.0.1,localhost,::1"
    return env


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_tree(root: Path, *, sha256_size_limit: int = DEFAULT_SHA256_SIZE_LIMIT) -> dict[str, Any]:
    root = root.expanduser()
    result: dict[str, Any] = {
        "root": str(root),
        "exists": root.exists(),
        "sha256_size_limit": sha256_size_limit,
        "entries": [],
    }
    if not root.exists():
        return result
    entries: list[dict[str, Any]] = []
    for path in sorted([root, *root.rglob("*")], key=lambda item: str(item)):
        relative = "." if path == root else str(path.relative_to(root))
        stat = path.stat()
        item: dict[str, Any] = {
            "relative_path": relative,
            "kind": "dir" if path.is_dir() else "file" if path.is_file() else "other",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
        if path.is_file() and stat.st_size <= sha256_size_limit:
            item["sha256"] = _sha256_file(path)
        entries.append(item)
    result["entries"] = entries
    result["entry_count"] = len(entries)
    return result


def diff_scans(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_entries = {
        entry["relative_path"]: entry for entry in before.get("entries", []) if isinstance(entry, dict)
    }
    after_entries = {
        entry["relative_path"]: entry for entry in after.get("entries", []) if isinstance(entry, dict)
    }
    created: list[str] = []
    deleted: list[str] = []
    changed: list[dict[str, Any]] = []
    unchanged: list[str] = []
    for relative_path in sorted(set(before_entries) | set(after_entries)):
        old = before_entries.get(relative_path)
        new = after_entries.get(relative_path)
        if old is None:
            created.append(relative_path)
            continue
        if new is None:
            deleted.append(relative_path)
            continue
        if old == new:
            unchanged.append(relative_path)
            continue
        changed.append(
            {
                "relative_path": relative_path,
                "before": old,
                "after": new,
            }
        )
    return {
        "created": created,
        "deleted": deleted,
        "changed": changed,
        "unchanged_count": len(unchanged),
        "created_count": len(created),
        "deleted_count": len(deleted),
        "changed_count": len(changed),
        "unchanged": unchanged[:100],
    }


def scan_protected_surfaces() -> dict[str, Any]:
    surfaces = {
        "codex_dir": Path.home() / ".codex",
        "default_app_support_codex": Path.home() / "Library" / "Application Support" / "Codex",
        "default_cache_codex": Path.home() / "Library" / "Caches" / "com.openai.codex",
        "default_httpstorage_codex": Path.home() / "Library" / "HTTPStorages" / "com.openai.codex",
    }
    return {
        "captured_at_utc": utc_now(),
        "surfaces": {name: scan_tree(path) for name, path in surfaces.items()},
    }


def diff_protected_surfaces(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_surfaces = before.get("surfaces", {})
    after_surfaces = after.get("surfaces", {})
    surface_results: dict[str, Any] = {}
    all_unchanged = True
    for name, old_scan in before_surfaces.items():
        new_scan = after_surfaces.get(name, {"root": "", "exists": False, "entries": []})
        diff = diff_scans(old_scan, new_scan)
        unchanged = (
            diff["created_count"] == 0
            and diff["deleted_count"] == 0
            and diff["changed_count"] == 0
        )
        if not unchanged:
            all_unchanged = False
        surface_results[name] = {
            "root": old_scan.get("root"),
            "unchanged": unchanged,
            "diff": diff,
        }
    return {
        "captured_at_utc": utc_now(),
        "all_protected_surfaces_unchanged": all_unchanged,
        "surfaces": surface_results,
    }


def _collect_codex_process_lines() -> list[str]:
    process = subprocess.run(
        ["pgrep", "-fal", "|".join(DEFAULT_CODEX_PROCESS_PATTERNS)],
        text=True,
        capture_output=True,
        check=False,
    )
    return [line for line in process.stdout.splitlines() if line.strip()]


def collect_codex_process_inventory(
    *,
    custom_user_data_dir: str,
    default_user_data_dir: str = DEFAULT_DEFAULT_USER_DATA_DIR,
) -> dict[str, Any]:
    lines = _collect_codex_process_lines()
    custom_lines = [line for line in lines if custom_user_data_dir in line]
    default_lines = [line for line in lines if default_user_data_dir in line]
    root_lines = [
        line
        for line in lines
        if "/Applications/Codex.app/Contents/MacOS/Codex" in line
    ]
    root_pids = sorted(
        int(line.split(" ", 1)[0])
        for line in root_lines
        if line.split(" ", 1)[0].isdigit()
    )
    return {
        "captured_at_utc": utc_now(),
        "line_count": len(lines),
        "sample": lines[:50],
        "custom_user_data_dir": custom_user_data_dir,
        "default_user_data_dir": default_user_data_dir,
        "custom_process_lines": custom_lines,
        "custom_process_count": len(custom_lines),
        "default_process_lines": default_lines,
        "default_process_count": len(default_lines),
        "root_app_pids": root_pids,
    }


def classify_current_codex_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_roots = set(before.get("root_app_pids", []))
    after_roots = set(after.get("root_app_pids", []))
    before_default = set(before.get("default_process_lines", []))
    after_default = set(after.get("default_process_lines", []))
    missing_root_pids = sorted(before_roots - after_roots)
    missing_default_lines = sorted(before_default - after_default)
    touched = bool(missing_root_pids)
    return {
        "captured_at_utc": utc_now(),
        "before_root_app_pids": sorted(before_roots),
        "after_root_app_pids": sorted(after_roots),
        "missing_root_app_pids": missing_root_pids,
        "missing_default_process_lines": missing_default_lines[:50],
        "default_helper_delta_present": bool(missing_default_lines),
        "current_codex_touched": touched,
        "delta_classification": "touched_or_restarted" if touched else "baseline_preserved",
    }


def classify_user_data_dir_respected(
    *,
    custom_process_observed: bool,
    owned_writes_present: bool,
    protected_surfaces_changed: bool,
) -> dict[str, Any]:
    if protected_surfaces_changed:
        return {
            "status": "blocked",
            "reason_class": "DEFAULT_PROTECTED_SURFACES_CHANGED",
            "user_data_dir_respected": False,
        }
    if custom_process_observed and owned_writes_present:
        return {
            "status": "ok",
            "reason_class": "",
            "user_data_dir_respected": True,
        }
    return {
        "status": "blocked",
        "reason_class": "WRITE_ATTRIBUTION_AMBIGUOUS",
        "user_data_dir_respected": False,
    }


def remove_tree_with_retry(path: Path, *, attempts: int = 12, delay_seconds: float = 0.5) -> str:
    last_error = ""
    for _ in range(attempts):
        if not path.exists():
            return ""
        try:
            shutil.rmtree(path)
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(delay_seconds)
            continue
        if not path.exists():
            return ""
    return last_error or "tree_still_present"


def terminate_custom_processes(custom_user_data_dir: str) -> dict[str, Any]:
    initial = collect_codex_process_inventory(custom_user_data_dir=custom_user_data_dir)
    custom_pids = sorted(
        {
            int(line.split(" ", 1)[0])
            for line in initial.get("custom_process_lines", [])
            if line.split(" ", 1)[0].isdigit()
        }
    )
    for pid in custom_pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    deadline = time.time() + DEFAULT_SHUTDOWN_WAIT_SECONDS
    while time.time() < deadline:
        inventory = collect_codex_process_inventory(custom_user_data_dir=custom_user_data_dir)
        if inventory["custom_process_count"] == 0:
            return {
                "captured_at_utc": utc_now(),
                "initial_custom_pids": custom_pids,
                "custom_processes_gone": True,
                "final_inventory": inventory,
            }
        time.sleep(0.5)
    for pid in custom_pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue
    final_inventory = collect_codex_process_inventory(custom_user_data_dir=custom_user_data_dir)
    return {
        "captured_at_utc": utc_now(),
        "initial_custom_pids": custom_pids,
        "custom_processes_gone": final_inventory["custom_process_count"] == 0,
        "final_inventory": final_inventory,
    }


def _token_json_payload(token_value: str) -> dict[str, str]:
    return {"OPENAI_API_KEY": token_value}


def _cli_proxy_api_key() -> str:
    config_path = Path.home() / ".cli-proxy-api" / "config.yaml"
    if not config_path.exists():
        return ""
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and "sk-cliproxy" in stripped:
            return stripped[2:].strip().strip("\"'")
    return ""


def build_provider_config(*, endpoint: str, model: str, auth_command_path: Path) -> str:
    cli_key = _cli_proxy_api_key()
    if cli_key:
        return (
            f'model = "{model}"\n'
            'model_provider = "wbp"\n'
            'approval_policy = "never"\n'
            'sandbox_mode = "read-only"\n\n'
            "[model_providers.wbp]\n"
            'name = "Wild Boar Proxy"\n'
            f'base_url = "{endpoint}"\n'
            'wire_api = "responses"\n'
            "requires_openai_auth = false\n"
            f'experimental_bearer_token = "{cli_key}"\n'
        )
    auth_command = str(auth_command_path.resolve())
    return (
        f'model = "{model}"\n'
        'model_provider = "wbp"\n'
        'approval_policy = "never"\n'
        'sandbox_mode = "read-only"\n\n'
        "[model_providers.wbp]\n"
        'name = "Wild Boar Proxy"\n'
        f'base_url = "{endpoint}"\n'
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n\n"
        "[model_providers.wbp.auth]\n"
        f'command = "{auth_command}"\n'
    )


@dataclass
class NativeProbeLayout:
    tmp_root: Path
    profile_dir: Path
    launcher_path: Path
    launcher_stdout: Path
    launcher_stderr: Path
    custom_user_data_dir: Path
    custom_home_dir: Path
    custom_codex_home: Path
    custom_tmp_dir: Path


def create_native_probe_layout(tmp_root: Path) -> NativeProbeLayout:
    profile_dir = tmp_root / "profile"
    return NativeProbeLayout(
        tmp_root=tmp_root,
        profile_dir=profile_dir,
        launcher_path=profile_dir / "codex-custom-launch.sh",
        launcher_stdout=tmp_root / "launcher.stdout.log",
        launcher_stderr=tmp_root / "launcher.stderr.log",
        custom_user_data_dir=profile_dir / "electron-user-data",
        custom_home_dir=profile_dir / "home",
        custom_codex_home=profile_dir,
        custom_tmp_dir=profile_dir / "tmp",
    )


def materialize_probe_profile(
    *,
    layout: NativeProbeLayout,
    endpoint: str,
    model: str,
    auth_command_path: Path,
    local_token: str,
) -> dict[str, Any]:
    layout.profile_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        layout.profile_dir / "config.toml",
        build_provider_config(endpoint=endpoint, model=model, auth_command_path=auth_command_path),
    )
    write_text_atomic(
        layout.profile_dir / "auth.json",
        json.dumps(_token_json_payload(local_token), sort_keys=True) + "\n",
    )
    write_text_atomic(
        layout.launcher_path,
        build_repo_owned_default_launcher_script_text() + "\n",
    )
    layout.launcher_path.chmod(0o755)
    return {
        "profile_dir": str(layout.profile_dir),
        "launcher_path": str(layout.launcher_path),
        "config_path": str(layout.profile_dir / "config.toml"),
        "auth_path": str(layout.profile_dir / "auth.json"),
        "custom_user_data_dir": str(layout.custom_user_data_dir),
        "custom_home_dir": str(layout.custom_home_dir),
        "custom_tmp_dir": str(layout.custom_tmp_dir),
    }


def launch_native_candidate(
    *,
    repo_root: Path,
    layout: NativeProbeLayout,
    real_runtime_paths: RuntimePaths,
    startup_wait_seconds: float = DEFAULT_STARTUP_WAIT_SECONDS,
) -> dict[str, Any]:
    env = clean_env()
    env.update(
        {
            "WBP_PROFILE_DIR": str(layout.profile_dir),
            "WBP_MANAGED_DIR": str(real_runtime_paths.managed_dir),
            "WBP_STABLE_CONFIG": str(real_runtime_paths.stable_config),
            "WBP_PYTHON_BIN": sys.executable,
        }
    )
    stdout_handle = layout.launcher_stdout.open("w", encoding="utf-8")
    stderr_handle = layout.launcher_stderr.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(layout.launcher_path), "desktop"],
        cwd=str(repo_root),
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        start_new_session=True,
        text=True,
    )
    custom_observed = False
    deadline = time.time() + startup_wait_seconds
    last_inventory = collect_codex_process_inventory(
        custom_user_data_dir=str(layout.custom_user_data_dir)
    )
    while time.time() < deadline:
        inventory = collect_codex_process_inventory(
            custom_user_data_dir=str(layout.custom_user_data_dir)
        )
        last_inventory = inventory
        if inventory["custom_process_count"] > 0:
            custom_observed = True
            break
        if process.poll() is not None:
            break
        time.sleep(0.5)
    stdout_handle.close()
    stderr_handle.close()
    return {
        "captured_at_utc": utc_now(),
        "launcher_pid": process.pid,
        "launcher_exit_code_early": process.poll(),
        "custom_process_observed": custom_observed,
        "startup_inventory": last_inventory,
        "launcher_stdout_path": str(layout.launcher_stdout),
        "launcher_stderr_path": str(layout.launcher_stderr),
        "launcher_stdout_size": layout.launcher_stdout.stat().st_size if layout.launcher_stdout.exists() else 0,
        "launcher_stderr_size": layout.launcher_stderr.stat().st_size if layout.launcher_stderr.exists() else 0,
    }


def run_native_filesystem_probe(
    *,
    repo_root: Path,
    evidence_dir: Path,
    endpoint: str,
    model: str,
) -> dict[str, Any]:
    real_runtime_paths = RuntimePaths.from_env()
    local_token = emit_local_token(real_runtime_paths)
    tmp_root = Path(tempfile.mkdtemp(prefix="wbp-native-fs-", dir="/tmp"))
    layout = create_native_probe_layout(tmp_root)
    materialized = materialize_probe_profile(
        layout=layout,
        endpoint=endpoint,
        model=model,
        auth_command_path=repo_root / "wbp_codex_auth_command.py",
        local_token=local_token,
    )
    before_process = collect_codex_process_inventory(
        custom_user_data_dir=str(layout.custom_user_data_dir)
    )
    before_surfaces = scan_protected_surfaces()
    launch_result = launch_native_candidate(
        repo_root=repo_root,
        layout=layout,
        real_runtime_paths=real_runtime_paths,
    )
    owned_scan = scan_tree(layout.profile_dir)
    termination = terminate_custom_processes(str(layout.custom_user_data_dir))
    after_surfaces = scan_protected_surfaces()
    after_process = collect_codex_process_inventory(
        custom_user_data_dir=str(layout.custom_user_data_dir)
    )
    protected_diff = diff_protected_surfaces(before_surfaces, after_surfaces)
    current_delta = classify_current_codex_delta(before_process, after_process)
    user_data_dir_result = classify_user_data_dir_respected(
        custom_process_observed=launch_result["custom_process_observed"],
        owned_writes_present=bool(owned_scan.get("entry_count", 0) > 1),
        protected_surfaces_changed=not protected_diff["all_protected_surfaces_unchanged"],
    )
    cleanup_error = remove_tree_with_retry(tmp_root)
    cleanup_packet = {
        "captured_at_utc": utc_now(),
        "tmp_root": str(tmp_root),
        "tmp_root_removed": not tmp_root.exists(),
        "cleanup_error": cleanup_error,
        "termination": termination,
    }
    packet = {
        "captured_at_utc": utc_now(),
        "status": "ok"
        if (
            protected_diff["all_protected_surfaces_unchanged"]
            and not current_delta["current_codex_touched"]
            and user_data_dir_result["status"] == "ok"
            and cleanup_packet["tmp_root_removed"]
        )
        else "blocked",
        "machine_error_code": "OK"
        if (
            protected_diff["all_protected_surfaces_unchanged"]
            and not current_delta["current_codex_touched"]
            and user_data_dir_result["status"] == "ok"
            and cleanup_packet["tmp_root_removed"]
        )
        else user_data_dir_result["reason_class"] or "NATIVE_FILESYSTEM_ISOLATION_BLOCKED",
        "materialized_profile": materialized,
        "current_codex_running_state_before": before_process,
        "current_codex_running_state_after": after_process,
        "current_codex_delta": current_delta,
        "protected_surface_recursive_before": before_surfaces,
        "protected_surface_recursive_after": after_surfaces,
        "protected_surface_recursive_diff": protected_diff,
        "custom_profile_write_inventory": owned_scan,
        "launch_result": launch_result,
        "user_data_dir_respected_packet": user_data_dir_result,
        "cleanup_reversibility_packet": cleanup_packet,
        "secret_value_recorded": False,
    }
    json_write(evidence_dir / "live_native_filesystem_probe_packet.json", packet)
    return packet


def run_idle_baseline_window(
    *,
    sleep_seconds: float = DEFAULT_IDLE_WINDOW_SECONDS,
) -> dict[str, Any]:
    before_process = collect_codex_process_inventory(
        custom_user_data_dir="/tmp/nonexistent-custom-user-data"
    )
    before_surfaces = scan_protected_surfaces()
    time.sleep(sleep_seconds)
    after_surfaces = scan_protected_surfaces()
    after_process = collect_codex_process_inventory(
        custom_user_data_dir="/tmp/nonexistent-custom-user-data"
    )
    protected_diff = diff_protected_surfaces(before_surfaces, after_surfaces)
    current_delta = classify_current_codex_delta(before_process, after_process)
    return {
        "captured_at_utc": utc_now(),
        "sleep_seconds": sleep_seconds,
        "custom_launch_observed": False,
        "current_codex_running_state_before": before_process,
        "current_codex_running_state_after": after_process,
        "current_codex_delta": current_delta,
        "protected_surface_recursive_before": before_surfaces,
        "protected_surface_recursive_after": after_surfaces,
        "protected_surface_recursive_diff": protected_diff,
        "status": "ok",
    }


def summarize_idle_baseline_windows(windows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(windows) < 2:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "INSUFFICIENT_OBSERVATION",
            "final_verdict": "INSUFFICIENT_OBSERVATION",
            "quiescent_current_codex_precondition_required": False,
            "drift_repeatability": "insufficient",
            "window_count": len(windows),
        }

    any_root_touched = False
    changed_surfaces_by_window: list[dict[str, list[str]]] = []
    windows_with_any_drift = 0
    windows_all_unchanged = 0
    repeated_surface_drift = False
    repeated_path_drift = False
    previous_surface_set: set[str] | None = None
    previous_path_set: set[tuple[str, str]] | None = None

    for window in windows:
        current_delta = window.get("current_codex_delta", {})
        if current_delta.get("current_codex_touched"):
            any_root_touched = True
        protected_diff = window.get("protected_surface_recursive_diff", {})
        surfaces = protected_diff.get("surfaces", {})
        changed_map: dict[str, list[str]] = {}
        current_surface_set: set[str] = set()
        current_path_set: set[tuple[str, str]] = set()
        for surface_name, payload in surfaces.items():
            diff = payload.get("diff", {})
            changed_paths = [entry["relative_path"] for entry in diff.get("changed", [])]
            created_paths = [entry for entry in diff.get("created", []) if isinstance(entry, str)]
            deleted_paths = [entry for entry in diff.get("deleted", []) if isinstance(entry, str)]
            all_changed_paths = sorted(changed_paths + created_paths + deleted_paths)
            if all_changed_paths:
                changed_map[surface_name] = all_changed_paths
                current_surface_set.add(surface_name)
                current_path_set.update((surface_name, path) for path in all_changed_paths)
        changed_surfaces_by_window.append(changed_map)
        if changed_map:
            windows_with_any_drift += 1
        else:
            windows_all_unchanged += 1
        if previous_surface_set is not None and current_surface_set & previous_surface_set:
            repeated_surface_drift = True
        if previous_path_set is not None and current_path_set & previous_path_set:
            repeated_path_drift = True
        previous_surface_set = current_surface_set
        previous_path_set = current_path_set

    if any_root_touched:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "INSUFFICIENT_OBSERVATION",
            "final_verdict": "INSUFFICIENT_OBSERVATION",
            "quiescent_current_codex_precondition_required": False,
            "drift_repeatability": "insufficient",
            "window_count": len(windows),
            "window_changed_surfaces": changed_surfaces_by_window,
            "current_codex_root_baseline_preserved": False,
        }

    if windows_with_any_drift == 0:
        final_verdict = "ACTIVE_CURRENT_CODEX_BASELINE_STABLE"
        drift_repeatability = "sporadic"
        quiescent_required = False
    elif windows_with_any_drift >= 2 and (repeated_surface_drift or repeated_path_drift):
        final_verdict = "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE"
        drift_repeatability = "repeated"
        quiescent_required = True
    elif windows_with_any_drift >= 2:
        final_verdict = "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE"
        drift_repeatability = "sporadic"
        quiescent_required = True
    else:
        final_verdict = "ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE"
        drift_repeatability = "sporadic"
        quiescent_required = True

    return {
        "captured_at_utc": utc_now(),
        "status": "ok",
        "reason_class": "",
        "final_verdict": final_verdict,
        "quiescent_current_codex_precondition_required": quiescent_required,
        "drift_repeatability": drift_repeatability,
        "window_count": len(windows),
        "windows_with_any_drift": windows_with_any_drift,
        "windows_all_unchanged": windows_all_unchanged,
        "repeated_surface_drift": repeated_surface_drift,
        "repeated_path_drift": repeated_path_drift,
        "window_changed_surfaces": changed_surfaces_by_window,
        "current_codex_root_baseline_preserved": True,
    }


def classify_quiescent_current_codex_precondition(
    inventory: dict[str, Any],
) -> dict[str, Any]:
    root_pids = inventory.get("root_app_pids", [])
    default_process_count = int(inventory.get("default_process_count", 0) or 0)
    custom_process_count = int(inventory.get("custom_process_count", 0) or 0)
    root_present = bool(root_pids)
    default_processes_present = default_process_count > 0
    quiescent = not root_present and not default_processes_present
    failures: list[str] = []
    if root_present:
        failures.append("ROOT_APP_PID_PRESENT")
    if default_processes_present:
        failures.append("DEFAULT_CODEX_PROCESS_PRESENT")
    if custom_process_count > 0:
        failures.append("CUSTOM_PROCESS_PRESENT_DURING_PRECONDITION_CHECK")
    return {
        "captured_at_utc": utc_now(),
        "status": "ok" if quiescent else "blocked",
        "reason_class": "" if quiescent else "CURRENT_CODEX_NOT_QUIESCENT",
        "quiescent_current_codex_precondition_satisfied": quiescent,
        "root_app_pid_present": root_present,
        "default_codex_process_present": default_processes_present,
        "custom_process_present": custom_process_count > 0,
        "root_app_pids": root_pids,
        "default_process_count": default_process_count,
        "custom_process_count": custom_process_count,
        "precondition_failures": failures,
        "inventory": inventory,
    }


def classify_quiescent_handoff_admission(
    *,
    operator_action_performed: bool,
    quiescent_precondition_packet: dict[str, Any],
    host_process_chain: list[dict[str, Any]],
) -> dict[str, Any]:
    codex_app_detected, codex_app_server_detected = _host_process_chain_contains_protected_codex(
        host_process_chain
    )
    hosted_by_codex = codex_app_detected or codex_app_server_detected
    quiescent_verified = bool(
        quiescent_precondition_packet.get("quiescent_current_codex_precondition_satisfied")
    )
    if hosted_by_codex:
        return {
            "captured_at_utc": utc_now(),
            "status": "ok",
            "reason_class": "",
            "operator_action_required": True,
            "operator_action_performed": operator_action_performed,
            "quiescent_precondition_verified": quiescent_verified,
            "same_thread_admissible": False,
            "fresh_context_required": True,
            "hosted_by_protected_codex_session": True,
            "verdict": "QUIESCENT_HANDOFF_REQUIRES_FRESH_CONTEXT",
        }
    if not operator_action_performed:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "QUIESCENT_HANDOFF_NOT_ADMITTED",
            "operator_action_required": True,
            "operator_action_performed": False,
            "quiescent_precondition_verified": quiescent_verified,
            "same_thread_admissible": False,
            "fresh_context_required": hosted_by_codex,
            "hosted_by_protected_codex_session": hosted_by_codex,
            "verdict": "operator_action_missing",
        }
    if quiescent_verified and not hosted_by_codex:
        return {
            "captured_at_utc": utc_now(),
            "status": "ok",
            "reason_class": "",
            "operator_action_required": True,
            "operator_action_performed": True,
            "quiescent_precondition_verified": True,
            "same_thread_admissible": True,
            "fresh_context_required": False,
            "hosted_by_protected_codex_session": False,
            "verdict": "QUIESCENT_HANDOFF_ADMISSIBLE",
        }
    return {
        "captured_at_utc": utc_now(),
        "status": "blocked",
        "reason_class": "QUIESCENT_HANDOFF_NOT_ADMITTED",
        "operator_action_required": True,
        "operator_action_performed": operator_action_performed,
        "quiescent_precondition_verified": quiescent_verified,
        "same_thread_admissible": False,
        "fresh_context_required": False,
        "hosted_by_protected_codex_session": False,
        "verdict": "quiescent_unverified",
    }


def classify_fresh_context_entry(
    *,
    host_process_chain: list[dict[str, Any]],
    quiescent_precondition_packet: dict[str, Any],
) -> dict[str, Any]:
    codex_app_detected, codex_app_server_detected = _host_process_chain_contains_protected_codex(
        host_process_chain
    )
    hosted_by_codex = codex_app_detected or codex_app_server_detected
    quiescent_verified = bool(
        quiescent_precondition_packet.get("quiescent_current_codex_precondition_satisfied")
    )
    if hosted_by_codex:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "FRESH_CONTEXT_NOT_ESTABLISHED",
            "fresh_context_verified": False,
            "hosted_by_protected_codex_session": True,
            "quiescent_precondition_verified": quiescent_verified,
            "phase7_retry_admissible": False,
            "verdict": "fresh_context_still_hosted_by_protected_codex",
        }
    if not quiescent_verified:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "QUIESCENT_PRECONDITION_STILL_FAILED",
            "fresh_context_verified": True,
            "hosted_by_protected_codex_session": False,
            "quiescent_precondition_verified": False,
            "phase7_retry_admissible": False,
            "verdict": "fresh_context_present_but_quiescent_precondition_failed",
        }
    return {
        "captured_at_utc": utc_now(),
        "status": "ok",
        "reason_class": "",
        "fresh_context_verified": True,
        "hosted_by_protected_codex_session": False,
        "quiescent_precondition_verified": True,
        "phase7_retry_admissible": True,
        "verdict": "FRESH_CONTEXT_ENTRY_ADMISSIBLE",
    }


def classify_fresh_context_acquisition(
    *,
    operator_action_performed: bool,
    fresh_context_entry_packet: dict[str, Any],
) -> dict[str, Any]:
    if not operator_action_performed:
        return {
            "captured_at_utc": utc_now(),
            "status": "blocked",
            "reason_class": "FRESH_CONTEXT_ACQUISITION_NOT_ADMITTED",
            "operator_action_required": True,
            "operator_action_performed": False,
            "fresh_context_verified": bool(
                fresh_context_entry_packet.get("fresh_context_verified")
            ),
            "phase7_retry_admissible": False,
            "verdict": "operator_mediated_fresh_context_not_provided",
        }
    if fresh_context_entry_packet.get("status") == "ok":
        return {
            "captured_at_utc": utc_now(),
            "status": "ok",
            "reason_class": "",
            "operator_action_required": True,
            "operator_action_performed": True,
            "fresh_context_verified": bool(
                fresh_context_entry_packet.get("fresh_context_verified")
            ),
            "phase7_retry_admissible": bool(
                fresh_context_entry_packet.get("phase7_retry_admissible")
            ),
            "verdict": "FRESH_CONTEXT_ENTRY_ADMISSIBLE",
        }
    return {
        "captured_at_utc": utc_now(),
        "status": "blocked",
        "reason_class": fresh_context_entry_packet.get(
            "reason_class", "FRESH_CONTEXT_NOT_ESTABLISHED"
        ),
        "operator_action_required": True,
        "operator_action_performed": True,
        "fresh_context_verified": bool(
            fresh_context_entry_packet.get("fresh_context_verified")
        ),
        "phase7_retry_admissible": False,
        "verdict": fresh_context_entry_packet.get(
            "verdict", "fresh_context_verification_failed"
        ),
    }


def classify_external_detached_context_outcome(
    *,
    host_negative_packet: dict[str, Any],
    precondition_packet: dict[str, Any],
    acquisition_packet: dict[str, Any],
    ambient_env_packet: dict[str, Any],
) -> dict[str, Any]:
    host_proven = bool(host_negative_packet.get("protected_codex_ancestry_disproven"))
    fresh_context_verified = bool(acquisition_packet.get("fresh_context_verified"))
    quiescent_satisfied = bool(
        precondition_packet.get("quiescent_current_codex_precondition_satisfied")
    )
    phase7_admissible = bool(acquisition_packet.get("phase7_retry_admissible"))
    ambient_env_ok = ambient_env_packet.get("status") == "ok"

    blocked_reason = (
        acquisition_packet.get("reason_class")
        or precondition_packet.get("reason_class")
        or host_negative_packet.get("reason_class")
        or ambient_env_packet.get("reason_class")
        or ""
    )

    if not host_proven or not fresh_context_verified:
        final_verdict = "EXTERNAL_DETACHED_CONTEXT_NOT_PROVEN"
        status = "blocked"
        reason_class = blocked_reason
    elif phase7_admissible and quiescent_satisfied:
        final_verdict = "EXTERNAL_DETACHED_CONTEXT_PROVEN_AND_PHASE7_ADMISSIBLE"
        status = "ok"
        reason_class = ""
    elif not quiescent_satisfied or not phase7_admissible:
        final_verdict = "EXTERNAL_DETACHED_CONTEXT_PROVEN_BUT_PHASE7_NOT_ADMISSIBLE"
        status = "blocked"
        reason_class = blocked_reason
    else:
        final_verdict = "EXTERNAL_DETACHED_CONTEXT_PROVEN"
        status = "ok"
        reason_class = ""

    return {
        "captured_at_utc": utc_now(),
        "status": status,
        "final_verdict": final_verdict,
        "reason_class": reason_class,
        "hosted_by_protected_codex_session": host_negative_packet.get(
            "hosted_by_protected_codex_session"
        ),
        "protected_codex_ancestry_disproven": host_negative_packet.get(
            "protected_codex_ancestry_disproven"
        ),
        "fresh_context_verified": fresh_context_verified,
        "operator_action_required": acquisition_packet.get("operator_action_required"),
        "operator_action_performed": acquisition_packet.get("operator_action_performed"),
        "quiescent_current_codex_precondition_satisfied": quiescent_satisfied,
        "phase7_retry_admissible": phase7_admissible,
        "ambient_env_ok": ambient_env_ok,
        "consumer_launch_performed": False,
        "native_launch_performed": False,
        "filesystem_retry_attempted": False,
        "protected_surface_mutation_performed": False,
        "forbidden_claims_present": False,
    }
