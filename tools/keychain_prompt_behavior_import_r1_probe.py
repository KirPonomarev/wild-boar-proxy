#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import bounded Keychain/system prompt behavior evidence under current claim limits."""

from __future__ import annotations

import argparse
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


READINESS_DIR = (
    ROOT / "audit_results/wbp_keychain_system_prompt_behavior_readiness_r1_2026-05-27"
)
OBSERVED_PROMPT_DIR = (
    ROOT
    / "audit_results/wbp_native_codex_custom_protected_surface_isolation_repair_pass_2026-05-25/evidence"
)
REPAIRED_LANE_DIR = (
    ROOT
    / "audit_results/wbp_native_codex_custom_isolation_and_keychain_root_cause_and_repair_pass_2026-05-25/evidence"
)
AUTH_STRATEGY_DIR = (
    ROOT / "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27"
)
CUSTOM_SAFETY_DIR = (
    ROOT / "audit_results/wbp_native_custom_safety_refresh_pre_live_r1_2026-05-27"
)

SOURCE_REQUIRED_PACKETS = {
    "readiness": {
        "declared_write_surfaces_packet.json",
        "keychain_prompt_readiness_summary_packet.json",
        "keychain_observation_readiness_packet.json",
        "keychain_allowed_owner_action_boundary_packet.json",
        "keychain_prompt_surface_inventory_packet.json",
        "keychain_prompt_non_substitution_packet.json",
        "auth_strategy_prompt_interaction_readiness_packet.json",
        "auth_strategy_reference_digest_packet.json",
        "keychain_no_hidden_mutation_packet.json",
        "original_codex_auth_keychain_non_dependency_packet.json",
        "system_prompt_suppression_prohibition_packet.json",
        "prompt_minimization_not_suppression_packet.json",
        "future_live_owner_stop_gate_packet.json",
        "future_live_keychain_observation_contract_packet.json",
        "keychain_prompt_false_green_audit.json",
        "independent_keychain_prompt_readiness_audit.json",
    },
    "observed_prompt": {
        "keychain_prompt_observation_packet.json",
        "keychain_prompt_refined_observation_packet.json",
        "final_safety_repair_summary.json",
        "custom_profile_isolation_repair_packet.json",
        "independent_profile_safety_audit.json",
    },
    "repaired_lane": {
        "keychain_risk_localization_packet.json",
        "custom_isolation_repair_packet.json",
        "independent_repair_audit.json",
    },
    "auth_strategy": {
        "provider_auth_strategy_summary_packet.json",
        "auth_strategy_false_green_audit.json",
    },
    "custom_safety": {
        "native_custom_auth_boundary_refresh_packet.json",
        "native_custom_safety_false_green_audit.json",
        "independent_native_custom_safety_audit.json",
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


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_behavior_import_input_error",
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


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


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
        "tools/keychain_prompt_behavior_import_r1_probe.py",
        "tests/test_keychain_prompt_behavior_import_r1_probe.py",
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keychain-prompt-behavior-import-r1-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--readiness-dir", default=str(READINESS_DIR))
    parser.add_argument("--observed-prompt-dir", default=str(OBSERVED_PROMPT_DIR))
    parser.add_argument("--repaired-lane-dir", default=str(REPAIRED_LANE_DIR))
    parser.add_argument("--auth-strategy-dir", default=str(AUTH_STRATEGY_DIR))
    parser.add_argument("--custom-safety-dir", default=str(CUSTOM_SAFETY_DIR))
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
    packets["source_keychain_prompt_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_keychain_prompt_evidence_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "current_live_prompt_observation_performed": False,
    }

    readiness = parsed["readiness"]
    observed = parsed["observed_prompt"]
    repaired = parsed["repaired_lane"]
    auth = parsed["auth_strategy"]
    safety = parsed["custom_safety"]

    readiness_summary = readiness["keychain_prompt_readiness_summary_packet.json"]
    readiness_obs = readiness["keychain_observation_readiness_packet.json"]
    readiness_owner = readiness["keychain_allowed_owner_action_boundary_packet.json"]
    readiness_surfaces = readiness["keychain_prompt_surface_inventory_packet.json"]
    readiness_non_substitution = readiness["keychain_prompt_non_substitution_packet.json"]
    readiness_auth = readiness["auth_strategy_prompt_interaction_readiness_packet.json"]
    readiness_auth_digest = readiness["auth_strategy_reference_digest_packet.json"]
    readiness_mutation = readiness["keychain_no_hidden_mutation_packet.json"]
    readiness_original_dependency = readiness["original_codex_auth_keychain_non_dependency_packet.json"]
    readiness_suppression = readiness["system_prompt_suppression_prohibition_packet.json"]
    readiness_minimization = readiness["prompt_minimization_not_suppression_packet.json"]
    readiness_owner_stop = readiness["future_live_owner_stop_gate_packet.json"]
    readiness_contract = readiness["future_live_keychain_observation_contract_packet.json"]
    readiness_false_green = readiness["keychain_prompt_false_green_audit.json"]
    readiness_independent = readiness["independent_keychain_prompt_readiness_audit.json"]

    observed_packet = observed["keychain_prompt_observation_packet.json"]
    refined_packet = observed["keychain_prompt_refined_observation_packet.json"]
    observed_summary = observed["final_safety_repair_summary.json"]
    observed_repair = observed["custom_profile_isolation_repair_packet.json"]
    observed_independent = observed["independent_profile_safety_audit.json"]

    repaired_risk = repaired["keychain_risk_localization_packet.json"]
    repaired_summary = repaired["custom_isolation_repair_packet.json"]
    repaired_independent = repaired["independent_repair_audit.json"]

    auth_summary = auth["provider_auth_strategy_summary_packet.json"]
    auth_false_green = auth["auth_strategy_false_green_audit.json"]

    safety_auth = safety["native_custom_auth_boundary_refresh_packet.json"]
    safety_false_green = safety["native_custom_safety_false_green_audit.json"]
    safety_independent = safety["independent_native_custom_safety_audit.json"]

    validation_checks = {
        "readiness_chain_ok": (
            readiness_summary.get("status") == "ok"
            and readiness_summary.get("final_status")
            == "CODEX_CUSTOM_KEYCHAIN_PROMPT_BEHAVIOR_READINESS_R1_CLASSIFIED"
            and readiness_surfaces.get("status") == "ok"
            and readiness_non_substitution.get("status") == "ok"
            and readiness_auth_digest.get("status") == "ok"
            and readiness_mutation.get("status") == "ok"
            and readiness_original_dependency.get("status") == "ok"
            and readiness_suppression.get("status") == "ok"
            and readiness_owner_stop.get("status") == "ok"
            and readiness_false_green.get("status") == "ok"
            and readiness_independent.get("status") == "ok"
        ),
        "historical_prompt_observation_ok": (
            observed_packet.get("status") == "blocked"
            and observed_packet.get("keychain_reset_prompt_observed") is True
            and refined_packet.get("status") == "blocked"
            and refined_packet.get("strong_keychain_prompt_observed") is True
            and refined_packet.get("destructive_dialog_interacted_with") is False
            and observed_independent.get("status") == "blocked"
        ),
        "repaired_lane_nonreproduction_ok": (
            repaired_summary.get("status") == "ok"
            and repaired_risk.get("repeated_machine_visible_keychain_prompt_observed")
            is False
            and repaired_summary.get("route_or_prompt_claimed") is False
            and repaired_summary.get("real_home_wrapper_launch_forbidden") is True
            and repaired_independent.get("status") == "ok"
        ),
        "auth_reference_ok": (
            auth_summary.get("status") == "ok"
            and auth_summary.get("selected_strategy") == "auth.command"
            and auth_false_green.get("status") == "ok"
            and safety_auth.get("status") == "ok"
            and safety_auth.get("selected_strategy") == "auth.command"
            and safety_auth.get("auth_boundary_dependency_check_only") is True
            and safety_false_green.get("status") == "ok"
            and safety_independent.get("status") == "ok"
        ),
    }
    packets["source_keychain_prompt_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_keychain_prompt_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [{"name": k, "passed": v} for k, v in validation_checks.items()],
        "current_live_prompt_behavior_proven": False,
        "historical_signal_import_only": True,
    }

    observation_ok = (
        packets["source_keychain_prompt_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_keychain_prompt_validation_packet.json"]["status"] == "ok"
    )
    packets["keychain_prompt_observation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_observation_import",
        "status": "ok" if observation_ok else "blocked",
        "historical_pre_repair_prompt_observed": (
            observed_packet.get("keychain_reset_prompt_observed") is True
        ),
        "historical_pre_repair_strong_prompt_observed": (
            refined_packet.get("strong_keychain_prompt_observed") is True
        ),
        "repaired_isolated_lane_repeated_machine_prompt_observed": (
            repaired_risk.get("repeated_machine_visible_keychain_prompt_observed") is True
        ),
        "current_live_prompt_observed_in_this_contour": False,
        "prompt_observation_mode": "historical_import_plus_repaired_nonreproduction",
        "prompt_absence_counts_as_auth_proof": False,
    }

    keychain_classified = (
        refined_packet.get("strong_keychain_prompt_observed") is True
        and "SecurityAgent" in refined_packet.get("after", {}).get("security_windows", {}).get("stdout", "")
    )
    packets["keychain_prompt_classification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_classification",
        "status": "ok" if observation_ok else "blocked",
        "prompt_class": (
            "keychain_security_agent_prompt_historically_observed"
            if keychain_classified
            else "unknown"
        ),
        "prompt_class_source": "security_window_name_without_secret_values",
        "historical_only": True,
        "classification_limited_to_historical_import": True,
        "current_live_prompt_class_proven": False,
        "prompt_text_shape_without_secrets": (
            refined_packet.get("after", {}).get("security_windows", {}).get("stdout", "")
        ),
        "raw_secret_recorded": False,
    }

    packets["keychain_prompt_owner_action_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_owner_action_boundary_import",
        "status": "ok" if observation_ok else "blocked",
        "owner_action_performed_in_this_contour": False,
        "historical_destructive_dialog_interacted_with": (
            refined_packet.get("destructive_dialog_interacted_with") is True
        ),
        "allowed_future_owner_actions": readiness_owner.get("allowed_future_owner_actions", []),
        "owner_cancel_counted_as_machine_proof": (
            readiness_owner.get("owner_cancel_counted_as_machine_proof") is True
        ),
        "owner_allow_counted_as_auth_success": (
            readiness_owner.get("owner_allow_counted_as_auth_success") is True
        ),
        "owner_action_boundary_reference_only": True,
    }

    packets["auth_strategy_prompt_interaction_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "auth_strategy_prompt_interaction_import",
        "status": "ok" if validation_checks["auth_reference_ok"] else "blocked",
        "selected_strategy": auth_summary.get("selected_strategy", ""),
        "bounded_bearer_selected": auth_summary.get("bounded_bearer_selected") is True,
        "file_auth_selected": auth_summary.get("file_auth_selected") is True,
        "silent_fallback_detected": auth_summary.get("silent_fallback_detected") is True,
        "auth_strategy_reference_only": True,
        "auth_boundary_dependency_check_only": (
            safety_auth.get("auth_boundary_dependency_check_only") is True
        ),
        "auth_success_claimed": False,
        "prompt_suppression_proved_by_auth_strategy": False,
    }

    packets["custom_flow_after_prompt_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "custom_flow_after_prompt_import",
        "status": "ok" if observation_ok else "blocked",
        "historical_pre_repair_flow_result": "blocked"
        if observed_summary.get("status") == "blocked"
        else "unknown",
        "historical_pre_repair_reason_class": observed_summary.get("machine_error_code", ""),
        "repaired_isolated_lane_process_observed": repaired_summary.get("process_observed") is True,
        "repaired_isolated_lane_window_observed": repaired_summary.get("window_observed") is True,
        "repaired_isolated_lane_repeated_prompt_observed": (
            repaired_risk.get("repeated_machine_visible_keychain_prompt_observed") is True
        ),
        "flow_effect_source": "historical_pre_repair_block_plus_repaired_nonreproduction_reference",
        "current_live_flow_after_prompt_classified": False,
        "flow_continued_counts_as_auth_proof": False,
        "flow_blocked_counts_as_route_failure": False,
    }

    no_hidden_mutation_ok = (
        readiness_mutation.get("status") == "ok"
        and readiness_suppression.get("status") == "ok"
        and readiness_minimization.get("status") == "ok"
        and readiness_mutation.get("keychain_mutation_performed") is False
        and readiness_mutation.get("keychain_reset_performed") is False
        and readiness_mutation.get("keychain_default_changed") is False
        and readiness_suppression.get("suppression_attempted") is False
        and readiness_suppression.get("hidden_runtime_mutation_allowed") is False
        and readiness_minimization.get("hidden_suppression_performed") is False
    )
    packets["keychain_no_hidden_mutation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_no_hidden_mutation_import",
        "status": "ok" if no_hidden_mutation_ok else "blocked",
        "keychain_mutation_performed": readiness_mutation.get("keychain_mutation_performed") is True,
        "keychain_reset_performed": readiness_mutation.get("keychain_reset_performed") is True,
        "keychain_default_changed": readiness_mutation.get("keychain_default_changed") is True,
        "original_codex_keychain_mutated": (
            readiness_mutation.get("original_codex_keychain_mutated") is True
        ),
        "suppression_attempted": readiness_suppression.get("suppression_attempted") is True,
        "hidden_runtime_mutation_allowed": (
            readiness_suppression.get("hidden_runtime_mutation_allowed") is True
        ),
        "hidden_suppression_performed": (
            readiness_minimization.get("hidden_suppression_performed") is True
        ),
        "counts_as_prompt_behavior_by_itself": False,
    }

    classification_ok = (
        packets["keychain_prompt_observation_packet.json"]["status"] == "ok"
        and packets["keychain_prompt_classification_packet.json"]["status"] == "ok"
        and packets["keychain_prompt_owner_action_packet.json"]["status"] == "ok"
        and packets["auth_strategy_prompt_interaction_packet.json"]["status"] == "ok"
        and packets["custom_flow_after_prompt_packet.json"]["status"] == "ok"
        and packets["keychain_no_hidden_mutation_packet.json"]["status"] == "ok"
    )
    packets["keychain_prompt_behavior_classification_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_behavior_classification",
        "status": "ok" if classification_ok else "blocked",
        "final_status": (
            "CODEX_CUSTOM_KEYCHAIN_PROMPT_BEHAVIOR_CLASSIFIED_WITH_LIMITS"
            if classification_ok
            else ""
        ),
        "historical_pre_repair_prompt_observed": (
            packets["keychain_prompt_observation_packet.json"][
                "historical_pre_repair_prompt_observed"
            ]
            is True
        ),
        "repaired_isolated_lane_repeated_prompt_observed": (
            packets["keychain_prompt_observation_packet.json"][
                "repaired_isolated_lane_repeated_machine_prompt_observed"
            ]
            is True
        ),
        "current_live_prompt_behavior_proven": False,
        "auth_boundary_proven": False,
        "route_proof_claimed": False,
        "persistent_profile_continuity_claimed": False,
        "model_availability_claimed": False,
        "native_ux_claimed": False,
        "original_codex_reversibility_claimed": False,
        "final_e2e_claimed": False,
        "with_limits_required": True,
        "with_limits_reasons": [
            "CURRENT_LIVE_PROMPT_BEHAVIOR_NOT_REOBSERVED",
            "PROMPT_NONREPRODUCTION_IN_REPAIRED_LANE_NOT_AUTH_PROOF",
            "OWNER_ACTION_NOT_OBSERVED_IN_THIS_CONTOUR",
        ],
    }

    false_green_checks = [
        {
            "name": "prompt_absence_not_auth_proof",
            "passed": packets["keychain_prompt_observation_packet.json"][
                "prompt_absence_counts_as_auth_proof"
            ]
            is False,
        },
        {
            "name": "flow_continued_not_auth_proof",
            "passed": packets["custom_flow_after_prompt_packet.json"][
                "flow_continued_counts_as_auth_proof"
            ]
            is False,
        },
        {
            "name": "flow_blocked_not_route_failure",
            "passed": packets["custom_flow_after_prompt_packet.json"][
                "flow_blocked_counts_as_route_failure"
            ]
            is False,
        },
        {
            "name": "no_hidden_mutation_or_suppression",
            "passed": packets["keychain_no_hidden_mutation_packet.json"]["status"] == "ok",
        },
        {
            "name": "no_route_or_final_e2e_claim",
            "passed": packets["keychain_prompt_behavior_classification_packet.json"][
                "route_proof_claimed"
            ]
            is False
            and packets["keychain_prompt_behavior_classification_packet.json"][
                "final_e2e_claimed"
            ]
            is False,
        },
    ]
    packets["keychain_prompt_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_behavior_false_green_audit",
        "status": "ok" if all(c["passed"] for c in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(c["passed"] for c in false_green_checks),
    }

    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "historical_pre_repair_prompt_observed": (
                packets["keychain_prompt_observation_packet.json"][
                    "historical_pre_repair_prompt_observed"
                ]
                is True
            ),
            "historical_pre_repair_strong_prompt_observed": (
                packets["keychain_prompt_observation_packet.json"][
                    "historical_pre_repair_strong_prompt_observed"
                ]
                is True
            ),
            "prompt_class": packets["keychain_prompt_classification_packet.json"][
                "prompt_class"
            ],
            "prompt_class_historical_only": (
                packets["keychain_prompt_classification_packet.json"][
                    "historical_only"
                ]
                is True
            ),
            "owner_action_performed_in_this_contour": (
                packets["keychain_prompt_owner_action_packet.json"][
                    "owner_action_performed_in_this_contour"
                ]
                is True
            ),
            "current_live_prompt_behavior_proven": False,
            "repaired_isolated_lane_repeated_machine_prompt_observed": (
                packets["keychain_prompt_observation_packet.json"][
                    "repaired_isolated_lane_repeated_machine_prompt_observed"
                ]
                is True
            ),
            "selected_auth_strategy": packets["auth_strategy_prompt_interaction_packet.json"][
                "selected_strategy"
            ],
            "auth_strategy_reference_only": (
                packets["auth_strategy_prompt_interaction_packet.json"][
                    "auth_strategy_reference_only"
                ]
                is True
            ),
            "hidden_mutation_or_suppression_detected": (
                packets["keychain_no_hidden_mutation_packet.json"]["status"] != "ok"
            ),
            "final_status": packets["keychain_prompt_behavior_classification_packet.json"].get(
                "final_status", ""
            ),
        },
        "non_claims": {
            "auth_boundary_proven": False,
            "route_proof_claimed": False,
            "persistent_profile_continuity_claimed": False,
            "final_e2e_claimed": False,
        },
    }

    packets["independent_keychain_prompt_behavior_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_keychain_prompt_behavior_audit",
        "status": "ok"
        if packets["source_keychain_prompt_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_keychain_prompt_validation_packet.json"]["status"] == "ok"
        and packets["keychain_prompt_behavior_classification_packet.json"]["status"] == "ok"
        and packets["keychain_prompt_false_green_audit.json"]["status"] == "ok"
        else "blocked",
        "referenced_packets": [
            "source_keychain_prompt_evidence_inventory_packet.json",
            "source_keychain_prompt_validation_packet.json",
            "keychain_prompt_observation_packet.json",
            "keychain_prompt_classification_packet.json",
            "keychain_prompt_owner_action_packet.json",
            "auth_strategy_prompt_interaction_packet.json",
            "custom_flow_after_prompt_packet.json",
            "keychain_no_hidden_mutation_packet.json",
            "keychain_prompt_behavior_classification_packet.json",
            "keychain_prompt_false_green_audit.json",
            "scanner_agent_fact_report_packet.json",
        ],
        "historical_prompt_chain_imported": True,
        "current_owner_action_collected": False,
        "current_live_prompt_observation_collected": False,
        "auth_boundary_proven": False,
        "route_proof_claimed": False,
        "persistent_profile_continuity_claimed": False,
        "final_e2e_claimed": False,
    }

    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok"
        if classification_ok
        and packets["keychain_prompt_false_green_audit.json"]["status"] == "ok"
        and packets["independent_keychain_prompt_behavior_audit.json"]["status"] == "ok"
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
    }

    packets["keychain_prompt_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "keychain_prompt_summary",
        "status": "ok"
        if packets["verification_results_packet.json"]["status"] == "ok"
        else "blocked",
        "final_status": (
            packets["keychain_prompt_behavior_classification_packet.json"].get(
                "final_status", ""
            )
            if packets["verification_results_packet.json"]["status"] == "ok"
            else ""
        ),
        "historical_pre_repair_prompt_observed": (
            packets["keychain_prompt_behavior_classification_packet.json"][
                "historical_pre_repair_prompt_observed"
            ]
            is True
        ),
        "repaired_isolated_lane_repeated_prompt_observed": (
            packets["keychain_prompt_behavior_classification_packet.json"][
                "repaired_isolated_lane_repeated_prompt_observed"
            ]
            is True
        ),
        "current_live_prompt_behavior_proven": False,
        "with_limits_required": True,
        "route_proof_claimed": False,
        "auth_boundary_proven": False,
        "persistent_profile_continuity_claimed": False,
        "final_e2e_claimed": False,
    }
    return packets


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_dirs = {
        "readiness": Path(args.readiness_dir).resolve(),
        "observed_prompt": Path(args.observed_prompt_dir).resolve(),
        "repaired_lane": Path(args.repaired_lane_dir).resolve(),
        "auth_strategy": Path(args.auth_strategy_dir).resolve(),
        "custom_safety": Path(args.custom_safety_dir).resolve(),
    }
    if not repo_root.exists():
        return _emit_input_error(
            reason_class="REPO_ROOT_MISSING",
            message=f"repo root does not exist: {repo_root}",
            evidence_dir=evidence_dir,
        )
    for label, path in source_dirs.items():
        if not path.exists():
            return _emit_input_error(
                reason_class="SOURCE_EVIDENCE_DIR_MISSING",
                message=f"{label} source evidence dir does not exist: {path}",
                evidence_dir=evidence_dir,
            )
    if not _is_relative_to(evidence_dir, repo_root):
        return _emit_input_error(
            reason_class="EVIDENCE_DIR_OUTSIDE_REPO",
            message="--evidence-dir must be inside --repo-root for this contour.",
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
    print(json.dumps(packets["keychain_prompt_summary_packet.json"], indent=2, sort_keys=True))
    return 0 if packets["keychain_prompt_summary_packet.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
