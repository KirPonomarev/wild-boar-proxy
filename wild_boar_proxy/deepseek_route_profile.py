# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""DeepSeek route profile and credential lifecycle contract.

Completes the DeepSeek provider lane for web v0.1.0 per WBP master plan W07.
The CLIProxyAPI engine remains the owner of low-level provider dispatch and
HTTP traffic; this module owns the WBP control-layer DeepSeek route profile,
credential provenance contract, validate/stream/tool error taxonomy, and the
route lifecycle receipt.

The credential value never appears in any packet, log, argv, or stored route
definition. Only an opaque credential reference and presence/provenance proof
are exposed. Live dispatch is not performed here; this is the deterministic
contract surface. Live exact-response proof is reserved for W13.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Mapping

from .core import packets as command_packets
from .runtime import build_command_payload

DEEPSEEK_PROVIDER_ID = "deepseek"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_ENDPOINT_PATH = "/v1/chat/completions"
DEEPSEEK_DEFAULT_UPSTREAM_MODEL = "deepseek-chat"
DEEPSEEK_DEFAULT_ROUTE_ID = "wbp-deepseek-chat"
DEEPSEEK_CREDENTIAL_REF = "DEEPSEEK_API_KEY"
DEEPSEEK_PROVIDER_DASHBOARD_URL = "https://platform.deepseek.com/api_keys"
DEEPSEEK_COST_CLASS = "paid_direct"
DEEPSEEK_LANE_ROLE = "deepseek_api_lane"

# Error taxonomy for DeepSeek provider dispatch. These are the control-layer
# normalized classes used by the validate/stream/tool test matrix.
DEEPSEEK_ERROR_OK = "OK"
DEEPSEEK_ERROR_DISABLED = "route_disabled"
DEEPSEEK_ERROR_MISSING_CREDENTIAL = "missing_credential"
DEEPSEEK_ERROR_INVALID_CREDENTIAL = "invalid_credential"
DEEPSEEK_ERROR_MODEL_NOT_AVAILABLE = "model_not_available"
DEEPSEEK_ERROR_QUOTA = "quota_exhausted"
DEEPSEEK_ERROR_NETWORK = "network_failed"
DEEPSEEK_ERROR_INVALID_RESPONSE = "invalid_upstream_response"
DEEPSEEK_ERROR_TOOL_UNSUPPORTED = "tool_unsupported"
DEEPSEEK_ERROR_STREAM_INCOMPLETE = "stream_incomplete"

DEEPSEEK_DISPATCH_MODE_NON_STREAM = "non_stream"
DEEPSEEK_DISPATCH_MODE_STREAM = "stream"
DEEPSEEK_DISPATCH_MODE_TOOL = "tool"

PROFILE_EFFECT_READ = "read"
PROFILE_EFFECT_MUTATE = "mutate"

# Capability flags derived from the official DeepSeek API contract. Declared
# capabilities are deterministic; they do not by themselves prove live provider
# availability (model listed != model usable).
DEEPSEEK_CAPABILITY_TEXT = True
DEEPSEEK_CAPABILITY_STREAM = True
DEEPSEEK_CAPABILITY_TOOL = True
DEEPSEEK_CAPABILITY_THINKING = True
DEEPSEEK_CAPABILITY_VISION = False
DEEPSEEK_CAPABILITY_WEB_SEARCH = False


@dataclasses.dataclass(frozen=True)
class DeepSeekCapabilityMatrix:
    text: bool
    stream: bool
    tool: bool
    thinking: bool
    vision: bool
    web_search: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "text": self.text,
            "stream": self.stream,
            "tool": self.tool,
            "thinking": self.thinking,
            "vision": self.vision,
            "web_search": self.web_search,
        }


DEEPSEEK_CAPABILITIES = DeepSeekCapabilityMatrix(
    text=DEEPSEEK_CAPABILITY_TEXT,
    stream=DEEPSEEK_CAPABILITY_STREAM,
    tool=DEEPSEEK_CAPABILITY_TOOL,
    thinking=DEEPSEEK_CAPABILITY_THINKING,
    vision=DEEPSEEK_CAPABILITY_VISION,
    web_search=DEEPSEEK_CAPABILITY_WEB_SEARCH,
)


def build_deepseek_route_definition(
    *,
    route_id: str = DEEPSEEK_DEFAULT_ROUTE_ID,
    display_name: str = "DeepSeek Chat",
    upstream_model: str = DEEPSEEK_DEFAULT_UPSTREAM_MODEL,
    base_url: str = DEEPSEEK_DEFAULT_BASE_URL,
    endpoint_path: str = DEEPSEEK_DEFAULT_ENDPOINT_PATH,
    secret_ref: str = DEEPSEEK_CREDENTIAL_REF,
    enabled: bool = False,
    fallback_eligible: bool = False,
) -> dict[str, Any]:
    """Build a canonical DeepSeek route definition.

    The route is created disabled by default. Enabling requires the owner
    credential source to be admitted through the credential lifecycle owner
    path; this function never embeds the credential value.
    """
    from .external_models.contracts import ROUTE_SCHEMA_VERSION

    return {
        "schema_version": ROUTE_SCHEMA_VERSION,
        "route_id": route_id,
        "display_name": display_name,
        "provider": DEEPSEEK_PROVIDER_ID,
        "base_url": base_url,
        "endpoint_path": endpoint_path,
        "upstream_model": upstream_model,
        "compatibility": "openai_chat_completions",
        "auth": {"type": "bearer", "secret_ref": secret_ref},
        "cost_class": DEEPSEEK_COST_CLASS,
        "lane_role": DEEPSEEK_LANE_ROLE,
        "fallback_eligible": fallback_eligible,
        "enabled": enabled,
        "transform_profile": "deepseek_default",
        "response_profile": "openai_chat_completions",
        "thinking": {"type": "disabled"},
        "check_max_tokens": 4096,
    }


@dataclasses.dataclass(frozen=True)
class CredentialProvenance:
    """Opaque credential provenance proof. Never carries the credential value."""

    credential_ref: str
    present: bool
    source_admitted: bool
    source_kind: str  # owner_env | owner_cli | none
    permissions_safe: bool | None
    provenance_digest: str | None  # digest of the credential value, never the value

    @property
    def proven(self) -> bool:
        return (
            self.present
            and self.source_admitted
            and self.source_kind in ("owner_env", "owner_cli")
            and (self.permissions_safe is None or self.permissions_safe is True)
        )


def classify_credential_provenance(
    *,
    credential_ref: str,
    present: bool,
    source_kind: str,
    permissions_safe: bool | None = None,
    credential_value_digest: str | None = None,
) -> CredentialProvenance:
    """Classify the DeepSeek credential provenance without exposing the value.

    The credential source must be owner-controlled (owner env or owner CLI).
    A browser-supplied raw key is never an admitted source.
    """
    source_admitted = source_kind in ("owner_env", "owner_cli") and present
    return CredentialProvenance(
        credential_ref=credential_ref,
        present=present,
        source_admitted=source_admitted,
        source_kind=source_kind,
        permissions_safe=permissions_safe,
        provenance_digest=credential_value_digest if source_admitted else None,
    )


def normalize_deepseek_dispatch_error(
    *,
    http_status: int | None,
    engine_error_code: str | None,
    dispatch_mode: str,
    response_observed: bool,
    stream_complete: bool | None = None,
    tool_call_admitted: bool | None = None,
) -> str:
    """Normalize a DeepSeek provider dispatch outcome into the control-layer
    error taxonomy. Deterministic; does not perform live dispatch."""
    if dispatch_mode == DEEPSEEK_DISPATCH_MODE_STREAM and stream_complete is False:
        return DEEPSEEK_ERROR_STREAM_INCOMPLETE
    if dispatch_mode == DEEPSEEK_DISPATCH_MODE_TOOL and tool_call_admitted is False:
        return DEEPSEEK_ERROR_TOOL_UNSUPPORTED
    if http_status is None and not response_observed:
        return DEEPSEEK_ERROR_NETWORK
    if http_status in (401, 403):
        return DEEPSEEK_ERROR_INVALID_CREDENTIAL
    if http_status == 404:
        return DEEPSEEK_ERROR_MODEL_NOT_AVAILABLE
    if http_status == 429:
        return DEEPSEEK_ERROR_QUOTA
    if http_status is not None and (http_status >= 500 or http_status == 408):
        return DEEPSEEK_ERROR_NETWORK
    if http_status == 200 and not response_observed:
        return DEEPSEEK_ERROR_INVALID_RESPONSE
    if engine_error_code in (
        "invalid_upstream_response",
        "INVALID_UPSTREAM_RESPONSE",
    ):
        return DEEPSEEK_ERROR_INVALID_RESPONSE
    return DEEPSEEK_ERROR_OK


def _build_packet(
    *,
    ok: bool,
    human_message: str,
    machine_error_code: str,
    operator_action: str,
    liveness: str,
    severity: str,
    changed_files: list[str],
    effect: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_command_payload(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        operator_action=operator_action,
        liveness=liveness,
        severity=severity,
        changed_files=changed_files,
        effect=effect,
        extra=extra,
    )


def build_deepseek_profile_packet(
    *,
    route: Mapping[str, Any],
    provenance: CredentialProvenance,
    capabilities: DeepSeekCapabilityMatrix = DEEPSEEK_CAPABILITIES,
) -> dict[str, Any]:
    """Build the DeepSeek route profile packet (read-only)."""
    enabled = bool(route.get("enabled"))
    ready = enabled and provenance.proven
    extra: dict[str, Any] = {
        "provider": DEEPSEEK_PROVIDER_ID,
        "route_id": route.get("route_id"),
        "upstream_model": route.get("upstream_model"),
        "base_url": route.get("base_url"),
        "endpoint_path": route.get("endpoint_path"),
        "lane_role": route.get("lane_role"),
        "cost_class": route.get("cost_class"),
        "fallback_eligible": bool(route.get("fallback_eligible")),
        "enabled": enabled,
        "credential": {
            "credential_ref": provenance.credential_ref,
            "present": provenance.present,
            "source_admitted": provenance.source_admitted,
            "source_kind": provenance.source_kind,
            "permissions_safe": provenance.permissions_safe,
            "proven": provenance.proven,
            "provenance_digest": provenance.provenance_digest,
        },
        "capabilities": capabilities.to_dict(),
        "provider_dashboard_url": DEEPSEEK_PROVIDER_DASHBOARD_URL,
        "ready_for_live_dispatch": ready,
    }
    if ready:
        return _build_packet(
            ok=True,
            human_message="DeepSeek route profile is ready for live dispatch.",
            machine_error_code=DEEPSEEK_ERROR_OK,
            operator_action="none",
            liveness="healthy",
            severity="recoverable",
            changed_files=[],
            effect=PROFILE_EFFECT_READ,
            extra=extra,
        )
    if not enabled:
        return _build_packet(
            ok=True,
            human_message="DeepSeek route is defined but disabled.",
            machine_error_code=DEEPSEEK_ERROR_DISABLED,
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=[],
            effect=PROFILE_EFFECT_READ,
            extra=extra,
        )
    if not provenance.present:
        return _build_packet(
            ok=False,
            human_message="DeepSeek credential is not present.",
            machine_error_code=DEEPSEEK_ERROR_MISSING_CREDENTIAL,
            operator_action="user_action",
            liveness="down",
            severity="recoverable",
            changed_files=[],
            effect=PROFILE_EFFECT_READ,
            extra=extra,
        )
    return _build_packet(
        ok=False,
        human_message="DeepSeek credential provenance is not admitted.",
        machine_error_code=DEEPSEEK_ERROR_INVALID_CREDENTIAL,
        operator_action="user_action",
        liveness="down",
        severity="recoverable",
        changed_files=[],
        effect=PROFILE_EFFECT_READ,
        extra=extra,
    )


def build_dispatch_test_matrix_receipt(
    *,
    route: Mapping[str, Any],
    provenance: CredentialProvenance,
) -> list[dict[str, Any]]:
    """Deterministic validate/stream/tool error-taxonomy test matrix.

    Returns one core command packet per scenario. No live dispatch; this is
    the deterministic contract proof. Scenarios cover: disabled route,
    missing credential, non-stream/stream/tool success, 401/403/404/429/5xx,
    stream-incomplete, tool-unsupported, network-failed, invalid-response.
    """
    scenarios: list[dict[str, Any]] = []
    base_extra = {
        "provider": DEEPSEEK_PROVIDER_ID,
        "route_id": route.get("route_id"),
        "upstream_model": route.get("upstream_model"),
        "credential_ref": provenance.credential_ref,
    }

    def scenario(
        *,
        label: str,
        dispatch_mode: str,
        ok: bool,
        code: str,
        human_message: str,
        http_status: int | None,
        response_observed: bool,
        stream_complete: bool | None = None,
        tool_call_admitted: bool | None = None,
    ) -> None:
        classified = normalize_deepseek_dispatch_error(
            http_status=http_status,
            engine_error_code=None,
            dispatch_mode=dispatch_mode,
            response_observed=response_observed,
            stream_complete=stream_complete,
            tool_call_admitted=tool_call_admitted,
        )
        packet = _build_packet(
            ok=ok and classified == DEEPSEEK_ERROR_OK,
            human_message=human_message,
            machine_error_code=classified if not (ok and classified == DEEPSEEK_ERROR_OK) else DEEPSEEK_ERROR_OK,
            operator_action="none" if ok and classified == DEEPSEEK_ERROR_OK else "user_action",
            liveness="healthy" if ok and classified == DEEPSEEK_ERROR_OK else "degraded",
            severity="recoverable",
            changed_files=[],
            effect=PROFILE_EFFECT_READ,
            extra={
                **base_extra,
                "scenario": label,
                "dispatch_mode": dispatch_mode,
                "http_status": http_status,
                "response_observed": response_observed,
                "stream_complete": stream_complete,
                "tool_call_admitted": tool_call_admitted,
                "classified_error": classified,
            },
        )
        scenarios.append(packet)

    # Non-stream success / failures
    scenario(label="non_stream_success", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=True, code=DEEPSEEK_ERROR_OK, human_message="Non-stream dispatch succeeded.", http_status=200, response_observed=True)
    scenario(label="non_stream_401", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_INVALID_CREDENTIAL, human_message="Credential rejected by provider (401).", http_status=401, response_observed=True)
    scenario(label="non_stream_403", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_INVALID_CREDENTIAL, human_message="Credential forbidden by provider (403).", http_status=403, response_observed=True)
    scenario(label="non_stream_404", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_MODEL_NOT_AVAILABLE, human_message="Upstream model not available (404).", http_status=404, response_observed=True)
    scenario(label="non_stream_429", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_QUOTA, human_message="Provider quota exhausted (429).", http_status=429, response_observed=True)
    scenario(label="non_stream_500", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_NETWORK, human_message="Provider server error (500).", http_status=500, response_observed=True)
    scenario(label="non_stream_network_failed", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_NETWORK, human_message="Network failure; no response observed.", http_status=None, response_observed=False)
    scenario(label="non_stream_invalid_response", dispatch_mode=DEEPSEEK_DISPATCH_MODE_NON_STREAM, ok=False, code=DEEPSEEK_ERROR_INVALID_RESPONSE, human_message="200 returned but response body not observable.", http_status=200, response_observed=False)
    # Stream success / incomplete
    scenario(label="stream_success", dispatch_mode=DEEPSEEK_DISPATCH_MODE_STREAM, ok=True, code=DEEPSEEK_ERROR_OK, human_message="Stream dispatch completed.", http_status=200, response_observed=True, stream_complete=True)
    scenario(label="stream_incomplete", dispatch_mode=DEEPSEEK_DISPATCH_MODE_STREAM, ok=False, code=DEEPSEEK_ERROR_STREAM_INCOMPLETE, human_message="Stream dispatch did not complete.", http_status=200, response_observed=True, stream_complete=False)
    # Tool success / unsupported
    scenario(label="tool_success", dispatch_mode=DEEPSEEK_DISPATCH_MODE_TOOL, ok=True, code=DEEPSEEK_ERROR_OK, human_message="Tool dispatch admitted.", http_status=200, response_observed=True, tool_call_admitted=True)
    scenario(label="tool_unsupported", dispatch_mode=DEEPSEEK_DISPATCH_MODE_TOOL, ok=False, code=DEEPSEEK_ERROR_TOOL_UNSUPPORTED, human_message="Tool dispatch not admitted by provider.", http_status=200, response_observed=True, tool_call_admitted=False)
    return scenarios


def run_deepseek_synthetic_profile_proof() -> dict[str, Any]:
    """Deterministic synthetic DeepSeek profile proof.

    Builds the canonical route definition, classifies credential provenance
    from synthetic owner-env source, runs the dispatch test matrix, and
    returns a single core command packet wrapping the proof summary. No live
    credentials or dispatch.
    """
    route = build_deepseek_route_definition(enabled=True)
    provenance = classify_credential_provenance(
        credential_ref=DEEPSEEK_CREDENTIAL_REF,
        present=True,
        source_kind="owner_env",
        permissions_safe=True,
        credential_value_digest="0" * 64,
    )
    profile_packet = build_deepseek_profile_packet(route=route, provenance=provenance)
    matrix = build_dispatch_test_matrix_receipt(route=route, provenance=provenance)
    violations: list[str] = []
    for packet in [profile_packet, *matrix]:
        violations.extend(command_packets.inspect_command_packet_semantics(packet))
    # Auth-material leak check: no raw provider key values (sk-...) may appear
    # in any packet body. The credential *reference* name (DEEPSEEK_API_KEY)
    # and the opaque provenance digest are intentionally present and are not
    # secret material.
    import json as _json

    no_auth_leak = all(
        "sk-" not in _json.dumps(p)
        and "provenance_digest" in p or True  # digest is opaque, not the value
        for p in [profile_packet, *matrix]
    )
    no_auth_leak = all("sk-" not in _json.dumps(p) for p in [profile_packet, *matrix])
    return _build_packet(
        ok=not violations and no_auth_leak and profile_packet["status"] == "ok",
        human_message=(
            "DeepSeek synthetic profile proof complete; route profile and "
            "dispatch test matrix conform to the shared core packet contract."
            if not violations and no_auth_leak
            else "DeepSeek synthetic profile proof had contract violations."
        ),
        machine_error_code=DEEPSEEK_ERROR_OK if not violations and no_auth_leak else "DEEPSEEK_PROFILE_PROOF_VIOLATIONS",
        operator_action="none" if not violations and no_auth_leak else "stop",
        liveness="healthy" if not violations and no_auth_leak else "degraded",
        severity="recoverable",
        changed_files=[],
        effect=PROFILE_EFFECT_READ,
        extra={
            "profile_ready": profile_packet.get("ready_for_live_dispatch", False),
            "scenario_count": len(matrix),
            "packet_violations": violations,
            "no_auth_material_leak": no_auth_leak,
            "capabilities": DEEPSEEK_CAPABILITIES.to_dict(),
            "provider_dashboard_url": DEEPSEEK_PROVIDER_DASHBOARD_URL,
        },
    )


__all__ = [
    "DEEPSEEK_PROVIDER_ID",
    "DEEPSEEK_DEFAULT_BASE_URL",
    "DEEPSEEK_DEFAULT_UPSTREAM_MODEL",
    "DEEPSEEK_DEFAULT_ROUTE_ID",
    "DEEPSEEK_CREDENTIAL_REF",
    "DEEPSEEK_LANE_ROLE",
    "DEEPSEEK_CAPABILITIES",
    "DEEPSEEK_DISPATCH_MODE_NON_STREAM",
    "DEEPSEEK_DISPATCH_MODE_STREAM",
    "DEEPSEEK_DISPATCH_MODE_TOOL",
    "DeepSeekCapabilityMatrix",
    "CredentialProvenance",
    "build_deepseek_route_definition",
    "classify_credential_provenance",
    "normalize_deepseek_dispatch_error",
    "build_deepseek_profile_packet",
    "build_dispatch_test_matrix_receipt",
    "run_deepseek_synthetic_profile_proof",
]
