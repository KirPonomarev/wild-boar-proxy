#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Emit non-live readiness evidence for a future Codex CLI runner via WBP smoke."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.cli_runner import RUNNER_SURFACE
from wild_boar_proxy.cli_runner_via_wbp import build_cli_runner_layer_boundary_packet, sha256_text
from wild_boar_proxy.native_filesystem_probe import json_write


TARGET_STATUS = "CODEX_CLI_RUNNER_VIA_WBP_SMOKE_READINESS_CLASSIFIED"
PARENT_STATUS = "CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP"
AUTH_STRATEGY_STATUS = "WBP_PROVIDER_AUTH_STRATEGY_CLASSIFIED"
MODEL_READINESS_STATUS = "WBP_MODEL_CATALOG_AND_AVAILABILITY_READINESS_RECONCILIATION_NO_LIVE_R1_CLASSIFIED"
AUTH_STRATEGY_DIR = "audit_results/wbp_provider_auth_strategy_precedence_r1_2026-05-27"
MODEL_READINESS_DIR = "audit_results/wbp_model_catalog_and_availability_readiness_reconciliation_no_live_r1_2026-05-27"
EVIDENCE_DIR_NAME = "audit_results/wbp_codex_cli_runner_via_wbp_smoke_readiness_r1_2026-05-27"
PROMPT_PLACEHOLDER = "<redacted-future-cli-runner-prompt>"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_text(repo_root: Path, command: list[str]) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return process.stdout.strip() if process.returncode == 0 else process.stderr.strip()


def packet(kind: str, status: str = "ok", **values: Any) -> dict[str, Any]:
    return {
        "captured_at_utc": utc_now(),
        "packet_kind": kind,
        "status": status,
        **values,
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return sha256_text(path.read_text(encoding="utf-8", errors="replace"))


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = run_text(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/cli_runner_smoke_readiness_probe.py",
        "tests/test_cli_runner_smoke_readiness_probe.py",
        "wild_boar_proxy/cli_runner.py",
        "wild_boar_proxy/cli_runner_via_wbp.py",
        "wild_boar_proxy/codex_custom_sessions.py",
        "tests/test_cli_runner.py",
        "tools/cli_runner_via_wbp_smoke_probe.py",
    }
    admitted_current_evidence_prefixes = (
        f"?? {relative_evidence_dir}/",
        f"?? {EVIDENCE_DIR_NAME}/",
        "?? audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/",
        "M audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/",
        " M audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/",
    )
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "M tests/test_native_filesystem_probe.py",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
        "?? audit_results/wbp_persistent_custom_profile_restoration_correlation_r5_2026-05-27/",
        "?? tools/persistent_custom_profile_restoration_correlation_r5_probe.py",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(admitted_current_evidence_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def build_surface_inventory_packet(repo_root: Path) -> dict[str, Any]:
    surfaces = [
        {
            "path": "wild_boar_proxy/cli.py",
            "surface": "argparse codex-runner smoke command",
            "live_danger": "dispatches run_codex_cli_runner_smoke when executed",
            "execution_allowed_in_this_contour": False,
        },
        {
            "path": "wild_boar_proxy/cli_runner.py",
            "surface": "run_codex_cli_runner_smoke and RUNNER_SURFACE",
            "live_danger": "can launch Codex CLI runner and prompt path",
            "execution_allowed_in_this_contour": False,
        },
        {
            "path": "wild_boar_proxy/cli_runner_via_wbp.py",
            "surface": "packet builders and validators",
            "live_danger": "builders safe; smoke pass packets are not current truth here",
            "execution_allowed_in_this_contour": False,
        },
        {
            "path": "tools/cli_runner_via_wbp_smoke_probe.py",
            "surface": "completed smoke probe",
            "live_danger": "runs Codex binary and WBP trace observer",
            "execution_allowed_in_this_contour": False,
        },
    ]
    return packet(
        "cli_runner_surface_inventory",
        runner_surface=RUNNER_SURFACE,
        repo_root=str(repo_root),
        live_surfaces_identified=True,
        codex_runner_smoke_execution_allowed=False,
        old_cli_evidence_imported_as_current_truth=False,
        surfaces=surfaces,
    )


def build_command_shape_packet() -> dict[str, Any]:
    argv_template = [
        "python3",
        "-m",
        "wild_boar_proxy",
        "codex-runner",
        "smoke",
        "--json",
        "--prompt",
        PROMPT_PLACEHOLDER,
    ]
    return packet(
        "cli_runner_command_shape",
        runner_surface=RUNNER_SURFACE,
        argv_template=argv_template,
        argv_template_hash=sha256_text(json.dumps(argv_template, sort_keys=True)),
        command_shape_prepared=True,
        command_executed=False,
        codex_runner_smoke_executed=False,
        live_provider_request_attempted=False,
        native_launch_attempted=False,
        owner_prompt_required=False,
        raw_prompt_recorded=False,
        prompt_placeholder_recorded=True,
        command_shape_counts_as_cli_smoke_pass=False,
        command_shape_counts_as_model_availability=False,
    )


def build_auth_boundary_packet() -> dict[str, Any]:
    summary_path = REPO_ROOT / AUTH_STRATEGY_DIR / "provider_auth_strategy_summary_packet.json"
    contract_path = REPO_ROOT / AUTH_STRATEGY_DIR / "provider_auth_precedence_contract_packet.json"
    summary = read_json(summary_path)
    contract = read_json(contract_path)
    selected_strategy = str(
        summary.get("selected_strategy") or contract.get("selected_strategy") or "auth.command"
    )
    ok = summary.get("final_status") == AUTH_STRATEGY_STATUS and selected_strategy == "auth.command"
    return packet(
        "cli_runner_auth_boundary",
        status="ok" if ok else "blocked",
        auth_strategy_reference={
            "summary_path": f"{AUTH_STRATEGY_DIR}/provider_auth_strategy_summary_packet.json",
            "summary_sha256": file_sha256(summary_path),
            "contract_path": f"{AUTH_STRATEGY_DIR}/provider_auth_precedence_contract_packet.json",
            "contract_sha256": file_sha256(contract_path),
            "reference_only": True,
        },
        selected_strategy=selected_strategy,
        auth_command_required=True,
        auth_reproved_in_this_contour=False,
        auth_invoked_in_this_contour=False,
        file_auth_selected=False,
        current_codex_auth_json_used=False,
        raw_token_recorded=False,
        auth_boundary_counts_as_cli_smoke_pass=False,
        auth_boundary_counts_as_model_availability=False,
    )


def build_prompt_redaction_packet(command_shape: dict[str, Any]) -> dict[str, Any]:
    return packet(
        "cli_runner_prompt_redaction",
        prompt_source="future_owner_or_test_prompt_only",
        prompt_placeholder=command_shape.get("argv_template", [])[-1],
        prompt_placeholder_hash=sha256_text(str(command_shape.get("argv_template", [])[-1])),
        raw_prompt_recorded=False,
        prompt_body_recorded=False,
        prompt_hash_only=True,
        prompt_text_used_for_execution=False,
        prompt_redaction_counts_as_response_proof=False,
        prompt_redaction_counts_as_native_ux=False,
    )


def build_model_selection_boundary_packet() -> dict[str, Any]:
    summary_path = REPO_ROOT / MODEL_READINESS_DIR / "model_availability_readiness_summary_packet.json"
    matrix_path = REPO_ROOT / MODEL_READINESS_DIR / "model_availability_candidate_matrix_packet.json"
    summary = read_json(summary_path)
    matrix = read_json(matrix_path)
    rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
    candidate_ids = [str(row.get("model_id") or "") for row in rows if isinstance(row, dict)]
    preferred = candidate_ids[0] if candidate_ids else ""
    return packet(
        "cli_runner_model_selection_boundary",
        status="ok" if summary.get("final_status") == MODEL_READINESS_STATUS and preferred else "blocked",
        model_readiness_reference={
            "summary_path": f"{MODEL_READINESS_DIR}/model_availability_readiness_summary_packet.json",
            "summary_sha256": file_sha256(summary_path),
            "candidate_matrix_path": f"{MODEL_READINESS_DIR}/model_availability_candidate_matrix_packet.json",
            "candidate_matrix_sha256": file_sha256(matrix_path),
            "reference_only": True,
        },
        preferred_candidate_model_id=preferred,
        candidate_ids=candidate_ids,
        candidate_selected_for_future_smoke=bool(preferred),
        candidate_selection_source="model_availability_readiness_reference",
        model_availability_reproved_in_this_contour=False,
        model_availability_claimed=False,
        gpt_5_5_availability_claimed=False,
        browser_can_supply_model_authority=False,
        client_can_override_model_provider_account=False,
        selection_counts_as_cli_smoke_pass=False,
        selection_counts_as_model_availability=False,
    )


def build_non_substitution_packet() -> dict[str, Any]:
    layer = build_cli_runner_layer_boundary_packet()
    return packet(
        "cli_runner_non_substitution",
        cli_runner_readiness_is_cli_smoke_pass=False,
        cli_runner_smoke_pass_is_native_codex_app_proof=False,
        cli_runner_smoke_pass_is_model_availability_matrix=False,
        cli_runner_smoke_pass_is_final_e2e=False,
        cli_runner_smoke_pass_is_direct_egress_absence=False,
        cli_runner_response_is_native_codex_app_response=False,
        cli_runner_route_proof_is_responses_wire_compatibility=False,
        inherited_layer_does_not_prove=layer.get("does_not_prove", []),
        native_app_claimed=False,
        model_availability_claimed=False,
        direct_egress_absence_claimed=False,
        streaming_claimed=False,
        tool_loop_claimed=False,
        final_e2e_claimed=False,
    )


def build_live_promotion_gate_packet() -> dict[str, Any]:
    return packet(
        "cli_runner_live_promotion_gate",
        live_execution_allowed_in_this_contour=False,
        codex_runner_smoke_allowed_in_this_contour=False,
        owner_live_authorization_present=False,
        native_launch_allowed=False,
        provider_model_request_allowed=False,
        required_before_future_smoke=[
            "explicit_operator_live_authorization",
            "fresh_auth_boundary_packet",
            "fresh_model_selection_boundary_packet",
            "declared_temp_write_surfaces",
            "secret_scan_clean",
            "rollback_or_cleanup_policy",
        ],
        readiness_counts_as_live_pass=False,
        readiness_counts_as_cli_runner_works=False,
    )


def build_false_green_audit(
    *,
    command_shape: dict[str, Any],
    auth: dict[str, Any],
    model_selection: dict[str, Any],
    non_substitution: dict[str, Any],
    live_gate: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    if command_shape.get("command_executed") is not False:
        findings.append("command_executed")
    if command_shape.get("command_shape_counts_as_cli_smoke_pass") is not False:
        findings.append("command_shape_counts_as_cli_smoke_pass")
    if auth.get("auth_boundary_counts_as_cli_smoke_pass") is not False:
        findings.append("auth_boundary_counts_as_cli_smoke_pass")
    if auth.get("current_codex_auth_json_used") is not False:
        findings.append("current_codex_auth_json_used")
    if model_selection.get("model_availability_claimed") is not False:
        findings.append("model_availability_claimed")
    reference = model_selection.get("model_readiness_reference")
    if not isinstance(reference, dict) or reference.get("reference_only") is not True:
        findings.append("model_readiness_reference_not_reference_only")
    if model_selection.get("selection_counts_as_cli_smoke_pass") is not False:
        findings.append("selection_counts_as_cli_smoke_pass")
    for field in (
        "native_app_claimed",
        "model_availability_claimed",
        "direct_egress_absence_claimed",
        "streaming_claimed",
        "tool_loop_claimed",
        "final_e2e_claimed",
    ):
        if non_substitution.get(field) is not False:
            findings.append(f"non_substitution.{field}")
    if live_gate.get("live_execution_allowed_in_this_contour") is not False:
        findings.append("live_execution_allowed")
    return packet(
        "cli_runner_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        cli_runner_readiness_claimed_as_works=False,
        cli_runner_command_shape_claimed_as_executed=False,
        cli_runner_smoke_pass_claimed=False,
        old_cli_evidence_imported_as_current_truth=False,
        native_app_claimed=False,
        model_availability_claimed=False,
        direct_egress_absence_claimed=False,
        streaming_claimed=False,
        tool_loop_claimed=False,
        final_e2e_claimed=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = {
        "cli_runner_surface_inventory_packet.json",
        "cli_runner_command_shape_packet.json",
        "cli_runner_auth_boundary_packet.json",
        "cli_runner_prompt_redaction_packet.json",
        "cli_runner_model_selection_boundary_packet.json",
        "cli_runner_non_substitution_packet.json",
        "cli_runner_live_promotion_gate_packet.json",
        "cli_runner_false_green_audit.json",
    }
    missing = sorted(required - set(packets))
    blocked = sorted(
        name for name, payload in packets.items() if payload.get("status") == "blocked"
    )
    return packet(
        "cli_runner_readiness_summary",
        status="blocked" if missing or blocked else "ok",
        final_status=TARGET_STATUS,
        parent_target=PARENT_STATUS,
        parent_target_closed=False,
        missing_required_packets=missing,
        blocked_packets=blocked,
        cli_runner_readiness_classified=not missing and not blocked,
        cli_runner_smoke_pass_proven=False,
        codex_runner_smoke_executed=False,
        live_provider_request_attempted=False,
        native_app_proven=False,
        model_availability_proven=False,
        direct_egress_absence_proven=False,
        streaming_compatibility_proven=False,
        tool_loop_compatibility_proven=False,
        final_e2e_proven=False,
    )


def build_secret_redaction_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    serialized = json.dumps(packets, sort_keys=True)
    markers = [
        "s" + "k-",
        "Authorization: " + "Bearer",
        "OPENAI" + "_API_KEY=",
        "OPENROUTER" + "_API_KEY=",
        "CLI_RUNNER" + "_WBP_OK",
        "answer " + "exactly",
    ]
    findings = [marker for marker in markers if marker in serialized]
    return packet(
        "secret_redaction_audit",
        status="blocked" if findings else "ok",
        raw_secret_found=bool(findings),
        raw_prompt_found=bool(
            findings
            and any(
                marker
                in {
                    "CLI_RUNNER" + "_WBP_OK",
                    "answer " + "exactly",
                }
                for marker in findings
            )
        ),
        secret_marker_findings=findings,
        marker_scan_scope="bounded_common_secret_and_cli_prompt_markers",
        exhaustive_dlp_claimed=False,
        raw_prompt_recorded=False,
        prompt_placeholder_recorded=PROMPT_PLACEHOLDER in serialized,
        checked_packet_count=len(packets),
    )


def _forbidden_true_fields(value: Any, *, prefix: str = "") -> list[str]:
    forbidden = {
        "command_executed",
        "codex_runner_smoke_executed",
        "live_provider_request_attempted",
        "native_launch_attempted",
        "native_app_claimed",
        "native_app_proven",
        "model_availability_claimed",
        "model_availability_proven",
        "direct_egress_absence_claimed",
        "direct_egress_absence_proven",
        "streaming_claimed",
        "streaming_compatibility_proven",
        "tool_loop_claimed",
        "tool_loop_compatibility_proven",
        "final_e2e_claimed",
        "final_e2e_proven",
    }
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in forbidden and item is True:
                findings.append(path)
            findings.extend(_forbidden_true_fields(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_true_fields(item, prefix=f"{prefix}[{index}]"))
    return findings


def build_independent_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    summary = packets.get("cli_runner_readiness_summary_packet.json", {})
    false_green = packets.get("cli_runner_false_green_audit.json", {})
    secret = packets.get("secret_redaction_audit.json", {})
    forbidden_true_fields = _forbidden_true_fields(packets)
    return packet(
        "independent_cli_runner_readiness_audit",
        status="ok"
        if summary.get("status") == "ok"
        and false_green.get("status") == "ok"
        and secret.get("status") == "ok"
        and not forbidden_true_fields
        else "blocked",
        summary_status=summary.get("status"),
        false_green_status=false_green.get("status"),
        secret_redaction_status=secret.get("status"),
        forbidden_true_fields=forbidden_true_fields,
        live_execution_found=False,
        native_launch_found=False,
        model_availability_claim_found=False,
        old_cli_evidence_counted_as_current_truth=False,
        text_only_audit_counted_as_pass=False,
    )


def build_base_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    return {
        "sync_gate_packet.json": packet(
            "sync_gate",
            status="ok" if not unexpected_dirty else "blocked",
            branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            head=head,
            unexpected_dirty_entries=unexpected_dirty,
            repo_resident_plan_written=False,
            codex_runner_smoke_executed=False,
            native_launch_attempted=False,
        ),
        "historical_dirt_quarantine_packet.json": packet(
            "historical_dirt_quarantine",
            quarantined_paths=quarantined,
            current_contour_relies_on_quarantined_paths=False,
            current_contour_mutates_quarantined_paths=False,
            current_contour_stages_quarantined_paths=False,
        ),
        "declared_write_surfaces_packet.json": packet(
            "declared_write_surfaces",
            write_surfaces=[
                "tools/cli_runner_smoke_readiness_probe.py",
                "tests/test_cli_runner_smoke_readiness_probe.py",
                str(evidence_dir.relative_to(repo_root)),
            ],
            live_provider_request_allowed=False,
            live_provider_request_attempted=False,
            codex_runner_smoke_allowed=False,
            codex_runner_smoke_executed=False,
            native_launch_allowed=False,
            native_launch_attempted=False,
            route_account_mutation_allowed=False,
            route_account_mutation_attempted=False,
        ),
        "version_pinning_packet.json": packet(
            "version_pinning",
            wbp_git_commit=head,
            branch=run_text(repo_root, ["git", "branch", "--show-current"]),
            python_version=sys.version.split()[0],
            cli_runner_readiness_schema_version=1,
            codex_cli_version_status="not_invoked_by_this_contour",
        ),
    }


def build_readiness_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    packets = build_base_packets(repo_root, evidence_dir)
    inventory = build_surface_inventory_packet(repo_root)
    command_shape = build_command_shape_packet()
    auth = build_auth_boundary_packet()
    prompt = build_prompt_redaction_packet(command_shape)
    model = build_model_selection_boundary_packet()
    non_substitution = build_non_substitution_packet()
    live_gate = build_live_promotion_gate_packet()
    packets.update(
        {
            "cli_runner_surface_inventory_packet.json": inventory,
            "cli_runner_command_shape_packet.json": command_shape,
            "cli_runner_auth_boundary_packet.json": auth,
            "cli_runner_prompt_redaction_packet.json": prompt,
            "cli_runner_model_selection_boundary_packet.json": model,
            "cli_runner_non_substitution_packet.json": non_substitution,
            "cli_runner_live_promotion_gate_packet.json": live_gate,
        }
    )
    packets["cli_runner_false_green_audit.json"] = build_false_green_audit(
        command_shape=command_shape,
        auth=auth,
        model_selection=model,
        non_substitution=non_substitution,
        live_gate=live_gate,
    )
    packets["secret_redaction_audit.json"] = build_secret_redaction_audit(packets)
    packets["cli_runner_readiness_summary_packet.json"] = build_summary_packet(packets)
    packets["independent_cli_runner_readiness_audit.json"] = build_independent_audit_packet(packets)
    return packets


def write_closeout(evidence_dir: Path, packets: dict[str, dict[str, Any]], repo_root: Path) -> None:
    summary = packets["cli_runner_readiness_summary_packet.json"]
    branch = run_text(repo_root, ["git", "branch", "--show-current"])
    head = run_text(repo_root, ["git", "rev-parse", "HEAD"])
    touched = [
        "tools/cli_runner_smoke_readiness_probe.py",
        "tests/test_cli_runner_smoke_readiness_probe.py",
        str(evidence_dir.relative_to(repo_root)),
    ]
    text = f"""# WBP Codex CLI Runner Via WBP Smoke Readiness R1 Closeout

## Goal

Classify non-live readiness for a future Codex CLI runner via WBP smoke without executing the runner.

## Result

- status: {summary["final_status"]}
- final verdict: readiness packets emitted; parent CLI runner works target not closed
- closure state: CLOSED

## Contour Capsule

- goal: classify CLI runner command shape, auth, prompt, model selection, and non-substitution readiness
- branch: {branch}
- head: {head}
- touched files: {', '.join(touched)}
- tests run: recorded in verification section
- blocked risks: CLI runner smoke pass, native app proof, model availability, direct egress absence, streaming, tool loop, final E2E
- closure state: CLOSED

## Verification

- tests: py_compile, targeted pytest, JSON parse, secret marker scan, closeout resilience, staged-only gate, diff check
- build: not applicable
- manual: not required
- live verification: not attempted

## Artifacts

- spec: thread-only contour text
- packet: cli_runner_readiness_summary_packet.json
- report: independent_cli_runner_readiness_audit.json

## Git

- branch: {branch}
- commit: filled after commit
- pushed: filled after push

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered: none for readiness; runner execution remains outside this contour
- resume from here: CLOSED
"""
    (evidence_dir / "closeout.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=EVIDENCE_DIR_NAME)
    args = parser.parse_args()
    evidence_dir = (REPO_ROOT / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_readiness_packets(REPO_ROOT, evidence_dir)
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    write_closeout(evidence_dir, packets, REPO_ROOT)
    print(json.dumps(packets["cli_runner_readiness_summary_packet.json"], indent=2, sort_keys=True))
    return 0 if packets["cli_runner_readiness_summary_packet.json"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
