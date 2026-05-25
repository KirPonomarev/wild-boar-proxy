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
from typing import Any

from .runtime import (
    RuntimePaths,
    build_repo_owned_default_launcher_script_text,
    write_text_atomic,
)
from .token_command import emit_local_token


DEFAULT_SHA256_SIZE_LIMIT = 5_000_000
DEFAULT_STARTUP_WAIT_SECONDS = 20.0
DEFAULT_SHUTDOWN_WAIT_SECONDS = 15.0
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


def build_provider_config(*, endpoint: str, model: str, auth_command_path: Path) -> str:
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
