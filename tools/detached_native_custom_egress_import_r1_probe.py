#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Import and classify detached native Custom egress evidence without launching Codex."""

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

from wild_boar_proxy.native_filesystem_probe import (
    build_detached_egress_command_hash_verification_packet,
    build_detached_egress_external_evidence_import_packet,
    build_detached_egress_handoff_prerequisite_packet,
    build_detached_egress_import_false_green_audit,
    build_detached_egress_import_secret_scan_packet,
    build_detached_egress_network_claim_classification_packet,
    build_detached_egress_network_observation_validation_packet,
    build_detached_egress_process_binding_validation_packet,
    build_detached_egress_safety_admission_prerequisite_packet,
    build_detached_egress_wbp_trace_validation_packet,
    build_domain_attribution_limit_packet,
    build_network_claim_limits_packet,
    build_owner_visible_response_context_packet,
    json_write,
    validate_external_evidence_packets,
)


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-cliproxy[A-Za-z0-9_-]+"),
    re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*[=:]\s*[A-Za-z0-9._-]{20,}"),
    re.compile(r"CLIPROXY_API_KEY\s*[=:]\s*[A-Za-z0-9._-]{20,}"),
]


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "source_path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "invalid_json",
            "source_path": str(path),
            "error": str(exc),
        }


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
        "wild_boar_proxy/native_filesystem_probe.py",
        "tests/test_native_filesystem_probe.py",
        "tools/detached_native_custom_egress_import_r1_probe.py",
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


def _secret_matches(external_evidence_dir: Path) -> list[str]:
    if not external_evidence_dir.exists():
        return []
    matches: list[str] = []
    for path in sorted(external_evidence_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            matches.append(str(path))
    return matches


def _owner_readiness_gate_packet(
    *,
    owner_ready_now: bool,
    owner_executed_externally: bool,
    owner_evidence_dir_preserved: bool,
) -> dict[str, Any]:
    ok = owner_ready_now and owner_executed_externally and owner_evidence_dir_preserved
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "detached_egress_owner_readiness_gate",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "OWNER_READINESS_OR_ATTESTATION_MISSING",
        "owner_ready_now": owner_ready_now,
        "owner_claimed_external_execution": owner_executed_externally,
        "owner_claimed_evidence_dir_preserved": owner_evidence_dir_preserved,
        "owner_statement_counts_as_packet_proof": False,
        "counts_as_network_claim": False,
    }


def _owner_execution_attestation_packet(
    *,
    owner_executed_externally: bool,
    owner_evidence_dir_preserved: bool,
    external_evidence_dir: Path,
) -> dict[str, Any]:
    ok = owner_executed_externally and owner_evidence_dir_preserved
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "detached_egress_owner_execution_attestation",
        "status": "ok" if ok else "blocked",
        "reason_class": "" if ok else "OWNER_EXECUTION_ATTESTATION_MISSING",
        "owner_claimed_external_execution": owner_executed_externally,
        "owner_claimed_evidence_dir_preserved": owner_evidence_dir_preserved,
        "external_evidence_dir": str(external_evidence_dir.resolve(strict=False)),
        "current_thread_executed_command": False,
        "current_thread_native_launch_attempted": False,
        "context_only": True,
        "counts_as_trace_proof": False,
        "counts_as_network_claim": False,
        "counts_as_native_ux_proof": False,
    }


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
        "sync_gate_packet.json": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "sync_gate",
            "status": "ok" if not unexpected_dirty else "blocked",
            "git_branch": "SKIPPED_FOR_TEST" if skip_git else _run(repo_root, ["git", "branch", "--show-current"]),
            "git_head": "SKIPPED_FOR_TEST" if skip_git else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
            "git_status_short": []
            if skip_git
            else _run(repo_root, ["git", "status", "--short"]).splitlines(),
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


def build_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    handoff_dir: Path,
    safety_admission_path: Path,
    external_evidence_dir: Path | None,
    owner_ready_now: bool = False,
    owner_executed_externally: bool = False,
    owner_evidence_dir_preserved: bool = False,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    command_packet = _read_json(handoff_dir / "detached_egress_execution_command_packet.json")
    handoff_summary = _read_json(handoff_dir / "handoff_summary_packet.json")
    if external_evidence_dir is None:
        external_evidence_dir = Path(
            str(command_packet.get("evidence_dir") or handoff_summary.get("external_evidence_dir") or "")
        )
    command_hash = _read_json(handoff_dir / "detached_egress_command_hash_packet.json")
    command_admission = _read_json(
        handoff_dir / "detached_egress_command_admission_packet.json"
    )
    import_contract = _read_json(handoff_dir / "future_result_import_contract_packet.json")
    required_packets = list(import_contract.get("required_packets", []))
    safety_admission = _read_json(safety_admission_path)

    packets = _base_packets(repo_root, evidence_dir, skip_git=skip_git)
    packets["owner_readiness_gate_packet.json"] = _owner_readiness_gate_packet(
        owner_ready_now=owner_ready_now,
        owner_executed_externally=owner_executed_externally,
        owner_evidence_dir_preserved=owner_evidence_dir_preserved,
    )
    packets["owner_execution_attestation_packet.json"] = (
        _owner_execution_attestation_packet(
            owner_executed_externally=owner_executed_externally,
            owner_evidence_dir_preserved=owner_evidence_dir_preserved,
            external_evidence_dir=external_evidence_dir,
        )
    )
    packets["safety_admission_prerequisite_packet.json"] = (
        build_detached_egress_safety_admission_prerequisite_packet(
            source_path=str(safety_admission_path),
            source_packet=safety_admission,
        )
    )
    packets["detached_handoff_prerequisite_packet.json"] = (
        build_detached_egress_handoff_prerequisite_packet(
            handoff_dir=handoff_dir,
            handoff_summary_packet=handoff_summary,
            command_packet=command_packet,
            command_hash_packet=command_hash,
            command_admission_packet=command_admission,
            import_contract_packet=import_contract,
        )
    )
    packets["detached_command_hash_verification_packet.json"] = (
        build_detached_egress_command_hash_verification_packet(
            command_packet=command_packet,
            expected_hash_packet=command_hash,
        )
    )
    external_process_observation = _read_json(
        external_evidence_dir / "native_process_network_observation_packet.json"
    )
    import_derived_alternatives: dict[str, dict[str, Any]] = {
        "import-derived context-only packet": build_owner_visible_response_context_packet(
            owner_visible_response_reported=False,
            owner_confirmation_collected=False,
        ),
        "import audit packet": {
            "captured_at_utc": _utc_now(),
            "packet_kind": "detached_egress_import_audit_reference",
            "status": "ok",
            "audit_emitted_by_import_tool": True,
            "text_only_audit_counted_as_pass": False,
        },
    }
    if external_process_observation.get("status") != "missing":
        import_derived_alternatives["import-derived domain attribution limit"] = (
            build_domain_attribution_limit_packet(
                process_network_observation_packet=external_process_observation,
                domain_attribution_available=False,
            )
        )
    validation = validate_external_evidence_packets(
        external_evidence_dir=external_evidence_dir,
        required_packets=required_packets,
        import_derived_alternatives=import_derived_alternatives,
    )
    packets["import_derived_owner_visible_response_context_packet.json"] = (
        import_derived_alternatives["import-derived context-only packet"]
    )
    packets["import_derived_import_audit_reference_packet.json"] = (
        import_derived_alternatives["import audit packet"]
    )
    if "import-derived domain attribution limit" in import_derived_alternatives:
        packets["import_derived_domain_attribution_limit_packet.json"] = (
            import_derived_alternatives["import-derived domain attribution limit"]
        )
    packets["external_json_packet_validation_packet.json"] = validation
    packets["external_evidence_import_packet.json"] = (
        build_detached_egress_external_evidence_import_packet(
            external_evidence_dir=external_evidence_dir,
            validation_packet=validation,
        )
    )
    packets["external_secret_scan_packet.json"] = (
        build_detached_egress_import_secret_scan_packet(
            external_evidence_dir=external_evidence_dir,
            matches=_secret_matches(external_evidence_dir),
        )
    )
    packets["native_process_binding_validation_packet.json"] = (
        build_detached_egress_process_binding_validation_packet(
            validation_packet=validation,
        )
    )
    packets["wbp_trace_validation_packet.json"] = (
        build_detached_egress_wbp_trace_validation_packet(validation_packet=validation)
    )
    packets["network_observation_validation_packet.json"] = (
        build_detached_egress_network_observation_validation_packet(
            validation_packet=validation,
        )
    )
    packets["network_claim_limits_packet.json"] = build_network_claim_limits_packet()
    packets["network_claim_classification_packet.json"] = (
        build_detached_egress_network_claim_classification_packet(
            safety_admission_prerequisite_packet=packets[
                "safety_admission_prerequisite_packet.json"
            ],
            handoff_prerequisite_packet=packets[
                "detached_handoff_prerequisite_packet.json"
            ],
            command_hash_verification_packet=packets[
                "detached_command_hash_verification_packet.json"
            ],
            external_evidence_import_packet=packets[
                "external_evidence_import_packet.json"
            ],
            secret_scan_packet=packets["external_secret_scan_packet.json"],
            process_binding_validation_packet=packets[
                "native_process_binding_validation_packet.json"
            ],
            wbp_trace_validation_packet=packets["wbp_trace_validation_packet.json"],
            network_observation_validation_packet=packets[
                "network_observation_validation_packet.json"
            ],
        )
    )
    packets["native_egress_false_green_audit.json"] = (
        build_detached_egress_import_false_green_audit(
            classification_packet=packets["network_claim_classification_packet.json"],
            external_evidence_import_packet=packets["external_evidence_import_packet.json"],
            command_hash_verification_packet=packets[
                "detached_command_hash_verification_packet.json"
            ],
            wbp_trace_validation_packet=packets["wbp_trace_validation_packet.json"],
            process_binding_validation_packet=packets[
                "native_process_binding_validation_packet.json"
            ],
            network_observation_validation_packet=packets[
                "network_observation_validation_packet.json"
            ],
        )
    )
    packets["independent_native_egress_audit.json"] = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "independent_native_egress_audit",
        "status": "ok"
        if packets["native_egress_false_green_audit.json"]["status"] == "ok"
        else "blocked",
        "evidence": [
            "safety_admission_prerequisite_packet.json",
            "detached_handoff_prerequisite_packet.json",
            "detached_command_hash_verification_packet.json",
            "external_json_packet_validation_packet.json",
            "network_claim_classification_packet.json",
        ],
        "facts": {
            "external_evidence_dir": str(external_evidence_dir),
            "external_evidence_dir_exists": validation["external_evidence_dir_exists"],
            "command_hash_matches": packets[
                "detached_command_hash_verification_packet.json"
            ]["command_hash_matches"],
            "final_status": packets["network_claim_classification_packet.json"][
                "final_status"
            ],
            "native_launch_attempted_from_current_thread": False,
            "positive_absence_claimed": packets[
                "native_egress_false_green_audit.json"
            ]["positive_absence_claimed"],
        },
        "text_only_audit_counted_as_pass": False,
    }
    return packets


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="detached-native-custom-egress-import-r1-probe")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument(
        "--evidence-dir",
        default=str(
            ROOT / "audit_results/wbp_detached_native_custom_egress_import_r1_2026-05-27"
        ),
    )
    parser.add_argument(
        "--handoff-dir",
        default=str(
            ROOT
            / "audit_results/wbp_native_custom_detached_egress_execution_handoff_r1_2026-05-26"
        ),
    )
    parser.add_argument(
        "--safety-admission-path",
        default=str(
            ROOT
            / "audit_results/wbp_native_custom_safety_admission_refresh_r1_2026-05-27/native_safety_admission_result_packet.json"
        ),
    )
    parser.add_argument("--external-evidence-dir", default="")
    parser.add_argument("--owner-ready-now", action="store_true")
    parser.add_argument("--owner-executed-externally", action="store_true")
    parser.add_argument("--owner-evidence-dir-preserved", action="store_true")
    parser.add_argument("--skip-git", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    evidence_dir = Path(args.evidence_dir).resolve()
    handoff_dir = Path(args.handoff_dir).resolve()
    safety_admission_path = Path(args.safety_admission_path).resolve()
    external_evidence_dir = (
        Path(args.external_evidence_dir).resolve()
        if args.external_evidence_dir
        else None
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_packets(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        handoff_dir=handoff_dir,
        safety_admission_path=safety_admission_path,
        external_evidence_dir=external_evidence_dir,
        owner_ready_now=args.owner_ready_now,
        owner_executed_externally=args.owner_executed_externally,
        owner_evidence_dir_preserved=args.owner_evidence_dir_preserved,
        skip_git=args.skip_git,
    )
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)
    classification = packets["network_claim_classification_packet.json"]
    summary = {
        "captured_at_utc": _utc_now(),
        "packet_kind": "detached_native_custom_egress_import_summary",
        "status": classification["status"],
        "final_status": classification["final_status"],
        "reason_class": classification["reason_class"],
        "external_evidence_dir": packets["external_evidence_import_packet.json"][
            "external_evidence_dir"
        ],
        "external_evidence_dir_exists": packets["external_evidence_import_packet.json"][
            "external_evidence_dir_exists"
        ],
        "owner_readiness_status": packets["owner_readiness_gate_packet.json"]["status"],
        "owner_attestation_context_only": packets[
            "owner_execution_attestation_packet.json"
        ]["context_only"],
        "command_hash_matches": packets[
            "detached_command_hash_verification_packet.json"
        ]["command_hash_matches"],
        "native_launch_attempted_from_current_thread": False,
        "native_ux_claimed": False,
        "direct_egress_absence_claimed": classification[
            "direct_non_wbp_model_egress_absent_within_bounded_window"
        ],
        "final_e2e_claimed": False,
    }
    json_write(evidence_dir / "detached_native_custom_egress_import_summary_packet.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
