# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Registry-bound production API dispatch for sequential workflows (R63).

The sequential runner owns ordering, context transitions, ambiguity, and repo
leases. This module owns the production dispatch boundary: canonical registry
resolution, exact identity readback, normalized request construction, transport
session policy, and explicit controlled/live evidence separation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import actor_dispatcher
from . import actor_registry
from . import sequential_workflow_runner as workflow
from .api_transport_adapter import ApiTransportAdapter
from .runtime import build_command_payload
from .transport_normalization import NormalizedRequest, TransportError

WORKFLOW_API_DISPATCH_SCHEMA_VERSION = 1

EXECUTION_MODE_CONTROLLED = "controlled"
EXECUTION_MODE_LIVE = "live"
EXECUTION_MODES = frozenset({EXECUTION_MODE_CONTROLLED, EXECUTION_MODE_LIVE})

WAD_OK = "OK"
WAD_LIVE_NOT_AUTHORIZED = "WORKFLOW_LIVE_DISPATCH_NOT_AUTHORIZED"
WAD_MODE_INVALID = "WORKFLOW_EXECUTION_MODE_INVALID"
WAD_REGISTRY_INVALID = "WORKFLOW_ACTOR_REGISTRY_INVALID"
WAD_IDENTITY_DRIFT = "WORKFLOW_DISPATCH_IDENTITY_DRIFT"
WAD_TRANSPORT_NOT_API = "WORKFLOW_TRANSPORT_NOT_API"
WAD_REQUEST_INVALID = "WORKFLOW_NORMALIZED_REQUEST_INVALID"
WAD_PROMPT_OVERSIZED = "WORKFLOW_DISPATCH_PROMPT_OVERSIZED"

MAX_ROLE_INSTRUCTION_CHARS = 8_192
MAX_DISPATCH_PROMPT_CHARS = 65_536


def _error(
    machine_error_code: str,
    message: str,
    *,
    provider: str = "",
) -> dict[str, Any]:
    return {
        "status": "error",
        "machine_error_code": machine_error_code,
        "human_message": message,
        "provider": provider,
        "dispatch_attempted": False,
        "response_observed": False,
        "controlled": None,
        "live_provider_called": False,
        "live_provider_proven": False,
        "context_material_delivered": False,
        "visible_context_sha256": "",
        "fallback_used": False,
        "actor_substitution_used": False,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _compose_prompt(
    step: workflow.WorkflowStep,
    context: workflow.WorkflowDispatchContext,
) -> str:
    role = str(step.role_instruction or "")[:MAX_ROLE_INSTRUCTION_CHARS]
    parts = []
    if role:
        parts.append(
            "DYNAMIC ROLE (non-authoritative; grants no permissions):\n" + role
        )
    if context.visible_context:
        parts.append(
            "VERIFIED PRIOR WORKFLOW CONTEXT "
            f"(source={context.visible_context_source_step}, "
            f"sha256={context.visible_context_sha256}):\n"
            + context.visible_context
        )
    parts.append("CURRENT WORKFLOW TASK:\n" + step.prompt)
    return "\n\n".join(parts)


@dataclass
class RegistryBoundApiWorkflowDispatcher:
    """Callable production seam consumed by ``run_sequential_workflow``."""

    registry_document: Mapping[str, Any]
    adapter: ApiTransportAdapter
    execution_mode: str

    def __call__(
        self,
        step: workflow.WorkflowStep,
        context: workflow.WorkflowDispatchContext,
    ) -> dict[str, Any]:
        alias = str(step.alias or "").strip()
        if not alias:
            return _error(
                WAD_IDENTITY_DRIFT,
                "production workflow step requires a bound alias.",
                provider=step.provider,
            )
        try:
            plan = actor_dispatcher.resolve_alias_dispatch(
                alias=alias,
                registry_document=self.registry_document,
                explicit_operator_grant="context_only",
                adapter_capability="context_only",
                runtime_policy="context_only",
                requested_permission="context_only",
                context_digest=context.incoming_context_digest,
            )
        except actor_dispatcher.DispatchResolutionError as exc:
            return _error(
                exc.machine_error_code,
                "workflow actor resolution failed safely.",
                provider=step.provider,
            )

        if str(plan.get("transport_adapter_id") or "") != actor_registry.API_ADAPTER:
            return _error(
                WAD_TRANSPORT_NOT_API,
                "workflow step is not bound to the API adapter.",
                provider=step.provider,
            )
        expected = {
            "slot_id": step.slot_id,
            "binding_id": step.binding_id,
            "binding_revision": step.binding_revision,
            "assignment_id": step.assignment_id,
            "provider_id": step.provider,
        }
        if any(plan.get(key) != value for key, value in expected.items()):
            return _error(
                WAD_IDENTITY_DRIFT,
                "workflow step identity differs from the canonical binding.",
                provider=step.provider,
            )
        if (
            step.assignment_revision is not None
            and plan.get("assignment_revision") != step.assignment_revision
        ):
            return _error(
                WAD_IDENTITY_DRIFT,
                "workflow assignment revision differs from the canonical binding.",
                provider=step.provider,
            )
        if (
            plan.get("no_fallback") is not True
            or plan.get("cross_provider_fallback") is not False
        ):
            return _error(
                WAD_IDENTITY_DRIFT,
                "workflow dispatch plan does not preserve the no-fallback contract.",
                provider=step.provider,
            )

        prompt = _compose_prompt(step, context)
        if not prompt.strip() or len(prompt) > MAX_DISPATCH_PROMPT_CHARS:
            return _error(
                WAD_PROMPT_OVERSIZED,
                "workflow dispatch prompt is empty or oversized.",
                provider=step.provider,
            )
        idempotency_key = hashlib.sha256(
            (
                f"{context.workflow_run_id}:{step.step_request_id}:"
                f"{context.dispatch_id}:{context.incoming_context_digest}"
            ).encode("utf-8")
        ).hexdigest()
        request = actor_dispatcher.build_dispatch_request(
            dispatch_plan=plan,
            dispatch_id=context.dispatch_id,
            text=prompt,
            idempotency_key=idempotency_key,
            context_digest=context.incoming_context_digest,
        )
        if isinstance(request, TransportError) or not isinstance(
            request, NormalizedRequest
        ):
            return _error(
                WAD_REQUEST_INVALID,
                "normalized workflow request could not be constructed.",
                provider=step.provider,
            )
        try:
            session = self.adapter.prepare_session(
                context_policy=step.context_policy,
                binding_id=step.binding_id,
                context_digest=context.incoming_context_digest,
            )
        except actor_dispatcher.DispatchResolutionError as exc:
            return _error(
                exc.machine_error_code,
                "workflow transport session preparation failed safely.",
                provider=step.provider,
            )

        controlled = self.execution_mode == EXECUTION_MODE_CONTROLLED
        result = self.adapter.dispatch(
            request,
            plan,
            controlled=controlled,
            dispatch_id=context.dispatch_id,
            turn_id=context.turn_id,
            workflow_run_id=context.workflow_run_id,
            step_request_id=step.step_request_id,
            slot_id=step.slot_id,
            binding_id=step.binding_id,
            binding_revision=step.binding_revision,
            assignment_id=step.assignment_id,
            assignment_revision=step.assignment_revision,
            transport_session_id=str(session.get("transport_session_id") or ""),
            text=prompt,
        )
        normalized = dict(result)
        normalized["provider"] = str(
            result.get("provider_id") or plan.get("provider_id") or ""
        )
        normalized["output_text"] = str(result.get("response_text") or "")
        if result.get("ambiguous_delivery") is True or result.get("result") == "ambiguous":
            normalized["status"] = "ambiguous"
        context_delivered = bool(
            result.get("dispatch_proven") is True
            and result.get("response_observed") is True
            and request.text == prompt
        )
        normalized["context_material_delivered"] = context_delivered
        normalized["visible_context_sha256"] = (
            context.visible_context_sha256 if context_delivered else ""
        )
        return normalized


def run_registry_bound_api_workflow(
    steps: Sequence[workflow.WorkflowStep],
    *,
    registry_document: Mapping[str, Any],
    adapter: ApiTransportAdapter,
    execution_mode: str = EXECUTION_MODE_LIVE,
    live_dispatch_authorized: bool = False,
    lease_root: Path | str | None = None,
    workflow_run_id: str | None = None,
) -> dict[str, Any]:
    """Run a workflow through the canonical API transport boundary.

    Authorization is checked before registry resolution, credential presence,
    transport session preparation, or network dispatch.
    """
    if execution_mode not in EXECUTION_MODES:
        return build_command_payload(
            ok=False,
            human_message="workflow execution mode is invalid.",
            machine_error_code=WAD_MODE_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"schema_version": WORKFLOW_API_DISPATCH_SCHEMA_VERSION},
        )
    if execution_mode == EXECUTION_MODE_LIVE and live_dispatch_authorized is not True:
        return build_command_payload(
            ok=False,
            human_message="live workflow dispatch requires explicit authorization.",
            machine_error_code=WAD_LIVE_NOT_AUTHORIZED,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={
                "schema_version": WORKFLOW_API_DISPATCH_SCHEMA_VERSION,
                "dispatch_attempted": False,
                "credential_probe_performed": False,
                "live_provider_called": False,
            },
        )
    validation = actor_registry.validate_actor_registry_document(registry_document)
    if validation.get("valid") is not True:
        return build_command_payload(
            ok=False,
            human_message="actor registry is invalid.",
            machine_error_code=WAD_REGISTRY_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={
                "schema_version": WORKFLOW_API_DISPATCH_SCHEMA_VERSION,
                "dispatch_attempted": False,
                "live_provider_called": False,
            },
        )
    dispatcher = RegistryBoundApiWorkflowDispatcher(
        registry_document=registry_document,
        adapter=adapter,
        execution_mode=execution_mode,
    )
    packet = workflow.run_sequential_workflow(
        steps,
        dispatch_with_context=dispatcher,
        lease_root=lease_root,
        workflow_run_id=workflow_run_id,
    )
    packet["execution_mode"] = execution_mode
    packet["controlled"] = execution_mode == EXECUTION_MODE_CONTROLLED
    packet["live_dispatch_authorized"] = live_dispatch_authorized is True
    packet["live_provider_proven"] = bool(
        packet.get("status") == "ok"
        and packet.get("receipts")
        and all(r.get("live_provider_proven") is True for r in packet["receipts"])
    )
    packet["schema_version"] = WORKFLOW_API_DISPATCH_SCHEMA_VERSION
    return packet


__all__ = [
    "EXECUTION_MODE_CONTROLLED",
    "EXECUTION_MODE_LIVE",
    "RegistryBoundApiWorkflowDispatcher",
    "WAD_IDENTITY_DRIFT",
    "WAD_LIVE_NOT_AUTHORIZED",
    "WAD_MODE_INVALID",
    "WAD_REGISTRY_INVALID",
    "WAD_TRANSPORT_NOT_API",
    "run_registry_bound_api_workflow",
]
