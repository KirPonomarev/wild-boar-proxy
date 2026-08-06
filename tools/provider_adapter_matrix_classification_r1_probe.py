#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify the optional multi-provider adapter matrix under current limits."""

from __future__ import annotations

import argparse
import ast
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


AUTH_STRATEGY_DIR = ROOT / "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27"
RUNTIME_COMPAT_DIR = ROOT / "audit_results/wbp_responses_runtime_compatibility_r1_2026-05-26"
LIVE_NON_NATIVE_DIR = (
    ROOT / "audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27"
)
MODEL_AVAILABILITY_DIR = ROOT / "audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27"
DEEPSEEK_DIR = ROOT / "audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23"
OPENROUTER_DIR = ROOT / "audit_results/legacy_api_routes_and_provider_proof_pass_2026-05-23"

SOURCE_REQUIRED_PACKETS = {
    "auth_strategy": {
        "provider_auth_source_inventory_packet.json",
        "provider_auth_precedence_contract_packet.json",
        "provider_auth_fallback_matrix_packet.json",
        "provider_auth_strategy_summary_packet.json",
        "auth_strategy_false_green_audit.json",
    },
    "runtime_compat": {
        "adapter_boundary_packet.json",
        "responses_runtime_compatibility_matrix.json",
        "responses_runtime_false_green_audit.json",
    },
    "live_non_native": {
        "responses_live_non_native_summary_packet.json",
        "failure_taxonomy_packet.json",
        "failure_semantics_packet.json",
        "responses_live_non_native_false_green_audit.json",
    },
    "model_availability": {
        "external_route_admission_packet.json",
        "route_family_classification_packet.json",
        "model_availability_admission_packet.json",
        "model_availability_false_green_audit.json",
    },
    "deepseek": {
        "proof.json",
        "independent_audit.json",
        "redaction_audit.json",
    },
    "openrouter": {
        "credential_admission_proof.json",
        "provider_check_proof.json",
        "route_restore_proof.json",
        "independent_audit.json",
        "redaction_audit.json",
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


def _status_in(packet: dict[str, Any], *allowed: str) -> bool:
    return str(packet.get("status", "")) in set(allowed)


def _emit_input_error(
    *,
    reason_class: str,
    message: str,
    evidence_dir: Path | None = None,
) -> int:
    packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_adapter_matrix_input_error",
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
        "tools/provider_adapter_matrix_classification_r1_probe.py",
        "tests/test_provider_adapter_matrix_classification_r1_probe.py",
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
    parser = argparse.ArgumentParser(prog="provider-adapter-matrix-classification-r1-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--auth-strategy-dir", default=str(AUTH_STRATEGY_DIR))
    parser.add_argument("--runtime-compat-dir", default=str(RUNTIME_COMPAT_DIR))
    parser.add_argument("--live-non-native-dir", default=str(LIVE_NON_NATIVE_DIR))
    parser.add_argument("--model-availability-dir", default=str(MODEL_AVAILABILITY_DIR))
    parser.add_argument("--deepseek-dir", default=str(DEEPSEEK_DIR))
    parser.add_argument("--openrouter-dir", default=str(OPENROUTER_DIR))
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


def _credential_provider_inventory(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "wild_boar_proxy" / "external_models" / "credentials.py"
    if not path.exists():
        return {
            "status": "blocked",
            "provider_families": [],
            "source_path": str(path),
            "error": "credential_provider_spec_missing",
        }
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return {
            "status": "blocked",
            "provider_families": [],
            "source_path": str(path),
            "error": f"credential_provider_spec_parse_failed:{exc.__class__.__name__}",
        }

    provider_families: list[str] = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            target_matches = any(
                isinstance(target, ast.Name) and target.id == "_PROVIDER_SPECS"
                for target in node.targets
            )
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target_matches = (
                isinstance(node.target, ast.Name) and node.target.id == "_PROVIDER_SPECS"
            )
            value = node.value
        else:
            continue
        if not target_matches or not isinstance(value, ast.Dict):
            continue
        for key in value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                provider_families.append(key.value)
        break

    return {
        "status": "ok" if provider_families else "blocked",
        "provider_families": sorted(provider_families),
        "source_path": str(path),
        "provider_count": len(provider_families),
    }


def _family_row(
    family: str,
    *,
    auth_summary: dict[str, Any],
    auth_fallback: dict[str, Any],
    runtime_adapter: dict[str, Any],
    runtime_matrix: dict[str, Any],
    live_summary: dict[str, Any],
    failure_taxonomy: dict[str, Any],
    failure_semantics: dict[str, Any],
    deepseek_proof: dict[str, Any],
    openrouter_credential: dict[str, Any],
    openrouter_provider_check: dict[str, Any],
    openrouter_restore: dict[str, Any],
) -> dict[str, Any]:
    base_row = {
        "provider_family": family,
        "adapter_present": True,
        "auth_strategy_classified": auth_summary.get("status") == "ok",
        "selected_auth_strategy": auth_summary.get("selected_strategy", ""),
        "silent_fallback_forbidden": auth_fallback.get("silent_fallback_detected") is False,
        "generic_request_shape_classified": live_summary.get("status") == "ok",
        "generic_response_shape_classified": live_summary.get("status") == "ok",
        "generic_failure_semantics_classified": (
            failure_taxonomy.get("status") == "ok"
            and failure_semantics.get("status") == "ok"
        ),
        "generic_runtime_harness_proves_provider_family_compatibility": (
            runtime_adapter.get("generic_runtime_harness_proves_provider_family_compatibility")
        ),
        "provider_family_compatibility_proven": False,
        "family_wide_model_proof": False,
        "limits": [],
    }

    if family == "deepseek":
        route_truth = deepseek_proof.get("route_truth", {})
        direct_probe = deepseek_proof.get("direct_provider_probe", {})
        command_proof = deepseek_proof.get("command_proof", {})
        representative_models = [
            value
            for value in [
                route_truth.get("upstream_model", ""),
                direct_probe.get("model", ""),
            ]
            if value
        ]
        base_row.update(
            {
                "representative_models": representative_models,
                "representative_model_scope_explicit": bool(representative_models),
                "provider_specific_route_observed": route_truth.get("provider") == "deepseek",
                "provider_specific_credential_present": (
                    deepseek_proof.get("credential_truth", {}).get("credential_present") is True
                ),
                "provider_specific_http_200_seen": (
                    direct_probe.get("status") == "ok"
                    and direct_probe.get("http_status") == 200
                ),
                "provider_specific_validate_passed": (
                    command_proof.get("check_status") == "ok"
                ),
                "matrix_proof_level": "classified",
            }
        )
        base_row["limits"].extend(
            [
                "REPRESENTATIVE_MODEL_ONLY",
                "FAMILY_WIDE_COMPATIBILITY_NOT_PROVEN",
                "GENERIC_RUNTIME_AND_LIVE_PACKETS_EXPLICITLY_DO_NOT_PROVE_PROVIDER_FAMILY_COMPATIBILITY",
            ]
        )
        return base_row

    route_target = openrouter_restore.get("canonical_route_target", {})
    representative_models = [
        value
        for value in [
            route_target.get("upstream_model", ""),
        ]
        if value
    ]
    credential_result = openrouter_credential.get("credential_result", {})
    base_row.update(
        {
            "representative_models": representative_models,
            "representative_model_scope_explicit": bool(representative_models),
            "provider_specific_route_observed": route_target.get("provider") == "openrouter",
            "provider_specific_credential_present": credential_result.get("credential_present")
            is True,
            "provider_specific_provider_check_ran": openrouter_provider_check.get("status")
            not in {"not_run", ""},
            "provider_specific_provider_check_ready": (
                openrouter_provider_check.get("status") == "not_run"
                and openrouter_provider_check.get("provider") == "openrouter"
            )
            or route_target.get("provider") == "openrouter",
            "matrix_proof_level": "declared",
        }
    )
    base_row["limits"].extend(
        [
            "OWNER_CREDENTIAL_MISSING",
            "OPENROUTER_PROVIDER_CHECK_NOT_RUN",
            "REPRESENTATIVE_MODEL_ONLY",
            "FAMILY_WIDE_COMPATIBILITY_NOT_PROVEN",
            "GENERIC_RUNTIME_AND_LIVE_PACKETS_EXPLICITLY_DO_NOT_PROVE_PROVIDER_FAMILY_COMPATIBILITY",
        ]
    )
    return base_row


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_dirs: dict[str, Path],
) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    parsed, missing, invalid = _load_sources(source_dirs)
    provider_inventory = _credential_provider_inventory(repo_root)

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
    packets["source_provider_adapter_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_provider_adapter_evidence_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "current_live_multi_provider_run_performed": False,
    }

    auth = parsed["auth_strategy"]
    runtime = parsed["runtime_compat"]
    live = parsed["live_non_native"]
    availability = parsed["model_availability"]
    deepseek = parsed["deepseek"]
    openrouter = parsed["openrouter"]

    auth_inventory = auth["provider_auth_source_inventory_packet.json"]
    auth_precedence = auth["provider_auth_precedence_contract_packet.json"]
    auth_fallback = auth["provider_auth_fallback_matrix_packet.json"]
    auth_summary = auth["provider_auth_strategy_summary_packet.json"]
    auth_false_green = auth["auth_strategy_false_green_audit.json"]

    runtime_adapter = runtime["adapter_boundary_packet.json"]
    runtime_matrix = runtime["responses_runtime_compatibility_matrix.json"]
    runtime_false_green = runtime["responses_runtime_false_green_audit.json"]

    live_summary = live["responses_live_non_native_summary_packet.json"]
    failure_taxonomy = live["failure_taxonomy_packet.json"]
    failure_semantics = live["failure_semantics_packet.json"]
    live_false_green = live["responses_live_non_native_false_green_audit.json"]

    external_route_admission = availability["external_route_admission_packet.json"]
    route_family_classification = availability["route_family_classification_packet.json"]
    model_admission = availability["model_availability_admission_packet.json"]
    model_false_green = availability["model_availability_false_green_audit.json"]

    deepseek_proof = deepseek["proof.json"]
    deepseek_independent = deepseek["independent_audit.json"]
    deepseek_redaction = deepseek["redaction_audit.json"]

    openrouter_credential = openrouter["credential_admission_proof.json"]
    openrouter_provider_check = openrouter["provider_check_proof.json"]
    openrouter_restore = openrouter["route_restore_proof.json"]
    openrouter_independent = openrouter["independent_audit.json"]
    openrouter_redaction = openrouter["redaction_audit.json"]

    validation_checks = {
        "provider_inventory_multi_family": (
            provider_inventory.get("status") == "ok"
            and provider_inventory.get("provider_count", 0) > 1
        ),
        "auth_strategy_contract_ok": (
            auth_inventory.get("status") == "ok"
            and auth_inventory.get("all_auth_sources_classified") is True
            and auth_precedence.get("status") == "ok"
            and auth_precedence.get("selected_strategy") == "auth.command"
            and auth_precedence.get("silent_fallback_allowed") is False
            and auth_fallback.get("status") == "ok"
            and auth_fallback.get("silent_fallback_detected") is False
            and auth_summary.get("status") == "ok"
            and auth_summary.get("selected_strategy") == "auth.command"
            and auth_false_green.get("status") == "ok"
        ),
        "runtime_generic_limits_ok": (
            runtime_adapter.get("status") == "ok"
            and runtime_adapter.get("generic_runtime_harness_proves_provider_family_compatibility")
            is False
            and runtime_matrix.get("status") == "ok"
            and runtime_false_green.get("status") == "ok"
            and live_summary.get("status") == "ok"
            and live_summary.get("provider_family_compatibility_proven") is False
            and failure_taxonomy.get("status") == "ok"
            and failure_taxonomy.get("failure_taxonomy_counts_as_provider_family_compatibility")
            is False
            and failure_semantics.get("status") == "ok"
            and live_false_green.get("status") == "ok"
        ),
        "model_availability_external_route_limits_ok": (
            external_route_admission.get("status") == "ok"
            and external_route_admission.get("provider_family_compatibility_claimed") is False
            and external_route_admission.get(
                "external_route_smoke_claims_provider_family_compatibility"
            )
            is False
            and route_family_classification.get("status") == "ok"
            and model_admission.get("status") == "ok"
            and model_false_green.get("status") == "ok"
        ),
        "deepseek_reference_ok": (
            _status_in(deepseek_proof, "ok")
            and deepseek_proof.get("route_truth", {}).get("provider") == "deepseek"
            and deepseek_proof.get("credential_truth", {}).get("credential_present") is True
            and deepseek_proof.get("direct_provider_probe", {}).get("status") == "ok"
            and deepseek_proof.get("direct_provider_probe", {}).get("http_status") == 200
            and _status_in(deepseek_independent, "pass", "ok")
            and _status_in(deepseek_redaction, "pass", "ok")
        ),
        "openrouter_reference_ok": (
            _status_in(openrouter_credential, "error")
            and openrouter_credential.get("credential_result", {}).get("provider")
            == "openrouter"
            and openrouter_credential.get("credential_result", {}).get("credential_present")
            is False
            and _status_in(openrouter_provider_check, "not_run")
            and openrouter_provider_check.get("provider") == "openrouter"
            and _status_in(openrouter_restore, "not_attempted")
            and openrouter_restore.get("canonical_route_target", {}).get("provider")
            == "openrouter"
            and _status_in(
                openrouter_independent,
                "pass",
                "ok",
                "clean_blocked_waiting_for_valid_provider_key",
            )
            and _status_in(openrouter_redaction, "pass", "ok")
        ),
    }
    packets["source_provider_adapter_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_provider_adapter_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [
            {"name": name, "passed": passed}
            for name, passed in validation_checks.items()
        ],
        "validation_scope": "optional_multi_provider_adapter_matrix_only",
        "source_chain_counts_as_native_reproof": False,
        "source_chain_counts_as_final_e2e_reproof": False,
    }

    provider_families = provider_inventory.get("provider_families", [])
    scope_ok = (
        packets["source_provider_adapter_evidence_inventory_packet.json"]["status"] == "ok"
        and validation_checks["provider_inventory_multi_family"]
    )
    packets["provider_adapter_scope_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_adapter_scope",
        "status": "ok" if scope_ok else "blocked",
        "active_provider_families": provider_families,
        "active_provider_family_count": len(provider_families),
        "multi_provider_scope_admitted": len(provider_families) > 1,
        "scope_source": "credential_provider_spec_inventory",
        "optional_annex_scope_only": True,
        "native_or_final_e2e_claimed": False,
    }

    representative_scope_rows = []
    family_rows = []
    auth_rows = []
    request_rows = []
    response_rows = []
    failure_rows = []
    for family in provider_families:
        row = _family_row(
            family,
            auth_summary=auth_summary,
            auth_fallback=auth_fallback,
            runtime_adapter=runtime_adapter,
            runtime_matrix=runtime_matrix,
            live_summary=live_summary,
            failure_taxonomy=failure_taxonomy,
            failure_semantics=failure_semantics,
            deepseek_proof=deepseek_proof,
            openrouter_credential=openrouter_credential,
            openrouter_provider_check=openrouter_provider_check,
            openrouter_restore=openrouter_restore,
        )
        family_rows.append(row)
        representative_scope_rows.append(
            {
                "provider_family": family,
                "representative_models": row["representative_models"],
                "representative_model_scope_explicit": row[
                    "representative_model_scope_explicit"
                ],
                "family_wide_proof": False,
            }
        )
        auth_rows.append(
            {
                "provider_family": family,
                "selected_strategy": auth_summary.get("selected_strategy", ""),
                "auth_sources_classified": auth_inventory.get("all_auth_sources_classified")
                is True,
                "silent_fallback_forbidden": auth_fallback.get("silent_fallback_detected")
                is False,
                "provider_specific_credential_present": row[
                    "provider_specific_credential_present"
                ],
                "provider_specific_runtime_usage_proven": False,
            }
        )
        request_rows.append(
            {
                "provider_family": family,
                "generic_request_shape_classified": row["generic_request_shape_classified"],
                "provider_specific_request_shape_proven": False,
                "request_shape_packet_family_wide_proof": False,
            }
        )
        response_rows.append(
            {
                "provider_family": family,
                "generic_response_shape_classified": row["generic_response_shape_classified"],
                "provider_specific_response_shape_proven": False,
                "response_shape_packet_family_wide_proof": False,
            }
        )
        failure_rows.append(
            {
                "provider_family": family,
                "generic_failure_semantics_classified": row[
                    "generic_failure_semantics_classified"
                ],
                "provider_specific_failure_semantics_proven": False,
                "failure_taxonomy_counts_as_provider_family_compatibility": False,
            }
        )

    packets["provider_representative_model_scope_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_representative_model_scope",
        "status": "ok" if representative_scope_rows else "blocked",
        "rows": representative_scope_rows,
        "one_representative_model_counts_as_family_wide_proof": False,
    }
    packets["provider_auth_strategy_matrix_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_auth_strategy_matrix",
        "status": "ok" if auth_rows else "blocked",
        "rows": auth_rows,
        "auth_strategy_counts_as_runtime_family_proof": False,
    }
    packets["provider_request_shape_matrix_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_request_shape_matrix",
        "status": "ok" if request_rows else "blocked",
        "rows": request_rows,
        "request_shape_counts_as_family_wide_compatibility": False,
    }
    packets["provider_response_shape_matrix_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_response_shape_matrix",
        "status": "ok" if response_rows else "blocked",
        "rows": response_rows,
        "response_shape_counts_as_family_wide_compatibility": False,
    }
    packets["provider_failure_semantics_matrix_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_failure_semantics_matrix",
        "status": "ok" if failure_rows else "blocked",
        "rows": failure_rows,
        "failure_semantics_counts_as_family_wide_compatibility": False,
    }

    matrix_ok = (
        packets["provider_adapter_scope_packet.json"]["status"] == "ok"
        and packets["provider_representative_model_scope_packet.json"]["status"] == "ok"
        and packets["provider_auth_strategy_matrix_packet.json"]["status"] == "ok"
        and packets["provider_request_shape_matrix_packet.json"]["status"] == "ok"
        and packets["provider_response_shape_matrix_packet.json"]["status"] == "ok"
        and packets["provider_failure_semantics_matrix_packet.json"]["status"] == "ok"
    )
    with_limits_required = True
    with_limits_reasons = [
        "GENERIC_RUNTIME_PACKETS_DO_NOT_PROVE_PROVIDER_FAMILY_COMPATIBILITY",
        "REPRESENTATIVE_MODEL_ROWS_ONLY",
        "OPENROUTER_OWNER_CREDENTIAL_MISSING",
        "OPENROUTER_PROVIDER_CHECK_NOT_RUN",
        "FAMILY_WIDE_MODEL_COMPATIBILITY_NOT_PROVEN",
    ]
    packets["provider_adapter_family_matrix_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_adapter_family_matrix",
        "status": "ok" if matrix_ok else "blocked",
        "rows": family_rows,
        "provider_family_compatibility_proven": False,
        "family_wide_model_compatibility_proven": False,
        "with_limits_required": with_limits_required,
        "with_limits_reasons": with_limits_reasons,
    }

    false_green_checks = [
        {
            "name": "multi_provider_scope_explicit",
            "passed": packets["provider_adapter_scope_packet.json"][
                "multi_provider_scope_admitted"
            ]
            is True,
        },
        {
            "name": "generic_runtime_not_promoted_to_family_compatibility",
            "passed": runtime_adapter.get(
                "generic_runtime_harness_proves_provider_family_compatibility"
            )
            is False
            and live_summary.get("provider_family_compatibility_proven") is False
            and failure_taxonomy.get("failure_taxonomy_counts_as_provider_family_compatibility")
            is False,
        },
        {
            "name": "representative_model_not_family_wide",
            "passed": all(row.get("family_wide_model_proof") is False for row in family_rows),
        },
        {
            "name": "native_model_ux_final_not_claimed",
            "passed": packets["provider_adapter_scope_packet.json"][
                "native_or_final_e2e_claimed"
            ]
            is False,
        },
        {
            "name": "source_false_green_audits_ok",
            "passed": auth_false_green.get("status") == "ok"
            and runtime_false_green.get("status") == "ok"
            and live_false_green.get("status") == "ok"
            and model_false_green.get("status") == "ok",
        },
    ]
    packets["provider_adapter_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_adapter_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(check["passed"] for check in false_green_checks),
    }

    classification_ok = (
        packets["source_provider_adapter_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_provider_adapter_validation_packet.json"]["status"] == "ok"
        and matrix_ok
        and packets["provider_adapter_false_green_audit.json"]["status"] == "ok"
    )
    final_status = ""
    if classification_ok:
        final_status = (
            "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED_WITH_LIMITS"
            if with_limits_required
            else "WBP_PROVIDER_ADAPTER_MATRIX_CLASSIFIED"
        )
    packets["provider_adapter_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "provider_adapter_summary",
        "status": "ok" if classification_ok else "blocked",
        "final_status": final_status,
        "active_provider_family_count": len(provider_families),
        "active_provider_families": provider_families,
        "provider_family_compatibility_proven": False,
        "family_wide_model_compatibility_proven": False,
        "with_limits_required": with_limits_required if classification_ok else None,
        "native_reproof_claimed": False,
        "final_e2e_reproof_claimed": False,
    }
    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "provider_families": provider_families,
            "provider_count": len(provider_families),
            "deepseek_direct_probe_http_200": deepseek_proof.get("direct_provider_probe", {}).get(
                "http_status"
            )
            == 200,
            "openrouter_credential_present": openrouter_credential.get(
                "credential_result", {}
            ).get("credential_present")
            is True,
            "openrouter_provider_check_status": openrouter_provider_check.get("status"),
            "generic_runtime_provider_family_compatibility_proven": runtime_adapter.get(
                "generic_runtime_harness_proves_provider_family_compatibility"
            ),
            "live_non_native_provider_family_compatibility_proven": live_summary.get(
                "provider_family_compatibility_proven"
            ),
            "final_status": final_status,
        },
        "non_claims": {
            "provider_family_compatibility_proven": False,
            "family_wide_model_compatibility_proven": False,
            "native_reproof_claimed": False,
            "final_e2e_reproof_claimed": False,
        },
    }
    packets["independent_provider_adapter_matrix_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_provider_adapter_matrix_audit",
        "status": "ok" if classification_ok else "blocked",
        "provider_count": len(provider_families),
        "multi_provider_scope_admitted": len(provider_families) > 1,
        "deepseek_row_proof_level": next(
            (row["matrix_proof_level"] for row in family_rows if row["provider_family"] == "deepseek"),
            "",
        ),
        "openrouter_row_proof_level": next(
            (
                row["matrix_proof_level"]
                for row in family_rows
                if row["provider_family"] == "openrouter"
            ),
            "",
        ),
        "family_wide_claim_detected": any(
            row.get("family_wide_model_proof") is True for row in family_rows
        ),
        "provider_family_compatibility_proven": False,
    }
    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok" if classification_ok else "blocked",
        "checks": [
            {"name": "source_inventory_ok", "passed": inventory_ok},
            {"name": "source_validation_ok", "passed": all(validation_checks.values())},
            {"name": "matrix_ok", "passed": matrix_ok},
            {
                "name": "false_green_audit_ok",
                "passed": packets["provider_adapter_false_green_audit.json"]["status"]
                == "ok",
            },
        ],
    }
    return packets


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    source_dirs = {
        "auth_strategy": Path(args.auth_strategy_dir).resolve(),
        "runtime_compat": Path(args.runtime_compat_dir).resolve(),
        "live_non_native": Path(args.live_non_native_dir).resolve(),
        "model_availability": Path(args.model_availability_dir).resolve(),
        "deepseek": Path(args.deepseek_dir).resolve(),
        "openrouter": Path(args.openrouter_dir).resolve(),
    }

    if not repo_root.exists():
        return _emit_input_error(
            reason_class="repo_root_missing",
            message=f"repo root not found: {repo_root}",
            evidence_dir=evidence_dir,
        )

    for label, path in source_dirs.items():
        if not path.exists():
            return _emit_input_error(
                reason_class="source_dir_missing",
                message=f"{label} source dir not found: {path}",
                evidence_dir=evidence_dir,
            )

    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        source_dirs=source_dirs,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = packets["provider_adapter_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
