# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Capability registry and intelligence-level mapping (P04).

Builds a validated capability catalog from provider route definitions.
Each model entry carries provider, upstream ID, modalities, tools, streaming,
thinking, web search, context window, availability, proof level, and
intelligence-level mapping.

Intelligence levels use a unified catalog (default/fast/high/max) but
cross-provider equivalence is NEVER claimed.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .provider_transforms import (
    PROVIDER_KIMI,
    PROVIDER_GLM,
    DIALECT_KIMI_REASONING_EFFORT,
    DIALECT_KIMI_THINKING,
    DIALECT_GLM_THINKING,
)

PROVIDER_QWEN = "qwen"


@dataclasses.dataclass(frozen=True)
class CapabilityEntry:
    provider: str
    upstream_model: str
    wbp_alias: str
    modalities: tuple[str, ...]
    tool_capable: bool
    streaming: bool
    thinking_dialect: str
    web_search: bool
    context_window: int
    intelligence_levels: tuple[str, ...]
    proof_level: str  # DECLARED | SYNTHETIC_PROVEN
    docs_source: str

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["modalities"] = list(self.modalities)
        d["intelligence_levels"] = list(self.intelligence_levels)
        return d


# Declared catalog — model IDs from official docs, not live-verified.
# Must be refreshed by live discovery before PHYSICAL_PROVEN.
CATALOG: list[CapabilityEntry] = [
    CapabilityEntry(
        provider="deepseek", upstream_model="deepseek-chat",
        wbp_alias="DIP", modalities=("text",),
        tool_capable=True, streaming=True,
        thinking_dialect="deepseek_thinking", web_search=False,
        context_window=128000, intelligence_levels=("default", "fast", "high", "max"),
        proof_level="SYNTHETIC_PROVEN",
        docs_source="https://api-docs.deepseek.com",
    ),
    CapabilityEntry(
        provider=PROVIDER_KIMI, upstream_model="kimi-k3",
        wbp_alias="Kimi", modalities=("text", "image"),
        tool_capable=True, streaming=True,
        thinking_dialect=DIALECT_KIMI_REASONING_EFFORT, web_search=True,
        context_window=131072, intelligence_levels=("default", "fast", "high", "max"),
        proof_level="DECLARED",
        docs_source="https://platform.kimi.ai/docs/api/chat",
    ),
    CapabilityEntry(
        provider=PROVIDER_KIMI, upstream_model="kimi-k2.7-code-highspeed",
        wbp_alias="Kimi-Code", modalities=("text", "image"),
        tool_capable=True, streaming=True,
        thinking_dialect=DIALECT_KIMI_THINKING, web_search=True,
        context_window=131072, intelligence_levels=("default", "fast", "high"),
        proof_level="DECLARED",
        docs_source="https://platform.kimi.ai/docs/api/chat",
    ),
    CapabilityEntry(
        provider=PROVIDER_KIMI, upstream_model="kimi-k2.6",
        wbp_alias="Kimi-Classic", modalities=("text", "image"),
        tool_capable=True, streaming=True,
        thinking_dialect=DIALECT_KIMI_THINKING, web_search=True,
        context_window=131072, intelligence_levels=("default", "fast", "high"),
        proof_level="DECLARED",
        docs_source="https://platform.kimi.ai/docs/api/chat",
    ),
    CapabilityEntry(
        provider=PROVIDER_GLM, upstream_model="glm-4.6",
        wbp_alias="GLM", modalities=("text", "image"),
        tool_capable=True, streaming=True,
        thinking_dialect=DIALECT_GLM_THINKING, web_search=True,
        context_window=131072, intelligence_levels=("default", "fast", "high", "max"),
        proof_level="DECLARED",
        docs_source="https://docs.z.ai/api-reference/llm/chat-completion",
    ),
    CapabilityEntry(
        provider=PROVIDER_QWEN, upstream_model="qwen-plus",
        wbp_alias="Qwen", modalities=("text",),
        tool_capable=True, streaming=True,
        thinking_dialect="qwen_thinking", web_search=False,
        context_window=131072, intelligence_levels=("default", "fast", "high"),
        proof_level="DECLARED",
        docs_source="https://help.aliyun.com/zh/model-studio",
    ),
    CapabilityEntry(
        provider=PROVIDER_QWEN, upstream_model="qwen-max",
        wbp_alias="Qwen-Max", modalities=("text",),
        tool_capable=True, streaming=True,
        thinking_dialect="qwen_thinking", web_search=False,
        context_window=131072, intelligence_levels=("default", "fast", "high"),
        proof_level="DECLARED",
        docs_source="https://help.aliyun.com/zh/model-studio",
    ),
    CapabilityEntry(
        provider=PROVIDER_QWEN, upstream_model="qwen3-max",
        wbp_alias="Qwen3", modalities=("text",),
        tool_capable=True, streaming=True,
        thinking_dialect="qwen_thinking", web_search=False,
        context_window=131072, intelligence_levels=("default", "fast", "high"),
        proof_level="DECLARED",
        docs_source="https://help.aliyun.com/zh/model-studio",
    ),
]

# Intelligence-level → provider parameter mapping
INTELLIGENCE_MAPPINGS: dict[str, dict[str, str | None]] = {
    f"kimi-k3": {"default": None, "fast": "low", "high": "high", "max": "max"},
    f"kimi-k2.7-code-highspeed": {"default": None, "fast": "disabled", "high": "enabled"},
    f"kimi-k2.6": {"default": None, "fast": "disabled", "high": "enabled"},
    f"glm-4.6": {"default": None, "fast": "disabled", "high": "enabled", "max": "enabled"},
    "deepseek-chat": {"default": None, "fast": "disabled", "high": "high", "max": "max"},
    "qwen3-max": {"default": None, "fast": "disabled", "high": "enabled"},
}


def get_catalog() -> list[dict[str, Any]]:
    """Return the full capability catalog as packet-safe dicts."""
    return [e.to_dict() for e in CATALOG]


def get_entry(model: str) -> CapabilityEntry | None:
    """Find a catalog entry by upstream model ID."""
    for entry in CATALOG:
        if entry.upstream_model == model:
            return entry
    return None


def get_intelligence_mapping(model: str) -> dict[str, str | None]:
    """Return the catalog→provider parameter mapping for a model.

    Unavailable levels are absent from the dict. Cross-provider equivalence
    is never claimed.
    """
    return dict(INTELLIGENCE_MAPPINGS.get(model, {}))


def resolve_intelligence_level(
    model: str, catalog_level: str,
) -> tuple[str | None, str]:
    """Resolve a catalog intelligence level to a provider parameter.

    Returns (provider_parameter, source).
    Unavailable levels return (None, "unavailable").
    """
    mapping = get_intelligence_mapping(model)
    if catalog_level not in mapping:
        return None, "unavailable"
    param = mapping[catalog_level]
    if param is None:
        return None, "provider_default"
    return param, "provider_declared"


__all__ = [
    "CapabilityEntry", "CATALOG", "INTELLIGENCE_MAPPINGS",
    "get_catalog", "get_entry", "get_intelligence_mapping",
    "resolve_intelligence_level",
]
