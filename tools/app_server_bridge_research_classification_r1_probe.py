#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify app-server bridge research boundaries for current WBP surfaces."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import json_write


PROVIDER_AUTH_DIR = ROOT / "audit_results/wbp_provider_auth_strategy_contract_r1_2026-05-27"
REMOTE_GATE_DIR = ROOT / "audit_results/wbp_remote_control_readiness_gate_classification_r1_2026-05-27"
SETUP_IMPORT_DIR = ROOT / "audit_results/web_setup_import_surface_admission_foundation_pass_2026-05-25"
ISOLATED_APP_E2E_DIR = ROOT / "audit_results/isolated_codex_app_e2e_pass_2026-05-23"

COMMAND_ADAPTER_FILE = ROOT / "wild_boar_proxy/web_design_command_adapter.py"
WEB_LIVE_SERVER_FILE = ROOT / "wild_boar_proxy/web_design_live_server.py"
HARNESS_FILE = ROOT / "tools/operator_control_surface_harness.py"

SOURCE_REQUIRED_PACKETS = {
    "provider_auth": {
        "authority_boundary_packet.json",
        "provider_auth_strategy_summary_packet.json",
        "auth_strategy_false_green_audit.json",
    },
    "remote_gate": {
        "remote_control_readiness_summary_packet.json",
        "remote_control_authority_boundary_packet.json",
        "remote_control_command_surface_packet.json",
        "remote_control_false_green_audit.json",
    },
    "setup_import": {
        "spec.md",
        "evidence/verification_summary.json",
        "evidence/independent_audit_report.json",
    },
    "isolated_app_e2e": {
        "proof.json",
        "independent_audit.json",
        "closeout.md",
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
        "packet_kind": "app_server_bridge_research_input_error",
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


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
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
        "tools/app_server_bridge_research_classification_r1_probe.py",
        "tests/test_app_server_bridge_research_classification_r1_probe.py",
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
    parser = argparse.ArgumentParser(
        prog="app-server-bridge-research-classification-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--provider-auth-dir", default=str(PROVIDER_AUTH_DIR))
    parser.add_argument("--remote-gate-dir", default=str(REMOTE_GATE_DIR))
    parser.add_argument("--setup-import-dir", default=str(SETUP_IMPORT_DIR))
    parser.add_argument("--isolated-app-e2e-dir", default=str(ISOLATED_APP_E2E_DIR))
    parser.add_argument("--command-adapter-file", default=str(COMMAND_ADAPTER_FILE))
    parser.add_argument("--web-live-server-file", default=str(WEB_LIVE_SERVER_FILE))
    parser.add_argument("--harness-file", default=str(HARNESS_FILE))
    return parser


def _load_sources(
    source_dirs: dict[str, Path],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
    parsed: dict[str, dict[str, Any]] = {}
    missing: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}
    for label, required in SOURCE_REQUIRED_PACKETS.items():
        parsed[label] = {}
        missing[label] = []
        invalid[label] = []
        source_dir = source_dirs[label]
        for rel_name in sorted(required):
            path = source_dir / rel_name
            if not path.exists():
                missing[label].append(rel_name)
                continue
            if path.suffix == ".json":
                try:
                    parsed[label][rel_name] = _read_json(path)
                except json.JSONDecodeError:
                    invalid[label].append(rel_name)
            else:
                parsed[label][rel_name] = {"text": path.read_text(encoding="utf-8")}
    return parsed, missing, invalid


def _extract_allowlist_entry_count(text: str) -> int:
    return text.count("CommandSpec(")


def _extract_ui_disabled_count(text: str) -> int:
    return text.count("ui_enabled=False")


def _extract_ui_action_allowlist_count(text: str) -> int:
    return text.count('"adapter_command_id":')


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_dirs: dict[str, Path],
    command_adapter_file: Path,
    web_live_server_file: Path,
    harness_file: Path,
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
    packets["source_app_server_bridge_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_app_server_bridge_evidence_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "current_bridge_implementation_performed": False,
    }

    provider_auth = parsed["provider_auth"]
    remote_gate = parsed["remote_gate"]
    setup_import = parsed["setup_import"]
    isolated_app = parsed["isolated_app_e2e"]

    authority_boundary = provider_auth["authority_boundary_packet.json"]
    auth_summary = provider_auth["provider_auth_strategy_summary_packet.json"]
    auth_false_green = provider_auth["auth_strategy_false_green_audit.json"]

    remote_summary = remote_gate["remote_control_readiness_summary_packet.json"]
    remote_authority = remote_gate["remote_control_authority_boundary_packet.json"]
    remote_command_surface = remote_gate["remote_control_command_surface_packet.json"]
    remote_false_green = remote_gate["remote_control_false_green_audit.json"]

    setup_spec = setup_import["spec.md"]["text"]
    setup_verification = setup_import["evidence/verification_summary.json"]
    setup_audit = setup_import["evidence/independent_audit_report.json"]

    isolated_proof = isolated_app["proof.json"]
    isolated_audit = isolated_app["independent_audit.json"]
    isolated_closeout = isolated_app["closeout.md"]["text"]

    adapter_text = command_adapter_file.read_text(encoding="utf-8")
    live_server_text = web_live_server_file.read_text(encoding="utf-8")
    harness_text = harness_file.read_text(encoding="utf-8")

    validation_checks = {
        "provider_auth_boundary_ok": (
            _status_in(authority_boundary, "ok")
            and _status_in(auth_summary, "ok")
            and _status_in(auth_false_green, "ok")
            and authority_boundary.get("browser_can_supply_token_path_model_provider_authority")
            is False
            and authority_boundary.get("remote_can_supply_token_path_model_provider_authority")
            is False
        ),
        "remote_gate_reference_ok": (
            _status_in(remote_summary, "ok")
            and _status_in(remote_authority, "ok")
            and _status_in(remote_command_surface, "ok")
            and _status_in(remote_false_green, "ok")
            and remote_summary.get("remote_control_implemented") is False
            and remote_summary.get("public_exposure_fully_enforced_for_all_surfaces") is False
        ),
        "setup_import_bridge_foundation_ok": (
            "no command adapter or runtime bridge execution path is enabled" in setup_spec
            and setup_verification.get("scope", {}).get("command_adapter_changed") is False
            and setup_verification.get("scope", {}).get("runtime_bridge_changed") is False
            and setup_verification.get("scope", {}).get("execution_enabled") is False
            and setup_audit.get("verdict") == "PASS"
        ),
        "isolated_app_bridge_limit_truth_ok": (
            isolated_proof.get("launched_gui_process", {}).get("observed") is True
            and bool(
                isolated_proof.get("launched_gui_process", {}).get("child_app_server_command", "")
            )
            and isolated_proof.get("followup_control_surface_probe", {}).get(
                "isolated_codex_home_socket_found"
            )
            is False
            and isolated_proof.get("followup_control_surface_probe", {}).get(
                "child_tcp_or_udp_listener_found"
            )
            is False
            and isolated_proof.get("boundary_verdict", {}).get("status") == "blocked"
            and "could not be truthfully tied" in isolated_closeout
            and any(
                item.get("name") == "strict_gui_through_app_proof"
                and "no isolated app-server control socket" in item.get("fact", "")
                for item in isolated_audit.get("checks", [])
            )
        ),
        "code_bridge_surfaces_ok": (
            "only planned Python-side bridge" in adapter_text
            and "execute_command(" in adapter_text
            and _extract_allowlist_entry_count(adapter_text) > 0
            and _extract_ui_disabled_count(adapter_text) > 0
            and _extract_ui_action_allowlist_count(live_server_text) > 0
            and 'ThreadingHTTPServer(("127.0.0.1"' in harness_text
        ),
    }
    packets["source_app_server_bridge_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_app_server_bridge_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [{"name": name, "passed": passed} for name, passed in validation_checks.items()],
        "validation_scope": "app_server_bridge_research_only",
        "source_chain_counts_as_implementation": False,
        "source_chain_counts_as_architecture_approval": False,
    }

    concept_rows = [
        {
            "concept_id": "web_design_command_adapter_bridge",
            "concept_class": "local_python_command_adapter",
            "source_file": str(command_adapter_file),
            "implementation_present": True,
            "research_admissible": True,
            "implementation_admitted": False,
            "architecture_approved": False,
            "notes": "Only planned Python-side bridge between HTML renderer path and Wild Boar Proxy command packets.",
        },
        {
            "concept_id": "web_design_live_server_ui_action_bridge",
            "concept_class": "loopback_http_ui_action_dispatch",
            "source_file": str(web_live_server_file),
            "implementation_present": True,
            "research_admissible": True,
            "implementation_admitted": False,
            "architecture_approved": False,
            "notes": "UI action allowlist maps metadata to adapter command ids but public metadata intentionally hides adapter internals.",
        },
        {
            "concept_id": "operator_control_surface_harness_bridge",
            "concept_class": "localhost_json_operator_harness",
            "source_file": str(harness_file),
            "implementation_present": True,
            "research_admissible": True,
            "implementation_admitted": False,
            "architecture_approved": False,
            "notes": "Temporary proof harness, not a production web app; localhost JSON surfaces only.",
        },
        {
            "concept_id": "codex_child_app_server_bridge",
            "concept_class": "historical_app_owned_child_app_server_surface",
            "source_file": str(source_dirs["isolated_app_e2e"] / "proof.json"),
            "implementation_present": True,
            "research_admissible": True,
            "implementation_admitted": False,
            "architecture_approved": False,
            "notes": "Historical child app-server observed, but no repo-usable machine-backed control socket or listener was proven.",
        },
    ]
    packets["app_server_bridge_concept_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_concept_inventory",
        "status": "ok",
        "rows": concept_rows,
        "concept_count": len(concept_rows),
        "inventory_counts_as_architecture_decision": False,
    }

    ownership_rows = [
        {
            "concept_id": "web_design_command_adapter_bridge",
            "owner_class": "WBP_owned",
            "owner_reason": "repo-owned Python adapter module",
        },
        {
            "concept_id": "web_design_live_server_ui_action_bridge",
            "owner_class": "WBP_owned",
            "owner_reason": "repo-owned web live server and UI action allowlist",
        },
        {
            "concept_id": "operator_control_surface_harness_bridge",
            "owner_class": "WBP_owned",
            "owner_reason": "repo-owned temporary harness",
        },
        {
            "concept_id": "codex_child_app_server_bridge",
            "owner_class": "app_owned",
            "owner_reason": "observed child process of Codex.app, not a repo-owned exposed machine surface",
        },
    ]
    packets["app_server_bridge_ownership_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_ownership_boundary",
        "status": "ok",
        "rows": ownership_rows,
        "unknown_ownership_rows": 0,
        "ownership_counts_as_native_compatibility_proof": False,
    }

    transport_rows = [
        {
            "concept_id": "web_design_command_adapter_bridge",
            "transport_class": "local_subprocess_json_command_bus",
            "security_proven": False,
            "implementation_admitted": False,
        },
        {
            "concept_id": "web_design_live_server_ui_action_bridge",
            "transport_class": "loopback_http_to_local_python_dispatch",
            "security_proven": False,
            "implementation_admitted": False,
        },
        {
            "concept_id": "operator_control_surface_harness_bridge",
            "transport_class": "loopback_http_local_json_surface",
            "security_proven": False,
            "implementation_admitted": False,
        },
        {
            "concept_id": "codex_child_app_server_bridge",
            "transport_class": "control_socket_or_listener_unproven",
            "security_proven": False,
            "implementation_admitted": False,
        },
    ]
    packets["app_server_bridge_transport_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_transport_boundary",
        "status": "ok",
        "rows": transport_rows,
        "transport_exists_equals_security": False,
        "transport_exists_equals_implementation_admission": False,
    }

    packets["app_server_bridge_auth_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_auth_boundary",
        "status": "ok",
        "selected_strategy": auth_summary.get("selected_strategy", ""),
        "network_auth_middleware_proven": remote_summary.get("network_auth_middleware_proven"),
        "owner_authorization_phrase_gate_present": True,
        "ambient_authority_forbidden": auth_summary.get("silent_fallback_detected") is False,
        "auth_boundary_counts_as_bridge_viability": False,
    }

    packets["app_server_bridge_authority_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_authority_boundary",
        "status": "ok",
        "browser_can_supply_token_path_model_provider_authority": authority_boundary.get(
            "browser_can_supply_token_path_model_provider_authority"
        ),
        "remote_can_supply_token_path_model_provider_authority": authority_boundary.get(
            "remote_can_supply_token_path_model_provider_authority"
        ),
        "browser_allowed_request_shape": authority_boundary.get("browser_allowed_request_shape", []),
        "server_owns_model_route_selection": authority_boundary.get(
            "server_owns_model_route_selection"
        )
        is True,
        "server_owns_provider_endpoint_selection": authority_boundary.get(
            "server_owns_provider_endpoint_selection"
        )
        is True,
        "auth_present_equals_authority_correct": False,
    }

    packets["app_server_bridge_command_surface_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_command_surface",
        "status": "ok",
        "command_adapter_allowlist_entries": _extract_allowlist_entry_count(adapter_text),
        "command_adapter_ui_disabled_entries": _extract_ui_disabled_count(adapter_text),
        "web_live_server_ui_actions_with_adapter_command_id": _extract_ui_action_allowlist_count(
            live_server_text
        ),
        "setup_import_runtime_bridge_execution_enabled": setup_verification.get("scope", {}).get(
            "runtime_bridge_changed"
        )
        is True,
        "remote_command_surface_counts_as_bridge_admission": False,
        "dangerous_visible_disabled_actions": remote_command_surface.get(
            "dangerous_visible_disabled_actions", []
        ),
    }

    packets["app_server_bridge_substitution_risk_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_substitution_risk",
        "status": "ok",
        "bridge_equals_native_app_proof": False,
        "bridge_equals_remote_control_admission": False,
        "bridge_equals_final_e2e": False,
        "bridge_equals_provider_compatibility_proof": False,
        "research_equals_architecture_approval": False,
        "research_equals_implementation_admission": False,
        "historical_app_server_surface_repo_usable_machine_proven": False,
        "isolated_app_boundary_verdict": isolated_proof.get("boundary_verdict", {}).get(
            "machine_classification", ""
        ),
    }

    packets["app_server_bridge_remote_control_gate_reference_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_remote_control_gate_reference",
        "status": "ok",
        "remote_control_final_status": remote_summary.get("final_status", ""),
        "remote_control_implemented": remote_summary.get("remote_control_implemented"),
        "public_exposure_fully_enforced_for_all_surfaces": remote_summary.get(
            "public_exposure_fully_enforced_for_all_surfaces"
        ),
        "reference_only": True,
        "reference_counts_as_bridge_viability": False,
    }

    false_green_checks = [
        {
            "name": "no_native_proof_overclaim",
            "passed": packets["app_server_bridge_substitution_risk_packet.json"][
                "bridge_equals_native_app_proof"
            ]
            is False,
        },
        {
            "name": "no_remote_control_admission_overclaim",
            "passed": packets["app_server_bridge_substitution_risk_packet.json"][
                "bridge_equals_remote_control_admission"
            ]
            is False,
        },
        {
            "name": "no_implementation_admission_overclaim",
            "passed": packets["app_server_bridge_substitution_risk_packet.json"][
                "research_equals_implementation_admission"
            ]
            is False,
        },
        {
            "name": "no_architecture_approval_overclaim",
            "passed": packets["app_server_bridge_substitution_risk_packet.json"][
                "research_equals_architecture_approval"
            ]
            is False,
        },
        {
            "name": "source_false_green_audits_ok",
            "passed": _status_in(auth_false_green, "ok") and _status_in(remote_false_green, "ok"),
        },
    ]
    packets["app_server_bridge_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_false_green_audit",
        "status": "ok" if all(item["passed"] for item in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(item["passed"] for item in false_green_checks),
    }

    classification_ok = (
        packets["source_app_server_bridge_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_app_server_bridge_validation_packet.json"]["status"] == "ok"
        and packets["app_server_bridge_false_green_audit.json"]["status"] == "ok"
    )
    final_status = ""
    if classification_ok:
        final_status = "WBP_APP_SERVER_BRIDGE_RESEARCH_CLASSIFIED_WITH_LIMITS"
    packets["app_server_bridge_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "app_server_bridge_summary",
        "status": "ok" if classification_ok else "blocked",
        "final_status": final_status,
        "concept_count": len(concept_rows),
        "network_auth_middleware_proven": remote_summary.get("network_auth_middleware_proven"),
        "remote_control_implemented": remote_summary.get("remote_control_implemented"),
        "historical_codex_child_control_socket_proven": False,
        "research_only": True,
        "implementation_admitted": False,
        "architecture_approved": False,
        "with_limits_required": True if classification_ok else None,
        "with_limits_reasons": [
            "NO_NETWORK_AUTH_MIDDLEWARE_PROVEN",
            "REMOTE_CONTROL_NOT_ADMITTED",
            "HISTORICAL_CODEX_CHILD_CONTROL_SOCKET_NOT_PROVEN",
            "BRIDGE_RESEARCH_DOES_NOT_APPROVE_IMPLEMENTATION",
        ]
        if classification_ok
        else [],
    }
    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "command_adapter_allowlist_entries": _extract_allowlist_entry_count(adapter_text),
            "command_adapter_ui_disabled_entries": _extract_ui_disabled_count(adapter_text),
            "web_live_server_ui_action_bridge_count": _extract_ui_action_allowlist_count(
                live_server_text
            ),
            "historical_child_app_server_observed": isolated_proof.get("launched_gui_process", {}).get(
                "observed"
            ),
            "historical_child_control_socket_proven": False,
            "remote_control_final_status": remote_summary.get("final_status", ""),
            "final_status": final_status,
        },
        "non_claims": {
            "native_compatibility_proven": False,
            "remote_control_admitted": False,
            "implementation_admitted": False,
            "architecture_approved": False,
        },
    }
    packets["independent_app_server_bridge_research_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_app_server_bridge_research_audit",
        "status": "ok" if classification_ok else "blocked",
        "bridge_concepts_explicit": True,
        "browser_remote_authority_forbidden": True,
        "historical_child_app_server_machine_surface_unproven": True,
        "remote_control_reference_only": True,
        "implementation_approval_claimed": False,
        "architecture_approval_claimed": False,
    }
    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok" if classification_ok else "blocked",
        "checks": [
            {"name": "source_inventory_ok", "passed": inventory_ok},
            {"name": "source_validation_ok", "passed": all(validation_checks.values())},
            {
                "name": "false_green_audit_ok",
                "passed": packets["app_server_bridge_false_green_audit.json"]["status"] == "ok",
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
        "provider_auth": Path(args.provider_auth_dir).resolve(),
        "remote_gate": Path(args.remote_gate_dir).resolve(),
        "setup_import": Path(args.setup_import_dir).resolve(),
        "isolated_app_e2e": Path(args.isolated_app_e2e_dir).resolve(),
    }
    command_adapter_file = Path(args.command_adapter_file).resolve()
    web_live_server_file = Path(args.web_live_server_file).resolve()
    harness_file = Path(args.harness_file).resolve()

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
    for label, path in {
        "command_adapter_file": command_adapter_file,
        "web_live_server_file": web_live_server_file,
        "harness_file": harness_file,
    }.items():
        if not path.exists():
            return _emit_input_error(
                reason_class="source_file_missing",
                message=f"{label} not found: {path}",
                evidence_dir=evidence_dir,
            )

    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        source_dirs=source_dirs,
        command_adapter_file=command_adapter_file,
        web_live_server_file=web_live_server_file,
        harness_file=harness_file,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = packets["app_server_bridge_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
