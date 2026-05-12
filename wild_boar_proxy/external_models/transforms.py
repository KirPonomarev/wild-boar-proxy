"""Bounded declarative transform profiles for external-models compatibility."""

from __future__ import annotations

from typing import Any

from wild_boar_proxy.runtime import RuntimeErrorInfo

from . import errors

DEFAULT_REQUEST_TRANSFORM = "openai_chat_passthrough"
DEFAULT_RESPONSE_PROFILE = "openai_chat_choices_message"

REQUEST_TRANSFORM_PROFILES = frozenset(
    {
        DEFAULT_REQUEST_TRANSFORM,
        "openai_chat_system_to_developer",
        "openai_chat_input_text",
    }
)
RESPONSE_PROFILES = frozenset(
    {
        DEFAULT_RESPONSE_PROFILE,
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


def route_transform_metadata(route: dict[str, Any]) -> dict[str, Any]:
    transform_profile = str(route.get("transform_profile") or DEFAULT_REQUEST_TRANSFORM)
    response_profile = str(route.get("response_profile") or DEFAULT_RESPONSE_PROFILE)
    return {
        "transform_profile": transform_profile,
        "response_profile": response_profile,
        "transform_declared": "transform_profile" in route,
        "response_profile_declared": "response_profile" in route,
    }


def build_check_request(route: dict[str, Any], *, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = route_transform_metadata(route)
    base_payload = {
        "model": route["upstream_model"],
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 8,
    }
    transform_profile = metadata["transform_profile"]
    if transform_profile == DEFAULT_REQUEST_TRANSFORM:
        return base_payload, metadata | {"request_shape": "openai_chat_messages"}
    if transform_profile == "openai_chat_system_to_developer":
        transformed_messages: list[dict[str, Any]] = []
        for message in base_payload["messages"]:
            role = "developer" if message.get("role") == "system" else message.get("role")
            transformed_messages.append({"role": role, "content": message.get("content", "")})
        return (
            {
                "model": route["upstream_model"],
                "messages": transformed_messages,
                "max_tokens": 8,
            },
            metadata | {"request_shape": "openai_chat_messages"},
        )
    if transform_profile == "openai_chat_input_text":
        parts = [str(message.get("content", "")).strip() for message in base_payload["messages"]]
        input_text = "\n".join(part for part in parts if part)
        return (
            {
                "model": route["upstream_model"],
                "input_text": input_text,
                "max_output_tokens": 8,
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
    if response_profile == DEFAULT_RESPONSE_PROFILE:
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
        if not isinstance(message, dict) or not str(message.get("content", "")).strip():
            raise RuntimeErrorInfo(
                "Provider smoke-check message did not contain text.",
                machine_error_code=errors.INVALID_UPSTREAM_RESPONSE,
                operator_action="retry",
            )
        return str(message["content"]).strip(), metadata | {"response_shape": "choices_message"}
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
