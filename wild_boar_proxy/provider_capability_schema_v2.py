# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Provider capability schema v2 and GLM/Kimi/Qwen adapters (P00–P04 + B08).

Generalizes the route schema to a capability-aware provider contract and adds
GLM (Z.AI), Kimi (Moonshot), and Qwen (DashScope) as first-class API actors
with deterministic capability proof. DeepSeek is included for the four-
provider release matrix (B08 admits Qwen).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .core import packets as command_packets
from .runtime import build_command_payload

CAPABILITY_EFFECT_READ = "read"

PROVIDER_DEEPSEEK = "deepseek"
PROVIDER_GLM = "glm"
PROVIDER_KIMI = "kimi"
PROVIDER_QWEN = "qwen"
RELEASE_PROVIDERS = (PROVIDER_DEEPSEEK, PROVIDER_GLM, PROVIDER_KIMI, PROVIDER_QWEN)
EXCLUDED_PROVIDERS = ()


@dataclasses.dataclass(frozen=True)
class ProviderCapabilityProfile:
    """Capability-aware provider profile (schema v2).

    Declared capabilities are deterministic; declared != live-verified.
    """
    provider_id: str
    display_name: str
    default_base_url: str
    credential_ref: str
    provider_dashboard_url: str
    capability_text: bool
    capability_stream: bool
    capability_tool: bool
    capability_thinking: bool
    capability_vision: bool
    capability_web_search: bool
    excluded: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


PROVIDER_PROFILES: dict[str, ProviderCapabilityProfile] = {
    PROVIDER_DEEPSEEK: ProviderCapabilityProfile(
        provider_id=PROVIDER_DEEPSEEK,
        display_name="DeepSeek",
        default_base_url="https://api.deepseek.com",
        credential_ref="DEEPSEEK_API_KEY",
        provider_dashboard_url="https://platform.deepseek.com/api_keys",
        capability_text=True, capability_stream=True, capability_tool=True,
        capability_thinking=True, capability_vision=False, capability_web_search=False,
        excluded=False,
    ),
    PROVIDER_GLM: ProviderCapabilityProfile(
        provider_id=PROVIDER_GLM,
        display_name="GLM (Z.AI)",
        default_base_url="https://api.z.ai/api/paas/v4",
        credential_ref="ZAI_API_KEY",
        provider_dashboard_url="https://docs.z.ai",
        capability_text=True, capability_stream=True, capability_tool=True,
        capability_thinking=True, capability_vision=True, capability_web_search=True,
        excluded=False,
    ),
    PROVIDER_KIMI: ProviderCapabilityProfile(
        provider_id=PROVIDER_KIMI,
        display_name="Kimi (Moonshot)",
        default_base_url="https://api.moonshot.cn/v1",
        credential_ref="MOONSHOT_API_KEY",
        provider_dashboard_url="https://platform.moonshot.cn",
        capability_text=True, capability_stream=True, capability_tool=True,
        capability_thinking=False, capability_vision=True, capability_web_search=True,
        excluded=False,
    ),
    PROVIDER_QWEN: ProviderCapabilityProfile(
        provider_id=PROVIDER_QWEN,
        display_name="Qwen",
        default_base_url="https://dashscope.aliyuncs.com",
        credential_ref="DASHSCOPE_API_KEY",
        provider_dashboard_url="https://bailian.console.aliyun.com/?apiKey=1",
        capability_text=True, capability_stream=True, capability_tool=True,
        capability_thinking=True, capability_vision=False, capability_web_search=False,
        excluded=False,
    ),
}


def _build_packet(*, ok, human_message, machine_error_code, operator_action,
                  liveness, severity, changed_files, effect, extra=None):
    return build_command_payload(
        ok=ok, human_message=human_message, machine_error_code=machine_error_code,
        operator_action=operator_action, liveness=liveness, severity=severity,
        changed_files=changed_files, effect=effect, extra=extra,
    )


def build_provider_capability_matrix_receipt() -> dict[str, Any]:
    """Build the three-provider capability matrix receipt (schema v2)."""
    release = {pid: PROVIDER_PROFILES[pid].to_dict() for pid in RELEASE_PROVIDERS}
    excluded = {pid: PROVIDER_PROFILES[pid].to_dict() for pid in EXCLUDED_PROVIDERS}
    extra: dict[str, Any] = {
        "schema_version": 2,
        "release_providers": release,
        "excluded_providers": excluded,
        "release_provider_count": len(RELEASE_PROVIDERS),
        "qwen_excluded": PROVIDER_QWEN in EXCLUDED_PROVIDERS,
        "qwen_admitted": PROVIDER_QWEN in RELEASE_PROVIDERS,
    }
    return _build_packet(
        ok=True,
        human_message="Provider capability schema v2: DeepSeek + GLM + Kimi; Qwen excluded.",
        machine_error_code="OK",
        operator_action="none",
        liveness="healthy",
        severity="recoverable",
        changed_files=[],
        effect=CAPABILITY_EFFECT_READ,
        extra=extra,
    )


def run_provider_v02_synthetic_proof() -> dict[str, Any]:
    """Deterministic three-provider synthetic capability proof."""
    matrix_receipt = build_provider_capability_matrix_receipt()
    # Per-provider profile receipts.
    per_provider: list[dict[str, Any]] = []
    for pid in RELEASE_PROVIDERS:
        p = PROVIDER_PROFILES[pid]
        per_provider.append(_build_packet(
            ok=True,
            human_message=f"{p.display_name} capability profile declared.",
            machine_error_code="OK",
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=CAPABILITY_EFFECT_READ,
            extra={"provider": p.to_dict(), "declared_not_live_verified": True},
        ))
    all_receipts = [matrix_receipt, *per_provider]
    violations: list[str] = []
    for r in all_receipts:
        violations.extend(command_packets.inspect_command_packet_semantics(r))
    no_qwen = all(PROVIDER_PROFILES[pid].excluded for pid in EXCLUDED_PROVIDERS)
    ok = not violations and no_qwen and len(RELEASE_PROVIDERS) == 4
    return _build_packet(
        ok=ok,
        human_message="Provider v0.2.0 synthetic proof complete; DeepSeek+GLM+Kimi+Qwen declared (B08)." if ok else "Violations.",
        machine_error_code="OK" if ok else "PROVIDER_PROOF_VIOLATIONS",
        operator_action="none" if ok else "stop",
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=CAPABILITY_EFFECT_READ,
        extra={
            "receipt_count": len(all_receipts),
            "release_providers": list(RELEASE_PROVIDERS),
            "qwen_excluded": False,
            "qwen_admitted": True,
            "packet_violations": violations,
        },
    )


__all__ = [
    "ProviderCapabilityProfile",
    "PROVIDER_PROFILES",
    "RELEASE_PROVIDERS",
    "EXCLUDED_PROVIDERS",
    "PROVIDER_DEEPSEEK",
    "PROVIDER_GLM",
    "PROVIDER_KIMI",
    "PROVIDER_QWEN",
    "build_provider_capability_matrix_receipt",
    "run_provider_v02_synthetic_proof",
]
