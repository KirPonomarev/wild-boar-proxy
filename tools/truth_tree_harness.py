# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping


Snapshot = dict[str, dict[str, object]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_paths(paths: Mapping[str, Path] | Iterable[Path]) -> dict[str, Path]:
    if isinstance(paths, Mapping):
        return {str(label): Path(path) for label, path in paths.items()}
    return {str(Path(path)): Path(path) for path in paths}


def snapshot_truth_tree(
    paths: Mapping[str, Path] | Iterable[Path],
    *,
    secret_labels: set[str] | frozenset[str] | None = None,
) -> Snapshot:
    secret_labels = secret_labels or set()
    snapshot: Snapshot = {}
    for label, raw_path in sorted(_normalize_paths(paths).items()):
        path = Path(raw_path)
        if not path.exists():
            snapshot[label] = {
                "path": str(path),
                "exists": False,
                "kind": "missing",
            }
            continue
        stat_result = path.stat()
        entry: dict[str, object] = {
            "path": str(path),
            "exists": True,
            "kind": "other",
            "size": stat_result.st_size,
            "mode": stat_result.st_mode & 0o777,
            "mtime_ns": stat_result.st_mtime_ns,
        }
        if path.is_file():
            entry["kind"] = "file"
            if label not in secret_labels:
                entry["sha256"] = _sha256(path)
        elif path.is_dir():
            entries = sorted(child.name for child in path.iterdir())
            entry["kind"] = "dir"
            entry["entries"] = entries
            entry["sha256"] = _stable_digest(entries)
        snapshot[label] = entry
    return snapshot


def changed_truth_labels(before: Snapshot, after: Snapshot) -> list[str]:
    labels = sorted(set(before) | set(after))
    return [
        label
        for label in labels
        if _comparable_entry(before.get(label)) != _comparable_entry(after.get(label))
    ]


def _comparable_entry(entry: dict[str, object] | None) -> dict[str, object] | None:
    if entry is None:
        return None
    comparable = dict(entry)
    comparable.pop("mtime_ns", None)
    return comparable


def changed_truth_paths(before: Snapshot, after: Snapshot) -> set[str]:
    paths: set[str] = set()
    combined = {**before, **after}
    for label in changed_truth_labels(before, after):
        entry = combined.get(label, {})
        path = entry.get("path")
        if isinstance(path, str):
            paths.add(path)
    return paths


def assert_no_truth_mutation(before: Snapshot, after: Snapshot) -> None:
    changed = changed_truth_labels(before, after)
    if changed:
        raise AssertionError(f"Unexpected truth-tree mutation: {changed}")


def assert_declared_mutations_match(
    before: Snapshot,
    after: Snapshot,
    changed_files: Iterable[str],
) -> None:
    changed_labels = changed_truth_labels(before, after)
    label_by_path = {
        str(entry["path"]): label
        for label, entry in {**before, **after}.items()
        if "path" in entry
    }
    declared_paths = sorted(str(Path(path)) for path in changed_files)
    outside_scope = [path for path in declared_paths if path not in label_by_path]
    if outside_scope:
        raise AssertionError(
            "changed_files contains paths outside truth-tree scope: "
            f"{outside_scope}"
        )
    declared_labels = sorted({label_by_path[path] for path in declared_paths})
    if changed_labels != declared_labels:
        raise AssertionError(
            "changed_files does not match truth-tree mutations: "
            f"actual={changed_labels} declared={declared_labels}"
        )
