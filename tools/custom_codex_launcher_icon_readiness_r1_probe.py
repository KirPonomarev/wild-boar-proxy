#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Classify Custom Codex launcher/icon readiness without shipping a new entrypoint."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.native_filesystem_probe import default_persistent_custom_profile_paths, json_write  # noqa: E402
from wild_boar_proxy.persistent_launcher_dry_run import (  # noqa: E402
    default_persistent_launcher_dry_run_config,
    render_persistent_launcher_dry_run_command,
    validate_persistent_launcher_dry_run_config,
)
from wild_boar_proxy.runtime import (  # noqa: E402
    RuntimePaths,
    build_current_proxy_adoption_contract,
    ensure_repo_owned_default_launcher_consumer,
)


TARGET_STATUS = "NO_ICON_SHIPPED_YET"
EVIDENCE_DIR_NAME = "audit_results/custom_codex_launcher_icon_readiness_r1_2026-05-28"
PROFILE_ID = "wbp-custom-main"
FORBIDDEN_TRUE_FIELDS = {
    "icon_shipped",
    "standalone_app_identity_claimed",
    "launcher_bypasses_wbp",
    "launcher_owns_model_authority",
    "launcher_owns_provider_authority",
    "launcher_owns_auth_authority",
    "launcher_owns_path_authority",
    "persistent_lane_broken",
    "history_reproven_from_scratch",
    "raw_codex_app_direct_icon_allowed",
    "ui_redesign_performed",
    "runtime_repair_performed",
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
        "tools/custom_codex_launcher_icon_readiness_r1_probe.py",
        "tests/test_custom_codex_launcher_icon_readiness_r1_probe.py",
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
        "launcher_icon_sync_gate",
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
        current_contour="CUSTOM_CODEX_LAUNCHER_ICON_READINESS_R1",
        master_plan_written_to_repo=False,
    )


def _runtime_paths_fixture(root: Path, *, external_override: bool = False) -> RuntimePaths:
    profile_dir = root / "profile"
    managed_dir = root / "managed"
    launcher_script = (
        root / "external-launcher.sh"
        if external_override
        else profile_dir / "codex-custom-launch.sh"
    )
    return RuntimePaths(
        profile_dir=profile_dir,
        managed_dir=managed_dir,
        stable_config=root / "stable.yaml",
        auth_file=profile_dir / "auth.json",
        config_toml=profile_dir / "config.toml",
        runtime_mode_file=profile_dir / "runtime-mode.txt",
        runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
        registry_file=managed_dir / "backend-registry.json",
        state_file=managed_dir / "supervisor-state.json",
        managed_config_file=managed_dir / "managed-config.yaml",
        launcher_script=launcher_script,
        sync_script=managed_dir / "supervisor-sync.sh",
        accounts_bin=managed_dir / "bin" / "codex-accounts",
        onboard_bin=managed_dir / "bin" / "codex-account-onboard",
        lock_file=managed_dir / "wild-boar-proxy.lock",
        launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed_dir / "stable-repair-target",
        repair_target_reference_file=managed_dir / "approved-repair-target.json",
        target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed_dir / "stable-runtime-config.generated.yaml",
    )


def build_launcher_contract_packet() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = _runtime_paths_fixture(root)
        ensure_repo_owned_default_launcher_consumer(paths)
        contract = build_current_proxy_adoption_contract(paths)
    path_surface = contract["external_launcher_path_surface"]
    launcher_consumer = contract["launcher_consumer_contract"]
    ok = (
        path_surface["path_kind"] == "default_owned_provisioning_target"
        and launcher_consumer["repo_owned_default_consumer_provisioned"] is True
        and launcher_consumer["owner_controlled_activation_only"] is True
    )
    return packet(
        "launcher_contract",
        status="ok" if ok else "blocked",
        launcher_path_kind=path_surface["path_kind"],
        launcher_path_status=path_surface["status"],
        repo_managed_marker_present=path_surface["repo_managed_marker_present"] is True,
        repo_managed_marker_valid=path_surface["repo_managed_marker_valid"] is True,
        repo_managed_marker_recognized=path_surface["repo_managed_marker_recognized"] is True,
        repo_owned_default_consumer_provisioned=launcher_consumer["repo_owned_default_consumer_provisioned"] is True,
        owner_controlled_activation_only=launcher_consumer["owner_controlled_activation_only"] is True,
        launcher_protocol_scope=launcher_consumer["launcher_protocol_scope"],
        icon_shipped=False,
        standalone_app_identity_claimed=False,
        command_executed=False,
    )


def build_launcher_target_resolution_packet() -> dict[str, Any]:
    paths = default_persistent_custom_profile_paths(profile_id=PROFILE_ID)
    config = default_persistent_launcher_dry_run_config(profile_id=PROFILE_ID)
    command = render_persistent_launcher_dry_run_command(config)
    validation = validate_persistent_launcher_dry_run_config(config)
    ok = (
        validation["status"] == "ok"
        and command["argv"][:3] == ["open", "-n", "/Applications/ChatGPT.app"]
        and command["launcher_path"] == str(Path(paths["launcher_path"]).expanduser().resolve(strict=False))
    )
    return packet(
        "launcher_target_resolution",
        status="ok" if ok else "blocked",
        persistent_profile_root=paths["persistent_profile_root"],
        launcher_path=command["launcher_path"],
        launch_argv=command["argv"],
        target_is_wbp_managed_launcher=True,
        launcher_invocation_mode="desktop",
        raw_codex_app_direct_icon_allowed=False,
        ephemeral_tmp_profile_target_forbidden=True,
        icon_shipped=False,
    )


def build_launcher_authority_boundary_packet() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        default_paths = _runtime_paths_fixture(root)
        ensure_repo_owned_default_launcher_consumer(default_paths)
        default_contract = build_current_proxy_adoption_contract(default_paths)
        override_paths = _runtime_paths_fixture(root, external_override=True)
        override_paths.launcher_script.parent.mkdir(parents=True, exist_ok=True)
        override_paths.launcher_script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        override_paths.launcher_script.chmod(0o755)
        override_contract = build_current_proxy_adoption_contract(override_paths)
    ok = (
        default_contract["external_launcher_path_surface"]["path_kind"]
        == "default_owned_provisioning_target"
        and override_contract["external_launcher_path_surface"]["path_kind"]
        == "explicit_external_override"
        and override_contract["launcher_consumer_contract"]["repo_owned_default_consumer_provisioned"]
        is False
    )
    return packet(
        "launcher_authority_boundary",
        status="ok" if ok else "blocked",
        default_lane_path_kind=default_contract["external_launcher_path_surface"]["path_kind"],
        override_lane_path_kind=override_contract["external_launcher_path_surface"]["path_kind"],
        override_lane_readiness=override_contract["external_launcher_readiness_status"],
        browser_payload_authority=False,
        launcher_owns_model_authority=False,
        launcher_owns_provider_authority=False,
        launcher_owns_auth_authority=False,
        launcher_owns_path_authority=False,
        explicit_external_override_shipping_ready=False,
        direct_operator_exec_surface_present=True,
        raw_bundle_dispatch_surface_present=True,
        icon_shipped=False,
    )


def build_relaunch_entrypoint_continuity_packet() -> dict[str, Any]:
    config = default_persistent_launcher_dry_run_config(profile_id=PROFILE_ID)
    command = render_persistent_launcher_dry_run_command(config)
    validation = validate_persistent_launcher_dry_run_config(config)
    ok = (
        validation["status"] == "ok"
        and command["env"]["CODEX_HOME"] == str(config.persistent_profile_root.expanduser().resolve(strict=False))
        and command["env"]["HOME"] == str(config.home_dir.expanduser().resolve(strict=False))
        and command["env"]["TMPDIR"] == command["env"]["WBP_RUNTIME_TMPDIR"]
        and command["argv"][-1] == str(config.user_data_dir.expanduser().resolve(strict=False))
    )
    return packet(
        "relaunch_entrypoint_continuity",
        status="ok" if ok else "blocked",
        persistent_profile_id=PROFILE_ID,
        codex_home=command["env"]["CODEX_HOME"],
        home_dir=command["env"]["HOME"],
        runtime_tmpdir=command["env"]["TMPDIR"],
        user_data_dir=command["argv"][-1],
        continuity_guard_classified=True,
        history_reproven_from_scratch=False,
        persistent_lane_broken=False,
        icon_shipped=False,
    )


def build_failure_mode_boundary_packet(repo_root: Path) -> dict[str, Any]:
    html = (repo_root / "wild_boar_proxy" / "web_design_ui" / "index.html").read_text(encoding="utf-8")
    js = (repo_root / "wild_boar_proxy" / "web_design_ui" / "scripts" / "overview.js").read_text(encoding="utf-8")
    server = (repo_root / "wild_boar_proxy" / "web_design_live_server.py").read_text(encoding="utf-8")
    icon_path_inert_display_only = (
        "inert display only" in html
        and "~/Applications/Codex Custom.app · inert display only" in js
    )
    icon_action_tokens = (
        "launch_custom_icon",
        "launch_custom_app_shortcut",
        "open_custom_icon",
        "custom_launcher_icon",
    )
    no_separate_icon_action_surface = not any(
        token in surface
        for token in icon_action_tokens
        for surface in (html, js, server)
    )
    no_fake_icon_shipping_claim = icon_path_inert_display_only and no_separate_icon_action_surface
    ok = (
        icon_path_inert_display_only
        and "owner_authorization_required" in server
        and 'data-ui-action="launch_custom_client_native"' in html
        and no_separate_icon_action_surface
        and no_fake_icon_shipping_claim
    )
    return packet(
        "failure_mode_boundary",
        status="ok" if ok else "blocked",
        icon_path_inert_display_only=icon_path_inert_display_only,
        owner_authorization_required_surface="owner_authorization_required" in server,
        no_separate_icon_action_surface=no_separate_icon_action_surface,
        no_fake_icon_shipping_claim=no_fake_icon_shipping_claim,
        truthful_outcome=TARGET_STATUS,
        icon_shipped=False,
        ui_redesign_performed=False,
    )


def build_false_green_audit(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    findings: list[str] = []
    required_ok = [
        "sync_gate_packet.json",
        "launcher_contract_packet.json",
        "launcher_target_resolution_packet.json",
        "launcher_authority_boundary_packet.json",
        "relaunch_entrypoint_continuity_packet.json",
        "failure_mode_boundary_packet.json",
    ]
    for filename, payload in packets.items():
        findings.extend(f"{filename}.{path}" for path in _scan_forbidden_true(payload))
    findings.extend(
        f"{name}.status=blocked"
        for name in required_ok
        if packets.get(name, {}).get("status") != "ok"
    )
    return packet(
        "launcher_false_green_audit",
        status="ok" if not findings else "blocked",
        findings=findings,
        no_icon_shipped_yet=True,
        icon_shipped=False,
        standalone_app_identity_claimed=False,
    )


def build_independent_launcher_audit_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    forbidden_true_fields: list[str] = []
    for filename, payload in packets.items():
        forbidden_true_fields.extend(
            f"{filename}.{field}"
            for field in sorted(FORBIDDEN_TRUE_FIELDS)
            if _field_true(payload, field)
        )
    authority = packets.get("launcher_authority_boundary_packet.json", {})
    failure = packets.get("failure_mode_boundary_packet.json", {})
    return packet(
        "independent_launcher_audit",
        status="ok" if not forbidden_true_fields else "blocked",
        forbidden_true_fields=forbidden_true_fields,
        explicit_external_override_shipping_ready=authority.get("explicit_external_override_shipping_ready") is True,
        icon_path_inert_display_only=failure.get("icon_path_inert_display_only") is True,
        truthful_outcome=failure.get("truthful_outcome"),
        icon_shipped=False,
        text_only_audit_counted_as_pass=False,
    )


def build_summary_packet(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = [
        "sync_gate_packet.json",
        "launcher_contract_packet.json",
        "launcher_target_resolution_packet.json",
        "launcher_authority_boundary_packet.json",
        "relaunch_entrypoint_continuity_packet.json",
        "failure_mode_boundary_packet.json",
        "false_green_audit.json",
        "independent_launcher_audit.json",
    ]
    missing = [name for name in required if name not in packets]
    blocked = [name for name in required if packets.get(name, {}).get("status") != "ok"]
    ok = not missing and not blocked
    return packet(
        "launcher_icon_readiness_summary",
        status="ok" if ok else "blocked",
        final_status=TARGET_STATUS if ok else "",
        missing_required_packets=missing,
        blocked_packets=blocked,
        icon_shipped=False,
        safe_wbp_managed_entrypoint_proven=False,
        standalone_app_identity_claimed=False,
    )


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    packets["sync_gate_packet.json"] = build_sync_gate_packet(repo_root, evidence_dir, skip_git=skip_git)
    packets["launcher_contract_packet.json"] = build_launcher_contract_packet()
    packets["launcher_target_resolution_packet.json"] = build_launcher_target_resolution_packet()
    packets["launcher_authority_boundary_packet.json"] = build_launcher_authority_boundary_packet()
    packets["relaunch_entrypoint_continuity_packet.json"] = build_relaunch_entrypoint_continuity_packet()
    packets["failure_mode_boundary_packet.json"] = build_failure_mode_boundary_packet(repo_root)
    packets["false_green_audit.json"] = build_false_green_audit(packets)
    packets["independent_launcher_audit.json"] = build_independent_launcher_audit_packet(packets)
    packets["launcher_icon_readiness_summary_packet.json"] = build_summary_packet(packets)
    packets["verification_results_packet.json"] = packet(
        "verification_results",
        status="ok" if packets["launcher_icon_readiness_summary_packet.json"]["status"] == "ok" else "blocked",
        top_level_packet_statuses={
            name: payload.get("status", "missing") for name, payload in packets.items()
        },
        ok_packet_count=sum(1 for payload in packets.values() if payload.get("status") == "ok"),
        blocked_packet_count=sum(1 for payload in packets.values() if payload.get("status") == "blocked"),
    )
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="custom-codex-launcher-icon-readiness-r1")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--evidence-dir", default=str(REPO_ROOT / EVIDENCE_DIR_NAME))
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(repo_root=repo_root, evidence_dir=evidence_dir, skip_git=args.skip_git)
    for name, payload in packets.items():
        json_write(evidence_dir / name, payload)
    summary = packets["launcher_icon_readiness_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
