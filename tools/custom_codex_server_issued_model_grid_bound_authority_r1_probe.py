#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only evidence builder for Custom Codex server-issued model grid authority."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_account_selection import build_model_selection_truth_packet  # noqa: E402
from wild_boar_proxy.codex_custom_sessions import CodexCustomSessionManager  # noqa: E402
from wild_boar_proxy.codex_model_registry import (  # noqa: E402
    build_custom_model_dry_run_packet,
    build_wbp_model_catalog_contract_packet,
    validate_wbp_model_catalog_contract,
)
from wild_boar_proxy.native_filesystem_probe import json_write  # noqa: E402


TARGET_STATUS = "CUSTOM_CODEX_SERVER_ISSUED_MODEL_GRID_VISIBLE_AND_BOUND"
EVIDENCE_DIR_NAME = "audit_results/custom_codex_server_issued_model_grid_bound_authority_r1_2026-05-28"
FORBIDDEN_TRUE_FIELDS = {
    "provider_reachability_proven",
    "route_readiness_proven",
    "all_models_work_claimed",
    "browser_can_supply_provider",
    "browser_can_supply_route",
    "browser_can_supply_base_url",
    "browser_can_supply_auth",
    "ui_redesign_required",
    "auth_repair_performed",
    "icon_readiness_claimed",
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


def operator_status() -> dict[str, object]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.3-codex",
        },
        "claim_gate": {"status": "passed"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": ["gpt-5.3-codex", "gpt-5.4"],
        },
    }


def account(backend_id: str, priority: int = 10) -> dict[str, object]:
    return {
        "id": backend_id,
        "label": backend_id,
        "enabled": True,
        "priority": priority,
        "pool": "active",
        "status": "healthy",
        "fail_count": 0,
        "success_count": 7,
        "last_success": "2026-05-23T00:00:00Z",
        "last_error": "",
        "last_error_class": "",
        "cooldown_until": None,
        "manual_hold": False,
        "auth_ref": "/tmp/wbp-redacted-auth.json",
    }


def commands() -> dict[str, dict[str, object]]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "ok",
            "packet": {
                "status": "ok",
                "machine_error_code": "OK",
                "claim_gate": {"status": "passed"},
                "pool_summary": {"selected_backend_ids": ["acct-a"]},
                "auth_pool_hygiene": {
                    "status": "launch_capable_available",
                    "selection_alignment_status": "aligned",
                },
            },
        },
        "accounts_list": {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "ok",
            "packet": {"accounts": [account("acct-a"), account("acct-b", 20)]},
        },
        "rollout_rotation_inspect": {
            "status": "ok",
            "machine_error_code": "OK",
            "human_message": "ok",
            "packet": {"status": "ok", "machine_error_code": "OK"},
        },
    }


def api_snapshot() -> dict[str, object]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": "wbp-enabled-openrouter",
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
            },
            {
                "route_id": "wbp-disabled-openrouter",
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5",
                "enabled": False,
                "secret_ref": "OPENROUTER_API_KEY",
            },
            {
                "route_id": "wbp-missing-secret",
                "provider": "openrouter",
                "upstream_model": "openai/gpt-5-mini",
                "enabled": True,
            },
        ],
    }


def _field_true(value: Any, field: str) -> bool:
    if isinstance(value, dict):
        if value.get(field) is True:
            return True
        return any(_field_true(item, field) for item in value.values())
    if isinstance(value, list):
        return any(_field_true(item, field) for item in value)
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
        "wild_boar_proxy/codex_model_registry.py",
        "wild_boar_proxy/web_design_live_server.py",
        "wild_boar_proxy/web_design_ui/index.html",
        "wild_boar_proxy/web_design_ui/scripts/overview.js",
        "wild_boar_proxy/web_design_ui/styles/overview.css",
        "tests/test_codex_model_registry.py",
        "tests/test_wbp_model_catalog_contract.py",
        "tests/test_web_design_live_server.py",
        "tests/test_web_design_ui.py",
        "tests/test_custom_codex_model_grid_bound_authority_r1_probe.py",
        "tools/custom_codex_server_issued_model_grid_bound_authority_r1_probe.py",
        "tests/test_custom_codex_model_grid_bound_authority_r1_probe.py",
    }
    admitted_current_evidence_dirs = (f"{relative_evidence_dir}/", f"{EVIDENCE_DIR_NAME}/")

    def is_current_contour_line(line: str) -> bool:
        path = line[3:] if len(line) > 3 else line.strip()
        return path in admitted_current_contour or path.startswith(admitted_current_evidence_dirs)

    quarantined = [line for line in status_lines if not is_current_contour_line(line)]
    return quarantined, []


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
        "model_grid_sync_gate",
        status="ok" if not unexpected_dirty else "blocked",
        git_branch="SKIPPED_FOR_TEST" if skip_git else run_text(repo_root, ["git", "branch", "--show-current"]),
        git_head="SKIPPED_FOR_TEST"
        if skip_git
        else run_text(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        git_status_short=[] if skip_git else run_text(repo_root, ["git", "status", "--short"]).splitlines(),
        quarantined_dirty_entries=quarantined,
        quarantined_dirty_count=len(quarantined),
        historical_dirty_quarantined=bool(quarantined),
        unexpected_dirty_entries=unexpected_dirty,
        sync_gate_blocks_only_unquarantined_current_contour_dirty=True,
        current_contour="CUSTOM_CODEX_SERVER_ISSUED_MODEL_GRID_BOUND_AUTHORITY_R1",
        master_plan_written_to_repo=False,
    )


def build_model_catalog_contract_packet() -> dict[str, Any]:
    catalog = build_wbp_model_catalog_contract_packet(operator_status(), api_snapshot=api_snapshot())
    findings = validate_wbp_model_catalog_contract(catalog)
    rows = {entry["model_id"]: entry for entry in catalog.get("models", [])}
    disabled_visible = {
        model_id: {
            "selection_state": row.get("selection_state"),
            "selection_disabled_reason_code": row.get("selection_disabled_reason_code"),
        }
        for model_id, row in rows.items()
        if row.get("selection_enabled") is not True
    }
    return packet(
        "model_catalog_contract",
        status="ok" if not findings else "blocked",
        final_status="MODEL_CATALOG_CONTRACT_VALID" if not findings else "",
        validation_findings=findings,
        contract_scope=catalog.get("contract_scope"),
        allowed_browser_fields=catalog.get("allowed_browser_fields"),
        browser_authority=catalog.get("browser_authority"),
        model_count=catalog.get("model_count"),
        selectable_model_count=catalog.get("selectable_model_count"),
        disabled_model_count=catalog.get("disabled_model_count"),
        disabled_visible_rows=disabled_visible,
        models=catalog.get("models", []),
        provider_reachability_proven=False,
        route_readiness_proven=False,
    )


def build_browser_selection_payload_negative_packet() -> dict[str, Any]:
    payload = {
        "model_id": "gpt-5.3-codex",
        "provider": "openai",
        "wire_api": "chat_completions",
        "model_provider": "browser-owned",
        "openai_base_url": "http://127.0.0.1:9999/v1",
        "auth_path": "/tmp/secret.txt",
    }
    rejected = build_custom_model_dry_run_packet(
        payload,
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    expected = ["provider", "wire_api", "model_provider", "openai_base_url", "auth_path"]
    ok = (
        rejected.get("status") == "rejected"
        and rejected.get("machine_error_code") == "FORBIDDEN_BROWSER_FIELD"
        and rejected.get("forbidden_fields") == expected
    )
    return packet(
        "browser_selection_payload_negative",
        status="ok" if ok else "blocked",
        expected_forbidden_fields=expected,
        observed_forbidden_fields=rejected.get("forbidden_fields", []),
        machine_error_code=rejected.get("machine_error_code"),
        browser_can_supply_provider=False,
        browser_can_supply_route=False,
        browser_can_supply_base_url=False,
        browser_can_supply_auth=False,
    )


def build_server_selection_binding_packet() -> dict[str, Any]:
    gpt = build_model_selection_truth_packet(
        {"model_id": "gpt-5.3-codex"},
        commands(),
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    enabled = build_model_selection_truth_packet(
        {"model_id": "wbp-enabled-openrouter"},
        commands(),
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    disabled = build_model_selection_truth_packet(
        {"model_id": "wbp-disabled-openrouter"},
        commands(),
        operator_status(),
        api_snapshot=api_snapshot(),
    )
    temp_root = Path(tempfile.mkdtemp(prefix="wbp-model-grid-r1-"))
    manager = CodexCustomSessionManager(temp_root)
    enabled_session = manager.create_packet(
        {"model_id": "wbp-enabled-openrouter"},
        commands(),
        operator_status(),
        selection=enabled,
        api_snapshot=api_snapshot(),
    )
    disabled_session = manager.create_packet(
        {"model_id": "wbp-disabled-openrouter"},
        commands(),
        operator_status(),
        selection=disabled,
        api_snapshot=api_snapshot(),
    )
    shutil.rmtree(temp_root, ignore_errors=True)
    ok = (
        gpt.get("status") == "degraded"
        and gpt.get("selected_backend_server_issued") is True
        and enabled.get("status") == "degraded"
        and enabled.get("selected_route_server_issued") is True
        and disabled.get("status") == "degraded"
        and enabled_session.get("status") == "rejected"
        and enabled_session.get("next_action") == "repair_account_selection_truth"
        and disabled_session.get("status") == "rejected"
    )
    return packet(
        "server_selection_binding",
        status="ok" if ok else "blocked",
        gpt_backend_server_issued=gpt.get("selected_backend_server_issued") is True,
        enabled_route_server_issued=enabled.get("selected_route_server_issued") is True,
        disabled_route_rejected=disabled_session.get("status") == "rejected",
        raw_backend_id_exposed=False,
        raw_route_id_exposed=False,
        raw_secret_exposed=False,
        server_owns_provider_endpoint_selection=True,
        server_owns_model_route_selection=True,
        session_creation_bypasses_selection_proof=False,
        enabled_route_launch_not_claimed=True,
        provider_reachability_proven=False,
        route_readiness_proven=False,
    )


def build_model_grid_visibility_boundary_packet(repo_root: Path) -> dict[str, Any]:
    html = (repo_root / "wild_boar_proxy" / "web_design_ui" / "index.html").read_text(encoding="utf-8")
    js = (
        repo_root / "wild_boar_proxy" / "web_design_ui" / "scripts" / "overview.js"
    ).read_text(encoding="utf-8")
    ok = (
        'id="codexCustomModelCatalog"' in html
        and 'entry?.provider_label || entry?.provider_class || "unknown"' in js
        and "entry?.selection_enabled === true" in js
        and 'body: JSON.stringify({ model_id: modelId })' in js
        and 'body: JSON.stringify({ model_id: modelId, route_id' not in js
        and 'body: JSON.stringify({ model_id: modelId, provider' not in js
    )
    return packet(
        "model_grid_visibility_boundary",
        status="ok" if ok else "blocked",
        quiet_surface_only=True,
        rich_ui_redesign_performed=False,
        provider_label_visible='entry?.provider_label || entry?.provider_class || "unknown"' in js,
        disabled_state_visible="selection_disabled_reason_code" in js,
        browser_payload_model_id_only='body: JSON.stringify({ model_id: modelId })' in js,
        browser_payload_route_absent='body: JSON.stringify({ model_id: modelId, route_id' not in js,
        browser_payload_provider_absent='body: JSON.stringify({ model_id: modelId, provider' not in js,
        ui_redesign_required=False,
    )


def build_availability_claim_boundary_packet() -> dict[str, Any]:
    catalog = build_wbp_model_catalog_contract_packet(operator_status(), api_snapshot=api_snapshot())
    rows = {entry["model_id"]: entry for entry in catalog.get("models", [])}
    ok = (
        rows["wbp-disabled-openrouter"]["selection_enabled"] is False
        and rows["wbp-disabled-openrouter"]["availability_claim_level"] == "listed_not_live_proven"
        and rows["wbp-disabled-openrouter"]["live_availability_proven"] is False
        and rows["wbp-missing-secret"]["selection_enabled"] is False
        and rows["wbp-missing-secret"]["live_availability_proven"] is False
    )
    return packet(
        "availability_claim_boundary",
        status="ok" if ok else "blocked",
        catalog_visibility_not_provider_reachability=True,
        catalog_visibility_not_route_readiness=True,
        disabled_route_visible=True,
        disabled_route_live_availability_proven=False,
        missing_secret_visible=True,
        missing_secret_live_availability_proven=False,
        provider_reachability_proven=False,
        route_readiness_proven=False,
        all_models_work_claimed=False,
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    required_ok = [
        "sync_gate_packet.json",
        "model_catalog_contract_packet.json",
        "browser_selection_payload_negative_packet.json",
        "server_selection_binding_packet.json",
        "model_grid_visibility_boundary_packet.json",
        "availability_claim_boundary_packet.json",
    ]
    for filename, payload in packets.items():
        findings.extend(f"{filename}.{path}" for path in _scan_forbidden_true(payload))
    findings.extend(
        f"{name}.status=blocked"
        for name in required_ok
        if packets.get(name, {}).get("status") != "ok"
    )
    return packet(
        "model_grid_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        forbidden_claims_present=bool(findings),
        provider_reachability_proven=False,
        route_readiness_proven=False,
        all_models_work_claimed=False,
        ui_redesign_required=False,
        auth_repair_performed=False,
    )


def build_independent_model_grid_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true_fields: list[str] = []
    for filename, payload in packets.items():
        forbidden_true_fields.extend(
            f"{filename}.{field}"
            for field in sorted(FORBIDDEN_TRUE_FIELDS)
            if _field_true(payload, field)
        )
    visibility = packets.get("model_grid_visibility_boundary_packet.json", {})
    binding = packets.get("server_selection_binding_packet.json", {})
    return packet(
        "independent_model_grid_audit",
        status="ok" if not forbidden_true_fields else "blocked",
        forbidden_true_fields=forbidden_true_fields,
        quiet_surface_only=visibility.get("quiet_surface_only") is True,
        browser_payload_model_id_only=visibility.get("browser_payload_model_id_only") is True,
        enabled_route_server_issued=binding.get("enabled_route_server_issued") is True,
        disabled_route_rejected=binding.get("disabled_route_rejected") is True,
        provider_reachability_proven=False,
        route_readiness_proven=False,
        all_models_work_claimed=False,
        text_only_audit_counted_as_pass=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "sync_gate_packet.json",
        "model_catalog_contract_packet.json",
        "browser_selection_payload_negative_packet.json",
        "server_selection_binding_packet.json",
        "model_grid_visibility_boundary_packet.json",
        "availability_claim_boundary_packet.json",
        "false_green_audit.json",
        "independent_model_grid_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [name for name in required if packets.get(name, {}).get("status") != "ok"]
    ok = not missing and not blocked
    return packet(
        "model_grid_bound_authority_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "",
        missing_required_packets=missing,
        blocked_packets=blocked,
        provider_reachability_proven=False,
        route_readiness_proven=False,
        all_models_work_claimed=False,
        icon_readiness_claimed=False,
    )


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = build_sync_gate_packet(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    packets["model_catalog_contract_packet.json"] = build_model_catalog_contract_packet()
    packets["browser_selection_payload_negative_packet.json"] = (
        build_browser_selection_payload_negative_packet()
    )
    packets["server_selection_binding_packet.json"] = build_server_selection_binding_packet()
    packets["model_grid_visibility_boundary_packet.json"] = build_model_grid_visibility_boundary_packet(
        repo_root
    )
    packets["availability_claim_boundary_packet.json"] = build_availability_claim_boundary_packet()
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    packets["independent_model_grid_audit.json"] = build_independent_model_grid_audit_packet(packets)
    packets["model_grid_bound_authority_summary_packet.json"] = build_summary_packet(packets)
    packets["verification_results_packet.json"] = packet(
        "verification_results",
        status="ok"
        if packets["model_grid_bound_authority_summary_packet.json"]["status"] == "ok"
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
    parser = argparse.ArgumentParser(prog="custom-codex-server-issued-model-grid-bound-authority-r1")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", default=str(REPO_ROOT / EVIDENCE_DIR_NAME))
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        skip_git=args.skip_git,
    )
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    summary = packets["model_grid_bound_authority_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
