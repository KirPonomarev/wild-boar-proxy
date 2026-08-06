#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Emit an R5 CI job receipt (EXECUTE_WBP_R5 stage R56).

Every required R5 CI job (unit-isolation, full-suite, macos-sandbox,
package) emits one canonical JSON receipt per workflow attempt:

{
  "schema_version": 2,
  "workflow_run_id": "...",
  "workflow_run_attempt": "...",
  "job_name": "...",
  "commit_sha": "...",
  "conclusion": "success" | "failure",
  "command": "...",
  "exit_code": 0,
  "test_summary_sha256": "..." | null,
  "artifact_sha256": "..." | null,
  "observed_at": "YYYY-MM-DDTHH:MM:SSZ",
  "details": { ... }            # optional job-specific facts
}

Honesty rules:

- conclusion/exit_code reflect the REAL command exit code; a rerun never
  rewrites a previous attempt (attempt is part of the receipt identity);
- the tool fails closed when the GitHub Actions environment is absent;
- output is canonical JSON: UTF-8, sorted keys, compact separators,
  exactly one trailing newline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RECEIPT_SCHEMA_VERSION = 2
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")

REQUIRED_ENV = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_receipt_bytes(receipt: dict) -> bytes:
    return (
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        + b"\n"
    )


def build_receipt(
    *,
    env: dict[str, str],
    job_name: str,
    command: str,
    exit_code: int,
    summary_file: Path | None,
    artifact_file: Path | None,
    details: dict | None,
    observed_at: str | None = None,
) -> dict:
    missing = [name for name in REQUIRED_ENV if not env.get(name)]
    if missing:
        raise SystemExit(f"missing required CI environment: {','.join(missing)}")
    commit_sha = env["GITHUB_SHA"]
    if not _SHA40_RE.match(commit_sha):
        raise SystemExit("GITHUB_SHA is not a 40-char lowercase hex sha")
    if not job_name:
        raise SystemExit("job_name must be non-empty")
    if not command:
        raise SystemExit("command must be non-empty")

    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "workflow_run_id": env["GITHUB_RUN_ID"],
        "workflow_run_attempt": env["GITHUB_RUN_ATTEMPT"],
        "job_name": job_name,
        "commit_sha": commit_sha,
        "conclusion": "success" if exit_code == 0 else "failure",
        "command": command,
        "exit_code": exit_code,
        "test_summary_sha256": (
            _sha256_file(summary_file) if summary_file is not None else None
        ),
        "artifact_sha256": (
            _sha256_file(artifact_file) if artifact_file is not None else None
        ),
        "observed_at": observed_at or _utc_now(),
    }
    if details is not None:
        if not isinstance(details, dict):
            raise SystemExit("details must be a JSON object")
        receipt["details"] = details
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--summary-file", type=Path, default=None)
    parser.add_argument("--artifact-file", type=Path, default=None)
    parser.add_argument("--details-json", type=Path, default=None)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    for label, path in (("summary", args.summary_file), ("artifact", args.artifact_file)):
        if path is not None and not path.is_file():
            print(f"{label} file missing: {path}", file=sys.stderr)
            return 2

    details = None
    if args.details_json is not None:
        try:
            details = json.loads(args.details_json.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"details json unreadable: {exc}", file=sys.stderr)
            return 2

    try:
        receipt = build_receipt(
            env=dict(os.environ),
            job_name=args.job_name,
            command=args.command,
            exit_code=args.exit_code,
            summary_file=args.summary_file,
            artifact_file=args.artifact_file,
            details=details,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    payload = canonical_receipt_bytes(receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    print(payload.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
