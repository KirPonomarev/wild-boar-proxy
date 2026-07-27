# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping
import hashlib
from pathlib import Path
import subprocess
from typing import Any


ACTIVE_PROJECT_ROOT_ENV = "WBP_ACTIVE_PROJECT_ROOT"
LEGACY_TARGET_REPO_ENV = "WBP_TARGET_REPO"

ACTIVE_PROJECT_ROOT_SOURCE_CLI_ARG = "active_project_root_cli_arg"
ACTIVE_PROJECT_ROOT_SOURCE_SERVER_ENV = "server_runtime_env"
ACTIVE_PROJECT_ROOT_SOURCE_LEGACY_CLI_ARG = "legacy_target_repo_cli_arg"
ACTIVE_PROJECT_ROOT_SOURCE_LEGACY_ENV = "legacy_target_repo_env"
ACTIVE_PROJECT_ROOT_SOURCE_MISSING = "missing"

ACTIVE_PROJECT_ROOT_STATUS_OK = "ok"
ACTIVE_PROJECT_ROOT_STATUS_MISSING = "active_project_root_missing"
ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SYSTEM_DIR = (
    "active_project_root_blocked_system_dir"
)
ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SENSITIVE_NAME = (
    "active_project_root_blocked_sensitive_name"
)
ACTIVE_PROJECT_ROOT_STATUS_NOT_DIRECTORY = "active_project_root_not_directory"
ACTIVE_PROJECT_ROOT_FIELD_NAMES = (
    "active_project_root_required",
    "active_project_root_available",
    "active_project_root_source",
    "active_project_root_status",
    "active_project_root_path_recorded",
    "active_project_root_sha256",
    "active_project_root_is_wbp_repo",
    "active_project_root_git_available",
    "active_project_root_fallback_used",
    "active_project_root_legacy_target_repo_alias_used",
)

TARGET_REPO_STATUS_BY_ACTIVE_STATUS = {
    ACTIVE_PROJECT_ROOT_STATUS_OK: "ok",
    ACTIVE_PROJECT_ROOT_STATUS_MISSING: "target_repo_missing",
    ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SYSTEM_DIR: "target_repo_blocked_system_dir",
    ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SENSITIVE_NAME: (
        "target_repo_blocked_sensitive_name"
    ),
    ACTIVE_PROJECT_ROOT_STATUS_NOT_DIRECTORY: "target_repo_not_directory",
}

ACTIVE_PROJECT_ROOT_BLOCKED_EXACT_PATHS = frozenset(
    {
        Path("/").resolve(strict=False),
        Path("/System").resolve(strict=False),
        Path("/Library").resolve(strict=False),
        Path("/bin").resolve(strict=False),
        Path("/sbin").resolve(strict=False),
        Path("/usr").resolve(strict=False),
        Path("/etc").resolve(strict=False),
        Path("/private/etc").resolve(strict=False),
    }
)
ACTIVE_PROJECT_ROOT_SENSITIVE_PART_NAMES = {
    ".git",
    ".env",
    ".ssh",
    ".gnupg",
    "__pycache__",
    "node_modules",
}
ACTIVE_PROJECT_ROOT_SENSITIVE_NAME_MARKERS = (
    "secret",
    "credential",
    "token",
    "private_key",
    "private-key",
    "api_key",
    "api-key",
)


def safe_text(value: object, *, limit: int = 4096) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def active_project_root_path_is_sensitive(path_text: str) -> bool:
    path = Path(path_text)
    parts = [part.casefold() for part in path.parts]
    if any(part in ACTIVE_PROJECT_ROOT_SENSITIVE_PART_NAMES for part in parts):
        return True
    if any(part.startswith(".env") for part in parts):
        return True
    return any(
        marker in part
        for marker in ACTIVE_PROJECT_ROOT_SENSITIVE_NAME_MARKERS
        for part in parts
    )


def active_project_root_block_reason(path: Path | None) -> str:
    if path is None:
        return ACTIVE_PROJECT_ROOT_STATUS_MISSING
    resolved = path.expanduser().resolve(strict=False)
    if resolved in ACTIVE_PROJECT_ROOT_BLOCKED_EXACT_PATHS:
        return ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SYSTEM_DIR
    if active_project_root_path_is_sensitive(str(resolved)):
        return ACTIVE_PROJECT_ROOT_STATUS_BLOCKED_SENSITIVE_NAME
    if not resolved.exists():
        return ACTIVE_PROJECT_ROOT_STATUS_MISSING
    if not resolved.is_dir():
        return ACTIVE_PROJECT_ROOT_STATUS_NOT_DIRECTORY
    return ""


def active_project_root_git_available(path: Path) -> bool:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5.0,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def active_project_root_metadata(
    raw_path: Path | str | None,
    *,
    source: str,
    wbp_repo_root: Path | None,
    required: bool,
) -> tuple[Path | None, dict[str, Any]]:
    candidate = Path(raw_path).expanduser().resolve(strict=False) if raw_path else None
    status = active_project_root_block_reason(candidate)
    available = status == ""
    control_root = (
        wbp_repo_root or Path(__file__).resolve().parents[1]
    ).expanduser().resolve(strict=False)
    fields: dict[str, Any] = {
        "active_project_root_required": bool(required),
        "active_project_root_available": available,
        "active_project_root_source": safe_text(source, limit=80),
        "active_project_root_status": (
            ACTIVE_PROJECT_ROOT_STATUS_OK if available else status
        ),
        "active_project_root_path_recorded": False,
        "active_project_root_sha256": sha256_text(str(candidate)) if candidate else "",
        "active_project_root_is_wbp_repo": bool(available and candidate == control_root),
        "active_project_root_git_available": bool(
            available
            and candidate is not None
            and active_project_root_git_available(candidate)
        ),
        "active_project_root_fallback_used": False,
        "active_project_root_legacy_target_repo_alias_used": safe_text(
            source,
            limit=80,
        )
        in {
            ACTIVE_PROJECT_ROOT_SOURCE_LEGACY_CLI_ARG,
            ACTIVE_PROJECT_ROOT_SOURCE_LEGACY_ENV,
        },
    }
    return (candidate if available else None), fields


def target_repo_fields_from_active_project_root(
    active_fields: Mapping[str, Any],
) -> dict[str, Any]:
    active_status = safe_text(active_fields.get("active_project_root_status"), limit=120)
    target_status = TARGET_REPO_STATUS_BY_ACTIVE_STATUS.get(active_status, active_status)
    return {
        "target_repo_required": active_fields.get("active_project_root_required")
        is True,
        "target_repo_available": active_fields.get("active_project_root_available")
        is True,
        "target_repo_source": safe_text(
            active_fields.get("active_project_root_source"),
            limit=80,
        ),
        "target_repo_status": target_status,
        "target_repo_path_recorded": False,
        "target_repo_sha256": safe_text(
            active_fields.get("active_project_root_sha256"),
            limit=80,
        ),
        "target_repo_is_wbp_repo": active_fields.get("active_project_root_is_wbp_repo")
        is True,
        "target_repo_git_available": active_fields.get(
            "active_project_root_git_available"
        )
        is True,
        "target_repo_fallback_used": active_fields.get(
            "active_project_root_fallback_used"
        )
        is True,
    }


def active_project_root_fields_from_mapping(
    source: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = source or {}
    return {
        "active_project_root_required": source.get("active_project_root_required")
        is True,
        "active_project_root_available": source.get("active_project_root_available")
        is True,
        "active_project_root_source": safe_text(
            source.get("active_project_root_source"),
            limit=80,
        ),
        "active_project_root_status": safe_text(
            source.get("active_project_root_status"),
            limit=120,
        ),
        "active_project_root_path_recorded": source.get(
            "active_project_root_path_recorded"
        )
        is True,
        "active_project_root_sha256": safe_text(
            source.get("active_project_root_sha256"),
            limit=80,
        ),
        "active_project_root_is_wbp_repo": source.get(
            "active_project_root_is_wbp_repo"
        )
        is True,
        "active_project_root_git_available": source.get(
            "active_project_root_git_available"
        )
        is True,
        "active_project_root_fallback_used": source.get(
            "active_project_root_fallback_used"
        )
        is True,
        "active_project_root_legacy_target_repo_alias_used": source.get(
            "active_project_root_legacy_target_repo_alias_used"
        )
        is True,
    }


def select_active_project_root_candidate(
    *,
    active_project_root_arg: str | None,
    target_repo_arg: str | None,
    env: Mapping[str, str],
) -> tuple[Path | None, str]:
    if active_project_root_arg:
        return (
            Path(active_project_root_arg).expanduser().resolve(strict=False),
            ACTIVE_PROJECT_ROOT_SOURCE_CLI_ARG,
        )
    env_active = safe_text(env.get(ACTIVE_PROJECT_ROOT_ENV), limit=4096)
    if env_active:
        return (
            Path(env_active).expanduser().resolve(strict=False),
            ACTIVE_PROJECT_ROOT_SOURCE_SERVER_ENV,
        )
    if target_repo_arg:
        return (
            Path(target_repo_arg).expanduser().resolve(strict=False),
            ACTIVE_PROJECT_ROOT_SOURCE_LEGACY_CLI_ARG,
        )
    env_target = safe_text(env.get(LEGACY_TARGET_REPO_ENV), limit=4096)
    if env_target:
        return (
            Path(env_target).expanduser().resolve(strict=False),
            ACTIVE_PROJECT_ROOT_SOURCE_LEGACY_ENV,
        )
    return None, ACTIVE_PROJECT_ROOT_SOURCE_MISSING
