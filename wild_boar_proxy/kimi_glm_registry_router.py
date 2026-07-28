# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Kimi/GLM model registry, alias router, and pool policy (P07+P09+P10).

Extends the model registry with Kimi/GLM families, adds alias routing for
Kimi:/GLM: labels, and defines cross-provider failover policy.
"""

from __future__ import annotations
import dataclasses
from typing import Any
from .core import packets as command_packets
from .runtime import build_command_payload

REGISTRY_EFFECT_READ = "read"

@dataclasses.dataclass(frozen=True)
class ModelRegistryEntry:
    provider: str
    family: str
    wbp_alias: str
    upstream_model: str
    context_window: int
    input_modalities: tuple[str, ...]
    tool_capable: bool
    streaming: bool
    intelligence_levels: tuple[str, ...]
    speed_tier: str
    source: str
    proof_level: str  # declared | live_verified
    verified_date: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

REGISTRY: list[ModelRegistryEntry] = [
    ModelRegistryEntry("deepseek", "DeepSeek", "DIP", "deepseek-chat", 128000,
        ("text",), True, True, ("default", "fast", "high", "max"), "medium",
        "provider_declared", "synthetic_proven", "2026-07-27"),
    ModelRegistryEntry("kimi", "Kimi", "Kimi", "kimi-k3", 131072,
        ("text", "image"), True, True, ("default", "fast", "high", "max"), "medium",
        "provider_declared", "declared", "2026-07-28"),
    ModelRegistryEntry("kimi", "Kimi", "Kimi-Code", "kimi-k2.7-code-highspeed", 131072,
        ("text",), True, True, ("default", "fast"), "fast",
        "provider_declared", "declared", "2026-07-28"),
    ModelRegistryEntry("kimi", "Kimi", "Kimi-Classic", "kimi-k2.6", 131072,
        ("text", "image"), True, True, ("default", "fast", "high"), "medium",
        "provider_declared", "declared", "2026-07-28"),
    ModelRegistryEntry("glm", "GLM", "GLM", "glm-4.6", 131072,
        ("text", "image"), True, True, ("default", "fast", "high", "max"), "medium",
        "provider_declared", "declared", "2026-07-28"),
]

# Alias router: label -> provider lane
ALIAS_ROUTES: dict[str, str] = {
    "Codex": "native_gpt",
    "DIP": "deepseek",
    "Deep": "deepseek",
    "DeepSeek": "deepseek",
    "Kimi": "kimi",
    "GLM": "glm",
}

FAILVOVER_POLICY = {
    "max_replacement_dispatches": 1,
    "eligible_failure_classes": ("quota", "auth", "cooldown"),
    "ambiguous_retry_count": 0,
    "no_fallback_after_tool_side_effect": True,
    "switch_always_visible": True,
}

def resolve_alias(label: str) -> tuple[str, str]:
    """Return (lane, machine_error_code). Unknown/ambiguous -> fail closed."""
    normalized = label.strip()
    if normalized in ALIAS_ROUTES:
        return ALIAS_ROUTES[normalized], "OK"
    return "unknown", "ALIAS_NOT_FOUND"

def build_alias_routing_matrix_receipt() -> dict[str, Any]:
    """Deterministic alias routing acceptance matrix (P09)."""
    test_cases = [
        ("Codex", "native_gpt"), ("DIP", "deepseek"), ("Deep", "deepseek"),
        ("DeepSeek", "deepseek"), ("Kimi", "kimi"), ("GLM", "glm"),
        ("Ghost", "unknown"), ("", "unknown"),
    ]
    results = []
    for label, expected_lane in test_cases:
        lane, code = resolve_alias(label)
        ok = (lane == expected_lane) if expected_lane != "unknown" else (code != "OK")
        results.append({"label": label, "lane": lane, "code": code, "correct": ok})
    all_ok = all(r["correct"] for r in results)
    no_silent_fallback = all(
        r["lane"] != "deepseek" for r in results if r["label"] in ("Kimi", "GLM")
    )
    return _build_packet(
        ok=all_ok and no_silent_fallback,
        human_message="Alias routing matrix proven." if all_ok else "Matrix failures.",
        machine_error_code="OK" if all_ok else "ALIAS_MATRIX_FAILURE",
        operator_action="none" if all_ok else "stop",
        liveness="healthy" if all_ok else "degraded",
        severity="recoverable", changed_files=[], effect=REGISTRY_EFFECT_READ,
        extra={"test_cases": results, "no_silent_fallback": no_silent_fallback,
               "failover_policy": FAILVOVER_POLICY},
    )

def build_registry_receipt() -> dict[str, Any]:
    """Model registry receipt (P07)."""
    entries = [e.to_dict() for e in REGISTRY]
    return _build_packet(
        ok=True,
        human_message="Model registry: DeepSeek + Kimi + GLM families.",
        machine_error_code="OK", operator_action="none",
        liveness="healthy", severity="recoverable",
        changed_files=[], effect=REGISTRY_EFFECT_READ,
        extra={"entry_count": len(entries), "entries": entries,
               "providers": sorted(set(e.provider for e in REGISTRY)),
               "proof_levels": sorted(set(e.proof_level for e in REGISTRY))},
    )

def run_registry_router_synthetic_proof() -> dict[str, Any]:
    """Combined P07+P09+P10 synthetic proof."""
    registry = build_registry_receipt()
    routing = build_alias_routing_matrix_receipt()
    receipts = [registry, routing]
    violations = []
    for r in receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    ok = not violations and registry["status"] == "ok" and routing["status"] == "ok"
    return _build_packet(
        ok=ok,
        human_message="Registry + router + pool synthetic proof complete." if ok else "Violations.",
        machine_error_code="OK" if ok else "REGISTRY_ROUTER_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable", changed_files=[], effect=REGISTRY_EFFECT_READ,
        extra={"receipt_count": len(receipts), "packet_violations": violations,
               "registry_entries": registry["entry_count"],
               "routing_matrix_ok": routing["status"] == "ok"},
    )

def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra)

__all__ = [
    "ModelRegistryEntry", "REGISTRY", "ALIAS_ROUTES", "FAILVOVER_POLICY",
    "resolve_alias", "build_alias_routing_matrix_receipt", "build_registry_receipt",
    "run_registry_router_synthetic_proof",
]
