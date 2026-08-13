# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Sequential workflow runner (B13).

User-defined sequential steps, each with independent request/dispatch IDs,
dynamic role instructions, executable `continue`/`fresh`/`fork` context
policies with digest transitions, exactly one repo-touching lease at a
time, fail-fast ambiguity, persisted intermediate receipts, no silent actor
swap, and proven visible delivery. Workflow V1 has no parallel repo steps;
automated native-primary workflow steps remain disabled until physically
proven. R63 adds a production dispatch seam whose input contains bounded
visible context and whose output must prove delivery of that exact context.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .repo_lease import RepoLease
from .runtime import build_command_payload
from .thread_context_ledger import redact_text

WORKFLOW_RUNNER_SCHEMA_VERSION = 1

CONTEXT_POLICY_CONTINUE = "continue"
CONTEXT_POLICY_FRESH = "fresh"
CONTEXT_POLICY_FORK = "fork"
CONTEXT_POLICIES = (CONTEXT_POLICY_CONTINUE, CONTEXT_POLICY_FRESH, CONTEXT_POLICY_FORK)

WF_OK = "OK"
WF_SCHEMA_INVALID = "WORKFLOW_SCHEMA_INVALID"
WF_AMBIGUOUS_STOP = "WORKFLOW_AMBIGUOUS_STOP"
WF_ACTOR_SWAP_VIOLATION = "WORKFLOW_ACTOR_SWAP_VIOLATION"
WF_REPO_LEASE_BLOCKED = "WORKFLOW_REPO_LEASE_BLOCKED"
WF_REPO_LEASE_RELEASE_FAILED = "WORKFLOW_REPO_LEASE_RELEASE_FAILED"
WF_DISPATCH_FAILED = "WORKFLOW_DISPATCH_FAILED"
WF_DISPATCH_EXCEPTION = "WORKFLOW_DISPATCH_EXCEPTION"
WF_FORK_TARGET_UNKNOWN = "WORKFLOW_FORK_TARGET_UNKNOWN"
WF_CONTEXT_DELIVERY_UNPROVEN = "WORKFLOW_CONTEXT_DELIVERY_UNPROVEN"

MAX_WORKFLOW_OUTPUT_CHARS = 32_768
MAX_VISIBLE_CONTEXT_CHARS = 49_152


def _digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkflowStep:
    """One sequential step in a workflow run.

    `role_instruction` is dynamic and non-authoritative: it never grants
    permission. `context_policy` selects the digest transition.
    """

    step_request_id: str
    slot_id: str
    binding_id: str
    binding_revision: int
    assignment_id: str
    provider: str
    prompt: str
    role_instruction: str = ""
    context_policy: str = CONTEXT_POLICY_FRESH
    fork_from: str = ""
    repo_touching: bool = False
    alias: str = ""
    assignment_revision: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_request_id": self.step_request_id,
            "slot_id": self.slot_id,
            "binding_id": self.binding_id,
            "binding_revision": self.binding_revision,
            "assignment_id": self.assignment_id,
            "provider": self.provider,
            "prompt": self.prompt,
            "role_instruction": self.role_instruction,
            "context_policy": self.context_policy,
            "fork_from": self.fork_from,
            "repo_touching": self.repo_touching,
            "alias": self.alias,
            "assignment_revision": self.assignment_revision,
        }


@dataclass(frozen=True)
class WorkflowDispatchContext:
    """Server-owned per-step facts supplied to a production dispatcher."""

    workflow_run_id: str
    dispatch_id: str
    turn_id: str
    incoming_context_digest: str
    visible_context: str
    visible_context_sha256: str
    visible_context_source_step: str


@dataclass
class WorkflowRun:
    """Accumulated run state: ordered step receipts + stop reason."""

    workflow_run_id: str
    receipts: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str | None = None
    stopped_at_step: str | None = None
    lease_fencing_token: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "workflow_run_id": self.workflow_run_id,
            "dispatched_steps": len(self.receipts),
            "stop_reason": self.stop_reason,
            "stopped_at_step": self.stopped_at_step,
            "receipts": self.receipts,
        }


# Dispatch callable: step + incoming context digest -> result dict with
# status ("ok" | "ambiguous" | "error"), provider, output_text,
# machine_error_code.
DispatchCallable = Callable[[WorkflowStep, str], dict[str, Any]]
ContextDispatchCallable = Callable[
    [WorkflowStep, WorkflowDispatchContext], dict[str, Any]
]


class WorkflowAmbiguityError(RuntimeError):
    """Raised by the dispatch seam on an ambiguous result."""


def _bounded_redacted(value: object, *, limit: int) -> str:
    return redact_text(str(value or ""))[:limit]


def _validate_steps(steps: Sequence[WorkflowStep]) -> dict[str, Any] | None:
    if not steps:
        return build_command_payload(
            ok=False,
            human_message="workflow requires at least one step.",
            machine_error_code=WF_SCHEMA_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"schema_version": WORKFLOW_RUNNER_SCHEMA_VERSION},
        )
    seen: set[str] = set()
    for step in steps:
        step_id = str(step.step_request_id or "").strip()
        if not step_id:
            return build_command_payload(
                ok=False,
                human_message="step_request_id must be non-empty.",
                machine_error_code=WF_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"schema_version": WORKFLOW_RUNNER_SCHEMA_VERSION},
            )
        if step_id in seen:
            return build_command_payload(
                ok=False,
                human_message=f"duplicate step_request_id '{step_id}'.",
                machine_error_code=WF_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"step_request_id": step_id},
            )
        seen.add(step_id)
        if step.context_policy not in CONTEXT_POLICIES:
            return build_command_payload(
                ok=False,
                human_message=f"unknown context policy '{step.context_policy}'.",
                machine_error_code=WF_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"step_request_id": step_id},
            )
        if step.context_policy == CONTEXT_POLICY_FORK and not step.fork_from:
            return build_command_payload(
                ok=False,
                human_message=f"fork step '{step_id}' needs fork_from.",
                machine_error_code=WF_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"step_request_id": step_id},
            )
        if not str(step.provider or "").strip():
            return build_command_payload(
                ok=False,
                human_message=f"step '{step_id}' needs a provider.",
                machine_error_code=WF_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"step_request_id": step_id},
            )
        if not str(step.prompt or "").strip() or len(step.prompt) > MAX_VISIBLE_CONTEXT_CHARS:
            return build_command_payload(
                ok=False,
                human_message=f"step '{step_id}' prompt is empty or oversized.",
                machine_error_code=WF_SCHEMA_INVALID,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={"step_request_id": step_id},
            )
    return None


def _context_for(
    step: WorkflowStep,
    *,
    previous_digest: str | None,
    previous_material: str,
    previous_step_id: str,
    digest_by_step: dict[str, str],
    material_by_step: dict[str, str],
    run: WorkflowRun,
) -> tuple[str | None, str, str, dict[str, Any] | None]:
    """Compute digest, visible material, and source for a step's policy.

    Returns (incoming_digest, visible_material, source_step, error_packet).
    """
    if step.context_policy == CONTEXT_POLICY_FRESH:
        return _digest(f"fresh:{step.step_request_id}:{step.prompt}"), "", "", None
    if step.context_policy == CONTEXT_POLICY_CONTINUE:
        if previous_digest is None:
            return _digest(f"fresh:{step.step_request_id}:{step.prompt}"), "", "", None
        return previous_digest, previous_material, previous_step_id, None
    if step.context_policy == CONTEXT_POLICY_FORK:
        source_digest = digest_by_step.get(step.fork_from)
        if source_digest is None:
            return None, "", "", build_command_payload(
                ok=False,
                human_message=(
                    f"fork target '{step.fork_from}' has no completed receipt."
                ),
                machine_error_code=WF_FORK_TARGET_UNKNOWN,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "step_request_id": step.step_request_id,
                    "fork_from": step.fork_from,
                    "workflow_run_id": run.workflow_run_id,
                },
            )
        return source_digest, material_by_step[step.fork_from], step.fork_from, None
    return None, "", "", None


def run_sequential_workflow(
    steps: Sequence[WorkflowStep],
    *,
    dispatch: DispatchCallable | None = None,
    dispatch_with_context: ContextDispatchCallable | None = None,
    lease_root: Path | str | None = None,
    workflow_run_id: str | None = None,
) -> dict[str, Any]:
    """Execute the sequential workflow.

    - validates the step plan (unique ids, valid policies, fork targets)
    - executes steps in order, persisting each receipt before the next step
    - fails fast on ambiguity (never substitutes an actor)
    - hard-fails on provider mismatch (no silent actor swap)
    - holds at most one repo lease; external holders block repo steps
    - releases the run's repo lease on completion (or failure)
    """
    if (dispatch is None) == (dispatch_with_context is None):
        return build_command_payload(
            ok=False,
            human_message="workflow requires exactly one dispatch seam.",
            machine_error_code=WF_SCHEMA_INVALID,
            liveness="healthy",
            severity="error",
            operator_action="user_action",
            changed_files=[],
            exit_code=1,
            extra={"schema_version": WORKFLOW_RUNNER_SCHEMA_VERSION},
        )
    validation = _validate_steps(steps)
    if validation is not None:
        return validation

    run = WorkflowRun(workflow_run_id=workflow_run_id or uuid.uuid4().hex)
    digest_by_step: dict[str, str] = {}
    material_by_step: dict[str, str] = {}
    previous_digest: str | None = None
    previous_material = ""
    previous_step_id = ""
    lease: RepoLease | None = None
    terminal_packet: dict[str, Any] | None = None

    def ensure_lease() -> dict[str, Any] | None:
        nonlocal lease
        if lease is not None:
            return None
        lease = RepoLease(lease_root or Path("/tmp/wbp-workflow-lease"))
        acquired = lease.acquire(
            holder=f"workflow:{run.workflow_run_id}",
            operation="sequential_workflow_repo_step",
            worktree="workflow-v1",
        )
        if acquired["status"] != "ok":
            return build_command_payload(
                ok=False,
                human_message="repo lease is held by another holder.",
                machine_error_code=WF_REPO_LEASE_BLOCKED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "workflow_run_id": run.workflow_run_id,
                    "lease": acquired.get("existing"),
                },
            )
        run.lease_fencing_token = acquired.get("fencing_token")
        return None

    def release_lease() -> dict[str, Any] | None:
        nonlocal lease
        if lease is None or run.lease_fencing_token is None:
            return None
        released = lease.release(fencing_token=run.lease_fencing_token)
        if released["status"] != "ok":
            return build_command_payload(
                ok=False,
                human_message="repo lease release failed.",
                machine_error_code=WF_REPO_LEASE_RELEASE_FAILED,
                liveness="healthy",
                severity="error",
                operator_action="user_action",
                changed_files=[],
                exit_code=1,
                extra={
                    "workflow_run_id": run.workflow_run_id,
                    "lease_result": released,
                },
            )
        lease = None
        return None

    def base_receipt(
        step: WorkflowStep,
        context: WorkflowDispatchContext,
    ) -> dict[str, Any]:
        return {
            "dispatch_id": context.dispatch_id,
            "turn_id": context.turn_id,
            "workflow_run_id": run.workflow_run_id,
            "step_request_id": step.step_request_id,
            "slot_id": step.slot_id,
            "binding_id": step.binding_id,
            "binding_revision": step.binding_revision,
            "assignment_id": step.assignment_id,
            "assignment_revision": step.assignment_revision,
            "provider": step.provider,
            "role_instruction": step.role_instruction,
            "context_policy": step.context_policy,
            "incoming_context_digest": context.incoming_context_digest,
            "visible_context_present": bool(context.visible_context),
            "visible_context_sha256": context.visible_context_sha256,
            "visible_context_source_step": context.visible_context_source_step,
        }

    def result_proof_fields(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "dispatch_attempted": result.get("dispatch_attempted") is True,
            "response_observed": result.get("response_observed") is True,
            "controlled": result.get("controlled"),
            "live_provider_called": result.get("live_provider_called") is True,
            "live_provider_proven": result.get("live_provider_proven") is True,
            "fallback_used": result.get("fallback_used") is True,
            "actor_substitution_used": result.get("actor_substitution_used") is True,
        }

    for step in steps:
        incoming_digest, visible_context, context_source, error = _context_for(
            step,
            previous_digest=previous_digest,
            previous_material=previous_material,
            previous_step_id=previous_step_id,
            digest_by_step=digest_by_step,
            material_by_step=material_by_step,
            run=run,
        )
        if error is not None:
            error["intermediate_receipts"] = run.receipts
            terminal_packet = error
            break

        if step.repo_touching:
            blocked = ensure_lease()
            if blocked is not None:
                blocked["intermediate_receipts"] = run.receipts
                blocked["stop_reason"] = WF_REPO_LEASE_BLOCKED
                blocked["stopped_at_step"] = step.step_request_id
                run.stop_reason = WF_REPO_LEASE_BLOCKED
                run.stopped_at_step = step.step_request_id
                terminal_packet = blocked
                break

        dispatch_id = uuid.uuid4().hex
        turn_id = uuid.uuid4().hex
        context = WorkflowDispatchContext(
            workflow_run_id=run.workflow_run_id,
            dispatch_id=dispatch_id,
            turn_id=turn_id,
            incoming_context_digest=str(incoming_digest or ""),
            visible_context=visible_context,
            visible_context_sha256=_digest(visible_context) if visible_context else "",
            visible_context_source_step=context_source,
        )
        try:
            result = (
                dispatch_with_context(step, context)
                if dispatch_with_context is not None
                else dispatch(step, context.incoming_context_digest)  # type: ignore[misc]
            )
        except WorkflowAmbiguityError as exc:
            run.stop_reason = WF_AMBIGUOUS_STOP
            run.stopped_at_step = step.step_request_id
            receipt = {
                **base_receipt(step, context),
                "status": "ambiguous",
                "machine_error_code": WF_AMBIGUOUS_STOP,
                "reason": _bounded_redacted(exc, limit=512),
                "delivered": False,
            }
            run.receipts.append(receipt)
            break
        except Exception:  # noqa: BLE001 - callback internals must not escape
            run.stop_reason = WF_DISPATCH_EXCEPTION
            run.stopped_at_step = step.step_request_id
            run.receipts.append(
                {
                    **base_receipt(step, context),
                    "status": "error",
                    "machine_error_code": WF_DISPATCH_EXCEPTION,
                    "reason": "workflow dispatch raised unexpectedly",
                    "delivered": False,
                    "dispatch_attempted": False,
                    "response_observed": False,
                    "live_provider_called": False,
                    "live_provider_proven": False,
                    "fallback_used": False,
                    "actor_substitution_used": False,
                }
            )
            break

        if not isinstance(result, dict):
            run.stop_reason = WF_DISPATCH_FAILED
            run.stopped_at_step = step.step_request_id
            run.receipts.append(
                {
                    **base_receipt(step, context),
                    "status": "error",
                    "machine_error_code": WF_DISPATCH_FAILED,
                    "reason": "workflow dispatch returned an invalid result",
                    "delivered": False,
                    "dispatch_attempted": False,
                    "response_observed": False,
                    "live_provider_called": False,
                    "live_provider_proven": False,
                    "fallback_used": False,
                    "actor_substitution_used": False,
                }
            )
            break

        result_status = str(result.get("status") or "error")
        result_provider = str(
            result.get("provider") or result.get("provider_id") or ""
        ).strip()
        if result_provider != step.provider:
            run.stop_reason = WF_ACTOR_SWAP_VIOLATION
            run.stopped_at_step = step.step_request_id
            receipt = {
                **base_receipt(step, context),
                **result_proof_fields(result),
                "status": "error",
                "machine_error_code": WF_ACTOR_SWAP_VIOLATION,
                "reason": (
                    f"dispatch returned provider '{result_provider}' "
                    f"but the step binds '{step.provider}'"
                ),
                "delivered": False,
            }
            run.receipts.append(receipt)
            break

        if result_status == "ambiguous":
            run.stop_reason = WF_AMBIGUOUS_STOP
            run.stopped_at_step = step.step_request_id
            receipt = {
                **base_receipt(step, context),
                **result_proof_fields(result),
                "status": "ambiguous",
                "machine_error_code": result.get("machine_error_code") or WF_AMBIGUOUS_STOP,
                "reason": _bounded_redacted(
                    result.get("human_message", "ambiguous dispatch result"),
                    limit=512,
                ),
                "delivered": False,
            }
            run.receipts.append(receipt)
            break

        if result_status != "ok":
            run.stop_reason = WF_DISPATCH_FAILED
            run.stopped_at_step = step.step_request_id
            receipt = {
                **base_receipt(step, context),
                **result_proof_fields(result),
                "status": "error",
                "machine_error_code": result.get("machine_error_code") or WF_DISPATCH_FAILED,
                "reason": _bounded_redacted(
                    result.get("human_message", "dispatch failed"), limit=512
                ),
                "delivered": False,
            }
            run.receipts.append(receipt)
            break

        if visible_context and dispatch_with_context is not None:
            proof_digest = str(result.get("visible_context_sha256") or "")
            if (
                result.get("context_material_delivered") is not True
                or proof_digest != context.visible_context_sha256
            ):
                run.stop_reason = WF_CONTEXT_DELIVERY_UNPROVEN
                run.stopped_at_step = step.step_request_id
                run.receipts.append(
                    {
                        **base_receipt(step, context),
                        **result_proof_fields(result),
                        "status": "error",
                        "machine_error_code": WF_CONTEXT_DELIVERY_UNPROVEN,
                        "reason": "dispatch did not prove the exact visible context",
                        "delivered": False,
                    }
                )
                break

        output_text = _bounded_redacted(
            result.get("output_text", result.get("response_text", "")),
            limit=MAX_WORKFLOW_OUTPUT_CHARS,
        )
        material = _bounded_redacted(
            (
                f"{visible_context}\n\n" if visible_context else ""
            )
            + f"Step {step.step_request_id} task:\n{step.prompt}\n\n"
            + f"Step {step.step_request_id} response:\n{output_text}",
            limit=MAX_VISIBLE_CONTEXT_CHARS,
        )
        out_digest = _digest(material)
        digest_by_step[step.step_request_id] = out_digest
        material_by_step[step.step_request_id] = material
        previous_digest = out_digest
        previous_material = material
        previous_step_id = step.step_request_id
        run.receipts.append(
            {
                **base_receipt(step, context),
                **result_proof_fields(result),
                "outgoing_context_digest": out_digest,
                "status": "ok",
                "machine_error_code": result.get("machine_error_code") or WF_OK,
                "output_text": output_text,
                "delivered": True,
                "context_material_delivered": (
                    result.get("context_material_delivered") is True
                    if visible_context
                    else True
                ),
            }
        )

    release_error = release_lease()
    if terminal_packet is not None:
        if release_error is not None:
            release_error["intermediate_receipts"] = run.receipts
            release_error["prior_machine_error_code"] = terminal_packet.get(
                "machine_error_code"
            )
            return release_error
        return terminal_packet
    ok = run.stop_reason is None
    final_ok = ok and release_error is None
    failure_message = (
        f"sequential workflow stopped: {run.stop_reason}"
        if run.stop_reason is not None
        else release_error.get("human_message", "lease release failure")
        if release_error is not None
        else ""
    )
    failure_code = (
        release_error.get("machine_error_code", run.stop_reason or WF_DISPATCH_FAILED)
        if release_error is not None
        else run.stop_reason or WF_DISPATCH_FAILED
    )
    return build_command_payload(
        ok=final_ok,
        human_message=(
            "sequential workflow completed with all steps delivered."
            if final_ok
            else failure_message
        ),
        machine_error_code=WF_OK if final_ok else failure_code,
        liveness="healthy",
        severity="info" if final_ok else "error",
        operator_action="none" if final_ok else "user_action",
        changed_files=[],
        exit_code=0 if final_ok else 1,
        extra={
            "schema_version": WORKFLOW_RUNNER_SCHEMA_VERSION,
            "workflow_run_id": run.workflow_run_id,
            "dispatched_steps": len(run.receipts),
            "all_steps_delivered": final_ok,
            "stop_reason": run.stop_reason,
            "stopped_at_step": run.stopped_at_step,
            "receipts": run.receipts,
            "visible_delivery": all(
                r.get("delivered") for r in run.receipts if r["status"] == "ok"
            ) and final_ok,
        },
    )


__all__ = [
    "CONTEXT_POLICIES",
    "CONTEXT_POLICY_CONTINUE",
    "CONTEXT_POLICY_FORK",
    "CONTEXT_POLICY_FRESH",
    "ContextDispatchCallable",
    "DispatchCallable",
    "MAX_VISIBLE_CONTEXT_CHARS",
    "MAX_WORKFLOW_OUTPUT_CHARS",
    "WorkflowAmbiguityError",
    "WorkflowDispatchContext",
    "WorkflowRun",
    "WorkflowStep",
    "run_sequential_workflow",
]
