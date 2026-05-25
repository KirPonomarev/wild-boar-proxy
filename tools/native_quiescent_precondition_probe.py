# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str]) -> str:
    return subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from wild_boar_proxy.native_filesystem_probe import (
        classify_quiescent_current_codex_precondition,
        collect_codex_process_inventory,
        json_write,
    )

    evidence_dir = Path(args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    inventory = collect_codex_process_inventory(
        custom_user_data_dir="/tmp/nonexistent-custom-user-data"
    )
    precondition = classify_quiescent_current_codex_precondition(inventory)

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

    json_write(evidence_dir / "sync_gate_packet.json", sync_packet)
    json_write(evidence_dir / "version_pinning_packet.json", version_packet)
    json_write(evidence_dir / "quiescent_current_codex_precondition_packet.json", precondition)
    print(json.dumps(precondition, indent=2, sort_keys=True))
    return 0 if precondition.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
