# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Qwen (Alibaba Cloud DashScope) provider vertical slice (B08).

Adds Qwen as a first-class API actor: credential reference, canonical route
definition, thinking dialect, model candidates, capability profile, and a
deterministic declared profile receipt. Live exact-response proof is reserved
for B08_LIVE. Credential values never appear in any packet.
"""

from __future__ import annotations

from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

QWEN_PROVIDER_ID = "qwen"
QWEN_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com"
QWEN_DEFAULT_ENDPOINT_PATH = "/compatible-mode/v1/chat/completions"
QWEN_CREDENTIAL_REF = "DASHSCOPE_API_KEY"
QWEN_PROVIDER_DASHBOARD = "https://bailian.console.aliyun.com/?apiKey=1"
QWEN_LANE_ROLE = "qwen_api_lane"
QWEN_DEFAULT_ROUTE_ID = "wbp-qwen-primary"

# Qwen model candidates (declared; to be confirmed by live discovery at
# B08_LIVE).
QWEN_MODEL_PLUS = "qwen-plus"
QWEN_MODEL_MAX = "qwen-max"
QWEN_MODEL_QWEN3 = "qwen3-max"
QWEN_MODEL_IDS = (QWEN_MODEL_PLUS, QWEN_MODEL_MAX, QWEN_MODEL_QWEN3)

# Qwen reasoning dialect: qwen3-family uses the top-level enable_thinking
# parameter (compatible mode).
QWEN_DIALECT_THINKING = "qwen_thinking"
QWEN_THINKING_ENABLED_MODELS = {QWEN_MODEL_QWEN3}


def apply_qwen_thinking(
    payload: dict[str, Any],
    *,
    model: str = "",
    thinking_enabled: bool = False,
) -> dict[str, Any]:
    """Apply the Qwen thinking dialect to a request payload.

    Only qwen3-family models carry the enable_thinking parameter; other Qwen
    models are provider-fixed. The parameter is never inferred from a model
    name outside the declared set.
    """
    if model in QWEN_THINKING_ENABLED_MODELS:
        payload["enable_thinking"] = bool(thinking_enabled)
    return payload


def build_qwen_route_definition(
    *,
    route_id: str = QWEN_DEFAULT_ROUTE_ID,
    upstream_model: str = QWEN_MODEL_PLUS,
    secret_ref: str = QWEN_CREDENTIAL_REF,
    enabled: bool = False,
) -> dict[str, Any]:
    """Build a canonical Qwen route definition.

    transform_profile / response_profile / thinking use only values registered
    in the production route validator, so the route passes
    validate_route_schema().
    """
    from .external_models.contracts import ROUTE_SCHEMA_VERSION
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "route_id": route_id,
        "display_name": "Qwen",
        "provider": QWEN_PROVIDER_ID,
        "base_url": QWEN_DEFAULT_BASE_URL,
        "endpoint_path": QWEN_DEFAULT_ENDPOINT_PATH,
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": secret_ref},
        "cost_class": "paid_direct",
        "lane_role": QWEN_LANE_ROLE,
        "fallback_eligible": False,
        "enabled": enabled,
        "transform_profile": "openai_chat_passthrough",
        "response_profile": "openai_chat_choices_message",
        "thinking": {"type": "disabled"},
        "check_max_tokens": 4096,
    }


def build_qwen_profile_packet() -> dict[str, Any]:
    """Deterministic declared profile receipt for the Qwen slice.

    Declared capabilities are deterministic; declared != live-verified.
    """
    route = build_qwen_route_definition()
    from .external_models import routes as external_routes

    violations: list[str] = []
    try:
        external_routes.validate_route_schema(route)
    except Exception as exc:  # noqa: BLE001
        violations.append(str(exc))
    from .external_models.capability_registry import get_entry

    catalog_missing = [model for model in QWEN_MODEL_IDS if get_entry(model) is None]
    ok = not violations and not catalog_missing
    return build_command_payload(
        ok=ok,
        human_message=(
            "Qwen provider slice profile complete (declared capabilities; "
            "no live verification claimed)."
            if ok
            else "Qwen provider slice profile violations."
        ),
        machine_error_code="SYNTHETIC_PROVEN" if ok else "QWEN_PROFILE_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect="read",
        extra={
            "provider_id": QWEN_PROVIDER_ID,
            "default_route_id": QWEN_DEFAULT_ROUTE_ID,
            "default_base_url": QWEN_DEFAULT_BASE_URL,
            "model_candidates": list(QWEN_MODEL_IDS),
            "thinking_dialect": QWEN_DIALECT_THINKING,
            "thinking_enabled_models": sorted(QWEN_THINKING_ENABLED_MODELS),
            "route_schema_valid": not violations,
            "catalog_missing_models": catalog_missing,
            "evidence_level": "SYNTHETIC_PROVEN",
            "declared_not_live_verified": True,
            "packet_violations": command_packets.inspect_command_packet_semantics(
                build_command_payload(
                    ok=ok,
                    human_message="",
                    machine_error_code="SYNTHETIC_PROVEN" if ok else "QWEN_PROFILE_VIOLATIONS",
                    operator_action="none" if ok else "stop",
                    liveness="healthy" if ok else "degraded",
                    severity="recoverable",
                    changed_files=[],
                    effect="read",
                )
            ),
        },
    )


__all__ = [
    "QWEN_PROVIDER_ID",
    "QWEN_DEFAULT_BASE_URL",
    "QWEN_DEFAULT_ENDPOINT_PATH",
    "QWEN_CREDENTIAL_REF",
    "QWEN_PROVIDER_DASHBOARD",
    "QWEN_LANE_ROLE",
    "QWEN_DEFAULT_ROUTE_ID",
    "QWEN_MODEL_PLUS",
    "QWEN_MODEL_MAX",
    "QWEN_MODEL_QWEN3",
    "QWEN_MODEL_IDS",
    "QWEN_DIALECT_THINKING",
    "QWEN_THINKING_ENABLED_MODELS",
    "apply_qwen_thinking",
    "build_qwen_route_definition",
    "build_qwen_profile_packet",
]
