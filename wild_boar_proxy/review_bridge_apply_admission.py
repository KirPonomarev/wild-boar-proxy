# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Zero-write target-resolution admission for review exact-text apply."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

from wild_boar_proxy.review_bridge_packet_import import default_review_import_context

if TYPE_CHECKING:
    from wild_boar_proxy.review_bridge_session_store import ReviewSessionRecord


REVIEW_SCENE_MAP_FILENAME = ".wbp-review-scene-map.json"
REVIEW_APPLY_FORBIDDEN_BROWSER_FIELDS = (
    "after",
    "artifact_path",
    "baseline_hash",
    "before",
    "digest",
    "path",
    "project_root",
    "receipt_path",
    "scene_id",
    "scene_path",
    "session_id",
)


@dataclass(frozen=True)
class ReviewSceneInventoryEntry:
    scene_id: str
    path: str


@dataclass(frozen=True)
class ReviewApplyContext:
    project_id: str
    baseline_hash: str
    project_root: Path
    scene_map_path: Path
    scene_inventory: tuple[ReviewSceneInventoryEntry, ...]
    source_status: str
    source_kind: str = "server_owned_scene_inventory_manifest"


def default_review_apply_context(repo_root: Path) -> ReviewApplyContext:
    import_context = default_review_import_context(repo_root)
    scene_map_path = (repo_root / REVIEW_SCENE_MAP_FILENAME).resolve()
    scene_inventory, source_status = _load_scene_inventory(scene_map_path)
    return ReviewApplyContext(
        project_id=import_context.project_id,
        baseline_hash=import_context.baseline_hash,
        project_root=repo_root.resolve(),
        scene_map_path=scene_map_path,
        scene_inventory=scene_inventory,
        source_status=source_status,
    )


def build_review_apply_preflight_packet(
    record: "ReviewSessionRecord | None",
    *,
    context: ReviewApplyContext,
    browser_payload: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    forbidden_browser_fields = sorted(
        field for field in (browser_payload or {}) if field in REVIEW_APPLY_FORBIDDEN_BROWSER_FIELDS
    )
    if forbidden_browser_fields:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight rejects browser-owned target fields.",
            machine_error_code="REVIEW_APPLY_BROWSER_FIELD_REJECTED",
            next_action="remove_forbidden_browser_fields",
            data={
                "preflight_only": True,
                "future_apply_admissible": False,
                "write_permitted_now": False,
                "manuscript_write_performed": False,
                "filesystem_mutation_performed": False,
                "session_present": record is not None,
                "target_resolution_source": context.source_kind,
                "scene_manifest_present": context.scene_map_path.is_file(),
                "scene_manifest_source_status": context.source_status,
                "target_resolved": False,
                "resolution_ambiguous": False,
                "forbidden_browser_fields": forbidden_browser_fields,
                "browser_forbidden_fields_rejected": True,
                "scene_path_absolute_exposed": False,
            },
        )

    if record is None:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight requires an active review session.",
            machine_error_code="REVIEW_APPLY_SESSION_CLOSED",
            next_action="import_review_packet",
            data=_base_preflight_data(context, session_present=False),
        )

    if record.project_id != context.project_id or record.baseline_hash != context.baseline_hash:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight baseline does not match the current project truth.",
            machine_error_code="REVIEW_APPLY_BASELINE_STALE",
            next_action="reimport_review_packet",
            data=_base_preflight_data(context, session_present=True),
        )

    exact_items = [
        item
        for item in _safe_list(record.review_surface.get("text_changes"))
        if isinstance(item, dict) and str(item.get("kind") or "") == "exact_text"
    ]
    if not exact_items:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight requires one exact-text item with target fields.",
            machine_error_code="REVIEW_APPLY_EXACT_FIELDS_MISSING",
            next_action="import_review_packet",
            data=_base_preflight_data(context, session_present=True),
        )
    if len(exact_items) != 1:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight requires exactly one exact-text item.",
            machine_error_code="REVIEW_APPLY_TARGET_AMBIGUOUS",
            next_action="narrow_review_packet_to_single_exact_item",
            data={
                **_base_preflight_data(context, session_present=True),
                "resolution_ambiguous": True,
                "candidate_exact_item_count": len(exact_items),
            },
        )

    item = exact_items[0]
    scene_id = _read_required_string(item, "scene_id")
    before = _read_required_string(item, "before")
    after = _read_required_string(item, "after")
    if not scene_id or before is None or after is None:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight requires exact-text items with scene_id, before, and after fields.",
            machine_error_code="REVIEW_APPLY_EXACT_FIELDS_MISSING",
            next_action="fix_review_packet_fields",
            data=_base_preflight_data(context, session_present=True),
        )

    if context.source_status != "ok":
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight target source is unavailable for the current project.",
            machine_error_code="REVIEW_APPLY_TARGET_SOURCE_UNAVAILABLE",
            next_action="materialize_server_owned_scene_manifest",
            data=_base_preflight_data(context, session_present=True),
        )

    candidates = [entry for entry in context.scene_inventory if entry.scene_id == scene_id]
    if not candidates:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight could not resolve the scene_id inside the current project manifest.",
            machine_error_code="REVIEW_APPLY_TARGET_SCENE_UNKNOWN",
            next_action="register_scene_in_server_owned_manifest",
            data=_base_preflight_data(context, session_present=True),
        )
    if len(candidates) != 1:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight found more than one target for the requested scene_id.",
            machine_error_code="REVIEW_APPLY_TARGET_AMBIGUOUS",
            next_action="deduplicate_scene_manifest",
            data={
                **_base_preflight_data(context, session_present=True),
                "resolution_ambiguous": True,
                "candidate_scene_count": len(candidates),
            },
        )

    resolved_path = (context.project_root / candidates[0].path).resolve()
    try:
        resolved_path.relative_to(context.project_root)
    except ValueError:
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight rejected a target path outside the current project boundary.",
            machine_error_code="REVIEW_APPLY_TARGET_PATH_OUTSIDE_PROJECT",
            next_action="repair_server_owned_scene_manifest",
            data=_base_preflight_data(context, session_present=True),
        )
    if not resolved_path.is_file():
        return _packet(
            status="blocked",
            exit_code=1,
            human_message="Review apply preflight resolved a scene path that is missing on disk.",
            machine_error_code="REVIEW_APPLY_TARGET_SCENE_UNKNOWN",
            next_action="repair_server_owned_scene_manifest",
            data=_base_preflight_data(context, session_present=True),
        )

    return _packet(
        status="ok",
        exit_code=0,
        human_message="Review apply preflight resolved one exact-text target. No write performed.",
        machine_error_code="REVIEW_APPLY_TARGET_RESOLVED_ADMITTED",
        next_action="wait_for_contour_04_apply_enablement",
        data={
            **_base_preflight_data(context, session_present=True),
            "future_apply_admissible": True,
            "target_resolved": True,
            "resolved_item_id": str(item.get("id") or ""),
            "resolved_scene_id": scene_id,
            "scene_path_ref": candidates[0].path,
            "scene_path_absolute_exposed": False,
        },
    )


def _base_preflight_data(
    context: ReviewApplyContext,
    *,
    session_present: bool,
) -> dict[str, Any]:
    return {
        "preflight_only": True,
        "future_apply_admissible": False,
        "write_permitted_now": False,
        "manuscript_write_performed": False,
        "filesystem_mutation_performed": False,
        "session_present": session_present,
        "target_resolution_source": context.source_kind,
        "scene_manifest_present": context.scene_map_path.is_file(),
        "scene_manifest_source_status": context.source_status,
        "target_resolved": False,
        "resolution_ambiguous": False,
        "forbidden_browser_fields": sorted(REVIEW_APPLY_FORBIDDEN_BROWSER_FIELDS),
        "browser_forbidden_fields_rejected": False,
        "scene_path_absolute_exposed": False,
    }


def _packet(
    *,
    status: str,
    exit_code: int,
    human_message: str,
    machine_error_code: str,
    next_action: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "exit_code": exit_code,
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": [],
        "next_action": next_action,
        "data": data,
    }


def _load_scene_inventory(
    scene_map_path: Path,
) -> tuple[tuple[ReviewSceneInventoryEntry, ...], str]:
    if not scene_map_path.is_file():
        return (), "missing"
    try:
        payload = json.loads(scene_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (), "invalid"
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return (), "invalid"
    raw_inventory = payload.get("scene_inventory")
    if not isinstance(raw_inventory, list):
        return (), "invalid"
    entries: list[ReviewSceneInventoryEntry] = []
    for raw_entry in raw_inventory:
        if not isinstance(raw_entry, dict):
            return (), "invalid"
        scene_id = _read_required_string(raw_entry, "scene_id")
        path = _read_required_string(raw_entry, "path")
        if not scene_id or not path:
            return (), "invalid"
        entries.append(ReviewSceneInventoryEntry(scene_id=scene_id, path=path))
    return tuple(entries), "ok"


def _read_required_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
