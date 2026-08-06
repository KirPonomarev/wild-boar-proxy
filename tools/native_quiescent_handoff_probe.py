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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str]) -> str:
    try:
        return subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except FileNotFoundError:
        return f"UNAVAILABLE_FILE_NOT_FOUND: {command[0]}"
    except OSError as exc:
        return f"UNAVAILABLE_OSERROR: {command[0]}: {exc}"


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument(
        "--operator-action-performed",
        action="store_true",
        help="Record that admitted operator action was already performed before this probe.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from wild_boar_proxy.native_filesystem_probe import (
        classify_quiescent_current_codex_precondition,
        classify_quiescent_handoff_admission,
        collect_codex_process_inventory,
        json_write,
    )

    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    inventory = collect_codex_process_inventory(
        custom_user_data_dir="/tmp/nonexistent-custom-user-data"
    )
    precondition = classify_quiescent_current_codex_precondition(inventory)
    host_chain = _host_process_chain()
    admission = classify_quiescent_handoff_admission(
        operator_action_performed=args.operator_action_performed,
        quiescent_precondition_packet=precondition,
        host_process_chain=host_chain,
    )

    sync_packet = {
        "captured_at_utc": _utc_now(),
        "git_status_short_branch": _run(repo_root, ["git", "status", "--short", "--branch"]).splitlines(),
        "git_head": _run(repo_root, ["git", "rev-parse", "HEAD"]),
    }
    version_packet = {
        "captured_at_utc": _utc_now(),
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
        "wbp_git_commit": _run(repo_root, ["git", "rev-parse", "HEAD"]),
        "status": "ok",
    }
    summary = {
        "captured_at_utc": _utc_now(),
        "status": admission["status"],
        "reason_class": admission["reason_class"],
        "final_verdict": admission["verdict"],
        "operator_action_required": admission["operator_action_required"],
        "operator_action_performed": admission["operator_action_performed"],
        "quiescent_precondition_verified": admission["quiescent_precondition_verified"],
        "same_thread_admissible": admission["same_thread_admissible"],
        "fresh_context_required": admission["fresh_context_required"],
        "hosted_by_protected_codex_session": admission["hosted_by_protected_codex_session"],
        "launch_attempted": False,
        "filesystem_retry_attempted": False,
        "host_process_chain_length": len(host_chain),
    }

    json_write(evidence_dir / "sync_gate_packet.json", sync_packet)
    json_write(evidence_dir / "version_pinning_packet.json", version_packet)
    json_write(evidence_dir / "quiescent_current_codex_precondition_packet.json", precondition)
    json_write(
        evidence_dir / "quiescent_handoff_admission_packet.json",
        {
            "captured_at_utc": _utc_now(),
            "operator_action_required": True,
            "operator_action_performed": args.operator_action_performed,
            "host_process_chain": host_chain,
            "admission": admission,
        },
    )
    json_write(evidence_dir / "quiescent_handoff_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
