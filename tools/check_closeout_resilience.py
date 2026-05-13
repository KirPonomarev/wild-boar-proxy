#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REQUIRED_PHRASES = (
    "## Contour Capsule",
    "- goal:",
    "- branch:",
    "- head:",
    "- touched files:",
    "- tests run:",
    "- blocked risks:",
    "- next exact command:",
    "resume from here:",
)


def is_closeout_path(path: Path) -> bool:
    return (
        path.suffix == ".md"
        and "closeout" in path.name.lower()
        and any(part == "audit_results" for part in path.parts)
    )


def changed_closeout_paths(repo_root: Path) -> list[Path]:
    candidates: set[Path] = set()
    commands = (
        ("git", "diff", "--name-only", "--diff-filter=ACMRT", "HEAD", "--", "audit_results"),
        (
            "git",
            "diff",
            "--name-only",
            "--cached",
            "--diff-filter=ACMRT",
            "HEAD",
            "--",
            "audit_results",
        ),
    )
    for command in commands:
        result = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            path = repo_root / line.strip()
            if is_closeout_path(path):
                candidates.add(path)
    return sorted(candidates)


def validate_closeout(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path}: file does not exist"]
    text = path.read_text(encoding="utf-8")
    normalized = text.lower()
    errors: list[str] = []
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() not in normalized:
            errors.append(f"{path}: missing required closeout field `{phrase}`")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate thread-compaction resilience fields in new or changed "
            "audit_results/*closeout*.md files."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Closeout files to validate. Defaults to changed closeout files.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    paths = [Path(path) for path in args.paths]
    if not paths:
        paths = changed_closeout_paths(repo_root)

    errors: list[str] = []
    for path in paths:
        full_path = path if path.is_absolute() else repo_root / path
        if not is_closeout_path(full_path):
            continue
        errors.extend(validate_closeout(full_path))

    if errors:
        print("Closeout resilience check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
