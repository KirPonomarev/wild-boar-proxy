#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_STAGED_BYTES = 5 * 1024 * 1024

FORBIDDEN_PLAN_FILE_PATTERN = re.compile(
    r"(^|/)(MASTER_PLAN|NEXT_CONTOUR_CANON_PLAN|EXECUTION_WAVE_1|"
    r".*[Pp]lan.*|.*master_plan.*|.*roadmap.*|recommended_next_contour|"
    r"next_.*contour|.*next.*contour.*|handoff_to_next_contour)\."
    r"(md|json|txt)$"
)
FORBIDDEN_PERSONAL_PATH_LITERALS = (
    b"kirillponomarev",
    b"/Users/kirillponomarev",
)


@dataclass(frozen=True)
class SecretPattern:
    name: str
    pattern: re.Pattern[bytes]


SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    SecretPattern("openai_style_token", re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("anthropic_style_token", re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern("github_token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    SecretPattern("bearer_token", re.compile(rb"\bBearer\s+[A-Za-z0-9_./+=-]{20,}\b")),
    SecretPattern(
        "generic_secret_assignment",
        re.compile(
            rb"(?i)(?:^|[\s,{])"
            rb"(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            rb"\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{16,})"
        ),
    ),
)


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def discover_repo_root(cwd: Path | None = None) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "not a git repository"
        raise RuntimeError(message)
    return Path(result.stdout.strip()).resolve()


def staged_paths(repo_root: Path) -> list[str]:
    result = _run_git(
        repo_root,
        ["diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z"],
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "failed to inspect staged paths")
    return [
        path.decode("utf-8", errors="surrogateescape")
        for path in result.stdout.split(b"\0")
        if path
    ]


def staged_blob_size(repo_root: Path, path: str) -> int:
    result = _run_git(repo_root, ["cat-file", "-s", f":{path}"])
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"failed to read staged blob size for {path}")
    return int(result.stdout.strip())


def staged_blob_bytes(repo_root: Path, path: str) -> bytes:
    result = _run_git(repo_root, ["show", f":{path}"])
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or f"failed to read staged blob for {path}")
    return result.stdout


def _match_digest(match: bytes) -> str:
    return hashlib.sha256(match).hexdigest()[:16]


def _finding(
    *,
    check: str,
    path: str,
    reason: str,
    evidence: str | None = None,
) -> dict[str, str]:
    finding = {"check": check, "path": path, "reason": reason}
    if evidence is not None:
        finding["evidence"] = evidence
    return finding


def inspect_path_policy(path: str) -> list[dict[str, str]]:
    if FORBIDDEN_PLAN_FILE_PATTERN.search(path):
        return [
            _finding(
                check="repo_plan_file",
                path=path,
                reason="repo-resident plan/roadmap/next-contour files are forbidden",
            )
        ]
    return []


def inspect_large_file(path: str, size: int, *, max_bytes: int) -> list[dict[str, str]]:
    if size <= max_bytes:
        return []
    return [
        _finding(
            check="large_file",
            path=path,
            reason=f"staged blob is {size} bytes; limit is {max_bytes} bytes",
        )
    ]


def inspect_secret_leaks(path: str, payload: bytes) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for secret_pattern in SECRET_PATTERNS:
        for match in secret_pattern.pattern.finditer(payload):
            findings.append(
                _finding(
                    check="secret_scan",
                    path=path,
                    reason=f"matched {secret_pattern.name}",
                    evidence=f"sha256:{_match_digest(match.group(0))}",
                )
            )
    return findings


def inspect_personal_paths(path: str, payload: bytes) -> list[dict[str, str]]:
    if not path.startswith("wild_boar_proxy/"):
        return []
    findings: list[dict[str, str]] = []
    for literal in FORBIDDEN_PERSONAL_PATH_LITERALS:
        if literal in payload:
            findings.append(
                _finding(
                    check="personal_path",
                    path=path,
                    reason="production package stores a personal path literal",
                    evidence=f"sha256:{_match_digest(literal)}",
                )
            )
    return findings


def inspect_staged_repo_hygiene(
    repo_root: Path,
    *,
    max_bytes: int = DEFAULT_MAX_STAGED_BYTES,
) -> dict[str, Any]:
    paths = staged_paths(repo_root)
    findings: list[dict[str, str]] = []
    checked_files: list[dict[str, Any]] = []

    for path in paths:
        size = staged_blob_size(repo_root, path)
        checked_files.append({"path": path, "size": size})
        findings.extend(inspect_path_policy(path))
        findings.extend(inspect_large_file(path, size, max_bytes=max_bytes))
        if size <= max_bytes:
            payload = staged_blob_bytes(repo_root, path)
            findings.extend(inspect_secret_leaks(path, payload))
            findings.extend(inspect_personal_paths(path, payload))

    return {
        "status": "blocked" if findings else "ok",
        "mode": "staged-only",
        "max_bytes": max_bytes,
        "checked_files": checked_files,
        "findings": findings,
    }


def render_text_report(report: dict[str, Any]) -> str:
    if report["status"] == "ok":
        return (
            "Repo hygiene check passed: "
            f"{len(report['checked_files'])} staged file(s) checked."
        )

    lines = ["Repo hygiene check failed:"]
    for finding in report["findings"]:
        evidence = finding.get("evidence")
        suffix = f" ({evidence})" if evidence else ""
        lines.append(
            f"- {finding['check']}: {finding['path']}: {finding['reason']}{suffix}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate staged repository hygiene before commit."
    )
    parser.add_argument(
        "--staged-only",
        action="store_true",
        help="Validate only staged blobs. This is the supported K1 mode.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_STAGED_BYTES,
        help="Maximum staged blob size allowed by the large-file guard.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Report format.",
    )
    args = parser.parse_args(argv)

    if not args.staged_only:
        print(
            "Repo hygiene check requires --staged-only in this contour.",
            file=sys.stderr,
        )
        return 2

    try:
        repo_root = discover_repo_root()
        report = inspect_staged_repo_hygiene(repo_root, max_bytes=args.max_bytes)
    except Exception as error:
        report = {
            "status": "blocked",
            "mode": "staged-only",
            "findings": [
                _finding(
                    check="repo_hygiene_runtime",
                    path=".",
                    reason=str(error),
                )
            ],
            "checked_files": [],
        }

    if args.format == "json":
        print(json.dumps(report, sort_keys=True))
    else:
        stream = sys.stderr if report["status"] == "blocked" else sys.stdout
        print(render_text_report(report), file=stream)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
