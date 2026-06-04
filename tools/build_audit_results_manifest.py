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
from pathlib import Path
from typing import Any


SECRET_PATTERNS: tuple[re.Pattern[bytes], ...] = (
    re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    re.compile(rb"\bBearer\s+[A-Za-z0-9_./+=-]{20,}\b"),
    re.compile(
        rb"(?i)(?:^|[\s,{])"
        rb"(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
        rb"\s*[:=]\s*['\"]?([A-Za-z0-9_./+=-]{16,})"
    ),
)
PERSONAL_PATH_PATTERNS: tuple[re.Pattern[bytes], ...] = (
    re.compile(rb"/Users/kirillponomarev\b"),
    re.compile(rb"\bkirillponomarev\b"),
)

TEXT_SCAN_CHUNK_BYTES = 1024 * 1024
TEXT_SCAN_OVERLAP_BYTES = 512


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


def _repo_relative(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def tracked_paths(repo_root: Path, audit_root: Path) -> set[str]:
    if not audit_root.exists():
        return set()
    result = _run_git(repo_root, ["ls-files", "-z", "--", _repo_relative(repo_root, audit_root)])
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "failed to list tracked audit_results paths")
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    }


def dirty_state_by_path(repo_root: Path, audit_root: Path) -> dict[str, str]:
    result = _run_git(
        repo_root,
        ["status", "--porcelain=v1", "-z", "--", _repo_relative(repo_root, audit_root)],
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "failed to inspect audit_results status")

    states: dict[str, str] = {}
    records = [record for record in result.stdout.split(b"\0") if record]
    index = 0
    while index < len(records):
        record = records[index]
        status = record[:2].decode("ascii", errors="replace")
        path = record[3:].decode("utf-8", errors="surrogateescape")
        if status == "??":
            states[path] = "untracked"
        elif "D" in status:
            states[path] = "deleted"
        elif status.strip():
            states[path] = "modified"
        else:
            states[path] = "unknown"

        if status[0] in {"R", "C"} and index + 1 < len(records):
            index += 1
        index += 1
    return states


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(TEXT_SCAN_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_dir(path: Path) -> str:
    names = sorted(child.name for child in path.iterdir())
    payload = json.dumps(names, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _matches_any(patterns: tuple[re.Pattern[bytes], ...], payload: bytes) -> bool:
    return any(pattern.search(payload) for pattern in patterns)


def scan_file_flags(path: Path) -> dict[str, bool]:
    contains_secret = False
    contains_personal_path = False
    tail = b""
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(TEXT_SCAN_CHUNK_BYTES), b""):
            payload = tail + chunk
            contains_secret = contains_secret or _matches_any(SECRET_PATTERNS, payload)
            contains_personal_path = contains_personal_path or _matches_any(
                PERSONAL_PATH_PATTERNS,
                payload,
            )
            tail = payload[-TEXT_SCAN_OVERLAP_BYTES:]
            if contains_secret and contains_personal_path:
                break
    return {
        "contains_secret_like_pattern": contains_secret,
        "contains_personal_path_pattern": contains_personal_path,
    }


def evidence_class_for_path(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if "closeout" in name and suffix == ".md":
        return "closeout"
    if "manifest" in name:
        return "manifest"
    if suffix in {".log", ".stdout", ".stderr"} or name.endswith((".stdout.log", ".stderr.log")):
        return "log"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return "image"
    if suffix == ".json" and "packet" in name:
        return "packet"
    if suffix == ".md" and ("spec" in name or name == "contour.md"):
        return "spec"
    return "other"


def dirty_state_for_path(
    repo_path: str,
    *,
    tracked: bool,
    status_map: dict[str, str],
    is_dir: bool,
) -> str:
    if repo_path in status_map:
        return status_map[repo_path]
    if tracked:
        return "clean"
    if is_dir:
        return "unknown"
    return "untracked"


def build_entry(
    repo_root: Path,
    path: Path,
    *,
    tracked: bool,
    status_map: dict[str, str],
) -> dict[str, Any]:
    repo_path = _repo_relative(repo_root, path)
    is_dir = path.is_dir()
    kind = "dir" if is_dir else "file"
    entry: dict[str, Any] = {
        "path": repo_path,
        "kind": kind,
        "size_bytes": 0 if is_dir else path.stat().st_size,
        "sha256": _sha256_dir(path) if is_dir else _sha256_file(path),
        "extension": "" if is_dir else path.suffix.lower(),
        "evidence_class": "other" if is_dir else evidence_class_for_path(path),
        "tracked": tracked,
        "dirty_state": dirty_state_for_path(
            repo_path,
            tracked=tracked,
            status_map=status_map,
            is_dir=is_dir,
        ),
        "contains_secret_like_pattern": False,
        "contains_personal_path_pattern": False,
    }
    if not is_dir:
        entry.update(scan_file_flags(path))
    return entry


def build_deleted_entry(repo_path: str, *, tracked: bool = True) -> dict[str, Any]:
    path = Path(repo_path)
    return {
        "path": repo_path,
        "kind": "file",
        "size_bytes": 0,
        "sha256": None,
        "extension": path.suffix.lower(),
        "evidence_class": evidence_class_for_path(path),
        "tracked": tracked,
        "dirty_state": "deleted",
        "contains_secret_like_pattern": False,
        "contains_personal_path_pattern": False,
    }


def build_manifest(repo_root: Path, audit_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    audit_root = audit_root.resolve()
    tracked = tracked_paths(repo_root, audit_root)
    status_map = dirty_state_by_path(repo_root, audit_root)

    paths: list[Path] = []
    if audit_root.exists():
        paths = sorted(audit_root.rglob("*"), key=lambda item: _repo_relative(repo_root, item))

    entries = [
        build_entry(
            repo_root,
            path,
            tracked=_repo_relative(repo_root, path) in tracked,
            status_map=status_map,
        )
        for path in paths
    ]
    existing_paths = {entry["path"] for entry in entries}
    entries.extend(
        build_deleted_entry(repo_path, tracked=repo_path in tracked)
        for repo_path, state in sorted(status_map.items())
        if state == "deleted" and repo_path not in existing_paths
    )
    entries.sort(key=lambda entry: entry["path"])
    summary: dict[str, Any] = {
        "entries_total": len(entries),
        "files_total": sum(1 for entry in entries if entry["kind"] == "file"),
        "dirs_total": sum(1 for entry in entries if entry["kind"] == "dir"),
        "tracked_total": sum(1 for entry in entries if entry["tracked"]),
        "dirty_total": sum(
            1
            for entry in entries
            if entry["dirty_state"] in {"modified", "untracked", "deleted"}
        ),
        "unknown_state_total": sum(
            1 for entry in entries if entry["dirty_state"] == "unknown"
        ),
        "secret_like_entries": sum(
            1 for entry in entries if entry["contains_secret_like_pattern"]
        ),
        "personal_path_entries": sum(
            1 for entry in entries if entry["contains_personal_path_pattern"]
        ),
    }
    return {
        "schema_version": 1,
        "artifact_type": "audit_results_redacted_inventory",
        "source_root": _repo_relative(repo_root, audit_root),
        "summary": summary,
        "entries": entries,
    }


def manifest_json_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(
        manifest,
        sort_keys=True,
        indent=2,
        separators=(",", ": "),
    ).encode("utf-8")


def validate_manifest_redaction(manifest: dict[str, Any]) -> list[str]:
    payload = manifest_json_bytes(manifest)
    errors: list[str] = []
    if _matches_any(SECRET_PATTERNS, payload):
        errors.append("manifest contains raw secret-like value")
    if _matches_any(PERSONAL_PATH_PATTERNS, payload):
        errors.append("manifest contains raw personal path value")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a redacted metadata-only inventory for audit_results."
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Repository root. Defaults to git rev-parse --show-toplevel.",
    )
    parser.add_argument(
        "--audit-root",
        type=Path,
        default=Path("audit_results"),
        help="Audit results directory, absolute or relative to --root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write manifest JSON to this path. Defaults to stdout.",
    )
    parser.add_argument(
        "--check-redaction",
        action="store_true",
        help="Fail if the generated manifest contains raw secret or personal path values.",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = (args.root or discover_repo_root()).resolve()
        audit_root = args.audit_root
        if not audit_root.is_absolute():
            audit_root = repo_root / audit_root
        manifest = build_manifest(repo_root, audit_root)
        errors = validate_manifest_redaction(manifest) if args.check_redaction else []
        if errors:
            for error in errors:
                print(f"Audit manifest redaction check failed: {error}", file=sys.stderr)
            return 1

        payload = manifest_json_bytes(manifest) + b"\n"
        if args.output:
            output_path = args.output
            if not output_path.is_absolute():
                output_path = Path.cwd() / output_path
            output_path = output_path.resolve()
            if _is_relative_to(output_path, audit_root):
                raise RuntimeError("refusing to write manifest under audit_results")
            if _is_relative_to(output_path, repo_root):
                raise RuntimeError("refusing to write manifest under repository root")
            output_path.write_bytes(payload)
        else:
            sys.stdout.buffer.write(payload)
        return 0
    except Exception as error:
        print(f"Audit manifest build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
