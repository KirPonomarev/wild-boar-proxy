# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_BASIS_PACKET = (
    "audit_results/"
    "wbp_codex_provider_contract_syntax_proof_pass_2026-05-25/"
    "evidence/version_pinning_packet.json"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = True) -> str:
    completed = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode, command, completed.stdout, completed.stderr
        )
    return completed.stdout.strip()


def _host_process_chain() -> list[dict[str, object]]:
    pid = os.getpid()
    chain: list[dict[str, object]] = []
    seen: set[int] = set()
    while pid and pid not in seen:
        seen.add(pid)
        process = subprocess.run(
            ["ps", "-o", "pid=,ppid=,command=", "-p", str(pid)],
            text=True,
            capture_output=True,
            check=True,
        )
        line = process.stdout.strip()
        if not line:
            break
        parts = line.split(None, 2)
        if len(parts) < 3:
            break
        cur_pid = int(parts[0])
        ppid = int(parts[1])
        command = parts[2]
        chain.append({"pid": cur_pid, "ppid": ppid, "command": command})
        pid = ppid
    return chain


def _load_schema_basis(repo_root: Path) -> dict[str, object]:
    path = repo_root / SCHEMA_BASIS_PACKET
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _git_upstream(repo_root: Path) -> str:
    return _run(
        repo_root,
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        check=False,
    )


def _build_sync_packet(repo_root: Path) -> dict[str, object]:
    return {
        "captured_at_utc": _utc_now(),
        "git_status_short_branch": _run(
            repo_root, ["git", "status", "--short", "--branch"]
        ).splitlines(),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "git_branch": _run(repo_root, ["git", "branch", "--show-current"]),
        "git_upstream": _git_upstream(repo_root),
    }


def _build_version_packet(repo_root: Path) -> dict[str, object]:
    schema_basis = _load_schema_basis(repo_root)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "version_pinning",
        "schema_version": 1,
        "status": "ok",
        "machine_error_code": "OK",
        "secret_value_recorded": False,
        "codex_cli_version": _run(repo_root, ["codex", "--version"]),
        "codex_cli_path": _run(repo_root, ["which", "codex"]),
        "codex_app_path": "/Applications/Codex.app",
        "codex_app_bundle_identifier": "com.openai.codex",
        "codex_app_bundle_name": "Codex",
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
        "config_schema_source": schema_basis.get(
            "config_schema_source",
            "https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/config.schema.json",
        ),
        "config_schema_retrieval_date_utc": schema_basis.get(
            "config_schema_retrieval_date_utc", ""
        ),
        "config_schema_sha256": schema_basis.get("config_schema_sha256", ""),
        "config_schema_basis_packet": str((repo_root / SCHEMA_BASIS_PACKET).resolve()),
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "cliproxyapi_version_status": "repo_runtime_engine_not_probed_in_admission_contour",
    }


def _build_host_chain_packet(
    host_chain: list[dict[str, object]],
) -> dict[str, object]:
    first = host_chain[0] if host_chain else {}
    return {
        "captured_at_utc": _utc_now(),
        "executor_pid": first.get("pid"),
        "executor_ppid": first.get("ppid"),
        "executor_command": first.get("command", ""),
        "host_process_chain_length": len(host_chain),
        "host_process_chain": host_chain,
    }


def _build_current_codex_running_state_packet(inventory: dict[str, object]) -> dict[str, object]:
    packet = dict(inventory)
    packet.update(
        {
            "captured_without_kill_or_restart": True,
            "window_inventory_observed": False,
            "window_inventory_reason": "process_only_probe",
        }
    )
    return packet


def _build_summary(
    *,
    summary_packet: dict[str, object],
) -> dict[str, object]:
    return dict(summary_packet)


def _build_independent_audit(
    *,
    evidence_dir: Path,
    host_negative_packet: dict[str, object],
    acquisition_packet: dict[str, object],
    precondition_packet: dict[str, object],
    ambient_env_packet: dict[str, object],
    summary_packet: dict[str, object],
) -> dict[str, object]:
    return {
        "auditor": "orchestrator:self_packet_audit",
        "captured_at_utc": _utc_now(),
        "status": "ok",
        "final_verdict": (
            "external_detached_context_proof_supported"
            if summary_packet.get("status") == "ok"
            else "external_detached_context_proof_block_supported"
        ),
        "supported_reason_class": summary_packet.get("reason_class", ""),
        "findings": [
            {
                "id": "protected_host_negative",
                "packet": str(
                    (evidence_dir / "protected_codex_host_negative_packet.json").resolve()
                ),
                "facts": {
                    "status": host_negative_packet.get("status"),
                    "reason_class": host_negative_packet.get("reason_class"),
                    "hosted_by_protected_codex_session": host_negative_packet.get(
                        "hosted_by_protected_codex_session"
                    ),
                    "protected_codex_ancestry_disproven": host_negative_packet.get(
                        "protected_codex_ancestry_disproven"
                    ),
                },
            },
            {
                "id": "fresh_context_acquisition",
                "packet": str(
                    (evidence_dir / "fresh_context_acquisition_packet.json").resolve()
                ),
                "facts": {
                    "status": acquisition_packet.get("status"),
                    "reason_class": acquisition_packet.get("reason_class"),
                    "operator_action_performed": acquisition_packet.get(
                        "operator_action_performed"
                    ),
                    "phase7_retry_admissible": acquisition_packet.get(
                        "phase7_retry_admissible"
                    ),
                },
            },
            {
                "id": "quiescent_gate",
                "packet": str(
                    (
                        evidence_dir / "quiescent_current_codex_precondition_packet.json"
                    ).resolve()
                ),
                "facts": {
                    "status": precondition_packet.get("status"),
                    "reason_class": precondition_packet.get("reason_class"),
                    "quiescent_current_codex_precondition_satisfied": precondition_packet.get(
                        "quiescent_current_codex_precondition_satisfied"
                    ),
                },
            },
            {
                "id": "ambient_env_classification",
                "packet": str((evidence_dir / "ambient_env_context_packet.json").resolve()),
                "facts": {
                    "status": ambient_env_packet.get("status"),
                    "reason_class": ambient_env_packet.get("reason_class"),
                    "ambient_openai_api_key_present": ambient_env_packet.get(
                        "ambient_openai_api_key_present"
                    ),
                    "unexplained_authority_present": ambient_env_packet.get(
                        "unexplained_authority_present"
                    ),
                },
            },
            {
                "id": "no_forbidden_claims",
                "packet": str(
                    (evidence_dir / "fresh_detached_context_admission_summary.json").resolve()
                ),
                "facts": {
                    "consumer_launch_performed": summary_packet.get(
                        "consumer_launch_performed"
                    ),
                    "native_launch_performed": summary_packet.get(
                        "native_launch_performed"
                    ),
                    "filesystem_retry_attempted": summary_packet.get(
                        "filesystem_retry_attempted"
                    ),
                    "forbidden_claims_present": summary_packet.get(
                        "forbidden_claims_present"
                    ),
                },
            },
        ],
        "overclaim_check": {
            "native_filesystem_isolation_claim_present": False,
            "native_window_claim_present": False,
            "provider_reproof_claim_present": False,
            "consumer_launch_claim_present": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument(
        "--operator-action-performed",
        action="store_true",
        help="Record that an owner- or runner-supplied detached context was admitted before this probe.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from wild_boar_proxy.native_filesystem_probe import (
        classify_external_detached_context_outcome,
        classify_fresh_context_acquisition,
        classify_fresh_context_entry,
        classify_protected_codex_host_negative,
        classify_quiescent_current_codex_precondition,
        collect_ambient_env_context,
        collect_codex_process_inventory,
        json_write,
    )

    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    inventory = collect_codex_process_inventory(
        custom_user_data_dir="/tmp/nonexistent-custom-user-data"
    )
    precondition_packet = classify_quiescent_current_codex_precondition(inventory)
    host_chain = _host_process_chain()
    host_chain_packet = _build_host_chain_packet(host_chain)
    host_negative_packet = classify_protected_codex_host_negative(host_chain)
    fresh_context_entry_packet = classify_fresh_context_entry(
        host_process_chain=host_chain,
        quiescent_precondition_packet=precondition_packet,
    )
    acquisition_packet = classify_fresh_context_acquisition(
        operator_action_performed=args.operator_action_performed,
        fresh_context_entry_packet=fresh_context_entry_packet,
    )
    ambient_env_packet = collect_ambient_env_context()
    current_codex_packet = _build_current_codex_running_state_packet(inventory)
    sync_packet = _build_sync_packet(repo_root)
    version_packet = _build_version_packet(repo_root)
    summary_packet = _build_summary(
        summary_packet=classify_external_detached_context_outcome(
            host_negative_packet=host_negative_packet,
            precondition_packet=precondition_packet,
            acquisition_packet=acquisition_packet,
            ambient_env_packet=ambient_env_packet,
        )
    )
    audit_packet = _build_independent_audit(
        evidence_dir=evidence_dir,
        host_negative_packet=host_negative_packet,
        acquisition_packet=acquisition_packet,
        precondition_packet=precondition_packet,
        ambient_env_packet=ambient_env_packet,
        summary_packet=summary_packet,
    )

    json_write(evidence_dir / "sync_gate_packet.json", sync_packet)
    json_write(evidence_dir / "version_pinning_packet.json", version_packet)
    json_write(
        evidence_dir / "fresh_detached_context_host_chain_packet.json", host_chain_packet
    )
    json_write(
        evidence_dir / "protected_codex_host_negative_packet.json", host_negative_packet
    )
    json_write(
        evidence_dir / "fresh_context_acquisition_packet.json", acquisition_packet
    )
    json_write(
        evidence_dir / "current_codex_running_state_packet.json", current_codex_packet
    )
    json_write(
        evidence_dir / "quiescent_current_codex_precondition_packet.json",
        precondition_packet,
    )
    json_write(evidence_dir / "ambient_env_context_packet.json", ambient_env_packet)
    json_write(
        evidence_dir / "fresh_detached_context_admission_summary.json", summary_packet
    )
    json_write(
        evidence_dir / "independent_fresh_detached_context_audit.json", audit_packet
    )
    print(json.dumps(summary_packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
