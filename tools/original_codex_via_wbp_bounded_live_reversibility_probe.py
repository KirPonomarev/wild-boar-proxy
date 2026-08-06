#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Owner-gated Original Codex via WBP bounded live contour probe.

This tool intentionally stops before any Original profile write unless the
exact owner authorization surface is present. The no-authorization path is a
valid blocked packet, not a partial green.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    build_original_auth_boundary_packet,
    build_original_live_false_green_audit,
    build_original_live_last_chance_dry_run_packet,
    build_original_live_owner_authorization_packet,
    build_original_live_rollback_point_packet,
    build_original_live_restore_failure_lockdown_packet,
    build_original_live_summary_packet,
    build_original_live_temporary_config_candidate_packet,
    build_original_live_temporary_route_apply_admission_packet,
    build_original_live_trace_timeout_policy_packet,
    build_original_process_window_state_packet,
    build_original_profile_inventory_packet,
    build_original_readiness_reference_packet,
    build_provider_auth_strategy_reference_packet,
    build_selected_model_trace_claim_packet,
    build_wbp_trace_observation_packet,
    collect_codex_process_inventory,
    json_write,
)
from wild_boar_proxy.operator_surface import WbpTraceObserver


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"access_token[\"']?\s*[:=]\s*[\"'][^\"']{8,}", re.IGNORECASE),
)
READINESS_SUMMARY = (
    "audit_results/original_codex_via_wbp_reversibility_readiness_2026-05-26/"
    "original_readiness_summary_packet.json"
)
AUTH_STRATEGY_PACKET = (
    "audit_results/wbp_provider_auth_strategy_contract_refresh_2026-05-26/"
    "provider_auth_strategy_packet.json"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    try:
        process = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"state": "absent", "path": str(path)}
    data = path.read_bytes()
    return {
        "state": "present",
        "path": str(path),
        "sha256": _sha256_bytes(data),
        "byte_length": len(data),
        "mode_octal": oct(path.stat().st_mode & 0o777),
    }


def _toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _strip_sections(config_text: str, section_names: set[str]) -> str:
    output: list[str] = []
    skipping = False
    section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$")
    for line in config_text.splitlines():
        match = section_pattern.match(line)
        if match:
            skipping = match.group(1).strip() in section_names
            if skipping:
                continue
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + "\n"


def _set_top_level_key(config_text: str, key: str, value: str) -> str:
    lines = config_text.splitlines()
    output: list[str] = []
    replaced = False
    inserted = False
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for line in lines:
        in_section = line.lstrip().startswith("[")
        if in_section and not inserted and not replaced:
            output.append(f"{key} = {_toml_quote(value)}")
            inserted = True
        if not in_section and pattern.match(line):
            if not replaced:
                output.append(f"{key} = {_toml_quote(value)}")
                replaced = True
                inserted = True
            continue
        output.append(line)
    if not inserted and not replaced:
        output.insert(0, f"{key} = {_toml_quote(value)}")
    return "\n".join(output).rstrip() + "\n"


def _build_preserving_wbp_config(
    *,
    existing_text: str,
    endpoint: str,
    model: str,
    auth_command_path: str,
) -> str:
    text = _strip_sections(
        existing_text,
        {"model_providers.wbp", "model_providers.wbp.auth"},
    )
    text = _set_top_level_key(text, "model", model)
    text = _set_top_level_key(text, "model_provider", "wbp")
    text = text.rstrip() + "\n\n"
    text += (
        "[model_providers.wbp]\n"
        'name = "Wild Boar Proxy"\n'
        f"base_url = {_toml_quote(endpoint)}\n"
        'wire_api = "responses"\n'
        "requires_openai_auth = false\n\n"
        "[model_providers.wbp.auth]\n"
        f"command = {_toml_quote(auth_command_path)}\n"
    )
    return text


def _atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    tmp = path.with_name(f".{path.name}.wbp-tmp")
    tmp.write_bytes(data)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = (
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/original_codex_via_wbp_bounded_live_reversibility_probe.py",
    )
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _base_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": _run(repo_root, ["git", "status", "--short"]).splitlines(),
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "master_plan_written_to_repo": False,
        },
        "historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "quarantine_classification": "out_of_scope_historical_residue",
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "codex_cli_version": _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version_optional_not_blocking": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "original_bounded_live_schema_version": 1,
        },
    }


def _declared_write_surfaces_packet(owner_auth: dict[str, Any]) -> dict[str, Any]:
    write_allowed = owner_auth.get("status") == "ok"
    declared = ["fresh evidence directory only"]
    if write_allowed:
        declared.append(str(owner_auth.get("exact_target_path", "")))
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "declared_write_surfaces",
        "status": "ok",
        "declared_write_surfaces": declared,
        "owner_authorization_required": True,
        "owner_authorization_status": owner_auth.get("status"),
        "original_codex_profile_write_allowed": write_allowed,
        "original_codex_profile_write_performed": False,
        "native_original_launch_allowed": write_allowed,
        "native_original_launch_attempted": False,
        "auth_json_mutation_allowed": False,
        "auth_json_runtime_dependency_allowed": False,
        "hidden_cleanup_allowed": False,
    }


def _secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    raw_secret_found = any(pattern.search(serialized) for pattern in SECRET_PATTERNS)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_live_secret_redaction_audit",
        "status": "blocked" if raw_secret_found else "ok",
        "raw_secret_found": raw_secret_found,
        "auth_json_token_value_recorded": False,
        "auth_header_recorded": False,
        "upstream_secret_recorded": False,
        "checked_packet_count": len(packets),
    }


def _temporary_route_apply_execution_packet(
    *,
    target_path: Path,
    candidate_sha256: str,
    apply_attempted: bool,
    apply_succeeded: bool,
) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_live_temporary_route_apply_execution",
        "status": "ok" if apply_succeeded else "blocked",
        "reason_class": "" if apply_succeeded else "TEMPORARY_ROUTE_APPLY_FAILED",
        "exact_target_path": str(target_path),
        "candidate_sha256": candidate_sha256,
        "apply_attempted": apply_attempted,
        "apply_succeeded": apply_succeeded,
        "original_profile_write_performed": apply_succeeded,
        "written_surface_count": 1 if apply_succeeded else 0,
        "written_surfaces": [str(target_path)] if apply_succeeded else [],
    }


def _native_original_launch_execution_packet(
    *,
    launch_attempted: bool,
    launch_returncode: int | None,
    launch_command: list[str],
    launch_pid: int | None = None,
    proxy_env_sanitized: bool = False,
) -> dict[str, Any]:
    ok = launch_attempted and (launch_returncode == 0 or launch_pid is not None)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_live_native_launch_execution",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "NATIVE_ORIGINAL_LAUNCH_FAILED",
        "native_original_launch_attempted": launch_attempted,
        "launch_command": launch_command,
        "launch_returncode": launch_returncode,
        "launch_pid": launch_pid,
        "proxy_env_sanitized": proxy_env_sanitized,
    }


def _owner_prompt_instruction_packet(*, nonce_prompt: str, timeout_seconds: int) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_live_owner_prompt_instruction",
        "status": "ok",
        "owner_action_required": True,
        "owner_may_type_prompt": True,
        "owner_must_not_change_config_model_route_or_account": True,
        "nonce_prompt": nonce_prompt,
        "timeout_seconds": timeout_seconds,
    }


def _independent_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "sync_gate_packet.json",
        "historical_dirt_quarantine_packet.json",
        "version_pinning_packet.json",
        "declared_write_surfaces_packet.json",
        "original_readiness_reference_packet.json",
        "owner_authorization_packet.json",
        "original_profile_before_packet.json",
        "original_auth_boundary_packet.json",
        "original_process_window_before_packet.json",
        "provider_auth_strategy_reference_packet.json",
        "rollback_point_packet.json",
        "temporary_config_candidate_packet.json",
        "last_chance_dry_run_packet.json",
        "temporary_route_apply_admission_packet.json",
        "trace_timeout_policy_packet.json",
        "restore_failure_lockdown_packet.json",
        "selected_model_trace_claim_packet.json",
        "original_via_wbp_summary_packet.json",
        "original_via_wbp_false_green_audit.json",
        "original_live_secret_redaction_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = [
        name for name, packet in packets.items() if packet.get("status") == "blocked"
    ]
    summary = packets.get("original_via_wbp_summary_packet.json", {})
    owner_auth = packets.get("owner_authorization_packet.json", {})
    false_green = packets.get("original_via_wbp_false_green_audit.json", {})
    dry_run = packets.get("last_chance_dry_run_packet.json", {})
    timeout_policy = packets.get("trace_timeout_policy_packet.json", {})
    lockdown = packets.get("restore_failure_lockdown_packet.json", {})
    auth_reference = packets.get("provider_auth_strategy_reference_packet.json", {})
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_original_via_wbp_audit",
        "status": "ok" if not missing and false_green.get("status") == "ok" else "blocked",
        "referenced_packets": sorted(required),
        "missing_required_packets": missing,
        "blocked_packets": sorted(blocked),
        "owner_authorization_status": owner_auth.get("status"),
        "blocked_closeout_is_honest": summary.get("status") == "blocked",
        "no_original_profile_write_without_authorization": (
            owner_auth.get("status") != "ok"
            and summary.get("original_profile_write_performed") is False
        ),
        "no_native_original_launch_without_authorization": (
            owner_auth.get("status") != "ok"
            and summary.get("native_original_launch_attempted") is False
        ),
        "last_chance_dry_run_present": bool(dry_run),
        "dry_run_did_not_write": dry_run.get("temporary_route_apply_performed") is False,
        "auth_strategy_reference_only": auth_reference.get("auth_strategy_reproved") is False,
        "trace_timeout_policy_restores_first": (
            timeout_policy.get("restore_first_after_timeout") is True
            and timeout_policy.get("retry_mutation_allowed") is False
        ),
        "restore_failure_lockdown_present": bool(lockdown),
        "restore_failure_does_not_allow_second_launch": lockdown.get(
            "second_launch_allowed"
        )
        is False,
        "false_green_audit_ok": false_green.get("status") == "ok",
        "direct_egress_absence_claimed": summary.get("direct_egress_absence_proven") is True,
        "model_availability_claimed": summary.get("model_availability_proven") is True,
        "wire_compatibility_claimed": summary.get("wire_compatibility_proven") is True,
        "final_e2e_claimed": summary.get("final_e2e_proven") is True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="original-codex-via-wbp-bounded-live-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--exact-target-path", default=str(Path.home() / ".codex" / "config.toml"))
    parser.add_argument("--allowed-write-operation", default="")
    parser.add_argument("--rollback-mode", default="")
    parser.add_argument("--launch-permission", action="store_true")
    parser.add_argument("--owner-prompt-permission", action="store_true")
    parser.add_argument("--restore-permission", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--trace-timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--owner-nonce-prompt",
        default="WBP_ORIGINAL_ROUTE_NONCE_2026_05_26: ответь одной строкой WBP_OK",
    )
    parser.add_argument("--model", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)

    readiness_path = repo_root / READINESS_SUMMARY
    readiness_summary = _read_json(readiness_path) if readiness_path.exists() else {}
    auth_strategy_path = repo_root / AUTH_STRATEGY_PACKET
    auth_strategy_packet = (
        _read_json(auth_strategy_path) if auth_strategy_path.exists() else {}
    )
    owner_auth = build_original_live_owner_authorization_packet(
        owner_authorized=args.owner_authorized,
        exact_target_path=args.exact_target_path,
        allowed_write_operation=args.allowed_write_operation,
        rollback_mode=args.rollback_mode,
        launch_permission=args.launch_permission,
        owner_prompt_permission=args.owner_prompt_permission,
        restore_permission=args.restore_permission,
    )
    packets: dict[str, dict[str, Any]] = _base_packets(repo_root, evidence_dir)
    packets["owner_authorization_packet.json"] = owner_auth
    packets["declared_write_surfaces_packet.json"] = _declared_write_surfaces_packet(
        owner_auth
    )
    packets["original_readiness_reference_packet.json"] = (
        build_original_readiness_reference_packet(
            readiness_summary_packet=readiness_summary,
            source_path=str(readiness_path),
        )
    )
    process_inventory = collect_codex_process_inventory(
        custom_user_data_dir="__original_bounded_live_no_custom_launch__"
    )
    profile_before = build_original_profile_inventory_packet()
    auth_boundary = build_original_auth_boundary_packet(
        profile_inventory_packet=profile_before
    )
    process_window = build_original_process_window_state_packet(
        process_inventory_packet=process_inventory
    )
    auth_strategy_reference = build_provider_auth_strategy_reference_packet(
        provider_auth_strategy_packet=auth_strategy_packet,
        source_path=str(auth_strategy_path),
    )
    target_path = Path(args.exact_target_path).expanduser()
    rollback_artifact_path = ""
    rollback_artifact_sha256 = ""
    rollback_point_created = False
    rollback_point_verified = False
    before_bytes: bytes | None = None
    before_state = _file_state(target_path)
    before_exists = before_state.get("state") == "present"
    if before_exists:
        before_bytes = target_path.read_bytes()
    live_write_performed = False
    launch_packet = _native_original_launch_execution_packet(
        launch_attempted=False,
        launch_returncode=None,
        launch_command=[],
    )
    apply_execution_packet = _temporary_route_apply_execution_packet(
        target_path=target_path,
        candidate_sha256="",
        apply_attempted=False,
        apply_succeeded=False,
    )
    trace_packet: dict[str, Any] = {}
    wbp_trace = build_wbp_trace_observation_packet(trace_packet=None)
    route_trace_packet = {
        "route_trace_confirmed": False,
        "native_original_launch_attempted": False,
        "original_profile_write_performed": False,
    }
    restore_verification = {}
    rollback_execution_attempted = False
    restore_verified = False
    trace_timeout_policy = build_original_live_trace_timeout_policy_packet(
        trace_observed=False,
        restore_attempted_after_timeout=False,
        restore_verified_after_timeout=False,
        timeout_seconds=args.trace_timeout_seconds,
    )
    restore_failure_lockdown = build_original_live_restore_failure_lockdown_packet(
        restore_verified=False,
    )
    observer_endpoint = "http://127.0.0.1:8318/v1"
    selected_model_id = args.model or str(profile_before.get("config_toml", {}).get("model") or "")
    if not selected_model_id:
        selected_model_id = "gpt-5.4"

    if args.execute_live and owner_auth.get("status") == "ok":
        rollback_root = Path.home() / ".codex" / ".tmp" / "wbp-original-live-rollback"
        rollback_root.mkdir(parents=True, exist_ok=True)
        if before_exists and before_bytes is not None:
            rollback_artifact = rollback_root / f"config-{int(time.time())}.toml"
            rollback_artifact.write_bytes(before_bytes)
            os.chmod(rollback_artifact, 0o600)
            rollback_artifact_path = str(rollback_artifact)
            rollback_artifact_sha256 = _sha256_bytes(before_bytes)
            rollback_point_created = rollback_artifact.exists()
            rollback_point_verified = (
                rollback_artifact.read_bytes() == before_bytes
                and rollback_artifact_sha256 == before_state.get("sha256")
            )
        else:
            rollback_point_created = True
            rollback_point_verified = True
    rollback_point = build_original_live_rollback_point_packet(
        profile_before_packet=profile_before,
        owner_authorization_packet=owner_auth,
        rollback_artifact_path=rollback_artifact_path,
        rollback_artifact_sha256=rollback_artifact_sha256,
        rollback_point_created=rollback_point_created,
        rollback_point_verified=rollback_point_verified,
    )
    temporary_candidate = build_original_live_temporary_config_candidate_packet(
        owner_authorization_packet=owner_auth,
        provider_auth_strategy_reference_packet=auth_strategy_reference,
    )
    last_chance_dry_run = build_original_live_last_chance_dry_run_packet(
        owner_authorization_packet=owner_auth,
        rollback_point_packet=rollback_point,
        temporary_config_candidate_packet=temporary_candidate,
        provider_auth_strategy_reference_packet=auth_strategy_reference,
    )
    apply_admission = build_original_live_temporary_route_apply_admission_packet(
        owner_authorization_packet=owner_auth,
        rollback_point_packet=rollback_point,
        readiness_reference_packet=packets["original_readiness_reference_packet.json"],
        last_chance_dry_run_packet=last_chance_dry_run,
    )
    if args.execute_live and apply_admission.get("status") == "ok":
        try:
            with WbpTraceObserver(downstream_endpoint="http://127.0.0.1:8318/v1") as trace:
                observer_endpoint = trace.listen_endpoint
                existing_text = target_path.read_text(encoding="utf-8") if before_exists else ""
                candidate_text = _build_preserving_wbp_config(
                    existing_text=existing_text,
                    endpoint=observer_endpoint,
                    model=selected_model_id,
                    auth_command_path=str(auth_strategy_reference.get("auth_command_path") or ""),
                )
                temporary_candidate = build_original_live_temporary_config_candidate_packet(
                    owner_authorization_packet=owner_auth,
                    provider_auth_strategy_reference_packet=auth_strategy_reference,
                    endpoint=observer_endpoint,
                    model=selected_model_id,
                    candidate_text=candidate_text,
                )
                last_chance_dry_run = build_original_live_last_chance_dry_run_packet(
                    owner_authorization_packet=owner_auth,
                    rollback_point_packet=rollback_point,
                    temporary_config_candidate_packet=temporary_candidate,
                    provider_auth_strategy_reference_packet=auth_strategy_reference,
                )
                apply_admission = build_original_live_temporary_route_apply_admission_packet(
                    owner_authorization_packet=owner_auth,
                    rollback_point_packet=rollback_point,
                    readiness_reference_packet=packets["original_readiness_reference_packet.json"],
                    last_chance_dry_run_packet=last_chance_dry_run,
                )
                if apply_admission.get("status") != "ok":
                    raise RuntimeError("apply admission failed after live trace endpoint candidate")
                _atomic_write_bytes(target_path, candidate_text.encode("utf-8"))
                live_write_performed = True
                apply_execution_packet = _temporary_route_apply_execution_packet(
                    target_path=target_path,
                    candidate_sha256=temporary_candidate.get("candidate_sha256", ""),
                    apply_attempted=True,
                    apply_succeeded=True,
                )
                launch_command = ["/Applications/Codex.app/Contents/MacOS/Codex"]
                launch_env = {
                    key: value
                    for key, value in os.environ.items()
                    if key.upper() not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
                }
                launch_env["NO_PROXY"] = "127.0.0.1,localhost,::1"
                launch_env["no_proxy"] = "127.0.0.1,localhost,::1"
                launch_process = subprocess.Popen(
                    launch_command,
                    cwd=repo_root,
                    env=launch_env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                time.sleep(3.0)
                launch_packet = _native_original_launch_execution_packet(
                    launch_attempted=True,
                    launch_returncode=launch_process.poll(),
                    launch_command=launch_command,
                    launch_pid=launch_process.pid,
                    proxy_env_sanitized=True,
                )
                json_write(
                    evidence_dir / "owner_prompt_instruction_packet.json",
                    _owner_prompt_instruction_packet(
                        nonce_prompt=args.owner_nonce_prompt,
                        timeout_seconds=args.trace_timeout_seconds,
                    ),
                )
                print("OWNER_PROMPT_READY", flush=True)
                print(args.owner_nonce_prompt, flush=True)
                deadline = time.monotonic() + max(args.trace_timeout_seconds, 1)
                while time.monotonic() < deadline:
                    trace_packet = trace.packet()
                    if (
                        trace_packet.get("request_observed") is True
                        and trace_packet.get("path") == "/v1/responses"
                        and trace_packet.get("response_observed") is True
                    ):
                        break
                    time.sleep(1.0)
                trace_packet = trace.packet()
        finally:
            if live_write_performed:
                rollback_execution_attempted = True
                if before_exists and before_bytes is not None:
                    _atomic_write_bytes(target_path, before_bytes)
                else:
                    try:
                        target_path.unlink()
                    except FileNotFoundError:
                        pass
                after_state = _file_state(target_path)
                restore_verified = after_state == before_state
                restore_verification = {
                    "before_state": before_state,
                    "after_state": after_state,
                    "rollback_execution_attempted": rollback_execution_attempted,
                    "restore_verified": restore_verified,
                }
    wbp_trace = build_wbp_trace_observation_packet(trace_packet=trace_packet)
    route_confirmed = wbp_trace.get("route_status") == "confirmed"
    route_trace_packet = {
        "route_trace_confirmed": route_confirmed,
        "native_original_launch_attempted": launch_packet.get(
            "native_original_launch_attempted", False
        ),
        "original_profile_write_performed": apply_execution_packet.get(
            "original_profile_write_performed", False
        ),
    }
    if not restore_verification:
        restore_verification = {
            "before_state": before_state,
            "after_state": _file_state(target_path),
            "rollback_execution_attempted": rollback_execution_attempted,
            "restore_verified": restore_verified,
        }
    restore_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_live_restore_verification",
        "status": "ok" if restore_verified and restore_verification["after_state"] == before_state else "blocked",
        "reason_class": "" if restore_verified and restore_verification["after_state"] == before_state else "RESTORE_NOT_VERIFIED",
        "rollback_execution_attempted": rollback_execution_attempted,
        "restore_verified": restore_verified and restore_verification["after_state"] == before_state,
        "restore_matches_before": restore_verification["after_state"] == before_state,
        "before_state": before_state,
        "after_state": restore_verification["after_state"],
        "second_launch_allowed": restore_verified and restore_verification["after_state"] == before_state,
        "second_launch_attempted_after_failed_restore": False,
        "normal_original_sanity_allowed": restore_verified and restore_verification["after_state"] == before_state,
    }
    trace_timeout_policy = build_original_live_trace_timeout_policy_packet(
        trace_observed=route_confirmed,
        restore_attempted_after_timeout=rollback_execution_attempted,
        restore_verified_after_timeout=restore_packet.get("status") == "ok",
        timeout_seconds=args.trace_timeout_seconds,
    )
    restore_failure_lockdown = build_original_live_restore_failure_lockdown_packet(
        restore_verified=restore_packet.get("status") == "ok",
    )
    selected_model = build_selected_model_trace_claim_packet(
        selected_model=selected_model_id if route_confirmed else "",
        route_trace_confirmed=route_confirmed,
    )
    summary = build_original_live_summary_packet(
        owner_authorization_packet=owner_auth,
        apply_admission_packet=apply_admission,
        route_trace_packet=route_trace_packet,
        restore_verification_packet=restore_packet,
    )
    false_green = build_original_live_false_green_audit(
        summary_packet=summary,
        selected_model_trace_claim_packet=selected_model,
    )
    packets.update(
        {
            "original_profile_before_packet.json": profile_before,
            "original_auth_boundary_packet.json": auth_boundary,
            "original_process_window_before_packet.json": process_window,
            "rollback_point_packet.json": rollback_point,
            "provider_auth_strategy_reference_packet.json": auth_strategy_reference,
            "temporary_config_candidate_packet.json": temporary_candidate,
            "last_chance_dry_run_packet.json": last_chance_dry_run,
            "temporary_route_apply_admission_packet.json": apply_admission,
            "temporary_route_apply_execution_packet.json": apply_execution_packet,
            "native_original_launch_execution_packet.json": launch_packet,
            "source_wbp_trace_packet.json": trace_packet,
            "wbp_trace_observation_packet.json": wbp_trace,
            "trace_timeout_policy_packet.json": trace_timeout_policy,
            "restore_failure_lockdown_packet.json": restore_failure_lockdown,
            "restore_verification_packet.json": restore_packet,
            "selected_model_trace_claim_packet.json": selected_model,
            "original_via_wbp_summary_packet.json": summary,
            "original_via_wbp_false_green_audit.json": false_green,
        }
    )
    packets["original_live_secret_redaction_audit.json"] = _secret_redaction_audit(packets)
    packets["independent_original_via_wbp_audit.json"] = _independent_audit(packets)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
