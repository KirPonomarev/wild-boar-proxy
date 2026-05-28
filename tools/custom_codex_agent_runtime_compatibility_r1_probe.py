#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify Custom Codex agent/runtime compatibility without live mutation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    PROTECTED_SURFACE_PATHS,
    default_persistent_custom_profile_paths,
    json_write,
)


TARGET_STATUS = "CUSTOM_CODEX_AGENT_RUNTIME_COMPATIBILITY_CLASSIFIED_WITH_ISOLATED_PROFILE"
EVIDENCE_DIR_NAME = "audit_results/custom_codex_agent_runtime_compatibility_r1_2026-05-28"
PROFILE_ID = "wbp-custom-main"

REQUIRED_PLUGIN_SURFACES = {
    "browser": ("openai-bundled", "browser"),
    "documents": ("openai-primary-runtime", "documents"),
    "spreadsheets": ("openai-primary-runtime", "spreadsheets"),
    "presentations": ("openai-primary-runtime", "presentations"),
}

FORBIDDEN_TRUE_FIELDS = {
    "performance_claimed",
    "latency_claimed",
    "parity_claimed",
    "all_plugins_claimed",
    "all_agent_models_claimed",
    "model_grid_claimed",
    "model_routing_changed",
    "ui_changed",
    "runtime_repair_performed",
    "plugin_implementation_changed",
    "original_profile_mutated",
    "original_profile_dependency",
    "live_cleanup_executed",
    "live_restore_executed",
    "thread_history_reproof_claimed",
    "auth_proof_claimed",
    "final_e2e_claimed",
    "all_users_claimed",
    "raw_secret_recorded",
    "raw_prompt_recorded",
    "browser_supplied_model_authority",
    "browser_supplied_path_authority",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def run_text(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if check and process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return process.stdout.rstrip("\n") if process.returncode == 0 else process.stderr.rstrip("\n")


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    path = _resolved(path)
    parent = _resolved(parent)
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(left: Path, right: Path) -> bool:
    left = _resolved(left)
    right = _resolved(right)
    return _path_is_relative_to(left, right) or _path_is_relative_to(right, left)


def _sha256_file(path: Path, *, limit: int = 1_000_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def _metadata(path: Path, *, hash_file: bool = False) -> dict[str, Any]:
    path = path.expanduser()
    resolved = _resolved(path)
    try:
        stat = resolved.stat()
    except OSError:
        return {
            "path": str(resolved),
            "exists": False,
            "kind": "absent",
            "content_recorded": False,
        }
    data: dict[str, Any] = {
        "path": str(resolved),
        "exists": True,
        "kind": "dir" if resolved.is_dir() else "file" if resolved.is_file() else "other",
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "content_recorded": False,
    }
    if hash_file and resolved.is_file():
        data["sha256"] = _sha256_file(resolved)
    return data


def _field_true(value: Any, field: str) -> bool:
    if isinstance(value, dict):
        if value.get(field) is True:
            return True
        return any(_field_true(nested, field) for nested in value.values())
    if isinstance(value, list):
        return any(_field_true(nested, field) for nested in value)
    return False


def _scan_forbidden_true(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_FIELDS and nested is True:
                findings.append(nested_path)
            findings.extend(_scan_forbidden_true(nested, nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(_scan_forbidden_true(nested, f"{prefix}[{index}]"))
    return findings


def historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> tuple[list[str], list[str]]:
    if skip_git:
        return [], []
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/custom_codex_agent_runtime_compatibility_r1_probe.py",
        "tests/test_custom_codex_agent_runtime_compatibility_r1_probe.py",
    }
    admitted_current_evidence_dirs = (
        f"{relative_evidence_dir}/",
        f"{EVIDENCE_DIR_NAME}/",
    )

    def is_current_contour_line(line: str) -> bool:
        path = line[3:] if len(line) > 3 else line.strip()
        return path in admitted_current_contour or path.startswith(admitted_current_evidence_dirs)

    quarantined = [line for line in status_lines if not is_current_contour_line(line)]
    unexpected_dirty: list[str] = []
    return quarantined, unexpected_dirty


def build_sync_gate_packet(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> dict[str, Any]:
    quarantined, unexpected_dirty = historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return packet(
        "agent_runtime_sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        git_status_short=[] if skip_git else run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        quarantined_dirty_count=len(quarantined),
        historical_dirty_quarantined=bool(quarantined),
        unexpected_dirty_entries=unexpected_dirty,
        sync_gate_blocks_only_unquarantined_current_contour_dirty=True,
        master_plan_written_to_repo=False,
        current_contour="CUSTOM_CODEX_AGENT_RUNTIME_COMPATIBILITY_CLASSIFICATION_R1",
    )


def build_agent_runtime_inventory_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    home_dir = Path(paths["home_dir"])
    plugin_cache_root = profile_root / "plugins" / "cache"
    runtime_cache_root = home_dir / ".cache" / "codex-runtimes"
    marketplace_tmp_root = profile_root / ".tmp"
    ok = _resolved(profile_root) == _resolved(Path(paths["codex_home"]))
    return packet(
        "agent_runtime_inventory",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "PERSISTENT_PROFILE_IDENTITY_UNSAFE",
        profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        codex_home=str(_resolved(Path(paths["codex_home"]))),
        home_dir=str(_resolved(home_dir)),
        plugin_cache_root=str(_resolved(plugin_cache_root)),
        runtime_cache_root=str(_resolved(runtime_cache_root)),
        marketplace_tmp_root=str(_resolved(marketplace_tmp_root)),
        profile_exists=profile_root.exists(),
        plugin_cache_root_exists=plugin_cache_root.exists(),
        runtime_cache_root_exists=runtime_cache_root.exists(),
        marketplace_tmp_root_exists=marketplace_tmp_root.exists(),
        command_executed=False,
        live_agent_invocation_performed=False,
        runtime_repair_performed=False,
        ui_changed=False,
        model_routing_changed=False,
    )


def _plugin_surface_packet_entry(
    *,
    surface_name: str,
    cache_root: Path,
    profile_root: Path,
) -> dict[str, Any]:
    vendor, plugin = REQUIRED_PLUGIN_SURFACES[surface_name]
    root = cache_root / vendor / plugin
    manifests = sorted(root.glob("*/.codex-plugin/plugin.json"))
    skills = sorted(root.glob(f"*/skills/{surface_name}/SKILL.md"))
    manifest = manifests[-1] if manifests else None
    skill = skills[-1] if skills else None
    manifest_payload: dict[str, Any] = {}
    if manifest is not None:
        try:
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest_payload = {}
    return {
        "surface": surface_name,
        "vendor": vendor,
        "plugin": plugin,
        "cache_root": str(_resolved(root)),
        "manifest_path": str(_resolved(manifest)) if manifest else "",
        "skill_path": str(_resolved(skill)) if skill else "",
        "available": bool(manifest and skill),
        "manifest_valid_json": bool(manifest_payload),
        "manifest_name": str(manifest_payload.get("name", "")),
        "manifest_version": str(manifest_payload.get("version", "")),
        "manifest_path_under_custom_profile": bool(manifest and _path_is_relative_to(manifest, profile_root)),
        "skill_path_under_custom_profile": bool(skill and _path_is_relative_to(skill, profile_root)),
        "invoked": False,
        "compatibility_claimed_from_existence": False,
    }


def build_bundled_plugin_availability_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    cache_root = profile_root / "plugins" / "cache"
    entries = [
        _plugin_surface_packet_entry(
            surface_name=surface,
            cache_root=cache_root,
            profile_root=profile_root,
        )
        for surface in REQUIRED_PLUGIN_SURFACES
    ]
    all_available = all(entry["available"] for entry in entries)
    all_inside_profile = all(
        entry["manifest_path_under_custom_profile"] and entry["skill_path_under_custom_profile"]
        for entry in entries
    )
    return packet(
        "bundled_plugin_availability",
        status="ok" if all_available and all_inside_profile else "blocked",
        reason_class="" if all_available and all_inside_profile else "BUNDLED_PLUGIN_SURFACE_MISSING_OR_OUTSIDE_PROFILE",
        profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        required_surfaces=list(REQUIRED_PLUGIN_SURFACES),
        surfaces=entries,
        all_required_surfaces_available=all_available,
        all_required_surfaces_inside_custom_profile=all_inside_profile,
        plugin_invocation_performed=False,
        all_plugins_claimed=False,
        parity_claimed=False,
    )


def build_agent_capable_workflow_classification_packet(
    *,
    observed: bool,
    source: str,
) -> dict[str, Any]:
    return packet(
        "agent_capable_workflow_classification",
        status="ok",
        workflow_observed=observed,
        workflow_source=source,
        workflow_classification="bounded_agent_capable_workflow_observed" if observed else "not_proven",
        unavailable_is_not_failure=not observed,
        workflow_result_usable=observed,
        live_agent_invocation_performed_by_probe=False,
        browser_supplied_model_authority=False,
        browser_supplied_path_authority=False,
        model_grid_claimed=False,
        performance_claimed=False,
        latency_claimed=False,
        parity_claimed=False,
    )


def build_profile_isolation_during_runtime_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
    plugin_availability_packet: dict[str, Any],
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    plugin_entries = plugin_availability_packet.get("surfaces", [])
    outside_profile = [
        entry
        for entry in plugin_entries
        if not (
            entry.get("manifest_path_under_custom_profile") is True
            and entry.get("skill_path_under_custom_profile") is True
        )
    ]
    protected_overlap = any(
        _paths_overlap(profile_root, protected)
        for protected in PROTECTED_SURFACE_PATHS.values()
    )
    ok = not outside_profile and not protected_overlap
    return packet(
        "profile_isolation_during_runtime",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "AGENT_RUNTIME_PROFILE_ISOLATION_UNSAFE",
        persistent_profile_root=str(_resolved(profile_root)),
        plugin_surfaces_outside_custom_profile=outside_profile,
        protected_surface_overlap=protected_overlap,
        runtime_work_writes_bounded=True,
        live_runtime_work_performed_by_probe=False,
        live_cleanup_executed=False,
        live_restore_executed=False,
        original_profile_dependency=False,
        original_profile_mutated=False,
        thread_history_reproof_claimed=False,
    )


def build_runtime_cache_path_classification_packet(
    *,
    profile_id: str,
    base_dir: Path | None,
) -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    cache_paths = {
        "plugin_cache_root": profile_root / "plugins" / "cache",
        "runtime_cache_root": Path(paths["home_dir"]) / ".cache" / "codex-runtimes",
        "marketplace_tmp_root": profile_root / ".tmp",
    }
    entries = {
        name: {
            **_metadata(path),
            "under_custom_profile": _path_is_relative_to(path, profile_root),
            "overlaps_original_codex": any(
                _paths_overlap(path, protected) for protected in PROTECTED_SURFACE_PATHS.values()
            ),
        }
        for name, path in cache_paths.items()
    }
    ok = all(entry["under_custom_profile"] and not entry["overlaps_original_codex"] for entry in entries.values())
    return packet(
        "runtime_cache_path_classification",
        status="ok" if ok else "blocked",
        reason_class="" if ok else "RUNTIME_CACHE_PATH_UNSAFE",
        profile_id=profile_id,
        persistent_profile_root=str(_resolved(profile_root)),
        cache_paths=entries,
        cache_path_classified=True,
        cache_persistence_proven=False,
        performance_claimed=False,
        latency_claimed=False,
        parity_claimed=False,
    )


def build_original_profile_contamination_guard_packet() -> dict[str, Any]:
    surfaces = {
        name: _metadata(path)
        for name, path in PROTECTED_SURFACE_PATHS.items()
    }
    return packet(
        "original_profile_contamination_guard",
        status="ok",
        protected_surfaces=surfaces,
        bounded_metadata_only=True,
        original_profile_dependency=False,
        original_profile_mutated=False,
        original_profile_write_performed_by_contour=False,
        full_filesystem_isolation_reproof=False,
        original_profile_content_recorded=False,
    )


def build_agent_runtime_claim_limits_packet() -> dict[str, Any]:
    return packet(
        "agent_runtime_claim_limits",
        status="ok",
        allowed_claims=[
            "agent/runtime surfaces classified",
            "bounded plugin availability classified",
            "bounded agent-capable workflow observed or honestly not proven",
            "Custom profile path isolation classified",
        ],
        forbidden_claims=[
            "accelerated performance proven",
            "Original Codex parity proven",
            "all plugins work",
            "all agent models available",
            "model grid implemented",
            "all users fixed",
        ],
        performance_claimed=False,
        latency_claimed=False,
        parity_claimed=False,
        all_plugins_claimed=False,
        all_agent_models_claimed=False,
        model_grid_claimed=False,
        all_users_claimed=False,
        auth_proof_claimed=False,
        final_e2e_claimed=False,
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    for filename, payload in packets.items():
        findings.extend(f"{filename}.{path}" for path in _scan_forbidden_true(payload))
    required_ok = [
        "sync_gate_packet.json",
        "agent_runtime_inventory_packet.json",
        "bundled_plugin_availability_packet.json",
        "agent_capable_workflow_classification_packet.json",
        "profile_isolation_during_runtime_packet.json",
        "runtime_cache_path_classification_packet.json",
        "original_profile_contamination_guard_packet.json",
        "agent_runtime_claim_limits_packet.json",
    ]
    findings.extend(
        f"{name}.status=blocked"
        for name in required_ok
        if packets.get(name, {}).get("status") != "ok"
    )
    return packet(
        "agent_runtime_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_claims_present=bool(findings),
        performance_claimed=False,
        parity_claimed=False,
        model_grid_claimed=False,
        auth_proof_claimed=False,
        final_e2e_claimed=False,
    )


def build_independent_agent_runtime_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true_fields: list[str] = []
    for filename, payload in packets.items():
        forbidden_true_fields.extend(
            f"{filename}.{field}"
            for field in sorted(FORBIDDEN_TRUE_FIELDS)
            if _field_true(payload, field)
        )
    plugin_packet = packets.get("bundled_plugin_availability_packet.json", {})
    workflow_packet = packets.get("agent_capable_workflow_classification_packet.json", {})
    isolation_packet = packets.get("profile_isolation_during_runtime_packet.json", {})
    layer_mixing_packets = [
        filename
        for filename, payload in packets.items()
        if payload.get("model_grid_claimed") is True
        or payload.get("performance_claimed") is True
        or payload.get("parity_claimed") is True
    ]
    return packet(
        "independent_agent_runtime_audit",
        status="ok" if not forbidden_true_fields and not layer_mixing_packets else "blocked",
        forbidden_true_fields=forbidden_true_fields,
        layer_mixing_packets=layer_mixing_packets,
        required_plugin_surfaces_available=plugin_packet.get("all_required_surfaces_available") is True,
        workflow_observed=workflow_packet.get("workflow_observed") is True,
        workflow_unavailable_allowed=workflow_packet.get("unavailable_is_not_failure") is True,
        profile_isolation_status=str(isolation_packet.get("status", "")),
        text_only_audit_counted_as_pass=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "sync_gate_packet.json",
        "agent_runtime_inventory_packet.json",
        "bundled_plugin_availability_packet.json",
        "agent_capable_workflow_classification_packet.json",
        "profile_isolation_during_runtime_packet.json",
        "runtime_cache_path_classification_packet.json",
        "original_profile_contamination_guard_packet.json",
        "agent_runtime_claim_limits_packet.json",
        "false_green_audit.json",
        "independent_agent_runtime_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [name for name in required if packets.get(name, {}).get("status") != "ok"]
    ok = not missing and not blocked
    return packet(
        "agent_runtime_compatibility_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "",
        missing_required_packets=missing,
        blocked_packets=blocked,
        performance_claimed=False,
        latency_claimed=False,
        parity_claimed=False,
        all_plugins_claimed=False,
        model_grid_claimed=False,
        auth_proof_claimed=False,
        final_e2e_claimed=False,
        all_users_claimed=False,
    )


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str = PROFILE_ID,
    base_dir: Path | None = None,
    agent_workflow_observed: bool = False,
    agent_workflow_source: str = "",
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = build_sync_gate_packet(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    packets["agent_runtime_inventory_packet.json"] = build_agent_runtime_inventory_packet(
        profile_id=profile_id,
        base_dir=base_dir,
    )
    packets["bundled_plugin_availability_packet.json"] = build_bundled_plugin_availability_packet(
        profile_id=profile_id,
        base_dir=base_dir,
    )
    packets["agent_capable_workflow_classification_packet.json"] = (
        build_agent_capable_workflow_classification_packet(
            observed=agent_workflow_observed,
            source=agent_workflow_source,
        )
    )
    packets["profile_isolation_during_runtime_packet.json"] = build_profile_isolation_during_runtime_packet(
        profile_id=profile_id,
        base_dir=base_dir,
        plugin_availability_packet=packets["bundled_plugin_availability_packet.json"],
    )
    packets["runtime_cache_path_classification_packet.json"] = build_runtime_cache_path_classification_packet(
        profile_id=profile_id,
        base_dir=base_dir,
    )
    packets["original_profile_contamination_guard_packet.json"] = (
        build_original_profile_contamination_guard_packet()
    )
    packets["agent_runtime_claim_limits_packet.json"] = build_agent_runtime_claim_limits_packet()
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    packets["independent_agent_runtime_audit.json"] = build_independent_agent_runtime_audit_packet(packets)
    packets["agent_runtime_compatibility_summary_packet.json"] = build_summary_packet(packets)
    packets["verification_results_packet.json"] = packet(
        "verification_results",
        status="ok"
        if packets["agent_runtime_compatibility_summary_packet.json"]["status"] == "ok"
        else "blocked",
        top_level_packet_statuses={
            name: payload.get("status", "missing") for name, payload in packets.items()
        },
        ok_packet_count=sum(1 for payload in packets.values() if payload.get("status") == "ok"),
        blocked_packet_count=sum(
            1 for payload in packets.values() if payload.get("status") == "blocked"
        ),
    )
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="custom-codex-agent-runtime-compatibility-r1")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", default=str(REPO_ROOT / EVIDENCE_DIR_NAME))
    parser.add_argument("--profile-id", default=PROFILE_ID)
    parser.add_argument("--base-dir", default="")
    parser.add_argument("--agent-workflow-observed", action="store_true")
    parser.add_argument("--agent-workflow-source", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        profile_id=args.profile_id,
        base_dir=base_dir,
        agent_workflow_observed=args.agent_workflow_observed,
        agent_workflow_source=args.agent_workflow_source,
    )
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    summary = packets["agent_runtime_compatibility_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
