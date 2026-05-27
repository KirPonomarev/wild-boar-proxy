# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Snapshot/diff/redaction helpers for Persistent Custom profile readiness."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


STATE_CLASSES = {
    "thread_history",
    "session_state",
    "user_settings",
    "model_menu_state",
    "provider_wbp_linkage_state",
    "integration_state",
    "cache_or_incidental_state",
    "unclassified_profile_state",
}

PROMPT_OR_SECRET_MARKERS = (
    "sk-",
    "OPENAI_API_KEY",
    "Authorization: Bearer",
    "refresh_token",
    "nonce_used=true",
    "owner_prompt_entered=true",
    "составь план следующего контура",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_persistent_profile_state_path(relative_path: str) -> str:
    lower = relative_path.lower()
    if any(token in lower for token in ("thread", "conversation", "chat", "transcript")):
        return "thread_history"
    if any(token in lower for token in ("session", "window-state", "state.vscdb", "local storage")):
        return "session_state"
    if any(token in lower for token in ("config.toml", "settings", "preferences", "prefs")):
        return "user_settings"
    if any(token in lower for token in ("model", "menu", "catalog", "picker")):
        return "model_menu_state"
    if any(token in lower for token in ("wbp", "provider", "route", "linkage")):
        return "provider_wbp_linkage_state"
    if any(token in lower for token in ("plugin", "integration", "oauth", "connector")):
        return "integration_state"
    if any(token in lower for token in ("cache", "tmp", "gpu", "blob_storage", "code cache", "logs")):
        return "cache_or_incidental_state"
    return "unclassified_profile_state"


def redacted_snapshot_entry(
    *,
    relative_path: str,
    kind: str = "file",
    size: int = 0,
    content_hash: str = "",
) -> dict[str, Any]:
    safe_hash = content_hash or sha256_text(f"{relative_path}:{kind}:{size}")
    return {
        "relative_path": relative_path,
        "kind": kind,
        "size": size,
        "sha256": safe_hash,
        "state_class": classify_persistent_profile_state_path(relative_path),
        "content_recorded": False,
        "raw_prompt_recorded": False,
        "raw_secret_recorded": False,
    }


def build_profile_snapshot(
    *,
    snapshot_label: str,
    entries: list[dict[str, Any]],
    synthetic_fixture: bool = True,
) -> dict[str, Any]:
    normalized = sorted(entries, key=lambda entry: str(entry["relative_path"]))
    digest_input = [
        {
            "relative_path": entry["relative_path"],
            "kind": entry.get("kind"),
            "size": entry.get("size"),
            "sha256": entry.get("sha256"),
            "state_class": entry.get("state_class"),
        }
        for entry in normalized
    ]
    return {
        "captured_at_utc": utc_now(),
        "snapshot_label": snapshot_label,
        "synthetic_fixture": synthetic_fixture,
        "entry_count": len(normalized),
        "entries": normalized,
        "snapshot_digest": sha256_text(json.dumps(digest_input, sort_keys=True)),
        "raw_prompt_recorded": False,
        "raw_secret_recorded": False,
        "snapshot_is_live_profile_proof": False,
        "snapshot_is_thread_history_proof": False,
    }


def diff_profile_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    diff_label: str,
) -> dict[str, Any]:
    before_entries = {
        entry["relative_path"]: entry
        for entry in before.get("entries", [])
        if isinstance(entry, dict)
    }
    after_entries = {
        entry["relative_path"]: entry
        for entry in after.get("entries", [])
        if isinstance(entry, dict)
    }
    created: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged_count = 0
    class_counts = {state_class: 0 for state_class in sorted(STATE_CLASSES)}

    for relative_path in sorted(set(before_entries) | set(after_entries)):
        old = before_entries.get(relative_path)
        new = after_entries.get(relative_path)
        reference = new or old or {}
        state_class = str(reference.get("state_class") or classify_persistent_profile_state_path(relative_path))
        if state_class in class_counts:
            class_counts[state_class] += 1
        if old is None and new is not None:
            created.append(_diff_item(relative_path, state_class, new=new))
            continue
        if new is None and old is not None:
            deleted.append(_diff_item(relative_path, state_class, old=old))
            continue
        if _entry_identity(old) != _entry_identity(new):
            changed.append(_diff_item(relative_path, state_class, old=old, new=new))
            continue
        unchanged_count += 1

    return {
        "captured_at_utc": utc_now(),
        "diff_label": diff_label,
        "synthetic_fixture": bool(before.get("synthetic_fixture") or after.get("synthetic_fixture")),
        "created": created,
        "deleted": deleted,
        "changed": changed,
        "unchanged_count": unchanged_count,
        "created_count": len(created),
        "deleted_count": len(deleted),
        "changed_count": len(changed),
        "state_class_counts": class_counts,
        "diff_detected": bool(created or deleted or changed),
        "diff_detected_is_saved_thread_proof": False,
        "hash_changed_is_user_visible_state": False,
        "synthetic_diff_is_real_profile_pass": False,
        "thread_history_preservation_claimed": False,
        "profile_storage_persistence_claimed": False,
    }


def _entry_identity(entry: dict[str, Any] | None) -> tuple[Any, ...]:
    if entry is None:
        return (None,)
    return (
        entry.get("kind"),
        entry.get("size"),
        entry.get("sha256"),
        entry.get("state_class"),
    )


def _diff_item(
    relative_path: str,
    state_class: str,
    *,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "relative_path": relative_path,
        "state_class": state_class,
        "old": _redacted_entry_ref(old),
        "new": _redacted_entry_ref(new),
        "state_class_label_is_runtime_truth": False,
        "state_class_label_is_thread_preservation_proof": False,
        "hash_change_is_user_visible_state": False,
    }


def _redacted_entry_ref(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if entry is None:
        return None
    return {
        "kind": entry.get("kind"),
        "size": entry.get("size"),
        "sha256": entry.get("sha256"),
        "state_class": entry.get("state_class"),
        "content_recorded": False,
    }


def synthetic_profile_snapshots() -> dict[str, dict[str, Any]]:
    before = build_profile_snapshot(
        snapshot_label="synthetic_before",
        entries=[
            redacted_snapshot_entry(
                relative_path="settings/config.toml",
                size=64,
                content_hash=sha256_text("settings-before"),
            ),
            redacted_snapshot_entry(
                relative_path="Cache/blob_storage/index",
                size=128,
                content_hash=sha256_text("cache-before"),
            ),
            redacted_snapshot_entry(
                relative_path="Local Storage/state.vscdb",
                size=256,
                content_hash=sha256_text("session-before"),
            ),
        ],
    )
    after = build_profile_snapshot(
        snapshot_label="synthetic_after",
        entries=[
            redacted_snapshot_entry(
                relative_path="settings/config.toml",
                size=72,
                content_hash=sha256_text("settings-after"),
            ),
            redacted_snapshot_entry(
                relative_path="Cache/blob_storage/index",
                size=144,
                content_hash=sha256_text("cache-after"),
            ),
            redacted_snapshot_entry(
                relative_path="Local Storage/state.vscdb",
                size=280,
                content_hash=sha256_text("session-after"),
            ),
            redacted_snapshot_entry(
                relative_path="conversations/thread-redacted.json",
                size=512,
                content_hash=sha256_text("thread-redacted-hash-only"),
            ),
            redacted_snapshot_entry(
                relative_path="integrations/connector-state.json",
                size=96,
                content_hash=sha256_text("integration-after"),
            ),
        ],
    )
    relaunch = build_profile_snapshot(
        snapshot_label="synthetic_relaunch",
        entries=[
            redacted_snapshot_entry(
                relative_path="settings/config.toml",
                size=72,
                content_hash=sha256_text("settings-after"),
            ),
            redacted_snapshot_entry(
                relative_path="Cache/blob_storage/index",
                size=160,
                content_hash=sha256_text("cache-relaunch"),
            ),
            redacted_snapshot_entry(
                relative_path="Local Storage/state.vscdb",
                size=300,
                content_hash=sha256_text("session-relaunch"),
            ),
            redacted_snapshot_entry(
                relative_path="conversations/thread-redacted.json",
                size=512,
                content_hash=sha256_text("thread-redacted-hash-only"),
            ),
            redacted_snapshot_entry(
                relative_path="integrations/connector-state.json",
                size=96,
                content_hash=sha256_text("integration-after"),
            ),
        ],
    )
    return {"before": before, "after": after, "relaunch": relaunch}


def marker_scan_text(text: str) -> dict[str, Any]:
    marker_findings = [marker for marker in PROMPT_OR_SECRET_MARKERS if marker in text]
    secret_pattern_findings = [
        pattern
        for pattern in (
            r"sk-(?:proj|live|cliproxy|wbp|[A-Za-z0-9]{20,})[A-Za-z0-9_-]{8,}",
            r"OPENAI_API_KEY\s*=",
            r"Authorization:\s*Bearer\s+[^<\s\"]+",
            r"refresh_token[\"']?\s*[:=]\s*[\"'][^\"']+[\"']",
        )
        if re.search(pattern, text, re.IGNORECASE)
    ]
    return {
        "marker_findings": marker_findings,
        "secret_pattern_findings": secret_pattern_findings,
        "raw_prompt_found": bool(marker_findings),
        "raw_secret_found": bool(secret_pattern_findings),
        "exhaustive_dlp_claimed": False,
    }
