# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping


Snapshot = dict[str, dict[str, object]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_truth_tree(
    paths: Mapping[str, Path],
    *,
    secret_labels: set[str] | frozenset[str] | None = None,
) -> Snapshot:
    secret_labels = secret_labels or set()
    snapshot: Snapshot = {}
    for label, raw_path in sorted(paths.items()):
        path = Path(raw_path)
        if not path.exists():
            snapshot[label] = {
                "path": str(path),
                "exists": False,
            }
            continue
        stat_result = path.stat()
        entry: dict[str, object] = {
            "path": str(path),
            "exists": True,
            "size": stat_result.st_size,
            "mode": stat_result.st_mode & 0o777,
            "mtime_ns": stat_result.st_mtime_ns,
        }
        if label not in secret_labels:
            entry["sha256"] = _sha256(path)
        snapshot[label] = entry
    return snapshot


def changed_truth_labels(before: Snapshot, after: Snapshot) -> list[str]:
    labels = sorted(set(before) | set(after))
    return [label for label in labels if before.get(label) != after.get(label)]


def assert_no_truth_mutation(before: Snapshot, after: Snapshot) -> None:
    changed = changed_truth_labels(before, after)
    if changed:
        raise AssertionError(f"Unexpected truth-tree mutation: {changed}")


def assert_declared_mutations_match(
    before: Snapshot,
    after: Snapshot,
    changed_files: list[str],
) -> None:
    changed_labels = changed_truth_labels(before, after)
    label_by_path = {
        str(entry["path"]): label
        for label, entry in {**before, **after}.items()
        if "path" in entry
    }
    declared_labels = sorted(
        {
            label_by_path[str(Path(path))]
            for path in changed_files
            if str(Path(path)) in label_by_path
        }
    )
    if changed_labels != declared_labels:
        raise AssertionError(
            "changed_files does not match truth-tree mutations: "
            f"actual={changed_labels} declared={declared_labels}"
        )
