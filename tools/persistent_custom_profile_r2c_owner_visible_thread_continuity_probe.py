#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""R2C owner-visible thread continuity probe for Persistent Custom Codex.

This contour classifies only whether the owner can still see the same nonce
thread after a controlled relaunch. It does not claim storage-level thread
history preservation, route proof, egress proof, model availability, UX
acceptance, Original Codex reversibility, or final E2E.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.persistent_custom_profile_history_r2b_probe import (  # noqa: E402
    _max_manifest_mtime_ns,
    build_bounded_state_diff_packet,
    collect_bounded_profile_manifest,
)
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    NativeProbeLayout,
    build_persistent_cleanup_policy_packet,
    build_persistent_custom_profile_contract_packet,
    build_persistent_custom_profile_identity_packet,
    build_persistent_launcher_selection_packet,
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
    json_write,
    launch_native_candidate,
    materialize_probe_profile,
    terminate_custom_processes,
)
from wild_boar_proxy.runtime import RuntimePaths  # noqa: E402
from wild_boar_proxy.token_command import emit_local_token  # noqa: E402


DEFAULT_R2B_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27"
)
DEFAULT_EVIDENCE_DIR = (
    ROOT
    / "audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27"
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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _paths(profile_id: str, base_dir: Path | None) -> dict[str, Any]:
    return default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)


def _layout(paths: dict[str, Any], evidence_dir: Path) -> NativeProbeLayout:
    profile_root = Path(paths["persistent_profile_root"])
    return NativeProbeLayout(
        tmp_root=evidence_dir,
        profile_dir=profile_root,
        launcher_path=Path(paths["launcher_path"]),
        launcher_stdout=evidence_dir / "persistent_r2c_launcher.stdout.log",
        launcher_stderr=evidence_dir / "persistent_r2c_launcher.stderr.log",
        custom_user_data_dir=Path(paths["user_data_dir"]),
        custom_home_dir=Path(paths["home_dir"]),
        custom_codex_home=Path(paths["codex_home"]),
        custom_tmp_dir=Path(paths["tmp_dir"]),
    )


def _historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> tuple[list[str], list[str]]:
    if skip_git:
        return [], []
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/persistent_custom_profile_r2c_owner_visible_thread_continuity_probe.py",
        "tests/test_native_filesystem_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    current_contour_prefixes = (f"?? {relative_evidence_dir}/",)
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(current_contour_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _base_packets(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return {
        "r2c_sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": []
            if skip_git
            else _run(repo_root, ["git", "status", "--short"]).splitlines(),
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "master_plan_written_to_repo": False,
        },
        "r2c_historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "r2c_version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_version_pinning",
            "status": "ok",
            "codex_cli_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "codex_app_bundle_version": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleVersion",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": "SKIPPED_FOR_TEST"
            if skip_git
            else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
    }


def build_prior_r2b_reference_packet(*, r2b_evidence_dir: Path) -> dict[str, Any]:
    r2b_evidence_dir = r2b_evidence_dir.expanduser().resolve(strict=False)
    summary_path = r2b_evidence_dir / "persistent_custom_profile_history_r2b_summary_packet.json"
    owner_path = r2b_evidence_dir / "r2b_owner_action_boundary_packet.json"
    relaunch_path = r2b_evidence_dir / "persistent_r2b_relaunch_packet.json"
    missing = [str(path) for path in (summary_path, owner_path, relaunch_path) if not path.exists()]
    if missing:
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_prior_r2b_reference",
            "status": "blocked",
            "reason_class": "PRIOR_R2B_EVIDENCE_MISSING",
            "r2b_evidence_dir": str(r2b_evidence_dir),
            "missing_packets": missing,
            "prior_r2b_counts_as_r2c_pass": False,
        }
    summary = _read_json(summary_path)
    owner = _read_json(owner_path)
    relaunch = _read_json(relaunch_path)
    expected_blocked = (
        summary.get("final_status") == "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN"
        and summary.get("thread_history_preserved") is False
    )
    ok = (
        summary.get("status") == "blocked"
        and expected_blocked
        and owner.get("status") == "ok"
        and relaunch.get("custom_process_observed") is True
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_prior_r2b_reference",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "PRIOR_R2B_REFERENCE_UNUSABLE",
        "r2b_evidence_dir": str(r2b_evidence_dir),
        "r2b_summary_sha256": _sha256_file(summary_path),
        "r2b_owner_boundary_sha256": _sha256_file(owner_path),
        "r2b_relaunch_packet_sha256": _sha256_file(relaunch_path),
        "prior_final_status": summary.get("final_status", ""),
        "prior_profile_state_preserved": summary.get("profile_state_preserved") is True,
        "prior_thread_history_preserved": summary.get("thread_history_preserved") is True,
        "prior_r2b_imported_as_blocked_limited_evidence": expected_blocked,
        "prior_r2b_counts_as_r2c_pass": False,
        "prior_r2b_overturned_by_r2c": False,
        "native_relaunch_previously_observed": relaunch.get("custom_process_observed") is True,
    }


def build_r2c_owner_nonce_prompt_packet(*, nonce: str) -> dict[str, Any]:
    prompt = (
        "WBP Persistent Custom R2C thread continuity check. "
        f"Please reply with OK and this nonce only: {nonce}"
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_owner_nonce_prompt",
        "status": "ok" if nonce else "blocked",
        "nonce_sha256": _sha256_text(nonce) if nonce else "",
        "prompt_sha256": _sha256_text(prompt) if nonce else "",
        "nonce_recorded": False,
        "raw_nonce_recorded": False,
        "prompt_hash_recorded": bool(nonce),
        "raw_prompt_recorded": False,
        "prompt_template_shape": (
            "WBP Persistent Custom R2C thread continuity check. "
            "Please reply with OK and this nonce only: <nonce>"
        ),
    }


def build_r2c_owner_first_action_boundary_packet(
    *,
    owner_prompt_entered: bool,
    nonce_used: bool,
    first_window_only: bool,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
) -> dict[str, Any]:
    ok = (
        owner_prompt_entered
        and nonce_used
        and first_window_only
        and target_window_clear
        and evidence_dir_preserved
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_owner_first_action_boundary",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "R2C_FIRST_OWNER_MARKER_INCOMPLETE",
        "owner_prompt_entered": owner_prompt_entered,
        "nonce_used": nonce_used,
        "first_window_only": first_window_only,
        "target_window_clear": target_window_clear,
        "evidence_dir_preserved": evidence_dir_preserved,
        "owner_action_counts_as_storage_proof": False,
        "owner_action_counts_as_route_proof": False,
        "owner_action_counts_as_ux_acceptance": False,
        "raw_prompt_recorded": False,
        "raw_nonce_recorded": False,
    }


def build_r2c_owner_relaunch_visibility_packet(
    *,
    owner_relaunch_checked: bool,
    same_nonce_thread_visible: bool | None,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
) -> dict[str, Any]:
    complete = (
        owner_relaunch_checked
        and same_nonce_thread_visible is not None
        and target_window_clear
        and evidence_dir_preserved
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_owner_relaunch_visibility",
        "status": "ok" if complete else "blocked",
        "reason_class": "" if complete else "R2C_RELAUNCH_VISIBILITY_MARKER_INCOMPLETE",
        "owner_relaunch_checked": owner_relaunch_checked,
        "same_nonce_thread_visible": same_nonce_thread_visible,
        "target_window_clear": target_window_clear,
        "evidence_dir_preserved": evidence_dir_preserved,
        "owner_visibility_counts_as_storage_proof": False,
        "owner_visibility_counts_as_route_proof": False,
        "owner_visibility_counts_as_native_ux_acceptance": False,
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def build_r2c_storage_context_packet(
    *,
    r2b_reference_packet: dict[str, Any],
    before_manifest: dict[str, Any],
    relaunch_manifest: dict[str, Any],
) -> dict[str, Any]:
    diff = build_bounded_state_diff_packet(
        before_manifest=before_manifest,
        after_manifest=relaunch_manifest,
        phase="r2c_before_to_relaunch",
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_storage_context",
        "status": "ok",
        "prior_r2b_profile_state_preserved": r2b_reference_packet.get(
            "prior_profile_state_preserved"
        )
        is True,
        "storage_level_thread_history_proven": False,
        "storage_profile_state_preservation_proven_by_r2c": False,
        "storage_context_only": True,
        "with_storage_unproven_required": True,
        "bounded_diff_status": diff.get("status"),
        "bounded_diff_state_classes_observed": diff.get("state_classes_observed", []),
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def build_r2c_thread_continuity_classification_packet(
    *,
    before_identity_packet: dict[str, Any],
    relaunch_identity_packet: dict[str, Any],
    first_action_packet: dict[str, Any],
    visibility_packet: dict[str, Any],
    storage_context_packet: dict[str, Any],
    relaunch_packet: dict[str, Any],
) -> dict[str, Any]:
    same_identity = (
        before_identity_packet.get("status") == "ok"
        and relaunch_identity_packet.get("status") == "ok"
        and before_identity_packet.get("persistent_profile_id")
        == relaunch_identity_packet.get("persistent_profile_id")
        and before_identity_packet.get("persistent_profile_root")
        == relaunch_identity_packet.get("persistent_profile_root")
    )
    visible = visibility_packet.get("same_nonce_thread_visible") is True
    checked_false = visibility_packet.get("same_nonce_thread_visible") is False
    target_unclear = (
        first_action_packet.get("target_window_clear") is False
        or visibility_packet.get("target_window_clear") is False
    )
    relaunch_observed = relaunch_packet.get("custom_process_observed") is True
    markers_ok = first_action_packet.get("status") == "ok" and visibility_packet.get("status") == "ok"
    storage_unproven = (
        storage_context_packet.get("storage_level_thread_history_proven") is False
        and storage_context_packet.get("with_storage_unproven_required") is True
    )
    classified = same_identity and relaunch_observed and markers_ok and visible and storage_unproven
    ambiguous = target_unclear or (
        markers_ok
        and not classified
        and not checked_false
        and (not same_identity or not relaunch_observed)
    )
    if classified:
        final_status = (
            "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_CLASSIFIED_WITH_STORAGE_UNPROVEN"
        )
        status = "ok"
    elif ambiguous:
        final_status = "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_AMBIGUOUS"
        status = "blocked"
    else:
        final_status = "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_BLOCKED"
        status = "blocked"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_thread_continuity_classification",
        "status": status,
        "final_status": final_status,
        "same_persistent_profile_identity": same_identity,
        "relaunch_observed": relaunch_observed,
        "owner_first_action_marker_ok": first_action_packet.get("status") == "ok",
        "owner_relaunch_visibility_marker_ok": visibility_packet.get("status") == "ok",
        "target_window_clear": not target_unclear,
        "same_nonce_thread_visible": visible,
        "owner_reported_same_nonce_thread_not_visible": checked_false,
        "owner_visible_thread_continuity_classified": classified,
        "storage_level_thread_history_proven": False,
        "profile_state_preservation_proven": False,
        "with_storage_unproven": True,
        "route_proof_claimed": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "native_ux_acceptance_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
        "raw_prompt_recorded": False,
        "raw_thread_content_recorded": False,
    }


def build_r2c_false_green_audit(
    *,
    classification_packet: dict[str, Any],
    storage_context_packet: dict[str, Any],
    visibility_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = (
        classification_packet.get("storage_level_thread_history_proven") is True
        or classification_packet.get("profile_state_preservation_proven") is True
        or classification_packet.get("route_proof_claimed") is True
        or classification_packet.get("direct_egress_absence_claimed") is True
        or classification_packet.get("model_availability_claimed") is True
        or classification_packet.get("native_ux_acceptance_claimed") is True
        or classification_packet.get("final_e2e_claimed") is True
        or visibility_packet.get("owner_visibility_counts_as_storage_proof") is True
        or storage_context_packet.get("storage_context_only") is not True
    )
    checks = [
        {
            "name": "owner_visibility_not_storage_proof",
            "passed": visibility_packet.get("owner_visibility_counts_as_storage_proof") is False,
        },
        {
            "name": "storage_unproven_suffix_required",
            "passed": classification_packet.get("with_storage_unproven") is True,
        },
        {
            "name": "no_route_egress_model_ux_e2e_claims",
            "passed": not any(
                classification_packet.get(field) is True
                for field in (
                    "route_proof_claimed",
                    "direct_egress_absence_claimed",
                    "model_availability_claimed",
                    "native_ux_acceptance_claimed",
                    "final_e2e_claimed",
                )
            ),
        },
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "r2c_false_green_audit",
        "status": "ok"
        if not forbidden_claims_present and all(check["passed"] for check in checks)
        else "blocked",
        "forbidden_claims_present": forbidden_claims_present,
        "checks": checks,
        "text_only_audit_counted_as_pass": False,
    }


def _admission_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    r2b_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    launcher_path = Path(paths["launcher_path"])
    base = _base_packets(repo_root, evidence_dir, skip_git=skip_git)
    r2b_reference = build_prior_r2b_reference_packet(r2b_evidence_dir=r2b_evidence_dir)
    before_identity = build_persistent_custom_profile_identity_packet(
        phase="r2c_before",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    contract = build_persistent_custom_profile_contract_packet(
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    launcher = build_persistent_launcher_selection_packet(
        launcher_path=launcher_path,
        profile_mode="persistent_custom",
        selected_profile_id=profile_id,
        selected_profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
    )
    before_manifest = collect_bounded_profile_manifest(profile_root, phase="r2c_before")
    admission_ok = all(
        packet.get("status") == "ok"
        for packet in (
            base["r2c_sync_gate_packet.json"],
            r2b_reference,
            before_identity,
            contract,
            launcher,
            before_manifest,
        )
    )
    base.update(
        {
            "r2c_prior_r2b_reference_packet.json": r2b_reference,
            "r2c_profile_identity_before_packet.json": before_identity,
            "persistent_custom_profile_contract_packet.json": contract,
            "persistent_launcher_selection_packet.json": launcher,
            "r2c_bounded_profile_manifest_before_packet.json": before_manifest,
            "r2c_admission_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2c_admission",
                "status": "ok" if admission_ok else "blocked",
                "reason_class": "" if admission_ok else "R2C_ADMISSION_BLOCKED",
                "prior_r2b_reference_status": r2b_reference.get("status"),
                "prior_r2b_counts_as_r2c_pass": False,
                "native_launch_attempted": False,
                "owner_action_required": False,
                "thread_continuity_claimed": False,
            },
            "r2c_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2c_summary",
                "status": "ok" if admission_ok else "blocked",
                "final_status": "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_ADMITTED_NO_NATIVE_LAUNCH"
                if admission_ok
                else "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_BLOCKED_ADMISSION",
                "execution_mode": "admission",
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "owner_visible_thread_continuity_classified": False,
                "storage_level_thread_history_proven": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    )
    return base


def build_first_launch_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    r2b_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    endpoint: str,
    model: str,
    owner_nonce: str,
    startup_wait_seconds: float,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    packets = _admission_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        r2b_evidence_dir=r2b_evidence_dir,
        profile_id=profile_id,
        base_dir=base_dir,
        skip_git=skip_git,
    )
    nonce_packet = build_r2c_owner_nonce_prompt_packet(nonce=owner_nonce)
    packets["r2c_owner_nonce_prompt_packet.json"] = nonce_packet
    if packets["r2c_admission_packet.json"].get("status") != "ok":
        packets["r2c_first_launch_packet.json"] = {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_first_launch",
            "status": "blocked",
            "reason_class": "R2C_ADMISSION_BLOCKED",
            "native_launch_attempted": False,
        }
        packets["r2c_summary_packet.json"].update(
            {
                "status": "blocked",
                "execution_mode": "first-launch",
                "final_status": "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_BLOCKED_ADMISSION",
            }
        )
        return packets
    paths = _paths(profile_id, base_dir)
    runtime_paths = RuntimePaths.from_env()
    local_token = emit_local_token(runtime_paths)
    layout = _layout(paths, evidence_dir)
    materialized = materialize_probe_profile(
        layout=layout,
        endpoint=endpoint,
        model=model,
        auth_command_path=repo_root / "wbp_codex_auth_command.py",
        local_token=local_token,
    )
    launch = launch_native_candidate(
        repo_root=repo_root,
        layout=layout,
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    observed = launch.get("custom_process_observed") is True
    packets.update(
        {
            "r2c_first_launch_packet.json": {
                **launch,
                "packet_kind": "r2c_first_launch",
                "status": "ok" if observed else "blocked",
                "profile_mode": "persistent_custom",
                "custom_user_data_dir": paths["user_data_dir"],
                "materialized_profile": materialized,
                "local_listener_token_materialized": True,
                "raw_token_recorded": False,
                "raw_prompt_recorded": False,
            },
            "r2c_process_inventory_after_first_launch_packet.json": (
                collect_codex_process_inventory(custom_user_data_dir=paths["user_data_dir"])
            ),
            "r2c_owner_first_action_stop_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2c_owner_first_action_stop",
                "status": "blocked",
                "reason_class": "R2C_OWNER_NONCE_ENTRY_REQUIRED",
                "stop_required_before_cleanup_or_relaunch": True,
                "required_owner_marker": (
                    "owner_prompt_entered=true; nonce_used=true; "
                    "first_window_only=true; target_window_clear=true; "
                    "evidence_dir_preserved=true"
                ),
                "thread_continuity_claimed": False,
                "raw_prompt_recorded": False,
                "raw_nonce_recorded": False,
            },
            "r2c_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2c_summary",
                "status": "blocked",
                "final_status": "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_STOP1_OWNER_ACTION_REQUIRED"
                if observed
                else "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_BLOCKED_NATIVE_LAUNCH_FAILED",
                "execution_mode": "first-launch",
                "profile_id": profile_id,
                "profile_root": paths["persistent_profile_root"],
                "native_launch_attempted": True,
                "custom_process_observed": observed,
                "owner_action_required": observed,
                "owner_nonce_hash_recorded": nonce_packet.get("nonce_sha256", "") != "",
                "owner_visible_thread_continuity_classified": False,
                "storage_level_thread_history_proven": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    )
    return packets


def build_relaunch_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    owner_prompt_entered: bool,
    nonce_used: bool,
    first_window_only: bool,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
    startup_wait_seconds: float,
) -> dict[str, dict[str, Any]]:
    paths = _paths(profile_id, base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    codex_home = Path(paths["codex_home"])
    user_data_dir = Path(paths["user_data_dir"])
    first_action = build_r2c_owner_first_action_boundary_packet(
        owner_prompt_entered=owner_prompt_entered,
        nonce_used=nonce_used,
        first_window_only=first_window_only,
        target_window_clear=target_window_clear,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    if first_action.get("status") != "ok":
        ambiguous = first_action.get("target_window_clear") is False
        return {
            "r2c_owner_first_action_boundary_packet.json": first_action,
            "r2c_summary_packet.json": {
                "captured_at_utc": _utc_now(),
                "packet_kind": "r2c_summary",
                "status": "blocked",
                "final_status": (
                    "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_AMBIGUOUS"
                    if ambiguous
                    else "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_BLOCKED_STOP1_OWNER_ACTION"
                ),
                "execution_mode": "relaunch",
                "profile_id": profile_id,
                "profile_root": str(profile_root),
                "native_launch_attempted": False,
                "relaunch_attempted": False,
                "owner_action_required": True,
                "owner_visible_thread_continuity_classified": False,
                "storage_level_thread_history_proven": False,
                "direct_egress_absence_claimed": False,
                "model_availability_claimed": False,
                "native_ux_acceptance_claimed": False,
                "final_e2e_claimed": False,
            },
        }
    before_manifest = _read_json(evidence_dir / "r2c_bounded_profile_manifest_before_packet.json")
    after_first_action_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="r2c_after_first_owner_action",
        changed_since_ns=_max_manifest_mtime_ns(before_manifest),
    )
    cleanup = terminate_custom_processes(str(user_data_dir))
    runtime_paths = RuntimePaths.from_env()
    relaunch = launch_native_candidate(
        repo_root=repo_root,
        layout=_layout(paths, evidence_dir),
        real_runtime_paths=runtime_paths,
        startup_wait_seconds=startup_wait_seconds,
    )
    relaunch_identity = build_persistent_custom_profile_identity_packet(
        phase="r2c_relaunch",
        profile_id=profile_id,
        profile_root=profile_root,
        codex_home=codex_home,
        user_data_dir=user_data_dir,
        expected_profile_id=profile_id,
        expected_profile_root=profile_root,
    )
    relaunch_manifest = collect_bounded_profile_manifest(
        profile_root,
        phase="r2c_after_relaunch",
        changed_since_ns=_max_manifest_mtime_ns(after_first_action_manifest),
    )
    observed = relaunch.get("custom_process_observed") is True
    return {
        "r2c_owner_first_action_boundary_packet.json": first_action,
        "r2c_bounded_profile_manifest_after_first_action_packet.json": (
            after_first_action_manifest
        ),
        "r2c_process_cleanup_packet.json": cleanup,
        "r2c_relaunch_packet.json": {
            **relaunch,
            "packet_kind": "r2c_relaunch",
            "status": "ok" if observed else "blocked",
            "profile_mode": "persistent_custom",
            "custom_user_data_dir": str(user_data_dir),
        },
        "r2c_profile_identity_relaunch_packet.json": relaunch_identity,
        "r2c_bounded_profile_manifest_relaunch_packet.json": relaunch_manifest,
        "r2c_owner_relaunch_visibility_stop_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_owner_relaunch_visibility_stop",
            "status": "blocked",
            "reason_class": "R2C_OWNER_RELAUNCH_VISIBILITY_REQUIRED",
            "stop_required_before_thread_continuity_classification": True,
            "required_owner_marker": (
                "owner_relaunch_checked=true; "
                "same_nonce_thread_visible=true|false; target_window_clear=true; "
                "evidence_dir_preserved=true"
            ),
            "thread_continuity_claimed": False,
        },
        "r2c_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_summary",
            "status": "blocked",
            "final_status": "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_STOP2_VISIBILITY_REQUIRED"
            if observed
            else "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_R2C_BLOCKED_RELAUNCH_FAILED",
            "execution_mode": "relaunch",
            "profile_id": profile_id,
            "profile_root": str(profile_root),
            "native_launch_attempted": True,
            "relaunch_attempted": True,
            "custom_process_observed": observed,
            "owner_action_required": observed,
            "owner_visible_thread_continuity_classified": False,
            "storage_level_thread_history_proven": False,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
        },
    }


def build_classification_packets(
    *,
    evidence_dir: Path,
    owner_relaunch_checked: bool,
    same_nonce_thread_visible: bool | None,
    target_window_clear: bool,
    evidence_dir_preserved: bool,
) -> dict[str, dict[str, Any]]:
    before_identity = _read_json(evidence_dir / "r2c_profile_identity_before_packet.json")
    relaunch_identity = _read_json(evidence_dir / "r2c_profile_identity_relaunch_packet.json")
    before_manifest = _read_json(evidence_dir / "r2c_bounded_profile_manifest_before_packet.json")
    relaunch_manifest = _read_json(
        evidence_dir / "r2c_bounded_profile_manifest_relaunch_packet.json"
    )
    first_action = _read_json(evidence_dir / "r2c_owner_first_action_boundary_packet.json")
    relaunch = _read_json(evidence_dir / "r2c_relaunch_packet.json")
    prior_r2b = _read_json(evidence_dir / "r2c_prior_r2b_reference_packet.json")
    visibility = build_r2c_owner_relaunch_visibility_packet(
        owner_relaunch_checked=owner_relaunch_checked,
        same_nonce_thread_visible=same_nonce_thread_visible,
        target_window_clear=target_window_clear,
        evidence_dir_preserved=evidence_dir_preserved,
    )
    storage_context = build_r2c_storage_context_packet(
        r2b_reference_packet=prior_r2b,
        before_manifest=before_manifest,
        relaunch_manifest=relaunch_manifest,
    )
    classification = build_r2c_thread_continuity_classification_packet(
        before_identity_packet=before_identity,
        relaunch_identity_packet=relaunch_identity,
        first_action_packet=first_action,
        visibility_packet=visibility,
        storage_context_packet=storage_context,
        relaunch_packet=relaunch,
    )
    false_green = build_r2c_false_green_audit(
        classification_packet=classification,
        storage_context_packet=storage_context,
        visibility_packet=visibility,
    )
    final_ok = classification.get("status") == "ok" and false_green.get("status") == "ok"
    final_status = (
        classification.get("final_status")
        if final_ok
        else (
            "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_AMBIGUOUS"
            if classification.get("final_status")
            == "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_AMBIGUOUS"
            else "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_BLOCKED"
        )
    )
    return {
        "r2c_owner_relaunch_visibility_packet.json": visibility,
        "r2c_storage_context_packet.json": storage_context,
        "r2c_thread_continuity_classification_packet.json": classification,
        "r2c_false_green_audit.json": false_green,
        "r2c_summary_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "r2c_summary",
            "status": "ok" if final_ok else "blocked",
            "final_status": final_status,
            "execution_mode": "classify",
            "owner_visible_thread_continuity_classified": final_ok,
            "same_nonce_thread_visible": visibility.get("same_nonce_thread_visible"),
            "storage_level_thread_history_proven": False,
            "with_storage_unproven": True,
            "direct_egress_absence_claimed": False,
            "model_availability_claimed": False,
            "native_ux_acceptance_claimed": False,
            "final_e2e_claimed": False,
        },
    }


def _parse_nullable_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    if normalized in {"unknown", "none", ""}:
        return None
    raise ValueError(f"Unsupported boolean value: {value!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="persistent-custom-profile-r2c-thread-continuity")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--r2b-evidence-dir", default=str(DEFAULT_R2B_EVIDENCE_DIR))
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", default="")
    parser.add_argument(
        "--execution-mode",
        choices=["admission", "first-launch", "relaunch", "classify"],
        default="admission",
    )
    parser.add_argument("--endpoint", default="http://127.0.0.1:8318/v1")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--owner-nonce", default="")
    parser.add_argument("--startup-wait-seconds", type=float, default=12.0)
    parser.add_argument("--owner-prompt-entered", action="store_true")
    parser.add_argument("--nonce-used", action="store_true")
    parser.add_argument("--first-window-only", action="store_true")
    parser.add_argument("--target-window-clear", action="store_true")
    parser.add_argument("--evidence-dir-preserved", action="store_true")
    parser.add_argument("--owner-relaunch-checked", action="store_true")
    parser.add_argument("--same-nonce-thread-visible", default="unknown")
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    r2b_evidence_dir = Path(args.r2b_evidence_dir).resolve()
    base_dir = Path(args.base_dir).expanduser().resolve() if args.base_dir else None
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if args.execution_mode == "first-launch":
        packets = build_first_launch_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            r2b_evidence_dir=r2b_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            endpoint=args.endpoint,
            model=args.model,
            owner_nonce=args.owner_nonce,
            startup_wait_seconds=args.startup_wait_seconds,
            skip_git=args.skip_git,
        )
    elif args.execution_mode == "relaunch":
        packets = build_relaunch_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            owner_prompt_entered=args.owner_prompt_entered,
            nonce_used=args.nonce_used,
            first_window_only=args.first_window_only,
            target_window_clear=args.target_window_clear,
            evidence_dir_preserved=args.evidence_dir_preserved,
            startup_wait_seconds=args.startup_wait_seconds,
        )
    elif args.execution_mode == "classify":
        packets = build_classification_packets(
            evidence_dir=evidence_dir,
            owner_relaunch_checked=args.owner_relaunch_checked,
            same_nonce_thread_visible=_parse_nullable_bool(args.same_nonce_thread_visible),
            target_window_clear=args.target_window_clear,
            evidence_dir_preserved=args.evidence_dir_preserved,
        )
    else:
        packets = _admission_packets(
            repo_root=repo_root,
            evidence_dir=evidence_dir,
            r2b_evidence_dir=r2b_evidence_dir,
            profile_id=args.profile_id,
            base_dir=base_dir,
            skip_git=args.skip_git,
        )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    summary = packets["r2c_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
