# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Mapping
import unicodedata

from .runtime import write_text_atomic


AGENT_BINDINGS_SCHEMA_VERSION = 1
AGENT_BINDINGS_FILENAME = "custom-agent-bindings.json"
AGENT_BINDINGS_PACKET_KIND = "codex_custom_agent_bindings"
RUNTIME_CONTEXT_BINDINGS_SOURCE = "server_owned_agent_bindings"
PRIMARY_CHATGPT_LANE = "primary_chatgpt"
API_ROUTE_LANE = "api_route"
ALLOWED_AGENT_LANES = {PRIMARY_CHATGPT_LANE, API_ROUTE_LANE}
ALLOWED_AGENT_BINDING_FIELDS = {
    "agent_id",
    "display_name",
    "role",
    "aliases",
    "lane",
    "enabled",
    "allowed_actions",
    "model_id",
    "route_id",
}
FORBIDDEN_AGENT_BINDING_FIELDS = {
    "backend",
    "backend_id",
    "base_url",
    "endpoint",
    "endpoint_path",
    "provider_base_url",
    "raw_backend",
    "secret",
    "secret_ref",
    "token",
}
FORBIDDEN_STALE_ROUTE_IDS = {"wbp-deepseek-v3"}
DEFAULT_PRIMARY_AGENT_ID = "codex"
DEFAULT_CODING_AGENT_ID = "dip"
TEXT_FIELD_LIMITS = {
    "agent_id": 64,
    "display_name": 80,
    "role": 64,
    "lane": 32,
    "model_id": 80,
    "route_id": 80,
    "alias": 80,
    "allowed_action": 64,
}
FORBIDDEN_TEXT_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}
WHITESPACE_RE = re.compile(r"\s+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def agent_bindings_state_path(managed_dir: Path) -> Path:
    return managed_dir / AGENT_BINDINGS_FILENAME


def _normalize_visible_text(value: object, *, collapse_whitespace: bool = True) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r", " ").replace("\n", " ")
    if collapse_whitespace:
        text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _has_forbidden_text_codepoint(text: str) -> bool:
    return any(unicodedata.category(character) in FORBIDDEN_TEXT_CATEGORIES for character in text)


def _canonical_alias_key(value: object) -> str:
    return _normalize_visible_text(value).casefold()


def default_agent_bindings(
    *,
    primary_model_id: str,
    api_route_id: str,
    additional_api_routes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build default agent bindings.

    additional_api_routes: list of {route_id, display_name, aliases, role}
    for Kimi, GLM, or other API providers beyond the default DIP route.
    """
    primary_model_id = str(primary_model_id or "").strip()
    api_route_id = str(api_route_id or "").strip()
    bindings: list[dict[str, Any]] = [
        {
            "agent_id": DEFAULT_PRIMARY_AGENT_ID,
            "display_name": "Codex",
            "role": "orchestrator",
            "aliases": ["Codex", "Agent 1", "1"],
            "lane": PRIMARY_CHATGPT_LANE,
            "model_id": primary_model_id,
            "enabled": True,
            "allowed_actions": ["plan", "inspect", "patch", "verify"],
        }
    ]
    if api_route_id:
        bindings.append(
            {
                "agent_id": DEFAULT_CODING_AGENT_ID,
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": ["DIP", "Agent 2", "2"],
                "lane": API_ROUTE_LANE,
                "route_id": api_route_id,
                "enabled": True,
                "allowed_actions": [
                    "code_review",
                    "implementation_help",
                    "format_check",
                ],
            }
        )
    # Additional API providers (Kimi, GLM, etc.)
    if additional_api_routes:
        for idx, route_info in enumerate(additional_api_routes, start=3):
            route_id = str(route_info.get("route_id") or "").strip()
            if not route_id:
                continue
            display_name = str(route_info.get("display_name") or f"Agent {idx}").strip()
            aliases_raw = route_info.get("aliases") or [display_name, f"Agent {idx}", str(idx)]
            if isinstance(aliases_raw, str):
                aliases_raw = [aliases_raw]
            role = str(route_info.get("role") or "coding_agent").strip()
            bindings.append(
                {
                    "agent_id": f"agent_{idx}",
                    "display_name": display_name,
                    "role": role,
                    "aliases": list(aliases_raw),
                    "lane": API_ROUTE_LANE,
                    "route_id": route_id,
                    "enabled": True,
                    "allowed_actions": [
                        "code_review",
                        "implementation_help",
                        "format_check",
                    ],
                }
            )
    return bindings

# Convenience: default additional routes for Kimi and GLM
def kimi_glm_additional_routes(
    *,
    kimi_route_id: str = "wbp-kimi-primary",
    glm_route_id: str = "wbp-glm-primary",
) -> list[dict[str, Any]]:
    """Build additional_api_routes for Kimi and GLM providers."""
    routes: list[dict[str, Any]] = []
    if kimi_route_id:
        routes.append({
            "route_id": kimi_route_id,
            "display_name": "Kimi",
            "aliases": ["Kimi"],
            "role": "coding_agent",
        })
    if glm_route_id:
        routes.append({
            "route_id": glm_route_id,
            "display_name": "GLM",
            "aliases": ["GLM"],
            "role": "coding_agent",
        })
    return routes


def kimi_glm_additional_routes_from_records(
    route_records: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    primary_api_route_id: str = "",
) -> list[dict[str, Any]]:
    """Project enabled Kimi/GLM route records into extra alias bindings.

    The first/primary API route remains the canonical DIP binding. This helper
    only admits additional Kimi/GLM routes that are already present in the
    server-owned route registry, so default bindings cannot invent a live lane.
    """
    primary_api_route_id = str(primary_api_route_id or "").strip()
    additional: list[dict[str, Any]] = []
    seen_route_ids: set[str] = set()
    for route in route_records:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        if not route_id or route_id == primary_api_route_id or route_id in seen_route_ids:
            continue
        if route.get("enabled") is not True:
            continue
        provider = str(route.get("provider") or "").strip().lower()
        if provider in {"kimi", "moonshot"}:
            display_name = str(route.get("display_name") or "Kimi").strip() or "Kimi"
            aliases = [display_name]
            if display_name.casefold() != "kimi":
                aliases.append("Kimi")
        elif provider in {"glm", "zai", "zhipu"}:
            display_name = str(route.get("display_name") or "GLM").strip() or "GLM"
            aliases = [display_name]
            if display_name.casefold() != "glm":
                aliases.append("GLM")
        else:
            continue
        additional.append(
            {
                "route_id": route_id,
                "display_name": display_name,
                "aliases": aliases,
                "role": str(route.get("lane_role") or "coding_agent").strip()
                or "coding_agent",
            }
        )
        seen_route_ids.add(route_id)
    return additional


def _safe_text(value: object, *, max_length: int = 96) -> str:
    text = _normalize_visible_text(value)
    return text[:max_length]


def _safe_id(value: object) -> str:
    text = _safe_text(value, max_length=64).lower()
    return "".join(character for character in text if character.isalnum() or character in {"-", "_"})


def _safe_list(raw: object, *, max_items: int = 20, max_length: int = 96) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw[:max_items]:
        text = _safe_text(item, max_length=max_length)
        if text:
            values.append(text)
    return values


def _letter_script_family(character: str) -> str:
    if not character.isalpha():
        return ""
    name = unicodedata.name(character, "")
    for family in ("LATIN", "CYRILLIC", "GREEK"):
        if family in name:
            return family.lower()
    return "other"


def _has_mixed_confusable_alias_scripts(text: str) -> bool:
    for token in re.findall(r"[\w]+", text, flags=re.UNICODE):
        families = {
            family
            for family in (_letter_script_family(character) for character in token)
            if family in {"latin", "cyrillic", "greek"}
        }
        if "latin" in families and bool(families & {"cyrillic", "greek"}):
            return True
    return False


def _route_records_by_id(
    route_records: list[dict[str, Any]],
    *,
    enabled_only: bool = True,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for route in route_records:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        if enabled_only and route.get("enabled") is not True:
            continue
        if route_id:
            records[route_id] = route
    return records


def _primary_model_ids(primary_model_ids: list[str] | tuple[str, ...] | set[str]) -> set[str]:
    return {
        _normalize_visible_text(model_id)
        for model_id in primary_model_ids
        if _normalize_visible_text(model_id)
    }


def _text_field_reasons(
    raw: Mapping[str, Any],
    field: str,
    index: int,
    *,
    required: bool = False,
) -> list[str]:
    if field not in raw:
        return [f"binding_{index}_{field}_missing"] if required else []
    value = raw.get(field)
    if not isinstance(value, str):
        return [f"binding_{index}_{field}_not_string"]
    normalized = _normalize_visible_text(value)
    reasons: list[str] = []
    if _has_forbidden_text_codepoint(value):
        reasons.append(f"binding_{index}_{field}_forbidden_codepoint")
    if required and not normalized:
        reasons.append(f"binding_{index}_{field}_missing")
    if len(normalized) > TEXT_FIELD_LIMITS[field]:
        reasons.append(f"binding_{index}_{field}_too_long")
    return reasons


def _list_field_reasons(
    raw: Mapping[str, Any],
    field: str,
    index: int,
    *,
    item_name: str,
    max_items: int,
) -> list[str]:
    if field not in raw:
        return []
    values = raw.get(field)
    if not isinstance(values, list):
        return [f"binding_{index}_{field}_not_list"]
    reasons: list[str] = []
    if len(values) > max_items:
        reasons.append(f"binding_{index}_{field}_too_many")
    for item_index, value in enumerate(values[:max_items]):
        if not isinstance(value, str):
            reasons.append(f"binding_{index}_{item_name}_{item_index}_not_string")
            continue
        normalized = _normalize_visible_text(value)
        if _has_forbidden_text_codepoint(value):
            reasons.append(f"binding_{index}_{item_name}_{item_index}_forbidden_codepoint")
        if not normalized:
            reasons.append(f"binding_{index}_{item_name}_{item_index}_empty")
        if len(normalized) > TEXT_FIELD_LIMITS[item_name]:
            reasons.append(f"binding_{index}_{item_name}_{item_index}_too_long")
    return reasons


def _binding_from_raw(raw: Mapping[str, Any]) -> dict[str, Any]:
    lane = _safe_text(raw.get("lane"), max_length=32)
    binding: dict[str, Any] = {
        "agent_id": _safe_id(raw.get("agent_id")),
        "display_name": _safe_text(raw.get("display_name"), max_length=80),
        "role": _safe_text(raw.get("role"), max_length=64),
        "aliases": _safe_list(raw.get("aliases"), max_items=24, max_length=80),
        "lane": lane,
        "enabled": raw.get("enabled") is not False,
        "allowed_actions": _safe_list(raw.get("allowed_actions"), max_items=24, max_length=64),
    }
    if lane == PRIMARY_CHATGPT_LANE:
        binding["model_id"] = _safe_text(raw.get("model_id"), max_length=80)
    if lane == API_ROUTE_LANE:
        binding["route_id"] = _safe_text(raw.get("route_id"), max_length=80)
    return binding


def validate_agent_bindings(
    raw_bindings: object,
    *,
    primary_model_ids: list[str] | tuple[str, ...] | set[str] = (),
    route_records: list[dict[str, Any]] | None = None,
    require_api_route_binding: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw_bindings, list):
        return _validation_packet(
            status="rejected",
            machine_error_code="CUSTOM_AGENT_BINDINGS_NOT_LIST",
            normalized_bindings=[],
            blocking_reasons=["agent_bindings_not_list"],
        )
    route_records = route_records or []
    all_routes_by_id = _route_records_by_id(route_records, enabled_only=False)
    routes_by_id = _route_records_by_id(route_records, enabled_only=True)
    available_route_ids = sorted(routes_by_id)
    available_primary_model_ids = _primary_model_ids(primary_model_ids)
    normalized: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    seen_agent_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for index, raw in enumerate(raw_bindings):
        if not isinstance(raw, Mapping):
            blocking_reasons.append(f"binding_{index}_not_object")
            continue
        unknown_fields = sorted(set(raw) - ALLOWED_AGENT_BINDING_FIELDS)
        if unknown_fields:
            blocking_reasons.append(f"binding_{index}_unknown_fields")
        forbidden_fields = sorted(set(raw) & FORBIDDEN_AGENT_BINDING_FIELDS)
        if forbidden_fields:
            blocking_reasons.append(f"binding_{index}_forbidden_fields")
        for field in ("agent_id", "display_name", "role", "lane"):
            blocking_reasons.extend(
                _text_field_reasons(
                    raw,
                    field,
                    index,
                    required=field in {"agent_id", "display_name", "lane"},
                )
            )
        blocking_reasons.extend(
            _list_field_reasons(
                raw,
                "aliases",
                index,
                item_name="alias",
                max_items=24,
            )
        )
        blocking_reasons.extend(
            _list_field_reasons(
                raw,
                "allowed_actions",
                index,
                item_name="allowed_action",
                max_items=24,
            )
        )
        if "enabled" in raw and not isinstance(raw.get("enabled"), bool):
            blocking_reasons.append(f"binding_{index}_enabled_not_bool")
        binding = _binding_from_raw(raw)
        agent_id = str(binding.get("agent_id") or "")
        lane = str(binding.get("lane") or "")
        aliases = list(binding.get("aliases") or [])
        if not agent_id:
            blocking_reasons.append(f"binding_{index}_agent_id_missing")
        elif agent_id in seen_agent_ids:
            blocking_reasons.append(f"binding_{index}_agent_id_duplicate")
        if agent_id:
            seen_agent_ids.add(agent_id)
        if not binding.get("display_name"):
            blocking_reasons.append(f"binding_{index}_display_name_missing")
        if lane not in ALLOWED_AGENT_LANES:
            blocking_reasons.append(f"binding_{index}_lane_unknown")
        if not aliases:
            blocking_reasons.append(f"binding_{index}_aliases_missing")
        for alias in aliases:
            alias_key = _canonical_alias_key(alias)
            if _has_mixed_confusable_alias_scripts(alias):
                blocking_reasons.append(f"alias_confusable_mixed_script:{alias}")
            if alias_key in seen_aliases:
                blocking_reasons.append(f"alias_duplicate:{alias}")
            else:
                seen_aliases[alias_key] = agent_id
        if lane == PRIMARY_CHATGPT_LANE:
            if "route_id" in raw:
                blocking_reasons.append(f"binding_{index}_route_id_wrong_lane")
            blocking_reasons.extend(
                _text_field_reasons(raw, "model_id", index, required=True)
            )
            model_id = str(binding.get("model_id") or "")
            if not model_id:
                blocking_reasons.append(f"binding_{index}_model_id_missing")
            elif available_primary_model_ids and model_id not in available_primary_model_ids:
                blocking_reasons.append(f"binding_{index}_model_id_not_server_issued")
        if lane == API_ROUTE_LANE:
            if "model_id" in raw:
                blocking_reasons.append(f"binding_{index}_model_id_wrong_lane")
            blocking_reasons.extend(
                _text_field_reasons(raw, "route_id", index, required=True)
            )
            route_id = str(binding.get("route_id") or "")
            if not route_id:
                blocking_reasons.append(f"binding_{index}_route_id_missing")
            elif route_id in FORBIDDEN_STALE_ROUTE_IDS:
                blocking_reasons.append(f"binding_{index}_route_id_stale")
            elif route_id in all_routes_by_id and route_id not in routes_by_id:
                blocking_reasons.append(f"binding_{index}_route_id_disabled")
            elif not routes_by_id:
                blocking_reasons.append(f"binding_{index}_route_registry_unavailable")
            elif route_id not in routes_by_id:
                blocking_reasons.append(f"binding_{index}_route_id_not_server_issued")
        normalized.append(binding)
    if not any(
        binding.get("lane") == PRIMARY_CHATGPT_LANE and binding.get("enabled") is True
        for binding in normalized
    ):
        blocking_reasons.append("primary_chatgpt_enabled_binding_missing")
    if require_api_route_binding and not any(
        binding.get("lane") == API_ROUTE_LANE and binding.get("enabled") is True
        for binding in normalized
    ):
        blocking_reasons.append("api_route_enabled_binding_missing")
    status = "ok" if not blocking_reasons else "rejected"
    return _validation_packet(
        status=status,
        machine_error_code="OK" if status == "ok" else "CUSTOM_AGENT_BINDINGS_INVALID",
        normalized_bindings=normalized,
        blocking_reasons=blocking_reasons,
        route_records=route_records,
    )


def _validation_packet(
    *,
    status: str,
    machine_error_code: str,
    normalized_bindings: list[dict[str, Any]],
    blocking_reasons: list[str],
    route_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    route_records = route_records or []
    active_bindings = normalized_bindings if status == "ok" else []
    projection = project_agent_bindings_for_runtime_context(
        active_bindings,
        route_records=route_records,
    )
    return {
        "schema_version": AGENT_BINDINGS_SCHEMA_VERSION,
        "packet_kind": AGENT_BINDINGS_PACKET_KIND,
        "captured_at_utc": utc_now(),
        "status": status,
        "machine_error_code": machine_error_code,
        "human_message": (
            "Custom Codex agent bindings validated."
            if status == "ok"
            else "Custom Codex agent bindings did not satisfy the server contract."
        ),
        "agent_bindings": normalized_bindings,
        "agent_binding_count": len(normalized_bindings),
        "blocking_reasons": blocking_reasons,
        "alias_to_agent_id": projection["alias_to_agent_id"],
        "agent_id_to_route": projection["agent_id_to_route"],
        "allowed_api_route_ids": projection["allowed_api_route_ids"],
        "forbidden_stale_route_ids": projection["forbidden_stale_route_ids"],
        "browser_can_supply_route_authority": False,
        "browser_backend_intake": False,
        "browser_secret_intake": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "changed_files": [],
        "next_action": "none" if status == "ok" else "repair_agent_bindings",
    }


def project_agent_bindings_for_runtime_context(
    agent_bindings: list[dict[str, Any]],
    *,
    route_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    route_records = route_records or []
    routes_by_id = _route_records_by_id(route_records)
    alias_to_agent_id: dict[str, str] = {}
    agent_id_to_route: dict[str, str] = {}
    agent_id_to_model: dict[str, str] = {}
    primary_aliases: list[str] = []
    coding_aliases: list[str] = []
    allowed_api_route_ids: list[str] = []
    for binding in agent_bindings:
        enabled = binding.get("enabled") is True
        agent_id = str(binding.get("agent_id") or "")
        lane = str(binding.get("lane") or "")
        aliases = [str(alias) for alias in binding.get("aliases", []) if str(alias)]
        if not enabled:
            continue
        for alias in aliases:
            alias_to_agent_id[alias] = agent_id
        if lane == PRIMARY_CHATGPT_LANE:
            if not primary_aliases:
                primary_aliases = aliases
            agent_id_to_model[agent_id] = str(binding.get("model_id") or "")
        if lane == API_ROUTE_LANE:
            if not coding_aliases:
                coding_aliases = aliases
            route_id = str(binding.get("route_id") or "")
            agent_id_to_route[agent_id] = route_id
            if route_id and route_id not in allowed_api_route_ids:
                allowed_api_route_ids.append(route_id)
    forbidden_stale_route_ids = sorted(
        route_id
        for route_id in FORBIDDEN_STALE_ROUTE_IDS
        if route_id not in allowed_api_route_ids
    )
    providers_by_route = {
        route_id: str(routes_by_id.get(route_id, {}).get("provider") or "")
        for route_id in allowed_api_route_ids
    }
    return {
        "agent_bindings": agent_bindings,
        "alias_to_agent_id": alias_to_agent_id,
        "agent_id_to_route": agent_id_to_route,
        "agent_id_to_model": agent_id_to_model,
        "allowed_api_route_ids": allowed_api_route_ids,
        "forbidden_stale_route_ids": forbidden_stale_route_ids,
        "route_providers": providers_by_route,
        "primary_aliases": primary_aliases,
        "coding_aliases": coding_aliases,
        "agent_binding_truth_source": RUNTIME_CONTEXT_BINDINGS_SOURCE,
    }


def _state_invalid_packet(reason: str) -> dict[str, Any]:
    packet = _validation_packet(
        status="blocked",
        machine_error_code="CUSTOM_AGENT_BINDINGS_STATE_INVALID",
        normalized_bindings=[],
        blocking_reasons=[reason],
    )
    packet["human_message"] = "Custom Codex agent bindings state file is invalid."
    packet["source"] = "persisted_state"
    packet["state_file_present"] = True
    packet["state_path_redacted"] = True
    packet["next_action"] = "repair_or_remove_agent_bindings_state"
    return packet


def read_agent_bindings_packet(
    path: Path,
    *,
    default_bindings: list[dict[str, Any]],
    primary_model_ids: list[str] | tuple[str, ...] | set[str] = (),
    route_records: list[dict[str, Any]] | None = None,
    require_api_route_binding: bool = False,
) -> dict[str, Any]:
    state_file_present = path.is_file()
    if state_file_present:
        try:
            document_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _state_invalid_packet("state_file_unreadable_or_invalid_json")
        if not isinstance(document_payload, dict):
            return _state_invalid_packet("state_document_not_object")
        document = document_payload
        raw_bindings = document.get("agent_bindings")
        source = "persisted_state"
    else:
        raw_bindings = default_bindings
        source = "server_default"
    packet = validate_agent_bindings(
        raw_bindings,
        primary_model_ids=primary_model_ids,
        route_records=route_records,
        require_api_route_binding=require_api_route_binding,
    )
    packet["source"] = source
    packet["state_file_present"] = state_file_present
    packet["state_path_redacted"] = True
    return packet


def dry_run_agent_bindings_packet(
    payload: Mapping[str, Any],
    *,
    primary_model_ids: list[str] | tuple[str, ...] | set[str] = (),
    route_records: list[dict[str, Any]] | None = None,
    require_api_route_binding: bool = False,
) -> dict[str, Any]:
    forbidden_fields = sorted(set(payload) - {"agent_bindings"})
    if forbidden_fields:
        return {
            "schema_version": AGENT_BINDINGS_SCHEMA_VERSION,
            "packet_kind": AGENT_BINDINGS_PACKET_KIND,
            "captured_at_utc": utc_now(),
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Agent bindings accept only the agent_bindings field.",
            "forbidden_fields": forbidden_fields,
            "agent_bindings": [],
            "agent_binding_count": 0,
            "alias_to_agent_id": {},
            "agent_id_to_route": {},
            "allowed_api_route_ids": [],
            "forbidden_stale_route_ids": sorted(FORBIDDEN_STALE_ROUTE_IDS),
            "browser_can_supply_route_authority": False,
            "browser_backend_intake": False,
            "browser_secret_intake": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "changed_files": [],
            "next_action": "remove_forbidden_browser_fields",
        }
    return validate_agent_bindings(
        payload.get("agent_bindings"),
        primary_model_ids=primary_model_ids,
        route_records=route_records,
        require_api_route_binding=require_api_route_binding,
    ) | {"dry_run": True}


def write_agent_bindings_packet(
    path: Path,
    payload: Mapping[str, Any],
    *,
    primary_model_ids: list[str] | tuple[str, ...] | set[str] = (),
    route_records: list[dict[str, Any]] | None = None,
    require_api_route_binding: bool = False,
) -> dict[str, Any]:
    packet = dry_run_agent_bindings_packet(
        payload,
        primary_model_ids=primary_model_ids,
        route_records=route_records,
        require_api_route_binding=require_api_route_binding,
    )
    if packet.get("status") != "ok":
        return packet | {"dry_run": False, "changed_files": []}
    document = {
        "schema_version": AGENT_BINDINGS_SCHEMA_VERSION,
        "packet_kind": "codex_custom_agent_bindings_state",
        "updated_at_utc": utc_now(),
        "agent_bindings": packet["agent_bindings"],
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
    }
    write_text_atomic(
        path,
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True),
    )
    return packet | {
        "dry_run": False,
        "source": "persisted_state",
        "state_file_present": True,
        "state_path_redacted": True,
        "changed_files": [str(path)],
        "human_message": "Custom Codex agent bindings saved.",
    }


def resolve_alias_binding(
    agent_bindings: list[dict[str, Any]],
    alias: str,
) -> dict[str, Any]:
    normalized_alias = _canonical_alias_key(alias)
    if not normalized_alias:
        return {}
    for binding in agent_bindings:
        aliases = [_canonical_alias_key(value) for value in binding.get("aliases", [])]
        if normalized_alias in aliases:
            return binding
    return {}
