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
from typing import Any, Callable

from wild_boar_proxy.operator_surface import redact_text

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
PROMPT_RUN_ALLOWED_FIELDS = {"prompt"}
SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{7,80}$")
PROMPT_RUN_ALLOWED_STATUSES = {"ready", "prompt_admitted_dry_run"}
BOUNDED_RESPONSE_PREVIEW_CHARS = 240


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


def forbidden_prompt_run_fields(payload: Any) -> list[str]:
    return sorted(set(_forbidden_fields(payload, PROMPT_RUN_ALLOWED_FIELDS)))


def _model_ids(
    operator_status: dict[str, Any] | None,
    api_snapshot: dict[str, Any] | None = None,
) -> list[str]:
    registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    return [str(entry["model_id"]) for entry in registry.get("available_models", [])]


def _response_preview(value: str) -> str:
    return redact_text(value)[:BOUNDED_RESPONSE_PREVIEW_CHARS]


def _token_usage(result: dict[str, Any]) -> tuple[bool, dict[str, Any], int | None]:
    raw_usage = result.get("token_usage") or result.get("usage")
    if not isinstance(raw_usage, dict):
        return False, {}, None
    usage = {
        str(key): value
        for key, value in raw_usage.items()
        if isinstance(key, str) and isinstance(value, (int, float, str, bool)) and key.lower() != "api_key"
    }
    total = usage.get("total_tokens") or usage.get("total")
    return True, usage, int(total) if isinstance(total, int) else None


def _safe_trace_observer_packet(packet: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "request_observed",
        "response_observed",
        "forwarded_to_wbp",
        "forwarded_endpoint",
        "method",
        "path",
        "request_body_sha256",
        "response_body_sha256",
        "upstream_status",
        "prompt_body_recorded",
        "auth_header_recorded",
        "secret_value_recorded",
        "raw_account_id_recorded",
        "raw_backend_id_recorded",
        "machine_error_code",
        "observer_closed",
    }
    safe: dict[str, Any] = {}
    for key, value in packet.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, bool)) or value is None:
            safe[key] = value
    return safe


def _safe_process_network_observation_packet(packet: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "status",
        "machine_error_code",
        "process_tree_observed",
        "sample_count",
        "observed_process_count_max",
        "allowed_local_endpoints",
        "allowed_local_endpoint_observed",
        "peer_endpoints",
        "non_local_peer_endpoints_present",
        "classification",
        "direct_non_wbp_model_egress_absent_proven",
        "raw_pid_exposed",
        "pid_not_exposed_to_browser",
        "secret_value_recorded",
    }
    safe: dict[str, Any] = {}
    for key, value in packet.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, list):
            safe[key] = value
    return safe


def _source_provenance_status(session: dict[str, Any]) -> str:
    if session.get("route_provenance_required") is True:
        if (
            session.get("selected_route_server_issued") is True
            and session.get("route_provenance_proven") is True
        ):
            return "route_proven"
        return "route_provenance_missing"
    if session.get("selected_backend_server_issued") is True:
        return "backend_proven"
    return "not_proven"


def _source_provenance_satisfied(session: dict[str, Any]) -> bool:
    return _source_provenance_status(session) in {"backend_proven", "route_proven"}


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
        *,
        selection: dict[str, Any] | None = None,
        api_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        forbidden = forbidden_session_create_fields(payload)
        if forbidden:
            return self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden)
        model_id = payload.get("model_id")
        model_ids = _model_ids(operator_status, api_snapshot)
        if not isinstance(model_id, str) or model_id not in model_ids:
            return {
                **self._base_packet("rejected", "MODEL_NOT_SERVER_ISSUED"),
                "human_message": "Session create accepts only server-issued model_id.",
                "model_server_issued": False,
                "next_action": "select_model_from_server_registry",
            }
        selection = selection or build_account_selection_packet(commands, operator_status)
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
            "selected_backend_ref": selection.get("selected_backend_ref"),
            "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
            "selected_route_ref": selection.get("selected_route_ref"),
            "selected_route_server_issued": selection.get("selected_route_server_issued") is True,
            "route_provenance_required": selection.get("route_provenance_required") is True,
            "route_provenance_proven": selection.get("route_provenance_proven") is True,
            "source_provenance_status": str(selection.get("source_provenance_status") or "not_proven"),
            "selection_dry_run_proven": selection.get("selection_dry_run_proven") is True,
            "live_selection_proven": selection.get("live_selection_proven") is True,
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
            "session_created": True,
            "live_prompt_admitted": False,
            "current_codex_home_used": False,
            "selected_backend_id_redacted": True,
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
            "raw_prompt_not_stored": True,
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
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
            "raw_prompt_not_stored": True,
            "model_response_present": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
            "token_burn": 0,
            "negative_claim_basis": "prompt_admission_dry_run_no_inference_adapter",
            "session": self._public_session(session),
            "next_action": "codex_custom_gpt_api_e2e_pass",
        }

    def prompt_not_admitted_packet(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        forbidden = forbidden_prompt_run_fields(payload)
        packet = {
            **self._base_packet("blocked", "OWNER_AUTHORIZATION_REQUIRED"),
            "human_message": "Live Codex Custom prompt requires exact owner authorization in the active thread.",
            "session_id": session_id,
            "authorization_status": "blocked_by_operator_authorization",
            "owner_authorization_phrase_present": False,
            "live_prompt_admitted": False,
            "live_prompt_executed": False,
            "prompt_runner_called": False,
            "raw_prompt_not_stored": True,
            "inference_proven": False,
            "model_response_present": False,
            "network_calls_made": False,
            "provider_called": False,
            "fallback_attempted": False,
            "token_burn": 0,
            "session": self._public_session(session),
            "next_action": "provide_exact_owner_authorization_phrase",
        }
        if forbidden:
            packet["status"] = "rejected"
            packet["machine_error_code"] = "FORBIDDEN_BROWSER_FIELD"
            packet["forbidden_fields"] = forbidden
            packet["next_action"] = "remove_forbidden_browser_fields"
        return packet

    def prompt_packet(
        self,
        session_id: str,
        payload: dict[str, Any],
        prompt_runner: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        owner_authorized: bool = False,
    ) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        precondition_failure = self._prompt_precondition_failure(session)
        if precondition_failure:
            return precondition_failure
        forbidden = forbidden_prompt_run_fields(payload)
        if forbidden:
            return {
                **self._rejected("FORBIDDEN_BROWSER_FIELD", forbidden),
                "session_id": session_id,
                "model_response_present": False,
                "fallback_attempted": False,
            }
        prompt = payload.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            return {
                **self._base_packet("rejected", "PROMPT_MISSING"),
                "session_id": session_id,
                "prompt_present": False,
                "model_response_present": False,
                "fallback_attempted": False,
                "next_action": "enter_prompt",
            }
        if not owner_authorized:
            return self.prompt_not_admitted_packet(session_id, {"prompt": prompt})
        prompt_hash = _digest(prompt)
        model_id = str(session.get("model_id") or "")
        runner_payload = {"prompt": prompt, "model_id": model_id}
        try:
            result = prompt_runner(runner_payload)
        except Exception as exc:  # pragma: no cover - defensive live boundary
            result = {
                "status": "failed",
                "machine_error_code": "PROMPT_RUNNER_EXCEPTION",
                "error_class": type(exc).__name__,
                "human_message": "Codex Custom prompt runner failed before returning a packet.",
            }
        response_text = str(result.get("final_message") or result.get("response_text") or "")
        response_digest = _digest(response_text) if response_text else ""
        token_usage_present, token_usage, token_burn = _token_usage(result)
        secret_value_recorded = result.get("secret_value_recorded") is True
        status_ok = result.get("status") == "ok" and bool(response_text) and not secret_value_recorded
        isolated_engine_home_proven = (
            result.get("env_codex_home_is_temp") is True
            and result.get("env_home_is_temp") is True
            and result.get("workdir_is_temp") is True
            and result.get("command_workdir_is_temp") is True
            and result.get("command_output_file_is_temp") is True
            and result.get("current_codex_home_used") is False
        )
        route_backed_source = session.get("selected_source_class") == "route_backed"
        allowed_providers = {"cliproxy", "external_route"} if route_backed_source else {"cliproxy"}
        allowed_wire_apis = {"responses", "chat_completions"} if route_backed_source else {"responses"}
        path_config_proven = (
            result.get("configured_provider") in allowed_providers
            and result.get("configured_wire_api") in allowed_wire_apis
            and result.get("wbp_endpoint_configured") is True
            and result.get("config_endpoint_matches") is True
            and result.get("config_provider_matches") is True
            and result.get("config_wire_api_matches") is True
            and result.get("command_uses_stdin_dash") is True
            and result.get("command_json_mode") is True
        )
        independent_wbp_trace_observed = result.get("independent_wbp_trace_observed") is True
        raw_trace_observer_packet = result.get("trace_observer_packet") if isinstance(result.get("trace_observer_packet"), dict) else {}
        trace_observer_packet = _safe_trace_observer_packet(raw_trace_observer_packet)
        raw_process_network_observation = (
            result.get("process_network_observation_packet")
            if isinstance(result.get("process_network_observation_packet"), dict)
            else {}
        )
        process_network_observation_packet = _safe_process_network_observation_packet(
            raw_process_network_observation
        )
        trace_path = str(trace_observer_packet.get("path") or "")
        upstream_status = trace_observer_packet.get("upstream_status")
        forwarded_to_wbp = trace_observer_packet.get("forwarded_to_wbp") is True
        wbp_path_configured = status_ok and path_config_proven
        wbp_path_proven = wbp_path_configured and independent_wbp_trace_observed
        source_provenance_status = _source_provenance_status(session)
        source_provenance_proven = _source_provenance_satisfied(session)
        cli_proxy_api_path_configured = (
            wbp_path_configured and result.get("configured_provider") == "cliproxy"
        )
        cli_proxy_api_path_proven = (
            wbp_path_proven and result.get("configured_provider") == "cliproxy"
        )
        trace_missing_after_response = status_ok and not wbp_path_proven
        route_provenance_missing_after_response = status_ok and wbp_path_proven and not source_provenance_proven
        current_codex_touched_after_response = status_ok and result.get("current_codex_home_used") is True
        isolation_missing_after_response = (
            status_ok and not current_codex_touched_after_response and not isolated_engine_home_proven
        )
        packet_status = (
            "ok"
            if status_ok and wbp_path_proven and source_provenance_proven and isolated_engine_home_proven
            else (
                "blocked"
                if trace_missing_after_response
                or route_provenance_missing_after_response
                or current_codex_touched_after_response
                or isolation_missing_after_response
                else str(result.get("status") or "failed")
            )
        )
        packet_machine_error_code = (
            "OK"
            if status_ok and wbp_path_proven and source_provenance_proven and isolated_engine_home_proven
            else (
                "WBP_TRACE_PROOF_MISSING"
                if trace_missing_after_response
                else (
                    "CURRENT_CODEX_TOUCHED"
                    if current_codex_touched_after_response
                    else (
                        "ISOLATION_PROOF_MISSING"
                        if isolation_missing_after_response
                        else (
                            "ROUTE_PROVENANCE_MISSING"
                            if route_provenance_missing_after_response
                            else str(result.get("machine_error_code") or "ENGINE_PROMPT_FAILED")
                        )
                    )
                )
            )
        )
        latency_ms = None
        duration_seconds = result.get("duration_seconds")
        if isinstance(duration_seconds, (int, float)):
            latency_ms = int(float(duration_seconds) * 1000)
        packet = {
            "schema_version": 1,
            "status": packet_status,
            "machine_error_code": packet_machine_error_code,
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "session_id": session_id,
            "model_id": model_id,
            "model_server_issued": True,
            "selected_source_class": session.get("selected_source_class"),
            "selected_backend_digest": str(session.get("selected_backend_ref") or ""),
            "selected_backend_server_issued": session.get("selected_backend_server_issued") is True,
            "selected_route_digest": str(session.get("selected_route_ref") or ""),
            "selected_route_server_issued": session.get("selected_route_server_issued") is True,
            "route_provenance_required": session.get("route_provenance_required") is True,
            "route_provenance_proven": session.get("route_provenance_proven") is True,
            "source_provenance_status": source_provenance_status,
            "source_provenance_proven": source_provenance_proven,
            "selected_source_provenance": source_provenance_status,
            "selection_dry_run_proven": session.get("selection_dry_run_proven") is True,
            "live_selection_proven": session.get("live_selection_proven") is True,
            "browser_selected_backend": False,
            "authorization_status": "authorized_by_owner_gate",
            "owner_authorization_phrase_present": True,
            "live_prompt_admitted": True,
            "live_prompt_executed": status_ok,
            "prompt_runner_called": True,
            "prompt_present": True,
            "prompt_length": len(prompt),
            "prompt_sha256": prompt_hash,
            "prompt_preview_redacted": _safe_preview(prompt),
            "model_response_present": status_ok,
            "inference_proven": status_ok,
            "live_prompt_full_success": (
                status_ok and wbp_path_proven and source_provenance_proven and isolated_engine_home_proven
            ),
            "response_digest": response_digest,
            "response_preview_bounded": _response_preview(response_text) if status_ok else "",
            "token_usage_present": token_usage_present,
            "token_usage": token_usage,
            "token_burn": token_burn,
            "latency_ms": latency_ms,
            "error_class": "" if status_ok else str(result.get("error_class") or result.get("machine_error_code") or "unknown"),
            "wbp_path_configured": wbp_path_configured,
            "cli_proxy_api_path_configured": cli_proxy_api_path_configured,
            "wbp_path_observed": independent_wbp_trace_observed,
            "cli_proxy_api_path_observed": independent_wbp_trace_observed,
            "wbp_path_proven": wbp_path_proven,
            "cli_proxy_api_path_proven": cli_proxy_api_path_proven,
            "independent_wbp_trace_observed": independent_wbp_trace_observed,
            "trace_path": trace_path,
            "upstream_status": upstream_status if isinstance(upstream_status, int) else None,
            "forwarded_to_wbp": forwarded_to_wbp,
            "trace_observer_packet": trace_observer_packet,
            "process_network_observation_packet": process_network_observation_packet,
            "isolated_engine_home_proven": isolated_engine_home_proven,
            "current_codex_touched": result.get("current_codex_home_used") is True,
            "configured_wire_api": result.get("configured_wire_api") if status_ok else "",
            "path_proof_status": "independently_observed" if wbp_path_proven else "configured_not_independently_observed",
            "path_proof_basis": "operator_surface_isolated_codex_exec_config_requires_independent_trace",
            "fallback_attempted": False,
            "raw_backend_id_exposed": False,
            "raw_auth_ref_exposed": False,
            "secret_value_recorded": secret_value_recorded,
            "session": self._public_session(session),
            "next_action": (
                "inspect_transcript"
                if status_ok and wbp_path_proven and source_provenance_proven and isolated_engine_home_proven
                else (
                    "inspect_trace_observer"
                    if trace_missing_after_response
                    else (
                        "stop_and_diagnose_current_codex_touch"
                        if current_codex_touched_after_response
                        else (
                            "repair_isolation_proof"
                            if isolation_missing_after_response
                            else (
                                "repair_route_provenance"
                                if route_provenance_missing_after_response
                                else str(result.get("next_action") or "stop_and_diagnose")
                            )
                        )
                    )
                )
            ),
        }
        event = "prompt_completed_e2e" if status_ok else "prompt_failed_e2e"
        session["status"] = event
        session["inference_proven"] = status_ok
        session["model_response_present"] = status_ok
        session["token_burn"] = token_burn
        session["updated_at_utc"] = utc_now()
        self._append_ledger(
            session,
            event,
            {
                "prompt_present": True,
                "prompt_length": len(prompt),
                "prompt_sha256": prompt_hash,
                "prompt_preview_redacted": _safe_preview(prompt),
                "model_response_present": status_ok,
                "inference_proven": status_ok,
                "response_digest": response_digest,
                "response_preview_bounded": _response_preview(response_text) if status_ok else "",
                "selected_source_class": session.get("selected_source_class"),
                "selected_backend_server_issued": session.get("selected_backend_server_issued") is True,
                "selected_route_server_issued": session.get("selected_route_server_issued") is True,
                "route_provenance_required": session.get("route_provenance_required") is True,
                "route_provenance_proven": session.get("route_provenance_proven") is True,
                "source_provenance_status": source_provenance_status,
                "source_provenance_proven": source_provenance_proven,
                "token_usage_present": token_usage_present,
                "token_usage": token_usage,
                "token_burn": token_burn,
                "latency_ms": latency_ms,
                "wbp_path_configured": wbp_path_configured,
                "cli_proxy_api_path_configured": cli_proxy_api_path_configured,
                "wbp_path_observed": independent_wbp_trace_observed,
                "cli_proxy_api_path_observed": independent_wbp_trace_observed,
                "wbp_path_proven": wbp_path_proven,
                "cli_proxy_api_path_proven": cli_proxy_api_path_proven,
                "independent_wbp_trace_observed": independent_wbp_trace_observed,
                "trace_observer_packet_present": bool(trace_observer_packet),
                "isolated_engine_home_proven": isolated_engine_home_proven,
                "fallback_attempted": False,
            },
        )
        self._write_session(session)
        packet["session"] = self._public_session(session)
        return packet

    def transcript_packet(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if not session:
            return self._unknown_session()
        entries = list(session.get("ledger") or [])
        model_response_present = any(entry.get("model_response_present") is True for entry in entries)
        inference_proven = any(entry.get("inference_proven") is True for entry in entries)
        return {
            **self._base_packet("ok", "OK"),
            "session_id": session_id,
            "transcript_kind": "service_ledger_only",
            "model_response_present": model_response_present,
            "inference_proven": inference_proven,
            "raw_prompt_not_stored": True,
            "raw_response_not_stored": True,
            "raw_backend_id_exposed": False,
            "raw_auth_ref_exposed": False,
            "network_calls_made": inference_proven,
            "provider_called": inference_proven,
            "token_burn": session.get("token_burn") if session.get("token_burn") is not None else 0,
            "entries": entries,
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
            "network_calls_made": False,
            "provider_called": False,
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
            "session_root_removed_or_marked_cleaned": True,
            "owned_session_root_only": True,
            "deleted_path_scope": "owned_temp_session_root",
            "arbitrary_path_accepted": False,
            "current_codex_home_touched": False,
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
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
        selected_backend_ref = str(session.get("selected_backend_ref") or "")
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
            "selected_backend_digest": selected_backend_ref,
            "selected_backend_id_redacted": True,
            "selected_backend_server_issued": session.get("selected_backend_server_issued") is True,
            "selected_route_digest": str(session.get("selected_route_ref") or ""),
            "selected_route_server_issued": session.get("selected_route_server_issued") is True,
            "route_provenance_required": session.get("route_provenance_required") is True,
            "route_provenance_proven": session.get("route_provenance_proven") is True,
            "source_provenance_status": _source_provenance_status(session),
            "source_provenance_proven": _source_provenance_satisfied(session),
            "selection_dry_run_proven": session.get("selection_dry_run_proven") is True,
            "live_selection_proven": session.get("live_selection_proven") is True,
            "selection_proven": session.get("selection_proven") is True,
            "selection_machine_error_code": session.get("selection_machine_error_code"),
            "session_root_digest": _digest(session_root) if session_root else "",
            "codex_home_digest": _digest(codex_home) if codex_home else "",
            "session_root_scope": "owned_temp_session_root",
            "current_codex_home_used": False,
            "prompt_admission_count": int(session.get("prompt_admission_count") or 0),
            "cleanup_state": session.get("cleanup_state"),
            "cancel_state": session.get("cancel_state"),
            "ledger_entry_count": len(session.get("ledger") or []),
            "model_response_present": session.get("model_response_present") is True,
            "inference_proven": session.get("inference_proven") is True,
            "runtime_meter_attached": False,
            "network_calls_made": session.get("inference_proven") is True,
            "provider_called": session.get("inference_proven") is True,
            "token_burn": session.get("token_burn") if session.get("token_burn") is not None else 0,
        }

    def _prompt_precondition_failure(self, session: dict[str, Any]) -> dict[str, Any] | None:
        session_id = str(session.get("session_id") or "")
        failures: list[str] = []
        if session.get("cleanup_state") == "cleaned":
            failures.append("SESSION_ALREADY_CLEANED")
        if str(session.get("status") or "") not in PROMPT_RUN_ALLOWED_STATUSES:
            failures.append("SESSION_STATUS_NOT_RUNNABLE")
        if session.get("model_server_issued") is not True:
            failures.append("MODEL_NOT_SERVER_ISSUED")
        if session.get("selection_proven") is not True:
            failures.append("SELECTION_NOT_PROVEN")
        route_required = session.get("route_provenance_required") is True
        if route_required:
            if session.get("selected_route_server_issued") is not True:
                failures.append("ROUTE_NOT_SERVER_ISSUED")
            if session.get("route_provenance_proven") is not True:
                failures.append("ROUTE_PROVENANCE_MISSING")
        elif session.get("selected_backend_server_issued") is not True:
            failures.append("BACKEND_NOT_SERVER_ISSUED")
        if not failures:
            return None
        return {
            **self._base_packet("rejected", failures[0]),
            "session_id": session_id,
            "precondition_failures": failures,
            "model_response_present": False,
            "token_usage_present": False,
            "fallback_attempted": False,
            "session": self._public_session(session),
            "next_action": "repair_session_preconditions",
        }

    def _selection_summary(self, selection: dict[str, Any]) -> dict[str, Any]:
        return {
            "selection_dry_run_proven": selection.get("selection_dry_run_proven") is True,
            "live_selection_proven": selection.get("live_selection_proven") is True,
            "selection_proven": selection.get("selection_proven") is True,
            "selected_source_class": selection.get("selected_source_class"),
            "selected_backend_digest": str(selection.get("selected_backend_ref") or ""),
            "selected_backend_server_issued": selection.get("selected_backend_server_issued") is True,
            "selected_route_digest": str(selection.get("selected_route_ref") or ""),
            "selected_route_server_issued": selection.get("selected_route_server_issued") is True,
            "route_provenance_required": selection.get("route_provenance_required") is True,
            "route_provenance_proven": selection.get("route_provenance_proven") is True,
            "source_provenance_status": str(selection.get("source_provenance_status") or "not_proven"),
            "browser_selected_backend": selection.get("browser_selected_backend") is True,
            "machine_error_code": selection.get("machine_error_code"),
            "inference_proven": False,
            "runtime_meter_attached": False,
            "network_calls_made": False,
            "provider_called": False,
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
            "network_calls_made": False,
            "provider_called": False,
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
