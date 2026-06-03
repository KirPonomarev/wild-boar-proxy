# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Validation and adaptation for bounded review packet import."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from wild_boar_proxy.process_runner import PROCESS_OK, run_bounded_process


REVIEW_BRIDGE_GIT_RUNTIME_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
REVIEW_BRIDGE_GIT_TIMEOUT_SECONDS = 10.0
REVIEW_BRIDGE_GIT_OUTPUT_CAP_BYTES = 8 * 1024


@dataclass(frozen=True)
class ReviewImportContext:
    project_id: str
    baseline_hash: str


class ReviewPacketImportError(Exception):
    """Raised when a review packet cannot be admitted for import."""

    def __init__(self, machine_error_code: str, human_message: str) -> None:
        super().__init__(human_message)
        self.machine_error_code = machine_error_code
        self.human_message = human_message


def default_review_import_context(repo_root: Path) -> ReviewImportContext:
    return ReviewImportContext(
        project_id=repo_root.name,
        baseline_hash=_git_head_sha(repo_root),
    )


def adapt_review_packet(
    review_packet: dict[str, Any],
    *,
    context: ReviewImportContext,
) -> dict[str, Any]:
    if not isinstance(review_packet, dict):
        raise ReviewPacketImportError(
            "REVIEW_PACKET_NOT_OBJECT",
            "review_packet must be a JSON object.",
        )

    schema_version = review_packet.get("schema_version")
    if schema_version != 1:
        raise ReviewPacketImportError(
            "REVIEW_PACKET_SCHEMA_UNSUPPORTED",
            "review_packet schema_version must equal 1.",
        )

    project_id = _require_nonempty_string(review_packet, "project_id")
    if project_id != context.project_id:
        raise ReviewPacketImportError(
            "REVIEW_PACKET_PROJECT_MISMATCH",
            "review_packet project_id does not match the current project.",
        )

    baseline_hash = _require_nonempty_string(review_packet, "baseline_hash")
    if baseline_hash != context.baseline_hash:
        raise ReviewPacketImportError(
            "REVIEW_PACKET_BASELINE_STALE",
            "review_packet baseline_hash does not match the current baseline.",
        )

    review_items = _require_list(review_packet, "review_items")
    orphan_comments = _optional_list(review_packet, "orphan_comments")
    diagnostics = _optional_list(review_packet, "diagnostics")

    text_changes: list[dict[str, Any]] = []
    structural_manual_only: list[dict[str, Any]] = []
    normalized_items: list[dict[str, Any]] = []
    for index, item in enumerate(review_items):
        if not isinstance(item, dict):
            raise ReviewPacketImportError(
                "REVIEW_PACKET_INVALID_FIELD",
                f"review_items[{index}] must be an object.",
            )
        item_id = _require_nonempty_string(item, "id", context=f"review_items[{index}]")
        kind = _require_nonempty_string(item, "kind", context=f"review_items[{index}]")
        normalized = {"id": item_id, "kind": kind, **item}
        if kind == "exact_text":
            text_changes.append(normalized)
        elif kind == "structural":
            structural_manual_only.append(
                {
                    **normalized,
                    "apply_mode": "manual_only",
                    "manual_only": True,
                }
            )
        else:
            raise ReviewPacketImportError(
                "REVIEW_PACKET_INVALID_FIELD",
                f"review_items[{index}].kind must be exact_text or structural.",
            )
        normalized_items.append(normalized)

    canonical_packet = json.dumps(review_packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    packet_hash = hashlib.sha256(canonical_packet.encode("utf-8")).hexdigest()
    session_id = f"review-import-{packet_hash[:12]}"
    review_surface = {
        "schema_version": 1,
        "items": normalized_items,
        "text_changes": text_changes,
        "structural_manual_only": structural_manual_only,
        "orphan_comments": orphan_comments,
        "diagnostics": diagnostics,
        "manuscript_write_performed": False,
        "filesystem_mutation_performed": False,
        "manual_only_structural": bool(structural_manual_only),
    }
    revision_session = {
        "mode": "review_only",
        "source": "bounded_review_packet_import",
        "schema_version": 1,
        "project_id": project_id,
        "baseline_hash": baseline_hash,
    }
    return {
        "project_id": project_id,
        "session_id": session_id,
        "baseline_hash": baseline_hash,
        "review_surface": review_surface,
        "revision_session": revision_session,
        "source_packet_hash": f"sha256:{packet_hash}",
    }


def _git_head_sha(repo_root: Path) -> str:
    try:
        result = run_bounded_process(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            env={
                "PATH": REVIEW_BRIDGE_GIT_RUNTIME_PATH,
                "NO_PROXY": "127.0.0.1,localhost,::1",
                "no_proxy": "127.0.0.1,localhost,::1",
            },
            timeout_seconds=REVIEW_BRIDGE_GIT_TIMEOUT_SECONDS,
            output_cap_bytes=REVIEW_BRIDGE_GIT_OUTPUT_CAP_BYTES,
        )
    except Exception as exc:
        raise ReviewPacketImportError(
            "REVIEW_IMPORT_CONTEXT_UNAVAILABLE",
            "Unable to determine the current baseline for review import.",
        ) from exc
    if (
        result.machine_error_code != PROCESS_OK
        or result.timed_out
        or result.exit_code != 0
    ):
        raise ReviewPacketImportError(
            "REVIEW_IMPORT_CONTEXT_UNAVAILABLE",
            "Unable to determine the current baseline for review import.",
        )
    value = result.stdout.strip()
    if not value:
        raise ReviewPacketImportError(
            "REVIEW_IMPORT_CONTEXT_UNAVAILABLE",
            "Current baseline hash is empty.",
        )
    return value


def _require_nonempty_string(
    payload: dict[str, Any],
    key: str,
    *,
    context: str | None = None,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        prefix = f"{context}." if context else ""
        raise ReviewPacketImportError(
            "REVIEW_PACKET_MISSING_FIELD",
            f"{prefix}{key} must be a non-empty string.",
        )
    return value.strip()


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ReviewPacketImportError(
            "REVIEW_PACKET_INVALID_FIELD",
            f"{key} must be a list.",
        )
    return value


def _optional_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key, [])
    if not isinstance(value, list):
        raise ReviewPacketImportError(
            "REVIEW_PACKET_INVALID_FIELD",
            f"{key} must be a list when present.",
        )
    return value
