# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Provider-specific request/response transforms for Kimi and GLM (P02+P03).

Each provider has its own reasoning dialect, streaming delta accumulator,
tool-call accumulator, and error normalization. These transforms sit between
the generic OpenAI-compatible request shape and the provider-specific wire
format.

Kimi reasoning dialects:
  - K3: top-level reasoning_effort=low|high|max
  - K2.6: thinking.type=enabled|disabled
  - K2.5/K2.7-code: always-thinking (provider-fixed)

GLM reasoning dialects:
  - thinking.type=enabled|disabled
  - clear_thinking=false preserves reasoning_content across tool calls
  - interleaved thinking via delta.reasoning_content accumulation
"""

from __future__ import annotations

import dataclasses
from typing import Any, Sequence

from . import errors

PROVIDER_KIMI = "kimi"
PROVIDER_GLM = "glm"

# Reasoning dialect identifiers
DIALECT_KIMI_REASONING_EFFORT = "kimi_reasoning_effort"
DIALECT_KIMI_THINKING = "kimi_thinking"
DIALECT_KLM_FIXED = "provider_fixed_reasoning"
DIALECT_GLM_THINKING = "glm_thinking"


@dataclasses.dataclass(frozen=True)
class ProviderErrorClassification:
    """Normalized provider error from an HTTP response."""

    error_class: str  # auth_failed | quota_exhausted | model_not_found | network | invalid_response | ok
    machine_error_code: str
    http_status: int | None
    retryable: bool


@dataclasses.dataclass
class StreamingDeltaAccumulator:
    """Accumulates streaming SSE deltas into a complete response.

    Handles both content deltas and reasoning_content deltas (GLM/Kimi).
    """

    content_parts: list[str] = dataclasses.field(default_factory=list)
    reasoning_parts: list[str] = dataclasses.field(default_factory=list)
    tool_call_args: dict[int, str] = dataclasses.field(default_factory=dict)
    tool_call_names: dict[int, str] = dataclasses.field(default_factory=dict)
    finish_reason: str | None = None
    model_observed: str | None = None
    delta_count: int = 0

    def feed_delta(self, delta: dict[str, Any]) -> None:
        """Feed one SSE delta object from a streaming response."""
        self.delta_count += 1
        if isinstance(delta.get("content"), str):
            self.content_parts.append(delta["content"])
        if isinstance(delta.get("reasoning_content"), str):
            self.reasoning_parts.append(delta["reasoning_content"])
        # Tool call accumulation
        for tc in delta.get("tool_calls", []) or []:
            idx = tc.get("index", 0)
            if isinstance(idx, int):
                fn = tc.get("function", {})
                if isinstance(fn.get("name"), str):
                    self.tool_call_names[idx] = fn["name"]
                if isinstance(fn.get("arguments"), str):
                    self.tool_call_args[idx] = self.tool_call_args.get(idx, "") + fn["arguments"]

    def feed_chunk(self, chunk: dict[str, Any]) -> None:
        """Feed one parsed SSE chunk (with 'choices' array)."""
        for choice in chunk.get("choices", []) or []:
            delta = choice.get("delta", {})
            if isinstance(delta, dict):
                self.feed_delta(delta)
            if isinstance(choice.get("finish_reason"), str):
                self.finish_reason = choice["finish_reason"]
        if isinstance(chunk.get("model"), str):
            self.model_observed = chunk["model"]

    @property
    def assembled_content(self) -> str:
        return "".join(self.content_parts)

    @property
    def assembled_reasoning(self) -> str:
        return "".join(self.reasoning_parts)

    @property
    def assembled_tool_calls(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for idx in sorted(self.tool_call_names.keys() | self.tool_call_args.keys()):
            result.append({
                "id": f"call_{idx}",
                "type": "function",
                "function": {
                    "name": self.tool_call_names.get(idx, ""),
                    "arguments": self.tool_call_args.get(idx, ""),
                },
            })
        return result

    @property
    def stream_complete(self) -> bool:
        return self.finish_reason is not None and self.finish_reason != "null"


def apply_kimi_thinking(
    payload: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str | None = None,
    thinking_enabled: bool | None = None,
) -> dict[str, Any]:
    """Apply Kimi reasoning dialect to a chat completions payload.

    - K3 (reasoning_effort in model name or explicit): top-level reasoning_effort
    - K2.6 (thinking.type): thinking object with type enabled/disabled
    - Others: provider-fixed, no parameter added
    """
    result = dict(payload)
    model_lower = model.lower()

    if reasoning_effort is not None:
        # K3 dialect: top-level reasoning_effort
        result["reasoning_effort"] = reasoning_effort
    elif thinking_enabled is not None and "k2.6" in model_lower:
        # K2.6 dialect: thinking.type
        result["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}
    # K2.5/K2.7-code: always thinking, no parameter needed

    return result


def apply_glm_thinking(
    payload: dict[str, Any],
    *,
    thinking_enabled: bool = False,
    clear_thinking: bool = False,
) -> dict[str, Any]:
    """Apply GLM reasoning dialect to a chat completions payload.

    - thinking.type=enabled|disabled
    - clear_thinking=false preserves reasoning_content in tool loops
    """
    result = dict(payload)
    result["thinking"] = {
        "type": "enabled" if thinking_enabled else "disabled",
    }
    if thinking_enabled and not clear_thinking:
        result["thinking"]["clear_thinking"] = False
    return result


def preserve_glm_reasoning_in_tool_loop(
    assistant_messages: list[dict[str, Any]],
    reasoning_content: str,
) -> list[dict[str, Any]]:
    """Preserve reasoning_content in assistant message history for GLM tool loops.

    GLM requires that reasoning_content from prior turns is carried forward
    when clear_thinking=false. This injects it into the last assistant message.
    """
    if not reasoning_content or not assistant_messages:
        return assistant_messages
    result = [dict(m) for m in assistant_messages]
    last = result[-1]
    if last.get("role") == "assistant":
        last["reasoning_content"] = reasoning_content
    return result


def classify_provider_error(
    *,
    http_status: int | None,
    response_body: dict[str, Any] | None,
    provider: str,
) -> ProviderErrorClassification:
    """Normalize a provider HTTP error into a typed classification."""
    if http_status is None:
        return ProviderErrorClassification(
            error_class="network",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            http_status=None,
            retryable=False,
        )
    if http_status == 200:
        return ProviderErrorClassification(
            error_class="ok",
            machine_error_code=errors.OK,
            http_status=200,
            retryable=False,
        )
    if http_status in (401, 403):
        return ProviderErrorClassification(
            error_class="auth_failed",
            machine_error_code=errors.PROVIDER_AUTH_FAILED,
            http_status=http_status,
            retryable=False,
        )
    if http_status == 404:
        return ProviderErrorClassification(
            error_class="model_not_found",
            machine_error_code=errors.MODEL_NOT_AVAILABLE,
            http_status=404,
            retryable=False,
        )
    if http_status == 429:
        return ProviderErrorClassification(
            error_class="quota_exhausted",
            machine_error_code=errors.PROVIDER_AUTH_FAILED,
            http_status=429,
            retryable=True,
        )
    if http_status >= 500 or http_status == 408:
        return ProviderErrorClassification(
            error_class="network",
            machine_error_code=errors.PROVIDER_NETWORK_FAILED,
            http_status=http_status,
            retryable=True,
        )
    # Check for invalid_upstream_response
    body = response_body or {}
    error_msg = str(body.get("error", {}).get("message", "") or body.get("message", "")).lower()
    if "invalid" in error_msg or "malformed" in error_msg:
        return ProviderErrorClassification(
            error_class="invalid_response",
            machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
            http_status=http_status,
            retryable=False,
        )
    return ProviderErrorClassification(
        error_class="invalid_response",
        machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
        http_status=http_status,
        retryable=False,
    )


def build_provider_auth_headers(
    *,
    provider: str,
    secret_value: str,
) -> dict[str, str]:
    """Build auth headers for a provider request. Never logs the secret."""
    return {
        "Authorization": f"Bearer {secret_value}",
        "Content-Type": "application/json",
    }


__all__ = [
    "ProviderErrorClassification",
    "StreamingDeltaAccumulator",
    "apply_kimi_thinking",
    "apply_glm_thinking",
    "preserve_glm_reasoning_in_tool_loop",
    "classify_provider_error",
    "build_provider_auth_headers",
    "PROVIDER_KIMI",
    "PROVIDER_GLM",
    "DIALECT_KIMI_REASONING_EFFORT",
    "DIALECT_KIMI_THINKING",
    "DIALECT_GLM_THINKING",
]
