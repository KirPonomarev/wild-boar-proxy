# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import re
from typing import Any
import unicodedata

from .command_effects import EFFECT_PROBE
from .core import packets
from .custom_agent_bindings import API_ROUTE_LANE, PRIMARY_CHATGPT_LANE


NATURAL_INTENT_CONTRACT_PACKET_KIND = "wbp_natural_intent_contract"

SOURCE_SURFACE_TEST_FIXTURE = "test_fixture"
SOURCE_SURFACE_UNKNOWN = "unknown"
SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW = "declared_custom_codex_flow"
SOURCE_SURFACE_CUSTOM_CODEX_FLOW = "custom_codex_flow"
ALLOWED_SOURCE_SURFACES = frozenset(
    {
        SOURCE_SURFACE_TEST_FIXTURE,
        SOURCE_SURFACE_UNKNOWN,
        SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
    }
)

INTENT_PASS = "INTENT_PASS"
NO_ALIAS_DETECTED = "NO_ALIAS_DETECTED"
FAIL_ALIAS_CONTEXT_MISSING = "FAIL_ALIAS_CONTEXT_MISSING"
FAIL_ALIAS_NOT_BOUND = "FAIL_ALIAS_NOT_BOUND"
FAIL_ALIAS_NOT_API_LANE = "FAIL_ALIAS_NOT_API_LANE"
FAIL_ROUTE_NOT_ALLOWED = "FAIL_ROUTE_NOT_ALLOWED"
INTENT_AMBIGUOUS_NO_DISPATCH = "INTENT_AMBIGUOUS_NO_DISPATCH"
FAIL_SOURCE_SURFACE_NOT_ADMITTED = "FAIL_SOURCE_SURFACE_NOT_ADMITTED"
FAIL_PROMPT_EMPTY = "FAIL_PROMPT_EMPTY"

PREFLIGHT_PASS = "PREFLIGHT_PASS"
PREFLIGHT_BLOCKED = "PREFLIGHT_BLOCKED"
DISPATCH_STATUS_NOT_ATTEMPTED = "not_attempted"

RUNTIME_CONTEXT_PACKET_KIND = "codex_custom_native_agent_runtime_context"

_WHITESPACE_RE = re.compile(r"\s+")


def _safe_text(value: object, *, limit: int = 256) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("\r", " ").replace("\n", " ")
    return _WHITESPACE_RE.sub(" ", text).strip()[:limit]


def _safe_list(value: object, *, limit: int = 80, max_items: int = 64) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value[:max_items]:
        text = _safe_text(item, limit=limit)
        if text:
            values.append(text)
    return values


def _alias_key(value: object) -> str:
    return _safe_text(value, limit=80).casefold()


def _normalized_prompt_text(prompt_text: object) -> str:
    return _safe_text(prompt_text, limit=8192)


def _prompt_digest(normalized_prompt: str) -> str:
    return hashlib.sha256(normalized_prompt.encode("utf-8")).hexdigest()


def _context_mapping(runtime_context: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return runtime_context if isinstance(runtime_context, Mapping) else {}


def _context_kind_valid(context: Mapping[str, Any]) -> bool:
    return context.get("packet_kind") == RUNTIME_CONTEXT_PACKET_KIND


def _runtime_context_source(context: Mapping[str, Any]) -> str:
    if not context:
        return "missing"
    return _safe_text(
        context.get("context_truth_source")
        or context.get("agent_binding_truth_source")
        or "unknown",
        limit=80,
    )


def _context_alias_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    alias_to_agent_id: dict[str, str] = {}
    agent_id_to_lane: dict[str, str] = {}
    agent_id_to_route: dict[str, str] = {}
    agent_id_to_model: dict[str, str] = {}
    alias_display: dict[str, str] = {}

    raw_bindings = context.get("agent_bindings")
    bindings = raw_bindings if isinstance(raw_bindings, list) else []
    for raw_binding in bindings:
        if not isinstance(raw_binding, Mapping):
            continue
        if raw_binding.get("enabled") is False:
            continue
        agent_id = _safe_text(raw_binding.get("agent_id"), limit=64)
        lane = _safe_text(raw_binding.get("lane"), limit=32)
        if not agent_id:
            continue
        if lane:
            agent_id_to_lane[agent_id] = lane
        route_id = _safe_text(raw_binding.get("route_id"), limit=80)
        if route_id:
            agent_id_to_route[agent_id] = route_id
        model_id = _safe_text(raw_binding.get("model_id"), limit=80)
        if model_id:
            agent_id_to_model[agent_id] = model_id
        for alias in _safe_list(raw_binding.get("aliases"), limit=80):
            key = _alias_key(alias)
            if key and key not in alias_to_agent_id:
                alias_to_agent_id[key] = agent_id
                alias_display[key] = alias

    raw_alias_to_agent_id = context.get("alias_to_agent_id")
    if isinstance(raw_alias_to_agent_id, Mapping):
        for raw_alias, raw_agent_id in raw_alias_to_agent_id.items():
            alias = _safe_text(raw_alias, limit=80)
            agent_id = _safe_text(raw_agent_id, limit=64)
            key = _alias_key(alias)
            if key and agent_id and key not in alias_to_agent_id:
                alias_to_agent_id[key] = agent_id
                alias_display[key] = alias

    raw_agent_id_to_route = context.get("agent_id_to_route")
    if isinstance(raw_agent_id_to_route, Mapping):
        for raw_agent_id, raw_route_id in raw_agent_id_to_route.items():
            agent_id = _safe_text(raw_agent_id, limit=64)
            route_id = _safe_text(raw_route_id, limit=80)
            if agent_id and route_id:
                agent_id_to_route.setdefault(agent_id, route_id)
                agent_id_to_lane.setdefault(agent_id, API_ROUTE_LANE)

    raw_agent_id_to_model = context.get("agent_id_to_model")
    if isinstance(raw_agent_id_to_model, Mapping):
        for raw_agent_id, raw_model_id in raw_agent_id_to_model.items():
            agent_id = _safe_text(raw_agent_id, limit=64)
            model_id = _safe_text(raw_model_id, limit=80)
            if agent_id and model_id:
                agent_id_to_model.setdefault(agent_id, model_id)
                agent_id_to_lane.setdefault(agent_id, PRIMARY_CHATGPT_LANE)

    return {
        "alias_to_agent_id": alias_to_agent_id,
        "agent_id_to_lane": agent_id_to_lane,
        "agent_id_to_route": agent_id_to_route,
        "agent_id_to_model": agent_id_to_model,
        "alias_display": alias_display,
    }


def _resolve_intent(
    *,
    prompt_present: bool,
    source_surface: str,
    alias_candidate: str,
    runtime_context: Mapping[str, Any],
    ambiguous: bool,
) -> dict[str, Any]:
    source_surface_allowed = source_surface in ALLOWED_SOURCE_SURFACES
    runtime_context_present = bool(runtime_context)
    runtime_context_kind_valid = runtime_context_present and _context_kind_valid(
        runtime_context
    )
    alias_candidate_key = _alias_key(alias_candidate)
    projection = _context_alias_projection(runtime_context)
    allowed_api_route_ids = _safe_list(runtime_context.get("allowed_api_route_ids"))
    forbidden_stale_route_ids = _safe_list(
        runtime_context.get("forbidden_stale_route_ids")
    )
    agent_id = projection["alias_to_agent_id"].get(alias_candidate_key, "")
    lane = projection["agent_id_to_lane"].get(agent_id, "")
    route_id = projection["agent_id_to_route"].get(agent_id, "")
    alias_bound = bool(agent_id)
    route_id_allowed = bool(
        route_id
        and route_id in allowed_api_route_ids
        and route_id not in forbidden_stale_route_ids
    )

    blocking_reasons: list[str] = []
    if not prompt_present:
        intent_status = FAIL_PROMPT_EMPTY
        blocking_reasons.append("prompt_empty")
    elif not source_surface_allowed:
        intent_status = FAIL_SOURCE_SURFACE_NOT_ADMITTED
        blocking_reasons.append("source_surface_not_admitted")
    elif not runtime_context_kind_valid:
        intent_status = FAIL_ALIAS_CONTEXT_MISSING
        blocking_reasons.append("alias_context_missing_or_invalid")
    elif ambiguous:
        intent_status = INTENT_AMBIGUOUS_NO_DISPATCH
        blocking_reasons.append("ambiguous_intent_no_dispatch")
    elif not alias_candidate_key:
        intent_status = NO_ALIAS_DETECTED
        blocking_reasons.append("alias_not_detected")
    elif not alias_bound:
        intent_status = FAIL_ALIAS_NOT_BOUND
        blocking_reasons.append("alias_not_bound_to_runtime_context")
    elif lane != API_ROUTE_LANE:
        intent_status = FAIL_ALIAS_NOT_API_LANE
        blocking_reasons.append("alias_not_bound_to_api_lane")
    elif not route_id_allowed:
        intent_status = FAIL_ROUTE_NOT_ALLOWED
        blocking_reasons.append("route_not_allowed_by_runtime_context")
    else:
        intent_status = INTENT_PASS

    contract_preflight_status = (
        PREFLIGHT_PASS if intent_status == INTENT_PASS else PREFLIGHT_BLOCKED
    )
    return {
        "source_surface_allowed": source_surface_allowed,
        "runtime_context_present": runtime_context_present,
        "runtime_context_kind_valid": runtime_context_kind_valid,
        "allowed_api_route_ids": allowed_api_route_ids,
        "forbidden_stale_route_ids": forbidden_stale_route_ids,
        "alias_bound": alias_bound,
        "alias_candidate_key": alias_candidate_key,
        "alias_display": projection["alias_display"].get(
            alias_candidate_key,
            _safe_text(alias_candidate, limit=80),
        ),
        "slot_candidate": agent_id,
        "lane_candidate": lane,
        "route_candidate": route_id,
        "route_id_allowed": route_id_allowed,
        "intent_status": intent_status,
        "contract_preflight_status": contract_preflight_status,
        "blocking_reasons": blocking_reasons,
    }


def build_natural_intent_contract_packet(
    *,
    prompt_text: object,
    alias_candidate: str = "",
    runtime_context: Mapping[str, Any] | None = None,
    source_surface: str = SOURCE_SURFACE_UNKNOWN,
    ambiguous: bool = False,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a sanitized contract packet for a natural alias intent fixture.

    This intentionally does not parse free text, call API lanes, start Codex,
    or prove Custom Codex origin. The caller supplies fixture-level intent
    candidates; later contours can add a real parser and router hook.
    """

    context = _context_mapping(runtime_context)
    normalized_prompt = _normalized_prompt_text(prompt_text)
    prompt_present = bool(normalized_prompt)
    normalized_source_surface = (
        _safe_text(source_surface, limit=80) or SOURCE_SURFACE_UNKNOWN
    )
    normalized_alias = _safe_text(alias_candidate, limit=80)
    resolved = _resolve_intent(
        prompt_present=prompt_present,
        source_surface=normalized_source_surface,
        alias_candidate=normalized_alias,
        runtime_context=context,
        ambiguous=ambiguous,
    )
    ok = resolved["contract_preflight_status"] == PREFLIGHT_PASS
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "Natural intent contract preflight passed without dispatch."
            if ok
            else "Natural intent contract preflight blocked without dispatch."
        ),
        machine_error_code="OK" if ok else str(resolved["intent_status"]),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra={
            "schema_version": 1,
            "packet_kind": NATURAL_INTENT_CONTRACT_PACKET_KIND,
            "prompt_digest": _prompt_digest(normalized_prompt)
            if prompt_present
            else "",
            "prompt_digest_present": prompt_present,
            "prompt_text_recorded": False,
            "raw_prompt_recorded": False,
            "natural_phrase_recorded": False,
            "source_surface": normalized_source_surface,
            "source_surface_allowed": resolved["source_surface_allowed"],
            "source_surface_observed": False,
            "command_origin_proven": False,
            "custom_codex_flow_observed": False,
            "alias_candidate": normalized_alias,
            "alias_candidate_present": bool(resolved["alias_candidate_key"]),
            "alias_bound": resolved["alias_bound"],
            "slot_candidate": resolved["slot_candidate"],
            "slot_candidate_present": bool(resolved["slot_candidate"]),
            "lane_candidate": resolved["lane_candidate"],
            "route_candidate": resolved["route_candidate"],
            "route_candidate_present": bool(resolved["route_candidate"]),
            "route_id_allowed": resolved["route_id_allowed"],
            "runtime_context_source": _runtime_context_source(context),
            "runtime_context_present": resolved["runtime_context_present"],
            "runtime_context_kind_valid": resolved["runtime_context_kind_valid"],
            "runtime_context_file_required": True,
            "alias_context_read": resolved["runtime_context_kind_valid"],
            "allowed_api_route_ids_enforced": resolved["route_id_allowed"],
            "allowed_api_route_ids_count": len(resolved["allowed_api_route_ids"]),
            "forbidden_stale_route_ids_count": len(
                resolved["forbidden_stale_route_ids"]
            ),
            "ambiguous_intent": bool(ambiguous),
            "intent_status": resolved["intent_status"],
            "contract_preflight_status": resolved["contract_preflight_status"],
            "dispatch_status": DISPATCH_STATUS_NOT_ATTEMPTED,
            "api_lane_called": False,
            "dispatch_proven": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "native_codex_subagent_used": False,
            "native_codex_subagent_used_as_dip": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_dispatch": True,
            "does_not_prove_native_free_chat_router": True,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "browser_can_supply_route_authority": False,
            "blocking_reasons": resolved["blocking_reasons"],
        },
    )


def packet_contains_text(packet: Mapping[str, Any], text: str) -> bool:
    needle = str(text or "")
    if not needle:
        return False
    encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    return needle in encoded
