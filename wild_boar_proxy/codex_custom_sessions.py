# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Server-owned Codex Custom session lifecycle packets."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wild_boar_proxy.codex_account_selection import (
    build_account_selection_packet,
    forbidden_account_smoke_fields,
)
from wild_boar_proxy.codex_model_registry import (
    build_custom_model_registry_packet,
    forbidden_custom_model_fields,
)


SESSION_CREATE_ALLOWED_FIELDS = {"model_id"}
PROMPT_DRY_RUN_ALLOWED_FIELDS = {"prompt"}
SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{7,80}$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_preview(value: str) -> str:
    return f"<prompt:{len(value)}:{_digest(value)[:8]}>"


def _forbidden_fields(payload: Any, allowed_fields: set[str], prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            key_lower = key_text.lower()
            if key_lower not in allowed_fields or prefix:
                findings.append(key_path)
            findings.extend(_forbidden_fields(value, allowed_fields, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_forbidden_fields(value, allowed_fields, f"{prefix}[{index}]"))
    return findings


def forbidden_session_create_fields(payload: Any) -> list[str]:
    return sorted(
        set(
            _forbidden_fields(payload, SESSION_CREATE_ALLOWED_FIELDS)
            + forbidden_custom_model_fields(payload)
            + forbidden_account_smoke_fields(payload)
        )
    )


def forbidden_prompt_dry_run_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, PROMPT_DRY_RUN_ALLOWED_FIELDS)))


def _model_ids(operator_status: dict[str, Any] | None) -> list[str]:
    registry = build_custom_model_registry_packet(operator_status)
    return [str(entry["model_id"]) for entry in registry.get("available_models", [])]


class CodexCustomSessionManager:
    def __init__(self, root: Path | None = None) -> None:
        base = root or Path(tempfile.gettempdir()) / "wbp-codex-custom-sessions"
        self.root = base.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._sessions: dict[str, dict[str, Any]] = {}

    def list_packet(self) -> dict[str, Any]:
        sessions = [self._public_session(session) for session in self._sessions.values()]
        return {
            "schema_version": 1,
            "status": "ok",
            "machine_error_code": "OK",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "session_count": len(sessions),
            "sessions": sessions,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
        }

    def create_packet(
        self,
        payload: dict[str, Any],
        commands: dict[str, dict[str, Any]],
        operator_status: dict[str, Any] | None,
    ) -> dict[str, Any]:
        forbidden = forbidden_session_create_fields(payload)
        if forbidden:
            return self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden)
        model_id = payload.get("model_id")
        model_ids = _model_ids(operator_status)
        if not isinstance(model_id, str) or model_id not in model_ids:
            return {
                **self._base_packet("rejected", "MODEL_NOT_SERVER_ISSUED"),
                "human_message": "Session create accepts only server-issued model_id.",
                "model_server_issued": False,
                "next_action": "select_model_from_server_registry",
            }
        selection = build_account_selection_packet(commands, operator_status)
        if selection.get("selection_proven") is not True:
            return {
                **self._base_packet(
                    "rejected",
                    str(selection.get("machine_error_code") or "SELECTION_NOT_PROVEN"),
                ),
                "human_message": "Codex Custom session requires server-issued account selection proof.",
                "model_id": model_id,
                "model_server_issued": True,
                "selection_proven": False,
                "selection_packet": self._selection_summary(selection),
                "session_created": False,
                "next_action": "repair_account_selection_truth",
            }
        session_id = f"ccs-{uuid.uuid4().hex[:20]}"
        session_root = (self.root / session_id).resolve()
        if not self._is_owned_session_path(session_root):
            return {
                **self._base_packet("failed", "SESSION_ROOT_OUTSIDE_APPROVED_ROOT"),
                "next_action": "stop_and_diagnose",
            }
        codex_home = session_root / "codex-home"
        workdir = session_root / "workdir"
        codex_home.mkdir(mode=0o700, parents=True, exist_ok=False)
        workdir.mkdir(mode=0o700, parents=True, exist_ok=False)
        now = utc_now()
        session = {
            "session_id": session_id,
            "created_at_utc": now,
            "updated_at_utc": now,
            "status": "ready",
            "model_id": model_id,
            "model_server_issued": True,
            "selected_source_class": selection.get("selected_source_class"),
            "selected_backend_id": selection.get("selected_backend_id"),
            "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
            "selection_proven": selection.get("selection_proven") is True,
            "selection_machine_error_code": selection.get("machine_error_code"),
            "session_root": str(session_root),
            "codex_home": str(codex_home),
            "workdir": str(workdir),
            "ledger": [],
            "prompt_admission_count": 0,
            "cleanup_state": "not_cleaned",
            "cancel_state": "not_cancelled",
        }
        self._append_ledger(session, "session_created")
        self._sessions[session_id] = session
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "human_message": "Codex Custom session created.",
            "session": self._public_session(session),
            "selection_packet": self._selection_summary(selection),
            "next_action": "prompt_dry_run",
        }

    def get_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        return {
            **self._base_packet("ok", "OK"),
            "session": self._public_session(session),
            "next_action": "none",
        }

    def prompt_dry_run_packet(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        if session.get("cleanup_state") == "cleaned":
            return {
                **self._base_packet("rejected", "SESSION_ALREADY_CLEANED"),
                "session_id": session_id,
                "next_action": "create_session",
            }
        forbidden = forbidden_prompt_dry_run_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
            }
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return {
                **self._base_packet("rejected", "PROMPT_MISSING"),
                "session_id": session_id,
                "prompt_present": False,
                "next_action": "enter_prompt",
            }
        prompt_hash = _digest(prompt)
        prompt_entry = {
            "event": "prompt_admitted_dry_run",
            "prompt_present": True,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "prompt_preview_redacted": _safe_preview(prompt),
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
        }
        session["prompt_admission_count"] = int(session.get("prompt_admission_count") or 0) + 1
        session["status"] = "prompt_admitted_dry_run"
        session["updated_at_utc"] = utc_now()
        self._append_ledger(session, "prompt_admitted_dry_run", prompt_entry)
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "dry_run": True,
            "prompt_admitted": True,
            "prompt_present": True,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "prompt_preview_redacted": _safe_preview(prompt),
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
            "negative_claim_basis": "prompt_admission_dry_run_no_inference_adapter",
            "session": self._public_session(session),
            "next_action": "codex_custom_gpt_api_e2e_pass",
        }

    def transcript_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "transcript_kind": "service_ledger_only",
            "model_response_present": False,
            "inference_proven": False,
            "entries": list(session.get("ledger") or []),
            "next_action": "none",
        }

    def cancel_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        if session.get("cleanup_state") == "cleaned":
            return {
                **self._base_packet("rejected", "SESSION_ALREADY_CLEANED"),
                "session_id": session_id,
                "process_kill_claimed": False,
                "next_action": "create_session",
            }
        session["cancel_state"] = "cancelled_dry_run_session"
        session["status"] = "cancelled"
        session["updated_at_utc"] = utc_now()
        self._append_ledger(session, "cancel_requested", {"process_kill_claimed": False})
        self._write_session(session)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "cancelled": True,
            "process_kill_claimed": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
            "session": self._public_session(session),
            "next_action": "cleanup_session",
        }

    def cleanup_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        session_root = Path(str(session.get("session_root") or "")).resolve()
        if not self._is_owned_session_path(session_root):
            return {
                **self._base_packet("failed", "SESSION_ROOT_OUTSIDE_APPROVED_ROOT"),
                "session_id": session_id,
                "cleanup_performed": False,
                "next_action": "stop_and_diagnose",
            }
        existed_before = session_root.exists()
        if existed_before:
            shutil.rmtree(session_root)
        session["cleanup_state"] = "cleaned"
        session["status"] = "cleaned"
        session["updated_at_utc"] = utc_now()
        self._append_ledger(
            session,
            "cleanup_completed",
            {"session_root_existed_before": existed_before, "session_root_exists_after": False},
        )
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "cleanup_performed": True,
            "session_root_existed_before": existed_before,
            "session_root_exists_after": session_root.exists(),
            "deleted_path_scope": "owned_temp_session_root",
            "arbitrary_path_accepted": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
            "session": self._public_session(session),
            "next_action": "none",
        }

    def _append_ledger(
        self,
        session: dict[str, Any],
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "event": event,
            "captured_at_utc": utc_now(),
            "session_id": session["session_id"],
        }
        if payload:
            entry.update(payload)
        session.setdefault("ledger", []).append(entry)

    def _write_session(self, session: dict[str, Any]) -> None:
        root = Path(str(session["session_root"])).resolve()
        if not self._is_owned_session_path(root):
            raise ValueError("session root outside approved root")
        payload = {
            "session": self._public_session(session),
            "ledger": session.get("ledger", []),
        }
        (root / "session.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (root / "ledger.jsonl").write_text(
            "".join(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n" for entry in session.get("ledger", [])),
            encoding="utf-8",
        )
        (root / "transcript.jsonl").write_text(
            "".join(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n" for entry in session.get("ledger", [])),
            encoding="utf-8",
        )

    def _public_session(self, session: dict[str, Any]) -> dict[str, Any]:
        session_id = str(session["session_id"])
        selected_backend_id = str(session.get("selected_backend_id") or "")
        session_root = str(session.get("session_root") or "")
        codex_home = str(session.get("codex_home") or "")
        return {
            "session_id": session_id,
            "created_at_utc": session.get("created_at_utc"),
            "updated_at_utc": session.get("updated_at_utc"),
            "status": session.get("status"),
            "model_id": session.get("model_id"),
            "model_server_issued": session.get("model_server_issued") is True,
            "selected_source_class": session.get("selected_source_class"),
            "selected_backend_digest": _digest(selected_backend_id) if selected_backend_id else "",
            "selected_backend_server_issued": session.get("selected_backend_server_issued") is True,
            "selection_proven": session.get("selection_proven") is True,
            "selection_machine_error_code": session.get("selection_machine_error_code"),
            "session_root_digest": _digest(session_root) if session_root else "",
            "codex_home_digest": _digest(codex_home) if codex_home else "",
            "session_root_scope": "owned_temp_session_root",
            "prompt_admission_count": int(session.get("prompt_admission_count") or 0),
            "cleanup_state": session.get("cleanup_state"),
            "cancel_state": session.get("cancel_state"),
            "ledger_entry_count": len(session.get("ledger") or []),
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
        }

    def _selection_summary(self, selection: dict[str, Any]) -> dict[str, Any]:
        selected_backend_id = str(selection.get("selected_backend_id") or "")
        return {
            "selection_proven": selection.get("selection_proven") is True,
            "selected_source_class": selection.get("selected_source_class"),
            "selected_backend_digest": _digest(selected_backend_id) if selected_backend_id else "",
            "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
            "browser_selected_backend": selection.get("browser_selected_backend") is True,
            "machine_error_code": selection.get("machine_error_code"),
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
        }

    def _is_owned_session_path(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
            resolved.relative_to(self.root)
        except ValueError:
            return False
        return resolved != self.root

    def _base_packet(self, status: str, machine_error_code: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "status": status,
            "machine_error_code": machine_error_code,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "inference_proven": False,
            "runtime_meter_attached": False,
            "token_burn": 0,
        }

    def _rejected(self, machine_error_code: str, forbidden: list[str]) -> dict[str, Any]:
        return {
            **self._base_packet("rejected", machine_error_code),
            "human_message": "Codex Custom session payload contains forbidden browser fields.",
            "forbidden_fields": forbidden,
            "next_action": "remove_forbidden_browser_fields",
        }

    def _unknown_session(self) -> dict[str, Any]:
        return {
            **self._base_packet("rejected", "SESSION_NOT_FOUND"),
            "human_message": "Codex Custom session id is not known to the server registry.",
            "next_action": "create_session",
        }


__all__ = [
    "CodexCustomSessionManager",
    "forbidden_prompt_dry_run_fields",
    "forbidden_session_create_fields",
]
