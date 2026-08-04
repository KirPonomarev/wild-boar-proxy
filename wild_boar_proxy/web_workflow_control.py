# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Web workflow control surface (B14).

JSON control endpoints over the execution core: workflow run controls
(B13 runner), workflow history, writer status, capability/evidence badges,
provider/transport/model selection facts, aliases, credential presence,
assignments, and context policies. Protected by token, rate limit,
origin/CSRF checks, strict packets, loopback policy, and secret redaction.
The dispatch seam is controlled-only in B14; live dispatch is rejected
with a typed error.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import execution_core_design_gate as ecg
from . import sequential_workflow_runner as wf
from .runtime import build_command_payload
from .web_ingress import origin_header_is_allowed
from .web_rate_limit import WebPostRateLimiter
from .web_token import WebTokenState, verify_web_token, web_post_csrf_valid

WEB_WORKFLOW_CONTROL_SCHEMA_VERSION = 1

HISTORY_MAX_ENTRIES = 50
LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost"})

DISPATCH_MODE_CONTROLLED = "controlled_fake"
DISPATCH_MODE_LIVE = "live"

WC_OK = "OK"
WC_UNAUTHORIZED = "WORKFLOW_CONTROL_UNAUTHORIZED"
WC_RATE_LIMITED = "WORKFLOW_CONTROL_RATE_LIMITED"
WC_ORIGIN_DENIED = "WORKFLOW_CONTROL_ORIGIN_DENIED"
WC_CSRF_INVALID = "WORKFLOW_CONTROL_CSRF_INVALID"
WC_LOOPBACK_DENIED = "WORKFLOW_CONTROL_LOOPBACK_DENIED"
WC_LIVE_DISPATCH_NOT_IMPLEMENTED = "WORKFLOW_LIVE_DISPATCH_NOT_IMPLEMENTED"
WC_UNKNOWN_PATH = "WORKFLOW_CONTROL_UNKNOWN_PATH"
WC_SCHEMA_INVALID = "WORKFLOW_CONTROL_SCHEMA_INVALID"
WC_WRITER_BUSY = "WORKFLOW_CONTROL_WRITER_BUSY"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class WorkflowRunHistory:
    """Bounded, thread-safe workflow run history."""

    max_entries: int = HISTORY_MAX_ENTRIES
    _entries: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries :]

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries = []


class WorkflowWriterLock:
    """Single workflow writer with a fencing token."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._holder: str | None = None
        self._fencing_token: str | None = None
        self._acquired_at: str | None = None

    def acquire(self, holder: str) -> dict[str, Any]:
        with self._lock:
            if self._holder is not None:
                return {
                    "status": "blocked",
                    "holder": self._holder,
                    "fencing_token": None,
                }
            token = uuid.uuid4().hex
            self._holder = holder
            self._fencing_token = token
            self._acquired_at = _utc_now()
            return {
                "status": "ok",
                "holder": holder,
                "fencing_token": token,
                "acquired_at": self._acquired_at,
            }

    def release(self, *, fencing_token: str) -> dict[str, Any]:
        with self._lock:
            if self._holder is None:
                return {"status": "ok", "released": False}
            if self._fencing_token != fencing_token:
                return {"status": "blocked", "reason": "fencing_mismatch"}
            self._holder = None
            self._fencing_token = None
            self._acquired_at = None
            return {"status": "ok", "released": True}

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._holder is None:
                return {"status": "free", "holder": None, "fencing_token": None}
            return {
                "status": "held",
                "holder": self._holder,
                "fencing_token": self._fencing_token,
                "acquired_at": self._acquired_at,
            }


class WorkflowControlState:
    """Server-owned state for the workflow control surface."""

    def __init__(
        self,
        *,
        gate_facts: Mapping[str, Any],
        capability_badges: Sequence[Mapping[str, Any]] | None = None,
        alias_bindings: Sequence[Mapping[str, Any]] | None = None,
        credential_presence: Mapping[str, Any] | None = None,
        assignment_facts: Sequence[Mapping[str, Any]] | None = None,
        context_policies: Sequence[Mapping[str, Any]] | None = None,
        selection_facts: Mapping[str, Any] | None = None,
    ) -> None:
        self.gate_facts = dict(gate_facts)
        self.capability_badges = list(capability_badges or [])
        self.alias_bindings = list(alias_bindings or [])
        self.credential_presence = dict(credential_presence or {})
        self.assignment_facts = list(assignment_facts or [])
        self.context_policies = list(context_policies or [])
        self.selection_facts = dict(selection_facts or {})
        self.history = WorkflowRunHistory()
        self.writer_lock = WorkflowWriterLock()


def _dispatch_seam(step: wf.WorkflowStep, incoming_digest: str) -> dict[str, Any]:
    """Controlled dispatch seam (fake adapter) for B14.

    Deterministic ok receipts; never touches a live provider.
    """
    return {
        "status": "ok",
        "provider": step.provider,
        "output_text": f"controlled:{step.step_request_id}",
        "machine_error_code": "OK",
    }


def _bad_request(message: str, machine_error_code: str) -> dict[str, Any]:
    return build_command_payload(
        ok=False,
        human_message=message,
        machine_error_code=machine_error_code,
        liveness="healthy",
        severity="error",
        operator_action="user_action",
        changed_files=[],
        exit_code=1,
        extra={"schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION},
    )


def handle_workflow_control_request(
    *,
    state: WorkflowControlState,
    token_state: WebTokenState,
    rate_limiter: WebPostRateLimiter,
    method: str,
    path: str,
    headers: Mapping[str, str],
    body: bytes | None = None,
    client_ip: str = "127.0.0.1",
    server_port: int = 0,
) -> dict[str, Any]:
    """Strict request handler for the workflow control surface.

    Protection order: loopback client -> rate limit -> token -> origin ->
    CSRF -> handler. Every response is a strict command packet.
    """
    if client_ip not in LOOPBACK_CLIENTS:
        return _bad_request("clients must be loopback.", WC_LOOPBACK_DENIED)

    if method == "POST":
        if not rate_limiter.admit(client_ip=client_ip, path=path):
            return _bad_request("rate limit exceeded.", WC_RATE_LIMITED)
        if not verify_web_token(token_state, headers.get("x-wbp-token")):
            return _bad_request("invalid web token.", WC_UNAUTHORIZED)
        if not origin_header_is_allowed(
            headers.get("origin"), host_header=headers.get("host"), server_port=server_port
        ):
            return _bad_request("origin is not allowed.", WC_ORIGIN_DENIED)
        if not web_post_csrf_valid(token_state, headers):
            return _bad_request("CSRF verification failed.", WC_CSRF_INVALID)
        return _handle_post(state, path, headers, body or b"")

    if method == "GET":
        return _handle_get(state, path)

    return _bad_request("method not supported.", WC_UNKNOWN_PATH)


def _handle_get(state: WorkflowControlState, path: str) -> dict[str, Any]:
    if path == "/api/workflow/gate":
        gate = ecg.run_execution_core_design_gate(**state.gate_facts)
        return build_command_payload(
            ok=gate["status"] == "ok",
            human_message=(
                "design gate earned."
                if gate["status"] == "ok"
                else "design gate not earned."
            ),
            machine_error_code=gate["machine_error_code"],
            liveness="healthy",
            severity="info" if gate["status"] == "ok" else "error",
            operator_action="none",
            changed_files=[],
            exit_code=gate["exit_code"],
            extra={
                "design_gate_earned": gate.get("design_gate_earned"),
                "design_gate_marker": gate.get("design_gate_marker"),
                "input_evidence": gate.get("input_evidence"),
                "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
            },
        )
    if path == "/api/workflow/history":
        return build_command_payload(
            ok=True,
            human_message=f"{len(state.history.list())} workflow run(s) recorded.",
            machine_error_code=WC_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "history": state.history.list(),
                "history_max_entries": state.history.max_entries,
                "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
            },
        )
    if path == "/api/workflow/status":
        return build_command_payload(
            ok=True,
            human_message="workflow control status.",
            machine_error_code=WC_OK,
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra={
                "writer": state.writer_lock.status(),
                "capability_badges": state.capability_badges,
                "alias_bindings": state.alias_bindings,
                "credential_presence": state.credential_presence,
                "assignment_facts": state.assignment_facts,
                "context_policies": state.context_policies,
                "selection_facts": state.selection_facts,
                "dispatch_modes_supported": [DISPATCH_MODE_CONTROLLED],
                "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
            },
        )
    return _bad_request("unknown GET path.", WC_UNKNOWN_PATH)


def _parse_run_payload(body: bytes) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return [], _bad_request("body is not valid JSON.", WC_SCHEMA_INVALID)
    if not isinstance(payload, dict):
        return [], _bad_request("payload must be an object.", WC_SCHEMA_INVALID)
    dispatch_mode = str(payload.get("dispatch_mode") or DISPATCH_MODE_CONTROLLED)
    if dispatch_mode == DISPATCH_MODE_LIVE:
        return [], _bad_request(
            "live dispatch is not implemented on the web control surface.",
            WC_LIVE_DISPATCH_NOT_IMPLEMENTED,
        )
    if dispatch_mode != DISPATCH_MODE_CONTROLLED:
        return [], _bad_request("unknown dispatch mode.", WC_SCHEMA_INVALID)
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return [], _bad_request("steps must be a non-empty list.", WC_SCHEMA_INVALID)
    return raw_steps, None


def _steps_from_payload(raw_steps: Sequence[Mapping[str, Any]]) -> list[wf.WorkflowStep]:
    steps: list[wf.WorkflowStep] = []
    for index, raw in enumerate(raw_steps):
        try:
            steps.append(
                wf.WorkflowStep(
                    step_request_id=str(raw.get("step_request_id") or f"s{index}"),
                    slot_id=str(raw.get("slot_id") or "slot-web"),
                    binding_id=str(raw.get("binding_id") or "binding-web"),
                    binding_revision=int(raw.get("binding_revision") or 1),
                    assignment_id=str(raw.get("assignment_id") or "assignment-web"),
                    provider=str(raw.get("provider") or ""),
                    prompt=str(raw.get("prompt") or ""),
                    role_instruction=str(raw.get("role_instruction") or ""),
                    context_policy=str(raw.get("context_policy") or wf.CONTEXT_POLICY_FRESH),
                    fork_from=str(raw.get("fork_from") or ""),
                    repo_touching=bool(raw.get("repo_touching") or False),
                )
            )
        except (TypeError, ValueError):
            continue
    return steps


def _handle_post(
    state: WorkflowControlState,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
) -> dict[str, Any]:
    if path != "/api/workflow/run":
        return _bad_request("unknown POST path.", WC_UNKNOWN_PATH)
    raw_steps, error = _parse_run_payload(body)
    if error is not None:
        return error
    steps = _steps_from_payload(raw_steps)
    if not steps:
        return _bad_request("no valid steps in payload.", WC_SCHEMA_INVALID)

    acquired = state.writer_lock.acquire("web-workflow-run")
    if acquired["status"] != "ok":
        return _bad_request(
            f"workflow writer is busy ({acquired['holder']}).", WC_WRITER_BUSY
        )
    fencing_token = acquired["fencing_token"]
    try:
        packet = wf.run_sequential_workflow(
            steps,
            dispatch=_dispatch_seam,
            workflow_run_id=uuid.uuid4().hex,
        )
        state.history.append(
            {
                "recorded_at_utc": _utc_now(),
                "workflow_run_id": packet.get("workflow_run_id"),
                "dispatched_steps": packet.get("dispatched_steps"),
                "all_steps_delivered": packet.get("all_steps_delivered"),
                "stop_reason": packet.get("stop_reason"),
            }
        )
    finally:
        state.writer_lock.release(fencing_token=fencing_token)
    return build_command_payload(
        ok=packet["status"] == "ok",
        human_message=packet["human_message"],
        machine_error_code=packet["machine_error_code"],
        liveness="healthy",
        severity="info" if packet["status"] == "ok" else "error",
        operator_action="none" if packet["status"] == "ok" else "user_action",
        changed_files=[],
        exit_code=packet["exit_code"],
        extra={
            "workflow_run_id": packet.get("workflow_run_id"),
            "dispatched_steps": packet.get("dispatched_steps"),
            "all_steps_delivered": packet.get("all_steps_delivered"),
            "stop_reason": packet.get("stop_reason"),
            "receipts": packet.get("receipts"),
            "dispatch_mode": DISPATCH_MODE_CONTROLLED,
            "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
        },
    )


__all__ = [
    "WorkflowRunHistory",
    "WorkflowWriterLock",
    "WorkflowControlState",
    "handle_workflow_control_request",
    "DISPATCH_MODE_CONTROLLED",
    "DISPATCH_MODE_LIVE",
]
