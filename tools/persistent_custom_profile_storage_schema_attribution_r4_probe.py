#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""R4 read-only schema attribution for Persistent Custom profile storage.

R4 narrows local restoration hypotheses by schema/structure only. It does not
launch Codex, mutate the profile, dump row values, or claim durable restoration
proof.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.persistent_custom_profile_storage_truth_r3_probe import (  # noqa: E402
    DEFAULT_EVIDENCE_DIR as DEFAULT_R3_EVIDENCE_DIR,
    _packet_file_metadata,
    classify_r3_storage_state_class,
)
from wild_boar_proxy.native_filesystem_probe import (  # noqa: E402
    default_persistent_custom_profile_paths,
    json_write,
)


DEFAULT_EVIDENCE_DIR = (
    ROOT / "audit_results/wbp_persistent_custom_profile_storage_schema_attribution_r4_2026-05-27"
)
MAX_CANDIDATES = 300
MAX_JSON_BYTES = 512 * 1024
MAX_JSONL_LINES_TO_SHAPE = 50
MAX_KEY_PATHS = 120

SQLITE_SUFFIXES = {".sqlite", ".sqlite3", ".db"}
JSON_SUFFIXES = {".json"}
JSONL_SUFFIXES = {".jsonl", ".ndjson"}
SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "token",
    "secret",
    "password",
    "credential",
)
SENSITIVE_PATH_TOKENS = (
    "auth.json",
    "token",
    "secret",
    "credential",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(repo_root: Path, command: list[str], *, check: bool = False) -> str:
    process = subprocess.run(
        command,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and process.returncode != 0:
        raise RuntimeError(
            f"{' '.join(command)} failed with {process.returncode}: {process.stderr.strip()}"
        )
    return process.stdout.strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _historical_quarantine(
    repo_root: Path,
    evidence_dir: Path,
    *,
    skip_git: bool = False,
) -> tuple[list[str], list[str]]:
    if skip_git:
        return [], []
    status_lines = _run(repo_root, ["git", "status", "--short"]).splitlines()
    relative_evidence_dir = str(evidence_dir.relative_to(repo_root))
    admitted_current_contour = {
        "tools/persistent_custom_profile_storage_schema_attribution_r4_probe.py",
        "tests/test_native_filesystem_probe.py",
    }
    quarantined_prefixes = (
        "M audit_results/wbp_codex_native_external_owner_executor_packet_capture_pass_2026-05-25/",
        "M audit_results/wbp_persistent_custom_profile_history_r2_live_2026-05-27/persistent_r2_launcher.stdout.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stderr.log",
        "M audit_results/wbp_persistent_custom_profile_history_r2b_live_2026-05-27/persistent_r2b_launcher.stdout.log",
        "?? audit_results/wbp_host_accessibility_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_host_quartz_enabled_retry_2026-05-25/",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stderr.log",
        "?? audit_results/wbp_persistent_custom_profile_r2c_owner_visible_thread_continuity_2026-05-27/persistent_r2c_launcher.stdout.log",
    )
    current_contour_prefixes = (f"?? {relative_evidence_dir}/",)
    quarantined = [
        line for line in status_lines if line.strip().startswith(quarantined_prefixes)
    ]
    unexpected_dirty = [
        line
        for line in status_lines
        if line not in quarantined
        and not line.strip().startswith(current_contour_prefixes)
        and not any(path in line for path in admitted_current_contour)
    ]
    return quarantined, unexpected_dirty


def build_r4_sync_gate_packet(
    *,
    repo_root: Path,
    evidence_dir: Path,
    skip_git: bool = False,
) -> dict[str, Any]:
    quarantined, unexpected_dirty = _historical_quarantine(
        repo_root,
        evidence_dir,
        skip_git=skip_git,
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_r4_sync_gate",
        "status": "ok" if not unexpected_dirty else "blocked",
        "git_branch": "SKIPPED_FOR_TEST"
        if skip_git
        else _run(repo_root, ["git", "branch", "--show-current"]),
        "git_head": "SKIPPED_FOR_TEST"
        if skip_git
        else _run(repo_root, ["git", "rev-parse", "HEAD"], check=True),
        "git_status_short": []
        if skip_git
        else _run(repo_root, ["git", "status", "--short"]).splitlines(),
        "unexpected_dirty_entries": unexpected_dirty,
        "quarantined_entry_count": len(quarantined),
        "phase": "r4_readonly_schema_attribution",
        "native_launch_attempted": False,
        "live_mutation_attempted": False,
        "owner_action_required": False,
        "master_plan_written_to_repo": False,
    }


def build_r4_r3_reference_packet(*, r3_evidence_dir: Path) -> dict[str, Any]:
    r3_evidence_dir = r3_evidence_dir.expanduser().resolve(strict=False)
    summary_path = r3_evidence_dir / "persistent_storage_r3_summary_packet.json"
    classification_path = r3_evidence_dir / "persistent_storage_truth_classification_packet.json"
    inventory_path = r3_evidence_dir / "persistent_storage_surface_inventory_packet.json"
    missing = [
        str(path)
        for path in (summary_path, classification_path, inventory_path)
        if not path.exists()
    ]
    if missing:
        return {
            "captured_at_utc": _utc_now(),
            "packet_kind": "persistent_storage_r3_reference",
            "status": "blocked",
            "reason_class": "R3_REFERENCE_MISSING",
            "missing_packets": missing,
            "r3_counts_as_r4_proof": False,
        }
    summary = _read_json(summary_path)
    classification = _read_json(classification_path)
    inventory = _read_json(inventory_path)
    expected = (
        summary.get("final_status")
        == "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_STORAGE_TRUTH_CLASSIFIED_WITH_LIMITS"
        and classification.get("storage_level_thread_history_proven") is False
        and classification.get("relaunch_restoration_source_proven") is False
        and inventory.get("metadata_only") is True
    )
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_r3_reference",
        "status": "ok" if expected else "blocked",
        "reason_class": "" if expected else "R3_REFERENCE_OVERCLAIM_OR_UNUSABLE",
        "r3_evidence_dir": str(r3_evidence_dir),
        "referenced_packets": {
            "summary": _packet_file_metadata(summary_path),
            "classification": _packet_file_metadata(classification_path),
            "inventory": _packet_file_metadata(inventory_path),
        },
        "r3_final_status": summary.get("final_status", ""),
        "r3_thread_history_candidate": summary.get("thread_history_candidate") is True,
        "r3_storage_level_thread_history_proven": (
            classification.get("storage_level_thread_history_proven") is True
        ),
        "r3_relaunch_restoration_source_proven": (
            classification.get("relaunch_restoration_source_proven") is True
        ),
        "r3_counts_as_r4_proof": False,
        "r3_inventory_entry_count": inventory.get("entry_count", 0),
        "r3_inventory_state_class_counts": inventory.get("state_class_counts", {}),
        "raw_content_recorded": False,
    }


def classify_candidate_surface_type(relative_path: str, *, kind: str = "file") -> str:
    lower = relative_path.replace("\\", "/").lower()
    suffix = Path(lower).suffix
    if suffix in SQLITE_SUFFIXES:
        return "sqlite"
    if suffix in JSONL_SUFFIXES:
        return "jsonl"
    if suffix in JSON_SUFFIXES:
        return "json"
    if any(token in lower for token in ("leveldb", "indexeddb", "local storage")):
        return "leveldb_like"
    if kind == "dir":
        return "opaque_dir"
    return "opaque_file"


def _is_sensitive_surface_path(relative_path: str) -> bool:
    lower = relative_path.replace("\\", "/").lower()
    return any(token in lower for token in SENSITIVE_PATH_TOKENS)


def _safe_json_key(key: str) -> str:
    lower = key.lower()
    if any(token in lower for token in SENSITIVE_KEY_TOKENS):
        return "<sensitive_key_name_redacted>"
    return key


def _candidate_score(relative_path: str, state_class: str, surface_type: str) -> int:
    lower = relative_path.lower()
    score = 0
    if state_class in {"thread_history", "session_state", "unknown"}:
        score += 10
    if surface_type in {"sqlite", "json", "jsonl", "leveldb_like"}:
        score += 5
    if any(token in lower for token in ("thread", "conversation", "history", "session", "message")):
        score += 5
    return score


def select_candidate_surfaces(
    profile_root: Path,
    *,
    max_candidates: int = MAX_CANDIDATES,
) -> dict[str, Any]:
    profile_root = profile_root.expanduser()
    candidates: list[dict[str, Any]] = []
    if profile_root.exists():
        for path in sorted(profile_root.rglob("*"), key=lambda item: str(item)):
            try:
                stat = path.lstat()
                kind = "dir" if path.is_dir() else "file" if path.is_file() else "symlink" if path.is_symlink() else "other"
            except OSError:
                continue
            relative_path = str(path.relative_to(profile_root))
            if _is_sensitive_surface_path(relative_path):
                continue
            state_class = classify_r3_storage_state_class(relative_path)
            surface_type = classify_candidate_surface_type(relative_path, kind=kind)
            score = _candidate_score(relative_path, state_class, surface_type)
            if score <= 0:
                continue
            candidates.append(
                {
                    "relative_path": relative_path,
                    "kind": kind,
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "state_class": state_class,
                    "surface_type": surface_type,
                    "selection_score": score,
                    "selection_source": "path_metadata_only",
                    "raw_content_recorded": False,
                }
            )
    candidates = sorted(
        candidates,
        key=lambda item: (-int(item["selection_score"]), str(item["relative_path"])),
    )[:max_candidates]
    counts = Counter(item["surface_type"] for item in candidates)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_candidate_selection",
        "status": "ok" if candidates else "blocked",
        "reason_class": "" if candidates else "R4_NO_CANDIDATE_SURFACES",
        "profile_root": str(profile_root),
        "candidate_count": len(candidates),
        "max_candidates": max_candidates,
        "surface_type_counts": dict(sorted(counts.items())),
        "candidates": candidates,
        "metadata_only": True,
        "raw_content_recorded": False,
        "r3_candidate_upgraded_to_proof": False,
    }


def _sqlite_uri(path: Path) -> str:
    return f"file:{path}?mode=ro&immutable=1"


def inspect_sqlite_schema(
    profile_root: Path,
    candidates: list[dict[str, Any]],
    *,
    max_databases: int = 30,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for candidate in [item for item in candidates if item.get("surface_type") == "sqlite"][:max_databases]:
        relative_path = str(candidate["relative_path"])
        db_path = profile_root / relative_path
        database: dict[str, Any] = {
            "relative_path": relative_path,
            "size": candidate.get("size", 0),
            "mtime_ns": candidate.get("mtime_ns", 0),
            "opened_readonly": False,
            "schema_observed": False,
            "tables": [],
            "views": [],
            "indexes": [],
            "triggers": [],
            "row_values_recorded": False,
            "raw_content_recorded": False,
            "semantic_content_classified": False,
            "durable_restoration_proven": False,
        }
        try:
            connection = sqlite3.connect(_sqlite_uri(db_path), uri=True, timeout=1)
            try:
                connection.row_factory = sqlite3.Row
                database["opened_readonly"] = True
                table_names = [
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    )
                ]
                view_names = [
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_schema WHERE type='view' ORDER BY name"
                    )
                ]
                trigger_names = [
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_schema WHERE type='trigger' ORDER BY name"
                    )
                ]
                indexes = [
                    {"name": row["name"], "table_name": row["tbl_name"]}
                    for row in connection.execute(
                        "SELECT name, tbl_name FROM sqlite_schema WHERE type='index' ORDER BY name"
                    )
                ]
                tables = []
                for table_name in table_names:
                    columns = [
                        {
                            "name": row["name"],
                            "type": row["type"],
                            "notnull": bool(row["notnull"]),
                            "pk": bool(row["pk"]),
                        }
                        for row in connection.execute(f"PRAGMA table_info({table_name!r})")
                    ]
                    try:
                        row_count = connection.execute(
                            f'SELECT COUNT(*) AS count FROM "{table_name.replace(chr(34), chr(34) + chr(34))}"'
                        ).fetchone()["count"]
                    except sqlite3.Error:
                        row_count = None
                    tables.append(
                        {
                            "name": table_name,
                            "columns": columns,
                            "row_count": row_count,
                            "row_count_counts_as_thread_count": False,
                            "row_values_recorded": False,
                        }
                    )
                database.update(
                    {
                        "schema_observed": bool(table_names or view_names or indexes or trigger_names),
                        "tables": tables,
                        "views": view_names,
                        "indexes": indexes,
                        "triggers": trigger_names,
                    }
                )
            finally:
                connection.close()
        except sqlite3.Error as exc:
            database["error_class"] = type(exc).__name__
            database["error_message_recorded"] = False
        rows.append(database)
    observed = sum(1 for row in rows if row.get("schema_observed") is True)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_sqlite_schema",
        "status": "ok" if observed else "blocked" if rows else "ok",
        "reason_class": "" if observed or not rows else "SQLITE_SCHEMA_NOT_OBSERVED",
        "database_count": len(rows),
        "schema_observed_count": observed,
        "databases": rows,
        "sqlite_open_mode": "uri_mode_ro_immutable",
        "row_values_recorded": False,
        "raw_content_recorded": False,
        "row_count_counts_as_thread_count": False,
        "row_count_counts_as_thread_history_preservation": False,
        "durable_restoration_proven": False,
    }


def _json_shape(value: Any, *, depth: int = 0, prefix: str = "") -> dict[str, Any]:
    if depth >= 4:
        return {"type": type(value).__name__, "depth_limited": True, "value_recorded": False}
    if isinstance(value, dict):
        original_keys = sorted(str(key) for key in value.keys())[:MAX_KEY_PATHS]
        keys = [_safe_json_key(key) for key in original_keys]
        children = {}
        for key in original_keys[:30]:
            safe_key = _safe_json_key(key)
            children[safe_key] = _json_shape(
                value[key],
                depth=depth + 1,
                prefix=f"{prefix}.{safe_key}" if prefix else safe_key,
            )
        return {
            "type": "object",
            "key_count": len(value),
            "keys": keys,
            "children": children,
            "values_recorded": False,
            "sensitive_key_names_redacted": any(key != safe for key, safe in zip(original_keys, keys)),
        }
    if isinstance(value, list):
        item_types = sorted({type(item).__name__ for item in value[:100]})
        return {
            "type": "array",
            "length": len(value),
            "sample_item_types": item_types,
            "values_recorded": False,
        }
    return {
        "type": type(value).__name__,
        "value_recorded": False,
    }


def inspect_json_shapes(
    profile_root: Path,
    candidates: list[dict[str, Any]],
    *,
    max_files: int = 60,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    json_candidates = [
        item for item in candidates if item.get("surface_type") in {"json", "jsonl"}
    ][:max_files]
    for candidate in json_candidates:
        relative_path = str(candidate["relative_path"])
        path = profile_root / relative_path
        item: dict[str, Any] = {
            "relative_path": relative_path,
            "surface_type": candidate.get("surface_type"),
            "size": candidate.get("size", 0),
            "mtime_ns": candidate.get("mtime_ns", 0),
            "shape_observed": False,
            "raw_lines_recorded": False,
            "raw_values_recorded": False,
            "semantic_content_classified": False,
            "durable_restoration_proven": False,
        }
        try:
            if int(candidate.get("size", 0)) > MAX_JSON_BYTES:
                item["skipped_reason"] = "JSON_FILE_TOO_LARGE_FOR_BOUNDED_SHAPE"
            elif candidate.get("surface_type") == "json":
                value = json.loads(path.read_text(encoding="utf-8"))
                item["shape"] = _json_shape(value)
                item["shape_observed"] = True
            else:
                line_count = 0
                shape_counter: Counter[str] = Counter()
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line_count += 1
                        if line_count <= MAX_JSONL_LINES_TO_SHAPE:
                            try:
                                value = json.loads(line)
                            except json.JSONDecodeError:
                                shape_counter["parse_error"] += 1
                            else:
                                shape_counter[_json_shape(value).get("type", "unknown")] += 1
                item["line_count"] = line_count
                item["bounded_shape_type_counts"] = dict(sorted(shape_counter.items()))
                item["shape_observed"] = line_count > 0
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            item["error_class"] = type(exc).__name__
            item["error_message_recorded"] = False
        rows.append(item)
    observed = sum(1 for row in rows if row.get("shape_observed") is True)
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_json_shape",
        "status": "ok" if observed or not rows else "blocked",
        "reason_class": "" if observed or not rows else "JSON_SHAPE_NOT_OBSERVED",
        "json_surface_count": len(rows),
        "shape_observed_count": observed,
        "surfaces": rows,
        "keys_types_counts_only": True,
        "raw_values_recorded": False,
        "raw_lines_recorded": False,
        "semantic_content_classified": False,
        "durable_restoration_proven": False,
    }


def build_opaque_surface_packet(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    opaque = [
        item
        for item in candidates
        if item.get("surface_type") in {"leveldb_like", "opaque_dir", "opaque_file"}
    ]
    rows = [
        {
            "relative_path": item.get("relative_path"),
            "kind": item.get("kind"),
            "size": item.get("size"),
            "mtime_ns": item.get("mtime_ns"),
            "surface_type": item.get("surface_type"),
            "state_class": item.get("state_class"),
            "opaque_storage_surface_observed": True,
            "restoration_source_hypothesis_unproven": True,
            "key_value_dump_recorded": False,
            "raw_content_recorded": False,
            "durable_restoration_proven": False,
        }
        for item in opaque[:MAX_CANDIDATES]
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_opaque_surface",
        "status": "ok",
        "opaque_surface_count": len(rows),
        "surfaces": rows,
        "key_value_dump_recorded": False,
        "raw_content_recorded": False,
        "durable_restoration_proven": False,
    }


def build_schema_attribution_matrix(
    *,
    candidate_packet: dict[str, Any],
    sqlite_packet: dict[str, Any],
    json_packet: dict[str, Any],
    opaque_packet: dict[str, Any],
) -> dict[str, Any]:
    sqlite_by_path = {row["relative_path"]: row for row in sqlite_packet.get("databases", [])}
    json_by_path = {row["relative_path"]: row for row in json_packet.get("surfaces", [])}
    opaque_paths = {row["relative_path"] for row in opaque_packet.get("surfaces", [])}
    rows = []
    for candidate in candidate_packet.get("candidates", []):
        relative_path = candidate.get("relative_path")
        surface_type = candidate.get("surface_type")
        schema_observed = False
        if relative_path in sqlite_by_path:
            schema_observed = sqlite_by_path[relative_path].get("schema_observed") is True
        elif relative_path in json_by_path:
            schema_observed = json_by_path[relative_path].get("shape_observed") is True
        elif relative_path in opaque_paths:
            schema_observed = False
        hypothesis = (
            candidate.get("state_class") in {"thread_history", "session_state", "unknown"}
            and surface_type in {"sqlite", "json", "jsonl", "leveldb_like", "opaque_dir", "opaque_file"}
        )
        rows.append(
            {
                "relative_path": relative_path,
                "surface_type": surface_type,
                "state_class": candidate.get("state_class"),
                "storage_surface_observed": True,
                "schema_observed": schema_observed,
                "semantic_content_classified": False,
                "restoration_source_hypothesis": hypothesis,
                "durable_restoration_proven": False,
                "row_count_counts_as_thread_count": False,
                "raw_values_recorded": False,
            }
        )
    hypothesis_count = sum(1 for row in rows if row["restoration_source_hypothesis"])
    schema_count = sum(1 for row in rows if row["schema_observed"])
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_schema_attribution_matrix",
        "status": "ok" if rows else "blocked",
        "row_count": len(rows),
        "schema_observed_count": schema_count,
        "restoration_source_hypothesis_count": hypothesis_count,
        "rows": rows,
        "semantic_content_classified": False,
        "durable_restoration_proven": False,
        "schema_observed_counts_as_durable_proof": False,
    }


def build_restoration_hypothesis_packet(
    *,
    matrix_packet: dict[str, Any],
    r3_reference_packet: dict[str, Any],
) -> dict[str, Any]:
    hypotheses = [
        {
            "relative_path": row["relative_path"],
            "surface_type": row["surface_type"],
            "state_class": row["state_class"],
            "schema_observed": row["schema_observed"],
            "hypothesis_proof_level": "schema_hypothesis"
            if row["schema_observed"]
            else "surface_hypothesis",
            "durable_restoration_proven": False,
        }
        for row in matrix_packet.get("rows", [])
        if row.get("restoration_source_hypothesis") is True
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_restoration_hypothesis",
        "status": "ok" if hypotheses else "blocked",
        "reason_class": "" if hypotheses else "NO_RESTORATION_HYPOTHESES_CLASSIFIED",
        "hypothesis_count": len(hypotheses),
        "hypotheses": hypotheses[:120],
        "hypotheses_truncated": len(hypotheses) > 120,
        "r3_candidate_counted_as_r4_proof": r3_reference_packet.get("r3_counts_as_r4_proof") is True,
        "remote_sync_cache_or_mixed_remains_possible": True,
        "remote_or_sync_likely_claimed": False,
        "durable_restoration_proven": False,
        "storage_level_thread_history_proven": False,
    }


def build_r4_false_green_audit(
    *,
    sqlite_packet: dict[str, Any],
    json_packet: dict[str, Any],
    opaque_packet: dict[str, Any],
    matrix_packet: dict[str, Any],
    hypothesis_packet: dict[str, Any],
) -> dict[str, Any]:
    forbidden_claims_present = (
        sqlite_packet.get("row_values_recorded") is True
        or sqlite_packet.get("row_count_counts_as_thread_count") is True
        or json_packet.get("raw_values_recorded") is True
        or json_packet.get("raw_lines_recorded") is True
        or opaque_packet.get("key_value_dump_recorded") is True
        or matrix_packet.get("semantic_content_classified") is True
        or matrix_packet.get("durable_restoration_proven") is True
        or hypothesis_packet.get("durable_restoration_proven") is True
        or hypothesis_packet.get("remote_or_sync_likely_claimed") is True
    )
    checks = [
        {
            "name": "sqlite_schema_not_row_values",
            "passed": sqlite_packet.get("row_values_recorded") is False,
        },
        {
            "name": "row_count_not_thread_count",
            "passed": sqlite_packet.get("row_count_counts_as_thread_count") is False,
        },
        {
            "name": "json_shape_not_raw_values",
            "passed": json_packet.get("raw_values_recorded") is False
            and json_packet.get("raw_lines_recorded") is False,
        },
        {
            "name": "opaque_store_not_key_value_dump",
            "passed": opaque_packet.get("key_value_dump_recorded") is False,
        },
        {
            "name": "hypothesis_not_durable_proof",
            "passed": hypothesis_packet.get("durable_restoration_proven") is False,
        },
        {
            "name": "remote_or_sync_not_claimed_likely",
            "passed": hypothesis_packet.get("remote_or_sync_likely_claimed") is False,
        },
    ]
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_r4_false_green_audit",
        "status": "ok"
        if not forbidden_claims_present and all(check["passed"] for check in checks)
        else "blocked",
        "forbidden_claims_present": forbidden_claims_present,
        "checks": checks,
        "text_only_audit_counted_as_pass": False,
    }


def build_r4_summary_packet(
    *,
    sync_packet: dict[str, Any],
    r3_reference_packet: dict[str, Any],
    candidate_packet: dict[str, Any],
    matrix_packet: dict[str, Any],
    hypothesis_packet: dict[str, Any],
    false_green_packet: dict[str, Any],
) -> dict[str, Any]:
    ok = all(
        packet.get("status") == "ok"
        for packet in (
            sync_packet,
            r3_reference_packet,
            candidate_packet,
            matrix_packet,
            hypothesis_packet,
            false_green_packet,
        )
    )
    if ok:
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_RESTORATION_HYPOTHESES_CLASSIFIED_WITH_LIMITS"
    elif candidate_packet.get("status") == "ok":
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_SCHEMA_ATTRIBUTION_CLASSIFIED_WITH_LIMITS"
    else:
        final_status = "WBP_CUSTOM_CODEX_PERSISTENT_PROFILE_SCHEMA_ATTRIBUTION_BLOCKED"
    return {
        "captured_at_utc": _utc_now(),
        "packet_kind": "persistent_storage_r4_summary",
        "status": "ok" if ok else "blocked",
        "final_status": final_status,
        "native_launch_attempted": False,
        "live_mutation_attempted": False,
        "owner_action_required": False,
        "candidate_count": candidate_packet.get("candidate_count", 0),
        "schema_observed_count": matrix_packet.get("schema_observed_count", 0),
        "restoration_source_hypothesis_count": hypothesis_packet.get("hypothesis_count", 0),
        "semantic_content_classified": False,
        "durable_restoration_proven": False,
        "storage_level_thread_history_proven": False,
        "route_proof_claimed": False,
        "direct_egress_absence_claimed": False,
        "model_availability_claimed": False,
        "native_ux_acceptance_claimed": False,
        "final_e2e_claimed": False,
    }


def build_r4_packets(
    *,
    repo_root: Path,
    evidence_dir: Path,
    r3_evidence_dir: Path,
    profile_id: str,
    base_dir: Path | None,
    skip_git: bool = False,
) -> dict[str, dict[str, Any]]:
    paths = default_persistent_custom_profile_paths(profile_id=profile_id, base_dir=base_dir)
    profile_root = Path(paths["persistent_profile_root"])
    sync = build_r4_sync_gate_packet(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        skip_git=skip_git,
    )
    r3_reference = build_r4_r3_reference_packet(r3_evidence_dir=r3_evidence_dir)
    candidates = select_candidate_surfaces(profile_root)
    sqlite_schema = inspect_sqlite_schema(profile_root, candidates.get("candidates", []))
    json_shape = inspect_json_shapes(profile_root, candidates.get("candidates", []))
    opaque = build_opaque_surface_packet(candidates.get("candidates", []))
    matrix = build_schema_attribution_matrix(
        candidate_packet=candidates,
        sqlite_packet=sqlite_schema,
        json_packet=json_shape,
        opaque_packet=opaque,
    )
    hypothesis = build_restoration_hypothesis_packet(
        matrix_packet=matrix,
        r3_reference_packet=r3_reference,
    )
    false_green = build_r4_false_green_audit(
        sqlite_packet=sqlite_schema,
        json_packet=json_shape,
        opaque_packet=opaque,
        matrix_packet=matrix,
        hypothesis_packet=hypothesis,
    )
    summary = build_r4_summary_packet(
        sync_packet=sync,
        r3_reference_packet=r3_reference,
        candidate_packet=candidates,
        matrix_packet=matrix,
        hypothesis_packet=hypothesis,
        false_green_packet=false_green,
    )
    return {
        "persistent_storage_r4_sync_gate_packet.json": sync,
        "persistent_storage_r3_reference_packet.json": r3_reference,
        "persistent_storage_candidate_selection_packet.json": candidates,
        "persistent_storage_sqlite_schema_packet.json": sqlite_schema,
        "persistent_storage_json_shape_packet.json": json_shape,
        "persistent_storage_opaque_surface_packet.json": opaque,
        "persistent_storage_schema_attribution_matrix.json": matrix,
        "persistent_storage_restoration_hypothesis_packet.json": hypothesis,
        "persistent_storage_r4_false_green_audit.json": false_green,
        "persistent_storage_r4_summary_packet.json": summary,
    }


def write_packets(evidence_dir: Path, packets: dict[str, dict[str, Any]]) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name, packet in packets.items():
        json_write(evidence_dir / name, packet)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="persistent-custom-profile-storage-schema-attribution-r4"
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--r3-evidence-dir", type=Path, default=DEFAULT_R3_EVIDENCE_DIR)
    parser.add_argument("--profile-id", default="wbp-custom-main")
    parser.add_argument("--base-dir", type=Path, default=None)
    parser.add_argument("--execution-mode", choices=("phase-a",), default="phase-a")
    parser.add_argument("--skip-git", action="store_true")
    args = parser.parse_args()

    packets = build_r4_packets(
        repo_root=args.repo_root,
        evidence_dir=args.evidence_dir,
        r3_evidence_dir=args.r3_evidence_dir,
        profile_id=args.profile_id,
        base_dir=args.base_dir,
        skip_git=args.skip_git,
    )
    write_packets(args.evidence_dir, packets)
    summary = packets["persistent_storage_r4_summary_packet.json"]
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
