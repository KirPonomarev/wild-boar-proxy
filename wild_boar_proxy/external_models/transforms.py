"""Bounded declarative transform profiles for external-models compatibility."""

from __future__ import annotations

from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import errors

DEFAULT_REQUEST_TRANSFORM = "openai_chat_passthrough"
DEFAULT_RESPONSE_PROFILE = "openai_chat_choices_message"
CHECK_REQUEST_COMPLETION_BUDGET = 96
THINKING_CHECK_REQUEST_COMPLETION_BUDGET = 2048
THINKING_REASONING_EFFORTS = frozenset({"high", "max"})
MIN_CHECK_REQUEST_COMPLETION_BUDGET = 1
MAX_CHECK_REQUEST_COMPLETION_BUDGET = 32768

REQUEST_TRANSFORM_PROFILES = frozenset(
    {
        DEFAULT_REQUEST_TRANSFORM,
        "deepseek_default",
        "openai_chat_developer_to_system",
        "openai_chat_system_to_developer",
        "openai_chat_input_text",
    }
)
RESPONSE_PROFILES = frozenset(
    {
        DEFAULT_RESPONSE_PROFILE,
        "openai_chat_completions",
        "top_level_output_text",
        "content_blocks_text",
    }
)


def validate_route_transform_profiles(route: dict[str, Any]) -> None:
    transform_profile = route.get("transform_profile")
    response_profile = route.get("response_profile")
    if transform_profile is not None and transform_profile not in REQUEST_TRANSFORM_PROFILES:
        raise RuntimeErrorInfo(
            f"Unknown transform_profile: {transform_profile}",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if response_profile is not None and response_profile not in RESPONSE_PROFILES:
        raise RuntimeErrorInfo(
            f"Unknown response_profile: {response_profile}",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    check_max_tokens = route.get("check_max_tokens")
    if check_max_tokens is not None:
        if not isinstance(check_max_tokens, int) or isinstance(check_max_tokens, bool):
            raise RuntimeErrorInfo(
                "check_max_tokens must be an integer.",
                machine_error_code=errors.SCHEMA_INVALID,
                operator_action="user_action",
            )
        if not (
            MIN_CHECK_REQUEST_COMPLETION_BUDGET
            <= check_max_tokens
            <= MAX_CHECK_REQUEST_COMPLETION_BUDGET
        ):
            raise RuntimeErrorInfo(
                "check_max_tokens is outside the supported range.",
                machine_error_code=errors.SCHEMA_INVALID,
                operator_action="user_action",
            )
    thinking = route.get("thinking")
    if thinking is None:
        return
    # Generic thinking policy: admitted for providers with reasoning support
    # (deepseek, kimi, glm, qwen). Each provider has its own reasoning dialect.
    provider = str(route.get("provider") or "").strip()
    _THINKING_CAPABLE_PROVIDERS = frozenset({"deepseek", "kimi", "glm", "qwen"})
    if provider not in _THINKING_CAPABLE_PROVIDERS:
        raise RuntimeErrorInfo(
            f"thinking policy is admitted only for reasoning-capable providers "
            f"({sorted(_THINKING_CAPABLE_PROVIDERS)}), not '{provider}'.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    if not isinstance(thinking, dict):
        raise RuntimeErrorInfo(
            "thinking must be an object.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    thinking_type = str(thinking.get("type") or "").strip()
    if thinking_type == "disabled":
        unexpected = sorted(str(key) for key in thinking if key != "type")
        if unexpected:
            raise RuntimeErrorInfo(
                "disabled thinking policy must not include extra fields.",
                machine_error_code=errors.SCHEMA_INVALID,
                operator_action="user_action",
            )
        return
    if thinking_type != "enabled":
        raise RuntimeErrorInfo(
            "thinking.type must be disabled or enabled.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    reasoning_effort = str(thinking.get("reasoning_effort") or "").strip()
    if reasoning_effort not in THINKING_REASONING_EFFORTS:
        raise RuntimeErrorInfo(
            "thinking.reasoning_effort must be high or max.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )
    unexpected = sorted(str(key) for key in thinking if key not in {"type", "reasoning_effort"})
    if unexpected:
        raise RuntimeErrorInfo(
            "thinking policy contains unsupported fields.",
            machine_error_code=errors.SCHEMA_INVALID,
            operator_action="user_action",
        )


def route_thinking_metadata(route: dict[str, Any]) -> dict[str, Any]:
    thinking = route.get("thinking")
    if not isinstance(thinking, dict):
        return {
            "thinking": {"type": "unconfigured"},
            "api_parameter_sent": False,
            "label_source": "unavailable_unknown",
            "intelligence_measured": False,
        }
    thinking_type = str(thinking.get("type") or "disabled").strip()
    if thinking_type != "enabled":
        return {
            "thinking": {"type": "disabled"},
            "api_parameter_sent": True,
            "label_source": "provider_declared_plus_operator_mapping",
            "intelligence_measured": False,
        }
    reasoning_effort = str(thinking.get("reasoning_effort") or "high").strip()
    return {
        "thinking": {
            "type": "enabled",
            "reasoning_effort": reasoning_effort,
        },
        "api_parameter_sent": True,
        "label_source": "provider_declared_plus_operator_mapping",
        "intelligence_measured": False,
    }


def apply_route_thinking_policy(
    payload: dict[str, Any],
    route: dict[str, Any],
) -> dict[str, Any]:
    metadata = route_thinking_metadata(route)
    thinking = metadata.get("thinking")
    if (
        isinstance(thinking, dict)
        and thinking.get("type") in {"disabled", "enabled"}
        and metadata.get("api_parameter_sent") is True
    ):
        payload["thinking"] = dict(thinking)
    return metadata


def route_transform_metadata(route: dict[str, Any]) -> dict[str, Any]:
    transform_profile = str(route.get("transform_profile") or DEFAULT_REQUEST_TRANSFORM)
    response_profile = str(route.get("response_profile") or DEFAULT_RESPONSE_PROFILE)
    return {
        "transform_profile": transform_profile,
        "response_profile": response_profile,
        "transform_declared": "transform_profile" in route,
        "response_profile_declared": "response_profile" in route,
    }


def route_check_completion_budget(route: dict[str, Any]) -> int:
    value = route.get("check_max_tokens")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return CHECK_REQUEST_COMPLETION_BUDGET


def build_check_request(route: dict[str, Any], *, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = route_transform_metadata(route)
    completion_budget = route_check_completion_budget(route)
    base_payload = {
        "model": route["upstream_model"],
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": completion_budget,
    }
    thinking_metadata = apply_route_thinking_policy(base_payload, route)
    metadata = metadata | thinking_metadata
    if (
        isinstance(thinking_metadata.get("thinking"), dict)
        and thinking_metadata["thinking"].get("type") == "enabled"
    ):
        base_payload["max_tokens"] = max(
            int(base_payload["max_tokens"]),
            THINKING_CHECK_REQUEST_COMPLETION_BUDGET,
        )
    transform_profile = metadata["transform_profile"]
    if transform_profile in {DEFAULT_REQUEST_TRANSFORM, "deepseek_default"}:
        return base_payload, metadata | {"request_shape": "openai_chat_messages"}
    if transform_profile == "openai_chat_system_to_developer":
        transformed_messages: list[dict[str, Any]] = []
        for message in base_payload["messages"]:
            role = "developer" if message.get("role") == "system" else message.get("role")
            transformed_messages.append({"role": role, "content": message.get("content", "")})
        payload = {
            "model": route["upstream_model"],
            "messages": transformed_messages,
            "max_tokens": base_payload["max_tokens"],
        }
        if "thinking" in base_payload:
            payload["thinking"] = base_payload["thinking"]
        return (payload, metadata | {"request_shape": "openai_chat_messages"})
    if transform_profile == "openai_chat_developer_to_system":
        transformed_messages = []
        for message in base_payload["messages"]:
            role = "system" if message.get("role") == "developer" else message.get("role")
            transformed_messages.append({"role": role, "content": message.get("content", "")})
        payload = {
            "model": route["upstream_model"],
            "messages": transformed_messages,
            "max_tokens": base_payload["max_tokens"],
        }
        if "thinking" in base_payload:
            payload["thinking"] = base_payload["thinking"]
        return (payload, metadata | {"request_shape": "openai_chat_messages"})
    if transform_profile == "openai_chat_input_text":
        parts = [str(message.get("content", "")).strip() for message in base_payload["messages"]]
        input_text = "\n".join(part for part in parts if part)
        return (
            {
                "model": route["upstream_model"],
                "input_text": input_text,
                "max_output_tokens": base_payload["max_tokens"],
            },
            metadata | {"request_shape": "input_text"},
        )
    raise RuntimeErrorInfo(
        f"Unknown transform_profile: {transform_profile}",
        machine_error_code=errors.SCHEMA_INVALID,
        operator_action="user_action",
    )


def extract_check_response(
    route: dict[str, Any], payload: Any
) -> tuple[str, dict[str, Any]]:
    metadata = route_transform_metadata(route)
    response_profile = metadata["response_profile"]
    if response_profile in {DEFAULT_RESPONSE_PROFILE, "openai_chat_completions"}:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise RuntimeErrorInfo(
                "Provider smoke-check payload did not contain choices.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        first = choices[0]
        if not isinstance(first, dict):
            raise RuntimeErrorInfo(
                "Provider smoke-check choice entry was invalid.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        message = first.get("message")
        if not isinstance(message, dict):
            raise RuntimeErrorInfo(
                "Provider smoke-check message did not contain text.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeErrorInfo(
                "Provider smoke-check message did not contain text.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        return content.strip(), metadata | {"response_shape": "choices_message"}
    if response_profile == "top_level_output_text":
        if not isinstance(payload, dict) or not str(payload.get("output_text", "")).strip():
            raise RuntimeErrorInfo(
                "Provider transform response did not contain output_text.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        return str(payload["output_text"]).strip(), metadata | {"response_shape": "output_text"}
    if response_profile == "content_blocks_text":
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise RuntimeErrorInfo(
                "Provider transform response did not contain content blocks.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        for block in payload["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("type") in {"text", "output_text"} and str(block.get("text", "")).strip():
                return (
                    str(block["text"]).strip(),
                    metadata | {"response_shape": "content_blocks"},
                )
        raise RuntimeErrorInfo(
            "Provider transform response content blocks did not contain text.",
            machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
            operator_action="retry",
        )
    raise RuntimeErrorInfo(
        f"Unknown response_profile: {response_profile}",
        machine_error_code=errors.SCHEMA_INVALID,
        operator_action="user_action",
    )
