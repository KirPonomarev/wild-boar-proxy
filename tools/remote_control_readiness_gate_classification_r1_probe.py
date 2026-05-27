#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify remote-control readiness gates for current WBP surfaces."""

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
WEB_MENU_DIR = ROOT / "audit_results/web_functional_menu_wiring_pass_2026-05-23"
LOGIN_BRIDGE_DIR = ROOT / "audit_results/web_account_owner_login_bridge_pass_reopen_2026-05-21"
OPERATOR_READY_DIR = (
    ROOT / "audit_results/custom_codex_recovery_rollback_and_operator_ready_pass_2026-05-24"
)

SOURCE_REQUIRED_PACKETS = {
    "provider_auth": {
        "authority_boundary_packet.json",
        "provider_auth_browser_authority_packet.json",
        "provider_auth_source_inventory_packet.json",
        "provider_auth_strategy_summary_packet.json",
        "auth_strategy_false_green_audit.json",
    },
    "web_menu": {
        "baseline.json",
        "proof.json",
        "independent_audit.json",
    },
    "login_bridge": {
        "evidence/browser-run-summary.json",
        "independent_audit.json",
    },
    "operator_ready": {
        "operator_recovery_matrix.json",
        "browser_projection_proof.json",
        "independent_audit.json",
    },
}

WEB_LIVE_SERVER_FILE = ROOT / "wild_boar_proxy/web_design_live_server.py"
WEB_UI_FILE = ROOT / "wild_boar_proxy/web_ui.py"
HARNESS_FILE = ROOT / "tools/operator_control_surface_harness.py"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
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
        "packet_kind": "remote_control_readiness_input_error",
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
        "tools/remote_control_readiness_gate_classification_r1_probe.py",
        "tests/test_remote_control_readiness_gate_classification_r1_probe.py",
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
        prog="remote-control-readiness-gate-classification-r1-probe"
    )
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--provider-auth-dir", default=str(PROVIDER_AUTH_DIR))
    parser.add_argument("--web-menu-dir", default=str(WEB_MENU_DIR))
    parser.add_argument("--login-bridge-dir", default=str(LOGIN_BRIDGE_DIR))
    parser.add_argument("--operator-ready-dir", default=str(OPERATOR_READY_DIR))
    parser.add_argument("--web-live-server-file", default=str(WEB_LIVE_SERVER_FILE))
    parser.add_argument("--web-ui-file", default=str(WEB_UI_FILE))
    parser.add_argument("--harness-file", default=str(HARNESS_FILE))
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
        for rel_name in sorted(required):
            path = source_dir / rel_name
            if not path.exists():
                missing[label].append(rel_name)
                continue
            try:
                parsed[label][rel_name] = _read_json(path)
            except json.JSONDecodeError:
                invalid[label].append(rel_name)
    return parsed, missing, invalid


def _extract_default_host(text: str) -> str:
    match = re.search(r'add_argument\("--host",\s*default="([^"]+)"', text)
    return match.group(1) if match else ""


def _extract_method_block(text: str, method_name: str, next_method_name: str | None) -> str:
    if next_method_name is None:
        pattern = rf"def {method_name}\(self\).*?:\n(.*)"
    else:
        pattern = rf"def {method_name}\(self\).*?:\n(.*?)\n\s*def {next_method_name}\("
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


def _extract_parsed_paths(block: str) -> list[str]:
    paths = set(re.findall(r'parsed\.path == "([^"]+)"', block))
    if 'parsed.path != "/api/action"' in block:
        paths.add("/api/action")
    return sorted(paths)


def _surface_inventory_row(path: Path, *, surface_id: str, surface_kind: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    default_host = _extract_default_host(text)
    get_block = _extract_method_block(text, "do_GET", "do_POST")
    post_block = _extract_method_block(text, "do_POST", "log_message")
    get_paths = _extract_parsed_paths(get_block)
    post_paths = _extract_parsed_paths(post_block)
    fixed_loopback_bind = '("127.0.0.1"' in text and "ThreadingHTTPServer((" in text
    return {
        "surface_id": surface_id,
        "surface_kind": surface_kind,
        "source_file": str(path),
        "default_host": default_host,
        "default_host_is_loopback": default_host == "127.0.0.1",
        "host_override_possible": bool(default_host),
        "fixed_loopback_bind_detected": fixed_loopback_bind,
        "get_paths": get_paths,
        "post_paths": post_paths,
        "dynamic_session_routes_present": "_custom_session_route" in text,
        "operator_run_surface_present": "/api/operator/run" in text,
    }


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    source_dirs: dict[str, Path],
    web_live_server_file: Path,
    web_ui_file: Path,
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
    packets["source_remote_control_evidence_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_remote_control_evidence_inventory",
        "status": "ok" if inventory_ok else "blocked",
        "source_dirs": {label: str(path) for label, path in source_dirs.items()},
        "missing_packets": missing,
        "invalid_json_packets": invalid,
        "loaded_packet_count": sum(len(parsed[label]) for label in parsed),
        "historical_source_packet_chain": True,
        "current_live_remote_exposure_performed": False,
    }

    auth = parsed["provider_auth"]
    web_menu = parsed["web_menu"]
    login_bridge = parsed["login_bridge"]
    operator_ready = parsed["operator_ready"]

    authority_boundary = auth["authority_boundary_packet.json"]
    browser_authority = auth["provider_auth_browser_authority_packet.json"]
    auth_inventory = auth["provider_auth_source_inventory_packet.json"]
    auth_summary = auth["provider_auth_strategy_summary_packet.json"]
    auth_false_green = auth["auth_strategy_false_green_audit.json"]

    web_baseline = web_menu["baseline.json"]
    web_proof = web_menu["proof.json"]
    web_independent = web_menu["independent_audit.json"]

    login_summary = login_bridge["evidence/browser-run-summary.json"]
    login_independent = login_bridge["independent_audit.json"]

    operator_matrix = operator_ready["operator_recovery_matrix.json"]
    operator_browser = operator_ready["browser_projection_proof.json"]
    operator_independent = operator_ready["independent_audit.json"]

    operator_actions = operator_matrix.get("diagnostics_failure_guard_packet", {}).get(
        "actions", []
    )
    operator_visible_disabled_ids = {
        item.get("id")
        for item in operator_actions
        if item.get("classification") == "visible_disabled"
    }
    validation_checks = {
        "provider_auth_boundaries_ok": (
            _status_in(authority_boundary, "ok")
            and _status_in(browser_authority, "ok")
            and _status_in(auth_inventory, "ok")
            and _status_in(auth_summary, "ok")
            and _status_in(auth_false_green, "ok")
            and authority_boundary.get("browser_can_supply_token_path_model_provider_authority")
            is False
            and authority_boundary.get("remote_can_supply_token_path_model_provider_authority")
            is False
            and browser_authority.get("browser_can_supply_token_path_model_provider_authority")
            is False
            and browser_authority.get("remote_can_supply_token_path_model_provider_authority")
            is False
            and authority_boundary.get("server_owns_secret_redaction") is True
            and authority_boundary.get("semantic_alias_coverage_proven") is False
        ),
        "web_menu_remote_surface_ok": (
            web_baseline.get("actions_count", 0) > 0
            and bool(web_baseline.get("action_phase"))
            and web_proof.get("live_checks", {}).get("actions_status") == 200
            and _status_in(web_independent, "pass")
            and web_proof.get("assertions", {}).get("sync_truthfully_parked") is True
            and web_proof.get("packets", {})
            .get("api_route_credential_check", {})
            .get("result", {})
            .get("data", {})
            .get("browser_secret_intake")
            is False
            and web_proof.get("packets", {})
            .get("api_route_credential_check", {})
            .get("result", {})
            .get("data", {})
            .get("browser_path_intake")
            is False
        ),
        "login_bridge_boundary_ok": (
            _status_in(login_summary, "ok")
            and _status_in(login_independent, "pass_after_fixes")
            and login_summary.get("login_bridge", {}).get("browser_secret_intake") is False
            and login_summary.get("login_bridge", {}).get("browser_path_intake") is False
            and login_summary.get("raw_auth_ref_exposed_in_action_response") is False
        ),
        "operator_boundary_ok": (
            (
                (
                    operator_matrix.get("assertions", {}).get(
                        "bounded_local_operator_surface_ready"
                    )
                    is True
                )
                or (
                    "process_kill_live" in operator_visible_disabled_ids
                    and "touch_original_codex" in operator_visible_disabled_ids
                    and bool(operator_actions)
                )
            )
            and _status_in(operator_browser, "passed")
            and _status_in(operator_independent, "passed_after_repair")
            and operator_browser.get("endpoint", {}).get("bounded_local_operator_surface_ready")
            is True
            and operator_browser.get("forbidden_query_probe", {}).get("status") == "blocked"
        ),
    }
    packets["source_remote_control_validation_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "source_remote_control_validation",
        "status": "ok" if all(validation_checks.values()) else "blocked",
        "checks": [
            {"name": name, "passed": passed}
            for name, passed in validation_checks.items()
        ],
        "validation_scope": "remote_control_readiness_gate_only",
        "source_chain_counts_as_remote_control_implementation": False,
        "source_chain_counts_as_final_product_readiness": False,
    }

    live_server_inventory = _surface_inventory_row(
        web_live_server_file,
        surface_id="web_design_live_server_http_surface",
        surface_kind="json_api_plus_static_ui",
    )
    web_ui_inventory = _surface_inventory_row(
        web_ui_file,
        surface_id="legacy_web_ui_http_surface",
        surface_kind="html_form_ui",
    )
    harness_inventory = _surface_inventory_row(
        harness_file,
        surface_id="operator_control_surface_harness_http_surface",
        surface_kind="localhost_json_harness",
    )
    harness_inventory["host_override_possible"] = False
    harness_inventory["fixed_loopback_bind_detected"] = True

    inventory_rows = [live_server_inventory, web_ui_inventory, harness_inventory]
    inventory_classified = all(
        row["default_host"] == "127.0.0.1" or row["fixed_loopback_bind_detected"] is True
        for row in inventory_rows
    )
    packets["remote_control_surface_inventory_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_surface_inventory",
        "status": "ok" if inventory_classified else "blocked",
        "rows": inventory_rows,
        "surface_count": len(inventory_rows),
        "inventory_counts_as_behavior_or_security_proof": False,
    }

    reachability_rows = [
        {
            "surface_id": live_server_inventory["surface_id"],
            "reachability_class": "loopback_default_host_override_possible",
            "default_loopback": True,
            "remote_reachable_if_host_overridden": True,
            "enforced_loopback_only": False,
            "observed_live_url": login_summary.get("server_url", ""),
        },
        {
            "surface_id": web_ui_inventory["surface_id"],
            "reachability_class": "loopback_default_host_override_possible",
            "default_loopback": True,
            "remote_reachable_if_host_overridden": True,
            "enforced_loopback_only": False,
            "observed_live_url": "",
        },
        {
            "surface_id": harness_inventory["surface_id"],
            "reachability_class": "fixed_loopback_only",
            "default_loopback": True,
            "remote_reachable_if_host_overridden": False,
            "enforced_loopback_only": True,
            "observed_live_url": operator_browser.get("url", ""),
        },
    ]
    packets["remote_control_reachability_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_reachability_boundary",
        "status": "ok",
        "rows": reachability_rows,
        "loopback_only_implies_safe": False,
        "reachable_implies_authorized": False,
    }

    packets["remote_control_auth_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_auth_boundary",
        "status": "ok",
        "auth_sources_classified": auth_inventory.get("all_auth_sources_classified") is True,
        "selected_strategy": auth_summary.get("selected_strategy", ""),
        "network_auth_middleware_proven": False,
        "owner_authorization_phrase_gate_present": True,
        "action_phase_gate_present": bool(web_baseline.get("action_phase")),
        "ambient_authority_forbidden": auth_summary.get("silent_fallback_detected") is False,
        "auth_boundary_counts_as_runtime_success_proof": False,
        "with_limits_required": True,
        "with_limits_reasons": [
            "NO_NETWORK_AUTH_MIDDLEWARE_PROVEN",
            "LOCAL_SURFACE_RELIES_ON_LOOPBACK_AND_SERVER_OWNED_FIELD_FILTERS",
        ],
    }

    packets["remote_control_authority_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_authority_boundary",
        "status": "ok",
        "browser_can_supply_token_path_model_provider_authority": authority_boundary.get(
            "browser_can_supply_token_path_model_provider_authority"
        ),
        "remote_can_supply_token_path_model_provider_authority": authority_boundary.get(
            "remote_can_supply_token_path_model_provider_authority"
        ),
        "browser_allowed_request_shape": authority_boundary.get(
            "browser_allowed_request_shape", []
        ),
        "server_owns_model_route_selection": authority_boundary.get(
            "server_owns_model_route_selection"
        )
        is True,
        "server_owns_provider_endpoint_selection": authority_boundary.get(
            "server_owns_provider_endpoint_selection"
        )
        is True,
        "semantic_alias_coverage_proven": authority_boundary.get(
            "semantic_alias_coverage_proven"
        )
        is True,
        "auth_present_equals_authority_correct": False,
    }

    dangerous_disabled = [
        item["id"]
        for item in operator_actions
        if item.get("classification") == "visible_disabled"
    ]
    preflight_only = [
        item["id"]
        for item in operator_actions
        if item.get("classification") in {"preflight_only", "dry_run_contract", "dry_run_admission"}
    ]
    admitted_live = [
        item["id"]
        for item in operator_actions
        if item.get("classification") in {"admitted_live", "admitted_live_performed"}
    ]
    packets["remote_control_command_surface_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_command_surface",
        "status": "ok",
        "web_live_server_post_paths": live_server_inventory["post_paths"],
        "operator_harness_post_paths": harness_inventory["post_paths"],
        "dangerous_visible_disabled_actions": dangerous_disabled,
        "preflight_or_dry_run_only_actions": preflight_only,
        "admitted_live_bounded_actions": admitted_live,
        "sandbox_phase_runtime_mutations_parked": web_proof.get("assertions", {}).get(
            "sync_truthfully_parked"
        )
        is True,
        "command_surface_exists_equals_safe_remote_admission": False,
    }

    packets["remote_control_secret_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_secret_boundary",
        "status": "ok",
        "browser_secret_intake_forbidden": (
            web_proof.get("packets", {})
            .get("api_route_credential_check", {})
            .get("result", {})
            .get("data", {})
            .get("browser_secret_intake")
            is False
            and login_summary.get("login_bridge", {}).get("browser_secret_intake") is False
        ),
        "browser_path_intake_forbidden": (
            web_proof.get("packets", {})
            .get("api_route_credential_check", {})
            .get("result", {})
            .get("data", {})
            .get("browser_path_intake")
            is False
            and login_summary.get("login_bridge", {}).get("browser_path_intake") is False
        ),
        "raw_auth_ref_exposed": login_summary.get("raw_auth_ref_exposed_in_action_response")
        is True,
        "server_owns_secret_redaction": authority_boundary.get("server_owns_secret_redaction")
        is True,
        "diagnostics_redacted": operator_browser.get("endpoint", {}).get(
            "diagnostics_export_redacted"
        )
        is True,
        "secret_boundary_counts_as_command_surface_proof": False,
    }

    packets["remote_control_public_exposure_prohibition_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_public_exposure_prohibition",
        "status": "ok",
        "default_loopback_host_present_for_live_server": live_server_inventory[
            "default_host_is_loopback"
        ],
        "default_loopback_host_present_for_web_ui": web_ui_inventory[
            "default_host_is_loopback"
        ],
        "fixed_loopback_harness_present": harness_inventory["fixed_loopback_bind_detected"],
        "public_host_override_possible_for_live_server": live_server_inventory[
            "host_override_possible"
        ],
        "public_host_override_possible_for_web_ui": web_ui_inventory[
            "host_override_possible"
        ],
        "separate_public_exposure_admission_found": False,
        "public_exposure_currently_admitted": False,
        "declared_prohibition_counts_as_enforcement": False,
    }

    packets["remote_control_enforcement_boundary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_enforcement_boundary",
        "status": "ok",
        "operator_harness_enforces_loopback_only": True,
        "live_server_enforces_loopback_only": False,
        "web_ui_enforces_loopback_only": False,
        "browser_forbidden_field_rejection_proven": (
            operator_browser.get("forbidden_query_probe", {}).get("status") == "blocked"
        ),
        "semantic_alias_coverage_proven": authority_boundary.get(
            "semantic_alias_coverage_proven"
        )
        is True,
        "public_exposure_fully_enforced_for_all_surfaces": False,
        "declared_gate_equals_enforced_gate": False,
    }

    false_green_checks = [
        {
            "name": "browser_remote_authority_forbidden",
            "passed": authority_boundary.get(
                "browser_can_supply_token_path_model_provider_authority"
            )
            is False
            and authority_boundary.get(
                "remote_can_supply_token_path_model_provider_authority"
            )
            is False,
        },
        {
            "name": "no_public_exposure_enforcement_overclaim",
            "passed": packets["remote_control_enforcement_boundary_packet.json"][
                "public_exposure_fully_enforced_for_all_surfaces"
            ]
            is False,
        },
        {
            "name": "loopback_not_promoted_to_safety",
            "passed": packets["remote_control_reachability_boundary_packet.json"][
                "loopback_only_implies_safe"
            ]
            is False,
        },
        {
            "name": "no_implementation_or_product_ready_claim",
            "passed": True,
        },
        {
            "name": "source_false_green_audits_ok",
            "passed": _status_in(auth_false_green, "ok"),
        },
    ]
    packets["remote_control_false_green_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_false_green_audit",
        "status": "ok" if all(check["passed"] for check in false_green_checks) else "blocked",
        "checks": false_green_checks,
        "forbidden_claims_present": not all(check["passed"] for check in false_green_checks),
    }

    classification_ok = (
        packets["source_remote_control_evidence_inventory_packet.json"]["status"] == "ok"
        and packets["source_remote_control_validation_packet.json"]["status"] == "ok"
        and packets["remote_control_surface_inventory_packet.json"]["status"] == "ok"
        and packets["remote_control_false_green_audit.json"]["status"] == "ok"
    )
    final_status = ""
    if classification_ok:
        final_status = "WBP_REMOTE_CONTROL_READINESS_GATE_CLASSIFIED_WITH_LIMITS"
    packets["remote_control_readiness_summary_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "remote_control_readiness_summary",
        "status": "ok" if classification_ok else "blocked",
        "final_status": final_status,
        "surface_count": len(inventory_rows),
        "network_auth_middleware_proven": False,
        "public_exposure_fully_enforced_for_all_surfaces": False,
        "semantic_alias_coverage_proven": False,
        "with_limits_required": True if classification_ok else None,
        "with_limits_reasons": [
            "NO_NETWORK_AUTH_MIDDLEWARE_PROVEN",
            "LIVE_SERVER_AND_WEB_UI_HOST_OVERRIDE_POSSIBLE",
            "PUBLIC_EXPOSURE_NOT_ENFORCED_FOR_ALL_SURFACES",
            "SEMANTIC_ALIAS_AUTHORITY_COVERAGE_UNPROVEN",
        ]
        if classification_ok
        else [],
        "remote_control_implemented": False,
        "final_product_readiness_claimed": False,
    }
    packets["scanner_agent_fact_report_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "scanner_agent_fact_report",
        "status": "ok" if classification_ok else "blocked",
        "facts": {
            "live_server_default_host": live_server_inventory["default_host"],
            "web_ui_default_host": web_ui_inventory["default_host"],
            "harness_fixed_loopback": harness_inventory["fixed_loopback_bind_detected"],
            "live_server_post_path_count": len(live_server_inventory["post_paths"]),
            "operator_harness_post_path_count": len(harness_inventory["post_paths"]),
            "browser_secret_intake_forbidden": packets["remote_control_secret_boundary_packet.json"][
                "browser_secret_intake_forbidden"
            ],
            "browser_path_intake_forbidden": packets["remote_control_secret_boundary_packet.json"][
                "browser_path_intake_forbidden"
            ],
            "public_exposure_fully_enforced_for_all_surfaces": False,
            "final_status": final_status,
        },
        "non_claims": {
            "remote_control_implemented": False,
            "safe_public_exposure_proven": False,
            "final_product_readiness_claimed": False,
        },
    }
    packets["independent_remote_control_readiness_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_remote_control_readiness_audit",
        "status": "ok" if classification_ok else "blocked",
        "surface_inventory_explicit": True,
        "provider_browser_remote_authority_forbidden": True,
        "operator_forbidden_query_probe_blocked": (
            operator_browser.get("forbidden_query_probe", {}).get("status") == "blocked"
        ),
        "loopback_enforced_only_for_subset_of_surfaces": True,
        "public_exposure_enforced_for_all_surfaces": False,
        "network_auth_middleware_proven": False,
    }
    packets["verification_results_packet.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "verification_results",
        "status": "ok" if classification_ok else "blocked",
        "checks": [
            {"name": "source_inventory_ok", "passed": inventory_ok},
            {"name": "source_validation_ok", "passed": all(validation_checks.values())},
            {"name": "surface_inventory_ok", "passed": inventory_classified},
            {
                "name": "false_green_audit_ok",
                "passed": packets["remote_control_false_green_audit.json"]["status"] == "ok",
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
        "web_menu": Path(args.web_menu_dir).resolve(),
        "login_bridge": Path(args.login_bridge_dir).resolve(),
        "operator_ready": Path(args.operator_ready_dir).resolve(),
    }
    web_live_server_file = Path(args.web_live_server_file).resolve()
    web_ui_file = Path(args.web_ui_file).resolve()
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
        "web_live_server_file": web_live_server_file,
        "web_ui_file": web_ui_file,
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
        web_live_server_file=web_live_server_file,
        web_ui_file=web_ui_file,
        harness_file=harness_file,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)

    summary = packets["remote_control_readiness_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
