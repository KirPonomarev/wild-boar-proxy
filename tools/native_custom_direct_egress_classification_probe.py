#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded native Custom direct-egress classifier.

This probe observes a single isolated Codex Custom launch tree with `lsof`.
It classifies only bounded direct non-WBP model egress for that run; it does not
claim global network absence, machine UI proof, filesystem safety, provider
compatibility, Original Codex via WBP, or final E2E.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wild_boar_proxy.native_filesystem_probe import (
    RuntimePaths,
    build_native_direct_egress_capability_packet,
    build_native_direct_egress_claim_packet,
    build_native_direct_egress_false_green_audit,
    build_wbp_trace_observation_packet,
    clean_env,
    collect_codex_process_inventory,
    create_native_probe_layout,
    json_write,
    materialize_probe_profile,
    remove_tree_with_retry,
    terminate_custom_processes,
)
from wild_boar_proxy.operator_surface import OwnerSideProcessNetworkObserver, WbpTraceObserver
from wild_boar_proxy.token_command import emit_local_token


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _endpoint_hostport(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if not parsed.hostname or not parsed.port:
        return ""
    return f"{parsed.hostname}:{parsed.port}"


def _background_noise_packet(
    *,
    launch_packet: dict[str, Any],
    after_inventory: dict[str, Any],
    network_packet: dict[str, Any],
) -> dict[str, Any]:
    allowed_basenames = {
        "Codex",
        "Codex Helper",
        "Codex Helper (Renderer)",
        "codex",
        "git",
        "git-remote-http",
        "git-remote-https",
        "sh",
        "bash",
        "zsh",
    }
    unexpected_peer_commands = sorted(
        {
            str(peer.get("command_basename") or "")
            for peer in network_packet.get("peer_endpoints", [])
            if isinstance(peer, dict)
            and str(peer.get("command_basename") or "")
            and str(peer.get("command_basename") or "") not in allowed_basenames
        }
    )
    before_default = int(
        launch_packet.get("before_process_inventory", {}).get("default_process_count") or 0
    )
    after_default = int(after_inventory.get("default_process_count") or 0)
    default_codex_drift = after_default > before_default
    background_noise_detected = bool(unexpected_peer_commands) or default_codex_drift
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_background_codex_noise",
        "status": "blocked" if background_noise_detected else "ok",
        "background_codex_noise_detected": background_noise_detected,
        "unexpected_peer_command_basenames": unexpected_peer_commands,
        "default_process_count_before": before_default,
        "default_process_count_after": after_default,
        "default_codex_process_count_increased": default_codex_drift,
        "observer_can_separate_custom_from_background": not background_noise_detected,
    }


def _historical_quarantine(repo_root: Path, evidence_dir: Path) -> tuple[list[str], list[str]]:
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/native_custom_direct_egress_classification_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
    )
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(f"?? {relative_evidence_dir}/")
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def _sync_packets(repo_root: Path, evidence_dir: Path) -> dict[str, dict[str, Any]]:
    quarantined, unexpected_dirty = _historical_quarantine(repo_root, evidence_dir)
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    return {
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": status_lines,
            "unexpected_dirty_entries": unexpected_dirty,
            "new_evidence_dir": str(evidence_dir),
            "master_plan_written_to_repo": False,
        },
        "historical_dirt_quarantine_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "historical_dirt_quarantine",
            "status": "ok",
            "quarantined_paths": quarantined,
            "quarantine_classification": "out_of_scope_historical_residue",
            "current_contour_relies_on_quarantined_paths": False,
            "current_contour_mutates_quarantined_paths": False,
            "current_contour_stages_quarantined_paths": False,
        },
        "version_pinning_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "version_pinning",
            "status": "ok",
            "codex_cli_version": _run(repo_root, ["codex", "--version"]),
            "codex_cli_path": _run(repo_root, ["which", "codex"]),
            "codex_app_path": "/Applications/Codex.app",
            "codex_app_version": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleShortVersionString",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "codex_app_bundle_version": _run(
                repo_root,
                [
                    "/usr/libexec/PlistBuddy",
                    "-c",
                    "Print :CFBundleVersion",
                    "/Applications/Codex.app/Contents/Info.plist",
                ],
            ),
            "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        },
        "declared_write_surfaces_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "declared_write_surfaces",
            "status": "ok",
            "declared_write_surfaces": [
                "fresh audit_results evidence directory",
                "temporary /tmp/wbp-native-egress-* profile if live mode is used",
            ],
            "protected_surfaces_write_allowed": False,
            "original_codex_bundle_write_allowed": False,
            "original_codex_profile_write_allowed": False,
            "rollback_expectation": "terminate isolated Custom process and remove temp root",
        },
    }


def _launch_native(
    *,
    repo_root: Path,
    endpoint: str,
    model: str,
) -> tuple[Path, dict[str, Any], Any]:
    real_runtime_paths = RuntimePaths.from_env()
    local_token = emit_local_token(real_runtime_paths)
    tmp_root = Path(tempfile.mkdtemp(prefix="wbp-native-egress-", dir="/tmp"))
    layout = create_native_probe_layout(tmp_root)
    materialized = materialize_probe_profile(
        layout=layout,
        endpoint=endpoint,
        model=model,
        auth_command_path=repo_root / "wbp_codex_auth_command.py",
        local_token=local_token,
    )
    before_process = collect_codex_process_inventory(
        custom_user_data_dir=str(layout.custom_user_data_dir)
    )
    launch_packet = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_direct_egress_launch",
        "status": "pending",
        "materialized_profile": materialized,
        "before_process_inventory": before_process,
        "configured_endpoint": endpoint,
        "configured_model": model,
        "config_sha256": "",
        "custom_process_observed": False,
        "launcher_pid": None,
    }
    config_path = layout.profile_dir / "config.toml"
    if config_path.exists():
        launch_packet["config_sha256"] = __import__("hashlib").sha256(
            config_path.read_bytes()
        ).hexdigest()
    stdout_handle = layout.launcher_stdout.open("w", encoding="utf-8")
    stderr_handle = layout.launcher_stderr.open("w", encoding="utf-8")
    env = clean_env()
    env.update(
        {
            "WBP_PROFILE_DIR": str(layout.profile_dir),
            "WBP_MANAGED_DIR": str(real_runtime_paths.managed_dir),
            "WBP_STABLE_CONFIG": str(real_runtime_paths.stable_config),
            "WBP_PYTHON_BIN": sys.executable,
        }
    )
    process = subprocess.Popen(
        [str(layout.launcher_path), "desktop"],
        cwd=str(repo_root),
        env=env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        start_new_session=True,
        text=True,
    )
    stdout_handle.close()
    stderr_handle.close()
    deadline = time.time() + 20.0
    last_inventory: dict[str, Any] = {}
    while time.time() < deadline:
        last_inventory = collect_codex_process_inventory(
            custom_user_data_dir=str(layout.custom_user_data_dir)
        )
        if last_inventory["custom_process_count"] > 0:
            launch_packet.update(
                {
                    "status": "ok",
                    "custom_process_observed": True,
                    "startup_inventory": last_inventory,
                    "launcher_pid": process.pid,
                }
            )
            break
        if process.poll() is not None:
            break
        time.sleep(0.5)
    if launch_packet["status"] != "ok":
        launch_packet.update(
            {
                "status": "blocked",
                "reason_class": "CUSTOM_PROCESS_NOT_OBSERVED",
                "startup_inventory": last_inventory,
                "launcher_pid": process.pid,
                "launcher_exit_code_early": process.poll(),
            }
        )
    return tmp_root, launch_packet, layout


def _capability_only(repo_root: Path, evidence_dir: Path) -> dict[str, Any]:
    packets = _sync_packets(repo_root, evidence_dir)
    capability = build_native_direct_egress_capability_packet(
        lsof_path=shutil.which("lsof") or "",
        tcpdump_path=shutil.which("tcpdump") or "",
        nettop_path=shutil.which("nettop") or "",
        process_tree_observer_available=True,
    )
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_direct_egress_summary",
        "status": capability["status"],
        "final_status": (
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_OBSERVER_INSUFFICIENT"
            if capability["status"] != "ok"
            else "NATIVE_DIRECT_EGRESS_OBSERVER_CAPABILITY_READY"
        ),
        "live_native_launch_attempted": False,
        "direct_non_wbp_model_egress_absent_proven": False,
        "full_network_absence_proven": False,
    }
    packets.update(
        {
            "observer_capability_packet.json": capability,
            "native_direct_egress_summary_packet.json": summary,
        }
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    return summary


def _live(repo_root: Path, evidence_dir: Path, *, model: str, wait_seconds: int) -> dict[str, Any]:
    packets = _sync_packets(repo_root, evidence_dir)
    capability = build_native_direct_egress_capability_packet(
        lsof_path=shutil.which("lsof") or "",
        tcpdump_path=shutil.which("tcpdump") or "",
        nettop_path=shutil.which("nettop") or "",
        process_tree_observer_available=True,
    )
    packets["observer_capability_packet.json"] = capability
    if capability["status"] != "ok":
        summary = _capability_only(repo_root, evidence_dir)
        return summary

    tmp_root: Path | None = None
    observer: OwnerSideProcessNetworkObserver | None = None
    with WbpTraceObserver(downstream_endpoint="http://127.0.0.1:8318/v1") as trace:
        tmp_root, launch_packet, layout = _launch_native(
            repo_root=repo_root,
            endpoint=trace.listen_endpoint,
            model=model,
        )
        packets["native_custom_launch_packet.json"] = launch_packet
        if launch_packet["status"] != "ok":
            wbp_trace = build_wbp_trace_observation_packet(trace_packet=trace.packet())
            empty_network = {
                "status": "ok",
                "machine_error_code": "INSUFFICIENT_OBSERVATION",
                "classification": "insufficient_observation",
                "direct_non_wbp_model_egress_absent_proven": False,
                "process_tree_observed": False,
                "sample_count": 0,
                "allowed_local_endpoint_observed": False,
            }
            claim = build_native_direct_egress_claim_packet(
                process_network_observation_packet=empty_network,
                wbp_trace_observation_packet=wbp_trace,
                custom_process_bound=False,
            )
            packets.update(
                {
                    "wbp_trace_observation_packet.json": wbp_trace,
                    "native_process_network_observation_packet.json": empty_network,
                    "native_direct_egress_claim_packet.json": claim,
                }
            )
        else:
            allowed = {_endpoint_hostport(trace.listen_endpoint)}
            observer = OwnerSideProcessNetworkObserver(
                root_pid=int(launch_packet["launcher_pid"]),
                allowed_local_endpoints={item for item in allowed if item},
            )
            observer.start()
            print(
                json.dumps(
                    {
                        "owner_action": "type_prompt_in_isolated_custom_window",
                        "prompt": (
                            "WBP direct egress classification check. Reply with OK only."
                        ),
                        "wait_seconds": wait_seconds,
                        "custom_user_data_dir": str(layout.custom_user_data_dir),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            deadline = time.time() + wait_seconds
            while time.time() < deadline:
                current_trace = trace.packet()
                if (
                    current_trace.get("request_observed") is True
                    and current_trace.get("response_observed") is True
                ):
                    break
                time.sleep(0.5)
            observer.stop()
            network_packet = observer.packet(warning_classes=[])
            trace_packet = trace.packet()
            wbp_trace = build_wbp_trace_observation_packet(trace_packet=trace_packet)
            after_inventory = collect_codex_process_inventory(
                custom_user_data_dir=str(layout.custom_user_data_dir)
            )
            background_noise = _background_noise_packet(
                launch_packet=launch_packet,
                after_inventory=after_inventory,
                network_packet=network_packet,
            )
            claim = build_native_direct_egress_claim_packet(
                process_network_observation_packet=network_packet,
                wbp_trace_observation_packet=wbp_trace,
                custom_process_bound=launch_packet["custom_process_observed"] is True,
                background_codex_noise_detected=background_noise[
                    "background_codex_noise_detected"
                ]
                is True,
            )
            audit = build_native_direct_egress_false_green_audit(
                native_direct_egress_claim_packet=claim,
                process_network_observation_packet=network_packet,
                wbp_trace_observation_packet=wbp_trace,
            )
            packets.update(
                {
                    "native_process_inventory_after_packet.json": after_inventory,
                    "native_background_codex_noise_packet.json": background_noise,
                    "native_process_network_observation_packet.json": network_packet,
                    "source_wbp_trace_packet.json": trace_packet,
                    "wbp_trace_observation_packet.json": wbp_trace,
                    "native_direct_egress_claim_packet.json": claim,
                    "native_direct_egress_false_green_audit.json": audit,
                }
            )
    cleanup_packet: dict[str, Any] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "cleanup_reversibility",
        "status": "blocked",
        "custom_processes_gone": False,
        "tmp_root_removed": False,
    }
    if tmp_root is not None:
        custom_dir = str((tmp_root / "profile" / "electron-user-data").resolve())
        termination = terminate_custom_processes(custom_user_data_dir=custom_dir)
        cleanup_error = remove_tree_with_retry(tmp_root)
        cleanup_packet.update(
            {
                "status": "ok"
                if termination.get("custom_processes_gone") is True and not cleanup_error
                else "blocked",
                "termination_packet": termination,
                "tmp_root": str(tmp_root),
                "tmp_root_removed": not tmp_root.exists(),
                "cleanup_error": cleanup_error,
                "custom_processes_gone": termination.get("custom_processes_gone") is True,
            }
        )
    packets["cleanup_reversibility_packet.json"] = cleanup_packet
    claim = packets.get("native_direct_egress_claim_packet.json", {})
    audit = packets.get("native_direct_egress_false_green_audit.json", {"status": "blocked"})
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "native_direct_egress_summary",
        "status": "ok"
        if claim.get("status") == "ok"
        and audit.get("status") == "ok"
        and cleanup_packet.get("status") == "ok"
        else "blocked",
        "final_status": claim.get(
            "final_status",
            "NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_OBSERVER_INSUFFICIENT",
        ),
        "live_native_launch_attempted": True,
        "direct_non_wbp_model_egress_absent_proven": claim.get(
            "direct_non_wbp_model_egress_absent_proven"
        )
        is True,
        "full_network_absence_proven": False,
        "native_ux_claimed": False,
        "filesystem_safety_claimed": False,
        "provider_compatibility_claimed": False,
        "final_e2e_claimed": False,
    }
    packets["native_direct_egress_summary_packet.json"] = summary
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="native-custom-direct-egress-classification-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--mode", choices=("capability", "live"), default="capability")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--wait-seconds", type=int, default=90)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    if not _is_relative_to(evidence_dir, repo_root):
        print("--evidence-dir must be inside --repo-root", file=sys.stderr)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "capability":
        summary = _capability_only(repo_root, evidence_dir)
    else:
        summary = _live(
            repo_root,
            evidence_dir,
            model=args.model,
            wait_seconds=args.wait_seconds,
        )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
