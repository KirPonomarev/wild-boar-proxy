#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


OK = "OK"
PUSH_NON_FAST_FORWARD_BLOCKED = "PUSH_NON_FAST_FORWARD_BLOCKED"
PUSH_BRANCH_DELETE_BLOCKED = "PUSH_BRANCH_DELETE_BLOCKED"
PUSH_ANCESTRY_UNPROVEN = "PUSH_ANCESTRY_UNPROVEN"
PUSH_INPUT_INVALID = "PUSH_INPUT_INVALID"

_OBJECT_ID = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


@dataclass(frozen=True)
class PushUpdate:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str


class PushInputError(ValueError):
    pass


def discover_repo_root(cwd: Path | None = None) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("git repository root could not be resolved")
    return Path(result.stdout.strip()).resolve()


def _is_object_id(value: str) -> bool:
    return _OBJECT_ID.fullmatch(value) is not None


def _is_zero_object_id(value: str) -> bool:
    return _is_object_id(value) and set(value) == {"0"}


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _commit_exists(repo_root: Path, object_id: str) -> bool:
    result = _run_git(repo_root, "cat-file", "-e", f"{object_id}^{{commit}}")
    return result.returncode == 0


def _result(
    update: PushUpdate,
    *,
    code: str,
    status: str,
    reason: str,
    disposition: str,
) -> dict[str, str]:
    return {
        "code": code,
        "disposition": disposition,
        "local_ref": update.local_ref,
        "local_sha": update.local_sha.lower(),
        "reason": reason,
        "remote_ref": update.remote_ref,
        "remote_sha": update.remote_sha.lower(),
        "status": status,
    }


def validate_update(update: PushUpdate) -> None:
    if not update.local_ref or not update.remote_ref.startswith("refs/"):
        raise PushInputError("push refs must be nonempty and remote ref must be full")
    if not _is_object_id(update.local_sha):
        raise PushInputError("local object id must be 40 or 64 hexadecimal characters")
    if not _is_object_id(update.remote_sha):
        raise PushInputError("remote object id must be 40 or 64 hexadecimal characters")
    if len(update.local_sha) != len(update.remote_sha):
        raise PushInputError("local and remote object ids must use the same hash format")


def inspect_update(repo_root: Path, update: PushUpdate) -> dict[str, str]:
    validate_update(update)

    if not update.remote_ref.startswith("refs/heads/"):
        return _result(
            update,
            code=OK,
            status="ok",
            reason="non-branch ref is outside the ancestry guard",
            disposition="ignored",
        )

    if _is_zero_object_id(update.local_sha):
        return _result(
            update,
            code=PUSH_BRANCH_DELETE_BLOCKED,
            status="blocked",
            reason="remote branch deletion is forbidden by delivery policy",
            disposition="blocked",
        )

    if not _commit_exists(repo_root, update.local_sha):
        return _result(
            update,
            code=PUSH_ANCESTRY_UNPROVEN,
            status="blocked",
            reason="local object is not available as a commit",
            disposition="blocked",
        )

    if _is_zero_object_id(update.remote_sha):
        return _result(
            update,
            code=OK,
            status="ok",
            reason="new remote branch starts from a proven local commit",
            disposition="allowed",
        )

    if not _commit_exists(repo_root, update.remote_sha):
        return _result(
            update,
            code=PUSH_ANCESTRY_UNPROVEN,
            status="blocked",
            reason="remote commit is unavailable; fetch it before pushing",
            disposition="blocked",
        )

    ancestry = _run_git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        update.remote_sha,
        update.local_sha,
    )
    if ancestry.returncode == 0:
        return _result(
            update,
            code=OK,
            status="ok",
            reason="remote commit is an ancestor of the local commit",
            disposition="allowed",
        )
    if ancestry.returncode == 1:
        return _result(
            update,
            code=PUSH_NON_FAST_FORWARD_BLOCKED,
            status="blocked",
            reason="remote commit is not an ancestor of the local commit",
            disposition="blocked",
        )
    return _result(
        update,
        code=PUSH_ANCESTRY_UNPROVEN,
        status="blocked",
        reason="git could not prove branch ancestry",
        disposition="blocked",
    )


def parse_pre_push_input(lines: Iterable[str]) -> list[PushUpdate]:
    updates: list[PushUpdate] = []
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        if not line:
            raise PushInputError(f"pre-push input line {line_number} is empty")
        fields = line.split()
        if len(fields) != 4:
            raise PushInputError(
                f"pre-push input line {line_number} must contain four fields"
            )
        update = PushUpdate(*fields)
        validate_update(update)
        updates.append(update)
    return updates


def inspect_updates(
    repo_root: Path,
    updates: list[PushUpdate],
    *,
    mode: str,
) -> dict[str, Any]:
    results = [inspect_update(repo_root, update) for update in updates]
    first_blocked = next(
        (result for result in results if result["status"] == "blocked"),
        None,
    )
    return {
        "code": first_blocked["code"] if first_blocked else OK,
        "mode": mode,
        "status": "blocked" if first_blocked else "ok",
        "updates": results,
    }


def invalid_packet(*, mode: str, reason: str) -> dict[str, Any]:
    return {
        "code": PUSH_INPUT_INVALID,
        "mode": mode,
        "reason": reason,
        "status": "blocked",
        "updates": [],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fail-closed branch push ancestry guard"
    )
    parser.add_argument("--previous", help="remote/before commit for CI mode")
    parser.add_argument("--current", help="local/after commit for CI mode")
    parser.add_argument("--ref", help="full target ref for CI mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ci_values = (args.previous, args.current, args.ref)
    ci_mode = any(value is not None for value in ci_values)
    mode = "ci" if ci_mode else "pre-push"

    try:
        repo_root = discover_repo_root()
        if ci_mode:
            if not all(value is not None for value in ci_values):
                raise PushInputError(
                    "CI mode requires --previous, --current, and --ref"
                )
            update = PushUpdate(
                local_ref=args.ref,
                local_sha=args.current,
                remote_ref=args.ref,
                remote_sha=args.previous,
            )
            validate_update(update)
            updates = [update]
        else:
            updates = parse_pre_push_input(sys.stdin)
        packet = inspect_updates(repo_root, updates, mode=mode)
    except (PushInputError, RuntimeError) as exc:
        packet = invalid_packet(mode=mode, reason=str(exc))

    print(json.dumps(packet, sort_keys=True, separators=(",", ":")))
    return 0 if packet["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
