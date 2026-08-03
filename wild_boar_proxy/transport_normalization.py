# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Normalized transport boundary (B03).

Implements the plan's transport model: ``native_primary``, ``api``,
``cli_one_shot``, and ``cli_acp`` adapters all normalize the same surface:

- request envelope
- stream events
- final response
- tool-call events
- typed errors
- ambiguity and cancellation
- capability negotiation
- dispatch receipts

``native_primary`` is a special host boundary, NOT an ordinary callable
``transport.send()`` adapter: this module never synthesizes a native primary
dispatch.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from typing import Any

NATIVE_PRIMARY = "native_primary"
API = "api"
CLI_ONE_SHOT = "cli_one_shot"
CLI_ACP = "cli_acp"
TRANSPORT_KINDS = (NATIVE_PRIMARY, API, CLI_ONE_SHOT, CLI_ACP)

EVENT_DELTA = "delta"
EVENT_TOOL_CALL = "tool_call"
EVENT_ERROR = "error"
EVENT_DONE = "done"
STREAM_EVENT_TYPES = (EVENT_DELTA, EVENT_TOOL_CALL, EVENT_ERROR, EVENT_DONE)

# Typed error taxonomy (aligned with the control-layer DeepSeek taxonomy and
# the plan's normalized-error requirement).
ERR_NETWORK_FAILED = "network_failed"
ERR_INVALID_CREDENTIAL = "invalid_credential"
ERR_QUOTA_EXHAUSTED = "quota_exhausted"
ERR_MODEL_NOT_AVAILABLE = "model_not_available"
ERR_INVALID_UPSTREAM_RESPONSE = "invalid_upstream_response"
ERR_STREAM_INCOMPLETE = "stream_incomplete"
ERR_TOOL_UNSUPPORTED = "tool_unsupported"
ERR_AMBIGUOUS_DELIVERY = "ambiguous_delivery"
ERR_CANCELLED = "cancelled"
ERR_TIMEOUT = "timeout"
ERR_CAPABILITY_NOT_ADMITTED = "capability_not_admitted"
TYPED_ERROR_CODES = (
    ERR_NETWORK_FAILED,
    ERR_INVALID_CREDENTIAL,
    ERR_QUOTA_EXHAUSTED,
    ERR_MODEL_NOT_AVAILABLE,
    ERR_INVALID_UPSTREAM_RESPONSE,
    ERR_STREAM_INCOMPLETE,
    ERR_TOOL_UNSUPPORTED,
    ERR_AMBIGUOUS_DELIVERY,
    ERR_CANCELLED,
    ERR_TIMEOUT,
    ERR_CAPABILITY_NOT_ADMITTED,
)

# Ambiguous-delivery errors are NEVER retried and NEVER replaced by another
# actor's response.
AMBIGUOUS_ERROR_CODES = {ERR_AMBIGUOUS_DELIVERY}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclasses.dataclass(frozen=True)
class NormalizedRequest:
    """Canonical request envelope accepted by every external adapter."""

    dispatch_id: str
    transport_kind: str
    provider_id: str
    model_id: str
    text: str
    idempotency_key: str
    context_digest: str
    requested_permission: str
    effective_permission: str
    capability_ids: tuple[str, ...] = ()
    stream: bool = False

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class NormalizedStreamEvent:
    """One normalized stream event from an external adapter."""

    event_type: str
    dispatch_id: str
    sequence: int
    text_delta: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    tool_arguments: str = ""
    error_code: str = ""
    error_message: str = ""
    finish_reason: str = ""


@dataclasses.dataclass(frozen=True)
class NormalizedToolCall:
    tool_call_id: str
    name: str
    arguments: str


@dataclasses.dataclass(frozen=True)
class NormalizedFinalResponse:
    """Canonical final response from an external adapter."""

    dispatch_id: str
    transport_kind: str
    provider_id: str
    model_id: str
    text: str
    tool_calls: tuple[NormalizedToolCall, ...] = ()
    finish_reason: str = ""
    usage: dict[str, int] = dataclasses.field(default_factory=dict)
    observed_at_utc: str = ""


@dataclasses.dataclass(frozen=True)
class TransportError:
    """Typed transport error. Never contains credentials or raw secrets."""

    code: str
    message: str
    retryable: bool = False
    ambiguous: bool = False

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclasses.dataclass(frozen=True)
class DispatchReceipt:
    """Secret-free dispatch receipt bound to exact identities."""

    dispatch_id: str
    turn_id: str
    workflow_run_id: str
    step_request_id: str
    slot_id: str
    binding_id: str
    binding_revision: int
    assignment_id: str
    assignment_revision: int
    transport_session_id: str
    context_digest: str
    provider_id: str
    model_id: str
    route_id: str
    request_id: str
    result: str  # ok | error | ambiguous
    error_code: str = ""
    evidence_level: str = ""
    response_observed: bool = False
    observed_at_utc: str = ""

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def normalize_request(raw: Any) -> NormalizedRequest | TransportError:
    """Normalize a raw request envelope; fail closed on malformed input."""
    if not isinstance(raw, dict):
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "request envelope must be an object")
    dispatch_id = str(raw.get("dispatch_id") or "")
    transport_kind = str(raw.get("transport_kind") or "")
    provider_id = str(raw.get("provider_id") or "")
    model_id = str(raw.get("model_id") or "")
    text = raw.get("text")
    idempotency_key = str(raw.get("idempotency_key") or "")
    context_digest = str(raw.get("context_digest") or "")
    requested_permission = str(raw.get("requested_permission") or "")
    effective_permission = str(raw.get("effective_permission") or "")
    if not dispatch_id or not transport_kind:
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "dispatch_id and transport_kind required")
    if transport_kind not in TRANSPORT_KINDS:
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, f"unknown transport kind {transport_kind}")
    if not isinstance(text, str) or not text.strip():
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "text must be a non-empty string")
    if not idempotency_key or not context_digest:
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "idempotency_key and context_digest required")
    if not effective_permission:
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "effective_permission required")
    capability_ids = tuple(str(c) for c in raw.get("capability_ids") or [])
    return NormalizedRequest(
        dispatch_id=dispatch_id,
        transport_kind=transport_kind,
        provider_id=provider_id,
        model_id=model_id,
        text=text,
        idempotency_key=idempotency_key,
        context_digest=context_digest,
        requested_permission=requested_permission,
        effective_permission=effective_permission,
        capability_ids=capability_ids,
        stream=raw.get("stream") is True,
    )


def normalize_stream_event(raw: Any, *, dispatch_id: str, sequence: int) -> NormalizedStreamEvent | TransportError:
    """Normalize one raw stream event."""
    if not isinstance(raw, dict):
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "stream event must be an object")
    event_type = str(raw.get("event_type") or "")
    if event_type not in STREAM_EVENT_TYPES:
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, f"unknown stream event type {event_type}")
    return NormalizedStreamEvent(
        event_type=event_type,
        dispatch_id=dispatch_id,
        sequence=sequence,
        text_delta=str(raw.get("text_delta") or ""),
        tool_call_id=str(raw.get("tool_call_id") or ""),
        tool_name=str(raw.get("tool_name") or ""),
        tool_arguments=str(raw.get("tool_arguments") or ""),
        error_code=str(raw.get("error_code") or ""),
        error_message=str(raw.get("error_message") or ""),
        finish_reason=str(raw.get("finish_reason") or ""),
    )


def normalize_final_response(
    raw: Any,
    *,
    dispatch_id: str,
    transport_kind: str,
    provider_id: str,
    model_id: str,
) -> NormalizedFinalResponse | TransportError:
    """Normalize a raw final response; credentials are structurally absent."""
    if not isinstance(raw, dict):
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "final response must be an object")
    text = raw.get("text")
    if not isinstance(text, str):
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "final response text must be a string")
    tool_calls: list[NormalizedToolCall] = []
    for tool in raw.get("tool_calls") or []:
        if not isinstance(tool, dict):
            return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "tool call must be an object")
        tool_calls.append(
            NormalizedToolCall(
                tool_call_id=str(tool.get("tool_call_id") or ""),
                name=str(tool.get("name") or ""),
                arguments=str(tool.get("arguments") or ""),
            )
        )
    usage = raw.get("usage")
    if usage is not None and not isinstance(usage, dict):
        return TransportError(ERR_INVALID_UPSTREAM_RESPONSE, "usage must be an object")
    return NormalizedFinalResponse(
        dispatch_id=dispatch_id,
        transport_kind=transport_kind,
        provider_id=provider_id,
        model_id=model_id,
        text=text,
        tool_calls=tuple(tool_calls),
        finish_reason=str(raw.get("finish_reason") or ""),
        usage={str(k): int(v) for k, v in (usage or {}).items() if isinstance(v, int)},
        observed_at_utc=utc_now(),
    )


def classify_dispatch_result(
    *,
    response_observed: bool,
    error_code: str,
) -> str:
    """Classify a dispatch result: ok | error | ambiguous.

    A possibly-delivered request is never ``ok`` and never retried.
    """
    if response_observed:
        return "ok"
    if error_code in AMBIGUOUS_ERROR_CODES:
        return "ambiguous"
    return "error"


__all__ = [
    "NATIVE_PRIMARY",
    "API",
    "CLI_ONE_SHOT",
    "CLI_ACP",
    "TRANSPORT_KINDS",
    "STREAM_EVENT_TYPES",
    "TYPED_ERROR_CODES",
    "AMBIGUOUS_ERROR_CODES",
    "NormalizedRequest",
    "NormalizedStreamEvent",
    "NormalizedToolCall",
    "NormalizedFinalResponse",
    "TransportError",
    "DispatchReceipt",
    "normalize_request",
    "normalize_stream_event",
    "normalize_final_response",
    "classify_dispatch_result",
]
