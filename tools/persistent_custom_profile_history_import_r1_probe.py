#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import packet-backed Persistent Custom profile continuity evidence under current bounds."""

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

from wild_boar_proxy.native_filesystem_probe import json_write


DEFAULT_SOURCE_DIRS = {
    "r1_contract": ROOT
    / "audit_results/wbp_persistent_profile_launcher_contract_readiness_r1_2026-05-27",
    "r2_enforcement": ROOT
    / "audit_results/wbp_persistent_profile_launcher_dry_run_enforcement_readiness_r2_2026-05-27",
    "r2b_live": ROOT
    / "audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27",
    "r2c_continuity": ROOT
    / "audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27",
    "r3_storage": ROOT
    / "audit_results/wbp_persistent_custom_profile_storage_truth_r3_2026-05-27",
    "r4_schema": ROOT
    / "audit_results/wbp_persistent_custom_profile_storage_schema_attribution_r4_2026-05-27",
}

SOURCE_REQUIRED_PACKETS = {
    "r1_contract": {
        "persistent_profile_identity_contract_packet.json",
        "persistent_cleanup_retention_policy_packet.json",
        "persistent_concurrent_launch_policy_packet.json",
        "original_codex_profile_non_dependency_packet.json",
        "persistent_launcher_contract_packet.json",
        "persistent_launcher_readiness_summary_packet.json",
    },
    "r2_enforcement": {
        "persistent_no_silent_fallback_packet.json",
        "persistent_launcher_enforcement_contract_packet.json",
        "persistent_launcher_enforcement_summary_packet.json",
    },
    "r2b_live": {
        "persistent_custom_profile_contract_packet.json",
        "persistent_custom_profile_before_bounded_manifest.json",
        "persistent_custom_profile_after_owner_action_bounded_manifest.json",
        "persistent_custom_profile_after_relaunch_bounded_manifest.json",
        "persistent_r2b_profile_state_preservation_packet.json",
        "persistent_r2b_thread_history_preservation_packet.json",
        "persistent_cleanup_policy_packet.json",
        "integration_ownership_baseline_packet.json",
        "original_codex_profile_drift_packet.json",
        "persistent_custom_profile_history_r2b_summary_packet.json",
        "r2b_owner_action_boundary_packet.json",
    },
    "r2c_continuity": {
        "r2c_profile_identity_before_packet.json",
        "r2c_profile_identity_relaunch_packet.json",
        "r2c_thread_continuity_classification_packet.json",
        "r2c_storage_context_packet.json",
        "r2c_summary_packet.json",
        "r2c_prior_r2b_reference_packet.json",
        "r2c_bounded_profile_manifest_before_packet.json",
        "r2c_bounded_profile_manifest_after_first_action_packet.json",
        "r2c_bounded_profile_manifest_relaunch_packet.json",
    },
    "r3_storage": {
        "persistent_storage_truth_classification_packet.json",
        "persistent_relaunch_restoration_source_packet.json",
        "persistent_storage_r3_summary_packet.json",
    },
    "r4_schema": {
        "persistent_storage_restoration_hypothesis_packet.json",
        "persistent_storage_candidate_selection_packet.json",
        "persistent_storage_r4_summary_packet.json",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_import_input_error",
        "status": "blocked",
        "reason_class": reason_class,
        "message": message,
        "traceback_emitted": False,
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        json_write(evidence_dir / "input_error_packet.json", packet)
    print(json.dumps(packet, indent=2, sort_keys=True), file=sys.stderr)
    return 2


def _historical_quarantine(
    repo_root: Path, evidence_dir: Path
) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    quarantined = [
        line
        for line in status_lines
        if line.strip().startswith(
            (
                "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
                "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/",
                "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/",
                "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
                "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/",
                "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
                "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
            )
        )
    ]
    admitted_current_contour = [
        "tools/persistent_custom_profile_history_import_r1_probe.py",
        "tests/test_persistent_custom_profile_history_import_r1_probe.py",
    ]
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _version_packet(repo_root: Path) -> dict[str, Any]:
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "status": "ok",
        "codex_cli_version": _run(repo_root, ["codex", "--version"], check=False),
        "codex_cli_path": _run(repo_root, ["which", "codex"], check=False),
        "codex_app_path": "/Applications/Codex.app",
        "codex_app_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleShortVersionString",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
            check=False,
        ),
        "codex_app_bundle_version": _run(
            repo_root,
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleVersion",
                "/Applications/Codex.app/Contents/Info.plist",
            ],
            check=False,
        ),
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
    }


def _source_manifest_summary(source_path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_packet": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "status": packet.get("status", "missing"),
        "phase": packet.get("phase", ""),
        "profile_root": packet.get("root", ""),
        "profile_fingerprint_sha256": packet.get("profile_fingerprint_sha256", ""),
        "entry_count": packet.get("entry_count", 0),
        "state_class_counts": packet.get("state_class_counts", {}),
        "counts": packet.get("counts", {}),
        "max_mtime_ns": packet.get("max_mtime_ns", 0),
        "total_file_bytes": packet.get("total_file_bytes", 0),
        "exists": packet.get("exists", False),
        "full_entry_list_recorded": packet.get("full_entry_list_recorded", False),
        "raw_content_recorded": packet.get("raw_content_recorded", False),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="persistent-custom-profile-history-import-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--r1-contract-dir", default=str(DEFAULT_SOURCE_DIRS["r1_contract"]))
    parser.add_argument(
        "--r2-enforcement-dir", default=str(DEFAULT_SOURCE_DIRS["r2_enforcement"])
    )
    parser.add_argument("--r2b-live-dir", default=str(DEFAULT_SOURCE_DIRS["r2b_live"]))
    parser.add_argument(
        "--r2c-continuity-dir", default=str(DEFAULT_SOURCE_DIRS["r2c_continuity"])
    )
    parser.add_argument("--r3-storage-dir", default=str(DEFAULT_SOURCE_DIRS["r3_storage"]))
    parser.add_argument("--r4-schema-dir", default=str(DEFAULT_SOURCE_DIRS["r4_schema"]))
    return parser


def _load_sources(
    source_dirs: dict[str, Path],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, list[str]], dict[str, list[str]]]:
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    missing: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}
    for label, required in SOURCE_REQUIRED_PACKETS.items():
        parsed[label] = {}
        missing[label] = []
        invalid[label] = []
        source_dir = source_dirs[label]
        for name in sorted(required):
            path = source_dir / name
            if not path.exists():
                missing[label].append(name)
                continue
            try:
                parsed[label][name] = _read_json(path)
            except json.JSONDecodeError:
                invalid[label].append(name)
    return parsed, missing, invalid


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_dirs: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    parsed, missing, invalid = _load_sources(source_dirs)

    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_status_short": status_lines,
        "unexpected_dirty_entries": unexpected_dirty,
        "new_evidence_dir": str(evidence_dir),
        "master_plan_written_to_repo": False,
    }
    packets["historical_dirt_quarantine_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "historical_dirt_quarantine",
        "status": "ok",
        "quarantined_paths": quarantined,
        "quarantine_classification": "out_of_scope_historical_residue",
        "current_contour_relies_on_quarantined_paths": False,
        "current_contour_mutates_quarantined_paths": False,
        "current_contour_stages_quarantined_paths": False,
    }
    packets["version_pinning_packet.json"] = _version_packet(repo_root)

    inventory_ok = all(not missing[label] and not invalid[label] for label in SOURCE_REQUIRED_PACKETS)
    packets["persistent_source_reference_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_source_reference_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "required_packets": {
            label: sorted(required) for label, required in SOURCE_REQUIRED_PACKETS.items()
        },
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "current_live_launch_attempted": False,
    }

    r1 = parsed["r1_contract"]
    r2 = parsed["r2_enforcement"]
    r2b = parsed["r2b_live"]
    r2c = parsed["r2c_continuity"]
    r3 = parsed["r3_storage"]
    r4 = parsed["r4_schema"]

    r1_identity = r1.get("persistent_profile_identity_contract_packet.json", {})
    r1_contract = r1.get("persistent_launcher_contract_packet.json", {})
    r1_cleanup = r1.get("persistent_cleanup_retention_policy_packet.json", {})
    r1_concurrent = r1.get("persistent_concurrent_launch_policy_packet.json", {})
    r1_original = r1.get("original_codex_profile_non_dependency_packet.json", {})
    r1_summary = r1.get("persistent_launcher_readiness_summary_packet.json", {})
    r2_no_fallback = r2.get("persistent_no_silent_fallback_packet.json", {})
    r2_contract = r2.get("persistent_launcher_enforcement_contract_packet.json", {})
    r2_summary = r2.get("persistent_launcher_enforcement_summary_packet.json", {})
    r2b_contract = r2b.get("persistent_custom_profile_contract_packet.json", {})
    r2b_profile_state = r2b.get("persistent_r2b_profile_state_preservation_packet.json", {})
    r2b_thread = r2b.get("persistent_r2b_thread_history_preservation_packet.json", {})
    r2b_summary = r2b.get("persistent_custom_profile_history_r2b_summary_packet.json", {})
    r2b_owner_boundary = r2b.get("r2b_owner_action_boundary_packet.json", {})
    r2b_integration = r2b.get("integration_ownership_baseline_packet.json", {})
    r2b_cleanup = r2b.get("persistent_cleanup_policy_packet.json", {})
    r2b_original_drift = r2b.get("original_codex_profile_drift_packet.json", {})
    r2c_before = r2c.get("r2c_profile_identity_before_packet.json", {})
    r2c_relaunch = r2c.get("r2c_profile_identity_relaunch_packet.json", {})
    r2c_class = r2c.get("r2c_thread_continuity_classification_packet.json", {})
    r2c_storage = r2c.get("r2c_storage_context_packet.json", {})
    r2c_summary = r2c.get("r2c_summary_packet.json", {})
    r2c_prior = r2c.get("r2c_prior_r2b_reference_packet.json", {})
    r3_truth = r3.get("persistent_storage_truth_classification_packet.json", {})
    r3_restore = r3.get("persistent_relaunch_restoration_source_packet.json", {})
    r3_summary = r3.get("persistent_storage_r3_summary_packet.json", {})
    r4_hypothesis = r4.get("persistent_storage_restoration_hypothesis_packet.json", {})
    r4_candidates = r4.get("persistent_storage_candidate_selection_packet.json", {})
    r4_summary = r4.get("persistent_storage_r4_summary_packet.json", {})

    validation_checks = {
        "r1_contract_ready": (
            r1_summary.get("status") == "ok"
            and r1_identity.get("status") == "ok"
            and r1_contract.get("status") == "ok"
            and r1_cleanup.get("status") == "ok"
            and r1_concurrent.get("status") == "ok"
            and r1_original.get("status") == "ok"
        ),
        "r2_enforcement_ready": (
            r2_summary.get("status") == "ok"
            and r2_no_fallback.get("status") == "ok"
            and r2_contract.get("status") == "ok"
        ),
        "r2b_negative_preservation_truth": (
            r2b_summary.get("status") == "blocked"
            and r2b_summary.get("final_status")
            == "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN"
            and r2b_profile_state.get("profile_state_preserved") is False
            and r2b_thread.get("thread_history_preserved") is False
            and r2b_owner_boundary.get("status") == "ok"
        ),
        "r2c_owner_visible_continuity_truth": (
            r2c_summary.get("status") == "ok"
            and r2c_summary.get("final_status")
            == "WBP_CUSTOM_CODEX_OWNER_VISIBLE_THREAD_CONTINUITY_CLASSIFIED_WITH_STORAGE_UNPROVEN"
            and r2c_class.get("owner_visible_thread_continuity_classified") is True
            and r2c_class.get("same_nonce_thread_visible") is True
            and r2c_class.get("same_persistent_profile_identity") is True
            and r2c_class.get("storage_level_thread_history_proven") is False
        ),
        "r2c_prior_r2b_consistent": (
            r2c_prior.get("status") == "ok"
            and r2c_prior.get("prior_final_status")
            == "WBP_CUSTOM_PERSISTENT_PROFILE_R2B_BLOCKED_HISTORY_UNPROVEN"
            and r2c_prior.get("prior_profile_state_preserved") is False
            and r2c_prior.get("prior_thread_history_preserved") is False
        ),
        "r3_storage_limits_truth": (
            r3_summary.get("status") == "ok"
            and r3_summary.get("final_status")
            == "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_STORAGE_TRUTH_CLASSIFIED_WITH_LIMITS"
            and r3_truth.get("state_class_classified") is True
            and r3_truth.get("storage_level_thread_history_proven") is False
            and r3_restore.get("local_storage_restoration_source_proven") is False
        ),
        "r4_schema_limits_truth": (
            r4_summary.get("status") == "ok"
            and r4_summary.get("final_status")
            == "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_HYPOTHESES_CLASSIFIED_WITH_LIMITS"
            and r4_hypothesis.get("durable_restoration_proven") is False
            and r4_hypothesis.get("storage_level_thread_history_proven") is False
            and r4_candidates.get("metadata_only") is True
        ),
    }
    packets["persistent_source_reference_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_source_reference_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [
            {"name": name, "passed": passed}
            for name, passed in validation_checks.items()
        ],
        "validation_scope": "bounded_persistent_custom_profile_continuity_only",
        "source_chain_counts_as_route_proof": False,
        "source_chain_counts_as_final_e2e": False,
    }

    contract_ok = (
        r2b_contract.get("status") == "ok"
        and r1_contract.get("status") == "ok"
        and r2_contract.get("status") == "ok"
        and r2_no_fallback.get("status") == "ok"
        and r2b_contract.get("profile_mode") == "persistent_custom"
        and r2b_contract.get("history_persistence_expected") is True
        and r2b_contract.get("original_codex_profile_runtime_dependency") is False
        and r2b_contract.get("browser_client_path_authority") is False
        and r2b_contract.get("remote_client_path_authority") is False
        and r2_no_fallback.get("silent_persistent_to_ephemeral_fallback_allowed") is False
    )
    packets["persistent_custom_profile_contract_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_contract_import",
        "status": "ok" if contract_ok else "blocked",
        "source_packets": [
            str(source_dirs["r2b_live"] / "persistent_custom_profile_contract_packet.json"),
            str(source_dirs["r1_contract"] / "persistent_launcher_contract_packet.json"),
            str(
                source_dirs["r2_enforcement"]
                / "persistent_launcher_enforcement_contract_packet.json"
            ),
            str(source_dirs["r2_enforcement"] / "persistent_no_silent_fallback_packet.json"),
        ],
        "persistent_profile_id": r2b_contract.get("persistent_profile_id", ""),
        "persistent_profile_root": r2b_contract.get("persistent_profile_root", ""),
        "codex_home": r2b_contract.get("codex_home", ""),
        "user_data_dir": r2b_contract.get("user_data_dir", ""),
        "profile_mode": r2b_contract.get("profile_mode", ""),
        "history_persistence_expected": r2b_contract.get("history_persistence_expected") is True,
        "original_codex_profile_runtime_dependency": (
            r2b_contract.get("original_codex_profile_runtime_dependency") is True
        ),
        "cleanup_deletes_persistent_profile_by_default": (
            r2b_contract.get("cleanup_deletes_persistent_profile_by_default") is True
        ),
        "browser_client_path_authority": (
            r2b_contract.get("browser_client_path_authority") is True
        ),
        "remote_client_path_authority": (
            r2b_contract.get("remote_client_path_authority") is True
        ),
        "silent_persistent_to_ephemeral_fallback_allowed": (
            r2_no_fallback.get("silent_persistent_to_ephemeral_fallback_allowed") is True
        ),
        "counts_as_route_proof": False,
        "counts_as_final_e2e": False,
    }

    same_profile_id = (
        r1_identity.get("persistent_profile_id")
        == r2c_before.get("persistent_profile_id")
        == r2c_relaunch.get("persistent_profile_id")
    )
    same_profile_root = (
        r1_identity.get("persistent_profile_root")
        == r2c_before.get("persistent_profile_root")
        == r2c_relaunch.get("persistent_profile_root")
    )
    same_codex_home = (
        r1_identity.get("codex_home")
        == r2c_before.get("codex_home")
        == r2c_relaunch.get("codex_home")
    )
    same_user_data_dir = (
        r1_identity.get("user_data_dir")
        == r2c_before.get("user_data_dir")
        == r2c_relaunch.get("user_data_dir")
    )
    identity_ok = (
        r1_identity.get("status") == "ok"
        and r2c_before.get("status") == "ok"
        and r2c_relaunch.get("status") == "ok"
        and same_profile_id
        and same_profile_root
        and same_codex_home
        and same_user_data_dir
        and r1_identity.get("same_profile_id_as_expected") is True
        and r1_identity.get("same_profile_root_as_expected") is True
        and r2c_before.get("same_profile_id_as_expected") is True
        and r2c_before.get("same_profile_root_as_expected") is True
        and r2c_relaunch.get("same_profile_id_as_expected") is True
        and r2c_relaunch.get("same_profile_root_as_expected") is True
        and r1_identity.get("silent_profile_switching_detected") is False
        and r2c_before.get("silent_profile_switching_detected") is False
        and r2c_relaunch.get("silent_profile_switching_detected") is False
        and r2_no_fallback.get("silent_persistent_to_ephemeral_fallback_allowed") is False
    )
    packets["persistent_custom_profile_identity_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_custom_profile_identity_import",
        "status": "ok" if identity_ok else "blocked",
        "source_packets": [
            str(
                source_dirs["r1_contract"]
                / "persistent_profile_identity_contract_packet.json"
            ),
            str(source_dirs["r2c_continuity"] / "r2c_profile_identity_before_packet.json"),
            str(source_dirs["r2c_continuity"] / "r2c_profile_identity_relaunch_packet.json"),
            str(source_dirs["r2_enforcement"] / "persistent_no_silent_fallback_packet.json"),
        ],
        "persistent_profile_id": r2c_before.get("persistent_profile_id", ""),
        "persistent_profile_root": r2c_before.get("persistent_profile_root", ""),
        "codex_home": r2c_before.get("codex_home", ""),
        "user_data_dir": r2c_before.get("user_data_dir", ""),
        "same_profile_id_across_relaunch": same_profile_id,
        "same_profile_root_across_relaunch": same_profile_root,
        "same_codex_home_across_relaunch": same_codex_home,
        "same_user_data_dir_across_relaunch": same_user_data_dir,
        "same_profile_identity_across_relaunch": (
            same_profile_id
            and same_profile_root
            and same_codex_home
            and same_user_data_dir
        ),
        "silent_profile_switching_detected": (
            r1_identity.get("silent_profile_switching_detected") is True
            or r2c_before.get("silent_profile_switching_detected") is True
            or r2c_relaunch.get("silent_profile_switching_detected") is True
        ),
        "silent_persistent_to_ephemeral_fallback_allowed": (
            r2_no_fallback.get("silent_persistent_to_ephemeral_fallback_allowed") is True
        ),
        "counts_as_daily_reliability_proof": False,
    }

    before_manifest_path = (
        source_dirs["r2c_continuity"] / "r2c_bounded_profile_manifest_before_packet.json"
    )
    after_manifest_path = (
        source_dirs["r2c_continuity"]
        / "r2c_bounded_profile_manifest_after_first_action_packet.json"
    )
    relaunch_manifest_path = (
        source_dirs["r2c_continuity"] / "r2c_bounded_profile_manifest_relaunch_packet.json"
    )
    packets["persistent_custom_profile_before_snapshot.json"] = _source_manifest_summary(
        before_manifest_path, r2c["r2c_bounded_profile_manifest_before_packet.json"]
    )
    packets["persistent_custom_profile_before_snapshot.json"].update(
        {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_before_snapshot_import",
        }
    )
    packets["persistent_custom_profile_after_event_snapshot.json"] = _source_manifest_summary(
        after_manifest_path, r2c["r2c_bounded_profile_manifest_after_first_action_packet.json"]
    )
    packets["persistent_custom_profile_after_event_snapshot.json"].update(
        {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_after_event_snapshot_import",
        }
    )
    packets["persistent_custom_profile_relaunch_snapshot.json"] = _source_manifest_summary(
        relaunch_manifest_path, r2c["r2c_bounded_profile_manifest_relaunch_packet.json"]
    )
    packets["persistent_custom_profile_relaunch_snapshot.json"].update(
        {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_custom_profile_relaunch_snapshot_import",
        }
    )

    thread_packet_ok = (
        r2c_class.get("status") == "ok"
        and r2b_profile_state.get("status") == "blocked"
        and r2b_thread.get("status") == "blocked"
        and r3_restore.get("status") == "ok"
        and r3_truth.get("status") == "ok"
        and r4_hypothesis.get("status") == "ok"
    )
    with_limits_reasons = [
        reason
        for reason, present in (
            ("PROFILE_STATE_PRESERVATION_UNPROVEN", r2b_profile_state.get("profile_state_preserved") is not True),
            ("THREAD_HISTORY_STORAGE_PROVEN_FALSE", r2b_thread.get("thread_history_preserved") is not True),
            ("STORAGE_LEVEL_THREAD_HISTORY_UNPROVEN", r2c_class.get("storage_level_thread_history_proven") is not True),
            ("RELAUNCH_RESTORATION_SOURCE_UNPROVEN", r3_restore.get("local_storage_restoration_source_proven") is not True),
            ("DURABLE_RESTORATION_UNPROVEN", r4_hypothesis.get("durable_restoration_proven") is not True),
        )
        if present
    ]
    packets["thread_history_preservation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "thread_history_preservation_import",
        "status": "ok" if thread_packet_ok else "blocked",
        "source_packets": [
            str(
                source_dirs["r2c_continuity"]
                / "r2c_thread_continuity_classification_packet.json"
            ),
            str(
                source_dirs["r2b_live"]
                / "persistent_r2b_profile_state_preservation_packet.json"
            ),
            str(
                source_dirs["r2b_live"]
                / "persistent_r2b_thread_history_preservation_packet.json"
            ),
            str(
                source_dirs["r3_storage"]
                / "persistent_relaunch_restoration_source_packet.json"
            ),
            str(
                source_dirs["r4_schema"]
                / "persistent_storage_restoration_hypothesis_packet.json"
            ),
        ],
        "owner_visible_thread_continuity_classified": (
            r2c_class.get("owner_visible_thread_continuity_classified") is True
        ),
        "same_nonce_thread_visible": r2c_class.get("same_nonce_thread_visible") is True,
        "same_persistent_profile_identity": (
            r2c_class.get("same_persistent_profile_identity") is True
        ),
        "profile_state_preservation_proven": (
            r2b_profile_state.get("profile_state_preserved") is True
        ),
        "thread_history_preserved": r2b_thread.get("thread_history_preserved") is True,
        "storage_level_thread_history_proven": (
            r2c_class.get("storage_level_thread_history_proven") is True
        ),
        "relaunch_restoration_source_proven": (
            r3_restore.get("local_storage_restoration_source_proven") is True
        ),
        "durable_restoration_proven": (
            r4_hypothesis.get("durable_restoration_proven") is True
        ),
        "visible_thread_context_only": r2b_thread.get("visible_thread_context_only") is True,
        "selected_state_surfaces_only": True,
        "with_limits_required": True,
        "with_limits_reasons": with_limits_reasons,
        "counts_as_route_proof": False,
        "counts_as_final_e2e": False,
    }

    concurrent_policy_ok = (
        r1_concurrent.get("status") == "ok"
        and r2_no_fallback.get("status") == "ok"
        and r2_contract.get("status") == "ok"
        and r1_concurrent.get("policy") == "single_writer_only"
        and r1_concurrent.get("launcher_enforces_policy") is True
        and r1_concurrent.get("same_profile_multi_writer_allowed") is False
        and r2_no_fallback.get("fallback_rejected") is True
    )
    packets["concurrent_launch_policy_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "concurrent_launch_policy_import",
        "status": "ok" if concurrent_policy_ok else "blocked",
        "source_packets": [
            str(
                source_dirs["r1_contract"] / "persistent_concurrent_launch_policy_packet.json"
            ),
            str(source_dirs["r2_enforcement"] / "persistent_no_silent_fallback_packet.json"),
            str(
                source_dirs["r2_enforcement"]
                / "persistent_launcher_enforcement_contract_packet.json"
            ),
        ],
        "policy": r1_concurrent.get("policy", ""),
        "launcher_enforces_policy": r1_concurrent.get("launcher_enforces_policy") is True,
        "lock_path": r1_concurrent.get("lock_path", ""),
        "same_profile_multi_writer_allowed": (
            r1_concurrent.get("same_profile_multi_writer_allowed") is True
        ),
        "state_consistency_risk_classified": (
            r1_concurrent.get("state_consistency_risk_classified") is True
        ),
        "silent_persistent_to_ephemeral_fallback_allowed": (
            r2_no_fallback.get("silent_persistent_to_ephemeral_fallback_allowed") is True
        ),
        "fallback_rejected": r2_no_fallback.get("fallback_rejected") is True,
        "counts_as_daily_reliability_proof": False,
    }

    integration_ok = (
        r2b_integration.get("status") == "ok"
        and r1_original.get("status") == "ok"
        and r2b_integration.get("integration_parity_claimed") is False
        and r2b_integration.get("original_codex_integration_state_runtime_dependency")
        is False
        and r1_original.get("original_codex_profile_dependency") is False
        and r1_original.get("original_codex_profile_used_as_custom_shortcut") is False
    )
    packets["integration_ownership_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "integration_ownership_import",
        "status": "ok" if integration_ok else "blocked",
        "source_packets": [
            str(source_dirs["r2b_live"] / "integration_ownership_baseline_packet.json"),
            str(
                source_dirs["r1_contract"]
                / "original_codex_profile_non_dependency_packet.json"
            ),
        ],
        "classification_scope": r2b_integration.get("classification_scope", ""),
        "integration_classes": r2b_integration.get("integration_classes", []),
        "integration_persistence_proven": (
            r2b_integration.get("integration_persistence_proven") is True
        ),
        "integration_parity_claimed": (
            r2b_integration.get("integration_parity_claimed") is True
        ),
        "original_codex_integration_state_runtime_dependency": (
            r2b_integration.get("original_codex_integration_state_runtime_dependency")
            is True
        ),
        "counts_as_original_integration_parity_proof": False,
    }

    drift_classified = (
        r1_original.get("status") == "ok"
        and r1_original.get("original_codex_profile_dependency") is False
        and r1_original.get("original_codex_profile_used_as_custom_shortcut") is False
        and r1_original.get("original_codex_profile_mutated") is False
        and r2b_original_drift.get("status") in {"ok", "blocked"}
        and r2b_original_drift.get("original_codex_write_performed_by_contour") is False
    )
    packets["original_codex_profile_drift_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "original_codex_profile_drift_import",
        "status": "ok" if drift_classified else "blocked",
        "source_packets": [
            str(
                source_dirs["r1_contract"]
                / "original_codex_profile_non_dependency_packet.json"
            ),
            str(source_dirs["r2b_live"] / "original_codex_profile_drift_packet.json"),
        ],
        "original_codex_profile_dependency": (
            r1_original.get("original_codex_profile_dependency") is True
        ),
        "original_codex_profile_used_as_custom_shortcut": (
            r1_original.get("original_codex_profile_used_as_custom_shortcut") is True
        ),
        "original_codex_profile_mutated": (
            r1_original.get("original_codex_profile_mutated") is True
        ),
        "declared_observed_surface_drift_clean": (
            r2b_original_drift.get("all_protected_surfaces_unchanged") is True
        ),
        "declared_observed_surface_drift_classified": True,
        "drift_reason_class": r2b_original_drift.get("reason_class", ""),
        "original_codex_write_performed_by_contour": (
            r2b_original_drift.get("original_codex_write_performed_by_contour") is True
        ),
        "counts_as_broad_original_innocence_proof": False,
    }

    cleanup_policy_ok = (
        r1_cleanup.get("status") == "ok"
        and r2b_cleanup.get("status") == "ok"
        and r1_cleanup.get("persistent_history_delete_allowed_by_default") is False
        and r1_cleanup.get("ordinary_cleanup_must_preserve_history") is True
        and r2b_cleanup.get("cleanup_deletes_persistent_profile_by_default") is False
    )
    packets["persistent_cleanup_policy_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_cleanup_policy_import",
        "status": "ok" if cleanup_policy_ok else "blocked",
        "source_packets": [
            str(
                source_dirs["r1_contract"]
                / "persistent_cleanup_retention_policy_packet.json"
            ),
            str(source_dirs["r2b_live"] / "persistent_cleanup_policy_packet.json"),
        ],
        "persistent_history_delete_allowed_by_default": (
            r1_cleanup.get("persistent_history_delete_allowed_by_default") is True
        ),
        "ordinary_cleanup_must_preserve_history": (
            r1_cleanup.get("ordinary_cleanup_must_preserve_history") is True
        ),
        "explicit_owner_delete_authorization_required": (
            r1_cleanup.get("explicit_owner_delete_authorization_required") is True
        ),
        "cleanup_deletes_persistent_profile_by_default": (
            r2b_cleanup.get("cleanup_deletes_persistent_profile_by_default") is True
        ),
        "profile_exists_after_cleanup": r2b_cleanup.get("profile_exists_after_cleanup"),
        "counts_as_cleanup_execution": False,
    }

    continuity_classifiable = (
        packets["persistent_source_reference_inventory_packet.json"]["status"] == "ok"
        and packets["persistent_source_reference_validation_packet.json"]["status"] == "ok"
        and packets["persistent_custom_profile_contract_packet.json"]["status"] == "ok"
        and packets["persistent_custom_profile_identity_packet.json"]["status"] == "ok"
        and packets["persistent_custom_profile_before_snapshot.json"]["status"] == "ok"
        and packets["persistent_custom_profile_after_event_snapshot.json"]["status"] == "ok"
        and packets["persistent_custom_profile_relaunch_snapshot.json"]["status"] == "ok"
        and packets["thread_history_preservation_packet.json"]["status"] == "ok"
        and packets["concurrent_launch_policy_packet.json"]["status"] == "ok"
        and packets["integration_ownership_packet.json"]["status"] == "ok"
        and packets["original_codex_profile_drift_packet.json"]["status"] == "ok"
        and packets["persistent_cleanup_policy_packet.json"]["status"] == "ok"
    )
    full_pass = (
        continuity_classifiable
        and packets["thread_history_preservation_packet.json"][
            "profile_state_preservation_proven"
        ]
        is True
        and packets["thread_history_preservation_packet.json"]["thread_history_preserved"]
        is True
        and packets["thread_history_preservation_packet.json"][
            "storage_level_thread_history_proven"
        ]
        is True
        and packets["thread_history_preservation_packet.json"][
            "relaunch_restoration_source_proven"
        ]
        is True
        and packets["original_codex_profile_drift_packet.json"][
            "declared_observed_surface_drift_clean"
        ]
        is True
    )
    final_status = (
        "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED"
        if full_pass
        else "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_HISTORY_CLASSIFIED_WITH_LIMITS"
    )
    packets["persistent_profile_continuity_classification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_continuity_classification",
        "status": "ok" if continuity_classifiable else "blocked",
        "final_status": final_status,
        "bounded_persistent_profile_continuity_classified": continuity_classifiable,
        "persistent_profile_identity_proven": True if identity_ok else False,
        "owner_visible_thread_continuity_classified": (
            packets["thread_history_preservation_packet.json"][
                "owner_visible_thread_continuity_classified"
            ]
            is True
        ),
        "profile_state_preservation_proven": (
            packets["thread_history_preservation_packet.json"][
                "profile_state_preservation_proven"
            ]
            is True
        ),
        "thread_history_preserved": (
            packets["thread_history_preservation_packet.json"]["thread_history_preserved"]
            is True
        ),
        "storage_level_thread_history_proven": (
            packets["thread_history_preservation_packet.json"][
                "storage_level_thread_history_proven"
            ]
            is True
        ),
        "relaunch_restoration_source_proven": (
            packets["thread_history_preservation_packet.json"][
                "relaunch_restoration_source_proven"
            ]
            is True
        ),
        "selected_state_surfaces_only": True,
        "original_codex_profile_non_dependency_proven": (
            packets["original_codex_profile_drift_packet.json"][
                "original_codex_profile_dependency"
            ]
            is False
        ),
        "original_codex_declared_observed_surface_drift_clean": (
            packets["original_codex_profile_drift_packet.json"][
                "declared_observed_surface_drift_clean"
            ]
            is True
        ),
        "daily_reliability_proven": False,
        "integration_parity_proven": False,
        "route_proof_claimed": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "native_ux_acceptance_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
        "with_limits_required": not full_pass,
        "with_limits_reasons": with_limits_reasons
        + (
            ["ORIGINAL_DECLARED_OBSERVED_SURFACE_DRIFT_NOT_CLEAN"]
            if packets["original_codex_profile_drift_packet.json"][
                "declared_observed_surface_drift_clean"
            ]
            is not True
            else []
        ),
    }

    false_green_checks = [
        {
            "name": "no_route_proof_claim",
            "passed": packets["persistent_profile_continuity_classification_packet.json"][
                "route_proof_claimed"
            ]
            is False,
        },
        {
            "name": "no_direct_egress_absence_claim",
            "passed": packets["persistent_profile_continuity_classification_packet.json"][
                "direct_egress_absence_claimed"
            ]
            is False,
        },
        {
            "name": "no_model_availability_claim",
            "passed": packets["persistent_profile_continuity_classification_packet.json"][
                "model_availability_claimed"
            ]
            is False,
        },
        {
            "name": "no_native_ux_or_final_e2e_claim",
            "passed": packets["persistent_profile_continuity_classification_packet.json"][
                "native_ux_acceptance_claimed"
            ]
            is False
            and packets["persistent_profile_continuity_classification_packet.json"][
                "final_e2e_claimed"
            ]
            is False,
        },
        {
            "name": "owner_visible_thread_not_widened_to_storage_proof",
            "passed": packets["thread_history_preservation_packet.json"][
                "storage_level_thread_history_proven"
            ]
            is False,
        },
        {
            "name": "some_retained_state_not_widened_to_full_parity",
            "passed": packets["persistent_profile_continuity_classification_packet.json"][
                "daily_reliability_proven"
            ]
            is False
            and packets["persistent_profile_continuity_classification_packet.json"][
                "integration_parity_proven"
            ]
            is False,
        },
    ]
    packets["persistent_profile_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(
            check["passed"] for check in false_green_checks
        ),
        "current_owner_action_collected": False,
        "current_live_launch_attempted": False,
    }

    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok"
        if continuity_classifiable
        and packets["persistent_profile_false_green_audit.json"]["status"] == "ok"
        else "blocked",
        "top_level_packet_statuses": {
            name: packet.get("status", "missing") for name, packet in packets.items()
        },
        "ok_packet_count": sum(
            1 for packet in packets.values() if packet.get("status") == "ok"
        ),
        "blocked_packet_count": sum(
            1 for packet in packets.values() if packet.get("status") == "blocked"
        ),
        "final_status": final_status if continuity_classifiable else "",
    }

    packets["persistent_profile_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_profile_summary",
        "status": packets["persistent_profile_continuity_classification_packet.json"][
            "status"
        ],
        "final_status": final_status if continuity_classifiable else "",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "bounded_persistent_profile_continuity_classified": continuity_classifiable,
        "persistent_profile_identity_proven": identity_ok,
        "owner_visible_thread_continuity_classified": (
            packets["thread_history_preservation_packet.json"][
                "owner_visible_thread_continuity_classified"
            ]
            is True
        ),
        "profile_state_preservation_proven": (
            packets["thread_history_preservation_packet.json"][
                "profile_state_preservation_proven"
            ]
            is True
        ),
        "storage_level_thread_history_proven": (
            packets["thread_history_preservation_packet.json"][
                "storage_level_thread_history_proven"
            ]
            is True
        ),
        "relaunch_restoration_source_proven": (
            packets["thread_history_preservation_packet.json"][
                "relaunch_restoration_source_proven"
            ]
            is True
        ),
        "original_declared_observed_surface_drift_clean": (
            packets["original_codex_profile_drift_packet.json"][
                "declared_observed_surface_drift_clean"
            ]
            is True
        ),
        "with_limits_required": not full_pass,
        "route_proof_claimed": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "native_ux_acceptance_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_dirs = {
        "r1_contract": Path(args.r1_contract_dir).resolve(),
        "r2_enforcement": Path(args.r2_enforcement_dir).resolve(),
        "r2b_live": Path(args.r2b_live_dir).resolve(),
        "r2c_continuity": Path(args.r2c_continuity_dir).resolve(),
        "r3_storage": Path(args.r3_storage_dir).resolve(),
        "r4_schema": Path(args.r4_schema_dir).resolve(),
    }
    if not repo_root.exists():
        return _emit_input_error(
            reason_class="REPO_ROOT_MISSING",
            message=f"repo root does not exist: {repo_root}",
            evidence_dir=evidence_dir,
        )
    for label, source_dir in source_dirs.items():
        if not source_dir.exists():
            return _emit_input_error(
                reason_class="SOURCE_EVIDENCE_DIR_MISSING",
                message=f"{label} source evidence dir does not exist: {source_dir}",
                evidence_dir=evidence_dir,
            )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        source_dirs=source_dirs,
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    print(json.dumps(packets["persistent_profile_summary_packet.json"], indent=2, sort_keys=True))
    return (
        0
        if packets["persistent_profile_summary_packet.json"]["status"] == "ok"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
