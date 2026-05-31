# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dry-run validation for Persistent Custom Codex launcher configuration."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .native_filesystem_probe import (
    PROTECTED_SURFACE_PATHS,
    default_persistent_custom_profile_paths,
)


PROFILE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


@dataclass(frozen=True)
class PersistentLauncherDryRunConfig:
    profile_mode: str
    persistent_profile_id: str
    persistent_profile_root: Path
    codex_home: Path
    user_data_dir: Path
    home_dir: Path
    tmp_dir: Path
    runtime_tmp_dir: Path
    launcher_path: Path
    app_path: Path = Path("/Applications/Codex.app")
    browser_client_path_authority: bool = False
    remote_client_path_authority: bool = False
    client_model_provider_authority: bool = False
    silent_fallback_to_ephemeral_allowed: bool = False
    original_codex_profile_dependency: bool = False
    original_codex_profile_mutation_allowed: bool = False
    cleanup_execution_allowed: bool = False
    backup_export_execution_allowed: bool = False
    persistent_profile_state_write_allowed: bool = False
    live_execution_allowed: bool = False
    lock_policy: str = "single_writer_only"


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        _resolved(path).relative_to(_resolved(parent))
        return True
    except ValueError:
        return False


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def default_persistent_launcher_dry_run_config(
    *,
    profile_id: str = "wbp-custom-main",
    base_dir: Path | None = None,
) -> PersistentLauncherDryRunConfig:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    return PersistentLauncherDryRunConfig(
        profile_mode="persistent_custom",
        persistent_profile_id=profile_id,
        persistent_profile_root=Path(paths["persistent_profile_root"]),
        codex_home=Path(paths["codex_home"]),
        user_data_dir=Path(paths["user_data_dir"]),
        home_dir=Path(paths["home_dir"]),
        tmp_dir=Path(paths["tmp_dir"]),
        runtime_tmp_dir=Path(paths["runtime_tmp_dir"]),
        launcher_path=Path(paths["launcher_path"]),
    )


def render_persistent_launcher_dry_run_command(
    config: PersistentLauncherDryRunConfig,
) -> dict[str, Any]:
    argv = [
        "open",
        "-n",
        str(_resolved(config.app_path)),
        "--args",
        "--user-data-dir",
        str(_resolved(config.user_data_dir)),
    ]
    env = {
        "CODEX_HOME": str(_resolved(config.codex_home)),
        "HOME": str(_resolved(config.home_dir)),
        "TMPDIR": str(_lexical_absolute(config.runtime_tmp_dir)),
        "WBP_RUNTIME_TMPDIR": str(_lexical_absolute(config.runtime_tmp_dir)),
        "WBP_PROFILE_MODE": config.profile_mode,
        "WBP_PERSISTENT_PROFILE_ID": config.persistent_profile_id,
    }
    return {
        "argv": argv,
        "argv_sha256": _sha256_json(argv),
        "env": env,
        "env_sha256": _sha256_json(env),
        "launcher_path": str(_resolved(config.launcher_path)),
        "command_executed": False,
        "native_launch_attempted": False,
        "custom_app_launch_attempted": False,
        "dry_run_only": True,
    }


def validate_persistent_launcher_dry_run_config(
    config: PersistentLauncherDryRunConfig,
) -> dict[str, Any]:
    failed: list[str] = []
    profile_root = _resolved(config.persistent_profile_root)
    codex_home = _resolved(config.codex_home)
    user_data_dir = _resolved(config.user_data_dir)
    home_dir = _resolved(config.home_dir)
    tmp_dir = _resolved(config.tmp_dir)
    runtime_tmp_dir = _lexical_absolute(config.runtime_tmp_dir)
    launcher_path = _resolved(config.launcher_path)

    if config.profile_mode != "persistent_custom":
        failed.append("profile_mode_must_be_persistent_custom")
    if not PROFILE_ID_PATTERN.fullmatch(config.persistent_profile_id):
        failed.append("persistent_profile_id_invalid")
    if codex_home != profile_root:
        failed.append("codex_home_must_equal_persistent_profile_root")
    expected_children = {
        "user_data_dir": user_data_dir,
        "home_dir": home_dir,
        "tmp_dir": tmp_dir,
        "launcher_path": launcher_path,
    }
    for name, path in expected_children.items():
        if not _path_is_relative_to(path, profile_root):
            failed.append(f"{name}_must_be_under_persistent_profile_root")
    protected_overlap = [
        name
        for name, protected in PROTECTED_SURFACE_PATHS.items()
        if any(
            _path_is_relative_to(path, protected)
            for path in (profile_root, codex_home, user_data_dir, home_dir, tmp_dir, launcher_path)
        )
    ]
    if protected_overlap:
        failed.append("persistent_paths_must_not_overlap_original_codex_surfaces")
    if not _lexical_absolute(runtime_tmp_dir).is_relative_to(_lexical_absolute(Path("/tmp"))):
        failed.append("runtime_tmp_dir_must_be_under_tmp_root")
    socket_candidate = runtime_tmp_dir / "codex-ipc" / "ipc-501.sock"
    if len(str(socket_candidate)) >= 104:
        failed.append("runtime_tmp_dir_socket_path_too_long")
    if config.browser_client_path_authority:
        failed.append("browser_client_path_authority_forbidden")
    if config.remote_client_path_authority:
        failed.append("remote_client_path_authority_forbidden")
    if config.client_model_provider_authority:
        failed.append("client_model_provider_authority_forbidden")
    if config.silent_fallback_to_ephemeral_allowed:
        failed.append("silent_persistent_to_ephemeral_fallback_forbidden")
    if config.original_codex_profile_dependency:
        failed.append("original_codex_profile_dependency_forbidden")
    if config.original_codex_profile_mutation_allowed:
        failed.append("original_codex_profile_mutation_forbidden")
    if config.cleanup_execution_allowed:
        failed.append("cleanup_execution_forbidden_in_dry_run")
    if config.backup_export_execution_allowed:
        failed.append("backup_export_execution_forbidden_in_dry_run")
    if config.persistent_profile_state_write_allowed:
        failed.append("persistent_profile_state_write_forbidden_in_dry_run")
    if config.live_execution_allowed:
        failed.append("live_execution_forbidden_in_dry_run")
    if config.lock_policy != "single_writer_only":
        failed.append("lock_policy_must_be_single_writer_only")

    return {
        "status": "ok" if not failed else "blocked",
        "failed_checks": failed,
        "profile_mode": config.profile_mode,
        "persistent_profile_id": config.persistent_profile_id,
        "persistent_profile_root": str(profile_root),
        "codex_home": str(codex_home),
        "user_data_dir": str(user_data_dir),
        "home_dir": str(home_dir),
        "tmp_dir": str(tmp_dir),
        "runtime_tmp_dir": str(runtime_tmp_dir),
        "launcher_path": str(launcher_path),
        "runtime_tmp_dir_under_tmp_root": runtime_tmp_dir.is_relative_to(
            _lexical_absolute(Path("/tmp"))
        ),
        "runtime_tmp_socket_candidate": str(socket_candidate),
        "runtime_tmp_socket_candidate_length": len(str(socket_candidate)),
        "protected_surface_overlap": protected_overlap,
        "browser_client_path_authority": config.browser_client_path_authority,
        "remote_client_path_authority": config.remote_client_path_authority,
        "client_model_provider_authority": config.client_model_provider_authority,
        "silent_fallback_to_ephemeral_allowed": config.silent_fallback_to_ephemeral_allowed,
        "original_codex_profile_dependency": config.original_codex_profile_dependency,
        "original_codex_profile_mutation_allowed": config.original_codex_profile_mutation_allowed,
        "cleanup_execution_allowed": config.cleanup_execution_allowed,
        "backup_export_execution_allowed": config.backup_export_execution_allowed,
        "persistent_profile_state_write_allowed": config.persistent_profile_state_write_allowed,
        "live_execution_allowed": config.live_execution_allowed,
        "lock_policy": config.lock_policy,
        "config_validation_is_live_runtime_enforcement": False,
        "dry_run_rejection_is_live_rejection_proof": False,
        "profile_path_existence_checked": False,
        "profile_path_existence_counts_as_storage_proof": False,
        "lock_policy_rendered_counts_as_lock_acquired": False,
    }


def dry_run_rejection_matrix(base_config: PersistentLauncherDryRunConfig) -> list[dict[str, Any]]:
    cases = [
        (
            "missing_profile_id",
            {"persistent_profile_id": ""},
            "persistent_profile_id_invalid",
        ),
        (
            "invalid_profile_id",
            {"persistent_profile_id": "../original"},
            "persistent_profile_id_invalid",
        ),
        (
            "browser_client_path_authority",
            {"browser_client_path_authority": True},
            "browser_client_path_authority_forbidden",
        ),
        (
            "remote_client_path_authority",
            {"remote_client_path_authority": True},
            "remote_client_path_authority_forbidden",
        ),
        (
            "silent_fallback",
            {"silent_fallback_to_ephemeral_allowed": True},
            "silent_persistent_to_ephemeral_fallback_forbidden",
        ),
        (
            "original_profile_dependency",
            {"original_codex_profile_dependency": True},
            "original_codex_profile_dependency_forbidden",
        ),
        (
            "profile_write_allowed",
            {"persistent_profile_state_write_allowed": True},
            "persistent_profile_state_write_forbidden_in_dry_run",
        ),
        (
            "live_execution_allowed",
            {"live_execution_allowed": True},
            "live_execution_forbidden_in_dry_run",
        ),
    ]
    matrix: list[dict[str, Any]] = []
    for name, overrides, expected_failure in cases:
        candidate = PersistentLauncherDryRunConfig(
            **{**base_config.__dict__, **overrides}
        )
        validation = validate_persistent_launcher_dry_run_config(candidate)
        matrix.append(
            {
                "case": name,
                "status": validation["status"],
                "expected_failure": expected_failure,
                "expected_failure_present": expected_failure in validation["failed_checks"],
                "failed_checks": validation["failed_checks"],
                "dry_run_rejection_only": True,
                "live_rejection_proven": False,
            }
        )
    return matrix
