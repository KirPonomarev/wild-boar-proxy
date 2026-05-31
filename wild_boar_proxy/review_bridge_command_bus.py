# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Main-side command bus for review bridge mutation contours."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from wild_boar_proxy.review_bridge_apply_admission import ReviewApplyContext
from wild_boar_proxy.review_bridge_packet_import import (
    ReviewImportContext,
    ReviewPacketImportError,
    adapt_review_packet,
)
from wild_boar_proxy.review_bridge_session_store import ReviewSessionStore


REVIEW_COMMAND_FIELDS = (
    "status",
    "exit_code",
    "human_message",
    "machine_error_code",
    "changed_files",
    "next_action",
)


@dataclass(frozen=True)
class ReviewCommandSpec:
    command_id: str
    required_args: tuple[str, ...] = ()
    allowed_args: tuple[str, ...] = ()
    runtime_enabled: bool = True


ALLOWLIST: dict[str, ReviewCommandSpec] = {
    "import_review_packet": ReviewCommandSpec(
        command_id="import_review_packet",
        required_args=("review_packet",),
        allowed_args=("review_packet",),
    ),
    "clear_review_session": ReviewCommandSpec(
        command_id="clear_review_session",
    ),
    "apply_exact_text_change": ReviewCommandSpec(
        command_id="apply_exact_text_change",
        runtime_enabled=True,
    ),
}


class ReviewBridgeCommandError(Exception):
    """Raised when the review bridge command bus rejects a command."""

    def __init__(self, machine_error_code: str, human_message: str) -> None:
        super().__init__(human_message)
        self.machine_error_code = machine_error_code
        self.human_message = human_message


def review_allowlist_metadata() -> list[dict[str, Any]]:
    return [
        {
            "command_id": spec.command_id,
            "required_args": list(spec.required_args),
            "allowed_args": list(spec.allowed_args),
            "runtime_enabled": spec.runtime_enabled,
        }
        for spec in ALLOWLIST.values()
    ]


def execute_review_command(
    store: ReviewSessionStore,
    command_id: str,
    *,
    payload: dict[str, Any] | None = None,
    import_context: ReviewImportContext | None = None,
    apply_context: ReviewApplyContext | None = None,
) -> dict[str, Any]:
    body = payload or {}
    try:
        spec = _require_spec(command_id)
        _validate_payload_shape(spec, body)
        if not spec.runtime_enabled:
            return _packet(
                status="blocked",
                exit_code=1,
                human_message="Exact text apply is reserved for Contour 04 and is not enabled yet.",
                machine_error_code="REVIEW_APPLY_NOT_ENABLED",
                next_action="wait_for_contour_04",
                data={"command_id": command_id},
            )
        if command_id == "apply_exact_text_change":
            result, updated_record = store._run_exact_text_apply(context=apply_context)
            if updated_record is not None:
                data = {
                    "command_id": command_id,
                    "session_present": True,
                    "session_record": asdict(updated_record),
                    **result.data,
                }
            else:
                data = {
                    "command_id": command_id,
                    "session_present": store.has_active_session(),
                    **result.data,
                }
            return _packet(
                status=result.status,
                exit_code=result.exit_code,
                human_message=result.human_message,
                machine_error_code=result.machine_error_code,
                next_action=result.next_action,
                data=data,
                changed_files=result.changed_files,
            )
        if command_id == "clear_review_session":
            had_active = store._clear_active_session()
            return _packet(
                status="ok",
                exit_code=0,
                human_message="Review session cleared from the main-process store.",
                machine_error_code="OK",
                next_action="query_review_surface",
                data={
                    "command_id": command_id,
                    "cleared": had_active,
                    "session_present": False,
                },
            )
        if command_id == "import_review_packet":
            adapted = _normalize_import_payload(body, import_context=import_context)
            project_id = _require_nonempty_string(adapted, "project_id")
            session_id = _require_nonempty_string(adapted, "session_id")
            baseline_hash = _require_nonempty_string(adapted, "baseline_hash")
            source_packet_hash = _require_nonempty_string(adapted, "source_packet_hash")
            review_surface = _require_object(adapted, "review_surface")
            revision_session = _require_object(adapted, "revision_session")
            record = store._store_imported_session(
                project_id=project_id,
                session_id=session_id,
                baseline_hash=baseline_hash,
                review_surface=review_surface,
                revision_session=revision_session,
                source_packet_hash=source_packet_hash,
            )
            return _packet(
                status="ok",
                exit_code=0,
                human_message="Review session stored in the main-process review bridge.",
                machine_error_code="OK",
                next_action="query_review_surface",
                data={
                    "command_id": command_id,
                    "session_present": True,
                    "manuscript_write_performed": False,
                    "filesystem_mutation_performed": False,
                    "session_store_memory_only": True,
                    "session_record": asdict(record),
                },
            )
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_NOT_ALLOWLISTED",
            f"Review command is not allowlisted: {command_id}",
        )
    except ReviewBridgeCommandError as exc:
        return _packet(
            status="command_error",
            exit_code=1,
            human_message=exc.human_message,
            machine_error_code=exc.machine_error_code,
            next_action="fix_command_payload",
            data={"command_id": command_id},
        )


def _normalize_import_payload(
    payload: dict[str, Any],
    *,
    import_context: ReviewImportContext | None,
) -> dict[str, Any]:
    if import_context is None:
        raise ReviewBridgeCommandError(
            "REVIEW_IMPORT_CONTEXT_UNAVAILABLE",
            "Review import context is unavailable for packet adaptation.",
        )
    try:
        return adapt_review_packet(payload["review_packet"], context=import_context)
    except ReviewPacketImportError as exc:
        raise ReviewBridgeCommandError(exc.machine_error_code, exc.human_message) from exc


def _packet(
    *,
    status: str,
    exit_code: int,
    human_message: str,
    machine_error_code: str,
    next_action: str,
    data: dict[str, Any],
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    packet = {
        "status": status,
        "exit_code": exit_code,
        "human_message": human_message,
        "machine_error_code": machine_error_code,
        "changed_files": changed_files or [],
        "next_action": next_action,
        "data": data,
    }
    return packet


def _require_spec(command_id: str) -> ReviewCommandSpec:
    try:
        return ALLOWLIST[command_id]
    except KeyError as exc:
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_NOT_ALLOWLISTED",
            f"Review command is not allowlisted: {command_id}",
        ) from exc


def _validate_payload_shape(spec: ReviewCommandSpec, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_INVALID_PAYLOAD",
            f"{spec.command_id} payload must be a JSON object.",
        )
    unknown_args = sorted(set(payload) - set(spec.allowed_args))
    if unknown_args:
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_UNSUPPORTED_ARGS",
            f"{spec.command_id} got unsupported args: {', '.join(unknown_args)}",
        )
    missing_args = [arg for arg in spec.required_args if arg not in payload]
    if missing_args:
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_MISSING_ARGS",
            f"{spec.command_id} missing required args: {', '.join(missing_args)}",
        )


def _require_nonempty_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_INVALID_PAYLOAD",
            f"{key} must be a non-empty string.",
        )
    return value.strip()


def _require_object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ReviewBridgeCommandError(
            "REVIEW_COMMAND_INVALID_PAYLOAD",
            f"{key} must be an object.",
        )
    return value
