# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Server-owned web workflow control boundary (B14 + R64).

The browser supplies bounded workflow intent only. Canonical actor identity,
provider routes, assignments, transport admission, live authorization, and
repository leases stay server-owned and are resolved again for every run.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import actor_dispatcher
from . import actor_registry
from . import execution_core_design_gate as ecg
from . import sequential_workflow_runner as wf
from . import workflow_api_dispatch as wad
from .api_transport_adapter import ApiTransportAdapter
from .runtime import build_command_payload
from .web_ingress import origin_header_is_allowed
from .web_rate_limit import WebPostRateLimiter
from .web_token import WebTokenState, verify_web_token, web_post_csrf_valid

WEB_WORKFLOW_CONTROL_SCHEMA_VERSION = 2

HISTORY_MAX_ENTRIES = 50
MAX_WORKFLOW_STEPS = 12
MAX_ALIAS_CHARS = 80
MAX_STEP_ID_CHARS = 96
MAX_ROLE_INSTRUCTION_CHARS = wad.MAX_ROLE_INSTRUCTION_CHARS
LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost"})

DISPATCH_MODE_CONTROLLED = wad.EXECUTION_MODE_CONTROLLED
DISPATCH_MODE_LIVE = wad.EXECUTION_MODE_LIVE

RUN_ALLOWED_FIELDS = frozenset({"execution_mode", "steps"})
STEP_ALLOWED_FIELDS = frozenset(
    {
        "step_request_id",
        "alias",
        "prompt",
        "role_instruction",
        "context_policy",
        "fork_from",
        "repo_touching",
    }
)
STEP_IDENTITY_FIELDS = frozenset(
    {
        "actor_id",
        "assignment_id",
        "assignment_revision",
        "backend",
        "base_url",
        "binding_id",
        "binding_revision",
        "credential",
        "credential_ref",
        "endpoint",
        "model",
        "model_id",
        "provider",
        "provider_id",
        "route",
        "route_id",
        "slot_id",
        "transport_adapter_id",
    }
)

WC_OK = "OK"
WC_UNAUTHORIZED = "WORKFLOW_CONTROL_UNAUTHORIZED"
WC_RATE_LIMITED = "WORKFLOW_CONTROL_RATE_LIMITED"
WC_ORIGIN_DENIED = "WORKFLOW_CONTROL_ORIGIN_DENIED"
WC_CSRF_INVALID = "WORKFLOW_CONTROL_CSRF_INVALID"
WC_LOOPBACK_DENIED = "WORKFLOW_CONTROL_LOOPBACK_DENIED"
WC_UNKNOWN_PATH = "WORKFLOW_CONTROL_UNKNOWN_PATH"
WC_SCHEMA_INVALID = "WORKFLOW_CONTROL_SCHEMA_INVALID"
WC_BROWSER_AUTHORITY_FORBIDDEN = "WORKFLOW_BROWSER_AUTHORITY_FORBIDDEN"
WC_REGISTRY_UNAVAILABLE = "WORKFLOW_ACTOR_REGISTRY_UNAVAILABLE"
WC_EXECUTION_UNAVAILABLE = "WORKFLOW_EXECUTION_BOUNDARY_UNAVAILABLE"
WC_ACTOR_LANE_UNSUPPORTED = "WORKFLOW_ACTOR_LANE_UNSUPPORTED"
WC_WRITER_BUSY = "WORKFLOW_CONTROL_WRITER_BUSY"

# Compatibility name retained for callers that inspect the historical symbol.
WC_LIVE_DISPATCH_NOT_IMPLEMENTED = wad.WAD_LIVE_NOT_AUTHORIZED


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class WorkflowRunHistory:
    """Bounded, thread-safe workflow run history for one server process."""

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
    """Single workflow writer with a private fencing token."""

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

    def public_status(self) -> dict[str, Any]:
        status = self.status()
        return {
            "status": status["status"],
            "holder": status.get("holder"),
            "acquired_at": status.get("acquired_at"),
            "fencing_token_present": bool(status.get("fencing_token")),
            "fencing_token_exposed": False,
        }


RegistryLoader = Callable[[], Mapping[str, Any] | None]
GateLoader = Callable[[], Mapping[str, Any]]


class WorkflowControlState:
    """Server-owned dependencies and bounded state for workflow control."""

    def __init__(
        self,
        *,
        registry_document: Mapping[str, Any] | None = None,
        registry_loader: RegistryLoader | None = None,
        adapter: ApiTransportAdapter | None = None,
        lease_root: Path | str | None = None,
        live_dispatch_authorized: bool = False,
        gate_loader: GateLoader | None = None,
        gate_facts: Mapping[str, Any] | None = None,
        capability_badges: Sequence[Mapping[str, Any]] | None = None,
        alias_bindings: Sequence[Mapping[str, Any]] | None = None,
        credential_presence: Mapping[str, Any] | None = None,
        assignment_facts: Sequence[Mapping[str, Any]] | None = None,
        context_policies: Sequence[Mapping[str, Any]] | None = None,
        selection_facts: Mapping[str, Any] | None = None,
        history_max_entries: int = HISTORY_MAX_ENTRIES,
    ) -> None:
        if registry_document is not None and registry_loader is not None:
            raise ValueError("registry_document and registry_loader are mutually exclusive")
        self._registry_document = dict(registry_document or {})
        self.registry_loader = registry_loader
        self.adapter = adapter
        self.lease_root = Path(lease_root) if lease_root is not None else None
        self.live_dispatch_authorized = live_dispatch_authorized is True
        self.gate_loader = gate_loader or ecg.run_execution_core_design_gate
        self.gate_facts = dict(gate_facts or {})
        self.capability_badges = [dict(item) for item in capability_badges or []]
        self.alias_bindings = [dict(item) for item in alias_bindings or []]
        self.credential_presence = dict(credential_presence or {})
        self.assignment_facts = [dict(item) for item in assignment_facts or []]
        self.context_policies = [dict(item) for item in context_policies or []]
        self.selection_facts = dict(selection_facts or {})
        self.history = WorkflowRunHistory(max_entries=history_max_entries)
        self.writer_lock = WorkflowWriterLock()

    def registry_document(self) -> dict[str, Any]:
        try:
            loaded = self.registry_loader() if self.registry_loader is not None else self._registry_document
        except Exception:  # noqa: BLE001 - runtime filesystem details stay private
            return {}
        return dict(loaded) if isinstance(loaded, Mapping) else {}


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
        extra={
            "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
            "browser_can_supply_identity_authority": False,
            "browser_can_authorize_live_dispatch": False,
        },
    )


def _registry_public_facts(document: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validation = actor_registry.validate_actor_registry_document(document)
    if validation.get("valid") is not True:
        return [], {
            "status": "blocked",
            "machine_error_code": WC_REGISTRY_UNAVAILABLE,
            "registry_revision": None,
            "invalid_reason_count": len(validation.get("reasons") or []),
        }

    actors = {
        str(actor.get("actor_id") or ""): actor
        for actor in document.get("actors", [])
        if isinstance(actor, Mapping)
    }
    assignments = {
        str(item.get("slot_id") or ""): item
        for item in document.get("role_assignments", [])
        if isinstance(item, Mapping)
    }
    slots: list[dict[str, Any]] = []
    for binding in document.get("slot_bindings", []):
        if not isinstance(binding, Mapping) or binding.get("enabled") is not True:
            continue
        actor = actors.get(str(binding.get("actor_id") or ""), {})
        if actor.get("transport_adapter_id") != actor_registry.API_ADAPTER:
            continue
        assignment = assignments.get(str(binding.get("slot_id") or ""), {})
        aliases = [str(alias) for alias in binding.get("aliases", []) if str(alias).strip()]
        slots.append(
            {
                "slot_id": str(binding.get("slot_id") or ""),
                "display_name": str(actor.get("display_name") or ""),
                "primary_alias": aliases[0] if aliases else "",
                "aliases": aliases,
                "provider_id": str(actor.get("provider_id") or ""),
                "route_id": str(binding.get("route_id") or ""),
                "role_label": str(assignment.get("role_label") or "coding_agent"),
                "binding_revision": binding.get("binding_revision"),
                "assignment_revision": assignment.get("assignment_revision"),
                "context_policy": str(
                    assignment.get("assignment_context_policy")
                    or wf.CONTEXT_POLICY_FRESH
                ),
                "transport_adapter_id": actor_registry.API_ADAPTER,
                "no_fallback": True,
                "browser_supplied_identity": False,
            }
        )
    return slots, {
        "status": "ok",
        "machine_error_code": WC_OK,
        "registry_revision": document.get("registry_revision"),
        "api_slot_count": len(slots),
    }


def _gate_packet(state: WorkflowControlState) -> dict[str, Any]:
    try:
        gate = dict(state.gate_facts or state.gate_loader())
    except Exception:  # noqa: BLE001 - do not expose internal gate failures
        gate = {
            "status": "error",
            "machine_error_code": "DESIGN_GATE_EVIDENCE_UNAVAILABLE",
            "exit_code": 1,
            "design_gate_earned": False,
        }
    earned = gate.get("status") == "ok" and gate.get("design_gate_earned") is True
    return build_command_payload(
        ok=earned,
        human_message="design gate earned." if earned else "design gate not earned.",
        machine_error_code=str(gate.get("machine_error_code") or "DESIGN_GATE_NOT_EARNED"),
        liveness="healthy" if earned else "down",
        severity="info" if earned else "error",
        operator_action="none" if earned else "user_action",
        changed_files=[],
        exit_code=0 if earned else 1,
        extra={
            "design_gate_earned": earned,
            "design_gate_marker": gate.get("design_gate_marker"),
            "input_evidence": gate.get("input_evidence"),
            "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
        },
    )


def _status_packet(state: WorkflowControlState) -> dict[str, Any]:
    document = state.registry_document()
    actor_slots, registry = _registry_public_facts(document)
    execution_ready = bool(
        registry["status"] == "ok" and actor_slots and state.adapter is not None
    )
    modes = [
        {
            "id": DISPATCH_MODE_CONTROLLED,
            "admitted": execution_ready,
            "provider_network": False,
            "evidence_scope": "synthetic_transport",
        },
        {
            "id": DISPATCH_MODE_LIVE,
            "admitted": execution_ready and state.live_dispatch_authorized,
            "provider_network": True,
            "evidence_scope": "provider_receipt_required",
        },
    ]
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
            "writer": state.writer_lock.public_status(),
            "capability_badges": state.capability_badges,
            "alias_bindings": state.alias_bindings,
            "credential_presence": state.credential_presence,
            "assignment_facts": state.assignment_facts,
            "context_policies": state.context_policies,
            "selection_facts": state.selection_facts,
            "registry": registry,
            "actor_slots": actor_slots,
            "workflow_execution_ready": execution_ready,
            "execution_modes": modes,
            "dispatch_modes_supported": [DISPATCH_MODE_CONTROLLED, DISPATCH_MODE_LIVE],
            "dispatch_modes_admitted": [item["id"] for item in modes if item["admitted"]],
            "live_dispatch_authorized": state.live_dispatch_authorized,
            "browser_can_authorize_live_dispatch": False,
            "browser_can_supply_identity_authority": False,
            "browser_allowed_step_fields": sorted(STEP_ALLOWED_FIELDS),
            "history_count": len(state.history.list()),
            "history_max_entries": state.history.max_entries,
            "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
        },
    )


def _history_packet(state: WorkflowControlState) -> dict[str, Any]:
    history = state.history.list()
    return build_command_payload(
        ok=True,
        human_message=f"{len(history)} workflow run(s) recorded.",
        machine_error_code=WC_OK,
        liveness="healthy",
        severity="info",
        operator_action="none",
        changed_files=[],
        exit_code=0,
        extra={
            "history": history,
            "history_max_entries": state.history.max_entries,
            "history_persistence": "server_process_memory",
            "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
        },
    )


def _parse_json_object(body: bytes) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return {}, _bad_request("body is not valid JSON.", WC_SCHEMA_INVALID)
    if not isinstance(payload, dict):
        return {}, _bad_request("payload must be an object.", WC_SCHEMA_INVALID)
    return payload, None


def _parse_run_payload(payload: Mapping[str, Any]) -> tuple[str, list[Mapping[str, Any]], dict[str, Any] | None]:
    unexpected = sorted(set(payload) - RUN_ALLOWED_FIELDS)
    if unexpected:
        code = (
            WC_BROWSER_AUTHORITY_FORBIDDEN
            if set(unexpected) & STEP_IDENTITY_FIELDS
            else WC_SCHEMA_INVALID
        )
        return "", [], _bad_request("run payload contains unsupported fields.", code)
    execution_mode = str(payload.get("execution_mode") or DISPATCH_MODE_CONTROLLED)
    if execution_mode not in {DISPATCH_MODE_CONTROLLED, DISPATCH_MODE_LIVE}:
        return "", [], _bad_request("unknown execution mode.", WC_SCHEMA_INVALID)
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        return "", [], _bad_request("steps must be a non-empty list.", WC_SCHEMA_INVALID)
    if len(raw_steps) > MAX_WORKFLOW_STEPS:
        return "", [], _bad_request("workflow contains too many steps.", WC_SCHEMA_INVALID)
    if not all(isinstance(item, Mapping) for item in raw_steps):
        return "", [], _bad_request("every step must be an object.", WC_SCHEMA_INVALID)
    return execution_mode, list(raw_steps), None


def _steps_from_intent(
    state: WorkflowControlState,
    raw_steps: Sequence[Mapping[str, Any]],
) -> tuple[list[wf.WorkflowStep], dict[str, Any] | None]:
    document = state.registry_document()
    validation = actor_registry.validate_actor_registry_document(document)
    if validation.get("valid") is not True:
        return [], _bad_request("canonical actor registry is unavailable.", WC_REGISTRY_UNAVAILABLE)

    steps: list[wf.WorkflowStep] = []
    for index, raw in enumerate(raw_steps, start=1):
        unexpected = sorted(set(raw) - STEP_ALLOWED_FIELDS)
        if unexpected:
            code = (
                WC_BROWSER_AUTHORITY_FORBIDDEN
                if set(unexpected) & STEP_IDENTITY_FIELDS
                else WC_SCHEMA_INVALID
            )
            return [], _bad_request("workflow step contains unsupported fields.", code)
        alias = str(raw.get("alias") or "").strip()
        step_id = str(raw.get("step_request_id") or f"step-{index}").strip()
        prompt = str(raw.get("prompt") or "").strip()
        role_instruction = str(raw.get("role_instruction") or "").strip()
        context_policy = str(raw.get("context_policy") or wf.CONTEXT_POLICY_FRESH)
        fork_from = str(raw.get("fork_from") or "").strip()
        repo_touching = raw.get("repo_touching", False)
        if not alias or len(alias) > MAX_ALIAS_CHARS:
            return [], _bad_request("step alias is missing or oversized.", WC_SCHEMA_INVALID)
        if not step_id or len(step_id) > MAX_STEP_ID_CHARS:
            return [], _bad_request("step_request_id is missing or oversized.", WC_SCHEMA_INVALID)
        if not prompt or len(prompt) > wf.MAX_VISIBLE_CONTEXT_CHARS:
            return [], _bad_request("step prompt is missing or oversized.", WC_SCHEMA_INVALID)
        if len(role_instruction) > MAX_ROLE_INSTRUCTION_CHARS:
            return [], _bad_request("step role instruction is oversized.", WC_SCHEMA_INVALID)
        if context_policy not in wf.CONTEXT_POLICIES:
            return [], _bad_request("step context policy is invalid.", WC_SCHEMA_INVALID)
        if not isinstance(repo_touching, bool):
            return [], _bad_request("repo_touching must be a boolean.", WC_SCHEMA_INVALID)
        try:
            plan = actor_dispatcher.resolve_alias_dispatch(
                alias=alias,
                registry_document=document,
                explicit_operator_grant=actor_registry.PERMISSION_CONTEXT_ONLY,
                adapter_capability=actor_registry.PERMISSION_CONTEXT_ONLY,
                runtime_policy=actor_registry.PERMISSION_CONTEXT_ONLY,
                requested_permission=actor_registry.PERMISSION_CONTEXT_ONLY,
            )
        except actor_dispatcher.DispatchResolutionError:
            return [], _bad_request("actor alias could not be resolved safely.", WC_REGISTRY_UNAVAILABLE)
        if plan.get("transport_adapter_id") != actor_registry.API_ADAPTER:
            return [], _bad_request(
                "the selected actor is not on the API workflow lane.",
                WC_ACTOR_LANE_UNSUPPORTED,
            )
        steps.append(
            wf.WorkflowStep(
                step_request_id=step_id,
                slot_id=str(plan.get("slot_id") or ""),
                binding_id=str(plan.get("binding_id") or ""),
                binding_revision=int(plan.get("binding_revision") or 0),
                assignment_id=str(plan.get("assignment_id") or ""),
                assignment_revision=int(plan.get("assignment_revision") or 0),
                provider=str(plan.get("provider_id") or ""),
                prompt=prompt,
                role_instruction=role_instruction,
                context_policy=context_policy,
                fork_from=fork_from,
                repo_touching=repo_touching,
                alias=alias,
            )
        )
    return steps, None


def _history_entry(
    packet: Mapping[str, Any],
    *,
    execution_mode: str,
    steps: Sequence[wf.WorkflowStep],
) -> dict[str, Any]:
    receipts = packet.get("receipts")
    if not isinstance(receipts, list):
        receipts = packet.get("intermediate_receipts")
    receipts = list(receipts) if isinstance(receipts, list) else []
    return {
        "recorded_at_utc": _utc_now(),
        "workflow_run_id": packet.get("workflow_run_id"),
        "status": packet.get("status"),
        "machine_error_code": packet.get("machine_error_code"),
        "execution_mode": execution_mode,
        "controlled": execution_mode == DISPATCH_MODE_CONTROLLED,
        "live_provider_proven": packet.get("live_provider_proven") is True,
        "requested_steps": len(steps),
        "dispatched_steps": packet.get("dispatched_steps", len(receipts)),
        "all_steps_delivered": packet.get("all_steps_delivered") is True,
        "stop_reason": packet.get("stop_reason"),
        "stopped_at_step": packet.get("stopped_at_step"),
        "actor_aliases": [step.alias for step in steps],
        "receipts": receipts,
    }


def _run_packet(state: WorkflowControlState, payload: Mapping[str, Any]) -> dict[str, Any]:
    execution_mode, raw_steps, error = _parse_run_payload(payload)
    if error is not None:
        return error
    if state.adapter is None:
        return _bad_request("workflow execution boundary is unavailable.", WC_EXECUTION_UNAVAILABLE)
    steps, error = _steps_from_intent(state, raw_steps)
    if error is not None:
        return error

    acquired = state.writer_lock.acquire("web-workflow-run")
    if acquired["status"] != "ok":
        return _bad_request(
            f"workflow writer is busy ({acquired['holder']}).", WC_WRITER_BUSY
        )
    fencing_token = str(acquired["fencing_token"])
    try:
        registry_document = state.registry_document()
        packet = wad.run_registry_bound_api_workflow(
            steps,
            registry_document=registry_document,
            adapter=state.adapter,
            execution_mode=execution_mode,
            live_dispatch_authorized=state.live_dispatch_authorized,
            lease_root=state.lease_root,
            workflow_run_id=uuid.uuid4().hex,
        )
        state.history.append(
            _history_entry(packet, execution_mode=execution_mode, steps=steps)
        )
    finally:
        state.writer_lock.release(fencing_token=fencing_token)

    return build_command_payload(
        ok=packet.get("status") == "ok",
        human_message=str(packet.get("human_message") or "workflow execution failed."),
        machine_error_code=str(packet.get("machine_error_code") or wf.WF_DISPATCH_FAILED),
        liveness="healthy",
        severity="info" if packet.get("status") == "ok" else "error",
        operator_action="none" if packet.get("status") == "ok" else "user_action",
        changed_files=[],
        exit_code=int(packet.get("exit_code") or (0 if packet.get("status") == "ok" else 1)),
        extra={
            "workflow_run_id": packet.get("workflow_run_id"),
            "requested_steps": len(steps),
            "dispatched_steps": packet.get("dispatched_steps"),
            "all_steps_delivered": packet.get("all_steps_delivered"),
            "stop_reason": packet.get("stop_reason"),
            "stopped_at_step": packet.get("stopped_at_step"),
            "receipts": packet.get("receipts", packet.get("intermediate_receipts", [])),
            "execution_mode": execution_mode,
            "controlled": packet.get("controlled"),
            "live_dispatch_authorized": state.live_dispatch_authorized,
            "live_provider_proven": packet.get("live_provider_proven") is True,
            "browser_can_authorize_live_dispatch": False,
            "browser_can_supply_identity_authority": False,
            "schema_version": WEB_WORKFLOW_CONTROL_SCHEMA_VERSION,
        },
    )


def handle_admitted_workflow_request(
    *,
    state: WorkflowControlState,
    method: str,
    path: str,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Handle a request after the enclosing server has admitted HTTP ingress."""

    if method == "GET":
        if path == "/api/workflow/gate":
            return _gate_packet(state)
        if path == "/api/workflow/history":
            return _history_packet(state)
        if path == "/api/workflow/status":
            return _status_packet(state)
        return _bad_request("unknown GET path.", WC_UNKNOWN_PATH)
    if method == "POST":
        if path != "/api/workflow/run":
            return _bad_request("unknown POST path.", WC_UNKNOWN_PATH)
        if not isinstance(payload, Mapping):
            return _bad_request("payload must be an object.", WC_SCHEMA_INVALID)
        return _run_packet(state, payload)
    return _bad_request("method not supported.", WC_UNKNOWN_PATH)


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
    """Standalone ingress adapter retained for non-live-server callers."""

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
        payload, error = _parse_json_object(body or b"")
        if error is not None:
            return error
        return handle_admitted_workflow_request(
            state=state,
            method=method,
            path=path,
            payload=payload,
        )
    return handle_admitted_workflow_request(state=state, method=method, path=path)


__all__ = [
    "DISPATCH_MODE_CONTROLLED",
    "DISPATCH_MODE_LIVE",
    "STEP_ALLOWED_FIELDS",
    "WorkflowControlState",
    "WorkflowRunHistory",
    "WorkflowWriterLock",
    "handle_admitted_workflow_request",
    "handle_workflow_control_request",
]
