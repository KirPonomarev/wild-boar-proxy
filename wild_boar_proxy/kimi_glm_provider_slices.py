# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Kimi and GLM provider vertical slices (P05 + P06).

Adds Kimi (Moonshot) and GLM (Z.AI) as direct providers with their own
reasoning dialects, model discovery, and error taxonomy. The CLIProxyAPI
engine remains the owner of low-level dispatch; this is the WBP control-layer
contract surface.

Reasoning dialects:
- Kimi K3: top-level reasoning_effort=low|high|max
- Kimi K2.7 Code: always-thinking, no reasoning_effort
- Kimi K2.6: thinking.type=enabled|disabled + thinking.keep
- GLM: thinking.type + interleaved thinking + reasoning_content preservation

Live dispatch is not performed here. Live exact-response proof is reserved
for P12. Credential values never appear in any packet.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Mapping

from .core import packets as command_packets
from .runtime import build_command_payload

SLICE_EFFECT_READ = "read"
SLICE_EFFECT_MUTATE = "mutate"

# ---- Kimi ----
KIMI_PROVIDER_ID = "kimi"
KIMI_DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_DEFAULT_ENDPOINT_PATH = "/chat/completions"
KIMI_CREDENTIAL_REF = "MOONSHOT_API_KEY"
KIMI_PROVIDER_DASHBOARD = "https://platform.moonshot.cn/console/api-keys"
KIMI_LANE_ROLE = "kimi_api_lane"

# Kimi model candidates (to be confirmed by live discovery at P12)
KIMI_MODEL_K3 = "kimi-k3"
KIMI_MODEL_K27_CODE = "kimi-k2.7-code-highspeed"
KIMI_MODEL_K26 = "kimi-k2.6"

# Kimi reasoning dialects
KIMI_DIALECT_K3 = "kimi_reasoning_effort"  # reasoning_effort=low|high|max
KIMI_DIALECT_K27 = "provider_fixed_reasoning"  # always thinking, no param
KIMI_DIALECT_K26 = "kimi_thinking"  # thinking.type=enabled|disabled

# Kimi intelligence mapping (catalog → provider param)
KIMI_K3_INTELLIGENCE = {
    "default": None,
    "fast": "low",
    "high": "high",
    "max": "max",
}
KIMI_K27_INTELLIGENCE = {
    "default": "provider-fixed",
    "fast": "highspeed-variant",
    "high": None,  # unavailable
    "max": None,  # unavailable
}
KIMI_K26_INTELLIGENCE = {
    "default": None,
    "fast": "disabled",
    "high": "enabled",
    "max": None,  # unavailable unless API provides
}

# ---- GLM ----
GLM_PROVIDER_ID = "glm"
GLM_DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
GLM_DEFAULT_ENDPOINT_PATH = "/chat/completions"
GLM_CREDENTIAL_REF = "ZAI_API_KEY"
GLM_PROVIDER_DASHBOARD = "https://docs.z.ai"
GLM_LANE_ROLE = "glm_api_lane"

GLM_MODEL_FLAGSHIP = "glm-4.6"  # to be confirmed by live discovery

GLM_DIALECT = "glm_thinking"  # thinking.type + interleaved + reasoning_content

GLM_INTELLIGENCE = {
    "default": None,
    "fast": "disabled",
    "high": "enabled",
    "max": "enabled",
}


@dataclasses.dataclass(frozen=True)
class ProviderSlice:
    provider_id: str
    display_name: str
    base_url: str
    endpoint_path: str
    credential_ref: str
    provider_dashboard_url: str
    lane_role: str
    reasoning_dialect: str
    capability_text: bool
    capability_stream: bool
    capability_tool: bool
    capability_vision: bool
    capability_web_search: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


KIMI_SLICE = ProviderSlice(
    provider_id=KIMI_PROVIDER_ID,
    display_name="Kimi (Moonshot)",
    base_url=KIMI_DEFAULT_BASE_URL,
    endpoint_path=KIMI_DEFAULT_ENDPOINT_PATH,
    credential_ref=KIMI_CREDENTIAL_REF,
    provider_dashboard_url=KIMI_PROVIDER_DASHBOARD,
    lane_role=KIMI_LANE_ROLE,
    reasoning_dialect=KIMI_DIALECT_K3,  # default to K3
    capability_text=True,
    capability_stream=True,
    capability_tool=True,
    capability_vision=True,
    capability_web_search=True,
)

GLM_SLICE = ProviderSlice(
    provider_id=GLM_PROVIDER_ID,
    display_name="GLM (Z.AI)",
    base_url=GLM_DEFAULT_BASE_URL,
    endpoint_path=GLM_DEFAULT_ENDPOINT_PATH,
    credential_ref=GLM_CREDENTIAL_REF,
    provider_dashboard_url=GLM_PROVIDER_DASHBOARD,
    lane_role=GLM_LANE_ROLE,
    reasoning_dialect=GLM_DIALECT,
    capability_text=True,
    capability_stream=True,
    capability_tool=True,
    capability_vision=True,
    capability_web_search=True,
)


def build_kimi_route_definition(
    *,
    route_id: str = "wbp-kimi-primary",
    upstream_model: str = KIMI_MODEL_K3,
    secret_ref: str = KIMI_CREDENTIAL_REF,
    enabled: bool = False,
) -> dict[str, Any]:
    """Build a canonical Kimi route definition.

    transform_profile / response_profile / thinking use only values registered
    in the production route validator (see external_models.transforms), so the
    route passes validate_route_schema().
    """
    from .external_models.contracts import ROUTE_SCHEMA_VERSION
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "route_id": route_id,
        "display_name": "Kimi",
        "provider": KIMI_PROVIDER_ID,
        "base_url": KIMI_DEFAULT_BASE_URL,
        "endpoint_path": KIMI_DEFAULT_ENDPOINT_PATH,
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": secret_ref},
        "cost_class": "paid_direct",
        "lane_role": KIMI_LANE_ROLE,
        "fallback_eligible": False,
        "enabled": enabled,
        "transform_profile": "openai_chat_passthrough",
        "response_profile": "openai_chat_choices_message",
        "thinking": {"type": "disabled"},
        "check_max_tokens": 4096,
    }


def build_glm_route_definition(
    *,
    route_id: str = "wbp-glm-primary",
    upstream_model: str = GLM_MODEL_FLAGSHIP,
    secret_ref: str = GLM_CREDENTIAL_REF,
    enabled: bool = False,
) -> dict[str, Any]:
    """Build a canonical GLM route definition.

    transform_profile / response_profile / thinking use only values registered
    in the production route validator (see external_models.transforms), so the
    route passes validate_route_schema().
    """
    from .external_models.contracts import ROUTE_SCHEMA_VERSION
    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "route_id": route_id,
        "display_name": "GLM",
        "provider": GLM_PROVIDER_ID,
        "base_url": GLM_DEFAULT_BASE_URL,
        "endpoint_path": GLM_DEFAULT_ENDPOINT_PATH,
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": secret_ref},
        "cost_class": "paid_direct",
        "lane_role": GLM_LANE_ROLE,
        "fallback_eligible": False,
        "enabled": enabled,
        "transform_profile": "openai_chat_passthrough",
        "response_profile": "openai_chat_choices_message",
        "thinking": {"type": "disabled"},
        "check_max_tokens": 4096,
    }


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_intelligence_mapping_receipt(
    *,
    provider: str,
    model: str,
) -> dict[str, Any]:
    """Build the intelligence-level mapping receipt for a provider/model."""
    if provider == KIMI_PROVIDER_ID:
        if model == KIMI_MODEL_K3:
            mapping = KIMI_K3_INTELLIGENCE
            dialect = KIMI_DIALECT_K3
        elif model == KIMI_MODEL_K27_CODE:
            mapping = KIMI_K27_INTELLIGENCE
            dialect = KIMI_DIALECT_K27
        elif model == KIMI_MODEL_K26:
            mapping = KIMI_K26_INTELLIGENCE
            dialect = KIMI_DIALECT_K26
        else:
            mapping = {}
            dialect = "unknown"
    elif provider == GLM_PROVIDER_ID:
        mapping = GLM_INTELLIGENCE
        dialect = GLM_DIALECT
    else:
        return _build_packet(
            ok=False, human_message=f"Unknown provider: {provider}",
            machine_error_code="UNKNOWN_PROVIDER", operator_action="user_action",
            liveness="down", severity="recoverable", changed_files=[], effect=SLICE_EFFECT_READ,
        )

    levels = []
    for catalog_level, provider_param in mapping.items():
        available = provider_param is not None
        levels.append({
            "catalog_level": catalog_level,
            "provider_parameter": provider_param,
            "available": available,
            "label_source": "provider_declared",
            "intelligence_measured": False,
            "cross_provider_equivalence_claimed": False,
        })
    return _build_packet(
        ok=True,
        human_message=f"Intelligence mapping for {provider}/{model}.",
        machine_error_code="OK",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=SLICE_EFFECT_READ,
        extra={
            "provider": provider,
            "model": model,
            "reasoning_dialect": dialect,
            "levels": levels,
        },
    )


def run_kimi_glm_synthetic_proof() -> dict[str, Any]:
    """Deterministic synthetic proof for Kimi + GLM vertical slices."""
    kimi_route = build_kimi_route_definition(enabled=True)
    glm_route = build_glm_route_definition(enabled=True)
    kimi_k3_map = build_intelligence_mapping_receipt(provider=KIMI_PROVIDER_ID, model=KIMI_MODEL_K3)
    kimi_k27_map = build_intelligence_mapping_receipt(provider=KIMI_PROVIDER_ID, model=KIMI_MODEL_K27_CODE)
    kimi_k26_map = build_intelligence_mapping_receipt(provider=KIMI_PROVIDER_ID, model=KIMI_MODEL_K26)
    glm_map = build_intelligence_mapping_receipt(provider=GLM_PROVIDER_ID, model=GLM_MODEL_FLAGSHIP)

    receipts = [kimi_k3_map, kimi_k27_map, kimi_k26_map, glm_map]
    violations: list[str] = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))

    # Verify intelligence mappings are correct
    k3_levels = {l["catalog_level"]: l for l in kimi_k3_map["levels"]}
    k27_levels = {l["catalog_level"]: l for l in kimi_k27_map["levels"]}
    glm_levels = {l["catalog_level"]: l for l in glm_map["levels"]}

    checks = {
        "kimi_k3_fast_maps_to_low": k3_levels["fast"]["provider_parameter"] == "low",
        "kimi_k3_max_maps_to_max": k3_levels["max"]["provider_parameter"] == "max",
        "kimi_k27_high_unavailable": k27_levels["high"]["available"] is False,
        "glm_high_maps_to_enabled": glm_levels["high"]["provider_parameter"] == "enabled",
        "no_equivalence_claimed": all(
            not l["cross_provider_equivalence_claimed"]
            for r in receipts for l in r["levels"]
        ),
    }

    no_secret_leak = all("sk-" not in __import__("json").dumps(r) for r in receipts)
    ok = not violations and no_secret_leak and all(checks.values())
    return _build_packet(
        ok=ok,
        human_message="Kimi + GLM vertical slices synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "KIMI_GLM_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=SLICE_EFFECT_READ,
        extra={
            "receipt_count": len(receipts),
            "kimi_route_defined": kimi_route["provider"] == KIMI_PROVIDER_ID,
            "glm_route_defined": glm_route["provider"] == GLM_PROVIDER_ID,
            "checks": checks,
            "packet_violations": violations,
        },
    )


__all__ = [
    "ProviderSlice", "KIMI_SLICE", "GLM_SLICE",
    "KIMI_PROVIDER_ID", "GLM_PROVIDER_ID",
    "KIMI_MODEL_K3", "KIMI_MODEL_K27_CODE", "KIMI_MODEL_K26",
    "GLM_MODEL_FLAGSHIP",
    "KIMI_DIALECT_K3", "KIMI_DIALECT_K27", "KIMI_DIALECT_K26", "GLM_DIALECT",
    "KIMI_K3_INTELLIGENCE", "KIMI_K27_INTELLIGENCE", "KIMI_K26_INTELLIGENCE",
    "GLM_INTELLIGENCE",
    "build_kimi_route_definition", "build_glm_route_definition",
    "build_intelligence_mapping_receipt",
    "run_kimi_glm_synthetic_proof",
]
