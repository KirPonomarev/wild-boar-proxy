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
import shlex
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
PROTECTED_SURFACE_PATHS = {
    "codex_dir": Path.home() / ".codex",
    "default_app_support_codex": Path.home() / "Library" / "Application Support" / "Codex",
    "default_cache_codex": Path.home() / "Library" / "Caches" / "com.openai.codex",
    "default_httpstorage_codex": Path.home() / "Library" / "HTTPStorages" / "com.openai.codex",
}
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
        try:
            stat = path.stat()
        except FileNotFoundError:
            entries.append(
                {
                    "relative_path": relative,
                    "kind": "transient_missing_during_scan",
                    "size": 0,
                    "mtime_ns": 0,
                }
            )
            continue
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
    return {
        "captured_at_utc": utc_now(),
        "surfaces": {name: scan_tree(path) for name, path in PROTECTED_SURFACE_PATHS.items()},
    }


def _path_metadata(
    path: Path,
    *,
    sha256_size_limit: int = DEFAULT_SHA256_SIZE_LIMIT,
) -> dict[str, Any]:
    path = path.expanduser()
    metadata: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "sha256_size_limit": sha256_size_limit,
    }
    if not path.exists():
        metadata["state"] = "absent"
        return metadata
    stat = path.stat()
    metadata.update(
        {
            "state": "present",
            "kind": "dir" if path.is_dir() else "file" if path.is_file() else "other",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    )
    if path.is_file() and stat.st_size <= sha256_size_limit:
        metadata["sha256"] = _sha256_file(path)
        metadata["hash_recorded"] = True
    else:
        metadata["hash_recorded"] = False
    return metadata


def build_original_surface_read_classification_packet(
    *,
    codex_home: Path | None = None,
    app_support_dir: Path | None = None,
    auth_json_path: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    codex_home = (codex_home or PROTECTED_SURFACE_PATHS["codex_dir"]).expanduser()
    app_support_dir = (
        app_support_dir or PROTECTED_SURFACE_PATHS["default_app_support_codex"]
    ).expanduser()
    auth_json_path = (auth_json_path or codex_home / "auth.json").expanduser()
    config_path = (config_path or codex_home / "config.toml").expanduser()
    targets = [
        {"surface": "original_codex_home", "path": str(codex_home), "classification": "inspection_only"},
        {
            "surface": "original_app_support_codex",
            "path": str(app_support_dir),
            "classification": "inspection_only",
        },
        {"surface": "original_auth_json", "path": str(auth_json_path), "classification": "hash_metadata_only"},
        {"surface": "original_config_toml", "path": str(config_path), "classification": "hash_metadata_only"},
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_surface_read_classification",
        "status": "ok",
        "reason_for_read": "Original Codex readiness inventory only; no runtime authority is consumed",
        "snapshot_targets": targets,
        "filesystem_read_performed": True,
        "filesystem_write_performed": False,
        "native_original_launch_attempted": False,
        "original_profile_write_performed": False,
        "runtime_auth_input_used": False,
        "runtime_provider_authority_used": False,
        "current_auth_json_execution_dependency": False,
        "auth_json_token_value_read": False,
        "auth_json_parsed": False,
        "auth_json_copied": False,
        "inspection_only": True,
    }


def build_original_profile_inventory_packet(
    *,
    codex_home: Path | None = None,
    app_support_dir: Path | None = None,
    config_path: Path | None = None,
    auth_json_path: Path | None = None,
) -> dict[str, Any]:
    codex_home = (codex_home or PROTECTED_SURFACE_PATHS["codex_dir"]).expanduser()
    app_support_dir = (
        app_support_dir or PROTECTED_SURFACE_PATHS["default_app_support_codex"]
    ).expanduser()
    config_path = (config_path or codex_home / "config.toml").expanduser()
    auth_json_path = (auth_json_path or codex_home / "auth.json").expanduser()
    config_metadata = _path_metadata(config_path)
    auth_metadata = _path_metadata(auth_json_path)
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_profile_inventory",
        "status": "ok",
        "codex_home": _path_metadata(codex_home),
        "app_support_dir": _path_metadata(app_support_dir),
        "config_toml": config_metadata,
        "auth_json": auth_metadata,
        "config_before_hash_or_absent_state_recorded": bool(
            config_metadata.get("sha256") or config_metadata.get("state") == "absent"
        ),
        "auth_json_hash_recorded": bool(
            auth_metadata.get("sha256") or auth_metadata.get("state") == "absent"
        ),
        "auth_json_token_value_read": False,
        "auth_json_parsed": False,
        "auth_json_copied": False,
        "current_auth_json_execution_dependency": False,
        "original_profile_write_performed": False,
        "native_original_launch_attempted": False,
    }


def build_original_auth_boundary_packet(
    *,
    profile_inventory_packet: dict[str, Any],
) -> dict[str, Any]:
    auth_json = (
        profile_inventory_packet.get("auth_json")
        if isinstance(profile_inventory_packet.get("auth_json"), dict)
        else {}
    )
    failed_checks: list[str] = []
    if profile_inventory_packet.get("auth_json_token_value_read") is not False:
        failed_checks.append("auth_json_token_value_must_not_be_read")
    if profile_inventory_packet.get("auth_json_parsed") is not False:
        failed_checks.append("auth_json_must_not_be_parsed")
    if profile_inventory_packet.get("current_auth_json_execution_dependency") is not False:
        failed_checks.append("current_auth_json_must_not_be_runtime_input")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_auth_boundary",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "ORIGINAL_AUTH_BOUNDARY_VIOLATED",
        "auth_json_exists": bool(auth_json.get("exists")),
        "auth_json_metadata_or_absent_state_recorded": bool(
            auth_json.get("sha256") or auth_json.get("state") == "absent"
        ),
        "auth_json_token_value_read": False,
        "auth_json_parsed": False,
        "auth_json_copied": False,
        "auth_json_used_as_runtime_input": False,
        "symlink_auth_used": False,
        "file_auth_used": False,
        "proxy_auth_equated_to_file_auth": False,
        "raw_upstream_secret_recorded": False,
        "failed_checks": failed_checks,
    }


def build_original_process_window_state_packet(
    *,
    process_inventory_packet: dict[str, Any],
) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_process_window_state",
        "status": "ok",
        "process_inventory": process_inventory_packet,
        "original_process_count": process_inventory_packet.get("line_count", 0),
        "default_process_count": process_inventory_packet.get("default_process_count", 0),
        "root_app_pids": process_inventory_packet.get("root_app_pids", []),
        "process_inventory_only": True,
        "native_window_ux_proven": False,
        "owner_visible_response_proven": False,
        "native_original_launch_attempted": False,
        "original_process_killed_or_mutated": False,
    }


def build_original_temporary_route_strategy_packet(
    *,
    profile_inventory_packet: dict[str, Any],
    config_path: Path | None = None,
    target_provider_id: str = "wbp",
    future_owner_authorization_required: bool = True,
) -> dict[str, Any]:
    config_metadata = (
        profile_inventory_packet.get("config_toml")
        if isinstance(profile_inventory_packet.get("config_toml"), dict)
        else {}
    )
    resolved_config_path = str(
        (config_path or Path(str(config_metadata.get("path", Path.home() / ".codex" / "config.toml")))).expanduser()
    )
    before_state_recorded = bool(
        config_metadata.get("sha256") or config_metadata.get("state") == "absent"
    )
    exact_target_declared = bool(resolved_config_path) and resolved_config_path.endswith(
        ".codex/config.toml"
    )
    expected_diff_shape = {
        "model_provider": target_provider_id,
        "model_providers.wbp.base_url": "local WBP /v1 endpoint",
        "model_providers.wbp.wire_api": "responses",
        "model_providers.wbp.auth": "server-owned auth.command or explicitly classified fallback",
    }
    failed_checks: list[str] = []
    if not exact_target_declared:
        failed_checks.append("exact_original_config_target_required")
    if not before_state_recorded:
        failed_checks.append("before_hash_or_absent_state_required")
    if not expected_diff_shape:
        failed_checks.append("expected_diff_shape_required")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_temporary_route_strategy",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "TEMPORARY_ROUTE_STRATEGY_INCOMPLETE",
        "strategy_scope": "future_live_original_route_preflight_only",
        "exact_target_path": resolved_config_path,
        "target_provider_id": target_provider_id,
        "before_hash_or_absent_state_recorded": before_state_recorded,
        "before_state": config_metadata,
        "planned_after_hash_strategy": "compute_after_candidate_config_in_future_live_preflight_before_apply",
        "expected_diff_shape_declared": True,
        "expected_diff_shape": expected_diff_shape,
        "restore_command_declared": True,
        "restore_command_plan": (
            "future live contour must restore exact prior bytes when before_state=present; "
            "must delete only the created target when before_state=absent"
        ),
        "rollback_trigger_declared": True,
        "rollback_triggers": [
            "Codex ignores model_providers",
            "WBP route trace missing",
            "Original normal mode cannot be restored",
            "unexpected protected surface drift",
            "owner cancels authorization",
        ],
        "owner_authorization_required": future_owner_authorization_required,
        "native_original_launch_attempted": False,
        "original_profile_write_performed": False,
        "route_proven": False,
        "failed_checks": failed_checks,
    }


def build_original_rollback_feasibility_packet(
    *,
    temporary_route_strategy_packet: dict[str, Any],
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if temporary_route_strategy_packet.get("status") != "ok":
        failed_checks.append("temporary_route_strategy_must_be_ok")
    if temporary_route_strategy_packet.get("restore_command_declared") is not True:
        failed_checks.append("restore_command_required")
    if temporary_route_strategy_packet.get("rollback_trigger_declared") is not True:
        failed_checks.append("rollback_trigger_required")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_rollback_feasibility",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "ROLLBACK_FEASIBILITY_INCOMPLETE",
        "rollback_plan_scope": "future_live_preflight_only",
        "exact_target_path": temporary_route_strategy_packet.get("exact_target_path", ""),
        "before_state": temporary_route_strategy_packet.get("before_state", {}),
        "restore_command_plan": temporary_route_strategy_packet.get(
            "restore_command_plan", ""
        ),
        "verification_command_plan": "future live contour must re-hash target and compare to before_state, then launch normal Original without WBP",
        "rollback_triggers": temporary_route_strategy_packet.get("rollback_triggers", []),
        "rollback_executed": False,
        "normal_original_post_cleanup_proven": False,
        "original_profile_write_performed": False,
        "failed_checks": failed_checks,
    }


def build_original_via_wbp_claim_limits_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_via_wbp_claim_limits",
        "status": "ok",
        "allowed_claims": [
            "Original protected surface read classified",
            "Original profile inventory classified",
            "Original auth boundary classified",
            "temporary route strategy readiness classified",
            "rollback feasibility classified",
            "future live admissibility classified with owner authorization",
        ],
        "forbidden_claims": [
            "Original Codex via WBP proven",
            "fresh Original native launch performed",
            "fresh Original WBP route proven",
            "Original native UX proven",
            "direct egress absence proven",
            "model availability proven",
            "auth strategy proven",
            "rollback executed",
            "normal Original post-cleanup proven",
            "final E2E proven",
        ],
        "native_original_launch_attempted": False,
        "original_route_proven": False,
        "rollback_executed": False,
        "direct_egress_absence_proven": False,
        "final_e2e_proven": False,
    }


def build_original_live_admissibility_decision_packet(
    *,
    surface_read_packet: dict[str, Any],
    profile_inventory_packet: dict[str, Any],
    auth_boundary_packet: dict[str, Any],
    process_window_state_packet: dict[str, Any],
    temporary_route_strategy_packet: dict[str, Any],
    rollback_feasibility_packet: dict[str, Any],
    claim_limits_packet: dict[str, Any],
    egress_blocked_prior_context: bool = False,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    for name, packet in (
        ("surface_read", surface_read_packet),
        ("profile_inventory", profile_inventory_packet),
        ("auth_boundary", auth_boundary_packet),
        ("process_window_state", process_window_state_packet),
        ("temporary_route_strategy", temporary_route_strategy_packet),
        ("rollback_feasibility", rollback_feasibility_packet),
        ("claim_limits", claim_limits_packet),
    ):
        if packet.get("status") != "ok":
            failed_checks.append(f"{name}_required")
    if surface_read_packet.get("inspection_only") is not True:
        failed_checks.append("surface_read_must_be_inspection_only")
    if auth_boundary_packet.get("auth_json_used_as_runtime_input") is not False:
        failed_checks.append("current_auth_json_must_not_be_runtime_input")
    if temporary_route_strategy_packet.get("route_proven") is not False:
        failed_checks.append("route_strategy_must_not_claim_route")
    if rollback_feasibility_packet.get("rollback_executed") is not False:
        failed_checks.append("rollback_plan_must_not_claim_execution")
    if process_window_state_packet.get("native_window_ux_proven") is not False:
        failed_checks.append("process_inventory_must_not_claim_ux")
    admissible = not failed_checks
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_admissibility_decision",
        "status": "ok" if admissible else "blocked",
        "final_status": (
            "ORIGINAL_CODEX_VIA_WBP_READINESS_CLASSIFIED_LIVE_ADMISSIBLE_WITH_OWNER_AUTHORIZATION"
            if admissible
            else "ORIGINAL_CODEX_VIA_WBP_READINESS_BLOCKED_WITH_PACKETED_REASON"
        ),
        "reason_class": "" if admissible else "ORIGINAL_READINESS_GATE_BLOCKED",
        "failed_checks": failed_checks,
        "future_live_original_admissible_with_owner_authorization": admissible,
        "owner_authorization_required": True,
        "ordinary_codex_quiescent_window_required": True,
        "egress_blocked_prior_context": egress_blocked_prior_context,
        "egress_blocked_counted_as_pass": False,
        "network_claim_limits_required_if_egress_remains_blocked": True,
        "native_original_launch_attempted": False,
        "original_profile_write_performed": False,
        "original_route_proven": False,
        "original_ux_proven": False,
        "direct_egress_absence_proven": False,
        "rollback_executed": False,
        "normal_original_post_cleanup_proven": False,
        "final_e2e_proven": False,
    }


def build_original_readiness_false_green_audit(
    *,
    live_admissibility_decision_packet: dict[str, Any],
    claim_limits_packet: dict[str, Any],
    custom_native_proof_used_as_original_proof: bool = False,
    auth_model_history_used_as_original_proof: bool = False,
) -> dict[str, Any]:
    checks = [
        {
            "name": "no_native_original_launch_claim",
            "passed": live_admissibility_decision_packet.get(
                "native_original_launch_attempted"
            )
            is False,
        },
        {
            "name": "route_strategy_not_route_proof",
            "passed": live_admissibility_decision_packet.get("original_route_proven")
            is False,
        },
        {
            "name": "rollback_plan_not_execution",
            "passed": live_admissibility_decision_packet.get("rollback_executed")
            is False,
        },
        {
            "name": "process_inventory_not_ux_proof",
            "passed": live_admissibility_decision_packet.get("original_ux_proven")
            is False,
        },
        {
            "name": "custom_native_proof_not_original_proof",
            "passed": custom_native_proof_used_as_original_proof is False,
        },
        {
            "name": "auth_model_history_not_original_proof",
            "passed": auth_model_history_used_as_original_proof is False,
        },
        {
            "name": "egress_blocked_not_counted_as_pass",
            "passed": live_admissibility_decision_packet.get(
                "egress_blocked_counted_as_pass"
            )
            is False,
        },
        {
            "name": "claim_limits_forbid_original_route_and_e2e",
            "passed": claim_limits_packet.get("original_route_proven") is False
            and claim_limits_packet.get("final_e2e_proven") is False,
        },
    ]
    forbidden_claims_present = any(not check["passed"] for check in checks)
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_readiness_false_green_audit",
        "status": "ok" if not forbidden_claims_present else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
        "readiness_counted_as_original_route_proof": False,
        "readiness_counted_as_rollback_execution": False,
    }


def build_original_live_owner_authorization_packet(
    *,
    owner_authorized: bool,
    exact_target_path: str,
    allowed_write_operation: str,
    rollback_mode: str,
    launch_permission: bool,
    owner_prompt_permission: bool,
    restore_permission: bool,
    expected_target_path: Path | None = None,
) -> dict[str, Any]:
    expected_target = str(
        (expected_target_path or (Path.home() / ".codex" / "config.toml")).expanduser()
    )
    failed_checks: list[str] = []
    if owner_authorized is not True:
        failed_checks.append("owner_authorization_missing")
    if exact_target_path != expected_target:
        failed_checks.append("exact_target_path_required")
    if allowed_write_operation != "temporary_wbp_route_config_replace":
        failed_checks.append("allowed_write_operation_too_broad")
    if rollback_mode not in {"restore_prior_bytes", "delete_created_target"}:
        failed_checks.append("rollback_mode_required")
    if launch_permission is not True:
        failed_checks.append("launch_permission_required")
    if owner_prompt_permission is not True:
        failed_checks.append("owner_prompt_permission_required")
    if restore_permission is not True:
        failed_checks.append("restore_permission_required")
    authorization_exact = not failed_checks
    reason_class = ""
    if "owner_authorization_missing" in failed_checks:
        reason_class = "NO_OWNER_AUTHORIZATION"
    elif failed_checks:
        reason_class = "OWNER_AUTHORIZATION_TOO_BROAD"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_owner_authorization",
        "status": "ok" if authorization_exact else "blocked",
        "reason_class": reason_class,
        "owner_authorized": owner_authorized,
        "authorization_exact": authorization_exact,
        "exact_target_path": exact_target_path,
        "expected_target_path": expected_target,
        "allowed_write_operation": allowed_write_operation,
        "rollback_mode": rollback_mode,
        "launch_permission": launch_permission,
        "owner_prompt_permission": owner_prompt_permission,
        "restore_permission": restore_permission,
        "broad_authorization_accepted": False,
        "implicit_previous_authorization_accepted": False,
        "retry_mutation_authorized": False,
        "original_profile_write_allowed": authorization_exact,
        "native_original_launch_allowed": authorization_exact,
        "failed_checks": failed_checks,
    }


def build_original_readiness_reference_packet(
    *,
    readiness_summary_packet: dict[str, Any],
    source_path: str,
) -> dict[str, Any]:
    expected = (
        "ORIGINAL_CODEX_VIA_WBP_READINESS_CLASSIFIED_LIVE_ADMISSIBLE_WITH_OWNER_AUTHORIZATION"
    )
    final_status = str(readiness_summary_packet.get("final_status", ""))
    status_ok = readiness_summary_packet.get("status") == "ok" and final_status == expected
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_readiness_reference",
        "status": "ok" if status_ok else "blocked",
        "reason_class": "" if status_ok else "READINESS_REFERENCE_NOT_ADMISSIBLE",
        "source_path": source_path,
        "referenced_final_status": final_status,
        "referenced_status": readiness_summary_packet.get("status"),
        "readiness_live_admissible_with_owner_authorization": status_ok,
        "readiness_counted_as_live_original_proof": False,
        "readiness_counted_as_route_proof": False,
        "readiness_counted_as_rollback_execution": False,
    }


def build_original_live_rollback_point_packet(
    *,
    profile_before_packet: dict[str, Any],
    owner_authorization_packet: dict[str, Any],
    rollback_artifact_path: str = "",
    rollback_artifact_sha256: str = "",
    rollback_point_created: bool = False,
    rollback_point_verified: bool = False,
) -> dict[str, Any]:
    config_metadata = (
        profile_before_packet.get("config_toml")
        if isinstance(profile_before_packet.get("config_toml"), dict)
        else {}
    )
    before_recorded = bool(
        config_metadata.get("sha256") or config_metadata.get("state") == "absent"
    )
    failed_checks: list[str] = []
    if owner_authorization_packet.get("status") != "ok":
        failed_checks.append("owner_authorization_required_before_rollback_point")
    if not before_recorded:
        failed_checks.append("before_hash_or_absent_state_required")
    if rollback_point_created is not True:
        failed_checks.append("rollback_point_created_required_before_apply")
    if rollback_point_verified is not True:
        failed_checks.append("rollback_point_verified_required_before_apply")
    if config_metadata.get("state") == "present" and not rollback_artifact_sha256:
        failed_checks.append("rollback_artifact_hash_required_for_present_config")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_rollback_point",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "ROLLBACK_POINT_NOT_READY",
        "before_state": config_metadata,
        "before_hash_or_absent_state_recorded": before_recorded,
        "rollback_mode": owner_authorization_packet.get("rollback_mode", ""),
        "rollback_artifact_path": rollback_artifact_path,
        "rollback_artifact_sha256": rollback_artifact_sha256,
        "rollback_point_created": rollback_point_created,
        "rollback_point_verified": rollback_point_verified,
        "temporary_route_apply_allowed": not failed_checks,
        "original_profile_write_performed": False,
        "failed_checks": failed_checks,
    }


def build_original_live_temporary_route_apply_admission_packet(
    *,
    owner_authorization_packet: dict[str, Any],
    rollback_point_packet: dict[str, Any],
    readiness_reference_packet: dict[str, Any],
    last_chance_dry_run_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    last_chance_dry_run_packet = (
        last_chance_dry_run_packet
        if isinstance(last_chance_dry_run_packet, dict)
        else {}
    )
    failed_checks: list[str] = []
    if readiness_reference_packet.get("status") != "ok":
        failed_checks.append("readiness_reference_required")
    if owner_authorization_packet.get("status") != "ok":
        failed_checks.append("owner_authorization_required")
    if rollback_point_packet.get("status") != "ok":
        failed_checks.append("rollback_point_required_before_apply")
    if last_chance_dry_run_packet:
        if last_chance_dry_run_packet.get("status") != "ok":
            failed_checks.append("last_chance_dry_run_required_before_apply")
        if last_chance_dry_run_packet.get("temporary_route_apply_performed") is True:
            failed_checks.append("dry_run_must_not_apply_route")
    apply_admitted = not failed_checks
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_temporary_route_apply_admission",
        "status": "ok" if apply_admitted else "blocked",
        "reason_class": "" if apply_admitted else "TEMPORARY_ROUTE_APPLY_NOT_ADMITTED",
        "temporary_route_apply_admitted": apply_admitted,
        "exact_target_path": owner_authorization_packet.get("exact_target_path", ""),
        "original_profile_write_allowed": apply_admitted,
        "original_profile_write_performed": False,
        "native_original_launch_allowed": apply_admitted,
        "native_original_launch_attempted": False,
        "failed_checks": failed_checks,
    }


def build_provider_auth_strategy_reference_packet(
    *,
    provider_auth_strategy_packet: dict[str, Any],
    source_path: str = "",
    auth_command_edited: bool = False,
    file_auth_fallback_used: bool = False,
    current_auth_json_runtime_dependency: bool = False,
) -> dict[str, Any]:
    auth_command = (
        provider_auth_strategy_packet.get("auth_command")
        if isinstance(provider_auth_strategy_packet.get("auth_command"), dict)
        else {}
    )
    failed_checks: list[str] = []
    if provider_auth_strategy_packet.get("status") != "ok":
        failed_checks.append("provider_auth_strategy_reference_must_be_ok")
    if provider_auth_strategy_packet.get("selected_strategy") != "auth.command":
        failed_checks.append("selected_strategy_must_remain_auth_command")
    if auth_command.get("server_owned_path") is not True:
        failed_checks.append("auth_command_path_must_be_server_owned")
    if auth_command.get("raw_upstream_secret") is not False:
        failed_checks.append("auth_command_must_not_emit_raw_upstream_secret")
    if auth_command_edited:
        failed_checks.append("auth_command_must_not_be_edited_in_original_live_contour")
    if file_auth_fallback_used:
        failed_checks.append("file_auth_fallback_deferred_to_separate_contour")
    if current_auth_json_runtime_dependency:
        failed_checks.append("current_auth_json_must_not_be_runtime_dependency")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "provider_auth_strategy_reference",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "AUTH_STRATEGY_REFERENCE_NOT_ADMISSIBLE",
        "referenced_packet": source_path,
        "referenced_status": "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED"
        if provider_auth_strategy_packet.get("status") == "ok"
        else "",
        "selected_strategy": provider_auth_strategy_packet.get("selected_strategy", ""),
        "auth_command_path": auth_command.get("path", ""),
        "auth_strategy_reproved": False,
        "auth_command_edited": auth_command_edited,
        "file_auth_fallback_used": file_auth_fallback_used,
        "current_auth_json_runtime_dependency": current_auth_json_runtime_dependency,
        "raw_upstream_secret_used": auth_command.get("raw_upstream_secret") is True,
        "temporary_route_apply_allowed": not failed_checks,
        "failed_checks": failed_checks,
    }


def build_original_live_temporary_config_candidate_packet(
    *,
    owner_authorization_packet: dict[str, Any],
    provider_auth_strategy_reference_packet: dict[str, Any],
    endpoint: str = "http://127.0.0.1:8318/v1",
    model: str = "gpt-5.4-mini",
    candidate_text: str | None = None,
) -> dict[str, Any]:
    auth_command_path = str(
        provider_auth_strategy_reference_packet.get("auth_command_path") or ""
    )
    if candidate_text is None:
        candidate_text = (
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
            f'command = "{auth_command_path}"\n'
        )
    failed_checks: list[str] = []
    if owner_authorization_packet.get("status") != "ok":
        failed_checks.append("owner_authorization_required_for_candidate")
    if provider_auth_strategy_reference_packet.get("status") != "ok":
        failed_checks.append("provider_auth_strategy_reference_required")
    if not auth_command_path:
        failed_checks.append("auth_command_path_required")
    if "experimental_bearer_token" in candidate_text:
        failed_checks.append("experimental_bearer_token_forbidden_in_original_live_r2")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_temporary_config_candidate",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "TEMPORARY_CONFIG_CANDIDATE_NOT_ADMISSIBLE",
        "exact_target_path": owner_authorization_packet.get("exact_target_path", ""),
        "candidate_sha256": hashlib.sha256(candidate_text.encode("utf-8")).hexdigest(),
        "candidate_byte_length": len(candidate_text.encode("utf-8")),
        "expected_diff_summary": [
            "set model_provider=wbp",
            f"set model={model}",
            f"set model_providers.wbp.base_url={endpoint}",
            "set model_providers.wbp.wire_api=responses",
            "set model_providers.wbp.requires_openai_auth=false",
            "set model_providers.wbp.auth.command=server_owned_path",
        ],
        "candidate_text_recorded": False,
        "raw_auth_token_in_candidate": False,
        "auth_command_reference_only": True,
        "experimental_bearer_token_in_candidate": False,
        "temporary_route_apply_performed": False,
        "failed_checks": failed_checks,
    }


def build_original_live_last_chance_dry_run_packet(
    *,
    owner_authorization_packet: dict[str, Any],
    rollback_point_packet: dict[str, Any],
    temporary_config_candidate_packet: dict[str, Any],
    provider_auth_strategy_reference_packet: dict[str, Any],
) -> dict[str, Any]:
    owner_target = str(owner_authorization_packet.get("exact_target_path") or "")
    candidate_target = str(temporary_config_candidate_packet.get("exact_target_path") or "")
    failed_checks: list[str] = []
    if owner_authorization_packet.get("status") != "ok":
        failed_checks.append("owner_authorization_required_after_dry_run")
    if rollback_point_packet.get("status") != "ok":
        failed_checks.append("rollback_point_required_after_dry_run")
    if temporary_config_candidate_packet.get("status") != "ok":
        failed_checks.append("temporary_config_candidate_required_after_dry_run")
    if provider_auth_strategy_reference_packet.get("status") != "ok":
        failed_checks.append("auth_strategy_reference_required_after_dry_run")
    if not owner_target or candidate_target != owner_target:
        failed_checks.append("candidate_target_must_match_owner_authorization")
    if not temporary_config_candidate_packet.get("expected_diff_summary"):
        failed_checks.append("expected_diff_summary_required")
    if temporary_config_candidate_packet.get("raw_auth_token_in_candidate") is not False:
        failed_checks.append("raw_auth_token_must_not_be_in_candidate")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_last_chance_dry_run",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "LAST_CHANCE_DRY_RUN_NOT_ADMISSIBLE",
        "dry_run_performed": True,
        "owner_authorization_current_after_dry_run": owner_authorization_packet.get("status")
        == "ok",
        "exact_target_path": owner_target,
        "candidate_target_path": candidate_target,
        "candidate_sha256": temporary_config_candidate_packet.get("candidate_sha256", ""),
        "temporary_route_apply_allowed": not failed_checks,
        "temporary_route_apply_performed": False,
        "original_profile_write_performed": False,
        "raw_auth_token_recorded": False,
        "failed_checks": failed_checks,
    }


def build_original_live_trace_timeout_policy_packet(
    *,
    trace_observed: bool,
    restore_attempted_after_timeout: bool,
    restore_verified_after_timeout: bool,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if timeout_seconds <= 0:
        failed_checks.append("positive_timeout_required")
    if not trace_observed and not restore_attempted_after_timeout:
        failed_checks.append("restore_attempt_required_after_trace_timeout")
    if not trace_observed and not restore_verified_after_timeout:
        failed_checks.append("restore_verification_required_after_trace_timeout")
    ok = trace_observed or not failed_checks
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_trace_timeout_policy",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "TRACE_TIMEOUT_RESTORE_FIRST_NOT_PROVEN",
        "timeout_seconds": timeout_seconds,
        "trace_observed": trace_observed,
        "restore_first_after_timeout": True,
        "restore_attempted_after_timeout": restore_attempted_after_timeout,
        "restore_verified_after_timeout": restore_verified_after_timeout,
        "retry_mutation_allowed": False,
        "second_launch_allowed_before_restore": False,
        "blocked_status_if_timeout": "ORIGINAL_CODEX_VIA_WBP_BLOCKED_ROUTE_TRACE_MISSING",
        "failed_checks": failed_checks,
    }


def build_original_live_restore_failure_lockdown_packet(
    *,
    restore_verified: bool,
    second_launch_attempted: bool = False,
    retry_apply_attempted: bool = False,
    hidden_cleanup_performed: bool = False,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if not restore_verified:
        failed_checks.append("restore_not_verified_requires_stop_and_diagnose")
    if second_launch_attempted:
        failed_checks.append("second_launch_forbidden_after_failed_restore")
    if retry_apply_attempted:
        failed_checks.append("retry_apply_forbidden_after_failed_restore")
    if hidden_cleanup_performed:
        failed_checks.append("hidden_cleanup_forbidden_after_failed_restore")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_restore_failure_lockdown",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "RESTORE_FAILURE_LOCKDOWN",
        "restore_verified": restore_verified,
        "stop_and_diagnose_required": not restore_verified,
        "second_launch_allowed": restore_verified,
        "normal_mode_sanity_allowed": restore_verified,
        "second_launch_attempted": second_launch_attempted,
        "retry_apply_attempted": retry_apply_attempted,
        "hidden_cleanup_performed": hidden_cleanup_performed,
        "failed_checks": failed_checks,
    }


def build_selected_model_trace_claim_packet(
    *,
    selected_model: str = "",
    route_trace_confirmed: bool = False,
) -> dict[str, Any]:
    trace_scoped = bool(selected_model) and route_trace_confirmed
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "selected_model_trace_claim",
        "status": "ok" if trace_scoped else "blocked",
        "reason_class": "" if trace_scoped else "SELECTED_MODEL_TRACE_NOT_PROVEN",
        "selected_model": selected_model,
        "route_trace_confirmed": route_trace_confirmed,
        "allowed_claim": (
            "selected_model_responded_in_this_original_route_trace"
            if trace_scoped
            else ""
        ),
        "model_availability_claimed": False,
        "model_family_availability_claimed": False,
        "catalog_availability_claimed": False,
        "gpt_5_5_availability_claimed": False,
    }


def build_original_live_restore_verification_packet(
    *,
    rollback_execution_attempted: bool,
    restore_verified: bool,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before_state = before_state if isinstance(before_state, dict) else {}
    after_state = after_state if isinstance(after_state, dict) else {}
    before_fingerprint = before_state.get("sha256", before_state.get("state"))
    after_fingerprint = after_state.get("sha256", after_state.get("state"))
    restore_matches_before = bool(before_fingerprint) and before_fingerprint == after_fingerprint
    ok = rollback_execution_attempted and restore_verified and restore_matches_before
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_restore_verification",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "RESTORE_NOT_VERIFIED",
        "rollback_execution_attempted": rollback_execution_attempted,
        "restore_verified": restore_verified,
        "restore_matches_before": restore_matches_before,
        "before_state": before_state,
        "after_state": after_state,
        "second_launch_allowed": ok,
        "second_launch_attempted_after_failed_restore": False,
        "normal_original_sanity_allowed": ok,
    }


def build_original_live_summary_packet(
    *,
    owner_authorization_packet: dict[str, Any],
    apply_admission_packet: dict[str, Any],
    route_trace_packet: dict[str, Any] | None = None,
    restore_verification_packet: dict[str, Any] | None = None,
    blocked_by_host_environment: bool = False,
) -> dict[str, Any]:
    route_trace_packet = route_trace_packet if isinstance(route_trace_packet, dict) else {}
    restore_verification_packet = (
        restore_verification_packet if isinstance(restore_verification_packet, dict) else {}
    )
    owner_missing = "owner_authorization_missing" in owner_authorization_packet.get(
        "failed_checks", []
    )
    auth_broad = (
        owner_authorization_packet.get("status") == "blocked"
        and not owner_missing
        and bool(owner_authorization_packet.get("failed_checks"))
    )
    route_confirmed = route_trace_packet.get("route_trace_confirmed") is True
    restore_ok = restore_verification_packet.get("status") == "ok"
    pass_ready = (
        apply_admission_packet.get("status") == "ok"
        and route_confirmed
        and restore_ok
        and not blocked_by_host_environment
    )
    if pass_ready:
        final_status = "ORIGINAL_CODEX_VIA_WBP_TEMP_ROUTE_AND_RESTORE_PROVEN_WITH_LIMITS"
        reason_class = ""
    elif owner_missing:
        final_status = "ORIGINAL_CODEX_VIA_WBP_BLOCKED_NO_OWNER_AUTHORIZATION"
        reason_class = "NO_OWNER_AUTHORIZATION"
    elif auth_broad:
        final_status = "ORIGINAL_CODEX_VIA_WBP_BLOCKED_AUTHORIZATION_TOO_BROAD"
        reason_class = "OWNER_AUTHORIZATION_TOO_BROAD"
    elif blocked_by_host_environment:
        final_status = "ORIGINAL_CODEX_VIA_WBP_BLOCKED_HOST_ENVIRONMENT"
        reason_class = "HOST_ENVIRONMENT_BLOCKED"
    elif apply_admission_packet.get("status") != "ok":
        final_status = "ORIGINAL_CODEX_VIA_WBP_BLOCKED_ROLLBACK_UNSAFE"
        reason_class = "TEMPORARY_ROUTE_APPLY_NOT_ADMITTED"
    elif not route_confirmed:
        final_status = "ORIGINAL_CODEX_VIA_WBP_BLOCKED_ROUTE_TRACE_MISSING"
        reason_class = "ROUTE_TRACE_MISSING"
    else:
        final_status = "ORIGINAL_CODEX_VIA_WBP_BLOCKED_RESTORE_DRIFT"
        reason_class = "RESTORE_NOT_VERIFIED"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_summary",
        "status": "ok" if pass_ready else "blocked",
        "final_status": final_status,
        "reason_class": reason_class,
        "native_original_launch_attempted": route_trace_packet.get(
            "native_original_launch_attempted", False
        ),
        "original_profile_write_performed": route_trace_packet.get(
            "original_profile_write_performed", False
        ),
        "original_route_proven": route_confirmed and pass_ready,
        "rollback_executed": restore_verification_packet.get(
            "rollback_execution_attempted", False
        ),
        "restore_verified": restore_ok,
        "normal_original_post_cleanup_proven": False,
        "direct_egress_absence_proven": False,
        "model_availability_proven": False,
        "wire_compatibility_proven": False,
        "full_native_ux_proven": False,
        "final_e2e_proven": False,
        "blocked_by_host_environment_counted_as_pass": False,
    }


def build_original_live_false_green_audit(
    *,
    summary_packet: dict[str, Any],
    selected_model_trace_claim_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_model_trace_claim_packet = (
        selected_model_trace_claim_packet
        if isinstance(selected_model_trace_claim_packet, dict)
        else {}
    )
    checks = [
        {
            "name": "direct_egress_not_claimed",
            "passed": summary_packet.get("direct_egress_absence_proven") is False,
        },
        {
            "name": "model_availability_not_claimed",
            "passed": summary_packet.get("model_availability_proven") is False
            and selected_model_trace_claim_packet.get("model_availability_claimed") is not True,
        },
        {
            "name": "full_ux_not_claimed",
            "passed": summary_packet.get("full_native_ux_proven") is False,
        },
        {
            "name": "final_e2e_not_claimed",
            "passed": summary_packet.get("final_e2e_proven") is False,
        },
        {
            "name": "wire_compatibility_not_claimed",
            "passed": summary_packet.get("wire_compatibility_proven") is not True,
        },
        {
            "name": "blocked_environment_not_pass",
            "passed": summary_packet.get("blocked_by_host_environment_counted_as_pass")
            is False,
        },
        {
            "name": "route_requires_restore_for_pass",
            "passed": (
                summary_packet.get("original_route_proven") is not True
                or summary_packet.get("restore_verified") is True
            ),
        },
    ]
    forbidden_claims_present = any(not check["passed"] for check in checks)
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "original_live_false_green_audit",
        "status": "ok" if not forbidden_claims_present else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
        "readiness_used_as_live_proof": False,
        "route_trace_used_as_egress_proof": False,
        "selected_model_used_as_model_availability": False,
        "owner_ux_used_as_full_ux": False,
        "rollback_plan_used_as_execution": False,
    }


def build_protected_surface_read_classification_packet() -> dict[str, Any]:
    targets = [
        {"surface": name, "path": str(path), "classification": "inspection_only"}
        for name, path in PROTECTED_SURFACE_PATHS.items()
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "protected_surface_read_classification",
        "status": "ok",
        "reason_for_read": "recursive before/after integrity snapshot only",
        "snapshot_targets": targets,
        "filesystem_read_performed": True,
        "filesystem_read_scope": "protected_surface_integrity_snapshot",
        "filesystem_write_performed": False,
        "runtime_auth_input_used": False,
        "runtime_provider_authority_used": False,
        "current_auth_json_execution_dependency": False,
        "inspection_only": True,
    }


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def build_native_safety_layer_boundary_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_safety_layer_boundary",
        "status": "ok",
        "proves_native_custom_safety_only": True,
        "native_ux_acceptance_proven": False,
        "owner_visible_response_proven": False,
        "machine_ui_input_field_proven": False,
        "model_availability_reproved": False,
        "codex_consumer_model_acceptance_proven": False,
        "direct_egress_absence_proven": False,
        "original_codex_reversibility_proven": False,
        "auth_strategy_reproved": False,
        "route_account_model_provider_mutated": False,
        "final_e2e_proven": False,
    }


def build_custom_profile_ownership_packet(
    *,
    tmp_root: Path,
    profile_dir: Path,
    codex_home: Path,
) -> dict[str, Any]:
    tmp_root = tmp_root.resolve(strict=False)
    profile_dir = profile_dir.resolve(strict=False)
    codex_home = codex_home.resolve(strict=False)
    profile_owned = _path_is_relative_to(profile_dir, tmp_root)
    codex_home_owned = _path_is_relative_to(codex_home, profile_dir)
    protected_overlap = any(
        _path_is_relative_to(profile_dir, protected_path)
        or _path_is_relative_to(codex_home, protected_path)
        for protected_path in PROTECTED_SURFACE_PATHS.values()
    )
    status_ok = profile_owned and codex_home_owned and not protected_overlap
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_profile_ownership",
        "status": "ok" if status_ok else "blocked",
        "reason_class": "" if status_ok else "CUSTOM_PROFILE_OWNERSHIP_UNCLEAR",
        "tmp_root": str(tmp_root),
        "profile_dir": str(profile_dir),
        "custom_codex_home": str(codex_home),
        "profile_under_tmp_root": profile_owned,
        "codex_home_under_profile": codex_home_owned,
        "protected_surface_overlap": protected_overlap,
        "current_codex_auth_json_runtime_dependency": False,
        "original_profile_write_allowed": False,
        "profile_materialized": profile_dir.exists(),
    }


def build_custom_user_data_dir_ownership_packet(
    *,
    tmp_root: Path,
    profile_dir: Path,
    user_data_dir: Path,
) -> dict[str, Any]:
    tmp_root = tmp_root.resolve(strict=False)
    profile_dir = profile_dir.resolve(strict=False)
    user_data_dir = user_data_dir.resolve(strict=False)
    under_tmp = _path_is_relative_to(user_data_dir, tmp_root)
    under_profile = _path_is_relative_to(user_data_dir, profile_dir)
    protected_overlap = any(
        _path_is_relative_to(user_data_dir, protected_path)
        for protected_path in PROTECTED_SURFACE_PATHS.values()
    )
    status_ok = under_tmp and under_profile and not protected_overlap
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_user_data_dir_ownership",
        "status": "ok" if status_ok else "blocked",
        "reason_class": "" if status_ok else "CUSTOM_USER_DATA_DIR_OWNERSHIP_UNCLEAR",
        "tmp_root": str(tmp_root),
        "profile_dir": str(profile_dir),
        "custom_user_data_dir": str(user_data_dir),
        "user_data_dir_under_tmp_root": under_tmp,
        "user_data_dir_under_profile": under_profile,
        "protected_surface_overlap": protected_overlap,
        "default_app_support_dependency": False,
        "original_profile_write_allowed": False,
        "user_data_dir_materialized": user_data_dir.exists(),
    }


def build_custom_profile_write_inventory_packet(
    *,
    tmp_root: Path,
    profile_dir: Path,
    user_data_dir: Path,
    codex_home: Path,
) -> dict[str, Any]:
    owned_paths = [profile_dir, user_data_dir, codex_home]
    protected_overlaps = [
        str(path)
        for path in owned_paths
        for protected_path in PROTECTED_SURFACE_PATHS.values()
        if _path_is_relative_to(path, protected_path)
    ]
    all_owned = all(_path_is_relative_to(path, tmp_root) for path in owned_paths)
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_profile_write_inventory",
        "status": "ok" if all_owned and not protected_overlaps else "blocked",
        "reason_class": "" if all_owned and not protected_overlaps else "CUSTOM_WRITE_SURFACE_UNCLEAR",
        "write_inventory_kind": "prelaunch_planned_owned_surfaces",
        "tmp_root": str(tmp_root.resolve(strict=False)),
        "owned_write_surfaces": [str(path.resolve(strict=False)) for path in owned_paths],
        "protected_surface_overlaps": protected_overlaps,
        "protected_surfaces_write_allowed": False,
        "original_codex_profile_write_allowed": False,
        "profile_materialized": profile_dir.exists(),
        "native_launch_attempted": False,
    }


def build_cleanup_reversibility_plan_packet(
    *,
    tmp_root: Path,
    owned_paths: list[Path],
) -> dict[str, Any]:
    tmp_root = tmp_root.resolve(strict=False)
    outside_targets = [
        str(path.resolve(strict=False))
        for path in owned_paths
        if not _path_is_relative_to(path, tmp_root)
    ]
    protected_targets = [
        str(path.resolve(strict=False))
        for path in owned_paths
        for protected_path in PROTECTED_SURFACE_PATHS.values()
        if _path_is_relative_to(path, protected_path)
    ]
    cleanup_safe = not outside_targets and not protected_targets
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "cleanup_reversibility",
        "status": "ok" if cleanup_safe else "blocked",
        "reason_class": "" if cleanup_safe else "CLEANUP_TARGET_UNCLEAR",
        "cleanup_plan_kind": "prelaunch_owned_tmp_root_cleanup_plan",
        "tmp_root": str(tmp_root),
        "cleanup_targets": [str(path.resolve(strict=False)) for path in owned_paths],
        "outside_tmp_root_targets": outside_targets,
        "protected_surface_targets": protected_targets,
        "cleanup_removes_only_custom_owned_surfaces": cleanup_safe,
        "cleanup_executed": False,
        "cleanup_not_required_reason": "profile_not_materialized_in_safety_refresh",
        "hidden_cleanup_performed": False,
        "original_codex_reversibility_claimed": False,
    }


def build_custom_native_launch_safety_packet(
    *,
    host_context_packet: dict[str, Any],
    quiescent_precondition_packet: dict[str, Any],
    native_launch_attempted: bool,
    owner_ui_action_performed: bool = False,
    incidental_wbp_request_observed: bool = False,
) -> dict[str, Any]:
    launch_blocked = (
        host_context_packet.get("status") != "ok"
        or quiescent_precondition_packet.get("status") != "ok"
    )
    failed_checks: list[str] = []
    if host_context_packet.get("status") != "ok":
        failed_checks.append("host_context_required_for_native_launch")
    if quiescent_precondition_packet.get("status") != "ok":
        failed_checks.append("quiescent_current_codex_required_for_native_launch")
    if owner_ui_action_performed:
        failed_checks.append("owner_ui_action_forbidden_in_safety_refresh")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "custom_native_launch_safety",
        "status": "blocked" if launch_blocked or failed_checks else "ok",
        "reason_class": "NATIVE_LAUNCH_BLOCKED_BY_HOST_ENVIRONMENT"
        if launch_blocked
        else "OWNER_ACTION_BOUNDARY_VIOLATED"
        if failed_checks
        else "",
        "native_launch_attempted": native_launch_attempted,
        "native_launch_admitted": not launch_blocked and not failed_checks,
        "owner_ui_action_performed": owner_ui_action_performed,
        "owner_prompt_required": False,
        "owner_prompt_submitted": False,
        "wbp_route_required": False,
        "incidental_wbp_request_observed": incidental_wbp_request_observed,
        "incidental_wbp_request_promoted_to_route_proof": False,
        "native_routing_proven": False,
        "native_ux_proven": False,
        "failed_checks": failed_checks,
    }


def build_native_custom_safety_claims_packet(
    *,
    native_safety_result_packet: dict[str, Any],
    custom_native_launch_safety_packet: dict[str, Any],
    protected_surface_diff_packet: dict[str, Any],
    cleanup_reversibility_packet: dict[str, Any],
    keychain_observation_packet: dict[str, Any],
) -> dict[str, Any]:
    final_pass = (
        native_safety_result_packet.get("status") == "ok"
        and protected_surface_diff_packet.get("all_protected_surfaces_unchanged")
        is True
        and cleanup_reversibility_packet.get("status") == "ok"
        and keychain_observation_packet.get("status") == "ok"
    )
    blocked_by_host = (
        native_safety_result_packet.get("actual_status")
        == "CODEX_CUSTOM_NATIVE_SAFETY_REFRESH_BLOCKED_BY_HOST_ENVIRONMENT"
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_custom_safety_claims",
        "status": "ok" if final_pass else "blocked",
        "allowed_final_claim": (
            "CODEX_CUSTOM_NATIVE_SAFETY_GUARD_REFRESHED_WITH_LIMITS"
            if final_pass
            else ""
        ),
        "actual_status": native_safety_result_packet.get("actual_status", ""),
        "blocked_by_host_environment": blocked_by_host,
        "blocked_by_host_environment_counted_as_pass": False,
        "native_launch_attempted": custom_native_launch_safety_packet.get(
            "native_launch_attempted"
        ),
        "native_launch_safety_packet_status": custom_native_launch_safety_packet.get(
            "status"
        ),
        "protected_surface_diff_clean": protected_surface_diff_packet.get(
            "all_protected_surfaces_unchanged"
        )
        is True,
        "cleanup_custom_owned_only": cleanup_reversibility_packet.get("status") == "ok",
        "keychain_mutation_required": keychain_observation_packet.get("status")
        == "blocked",
        "native_ux_acceptance_proven": False,
        "owner_visible_response_proven": False,
        "machine_ui_input_field_proven": False,
        "native_wbp_routing_success_proven": False,
        "response_accepted_by_codex_proven": False,
        "direct_egress_absence_proven": False,
        "model_availability_reproved": False,
        "streaming_compatibility_proven": False,
        "tool_call_loop_compatibility_proven": False,
        "full_responses_wire_compatibility_proven": False,
        "original_codex_reversibility_proven": False,
        "final_e2e_proven": False,
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


def classify_keychain_observation(
    *,
    machine_prompt_observed: bool,
    owner_pressed_cancel: bool = False,
    keychain_reset_performed: bool = False,
    keychain_default_changed: bool = False,
) -> dict[str, Any]:
    manual_cancel_only = bool(owner_pressed_cancel and machine_prompt_observed)
    blocked = keychain_reset_performed or keychain_default_changed
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "keychain_observation",
        "status": "blocked" if blocked else "ok",
        "reason_class": "KEYCHAIN_MUTATION_REQUIRED" if blocked else "",
        "machine_prompt_observed": machine_prompt_observed,
        "owner_pressed_cancel": owner_pressed_cancel,
        "owner_cancel_classification": (
            "manual_observation_only" if manual_cancel_only else "not_applicable"
        ),
        "keychain_reset_performed": keychain_reset_performed,
        "keychain_default_changed": keychain_default_changed,
        "keychain_cancel_equals_auth_success": False,
        "auth_success_claimed": False,
    }


def build_owner_action_boundary_packet(
    *,
    ordinary_codex_close_requested: bool = False,
    ordinary_codex_close_confirmed: bool = False,
    prompt_submitted: bool = False,
    runtime_authority_edited: bool = False,
    hidden_cleanup_performed: bool = False,
) -> dict[str, Any]:
    violation = prompt_submitted or runtime_authority_edited or hidden_cleanup_performed
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_action_boundary",
        "status": "blocked" if violation else "ok",
        "reason_class": "OWNER_ACTION_BOUNDARY_VIOLATED" if violation else "",
        "allowed_actions": [
            "close ordinary Codex",
            "confirm ordinary Codex is closed",
            "press Cancel on Keychain prompt if it appears",
            "confirm no prompt was typed",
        ],
        "forbidden_actions": [
            "edit config",
            "edit model/provider/route/account",
            "move profile paths",
            "patch app/runtime",
            "manually delete hidden profile/protected files",
            "type prompt into Custom window",
        ],
        "ordinary_codex_close_requested": ordinary_codex_close_requested,
        "ordinary_codex_close_confirmed": ordinary_codex_close_confirmed,
        "prompt_submitted": prompt_submitted,
        "runtime_authority_edited": runtime_authority_edited,
        "hidden_cleanup_performed": hidden_cleanup_performed,
    }


def build_owner_ux_action_boundary_packet(
    *,
    owner_typed_specified_prompt: bool,
    runtime_authority_edited: bool = False,
    provider_or_model_authority_edited: bool = False,
    hidden_cleanup_performed: bool = False,
) -> dict[str, Any]:
    violation = (
        runtime_authority_edited
        or provider_or_model_authority_edited
        or hidden_cleanup_performed
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_ux_action_boundary",
        "status": "blocked" if violation else "ok",
        "reason_class": "OWNER_ACTION_BOUNDARY_VIOLATED" if violation else "",
        "allowed_actions": [
            "observe isolated Custom native window",
            "type the specified nonce prompt into isolated Custom window",
            "confirm visible response",
            "press Cancel on Keychain prompt if it appears",
            "confirm cleanup result",
        ],
        "forbidden_actions": [
            "edit config",
            "edit model/provider/route/account",
            "move profile paths",
            "patch app/runtime",
            "perform hidden cleanup outside packet",
        ],
        "owner_typed_specified_prompt": owner_typed_specified_prompt,
        "runtime_authority_edited": runtime_authority_edited,
        "provider_or_model_authority_edited": provider_or_model_authority_edited,
        "hidden_cleanup_performed": hidden_cleanup_performed,
        "owner_prompt_action_allowed": True,
        "owner_prompt_action_grants_route_claim": False,
    }


def classify_host_context(host_process_chain: list[dict[str, Any]]) -> dict[str, Any]:
    host_negative = classify_protected_codex_host_negative(host_process_chain)
    if not host_process_chain:
        context = "unproven"
        status = "blocked"
        reason_class = "HOST_CONTEXT_UNPROVEN"
    elif host_negative.get("hosted_by_protected_codex_session"):
        context = "protected_codex_hosted"
        status = "blocked"
        reason_class = "PROTECTED_CODEX_HOSTED_EXECUTOR"
    else:
        context = "detached_external"
        status = "ok"
        reason_class = ""
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "host_context",
        "status": status,
        "reason_class": reason_class,
        "executor_context": context,
        "host_process_chain": host_process_chain,
        "host_process_chain_length": len(host_process_chain),
        "hosted_by_protected_codex_session": host_negative.get(
            "hosted_by_protected_codex_session"
        ),
        "protected_codex_ancestry_disproven": host_negative.get(
            "protected_codex_ancestry_disproven"
        ),
        "machine_filesystem_proof_environment_constrained": context
        == "protected_codex_hosted",
    }


def build_quiescent_retry_launch_admission_packet(
    *,
    host_context_packet: dict[str, Any],
    owner_action_boundary_packet: dict[str, Any],
    quiescent_precondition_packet: dict[str, Any],
    idle_stability_packet: dict[str, Any] | None = None,
    declared_write_surfaces_packet: dict[str, Any] | None = None,
    protected_surface_read_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if host_context_packet.get("status") != "ok":
        failed_checks.append("host_context_required")
    if owner_action_boundary_packet.get("status") != "ok":
        failed_checks.append("owner_action_boundary_required")
    if not quiescent_precondition_packet.get(
        "quiescent_current_codex_precondition_satisfied"
    ):
        failed_checks.append("quiescent_current_codex_required")
    if idle_stability_packet is None:
        failed_checks.append("idle_stability_required")
    elif idle_stability_packet.get("final_verdict") != "ACTIVE_CURRENT_CODEX_BASELINE_STABLE":
        failed_checks.append("idle_stability_required")
    if declared_write_surfaces_packet is None or declared_write_surfaces_packet.get("status") != "ok":
        failed_checks.append("declared_write_surfaces_required")
    if protected_surface_read_packet is None or not protected_surface_read_packet.get(
        "inspection_only"
    ):
        failed_checks.append("protected_surface_read_classification_required")
    launch_admitted = not failed_checks
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "quiescent_retry_launch_admission",
        "status": "ok" if launch_admitted else "blocked",
        "reason_class": "" if launch_admitted else "PRELAUNCH_GATE_BLOCKED",
        "native_launch_admitted": launch_admitted,
        "native_launch_attempted": False,
        "failed_checks": failed_checks,
        "host_context": host_context_packet.get("executor_context"),
        "quiescent_precondition_satisfied": quiescent_precondition_packet.get(
            "quiescent_current_codex_precondition_satisfied"
        ),
        "idle_stability_final_verdict": (
            idle_stability_packet or {}
        ).get("final_verdict"),
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
    }


def build_quiescent_retry_blocker_packet(
    *,
    launch_admission_packet: dict[str, Any],
    host_context_packet: dict[str, Any],
    quiescent_precondition_packet: dict[str, Any],
    idle_stability_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if host_context_packet.get("executor_context") == "protected_codex_hosted":
        actual_status = "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_HOSTED_EXECUTOR_CONTEXT"
    elif not quiescent_precondition_packet.get(
        "quiescent_current_codex_precondition_satisfied"
    ):
        actual_status = "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_NON_QUIESCENT_CURRENT_CODEX"
    elif idle_stability_packet and idle_stability_packet.get(
        "final_verdict"
    ) != "ACTIVE_CURRENT_CODEX_BASELINE_STABLE":
        actual_status = "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_IDLE_PROTECTED_SURFACE_DRIFT"
    else:
        actual_status = "NATIVE_CUSTOM_SAFETY_BLOCKED_BY_PRELAUNCH_GATE"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "quiescent_retry_blocker",
        "status": "blocked",
        "target_status": "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS",
        "target_status_achieved": False,
        "actual_status": actual_status,
        "reason_class": launch_admission_packet.get(
            "reason_class", "PRELAUNCH_GATE_BLOCKED"
        ),
        "failed_checks": launch_admission_packet.get("failed_checks", []),
        "native_launch_attempted": False,
        "filesystem_retry_attempted": False,
        "route_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
    }


def build_external_detached_handoff_command_packet(
    *,
    repo_root: Path,
    evidence_dir: Path,
    python_bin: str = "python3",
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    evidence_dir = evidence_dir.resolve()
    tool_path = repo_root / "tools" / "native_custom_quiescent_safety_retry_probe.py"
    argv = [
        python_bin,
        str(tool_path),
        "--repo-root",
        str(repo_root),
        "--evidence-dir",
        str(evidence_dir),
    ]
    shell_command = (
        f"cd {shlex.quote(str(repo_root))} && "
        + " ".join(shlex.quote(part) for part in argv)
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_detached_command",
        "status": "ok",
        "cwd": str(repo_root),
        "argv": argv,
        "shell_command": shell_command,
        "target_tool": str(tool_path),
        "evidence_dir": str(evidence_dir),
        "command_executed": False,
        "external_result_imported": False,
        "native_launch_attempted_from_current_thread": False,
    }


def build_external_detached_command_admission_packet(
    command_packet: dict[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    argv = [str(part) for part in command_packet.get("argv", [])]
    cwd = Path(str(command_packet.get("cwd", ""))).expanduser()
    evidence_dir = Path(str(command_packet.get("evidence_dir", ""))).expanduser()
    target_tool = str(command_packet.get("target_tool", ""))
    wildcard_chars = {"*", "?", "["}
    failed_checks: list[str] = []
    if cwd.resolve() != repo_root:
        failed_checks.append("cwd_must_equal_repo_root")
    if len(argv) < 6:
        failed_checks.append("argv_shape_required")
    if any(any(char in part for char in wildcard_chars) for part in argv):
        failed_checks.append("shell_wildcards_forbidden")
    if any("$" in part or "`" in part for part in argv):
        failed_checks.append("shell_expansion_forbidden")
    if target_tool != str(repo_root / "tools" / "native_custom_quiescent_safety_retry_probe.py"):
        failed_checks.append("target_tool_must_be_quiescent_retry_probe")
    try:
        evidence_dir.relative_to(repo_root / "audit_results")
    except ValueError:
        failed_checks.append("evidence_dir_must_be_under_audit_results")
    if "EXTERNAL" not in evidence_dir.name:
        failed_checks.append("external_evidence_dir_marker_required")
    if command_packet.get("command_executed"):
        failed_checks.append("handoff_only_command_must_not_be_executed")
    if command_packet.get("external_result_imported"):
        failed_checks.append("handoff_only_result_must_not_be_imported")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_detached_command_admission",
        "status": "ok" if not failed_checks else "blocked",
        "reason_class": "" if not failed_checks else "UNSAFE_COMMAND_SURFACE",
        "failed_checks": failed_checks,
        "cwd_fixed": cwd.resolve() == repo_root,
        "repo_root_fixed": str(repo_root) in argv,
        "evidence_dir_fixed": str(evidence_dir) in argv,
        "no_shell_wildcard": "shell_wildcards_forbidden" not in failed_checks,
        "no_shell_variable_expansion": "shell_expansion_forbidden" not in failed_checks,
        "expected_writes": [
            str(evidence_dir),
            "/tmp/wbp-native-fs-* only if the external retry later admits launch",
        ],
        "protected_surfaces_write_allowed": False,
        "route_model_account_provider_mutation_allowed": False,
        "expected_exit_codes": {
            "0": "external retry reached a pass-classified result",
            "1": "external retry produced honest blocker evidence",
            "other": "tool/runtime failure requiring diagnosis",
        },
        "command_executed": False,
        "external_result_imported": False,
    }


def build_external_detached_operator_boundary_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_detached_operator_boundary",
        "status": "ok",
        "owner_allowed_actions": [
            "close ordinary Codex before running command",
            "open Terminal outside Codex",
            "run exactly the generated command",
            "preserve generated evidence directory",
            "report command exit code and evidence path later",
        ],
        "owner_forbidden_actions": [
            "edit command",
            "edit config/model/provider/route/account",
            "manually cleanup hidden files",
            "type prompt into Custom window",
            "mark pass without packet output",
        ],
        "owner_edits_command_allowed": False,
        "owner_runtime_authority_edits_allowed": False,
        "owner_prompt_allowed": False,
    }


def build_external_detached_import_contract_packet(
    *,
    required_packets: list[str] | None = None,
) -> dict[str, Any]:
    packets = required_packets or [
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "host_context_packet.json",
        "owner_action_boundary_packet.json",
        "current_codex_running_state_initial.json",
        "quiescent_current_codex_precondition_packet.json",
        "pre_custom_idle_stability_packet.json",
        "launch_admission_packet.json",
        "native_safety_blocker_packet.json or native safety pass packets",
        "allowed_claims_matrix.json",
        "native_safety_false_green_audit.json",
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_detached_import_contract",
        "status": "ok",
        "required_packets": packets,
        "future_import_must_verify_json": True,
        "future_import_must_verify_no_secrets": True,
        "future_import_must_verify_host_detached_if_launch_proceeded": True,
        "future_import_must_verify_quiescent_if_launch_proceeded": True,
        "future_import_must_verify_idle_stability_if_launch_proceeded": True,
        "future_import_must_verify_launch_admission_matches_attempt": True,
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
        "model_availability_reproof_allowed": False,
        "external_result_imported_in_this_contour": False,
    }


def build_no_launch_from_current_thread_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "no_launch_from_current_thread",
        "status": "ok",
        "native_launch_attempted": False,
        "filesystem_retry_attempted": False,
        "external_command_executed": False,
        "external_result_imported": False,
        "claim_scope": "handoff_only",
    }


def build_external_detached_handoff_allowed_claims_matrix() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_detached_handoff_allowed_claims_matrix",
        "status": "ok",
        "allowed_claims": [
            "EXTERNAL_DETACHED_NATIVE_SAFETY_RETRY_HANDOFF_READY",
            "external_command_bounded",
            "operator_boundary_defined",
            "import_contract_defined",
            "no_launch_from_current_thread_proven",
        ],
        "forbidden_claims": [
            "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS",
            "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_PROVEN",
            "native_safety_passed",
            "native_route_proven",
            "owner_ux_proven",
            "direct_egress_absent",
            "Original_Codex_via_WBP_proven",
            "model_availability_reproven",
            "auth_strategy_reproven",
            "external_result_passed_before_import",
            "external_result_classified_in_handoff_only_mode",
        ],
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "native_safety_pass_claim_allowed": False,
    }


def build_external_detached_handoff_false_green_audit(
    *,
    command_admission_packet: dict[str, Any],
    import_contract_packet: dict[str, Any],
    no_launch_packet: dict[str, Any],
    allowed_claims_matrix: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        {
            "name": "command_admission_ok",
            "passed": command_admission_packet.get("status") == "ok",
        },
        {
            "name": "no_native_launch_from_current_thread",
            "passed": no_launch_packet.get("native_launch_attempted") is False
            and no_launch_packet.get("filesystem_retry_attempted") is False,
        },
        {
            "name": "no_external_result_import",
            "passed": import_contract_packet.get("external_result_imported_in_this_contour")
            is False,
        },
        {
            "name": "no_route_ux_egress_claim",
            "passed": not allowed_claims_matrix.get("route_claim_allowed", True)
            and not allowed_claims_matrix.get("ux_claim_allowed", True)
            and not allowed_claims_matrix.get("egress_claim_allowed", True),
        },
        {
            "name": "native_safety_pass_not_claimed",
            "passed": not allowed_claims_matrix.get("native_safety_pass_claim_allowed", True),
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_detached_handoff_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "forbidden_claims_present": False,
    }


def build_external_result_execution_ownership_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_execution_ownership",
        "status": "ok",
        "current_thread_external_command_executed": False,
        "current_thread_native_launch_attempted": False,
        "current_thread_owner_prompt_submitted": False,
        "owner_execution_required": True,
        "owner_command_edit_allowed": False,
        "claim_scope": "import_and_classification_only",
    }


def build_external_result_command_integrity_packet(
    *,
    handoff_command_packet: dict[str, Any],
    external_evidence_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    expected_evidence_dir = Path(str(handoff_command_packet.get("evidence_dir", ""))).resolve()
    actual_evidence_dir = external_evidence_dir.resolve()
    command_admission = build_external_detached_command_admission_packet(
        handoff_command_packet,
        repo_root=repo_root,
    )
    failed_checks = list(command_admission.get("failed_checks", []))
    if expected_evidence_dir != actual_evidence_dir:
        failed_checks.append("external_evidence_path_mismatch")
    if handoff_command_packet.get("command_executed"):
        failed_checks.append("handoff_packet_must_not_mark_command_executed")
    if handoff_command_packet.get("external_result_imported"):
        failed_checks.append("handoff_packet_must_not_mark_result_imported")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_command_integrity",
        "status": "ok" if not failed_checks else "blocked",
        "failed_checks": failed_checks,
        "expected_external_evidence_dir": str(expected_evidence_dir),
        "actual_external_evidence_dir": str(actual_evidence_dir),
        "external_evidence_path_matches_handoff": expected_evidence_dir == actual_evidence_dir,
        "target_tool": handoff_command_packet.get("target_tool", ""),
        "cwd": handoff_command_packet.get("cwd", ""),
        "no_shell_wildcard": command_admission.get("no_shell_wildcard") is True,
        "no_shell_variable_expansion": command_admission.get("no_shell_variable_expansion") is True,
        "current_thread_executed_command": False,
    }


def validate_external_evidence_packets(
    *,
    external_evidence_dir: Path,
    required_packets: list[str],
) -> dict[str, Any]:
    external_evidence_dir = external_evidence_dir.resolve()
    required: list[str] = []
    alternatives: list[str] = []
    for packet in required_packets:
        if " or " in packet:
            alternatives.append(packet)
        else:
            required.append(packet)

    packet_statuses: dict[str, str] = {}
    parsed_packets: dict[str, Any] = {}
    missing_packets: list[str] = []
    invalid_json_packets: list[str] = []
    if not external_evidence_dir.exists():
        missing_packets = required[:]
        for packet in required:
            packet_statuses[packet] = "missing"
    else:
        for packet in required:
            path = external_evidence_dir / packet
            if not path.exists():
                packet_statuses[packet] = "missing"
                missing_packets.append(packet)
                continue
            try:
                parsed_packets[packet] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                packet_statuses[packet] = "invalid_json"
                invalid_json_packets.append(packet)
                continue
            packet_statuses[packet] = "present"

    alternative_statuses: dict[str, str] = {}
    for alternative in alternatives:
        choices = [choice.strip() for choice in alternative.split(" or ")]
        present = [choice for choice in choices if (external_evidence_dir / choice).exists()]
        alternative_statuses[alternative] = "present" if present else "missing"
        if present:
            for choice in present:
                try:
                    parsed_packets[choice] = json.loads(
                        (external_evidence_dir / choice).read_text(encoding="utf-8")
                    )
                except json.JSONDecodeError:
                    invalid_json_packets.append(choice)
                    alternative_statuses[alternative] = "invalid_json"
        else:
            missing_packets.append(alternative)

    status = "ok"
    reason_class = ""
    if not external_evidence_dir.exists():
        status = "blocked"
        reason_class = "EXTERNAL_EVIDENCE_DIR_MISSING"
    elif missing_packets:
        status = "blocked"
        reason_class = "REQUIRED_EXTERNAL_PACKETS_MISSING"
    elif invalid_json_packets:
        status = "blocked"
        reason_class = "INVALID_EXTERNAL_PACKET_JSON"

    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_evidence_validation",
        "status": status,
        "reason_class": reason_class,
        "external_evidence_dir": str(external_evidence_dir),
        "external_evidence_dir_exists": external_evidence_dir.exists(),
        "required_packets": required_packets,
        "packet_statuses": packet_statuses,
        "alternative_statuses": alternative_statuses,
        "missing_packets": missing_packets,
        "invalid_json_packets": invalid_json_packets,
        "json_validated": status == "ok",
        "parsed_packet_count": len(parsed_packets),
        "parsed_packets": parsed_packets,
        "partial_write_state_detected": False,
    }


def build_external_result_secret_scan_packet(
    *,
    external_evidence_dir: Path,
    matches: list[str],
) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_secret_scan",
        "status": "ok" if not matches else "blocked",
        "external_evidence_dir": str(external_evidence_dir.resolve()),
        "secret_scan_performed": True,
        "raw_secret_matches": matches,
        "raw_secrets_found": bool(matches),
    }


def build_import_allowed_claims_matrix() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_import_allowed_claims_matrix",
        "status": "ok",
        "allowed_claims": [
            "external evidence imported",
            "external evidence validated",
            "native filesystem safety classified",
            "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORTED_PASS_WITH_LIMITS",
            "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
        ],
        "forbidden_claims": [
            "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_PROVEN",
            "CODEX_CUSTOM_NATIVE_APP_USABLE",
            "NATIVE_ROUTING_PROVEN",
            "OWNER_UX_PROVEN",
            "DIRECT_EGRESS_ABSENT",
            "ORIGINAL_CODEX_VIA_WBP_PROVEN",
            "MODEL_AVAILABILITY_PROVEN",
            "AUTH_STRATEGY_PROVEN",
            "FINAL_E2E_COMPLETE",
        ],
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
        "model_availability_reproof_allowed": False,
    }


def build_layer_separation_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_import_layer_separation",
        "status": "ok",
        "current_contour_scope": "native_filesystem_safety_import_only",
        "deferred_or_incidental_observations": [
            "route traces",
            "WBP 200 responses",
            "visible native window",
            "owner screenshots",
            "owner prompt-response observations",
            "network egress observations",
            "model availability observations",
            "auth/account observations",
        ],
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
        "model_availability_reproof_allowed": False,
    }


def build_keychain_boundary_packet(
    *,
    keychain_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keychain_packet = keychain_packet or {}
    reset_required = keychain_packet.get("keychain_reset_performed") is True
    default_required = keychain_packet.get("keychain_default_required") is True
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_import_keychain_boundary",
        "status": "blocked" if reset_required or default_required else "ok",
        "reason_class": "KEYCHAIN_MUTATION_REQUIRED"
        if reset_required or default_required
        else "",
        "keychain_observation_present": bool(keychain_packet),
        "keychain_observation_classifies_native_safety_only": True,
        "keychain_observation_treated_as_auth_proof": False,
        "keychain_reset_required": reset_required,
        "keychain_default_required": default_required,
    }


def build_protected_surface_import_summary(
    *,
    validation_packet: dict[str, Any],
) -> dict[str, Any]:
    parsed_packets = validation_packet.get("parsed_packets", {})
    diff_packet = parsed_packets.get("protected_surface_recursive_diff.json", {})
    surfaces = diff_packet.get("surfaces", {})
    classifications: dict[str, str] = {}
    if not diff_packet:
        classifications = {
            "~/.codex": "not_measured_blocker",
            "~/Library/Application Support/Codex": "not_measured_blocker",
            "~/Library/Caches/com.openai.codex": "not_measured_blocker",
            "~/Library/HTTPStorages/com.openai.codex": "not_measured_blocker",
        }
    else:
        for name, surface in surfaces.items():
            diff = surface.get("diff", {})
            changed = bool(diff.get("created") or diff.get("deleted") or diff.get("changed"))
            classifications[name] = "changed_unexpected_blocker" if changed else "unchanged"
    all_safe = bool(classifications) and all(
        value in {"unchanged", "changed_safe_owned"} for value in classifications.values()
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "protected_surface_import_summary",
        "status": "ok" if all_safe else "blocked",
        "surface_classifications": classifications,
        "all_protected_surfaces_safe": all_safe,
    }


def classify_native_safety_retry_import(
    *,
    command_integrity_packet: dict[str, Any],
    validation_packet: dict[str, Any],
    secret_scan_packet: dict[str, Any],
    protected_surface_summary_packet: dict[str, Any],
    keychain_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    parsed_packets = validation_packet.get("parsed_packets", {})
    launch_admission = parsed_packets.get("launch_admission_packet.json", {})
    cleanup = parsed_packets.get("cleanup_reversibility_packet.json", {})
    false_green = parsed_packets.get("native_safety_false_green_audit.json", {})
    failed_checks: list[str] = []
    if command_integrity_packet.get("status") != "ok":
        failed_checks.append("external_command_integrity_required")
    if validation_packet.get("status") != "ok":
        failed_checks.append("external_evidence_validation_required")
    if secret_scan_packet.get("status") != "ok":
        failed_checks.append("secret_scan_clean_required")
    if launch_admission.get("native_launch_admitted") is not True:
        failed_checks.append("native_launch_admission_required")
    if protected_surface_summary_packet.get("status") != "ok":
        failed_checks.append("protected_surface_import_summary_required")
    if cleanup and cleanup.get("tmp_root_removed") is not True:
        failed_checks.append("cleanup_reversibility_required")
    if keychain_boundary_packet.get("status") != "ok":
        failed_checks.append("keychain_boundary_required")
    if false_green and false_green.get("status") != "ok":
        failed_checks.append("native_safety_false_green_audit_required")

    final_status = (
        "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORTED_PASS_WITH_LIMITS"
        if not failed_checks
        else "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED"
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_safety_retry_import_classification",
        "status": "ok" if not failed_checks else "blocked",
        "final_status": final_status,
        "failed_checks": failed_checks,
        "native_safety_pass_claimed": not failed_checks,
        "route_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
    }


def build_external_result_import_packet(
    *,
    validation_packet: dict[str, Any],
    classification_packet: dict[str, Any],
) -> dict[str, Any]:
    evidence_json_loaded = validation_packet.get("status") == "ok"
    classification_ok = classification_packet.get("status") == "ok"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_result_import",
        "status": "ok" if evidence_json_loaded and classification_ok else "blocked",
        "external_evidence_dir": validation_packet.get("external_evidence_dir", ""),
        "external_evidence_json_loaded": evidence_json_loaded,
        "external_result_imported": evidence_json_loaded and classification_ok,
        "external_result_classified": True,
        "classification_status": classification_packet.get("status"),
        "final_status": classification_packet.get("final_status"),
    }


def build_native_safety_import_false_green_audit(
    *,
    execution_ownership_packet: dict[str, Any],
    command_integrity_packet: dict[str, Any],
    validation_packet: dict[str, Any],
    secret_scan_packet: dict[str, Any],
    classification_packet: dict[str, Any],
    allowed_claims_matrix: dict[str, Any],
    layer_separation_packet: dict[str, Any],
    keychain_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        {
            "name": "current_thread_did_not_execute_external_command",
            "passed": execution_ownership_packet.get("current_thread_external_command_executed")
            is False,
        },
        {
            "name": "current_thread_did_not_launch_native_app",
            "passed": execution_ownership_packet.get("current_thread_native_launch_attempted")
            is False,
        },
        {
            "name": "external_command_integrity_verified_or_blocked",
            "passed": command_integrity_packet.get("status") in {"ok", "blocked"},
        },
        {
            "name": "external_evidence_json_validated_or_missing_blocked",
            "passed": validation_packet.get("status") in {"ok", "blocked"},
        },
        {
            "name": "secret_scan_clean_or_blocked",
            "passed": secret_scan_packet.get("status") in {"ok", "blocked"},
        },
        {
            "name": "route_ux_egress_auth_model_claims_forbidden",
            "passed": not allowed_claims_matrix.get("route_claim_allowed", True)
            and not allowed_claims_matrix.get("ux_claim_allowed", True)
            and not allowed_claims_matrix.get("egress_claim_allowed", True)
            and not allowed_claims_matrix.get("auth_strategy_reproof_allowed", True)
            and not allowed_claims_matrix.get("model_availability_reproof_allowed", True),
        },
        {
            "name": "layer_separation_respected",
            "passed": layer_separation_packet.get("status") == "ok",
        },
        {
            "name": "keychain_not_auth_proof",
            "passed": keychain_boundary_packet.get("keychain_observation_treated_as_auth_proof")
            is False,
        },
        {
            "name": "blocked_result_not_counted_as_pass",
            "passed": classification_packet.get("status") == "ok"
            or classification_packet.get("final_status")
            == "NATIVE_CUSTOM_FILESYSTEM_SAFETY_IMPORT_BLOCKED",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_safety_import_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "forbidden_claims_present": False,
    }


EXTERNAL_EXECUTION_MINIMAL_EXPECTED_PACKETS = [
    "sync_gate_packet.json",
    "historical_dirt_quarantine_packet.json",
    "version_pinning_packet.json",
    "host_context_packet.json",
    "owner_action_boundary_packet.json",
    "current_codex_running_state_initial.json",
    "quiescent_current_codex_precondition_packet.json",
    "pre_custom_idle_stability_packet.json",
    "launch_admission_packet.json",
    "allowed_claims_matrix.json",
    "native_safety_false_green_audit.json",
]


def build_external_execution_scope_boundary_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_scope_boundary",
        "status": "ok",
        "current_contour_scope": "external_execution_evidence_only",
        "safety_result_imported": False,
        "filesystem_safety_classified": False,
        "native_safety_pass_claimed": False,
        "routing_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
    }


def build_owner_execution_boundary_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_external_execution_boundary",
        "status": "ok",
        "owner_allowed_actions": [
            "open external Terminal",
            "run exactly generated shell_command",
            "report exit code if visible",
            "leave evidence directory untouched",
        ],
        "owner_forbidden_actions": [
            "edit command",
            "change config/model/provider/account",
            "move evidence/profile paths",
            "patch app/runtime",
            "manually cleanup hidden Codex files",
            "type prompt into Custom window",
            "declare pass from screenshot",
        ],
        "owner_command_edit_allowed": False,
        "owner_runtime_authority_edits_allowed": False,
        "owner_prompt_allowed": False,
    }


def build_external_execution_command_verification_packet(
    *,
    handoff_command_packet: dict[str, Any],
    external_evidence_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    integrity = build_external_result_command_integrity_packet(
        handoff_command_packet=handoff_command_packet,
        external_evidence_dir=external_evidence_dir,
        repo_root=repo_root,
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_command_verification",
        "status": integrity["status"],
        "failed_checks": integrity["failed_checks"],
        "cwd": integrity["cwd"],
        "target_tool": integrity["target_tool"],
        "expected_external_evidence_dir": integrity["expected_external_evidence_dir"],
        "actual_external_evidence_dir": integrity["actual_external_evidence_dir"],
        "external_evidence_path_matches_handoff": integrity[
            "external_evidence_path_matches_handoff"
        ],
        "no_shell_wildcard": integrity["no_shell_wildcard"],
        "no_shell_variable_expansion": integrity["no_shell_variable_expansion"],
        "command_executed_in_current_thread": False,
        "shell_command": handoff_command_packet.get("shell_command", ""),
    }


def build_external_execution_observation_packet(
    *,
    shell_command: str,
    reported_exit_code: int | None = None,
) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_observation",
        "status": "ok",
        "owner_execution_requested": True,
        "reported_exit_code": reported_exit_code,
        "shell_command_presented_to_owner": shell_command,
        "current_thread_executed_command": False,
        "native_launch_from_current_thread": False,
        "owner_prompt_submitted": False,
    }


def build_external_evidence_presence_packet(
    *,
    external_evidence_dir: Path,
    minimal_expected_packets: list[str] | None = None,
) -> dict[str, Any]:
    external_evidence_dir = external_evidence_dir.resolve()
    expected = minimal_expected_packets or EXTERNAL_EXECUTION_MINIMAL_EXPECTED_PACKETS
    file_list: list[str] = []
    packet_statuses: dict[str, str] = {}
    missing_packets: list[str] = []
    invalid_json_packets: list[str] = []
    alternative_block_present = False
    if external_evidence_dir.exists():
        file_list = sorted(
            str(path.relative_to(external_evidence_dir))
            for path in external_evidence_dir.rglob("*")
            if path.is_file()
        )
        for packet in expected:
            path = external_evidence_dir / packet
            if not path.exists():
                packet_statuses[packet] = "missing"
                missing_packets.append(packet)
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                packet_statuses[packet] = "invalid_json"
                invalid_json_packets.append(packet)
                continue
            packet_statuses[packet] = "present"
        alternative_block_present = (
            (external_evidence_dir / "native_safety_blocker_packet.json").exists()
            or (external_evidence_dir / "protected_surface_recursive_diff.json").exists()
        )
        if not alternative_block_present:
            missing_packets.append(
                "native_safety_blocker_packet.json OR protected surface packet set"
            )
    classification = "evidence_dir_present"
    status = "ok"
    reason_class = ""
    if not external_evidence_dir.exists():
        classification = "evidence_dir_missing"
        status = "blocked"
        reason_class = "EXTERNAL_EVIDENCE_DIR_MISSING"
    elif invalid_json_packets:
        classification = "evidence_present_but_invalid_json"
        status = "blocked"
        reason_class = "EXTERNAL_EVIDENCE_INVALID_JSON"
    elif missing_packets:
        classification = "evidence_present_but_required_packets_missing"
        status = "blocked"
        reason_class = "EXTERNAL_EVIDENCE_REQUIRED_PACKETS_MISSING"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_evidence_presence",
        "status": status,
        "reason_class": reason_class,
        "classification": classification,
        "external_evidence_dir": str(external_evidence_dir),
        "external_evidence_dir_exists": external_evidence_dir.exists(),
        "file_list": file_list,
        "minimal_expected_packets": expected,
        "packet_statuses": packet_statuses,
        "missing_packets": missing_packets,
        "invalid_json_packets": invalid_json_packets,
        "json_parse_check_completed": external_evidence_dir.exists(),
        "safety_result_imported": False,
        "filesystem_safety_classified": False,
    }


def build_external_execution_secret_scan_packet(
    *,
    external_evidence_dir: Path,
    matches: list[str],
) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_secret_scan",
        "status": "ok" if not matches else "blocked",
        "external_evidence_dir": str(external_evidence_dir.resolve()),
        "secret_scan_performed": True,
        "raw_secret_matches": matches,
        "raw_secrets_found": bool(matches),
    }


def build_execution_layer_separation_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_layer_separation",
        "status": "ok",
        "current_contour_scope": "evidence_production_only",
        "incidental_only": [
            "native process",
            "native window",
            "Keychain prompt",
            "WBP trace",
            "HTTP status",
            "model id",
            "network egress",
            "owner screenshot",
            "owner visual confirmation",
        ],
        "safety_result_imported": False,
        "filesystem_safety_classified": False,
        "native_safety_pass_claimed": False,
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
        "model_availability_reproof_allowed": False,
    }


def build_external_execution_result_packet(
    *,
    command_verification_packet: dict[str, Any],
    evidence_presence_packet: dict[str, Any],
    secret_scan_packet: dict[str, Any],
) -> dict[str, Any]:
    if command_verification_packet.get("status") != "ok":
        final_status = "EXTERNAL_NATIVE_SAFETY_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    elif secret_scan_packet.get("status") != "ok":
        final_status = "EXTERNAL_NATIVE_SAFETY_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    elif evidence_presence_packet.get("classification") == "evidence_dir_missing":
        final_status = "EXTERNAL_NATIVE_SAFETY_EXECUTION_NO_EVIDENCE_PRODUCED"
    elif evidence_presence_packet.get("status") == "ok":
        final_status = "EXTERNAL_NATIVE_SAFETY_EXECUTION_EVIDENCE_PRODUCED"
    else:
        final_status = "EXTERNAL_NATIVE_SAFETY_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_result",
        "status": "ok"
        if final_status == "EXTERNAL_NATIVE_SAFETY_EXECUTION_EVIDENCE_PRODUCED"
        else "blocked",
        "final_status": final_status,
        "external_evidence_dir": evidence_presence_packet.get("external_evidence_dir", ""),
        "external_evidence_dir_exists": evidence_presence_packet.get(
            "external_evidence_dir_exists", False
        ),
        "safety_result_imported": False,
        "filesystem_safety_classified": False,
        "native_safety_pass_claimed": False,
        "routing_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
    }


def build_external_execution_false_green_audit(
    *,
    scope_boundary_packet: dict[str, Any],
    command_verification_packet: dict[str, Any],
    owner_boundary_packet: dict[str, Any],
    observation_packet: dict[str, Any],
    evidence_presence_packet: dict[str, Any],
    secret_scan_packet: dict[str, Any],
    result_packet: dict[str, Any],
    layer_separation_packet: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        {
            "name": "current_thread_did_not_execute_external_command",
            "passed": observation_packet.get("current_thread_executed_command") is False,
        },
        {
            "name": "current_thread_did_not_launch_native_app",
            "passed": observation_packet.get("native_launch_from_current_thread") is False,
        },
        {
            "name": "command_integrity_verified_or_blocked",
            "passed": command_verification_packet.get("status") in {"ok", "blocked"},
        },
        {
            "name": "owner_boundary_recorded",
            "passed": owner_boundary_packet.get("owner_command_edit_allowed") is False,
        },
        {
            "name": "evidence_presence_classified",
            "passed": evidence_presence_packet.get("classification")
            in {
                "evidence_dir_present",
                "evidence_dir_missing",
                "evidence_present_but_invalid_json",
                "evidence_present_but_required_packets_missing",
            },
        },
        {
            "name": "secret_scan_recorded",
            "passed": secret_scan_packet.get("secret_scan_performed") is True,
        },
        {
            "name": "safety_not_imported_or_classified",
            "passed": scope_boundary_packet.get("safety_result_imported") is False
            and scope_boundary_packet.get("filesystem_safety_classified") is False
            and result_packet.get("native_safety_pass_claimed") is False,
        },
        {
            "name": "route_ux_egress_auth_model_not_claimed",
            "passed": result_packet.get("routing_claimed") is False
            and result_packet.get("ux_claimed") is False
            and result_packet.get("egress_claimed") is False
            and result_packet.get("auth_strategy_reproved") is False
            and result_packet.get("model_availability_reproved") is False,
        },
        {
            "name": "blocked_or_no_evidence_not_counted_as_safety_pass",
            "passed": result_packet.get("final_status")
            != "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS",
        },
        {
            "name": "layer_separation_respected",
            "passed": layer_separation_packet.get("status") == "ok",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "external_execution_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "forbidden_claims_present": False,
    }


def build_current_thread_boundary_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_external_current_thread_boundary",
        "status": "ok",
        "current_thread_may_verify_handoff": True,
        "current_thread_may_check_evidence_presence": True,
        "current_thread_executed_external_command": False,
        "current_thread_launched_native_app": False,
        "current_thread_typed_into_custom_window": False,
        "current_thread_imported_safety_pass": False,
        "current_thread_classified_filesystem_safety": False,
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
        "model_availability_reproof_allowed": False,
    }


def build_owner_command_reverification_packet(
    *,
    handoff_command_packet: dict[str, Any],
    expected_shell_command: str,
    external_evidence_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    verification = build_external_execution_command_verification_packet(
        handoff_command_packet=handoff_command_packet,
        external_evidence_dir=external_evidence_dir,
        repo_root=repo_root,
    )
    failed_checks = list(verification.get("failed_checks", []))
    if handoff_command_packet.get("shell_command") != expected_shell_command:
        failed_checks.append("shell_command_mismatch")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_command_reverification",
        "status": "ok" if not failed_checks else "blocked",
        "failed_checks": failed_checks,
        "shell_command": handoff_command_packet.get("shell_command", ""),
        "expected_shell_command": expected_shell_command,
        "shell_command_matches_expected": handoff_command_packet.get("shell_command")
        == expected_shell_command,
        "cwd": verification.get("cwd", ""),
        "target_tool": verification.get("target_tool", ""),
        "external_evidence_path_matches_handoff": verification.get(
            "external_evidence_path_matches_handoff", False
        ),
        "command_executed_in_current_thread": False,
        "external_result_imported": False,
        "native_launch_attempted_from_current_thread": False,
        "no_shell_wildcard": verification.get("no_shell_wildcard") is True,
        "no_shell_variable_expansion": verification.get("no_shell_variable_expansion")
        is True,
    }


def build_owner_execution_attestation_packet(
    *,
    owner_reported_execution: bool = False,
) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_execution_attestation",
        "status": "ok" if owner_reported_execution else "blocked",
        "owner_reported_execution": owner_reported_execution,
        "owner_report_is_not_packet_truth": True,
        "owner_command_edit_allowed": False,
        "owner_config_model_provider_account_change_allowed": False,
        "owner_prompt_allowed": False,
        "owner_screenshot_counts_as_proof": False,
    }


def build_owner_execution_observation_packet(
    *,
    owner_reported_execution: bool = False,
    owner_reported_exit_code: int | None = None,
    owner_reported_output_summary: str = "",
) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_execution_observation",
        "status": "ok" if owner_reported_execution else "blocked",
        "owner_reported_execution": owner_reported_execution,
        "owner_reported_exit_code": owner_reported_exit_code,
        "owner_reported_output_summary": owner_reported_output_summary,
        "owner_report_is_not_packet_truth": True,
        "exit_code_used_as_proof": False,
        "current_thread_executed_command": False,
        "native_launch_from_current_thread": False,
    }


def build_no_safety_interpretation_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "no_safety_interpretation",
        "status": "ok",
        "safety_interpreted": False,
        "protected_surface_interpreted": False,
        "launch_admission_interpreted": False,
        "cleanup_interpreted": False,
        "keychain_interpreted_as_auth": False,
        "exit_code_used_as_proof": False,
    }


def build_external_execution_minimal_json_packet(
    *,
    evidence_presence_packet: dict[str, Any],
) -> dict[str, Any]:
    evidence_exists = evidence_presence_packet.get("external_evidence_dir_exists") is True
    invalid_json = list(evidence_presence_packet.get("invalid_json_packets", []))
    missing_packets = list(evidence_presence_packet.get("missing_packets", []))
    evidence_presence_ok = evidence_presence_packet.get("status") == "ok"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_external_execution_minimal_json",
        "status": "ok"
        if evidence_exists and evidence_presence_ok and not invalid_json and not missing_packets
        else "blocked",
        "external_evidence_dir": evidence_presence_packet.get("external_evidence_dir", ""),
        "json_parse_check_completed": evidence_presence_packet.get(
            "json_parse_check_completed", False
        ),
        "required_packets_present": evidence_presence_ok,
        "missing_packets": missing_packets,
        "invalid_json_packets": invalid_json,
        "safety_interpreted": False,
        "protected_surface_interpreted": False,
        "launch_admission_interpreted": False,
    }


def build_owner_execution_layer_separation_packet() -> dict[str, Any]:
    packet = build_execution_layer_separation_packet()
    packet["packet_kind"] = "owner_execution_layer_separation"
    packet["owner_report_is_not_packet_truth"] = True
    packet["exit_code_used_as_proof"] = False
    return packet


def build_owner_external_execution_result_packet(
    *,
    command_reverification_packet: dict[str, Any],
    owner_attestation_packet: dict[str, Any],
    evidence_presence_packet: dict[str, Any],
    minimal_json_packet: dict[str, Any],
    secret_scan_packet: dict[str, Any],
    no_safety_interpretation_packet: dict[str, Any],
) -> dict[str, Any]:
    owner_reported_execution = owner_attestation_packet.get(
        "owner_reported_execution", False
    )
    if command_reverification_packet.get("status") != "ok":
        final_status = "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    elif secret_scan_packet.get("status") != "ok":
        final_status = "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    elif evidence_presence_packet.get("classification") == "evidence_dir_missing":
        final_status = "OWNER_EXTERNAL_EXECUTION_NO_EVIDENCE_PRODUCED"
    elif owner_reported_execution is not True:
        final_status = "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    elif evidence_presence_packet.get("status") != "ok":
        final_status = "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    elif minimal_json_packet.get("status") == "ok":
        final_status = "OWNER_EXTERNAL_EXECUTION_EVIDENCE_PRODUCED"
    else:
        final_status = "OWNER_EXTERNAL_EXECUTION_BLOCKED_WITH_PACKET_TRUTH"
    evidence_produced = final_status == "OWNER_EXTERNAL_EXECUTION_EVIDENCE_PRODUCED"
    closeout_status_ok = final_status in {
        "OWNER_EXTERNAL_EXECUTION_EVIDENCE_PRODUCED",
        "OWNER_EXTERNAL_EXECUTION_NO_EVIDENCE_PRODUCED",
    }
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_external_execution_result",
        "status": "ok" if closeout_status_ok else "blocked",
        "final_status": final_status,
        "owner_reported_execution": owner_reported_execution,
        "owner_attestation_required_for_evidence_produced": True,
        "owner_external_execution_evidence_produced": evidence_produced,
        "external_evidence_dir": evidence_presence_packet.get("external_evidence_dir", ""),
        "external_evidence_dir_exists": evidence_presence_packet.get(
            "external_evidence_dir_exists", False
        ),
        "safety_interpreted": no_safety_interpretation_packet.get(
            "safety_interpreted", True
        ),
        "protected_surface_interpreted": no_safety_interpretation_packet.get(
            "protected_surface_interpreted", True
        ),
        "launch_admission_interpreted": no_safety_interpretation_packet.get(
            "launch_admission_interpreted", True
        ),
        "cleanup_interpreted": no_safety_interpretation_packet.get(
            "cleanup_interpreted", True
        ),
        "exit_code_used_as_proof": no_safety_interpretation_packet.get(
            "exit_code_used_as_proof", True
        ),
        "native_safety_pass_claimed": False,
        "routing_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
    }


def build_owner_execution_false_green_audit(
    *,
    current_thread_boundary_packet: dict[str, Any],
    command_reverification_packet: dict[str, Any],
    owner_attestation_packet: dict[str, Any],
    owner_observation_packet: dict[str, Any],
    evidence_presence_packet: dict[str, Any],
    minimal_json_packet: dict[str, Any],
    secret_scan_packet: dict[str, Any],
    no_safety_interpretation_packet: dict[str, Any],
    result_packet: dict[str, Any],
    layer_separation_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = (
        result_packet.get("native_safety_pass_claimed") is True
        or result_packet.get("routing_claimed") is True
        or result_packet.get("ux_claimed") is True
        or result_packet.get("egress_claimed") is True
        or result_packet.get("auth_strategy_reproved") is True
        or result_packet.get("model_availability_reproved") is True
        or result_packet.get("safety_interpreted") is True
        or result_packet.get("protected_surface_interpreted") is True
        or result_packet.get("launch_admission_interpreted") is True
        or result_packet.get("cleanup_interpreted") is True
    )
    checks = [
        {
            "name": "current_thread_did_not_execute_external_command",
            "passed": current_thread_boundary_packet.get(
                "current_thread_executed_external_command"
            )
            is False
            and owner_observation_packet.get("current_thread_executed_command") is False,
        },
        {
            "name": "current_thread_did_not_launch_native_app",
            "passed": current_thread_boundary_packet.get("current_thread_launched_native_app")
            is False
            and owner_observation_packet.get("native_launch_from_current_thread") is False,
        },
        {
            "name": "owner_command_boundary_recorded",
            "passed": owner_attestation_packet.get("owner_command_edit_allowed") is False,
        },
        {
            "name": "command_reverification_passed_or_blocked",
            "passed": command_reverification_packet.get("status") in {"ok", "blocked"},
        },
        {
            "name": "owner_execution_observation_recorded",
            "passed": "owner_reported_execution" in owner_observation_packet,
        },
        {
            "name": "evidence_produced_requires_owner_reported_execution",
            "passed": result_packet.get("owner_external_execution_evidence_produced")
            is not True
            or (
                owner_attestation_packet.get("owner_reported_execution") is True
                and owner_observation_packet.get("owner_reported_execution") is True
                and result_packet.get("owner_reported_execution") is True
            ),
        },
        {
            "name": "evidence_presence_classified",
            "passed": evidence_presence_packet.get("classification")
            in {
                "evidence_dir_present",
                "evidence_dir_missing",
                "evidence_present_but_invalid_json",
                "evidence_present_but_required_packets_missing",
            },
        },
        {
            "name": "json_parse_result_recorded",
            "passed": "json_parse_check_completed" in minimal_json_packet,
        },
        {
            "name": "secret_scan_recorded",
            "passed": secret_scan_packet.get("secret_scan_performed") is True,
        },
        {
            "name": "no_safety_interpretation",
            "passed": no_safety_interpretation_packet.get("safety_interpreted") is False
            and no_safety_interpretation_packet.get("protected_surface_interpreted") is False
            and no_safety_interpretation_packet.get("launch_admission_interpreted") is False
            and no_safety_interpretation_packet.get("cleanup_interpreted") is False
            and no_safety_interpretation_packet.get("exit_code_used_as_proof") is False,
        },
        {
            "name": "route_ux_egress_auth_model_not_claimed",
            "passed": result_packet.get("routing_claimed") is False
            and result_packet.get("ux_claimed") is False
            and result_packet.get("egress_claimed") is False
            and result_packet.get("auth_strategy_reproved") is False
            and result_packet.get("model_availability_reproved") is False,
        },
        {
            "name": "blocked_or_no_evidence_not_counted_as_pass",
            "passed": result_packet.get("final_status")
            != "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS",
        },
        {
            "name": "layer_separation_respected",
            "passed": layer_separation_packet.get("status") == "ok",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_execution_false_green_audit",
        "status": "ok"
        if all(check["passed"] for check in checks) and not forbidden_claims_present
        else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
    }


def classify_environment_blocked_result(
    *,
    item: str,
    status: str,
    root_cause: str = "",
    exercised: str = "",
    remains_unproven: str = "",
) -> dict[str, Any]:
    if status not in {"passed", "failed", "blocked_by_host_environment"}:
        raise ValueError("status must be passed, failed, or blocked_by_host_environment")
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "environment_blocked_result",
        "item": item,
        "status": status,
        "root_cause": root_cause,
        "what_was_exercised": exercised,
        "what_remains_unproven": remains_unproven,
        "counts_as_pass": status == "passed",
    }


def build_allowed_claims_matrix(*, final_status: str) -> dict[str, Any]:
    allowed = [
        "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS",
        "protected_surfaces_unchanged",
        "protected_surface_drift_classified",
        "custom_writes_owned_and_cleanable",
        "user_data_dir_respected_if_packet_proves_owned_writes",
        "keychain_behavior_observed",
        "current_codex_state_preserved_or_drift_classified",
        "blocked_by_host_environment_if_packeted",
    ]
    forbidden = [
        "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_PROVEN",
        "native_route_proven",
        "owner_ux_proven",
        "direct_egress_absent",
        "Original_Codex_via_WBP_proven",
        "all_models_work",
        "GPT-5.5_native_works",
        "Keychain_Cancel_equals_auth_success",
        "process_started_equals_usable_app",
        "--user-data-dir_present_equals_respected",
        "read_only_snapshot_equals_auth_independence",
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_safety_allowed_claims_matrix",
        "status": "ok",
        "final_status": final_status,
        "allowed_claims": allowed,
        "forbidden_claims": forbidden,
        "route_claim_allowed": False,
        "ux_claim_allowed": False,
        "egress_claim_allowed": False,
        "model_availability_claim_allowed": False,
        "auth_strategy_reproof_allowed": False,
    }


def build_native_safety_false_green_audit(
    *,
    probe_packet: dict[str, Any],
    allowed_claims_matrix: dict[str, Any],
) -> dict[str, Any]:
    protected_diff = probe_packet.get("protected_surface_recursive_diff", {})
    user_data = probe_packet.get("user_data_dir_respected_packet", {})
    cleanup = probe_packet.get("cleanup_reversibility_packet", {})
    current_delta = probe_packet.get("current_codex_delta", {})
    keychain = probe_packet.get("keychain_observation_packet", {})
    checks = [
        {
            "name": "no_route_claim",
            "passed": not allowed_claims_matrix.get("route_claim_allowed", True),
            "evidence": "allowed_claims_matrix.route_claim_allowed",
        },
        {
            "name": "no_ux_claim",
            "passed": not allowed_claims_matrix.get("ux_claim_allowed", True),
            "evidence": "allowed_claims_matrix.ux_claim_allowed",
        },
        {
            "name": "no_egress_claim",
            "passed": not allowed_claims_matrix.get("egress_claim_allowed", True),
            "evidence": "allowed_claims_matrix.egress_claim_allowed",
        },
        {
            "name": "protected_surfaces_recursive_diff_classified",
            "passed": "all_protected_surfaces_unchanged" in protected_diff,
            "evidence": "protected_surface_recursive_diff",
        },
        {
            "name": "user_data_dir_respected_requires_owned_writes",
            "passed": user_data.get("user_data_dir_respected") is True,
            "evidence": "user_data_dir_respected_packet",
        },
        {
            "name": "cleanup_removed_tmp_root",
            "passed": cleanup.get("tmp_root_removed") is True,
            "evidence": "cleanup_reversibility_packet",
        },
        {
            "name": "current_codex_not_touched",
            "passed": current_delta.get("current_codex_touched") is False,
            "evidence": "current_codex_delta",
        },
        {
            "name": "keychain_cancel_not_auth_success",
            "passed": keychain.get("keychain_cancel_equals_auth_success") is False,
            "evidence": "keychain_observation_packet",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_safety_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "forbidden_claims_present": False,
        "allowed_final_status": "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS",
    }


def build_native_safety_refresh_false_green_audit(
    *,
    layer_boundary_packet: dict[str, Any],
    owner_action_boundary_packet: dict[str, Any],
    protected_surface_read_packet: dict[str, Any],
    profile_ownership_packet: dict[str, Any],
    user_data_ownership_packet: dict[str, Any],
    write_inventory_packet: dict[str, Any],
    cleanup_reversibility_packet: dict[str, Any],
    keychain_observation_packet: dict[str, Any],
    auth_strategy_reference_packet: dict[str, Any],
    model_availability_reference_packet: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        {
            "name": "layer_boundary_forbids_ux_egress_original_final_claims",
            "passed": layer_boundary_packet.get("native_ux_acceptance_proven") is False
            and layer_boundary_packet.get("direct_egress_absence_proven") is False
            and layer_boundary_packet.get("original_codex_reversibility_proven") is False
            and layer_boundary_packet.get("final_e2e_proven") is False,
            "evidence": "native_safety_layer_boundary_packet",
        },
        {
            "name": "no_owner_ui_action",
            "passed": owner_action_boundary_packet.get("status") == "ok"
            and owner_action_boundary_packet.get("prompt_submitted") is False,
            "evidence": "owner_action_boundary_packet",
        },
        {
            "name": "protected_reads_are_inspection_only",
            "passed": protected_surface_read_packet.get("inspection_only") is True
            and protected_surface_read_packet.get("runtime_auth_input_used") is False,
            "evidence": "protected_surface_read_classification_packet",
        },
        {
            "name": "custom_profile_owned",
            "passed": profile_ownership_packet.get("status") == "ok",
            "evidence": "custom_profile_ownership_packet",
        },
        {
            "name": "custom_user_data_dir_owned",
            "passed": user_data_ownership_packet.get("status") == "ok",
            "evidence": "custom_user_data_dir_ownership_packet",
        },
        {
            "name": "write_inventory_custom_owned_only",
            "passed": write_inventory_packet.get("status") == "ok",
            "evidence": "custom_profile_write_inventory_packet",
        },
        {
            "name": "cleanup_custom_owned_only",
            "passed": cleanup_reversibility_packet.get("status") == "ok"
            and cleanup_reversibility_packet.get("original_codex_reversibility_claimed")
            is False,
            "evidence": "cleanup_reversibility_packet",
        },
        {
            "name": "keychain_not_auth_proof",
            "passed": keychain_observation_packet.get("status") == "ok"
            and keychain_observation_packet.get("auth_success_claimed") is False,
            "evidence": "keychain_observation_packet",
        },
        {
            "name": "auth_strategy_reference_only",
            "passed": auth_strategy_reference_packet.get("auth_strategy_reproved_in_this_contour")
            is False,
            "evidence": "auth_strategy_reference_packet",
        },
        {
            "name": "model_availability_reference_only",
            "passed": model_availability_reference_packet.get(
                "model_availability_reproved_in_this_contour"
            )
            is False,
            "evidence": "model_availability_reference_packet",
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_safety_refresh_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "forbidden_claims_present": not all(check["passed"] for check in checks),
        "native_launch_claimed": False,
        "ux_claimed": False,
        "egress_claimed": False,
        "original_reversibility_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
        "route_account_model_provider_mutated": False,
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
    protected_read_packet = build_protected_surface_read_classification_packet()
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
    keychain_packet = classify_keychain_observation(machine_prompt_observed=False)
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
        "native_custom_safety_launch_packet": launch_result,
        "launch_result": launch_result,
        "protected_surface_read_classification_packet": protected_read_packet,
        "keychain_observation_packet": keychain_packet,
        "user_data_dir_respected_packet": user_data_dir_result,
        "cleanup_reversibility_packet": cleanup_packet,
        "secret_value_recorded": False,
    }
    allowed_claims_matrix = build_allowed_claims_matrix(
        final_status=(
            "NATIVE_CUSTOM_APP_SAFE_TO_CONTINUE_WITH_LIMITS"
            if packet["status"] == "ok"
            else "NATIVE_CUSTOM_APP_SAFETY_BLOCKED_OR_UNPROVEN"
        )
    )
    false_green_audit = build_native_safety_false_green_audit(
        probe_packet=packet,
        allowed_claims_matrix=allowed_claims_matrix,
    )
    packet["allowed_claims_matrix"] = allowed_claims_matrix
    packet["native_safety_false_green_audit"] = false_green_audit

    split_packets = {
        "protected_surface_read_classification_packet.json": protected_read_packet,
        "protected_surface_recursive_before.json": before_surfaces,
        "current_codex_running_state_before.json": before_process,
        "native_custom_safety_launch_packet.json": launch_result,
        "keychain_observation_packet.json": keychain_packet,
        "user_data_dir_respected_packet.json": user_data_dir_result,
        "custom_profile_write_inventory.json": owned_scan,
        "protected_surface_recursive_after.json": after_surfaces,
        "protected_surface_recursive_diff.json": protected_diff,
        "current_codex_running_state_after.json": after_process,
        "current_codex_delta_packet.json": current_delta,
        "cleanup_reversibility_packet.json": cleanup_packet,
        "allowed_claims_matrix.json": allowed_claims_matrix,
        "native_safety_false_green_audit.json": false_green_audit,
    }
    for file_name, payload in split_packets.items():
        json_write(evidence_dir / file_name, payload)
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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_machine_ui_waiver_packet(*, owner_waives_machine_ui: bool) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "machine_ui_waiver",
        "status": "ok" if owner_waives_machine_ui else "blocked",
        "owner_waives_machine_ui": owner_waives_machine_ui,
        "machine_ui_input_field_proven": False,
        "machine_observed_response_text_proven": False,
        "manual_ui_confirmation_allowed": owner_waives_machine_ui,
        "manual_ui_confirmation_replaces_route_trace": False,
        "route_trace_replaces_owner_ux_confirmation": False,
    }


def build_owner_nonce_prompt_packet(*, nonce: str, prompt_template: str | None = None) -> dict[str, Any]:
    prompt = prompt_template or f"WBP owner UX route check {nonce}. Reply with OK and the nonce only."
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_nonce_prompt",
        "status": "ok" if nonce else "blocked",
        "nonce": nonce,
        "nonce_recorded": bool(nonce),
        "prompt_sha256": _sha256_text(prompt) if prompt else "",
        "prompt_hash_recorded": bool(prompt),
        "raw_prompt_recorded": False,
        "prompt_template_shape": "WBP owner UX route check <nonce>. Reply with OK and the nonce only.",
    }


def build_owner_manual_ux_check_packet(
    *,
    owner_saw_window: bool,
    owner_typed_prompt: bool,
    owner_saw_response: bool,
    machine_ui_waiver_packet: dict[str, Any],
) -> dict[str, Any]:
    if owner_saw_window and owner_typed_prompt and owner_saw_response:
        ux_status = "confirmed"
        status = "ok"
    elif not owner_saw_window:
        ux_status = "blocked_no_window"
        status = "blocked"
    elif not owner_typed_prompt:
        ux_status = "blocked_no_prompt_entry"
        status = "blocked"
    else:
        ux_status = "blocked_no_visible_response"
        status = "blocked"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_manual_ux_check",
        "status": status,
        "ux_status": ux_status,
        "owner_saw_window": owner_saw_window,
        "owner_typed_prompt": owner_typed_prompt,
        "owner_saw_response": owner_saw_response,
        "machine_ui_waived": machine_ui_waiver_packet.get("owner_waives_machine_ui") is True,
        "machine_ui_input_field_proven": False,
        "machine_observed_response_text_proven": False,
        "route_claimed": False,
    }


def build_wbp_trace_observation_packet(*, trace_packet: dict[str, Any] | None) -> dict[str, Any]:
    trace = trace_packet or {}
    request_observed = trace.get("request_observed") is True
    response_observed = trace.get("response_observed") is True
    forwarded_to_wbp = trace.get("forwarded_to_wbp") is True
    path_ok = trace.get("path") == "/v1/responses"
    upstream_status = trace.get("upstream_status")
    try:
        upstream_status_code = int(upstream_status)
    except (TypeError, ValueError):
        upstream_status_code = None
    upstream_status_ok = (
        upstream_status_code is not None and 200 <= upstream_status_code < 300
    )
    response_body_sha256 = str(trace.get("response_body_sha256", ""))
    response_hash_recorded = bool(response_body_sha256)
    raw_secret_or_prompt = (
        trace.get("secret_value_recorded") is True
        or trace.get("auth_header_recorded") is True
        or trace.get("prompt_body_recorded") is True
    )
    transport_observed = request_observed and response_observed and forwarded_to_wbp and path_ok
    if raw_secret_or_prompt:
        route_status = "blocked_secret_risk"
        status = "blocked"
    elif transport_observed and upstream_status_code is not None and not upstream_status_ok:
        route_status = "blocked_model_failure"
        status = "blocked"
    elif transport_observed and upstream_status_ok and response_hash_recorded:
        route_status = "confirmed"
        status = "ok"
    elif request_observed or response_observed:
        route_status = "blocked_trace_mismatch"
        status = "blocked"
    else:
        route_status = "missing"
        status = "blocked"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "wbp_trace_observation",
        "status": status,
        "route_status": route_status,
        "request_observed": request_observed,
        "response_observed": response_observed,
        "forwarded_to_wbp": forwarded_to_wbp,
        "trace_path": trace.get("path", ""),
        "upstream_status": upstream_status,
        "upstream_status_ok": upstream_status_ok,
        "request_body_sha256": trace.get("request_body_sha256", ""),
        "response_body_sha256": response_body_sha256,
        "response_hash_recorded": response_hash_recorded,
        "model_id": trace.get("model_id", ""),
        "raw_prompt_recorded": trace.get("prompt_body_recorded") is True,
        "auth_header_recorded": trace.get("auth_header_recorded") is True,
        "raw_auth_recorded": trace.get("secret_value_recorded") is True,
    }


def build_native_route_trace_binding_packet(
    *,
    owner_nonce_prompt_packet: dict[str, Any],
    wbp_trace_observation_packet: dict[str, Any],
) -> dict[str, Any]:
    route_confirmed = wbp_trace_observation_packet.get("route_status") == "confirmed"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_route_trace_binding",
        "status": "ok" if route_confirmed else "blocked",
        "route_status": wbp_trace_observation_packet.get("route_status", "missing"),
        "route_trace_bound": route_confirmed,
        "nonce_recorded": owner_nonce_prompt_packet.get("nonce_recorded") is True,
        "prompt_hash_recorded": owner_nonce_prompt_packet.get("prompt_hash_recorded") is True,
        "raw_prompt_recorded": False,
        "trace_request_body_sha256": wbp_trace_observation_packet.get("request_body_sha256", ""),
        "trace_response_body_sha256": wbp_trace_observation_packet.get("response_body_sha256", ""),
        "trace_path": wbp_trace_observation_packet.get("trace_path", ""),
        "owner_ux_claimed": False,
    }


def build_two_lane_result_matrix(
    *,
    owner_manual_ux_check_packet: dict[str, Any],
    route_trace_binding_packet: dict[str, Any],
    wbp_trace_observation_packet: dict[str, Any],
) -> dict[str, Any]:
    ux_status = str(owner_manual_ux_check_packet.get("ux_status") or "blocked_no_visible_response")
    route_status = str(wbp_trace_observation_packet.get("route_status") or "missing")
    route_trace_bound = route_trace_binding_packet.get("route_trace_bound") is True
    if route_status == "blocked_secret_risk":
        final_status = "OWNER_UX_ROUTE_BLOCKED_SECRET_RISK"
        status = "blocked"
    elif route_status == "blocked_model_failure":
        final_status = "OWNER_UX_ROUTE_BLOCKED_MODEL_FAILURE"
        status = "blocked"
    elif ux_status == "confirmed" and route_status == "confirmed" and route_trace_bound:
        final_status = "CODEX_CUSTOM_NATIVE_APP_VIA_WBP_USABLE_WITH_OWNER_CONFIRMATION"
        status = "ok"
    elif ux_status == "confirmed":
        final_status = "OWNER_UX_CONFIRMED_ROUTE_UNPROVEN"
        status = "blocked"
    elif route_status == "confirmed" and route_trace_bound:
        final_status = "ROUTE_CONFIRMED_OWNER_UX_UNCONFIRMED"
        status = "blocked"
    else:
        final_status = "OWNER_UX_AND_ROUTE_BLOCKED"
        status = "blocked"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "two_lane_result_matrix",
        "status": status,
        "ux_status": ux_status,
        "route_status": route_status,
        "final_status": final_status,
        "owner_ux_confirmed": ux_status == "confirmed",
        "route_trace_bound": route_trace_bound,
        "route_trace_confirmed": route_status == "confirmed" and route_trace_bound,
        "machine_ui_proof_claimed": False,
        "filesystem_safety_claimed": False,
        "direct_egress_claimed": False,
        "final_e2e_claimed": False,
    }


def build_native_owner_ux_false_green_audit(
    *,
    machine_ui_waiver_packet: dict[str, Any],
    owner_manual_ux_check_packet: dict[str, Any],
    wbp_trace_observation_packet: dict[str, Any],
    two_lane_result_matrix: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = (
        two_lane_result_matrix.get("machine_ui_proof_claimed") is True
        or two_lane_result_matrix.get("filesystem_safety_claimed") is True
        or two_lane_result_matrix.get("direct_egress_claimed") is True
        or two_lane_result_matrix.get("final_e2e_claimed") is True
        or owner_manual_ux_check_packet.get("route_claimed") is True
        or wbp_trace_observation_packet.get("raw_prompt_recorded") is True
        or wbp_trace_observation_packet.get("auth_header_recorded") is True
        or wbp_trace_observation_packet.get("raw_auth_recorded") is True
    )
    checks = [
        {
            "name": "manual_ui_waiver_does_not_replace_route_trace",
            "passed": machine_ui_waiver_packet.get("manual_ui_confirmation_replaces_route_trace") is False,
        },
        {
            "name": "route_trace_does_not_replace_owner_ux",
            "passed": machine_ui_waiver_packet.get("route_trace_replaces_owner_ux_confirmation") is False,
        },
        {
            "name": "two_lane_matrix_present",
            "passed": two_lane_result_matrix.get("packet_kind") == "two_lane_result_matrix",
        },
        {
            "name": "no_raw_prompt_or_auth",
            "passed": not (
                wbp_trace_observation_packet.get("raw_prompt_recorded")
                or wbp_trace_observation_packet.get("auth_header_recorded")
                or wbp_trace_observation_packet.get("raw_auth_recorded")
            ),
        },
        {
            "name": "no_filesystem_or_egress_or_final_claim",
            "passed": not (
                two_lane_result_matrix.get("filesystem_safety_claimed")
                or two_lane_result_matrix.get("direct_egress_claimed")
                or two_lane_result_matrix.get("final_e2e_claimed")
            ),
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_owner_ux_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) and not forbidden_claims_present else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
    }


def build_owner_historical_observation_import_packet(
    *,
    owner_confirmation_text: str,
    owner_reported_agent_answered: bool,
    owner_reported_config_model_route_untouched: bool,
    owner_reported_hidden_cleanup_not_performed: bool,
    owner_reported_first_custom_answered: bool = False,
) -> dict[str, Any]:
    status_ok = (
        bool(owner_confirmation_text)
        and owner_reported_agent_answered
        and owner_reported_config_model_route_untouched
        and owner_reported_hidden_cleanup_not_performed
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_historical_observation_import",
        "status": "ok" if status_ok else "blocked",
        "reason_class": "" if status_ok else "OWNER_HISTORICAL_OBSERVATION_INCOMPLETE",
        "source_class": "thread_owner_statement",
        "historical_only": True,
        "fresh_live_native_launch_performed": False,
        "fresh_live_native_launch_claimed": False,
        "owner_confirmation_text_sha256": _sha256_text(owner_confirmation_text),
        "owner_confirmation_text_recorded": True,
        "owner_reported_agent_answered": owner_reported_agent_answered,
        "owner_reported_first_custom_answered": owner_reported_first_custom_answered,
        "owner_reported_config_model_route_untouched": (
            owner_reported_config_model_route_untouched
        ),
        "owner_reported_hidden_cleanup_not_performed": (
            owner_reported_hidden_cleanup_not_performed
        ),
        "owner_observation_replaces_route_trace": False,
        "owner_observation_replaces_machine_ui_proof": False,
    }


def build_owner_visible_response_observation_packet(
    *,
    historical_observation_import_packet: dict[str, Any],
    screenshot_limit_packet: dict[str, Any],
) -> dict[str, Any]:
    owner_saw_response = (
        historical_observation_import_packet.get("owner_reported_agent_answered") is True
    )
    screenshot_support_ok = screenshot_limit_packet.get("status") == "ok"
    status_ok = (
        historical_observation_import_packet.get("status") == "ok"
        and owner_saw_response
        and screenshot_support_ok
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_visible_response_observation",
        "status": "ok" if status_ok else "blocked",
        "reason_class": "" if status_ok else "OWNER_VISIBLE_RESPONSE_UNPROVEN",
        "historical_only": True,
        "owner_saw_response": owner_saw_response,
        "owner_reported_first_custom_answered": (
            historical_observation_import_packet.get("owner_reported_first_custom_answered")
            is True
        ),
        "screenshots_used_as_narrative_support": (
            screenshot_limit_packet.get("screenshots_used_as_narrative_support") is True
        ),
        "screenshot_counts_as_packet_truth": False,
        "machine_ui_input_field_proven": False,
        "machine_observed_response_text_proven": False,
        "route_claimed": False,
    }


def build_owner_cleanup_perception_packet(
    *,
    owner_reported_hidden_cleanup_not_performed: bool,
    owner_confirmed_cleanup_result: bool = False,
) -> dict[str, Any]:
    status_ok = owner_reported_hidden_cleanup_not_performed
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_cleanup_perception",
        "status": "ok" if status_ok else "blocked",
        "reason_class": "" if status_ok else "OWNER_HIDDEN_CLEANUP_REPORTED",
        "historical_only": True,
        "owner_confirmed_cleanup_result": owner_confirmed_cleanup_result,
        "owner_reported_hidden_cleanup_not_performed": (
            owner_reported_hidden_cleanup_not_performed
        ),
        "cleanup_perception_recorded": True,
        "cleanup_perception_counts_as_filesystem_proof": False,
        "filesystem_cleanup_proven": False,
        "protected_surface_diff_proven": False,
        "tmp_root_removed_proven": False,
    }


def build_screenshot_limit_packet(
    *,
    screenshot_count: int,
    screenshots_used_as_narrative_support: bool,
    screenshot_claims_packet_truth: bool = False,
    max_narrative_screenshots: int = 3,
) -> dict[str, Any]:
    count = max(0, int(screenshot_count))
    cap_ok = count <= max_narrative_screenshots
    status_ok = cap_ok and not screenshot_claims_packet_truth
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "screenshot_limit",
        "status": "ok" if status_ok else "blocked",
        "reason_class": (
            ""
            if status_ok
            else (
                "SCREENSHOT_PROMOTED_TO_PACKET_TRUTH"
                if screenshot_claims_packet_truth
                else "SCREENSHOT_NARRATIVE_CAP_EXCEEDED"
            )
        ),
        "screenshot_count": count,
        "max_narrative_screenshots": max_narrative_screenshots,
        "screenshots_used_as_narrative_support": screenshots_used_as_narrative_support,
        "screenshot_claims_packet_truth": screenshot_claims_packet_truth,
        "screenshot_counts_as_packet_truth": False,
        "screenshot_counts_as_route_proof": False,
        "screenshot_counts_as_machine_ui_proof": False,
        "screenshot_counts_as_filesystem_proof": False,
    }


def build_historical_routing_trace_reference_packet(
    *,
    wbp_trace_observation_packet: dict[str, Any],
    source_trace_path: str,
    source_closeout_path: str = "",
) -> dict[str, Any]:
    trace_confirmed = wbp_trace_observation_packet.get("route_status") == "confirmed"
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "historical_routing_trace_reference",
        "status": "ok" if trace_confirmed else "blocked",
        "reason_class": "" if trace_confirmed else "HISTORICAL_ROUTE_TRACE_UNCONFIRMED",
        "historical_only": True,
        "source_trace_path": source_trace_path,
        "source_closeout_path": source_closeout_path,
        "historical_route_trace_referenced": trace_confirmed,
        "historical_trace_path": wbp_trace_observation_packet.get("trace_path", ""),
        "historical_forwarded_to_wbp": (
            wbp_trace_observation_packet.get("forwarded_to_wbp") is True
        ),
        "historical_upstream_status": wbp_trace_observation_packet.get("upstream_status"),
        "historical_response_hash_recorded": (
            wbp_trace_observation_packet.get("response_hash_recorded") is True
        ),
        "routing_reproved_in_this_contour": False,
        "fresh_trace_claimed": False,
        "owner_observation_replaces_trace": False,
    }


def build_owner_ux_layer_boundary_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_ux_layer_boundary",
        "status": "ok",
        "this_contour_proves": [
            "historical owner-visible Custom native response observation",
            "owner action boundary stayed within allowed manual actions",
            "screenshots remain narrative support only",
        ],
        "this_contour_does_not_prove": [
            "fresh native launch",
            "fresh WBP routing",
            "machine UI input field proof",
            "machine-observed UI response text",
            "protected filesystem safety",
            "direct egress absence",
            "auth strategy",
            "model availability",
            "Original Codex via WBP",
            "final E2E",
        ],
        "fresh_live_native_launch_claimed": False,
        "fresh_route_claimed": False,
        "machine_ui_proof_claimed": False,
        "filesystem_safety_claimed": False,
        "direct_egress_claimed": False,
        "auth_strategy_reproved": False,
        "model_availability_reproved": False,
        "original_codex_via_wbp_claimed": False,
        "final_e2e_claimed": False,
    }


def build_owner_ux_historical_false_green_audit(
    *,
    historical_observation_import_packet: dict[str, Any],
    visible_response_observation_packet: dict[str, Any],
    cleanup_perception_packet: dict[str, Any],
    screenshot_limit_packet: dict[str, Any],
    historical_routing_trace_reference_packet: dict[str, Any],
    layer_boundary_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = any(
        layer_boundary_packet.get(key) is True
        for key in (
            "fresh_live_native_launch_claimed",
            "fresh_route_claimed",
            "machine_ui_proof_claimed",
            "filesystem_safety_claimed",
            "direct_egress_claimed",
            "auth_strategy_reproved",
            "model_availability_reproved",
            "original_codex_via_wbp_claimed",
            "final_e2e_claimed",
        )
    ) or any(
        packet.get(key) is True
        for packet in (
            historical_observation_import_packet,
            visible_response_observation_packet,
            cleanup_perception_packet,
            screenshot_limit_packet,
            historical_routing_trace_reference_packet,
        )
        for key in (
            "fresh_live_native_launch_claimed",
            "fresh_trace_claimed",
            "route_claimed",
            "screenshot_claims_packet_truth",
            "cleanup_perception_counts_as_filesystem_proof",
            "owner_observation_replaces_route_trace",
            "owner_observation_replaces_trace",
            "machine_ui_input_field_proven",
            "machine_observed_response_text_proven",
            "filesystem_cleanup_proven",
            "protected_surface_diff_proven",
        )
    )
    checks = [
        {
            "name": "historical_import_not_fresh_native_launch",
            "passed": (
                historical_observation_import_packet.get("historical_only") is True
                and historical_observation_import_packet.get(
                    "fresh_live_native_launch_claimed"
                )
                is False
            ),
        },
        {
            "name": "visible_response_not_machine_ui_proof",
            "passed": not (
                visible_response_observation_packet.get("machine_ui_input_field_proven")
                or visible_response_observation_packet.get(
                    "machine_observed_response_text_proven"
                )
            ),
        },
        {
            "name": "cleanup_perception_not_filesystem_proof",
            "passed": cleanup_perception_packet.get(
                "cleanup_perception_counts_as_filesystem_proof"
            )
            is False,
        },
        {
            "name": "screenshot_not_packet_truth",
            "passed": screenshot_limit_packet.get("screenshot_counts_as_packet_truth")
            is False
            and screenshot_limit_packet.get("screenshot_claims_packet_truth") is False,
        },
        {
            "name": "historical_route_reference_not_fresh_route_reproof",
            "passed": historical_routing_trace_reference_packet.get(
                "routing_reproved_in_this_contour"
            )
            is False
            and historical_routing_trace_reference_packet.get("fresh_trace_claimed")
            is False,
        },
        {
            "name": "no_adjacent_layer_claims",
            "passed": not any(
                layer_boundary_packet.get(key) is True
                for key in (
                    "filesystem_safety_claimed",
                    "direct_egress_claimed",
                    "auth_strategy_reproved",
                    "model_availability_reproved",
                    "original_codex_via_wbp_claimed",
                    "final_e2e_claimed",
                )
            ),
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_ux_historical_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) and not forbidden_claims_present else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
    }


def build_native_direct_egress_capability_packet(
    *,
    lsof_path: str,
    tcpdump_path: str = "",
    nettop_path: str = "",
    process_tree_observer_available: bool = True,
) -> dict[str, Any]:
    """Classify local observer availability without implying a live egress result."""

    lsof_available = bool(lsof_path)
    unsafe_packet_capture_tools_present = bool(tcpdump_path or nettop_path)
    observer_usable = lsof_available and process_tree_observer_available
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_direct_egress_observer_capability",
        "status": "ok" if observer_usable else "blocked",
        "observer_strategy": "lsof_process_tree_sampling",
        "lsof_path": lsof_path,
        "lsof_available": lsof_available,
        "process_tree_observer_available": process_tree_observer_available,
        "tcpdump_path": tcpdump_path,
        "nettop_path": nettop_path,
        "packet_capture_used": False,
        "unsafe_packet_capture_tools_present": unsafe_packet_capture_tools_present,
        "observer_usable_for_bounded_native_classification": observer_usable,
        "full_network_absence_proven": False,
    }


def build_native_direct_egress_claim_packet(
    *,
    process_network_observation_packet: dict[str, Any],
    wbp_trace_observation_packet: dict[str, Any],
    custom_process_bound: bool,
    background_codex_noise_detected: bool = False,
) -> dict[str, Any]:
    classification = str(
        process_network_observation_packet.get("classification")
        or "insufficient_observation"
    )
    route_confirmed = wbp_trace_observation_packet.get("route_status") == "confirmed"
    observer_absent = (
        process_network_observation_packet.get("direct_non_wbp_model_egress_absent_proven")
        is True
    )
    allowed_local_endpoint_observed = (
        process_network_observation_packet.get("allowed_local_endpoint_observed") is True
    )
    direct_model_egress_observed = classification == "direct_model_egress_observed"
    if background_codex_noise_detected:
        status = "blocked"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE"
        reason_class = "BACKGROUND_CODEX_NOISE"
        bounded_absent = False
    elif direct_model_egress_observed:
        status = "blocked"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_DIRECT_EGRESS_OBSERVED"
        reason_class = "DIRECT_NON_WBP_MODEL_EGRESS_OBSERVED"
        bounded_absent = False
    elif not custom_process_bound:
        status = "blocked"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_OBSERVER_INSUFFICIENT"
        reason_class = "CUSTOM_PROCESS_BINDING_MISSING"
        bounded_absent = False
    elif classification == "insufficient_observation":
        status = "blocked"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_OBSERVER_INSUFFICIENT"
        reason_class = "INSUFFICIENT_NETWORK_OBSERVATION"
        bounded_absent = False
    elif observer_absent and route_confirmed and allowed_local_endpoint_observed:
        status = "ok"
        final_status = (
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_ABSENT_WITH_LIMITS"
        )
        reason_class = ""
        bounded_absent = True
    else:
        status = "blocked"
        final_status = (
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_CLASSIFIED_DIRECT_EGRESS_UNPROVEN_WITH_OBSERVER_LIMITS"
        )
        reason_class = "ROUTE_OR_LOCAL_ENDPOINT_BINDING_UNPROVEN"
        bounded_absent = False
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_direct_egress_claim",
        "status": status,
        "final_status": final_status,
        "reason_class": reason_class,
        "observer_classification": classification,
        "custom_process_bound": custom_process_bound,
        "route_trace_confirmed": route_confirmed,
        "allowed_local_endpoint_observed": allowed_local_endpoint_observed,
        "direct_model_egress_observed": direct_model_egress_observed,
        "direct_non_wbp_model_egress_absent_proven": bounded_absent,
        "bounded_observation_absence_proven": bounded_absent,
        "full_network_absence_proven": False,
        "native_ux_claimed": False,
        "machine_ui_proof_claimed": False,
        "filesystem_safety_claimed": False,
        "provider_compatibility_claimed": False,
        "original_codex_via_wbp_claimed": False,
        "final_e2e_claimed": False,
    }


def build_native_direct_egress_false_green_audit(
    *,
    native_direct_egress_claim_packet: dict[str, Any],
    process_network_observation_packet: dict[str, Any],
    wbp_trace_observation_packet: dict[str, Any],
) -> dict[str, Any]:
    direct_absent = (
        native_direct_egress_claim_packet.get("direct_non_wbp_model_egress_absent_proven")
        is True
    )
    observer_absent = (
        process_network_observation_packet.get("direct_non_wbp_model_egress_absent_proven")
        is True
    )
    forbidden_claims_present = any(
        native_direct_egress_claim_packet.get(key) is True
        for key in (
            "native_ux_claimed",
            "machine_ui_proof_claimed",
            "filesystem_safety_claimed",
            "provider_compatibility_claimed",
            "original_codex_via_wbp_claimed",
            "final_e2e_claimed",
            "full_network_absence_proven",
        )
    )
    checks = [
        {
            "name": "route_trace_alone_not_counted_as_egress_absence",
            "passed": not (
                direct_absent
                and not observer_absent
                and wbp_trace_observation_packet.get("route_status") == "confirmed"
            ),
        },
        {
            "name": "observer_insufficient_not_counted_as_pass",
            "passed": not (
                direct_absent
                and process_network_observation_packet.get("classification")
                == "insufficient_observation"
            ),
        },
        {
            "name": "direct_model_egress_blocks",
            "passed": not (
                direct_absent
                and process_network_observation_packet.get("classification")
                == "direct_model_egress_observed"
            ),
        },
        {
            "name": "bounded_absence_not_global_absence",
            "passed": native_direct_egress_claim_packet.get("full_network_absence_proven")
            is False,
        },
        {
            "name": "no_cross_layer_claims",
            "passed": not forbidden_claims_present,
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_direct_egress_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
        "route_trace_counted_as_egress_absence": direct_absent and not observer_absent,
    }


def build_egress_prior_blocker_replay_packet(
    *,
    prior_claim_packet: dict[str, Any],
    prior_process_network_observation_packet: dict[str, Any],
    prior_background_noise_packet: dict[str, Any],
    prior_wbp_trace_observation_packet: dict[str, Any],
) -> dict[str, Any]:
    final_status = str(prior_claim_packet.get("final_status") or "")
    reason_class = str(prior_claim_packet.get("reason_class") or "")
    background_noise = (
        prior_background_noise_packet.get("background_codex_noise_detected") is True
    )
    route_context_confirmed = (
        prior_wbp_trace_observation_packet.get("route_status") == "confirmed"
        or prior_wbp_trace_observation_packet.get("forwarded_to_wbp") is True
    )
    direct_absence_proven = (
        prior_claim_packet.get("direct_non_wbp_model_egress_absent_proven") is True
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "egress_prior_blocker_replay",
        "status": "ok" if background_noise and not direct_absence_proven else "blocked",
        "reason_class": (
            ""
            if background_noise and not direct_absence_proven
            else "PRIOR_EGRESS_BLOCKER_REPLAY_MISMATCH"
        ),
        "prior_final_status": final_status,
        "prior_reason_class": reason_class,
        "prior_observer_classification": prior_claim_packet.get(
            "observer_classification", ""
        ),
        "prior_process_observation_classification": (
            prior_process_network_observation_packet.get("classification", "")
        ),
        "prior_background_codex_noise_detected": background_noise,
        "prior_route_context_confirmed": route_context_confirmed,
        "prior_direct_model_egress_observed": (
            prior_claim_packet.get("direct_model_egress_observed") is True
        ),
        "prior_direct_egress_absence_proven": direct_absence_proven,
        "prior_full_network_absence_proven": (
            prior_claim_packet.get("full_network_absence_proven") is True
        ),
        "current_egress_absence_claimed": False,
        "historical_route_trace_counted_as_current_egress_proof": False,
    }


def build_historical_route_context_packet(
    *,
    wbp_trace_observation_packet: dict[str, Any],
    source_trace_path: str,
) -> dict[str, Any]:
    route_confirmed = (
        wbp_trace_observation_packet.get("route_status") == "confirmed"
        or wbp_trace_observation_packet.get("forwarded_to_wbp") is True
    )
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "historical_route_context",
        "status": "ok" if route_confirmed else "blocked",
        "reason_class": "" if route_confirmed else "HISTORICAL_ROUTE_CONTEXT_UNCONFIRMED",
        "source_trace_path": source_trace_path,
        "historical_only": True,
        "historical_route_context_confirmed": route_confirmed,
        "historical_trace_path": wbp_trace_observation_packet.get("trace_path")
        or wbp_trace_observation_packet.get("path", ""),
        "historical_forwarded_to_wbp": (
            wbp_trace_observation_packet.get("forwarded_to_wbp") is True
        ),
        "historical_upstream_status": wbp_trace_observation_packet.get("upstream_status"),
        "fresh_route_reproved_in_this_contour": False,
        "historical_route_counted_as_egress_absence": False,
        "direct_egress_absence_claimed": False,
    }


def build_current_background_codex_noise_packet(
    *,
    current_process_inventory_packet: dict[str, Any],
    hosted_by_codex_context: bool = True,
) -> dict[str, Any]:
    root_count = len(current_process_inventory_packet.get("root_app_pids", []) or [])
    line_count = int(current_process_inventory_packet.get("line_count") or 0)
    default_count = int(current_process_inventory_packet.get("default_process_count") or 0)
    custom_count = int(current_process_inventory_packet.get("custom_process_count") or 0)
    noise_detected = hosted_by_codex_context or root_count > 0 or default_count > 0
    clean_attribution_feasible = not noise_detected and custom_count == 0
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "current_background_codex_noise",
        "status": "ok" if not noise_detected else "blocked",
        "reason_class": "" if not noise_detected else "BACKGROUND_CODEX_NOISE_PRESENT",
        "hosted_by_codex_context": hosted_by_codex_context,
        "current_codex_root_process_count": root_count,
        "current_codex_default_process_count": default_count,
        "current_codex_process_line_count": line_count,
        "current_custom_process_count": custom_count,
        "background_codex_noise_detected": noise_detected,
        "clean_process_attribution_currently_feasible": clean_attribution_feasible,
        "current_codex_process_mutated": False,
        "fresh_native_launch_attempted": False,
    }


def build_quiescent_network_precondition_packet(
    *,
    observer_capability_packet: dict[str, Any],
    current_background_codex_noise_packet: dict[str, Any],
) -> dict[str, Any]:
    observer_available = (
        observer_capability_packet.get("observer_usable_for_bounded_native_classification")
        is True
    )
    background_noise = (
        current_background_codex_noise_packet.get("background_codex_noise_detected")
        is True
    )
    quiescent_ready = observer_available and not background_noise
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "quiescent_network_precondition",
        "status": "ok" if quiescent_ready else "blocked",
        "reason_class": (
            ""
            if quiescent_ready
            else (
                "BACKGROUND_CODEX_NOISE_PRESENT"
                if background_noise
                else "OBSERVER_CAPABILITY_UNAVAILABLE"
            )
        ),
        "observer_available": observer_available,
        "background_codex_noise_detected": background_noise,
        "owner_assisted_quiescent_window_required": background_noise,
        "fresh_native_launch_admissible_in_this_contour": False,
        "process_peer_attribution_currently_clean": quiescent_ready,
        "direct_egress_absence_claimed": False,
    }


def build_network_observer_feasibility_decision_packet(
    *,
    prior_blocker_replay_packet: dict[str, Any],
    observer_capability_packet: dict[str, Any],
    quiescent_network_precondition_packet: dict[str, Any],
) -> dict[str, Any]:
    prior_ok = prior_blocker_replay_packet.get("status") == "ok"
    observer_ok = observer_capability_packet.get("status") == "ok"
    quiescent_ok = quiescent_network_precondition_packet.get("status") == "ok"
    if not prior_ok:
        status = "blocked"
        final_status = (
            "NATIVE_WBP_ROUTE_NETWORK_OBSERVER_FEASIBILITY_BLOCKED_PRIOR_REPLAY"
        )
        reason_class = "PRIOR_BLOCKER_REPLAY_FAILED"
        separate_live_admissible = False
    elif not observer_ok:
        status = "blocked"
        final_status = (
            "NATIVE_WBP_ROUTE_NETWORK_OBSERVER_FEASIBILITY_BLOCKED_OBSERVER_UNAVAILABLE"
        )
        reason_class = "OBSERVER_CAPABILITY_UNAVAILABLE"
        separate_live_admissible = False
    elif not quiescent_ok:
        status = "blocked"
        final_status = (
            "NATIVE_WBP_ROUTE_NETWORK_OBSERVER_FEASIBILITY_BLOCKED_CURRENT_NOISE"
        )
        reason_class = quiescent_network_precondition_packet.get(
            "reason_class", "QUIESCENT_PRECONDITION_FAILED"
        )
        separate_live_admissible = False
    else:
        status = "ok"
        final_status = "NATIVE_WBP_ROUTE_NETWORK_OBSERVER_FEASIBILITY_CLASSIFIED"
        reason_class = ""
        separate_live_admissible = True
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "network_observer_feasibility_decision",
        "status": status,
        "final_status": final_status,
        "reason_class": reason_class,
        "prior_blocker_replay_ok": prior_ok,
        "observer_capability_ok": observer_ok,
        "quiescent_network_precondition_ok": quiescent_ok,
        "separate_live_bounded_egress_contour_admissible": separate_live_admissible,
        "fresh_native_launch_attempted": False,
        "fresh_native_launch_claimed": False,
        "direct_egress_absence_proven": False,
        "api_openai_com_absence_proven": False,
        "full_network_absence_proven": False,
        "final_e2e_claimed": False,
    }


def build_network_claim_limits_packet() -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "network_claim_limits",
        "status": "ok",
        "allowed_claims": [
            "prior native egress blocker replayed",
            "observer capability classified",
            "current quiescence feasibility classified",
            "separate live bounded egress contour admissibility classified",
        ],
        "forbidden_claims": [
            "direct egress absence proven",
            "api.openai.com absence proven",
            "full network absence proven",
            "fresh native launch performed",
            "native UX proven",
            "filesystem safety proven",
            "model availability proven",
            "auth strategy proven",
            "Original Codex via WBP proven",
            "final E2E proven",
        ],
        "historical_route_trace_may_support": "historical_route_context_only",
        "historical_route_trace_may_not_support": "current_egress_absence",
        "owner_ux_may_support": "non_network_context_only",
        "owner_ux_may_not_support": "network_proof",
        "screenshot_may_support": "narrative_only",
        "screenshot_may_not_support": "packet_truth_or_network_proof",
        "bounded_process_peer_absence_claimed": False,
        "direct_egress_absence_claimed": False,
        "api_openai_com_absence_claimed": False,
    }


def build_native_egress_observer_false_green_audit(
    *,
    historical_route_context_packet: dict[str, Any],
    network_observer_feasibility_decision_packet: dict[str, Any],
    network_claim_limits_packet: dict[str, Any],
    owner_ux_used_as_network_proof: bool = False,
    screenshot_used_as_network_proof: bool = False,
) -> dict[str, Any]:
    forbidden_claims_present = (
        network_observer_feasibility_decision_packet.get("direct_egress_absence_proven")
        is True
        or network_observer_feasibility_decision_packet.get("api_openai_com_absence_proven")
        is True
        or network_observer_feasibility_decision_packet.get("full_network_absence_proven")
        is True
        or network_observer_feasibility_decision_packet.get("fresh_native_launch_claimed")
        is True
        or network_observer_feasibility_decision_packet.get("final_e2e_claimed")
        is True
        or network_claim_limits_packet.get("direct_egress_absence_claimed") is True
        or network_claim_limits_packet.get("api_openai_com_absence_claimed") is True
        or owner_ux_used_as_network_proof
        or screenshot_used_as_network_proof
    )
    checks = [
        {
            "name": "historical_route_trace_not_current_egress_proof",
            "passed": historical_route_context_packet.get(
                "historical_route_counted_as_egress_absence"
            )
            is False,
        },
        {
            "name": "owner_ux_not_network_proof",
            "passed": owner_ux_used_as_network_proof is False,
        },
        {
            "name": "screenshot_not_network_proof",
            "passed": screenshot_used_as_network_proof is False,
        },
        {
            "name": "observer_feasibility_not_absence_claim",
            "passed": network_observer_feasibility_decision_packet.get(
                "direct_egress_absence_proven"
            )
            is False,
        },
        {
            "name": "no_api_or_full_network_absence_claim",
            "passed": not (
                network_observer_feasibility_decision_packet.get(
                    "api_openai_com_absence_proven"
                )
                or network_observer_feasibility_decision_packet.get(
                    "full_network_absence_proven"
                )
            ),
        },
        {
            "name": "no_live_native_launch_claim",
            "passed": network_observer_feasibility_decision_packet.get(
                "fresh_native_launch_attempted"
            )
            is False,
        },
    ]
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": "native_egress_observer_false_green_audit",
        "status": "ok" if all(check["passed"] for check in checks) and not forbidden_claims_present else "blocked",
        "checks": checks,
        "forbidden_claims_present": forbidden_claims_present,
        "blocked_observer_counted_as_pass": False,
    }
