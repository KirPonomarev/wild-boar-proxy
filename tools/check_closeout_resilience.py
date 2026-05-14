#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import re
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

PLACEHOLDER_TOKENS = (
    "[",
    "]",
    "todo",
    "tbd",
    "n/a",
    "none",
    "not set",
    "fill",
)

FIELD_REGEX = {
    "goal": re.compile(r"^\s*-\s*goal:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE),
    "branch": re.compile(r"^\s*-\s*branch:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE),
    "head": re.compile(r"^\s*-\s*head:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE),
    "touched files": re.compile(
        r"^\s*-\s*touched files:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE
    ),
    "tests run": re.compile(
        r"^\s*-\s*tests run:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE
    ),
    "blocked risks": re.compile(
        r"^\s*-\s*blocked risks:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE
    ),
    "next exact command": re.compile(
        r"^\s*-\s*next exact command:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE
    ),
    "resume from here": re.compile(
        r"^\s*-\s*resume from here:\s*(.+?)\s*$", flags=re.IGNORECASE | re.MULTILINE
    ),
}


def is_closeout_path(path: Path) -> bool:
    return (
        path.suffix == ".md"
        and "closeout" in path.name.lower()
        and any(part == "audit_results" for part in path.parts)
    )


def _changed_paths(repo_root: Path, command: tuple[str, ...]) -> set[Path]:
    candidates: set[Path] = set()
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return candidates
    for line in result.stdout.splitlines():
        path = repo_root / line.strip()
        if is_closeout_path(path):
            candidates.add(path)
    return candidates


def changed_closeout_paths(
    repo_root: Path,
    *,
    include_worktree: bool = True,
    include_staged: bool = True,
) -> list[Path]:
    candidates: set[Path] = set()
    if include_worktree:
        candidates.update(
            _changed_paths(
                repo_root,
                ("git", "diff", "--name-only", "--diff-filter=ACMRT", "HEAD", "--", "audit_results"),
            )
        )
    if include_staged:
        candidates.update(
            _changed_paths(
                repo_root,
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
        )
    return sorted(candidates)


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    if normalized in PLACEHOLDER_TOKENS:
        return True
    return any(token in normalized for token in ("[exact", "[what", "[contour"))


def _field_value(text: str, field_name: str) -> str | None:
    pattern = FIELD_REGEX[field_name]
    match = pattern.search(text)
    if not match:
        return None
    return match.group(1).strip()


def validate_closeout(path: Path) -> list[str]:
    if not path.exists():
        return [f"{path}: file does not exist"]
    text = path.read_text(encoding="utf-8")
    normalized = text.lower()
    errors: list[str] = []
    for phrase in REQUIRED_PHRASES:
        if phrase.lower() not in normalized:
            errors.append(f"{path}: missing required closeout field `{phrase}`")

    for field_name in (
        "goal",
        "branch",
        "head",
        "touched files",
        "tests run",
        "blocked risks",
        "next exact command",
        "resume from here",
    ):
        value = _field_value(text, field_name)
        if value is None:
            continue
        if _looks_like_placeholder(value):
            errors.append(f"{path}: field `{field_name}` is empty or placeholder")

    resume = _field_value(text, "resume from here")
    if resume and resume.strip().upper() != "CLOSED" and resume.strip().lower().startswith("closed /"):
        errors.append(
            f"{path}: field `resume from here` should be `CLOSED` or an exact next contour/command"
        )
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
    parser.add_argument(
        "--staged-only",
        action="store_true",
        help="Validate only staged closeout files (for pre-commit hooks).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[1]
    paths = [Path(path) for path in args.paths]
    if not paths:
        paths = changed_closeout_paths(
            repo_root,
            include_worktree=not args.staged_only,
            include_staged=True,
        )

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
