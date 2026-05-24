# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Bounded single exact-text apply for the review bridge."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from wild_boar_proxy.review_bridge_apply_admission import (
    ReviewApplyContext,
    build_review_apply_preflight_packet,
)


@dataclass(frozen=True)
class ReviewExactTextApplyResult:
    status: str
    exit_code: int
    human_message: str
    machine_error_code: str
    next_action: str
    changed_files: list[str]
    data: dict[str, Any]
    updated_review_surface: dict[str, Any] | None = None


def apply_exact_text_change(
    review_record: Any,
    *,
    context: ReviewApplyContext | None,
) -> ReviewExactTextApplyResult:
    if context is None:
        return _result(
            status="blocked",
            exit_code=1,
            human_message="Exact text apply requires server-owned apply preflight context.",
            machine_error_code="REVIEW_APPLY_PREFLIGHT_REQUIRED",
            next_action="provide_server_owned_apply_context",
            changed_files=[],
            data={
                "apply_attempted": False,
                "write_performed": False,
                "rollback_snapshot_captured": False,
                "rollback_attempted": False,
                "rollback_outcome": "not_available",
            },
        )

    preflight = build_review_apply_preflight_packet(review_record, context=context)
    if preflight["status"] != "ok":
        return _result(
            status="blocked",
            exit_code=1,
            human_message=str(preflight["human_message"]),
            machine_error_code=str(preflight["machine_error_code"]),
            next_action=str(preflight["next_action"]),
            changed_files=[],
            data={
                "apply_attempted": False,
                "write_performed": False,
                "rollback_snapshot_captured": False,
                "rollback_attempted": False,
                "rollback_outcome": "not_needed",
                "source_preflight_packet": preflight,
                "source_preflight_sha256": _stable_digest(preflight),
                **dict(preflight["data"]),
            },
        )

    source_preflight_sha256 = _stable_digest(preflight)
    source_preflight_data = dict(preflight["data"])
    scene_path_ref = str(source_preflight_data["scene_path_ref"])
    resolved_path = (context.project_root / scene_path_ref).resolve()
    resolved_path.relative_to(context.project_root)

    exact_items = [
        item
        for item in review_record.review_surface.get("text_changes", [])
        if isinstance(item, dict) and str(item.get("id") or "") == str(source_preflight_data["resolved_item_id"])
    ]
    if len(exact_items) != 1:
        return _result(
            status="blocked",
            exit_code=1,
            human_message="Exact text apply could not bind the admitted item inside the active session.",
            machine_error_code="REVIEW_APPLY_TARGET_ITEM_MISSING",
            next_action="reimport_review_packet",
            changed_files=[],
            data={
                "apply_attempted": False,
                "write_performed": False,
                "rollback_snapshot_captured": False,
                "rollback_attempted": False,
                "rollback_outcome": "not_needed",
                "source_preflight_packet": preflight,
                "source_preflight_sha256": source_preflight_sha256,
            },
        )
    item = exact_items[0]
    before = str(item["before"])
    after = str(item["after"])
    current_text = resolved_path.read_text(encoding="utf-8")
    occurrence_count = _count_exact_occurrences(current_text, before)
    if occurrence_count == 0:
        return _result(
            status="blocked",
            exit_code=1,
            human_message="Exact text apply found no exact match in the resolved scene file.",
            machine_error_code="REVIEW_APPLY_NO_MATCH",
            next_action="refresh_scene_or_review_packet",
            changed_files=[],
            data={
                "apply_attempted": True,
                "write_performed": False,
                "rollback_snapshot_captured": False,
                "rollback_attempted": False,
                "rollback_outcome": "not_needed",
                "exact_match_count": 0,
                "source_preflight_packet": preflight,
                "source_preflight_sha256": source_preflight_sha256,
            },
        )
    if occurrence_count != 1:
        return _result(
            status="blocked",
            exit_code=1,
            human_message="Exact text apply found more than one matching occurrence in the resolved scene file.",
            machine_error_code="REVIEW_APPLY_DUPLICATE_MATCH",
            next_action="narrow_target_or_edit_packet",
            changed_files=[],
            data={
                "apply_attempted": True,
                "write_performed": False,
                "rollback_snapshot_captured": False,
                "rollback_attempted": False,
                "rollback_outcome": "not_needed",
                "exact_match_count": occurrence_count,
                "source_preflight_packet": preflight,
                "source_preflight_sha256": source_preflight_sha256,
            },
        )

    snapshot = {
        "text": current_text,
        "mode": resolved_path.stat().st_mode & 0o777,
    }
    updated_text = current_text.replace(before, after, 1)
    try:
        _write_text_exact_atomic(resolved_path, updated_text)
    except Exception:
        rollback_outcome = "restore_failed"
        rollback_attempted = True
        try:
            _write_text_exact_atomic(resolved_path, snapshot["text"])
            resolved_path.chmod(int(snapshot["mode"]))
            rollback_outcome = "completed"
        except Exception:
            pass
        return _result(
            status="command_error",
            exit_code=1,
            human_message="Exact text apply write failed after admitted preflight.",
            machine_error_code="REVIEW_APPLY_WRITE_FAILED",
            next_action="inspect_single_file_write_failure",
            changed_files=[],
            data={
                "apply_attempted": True,
                "write_performed": False,
                "rollback_snapshot_captured": True,
                "rollback_attempted": rollback_attempted,
                "rollback_outcome": rollback_outcome,
                "source_preflight_packet": preflight,
                "source_preflight_sha256": source_preflight_sha256,
            },
        )

    relative_changed = str(resolved_path)
    updated_review_surface = _build_updated_review_surface(
        review_record.review_surface,
        applied_item_id=str(item["id"]),
    )
    receipt = {
        "receipt_kind": "review_exact_text_apply_receipt",
        "command_id": "apply_exact_text_change",
        "project_id": context.project_id,
        "session_id": str(review_record.session_id),
        "source_packet_hash": str(review_record.source_packet_hash),
        "source_preflight_sha256": source_preflight_sha256,
        "applied_item_id": str(item["id"]),
        "resolved_scene_id": str(source_preflight_data["resolved_scene_id"]),
        "scene_path_ref": scene_path_ref,
        "write_count": 1,
        "write_performed": True,
        "before_sha256": _sha256_text(before),
        "after_sha256": _sha256_text(after),
        "file_text_before_sha256": _sha256_text(current_text),
        "file_text_after_sha256": _sha256_text(updated_text),
        "rollback_snapshot_captured": True,
        "rollback_attempted": False,
        "rollback_outcome": "not_needed",
    }
    return _result(
        status="ok",
        exit_code=0,
        human_message="Exact text change applied to one resolved scene file.",
        machine_error_code="OK",
        next_action="query_review_surface",
        changed_files=[relative_changed],
        data={
            "apply_attempted": True,
            "write_performed": True,
            "write_count": 1,
            "scene_path_ref": scene_path_ref,
            "source_preflight_packet": preflight,
            "source_preflight_sha256": source_preflight_sha256,
            "receipt": receipt,
            "rollback_snapshot_captured": True,
            "rollback_attempted": False,
            "rollback_outcome": "not_needed",
        },
        updated_review_surface=updated_review_surface,
    )


def _build_updated_review_surface(
    review_surface: dict[str, Any],
    *,
    applied_item_id: str,
) -> dict[str, Any]:
    items = [
        item
        for item in _safe_list(review_surface.get("items"))
        if str(getattr(item, "get", lambda *_args, **_kwargs: "")("id") or "") != applied_item_id
    ]
    text_changes = [
        item
        for item in _safe_list(review_surface.get("text_changes"))
        if str(getattr(item, "get", lambda *_args, **_kwargs: "")("id") or "") != applied_item_id
    ]
    diagnostics = list(_safe_list(review_surface.get("diagnostics")))
    diagnostics.append(
        {
            "code": "exact-text-applied",
            "severity": "info",
            "item_id": applied_item_id,
        }
    )
    return {
        **review_surface,
        "items": items,
        "text_changes": text_changes,
        "diagnostics": diagnostics,
        "manuscript_write_performed": True,
        "filesystem_mutation_performed": True,
    }


def _result(
    *,
    status: str,
    exit_code: int,
    human_message: str,
    machine_error_code: str,
    next_action: str,
    changed_files: list[str],
    data: dict[str, Any],
    updated_review_surface: dict[str, Any] | None = None,
) -> ReviewExactTextApplyResult:
    return ReviewExactTextApplyResult(
        status=status,
        exit_code=exit_code,
        human_message=human_message,
        machine_error_code=machine_error_code,
        next_action=next_action,
        changed_files=changed_files,
        data=data,
        updated_review_surface=updated_review_surface,
    )


def _write_text_exact_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(value, encoding="utf-8")
    tmp_path.replace(path)


def _count_exact_occurrences(text: str, needle: str) -> int:
    if needle == "":
        return 0
    count = 0
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            return count
        count += 1
        start = index + 1


def _stable_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
