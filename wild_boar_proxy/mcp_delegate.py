# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, BinaryIO, Mapping, TextIO
import unicodedata

from .command_effects import EFFECT_PROBE
from .core import packets as command_packets
from .custom_agent_bindings import API_ROUTE_LANE, resolve_alias_binding
from .native_filesystem_probe import AGENT_RUNTIME_CONTEXT_FILENAME


MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SERVER_NAME = "wild-boar-proxy"
MCP_SERVER_VERSION = "0.0.0"
DELEGATE_TO_DIP_TOOL = "delegate_to_dip"
DELEGATE_PACKET_KIND = "wbp_mcp_delegate_to_dip_reality"
DELEGATE_FINAL_STATUS_WITH_LIMITS = "WBP_MCP_DELEGATE_TO_DIP_PROVEN_WITH_LIMITS"
DELEGATE_FINAL_STATUS_NOT_PROVEN = "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN"
CONFIG_PROBE_PACKET_KIND = "wbp_codex_mcp_config_probe"
CONFIG_PROBE_FINAL_STATUS_LOADED = "WBP_CODEX_MCP_CONFIG_PROBE_LOADED"
CONFIG_PROBE_FINAL_STATUS_BLOCKED = "WBP_CODEX_MCP_CONFIG_PROBE_BLOCKED"
WIRING_PACKET_KIND = "wbp_codex_mcp_wiring_reality"
WIRING_FINAL_STATUS_PROVEN = "WBP_CODEX_MCP_WIRING_PROVEN"
WIRING_FINAL_STATUS_WORKS_WITH_LIMITS = "WBP_CODEX_MCP_WIRING_WORKS_WITH_LIMITS"
WIRING_FINAL_STATUS_BLOCKED = "WBP_CODEX_MCP_WIRING_BLOCKED"
CODEX_EXEC_TOOL_CALL_PACKET_KIND = "wbp_codex_exec_tool_call_observation"
CODEX_EXEC_TOOL_CALL_FINAL_STATUS_OBSERVED = (
    "WBP_CODEX_EXEC_TOOL_CALL_OBSERVED"
)
CODEX_EXEC_TOOL_CALL_FINAL_STATUS_BLOCKED = "WBP_CODEX_EXEC_TOOL_CALL_BLOCKED"


@dataclass(frozen=True)
class RuntimeContextRead:
    context: dict[str, Any]
    metadata: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_text(value: object, *, limit: int = 4096) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return text.replace("\r", " ").replace("\n", " ").strip()[:limit]


def _alias_key(value: object) -> str:
    return " ".join(_safe_text(value, limit=256).split()).casefold()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=128)
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def _canonical_delegate_arguments(arguments: Mapping[str, Any] | None) -> dict[str, str]:
    source = arguments if isinstance(arguments, Mapping) else {}
    task = _safe_text(source.get("task") or "", limit=4096)
    expected_alias = _safe_text(
        source.get("expected_alias") or source.get("alias") or "",
        limit=80,
    )
    return {
        "task": task,
        "expected_alias": expected_alias,
    }


def _delegate_call_sha256(arguments: Mapping[str, Any] | None) -> str:
    canonical_arguments = _canonical_delegate_arguments(arguments)
    return _sha256_text(
        json.dumps(
            {
                "tool_name": DELEGATE_TO_DIP_TOOL,
                "arguments": canonical_arguments,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _runtime_context_path_from_env(env: Mapping[str, str] | None) -> Path | None:
    source = env if env is not None else os.environ
    profile_dir = _safe_text(source.get("WBP_PROFILE_DIR") or "", limit=4096)
    if not profile_dir:
        return None
    return Path(profile_dir).expanduser() / AGENT_RUNTIME_CONTEXT_FILENAME


def read_runtime_context_from_profile(
    env: Mapping[str, str] | None = None,
) -> RuntimeContextRead:
    context_path = _runtime_context_path_from_env(env)
    if context_path is None:
        return RuntimeContextRead(
            context={},
            metadata={
                "status": "blocked",
                "machine_error_code": "FAIL_ALIAS_CONTEXT_MISSING",
                "context_file_present": False,
                "context_file_sha256_present": False,
                "context_sha256": "",
                "alias_context_read": False,
                "context_read_source": "none",
                "context_path_redacted": True,
            },
        )
    if not context_path.is_file():
        return RuntimeContextRead(
            context={},
            metadata={
                "status": "blocked",
                "machine_error_code": "FAIL_ALIAS_CONTEXT_MISSING",
                "context_file_present": False,
                "context_file_sha256_present": False,
                "context_sha256": "",
                "alias_context_read": False,
                "context_read_source": "profile_context_file",
                "context_path_redacted": True,
            },
        )
    try:
        text = context_path.read_text(encoding="utf-8")
        payload = json.loads(text)
    except OSError:
        return RuntimeContextRead(
            context={},
            metadata={
                "status": "blocked",
                "machine_error_code": "FAIL_ALIAS_CONTEXT_UNREADABLE",
                "context_file_present": True,
                "context_file_sha256_present": False,
                "context_sha256": "",
                "alias_context_read": False,
                "context_read_source": "profile_context_file",
                "context_path_redacted": True,
            },
        )
    except json.JSONDecodeError:
        return RuntimeContextRead(
            context={},
            metadata={
                "status": "blocked",
                "machine_error_code": "FAIL_ALIAS_CONTEXT_INVALID",
                "context_file_present": True,
                "context_file_sha256_present": False,
                "context_sha256": "",
                "alias_context_read": False,
                "context_read_source": "profile_context_file",
                "context_path_redacted": True,
            },
        )
    if not isinstance(payload, dict):
        return RuntimeContextRead(
            context={},
            metadata={
                "status": "blocked",
                "machine_error_code": "FAIL_ALIAS_CONTEXT_INVALID",
                "context_file_present": True,
                "context_file_sha256_present": False,
                "context_sha256": "",
                "alias_context_read": False,
                "context_read_source": "profile_context_file",
                "context_path_redacted": True,
            },
        )
    return RuntimeContextRead(
        context=payload,
        metadata={
            "status": "ok",
            "machine_error_code": "OK",
            "context_file_present": True,
            "context_file_sha256_present": True,
            "context_sha256": _sha256_text(text),
            "alias_context_read": True,
            "context_read_source": "profile_context_file",
            "context_path_redacted": True,
        },
    )


def _aliases_for_lane(context: Mapping[str, Any], lane: str) -> list[str]:
    context_key = "coding_aliases" if lane == API_ROUTE_LANE else "primary_aliases"
    raw_aliases = context.get(context_key)
    aliases = (
        [_safe_text(alias, limit=80) for alias in raw_aliases]
        if isinstance(raw_aliases, list)
        else []
    )
    aliases = [alias for alias in aliases if alias]
    if aliases:
        return aliases
    bindings = context.get("agent_bindings")
    if not isinstance(bindings, list):
        return []
    derived: list[str] = []
    seen: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, dict) or binding.get("lane") != lane:
            continue
        raw_binding_aliases = binding.get("aliases")
        if not isinstance(raw_binding_aliases, list):
            continue
        for alias in raw_binding_aliases:
            text = _safe_text(alias, limit=80)
            key = _alias_key(text)
            if text and key and key not in seen:
                derived.append(text)
                seen.add(key)
    return derived


def _select_alias(arguments: Mapping[str, Any], coding_aliases: list[str]) -> str:
    explicit_alias = _safe_text(
        arguments.get("expected_alias") or arguments.get("alias") or "",
        limit=80,
    )
    if explicit_alias:
        return explicit_alias
    task_key = _alias_key(arguments.get("task") or "")
    for alias in coding_aliases:
        alias_key = _alias_key(alias)
        if alias_key and alias_key in task_key:
            return alias
    return coding_aliases[0] if len(coding_aliases) == 1 else ""


def _command_packet_for_kind(
    *,
    ok: bool,
    machine_error_code: str,
    human_message: str,
    blocking_reasons: list[str],
    extra: dict[str, Any],
    packet_kind: str,
    final_status: str,
    result_status: str,
) -> dict[str, Any]:
    operator_action = "none" if ok else "stop"
    return command_packets.build_command_packet(
        ok=ok,
        human_message=human_message,
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable" if ok else "high",
        operator_action=operator_action,
        changed_files=[],
        effect=EFFECT_PROBE,
        extra={
            "schema_version": 1,
            "packet_kind": packet_kind,
            "captured_at_utc": utc_now(),
            "final_status": final_status,
            "result_status": result_status,
            "blocking_reasons": blocking_reasons,
            **extra,
        },
    )


def _command_packet(
    *,
    ok: bool,
    machine_error_code: str,
    human_message: str,
    blocking_reasons: list[str],
    extra: dict[str, Any],
) -> dict[str, Any]:
    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=human_message,
        blocking_reasons=blocking_reasons,
        extra=extra,
        packet_kind=DELEGATE_PACKET_KIND,
        final_status=(
            DELEGATE_FINAL_STATUS_WITH_LIMITS
            if ok
            else DELEGATE_FINAL_STATUS_NOT_PROVEN
        ),
        result_status="with_limits" if ok else "blocked",
    )


def _mcp_get_field(stdout: str, field: str) -> str:
    prefix = f"{field}:"
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return ""


def _mcp_list_server_line(stdout: str, server_name: str) -> str:
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{server_name} "):
            return stripped
    return ""


def build_codex_mcp_config_probe_packet(
    list_stdout: str,
    get_stdout: str = "",
    *,
    list_exit_code: int = 0,
    get_exit_code: int = 0,
    expected_server_name: str = "wbp",
) -> dict[str, Any]:
    safe_server_name = _safe_text(expected_server_name, limit=80) or "wbp"
    safe_list_stdout = _safe_text(list_stdout, limit=8192)
    safe_get_stdout = _safe_text(get_stdout, limit=8192)
    combined_stdout = f"{safe_list_stdout}\n{safe_get_stdout}"
    server_line = _mcp_list_server_line(list_stdout, safe_server_name)
    command = _mcp_get_field(get_stdout, "command")
    args = _mcp_get_field(get_stdout, "args")
    transport = _mcp_get_field(get_stdout, "transport")
    enabled_field = _mcp_get_field(get_stdout, "enabled")
    status_enabled = bool(
        enabled_field.casefold() == "true"
        or (" enabled " in f" {server_line} ".casefold())
    )
    args_match = args == "-m wild_boar_proxy.mcp_delegate" or (
        "-m wild_boar_proxy.mcp_delegate" in server_line
    )
    command_present = bool(
        "python" in command.casefold()
        or re.search(r"\bpython(?:3)?\b", server_line.casefold())
    )
    env_redacted = "WBP_PROFILE_DIR=*****" in combined_stdout
    config_commands_succeeded = list_exit_code == 0 and get_exit_code == 0
    server_listed = bool(
        server_line
        or any(line.strip() == safe_server_name for line in get_stdout.splitlines())
    )
    global_config_error_observed = bool(
        "failed to load configuration" in combined_stdout.casefold()
        or "unknown variant" in combined_stdout.casefold()
    )
    config_loaded = bool(
        config_commands_succeeded
        and server_listed
        and status_enabled
        and command_present
        and args_match
        and env_redacted
    )
    blocking_reasons: list[str] = []
    if not config_commands_succeeded:
        blocking_reasons.append("codex_mcp_command_failed")
    if global_config_error_observed:
        blocking_reasons.append("codex_global_config_error_observed")
    if not server_listed:
        blocking_reasons.append("codex_mcp_server_not_listed")
    if not status_enabled:
        blocking_reasons.append("codex_mcp_server_not_enabled")
    if not command_present:
        blocking_reasons.append("codex_mcp_command_missing")
    if not args_match:
        blocking_reasons.append("codex_mcp_args_not_wbp_delegate")
    if not env_redacted:
        blocking_reasons.append("codex_mcp_env_not_redacted")

    return _command_packet_for_kind(
        ok=config_loaded,
        machine_error_code="OK" if config_loaded else "WBP_CODEX_MCP_CONFIG_NOT_LOADED",
        human_message=(
            "Codex MCP config probe found a redacted WBP delegate server registration."
            if config_loaded
            else "Codex MCP config probe did not prove a usable WBP delegate registration."
        ),
        blocking_reasons=[] if config_loaded else blocking_reasons,
        extra={
            "config_loaded": config_loaded,
            "codex_mcp_config_loaded": config_loaded,
            "codex_mcp_config_command_succeeded": config_commands_succeeded,
            "codex_mcp_server_name": safe_server_name,
            "codex_mcp_server_listed": server_listed,
            "codex_mcp_server_enabled": status_enabled,
            "codex_mcp_transport_stdio": transport in {"", "stdio"},
            "codex_mcp_command_present": command_present,
            "codex_mcp_command": command,
            "codex_mcp_args_match": args_match,
            "codex_mcp_env_redacted": env_redacted,
            "codex_mcp_original_profile_touched": False,
            "original_profile_touched": False,
            "global_config_error_observed": global_config_error_observed,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "raw_config_stdout_recorded": False,
            "raw_config_stderr_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
        packet_kind=CONFIG_PROBE_PACKET_KIND,
        final_status=(
            CONFIG_PROBE_FINAL_STATUS_LOADED
            if config_loaded
            else CONFIG_PROBE_FINAL_STATUS_BLOCKED
        ),
        result_status="loaded" if config_loaded else "blocked",
    )


def build_prompt_observation_packet(
    prompt_text: str,
    *,
    source: str = "manual",
    expected_delegate_arguments: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    expected_arguments = (
        dict(expected_delegate_arguments)
        if isinstance(expected_delegate_arguments, Mapping)
        else {}
    )
    return {
        "packet_kind": "wbp_codex_prompt_observation",
        "prompt_sha256": _sha256_text(prompt) if prompt else "",
        "prompt_digest_present": bool(prompt),
        "prompt_source": _safe_text(source, limit=80) or "manual",
        "expected_delegate_tool_call_sha256": (
            _delegate_call_sha256(expected_arguments) if expected_arguments else ""
        ),
        "expected_delegate_tool_call_digest_present": bool(expected_arguments),
        "expected_delegate_tool_name": (
            DELEGATE_TO_DIP_TOOL if expected_arguments else ""
        ),
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "expected_delegate_arguments_recorded": False,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _jsonl_event_objects(jsonl_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for index, line in enumerate(str(jsonl_text or "").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            parse_errors.append(f"jsonl_line_{index}_invalid")
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events, parse_errors


def _iter_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for item in value.values():
            found.extend(_iter_mappings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_iter_mappings(item))
    return found


def _first_text_field(mapping: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        text = _safe_text(mapping.get(field) or "", limit=256)
        if text:
            return text
    return ""


def _json_mapping_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _tool_call_arguments_from_event_mapping(
    mapping: Mapping[str, Any],
) -> dict[str, Any]:
    for field in ("arguments", "args", "input", "parameters", "params"):
        candidate = _json_mapping_from_value(mapping.get(field))
        if candidate:
            return candidate
    return {}


def _codex_exec_mcp_tool_call_candidates(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for event in events:
        event_type = _safe_text(event.get("type") or "", limit=128)
        for mapping in _iter_mappings(event):
            item_type = _first_text_field(
                mapping,
                ("type", "kind", "item_type", "itemType"),
            )
            tool_name = _first_text_field(
                mapping,
                ("tool_name", "toolName", "tool", "name"),
            )
            server_name = _first_text_field(
                mapping,
                ("server_name", "serverName", "mcp_server", "mcpServer", "server"),
            )
            item_type_key = item_type.casefold()
            structured_mcp_tool_event = "mcp" in item_type_key and "tool" in item_type_key
            if tool_name != DELEGATE_TO_DIP_TOOL:
                continue
            if not structured_mcp_tool_event:
                continue
            status = _first_text_field(mapping, ("status", "state"))
            candidates.append(
                {
                    "event_type": event_type,
                    "item_type": item_type,
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "status": status,
                    "arguments": _tool_call_arguments_from_event_mapping(mapping),
                }
            )
    return candidates


_CODEX_EXEC_AUTH_BLOCKER_PATTERN = re.compile(
    r"(?i)\b("
    r"auth[a-z_-]*|oauth|login|log in|logged in|sign in|signed in|"
    r"not authenticated|not signed in|unauthenticated|unauthorized|"
    r"api key|CODEX_API_KEY|401|bearer|admission|subscription|"
    r"plan required|account access required|account required|access required|"
    r"entitled|entitlement"
    r")\b"
)


def _codex_exec_auth_blocker_from_events(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if _safe_text(event.get("type") or "", limit=128) != "error":
            continue
        try:
            encoded = json.dumps(event, ensure_ascii=True, sort_keys=True)
        except (TypeError, ValueError):
            encoded = repr(event)
        if _CODEX_EXEC_AUTH_BLOCKER_PATTERN.search(encoded):
            return True
    return False


def _select_codex_exec_tool_call_candidate(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    completed_statuses = {"completed", "complete", "succeeded", "success", "ok"}
    for candidate in reversed(candidates):
        status_key = str(candidate.get("status") or "").casefold()
        if (
            candidate.get("event_type") == "item.completed"
            or status_key in completed_statuses
        ):
            return candidate
    return candidates[-1] if candidates else {}


def build_codex_exec_tool_call_observation_packet(
    jsonl_text: str,
    *,
    prompt_packet: Mapping[str, Any] | None = None,
    exec_exit_code: int = 0,
    stderr_text: str = "",
) -> dict[str, Any]:
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    events, parse_errors = _jsonl_event_objects(jsonl_text)
    event_types = [
        _safe_text(event.get("type") or "", limit=128) for event in events
    ]
    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    expected_call_sha256 = _hex_sha256(
        prompt.get("expected_delegate_tool_call_sha256") or ""
    )
    candidates = _codex_exec_mcp_tool_call_candidates(events)
    selected_call = _select_codex_exec_tool_call_candidate(candidates)
    arguments = (
        dict(selected_call.get("arguments"))
        if isinstance(selected_call.get("arguments"), Mapping)
        else {}
    )
    actual_call_sha256 = _delegate_call_sha256(arguments) if arguments else ""
    task_text = _safe_text(arguments.get("task") or "", limit=4096)
    task_sha256 = _sha256_text(task_text) if task_text else ""
    expected_call_matches = bool(
        expected_call_sha256 and actual_call_sha256 == expected_call_sha256
    )
    prompt_task_matches = bool(prompt_sha256 and task_sha256 == prompt_sha256)
    prompt_to_mcp_call_bound = (
        expected_call_matches if expected_call_sha256 else prompt_task_matches
    )
    delegate_to_dip_tool_called = bool(selected_call)
    events_observed = bool(events)
    real_codex_prompt_executed = any(
        event_type in {"thread.started", "turn.started", "turn.completed"}
        for event_type in event_types
    )
    stderr_safe = _safe_text(stderr_text, limit=4096)
    auth_blocker_observed = bool(
        exec_exit_code != 0
        and (
            _CODEX_EXEC_AUTH_BLOCKER_PATTERN.search(stderr_safe)
            or _codex_exec_auth_blocker_from_events(events)
        )
    )
    blocking_reasons: list[str] = []
    if exec_exit_code != 0:
        blocking_reasons.append("codex_exec_nonzero_exit")
    if auth_blocker_observed:
        blocking_reasons.append("codex_exec_auth_or_model_admission_required")
    if parse_errors:
        blocking_reasons.append("codex_exec_jsonl_parse_error")
    if not events_observed:
        blocking_reasons.append("codex_exec_json_events_not_observed")
    if not real_codex_prompt_executed:
        blocking_reasons.append("real_codex_prompt_not_executed")
    if not delegate_to_dip_tool_called:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_observed")
    if delegate_to_dip_tool_called and not prompt_to_mcp_call_bound:
        blocking_reasons.append("prompt_not_bound_to_codex_mcp_tool_call")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif auth_blocker_observed:
        machine_error_code = "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED"
    elif parse_errors and not events:
        machine_error_code = "WBP_CODEX_EXEC_JSONL_INVALID"
    else:
        machine_error_code = "WBP_CODEX_EXEC_TOOL_CALL_NOT_PROVEN"

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "Codex exec JSONL proves a prompt-bound delegate_to_dip MCP tool call."
            if ok
            else "Codex exec JSONL does not prove a prompt-bound delegate_to_dip MCP tool call."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "codex_exec_json_events_observed": events_observed,
            "codex_exec_exit_code": int(exec_exit_code),
            "codex_exec_auth_blocker_observed": auth_blocker_observed,
            "codex_exec_jsonl_parse_error_count": len(parse_errors),
            "codex_exec_event_count": len(events),
            "codex_exec_event_digest": _sha256_text(
                json.dumps(event_types, sort_keys=True)
            ),
            "real_codex_prompt_executed": real_codex_prompt_executed,
            "delegate_to_dip_tool_called": delegate_to_dip_tool_called,
            "codex_delegate_to_dip_tool_called": delegate_to_dip_tool_called,
            "tool_name": DELEGATE_TO_DIP_TOOL if delegate_to_dip_tool_called else "",
            "mcp_server_name_observed": _safe_text(
                selected_call.get("server_name") or "", limit=128
            ),
            "tool_call_status_observed": _safe_text(
                selected_call.get("status") or "", limit=80
            ),
            "tool_call_digest_present": bool(actual_call_sha256),
            "tool_call_sha256": actual_call_sha256,
            "prompt_sha256": prompt_sha256 if prompt_to_mcp_call_bound else "",
            "prompt_digest_present": bool(prompt_sha256),
            "expected_delegate_tool_call_digest_present": bool(expected_call_sha256),
            "expected_delegate_tool_call_matched": expected_call_matches,
            "prompt_task_digest_matched": prompt_task_matches,
            "prompt_to_mcp_call_bound": prompt_to_mcp_call_bound,
            "api_lane_called": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_api_lane_provider_dispatch": True,
            "raw_jsonl_recorded": False,
            "raw_stderr_recorded": False,
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "tool_call_arguments_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
        packet_kind=CODEX_EXEC_TOOL_CALL_PACKET_KIND,
        final_status=(
            CODEX_EXEC_TOOL_CALL_FINAL_STATUS_OBSERVED
            if ok
            else CODEX_EXEC_TOOL_CALL_FINAL_STATUS_BLOCKED
        ),
        result_status="observed" if ok else "blocked",
    )


def build_codex_mcp_wiring_reality_packet(
    *,
    config_packet: Mapping[str, Any] | None = None,
    mcp_reality_packet: Mapping[str, Any] | None = None,
    prompt_packet: Mapping[str, Any] | None = None,
    hook_packet: Mapping[str, Any] | None = None,
    codex_tool_call_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(config_packet) if isinstance(config_packet, Mapping) else {}
    mcp_reality = (
        dict(mcp_reality_packet) if isinstance(mcp_reality_packet, Mapping) else {}
    )
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    hook = dict(hook_packet) if isinstance(hook_packet, Mapping) else {}
    codex_call = (
        dict(codex_tool_call_packet)
        if isinstance(codex_tool_call_packet, Mapping)
        else {}
    )

    codex_mcp_config_loaded = bool(
        config.get("config_loaded") is True
        or config.get("codex_mcp_config_loaded") is True
    )
    codex_mcp_original_profile_touched = bool(
        config.get("codex_mcp_original_profile_touched") is True
        or config.get("original_profile_touched") is True
    )
    direct_mcp_server_visible = mcp_reality.get("mcp_server_visible") is True
    direct_delegate_to_dip_tool_listed = bool(
        mcp_reality.get("delegate_to_dip_tool_listed") is True
        or mcp_reality.get("delegate_to_dip_tool_visible") is True
    )
    direct_delegate_to_dip_tool_called = (
        mcp_reality.get("delegate_to_dip_tool_called") is True
    )
    direct_mcp_reality_ok = mcp_reality.get("status") == "ok"
    delegate_to_dip_tool_visible_to_codex = bool(
        codex_mcp_config_loaded and direct_delegate_to_dip_tool_listed
    )
    direct_mcp_proven_with_limits = bool(
        codex_mcp_config_loaded
        and not codex_mcp_original_profile_touched
        and direct_mcp_reality_ok
        and direct_mcp_server_visible
        and direct_delegate_to_dip_tool_listed
        and direct_delegate_to_dip_tool_called
        and mcp_reality.get("local_imitation_used") is False
        and mcp_reality.get("fallback_used") is False
        and mcp_reality.get("product_ready") is False
    )

    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    codex_call_prompt_sha256 = _hex_sha256(
        codex_call.get("prompt_sha256")
        or codex_call.get("bound_prompt_sha256")
        or ""
    )
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    real_codex_prompt_executed = bool(
        codex_call.get("real_codex_prompt_executed") is True
        or codex_call.get("codex_prompt_executed") is True
    )
    codex_tool_call_observation_ok = bool(
        codex_call.get("status") == "ok"
        and codex_call.get("result_status") in {"", "observed"}
    ) if codex_call else False
    codex_delegate_to_dip_tool_called = bool(
        codex_call.get("delegate_to_dip_tool_called") is True
        or codex_call.get("tool_name") == DELEGATE_TO_DIP_TOOL
    )
    prompt_to_mcp_call_bound = bool(
        codex_call.get("prompt_to_mcp_call_bound") is True
        and prompt_digest_present
        and codex_call_prompt_sha256 == prompt_sha256
    )
    api_lane_called = codex_call.get("api_lane_called") is True
    fallback_used = bool(
        codex_call.get("fallback_used") is True
        or mcp_reality.get("fallback_used") is True
    )
    local_imitation_used = bool(
        codex_call.get("local_imitation_used") is True
        or mcp_reality.get("local_imitation_used") is True
    )
    native_free_chat_router_proven = bool(
        codex_call.get("native_free_chat_router_proven") is True
        and api_lane_called
        and not fallback_used
        and not local_imitation_used
    )
    codex_mcp_wiring_proven = bool(
        direct_mcp_proven_with_limits
        and codex_tool_call_observation_ok
        and real_codex_prompt_executed
        and codex_delegate_to_dip_tool_called
        and prompt_to_mcp_call_bound
        and not fallback_used
        and not local_imitation_used
    )

    blocking_reasons: list[str] = []
    if not codex_mcp_config_loaded:
        blocking_reasons.append("codex_mcp_config_not_loaded")
    if codex_mcp_original_profile_touched:
        blocking_reasons.append("codex_mcp_original_profile_touched")
    if not direct_mcp_server_visible:
        blocking_reasons.append("direct_mcp_server_not_visible")
    if not direct_delegate_to_dip_tool_listed:
        blocking_reasons.append("direct_delegate_to_dip_tool_not_listed")
    if not direct_delegate_to_dip_tool_called:
        blocking_reasons.append("direct_delegate_to_dip_tool_not_called")
    if not direct_mcp_reality_ok:
        blocking_reasons.append("direct_mcp_reality_packet_not_ok")
    if direct_mcp_proven_with_limits and not real_codex_prompt_executed:
        blocking_reasons.append("real_codex_prompt_not_executed")
    if direct_mcp_proven_with_limits and codex_call and not codex_tool_call_observation_ok:
        blocking_reasons.append("codex_tool_call_observation_packet_not_ok")
    if direct_mcp_proven_with_limits and not codex_delegate_to_dip_tool_called:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_observed")
    if direct_mcp_proven_with_limits and not prompt_to_mcp_call_bound:
        blocking_reasons.append("prompt_not_bound_to_codex_mcp_tool_call")
    if fallback_used:
        blocking_reasons.append("fallback_used")
    if local_imitation_used:
        blocking_reasons.append("local_imitation_used")

    if codex_mcp_wiring_proven:
        result_status = "proven"
        final_status = WIRING_FINAL_STATUS_PROVEN
    elif direct_mcp_proven_with_limits:
        result_status = "works_with_limits"
        final_status = WIRING_FINAL_STATUS_WORKS_WITH_LIMITS
    else:
        result_status = "blocked"
        final_status = WIRING_FINAL_STATUS_BLOCKED
    ok = result_status != "blocked"
    limiting_reasons = blocking_reasons if result_status == "works_with_limits" else []
    packet_blocking_reasons = blocking_reasons if result_status == "blocked" else []

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code="OK" if ok else "WBP_CODEX_MCP_WIRING_NOT_PROVEN",
        human_message=(
            "Codex MCP wiring is proven by a prompt-bound delegate_to_dip tool call."
            if result_status == "proven"
            else (
                "Codex can load the WBP MCP server and the direct MCP proof works, "
                "but no real Codex prompt-bound tool call is proven."
            )
            if result_status == "works_with_limits"
            else "Codex MCP wiring is not proven by the supplied evidence."
        ),
        blocking_reasons=packet_blocking_reasons,
        extra={
            "codex_mcp_config_loaded": codex_mcp_config_loaded,
            "codex_mcp_config_truth_source": (
                "codex_mcp_config_probe" if config else "not_observed"
            ),
            "codex_mcp_original_profile_touched": codex_mcp_original_profile_touched,
            "wbp_mcp_server_visible_to_codex": codex_mcp_config_loaded,
            "delegate_to_dip_tool_visible_to_codex": delegate_to_dip_tool_visible_to_codex,
            "direct_mcp_server_visible": direct_mcp_server_visible,
            "direct_delegate_to_dip_tool_listed": direct_delegate_to_dip_tool_listed,
            "direct_delegate_to_dip_tool_called": direct_delegate_to_dip_tool_called,
            "direct_mcp_reality_packet_status": str(mcp_reality.get("status") or ""),
            "direct_mcp_proven_with_limits": direct_mcp_proven_with_limits,
            "real_codex_prompt_executed": real_codex_prompt_executed,
            "codex_delegate_to_dip_tool_called": codex_delegate_to_dip_tool_called,
            "prompt_digest_present": prompt_digest_present,
            "prompt_to_mcp_call_bound": prompt_to_mcp_call_bound,
            "hook_observed_prompt": bool(
                hook.get("hook_observed_prompt") is True
                or hook.get("prompt_observed") is True
            ),
            "hook_can_enforce_router": hook.get("hook_can_enforce_router") is True,
            "hook_can_route_delegate_to_dip": hook.get("hook_can_route_delegate_to_dip") is True,
            "codex_mcp_wiring_proven": codex_mcp_wiring_proven,
            "codex_cli_prompt_mcp_tool_call_proven": codex_mcp_wiring_proven,
            "codex_tool_call_observation_packet_ok": codex_tool_call_observation_ok,
            "codex_exec_json_events_observed": (
                codex_call.get("codex_exec_json_events_observed") is True
            ),
            "codex_exec_tool_call_observation_status": str(
                codex_call.get("status") or ""
            ),
            "limiting_reasons": limiting_reasons,
            "missing_evidence_reasons": blocking_reasons,
            "api_lane_called": api_lane_called,
            "fallback_used": fallback_used,
            "local_imitation_used": local_imitation_used,
            "product_ready": False,
            "native_free_chat_router_proven": native_free_chat_router_proven,
            "does_not_prove_native_free_chat_router": not native_free_chat_router_proven,
            "does_not_prove_api_lane_provider_dispatch": not api_lane_called,
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "raw_transcript_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
        packet_kind=WIRING_PACKET_KIND,
        final_status=final_status,
        result_status=result_status,
    )


def build_delegate_to_dip_packet(
    arguments: Mapping[str, Any] | None,
    *,
    env: Mapping[str, str] | None = None,
    mcp_tool_called: bool = False,
) -> dict[str, Any]:
    args = arguments if isinstance(arguments, Mapping) else {}
    task = _safe_text(args.get("task") or "", limit=4096)
    expected_alias = _safe_text(
        args.get("expected_alias") or args.get("alias") or "",
        limit=80,
    )
    tool_call_sha256 = _delegate_call_sha256(args)
    forbidden_fields = sorted(set(args) - {"task", "expected_alias", "alias"})
    context_read = read_runtime_context_from_profile(env)
    context = context_read.context
    metadata = context_read.metadata
    raw_agent_bindings = (
        context.get("agent_bindings") if isinstance(context.get("agent_bindings"), list) else []
    )
    agent_bindings = [
        binding for binding in raw_agent_bindings if isinstance(binding, dict)
    ]
    allowed_api_route_ids = [
        _safe_text(route_id, limit=128)
        for route_id in context.get("allowed_api_route_ids", [])
        if _safe_text(route_id, limit=128)
    ] if isinstance(context.get("allowed_api_route_ids"), list) else []
    forbidden_stale_route_ids = {
        _safe_text(route_id, limit=128)
        for route_id in context.get("forbidden_stale_route_ids", [])
        if _safe_text(route_id, limit=128)
    } if isinstance(context.get("forbidden_stale_route_ids"), list) else set()
    coding_aliases = _aliases_for_lane(context, API_ROUTE_LANE)
    selected_alias = _select_alias(args, coding_aliases)
    alias_binding = resolve_alias_binding(agent_bindings, selected_alias)
    route_id = _safe_text(alias_binding.get("route_id") or "", limit=128)

    stale_route_guard_present = bool(forbidden_stale_route_ids)
    route_allowed = bool(
        route_id
        and route_id in allowed_api_route_ids
        and stale_route_guard_present
        and route_id not in forbidden_stale_route_ids
    )
    binding_valid = bool(
        alias_binding
        and alias_binding.get("enabled") is True
        and alias_binding.get("lane") == API_ROUTE_LANE
        and str(alias_binding.get("role") or "") == "coding_agent"
    )
    context_valid = bool(
        metadata.get("alias_context_read") is True
        and context.get("packet_kind") == "codex_custom_native_agent_runtime_context"
        and context.get("execution_mode") == "chatgpt_plus_api"
        and context.get("agent_bindings_status") in {None, "", "ok"}
    )
    task_digest_preserved = bool(task)
    blocking_reasons: list[str] = []
    if forbidden_fields:
        blocking_reasons.extend(f"forbidden_field:{field}" for field in forbidden_fields)
    if not mcp_tool_called:
        blocking_reasons.append("mcp_tool_call_not_observed")
    if not task:
        blocking_reasons.append("task_required")
    if not metadata.get("alias_context_read"):
        blocking_reasons.append(
            str(metadata.get("machine_error_code") or "FAIL_ALIAS_CONTEXT_MISSING")
        )
    elif not context_valid:
        blocking_reasons.append("alias_context_invalid_for_chatgpt_plus_api")
    if not coding_aliases:
        blocking_reasons.append("coding_aliases_missing")
    if not selected_alias:
        blocking_reasons.append("coding_alias_not_selected")
    if selected_alias and not binding_valid:
        blocking_reasons.append("coding_alias_binding_invalid")
    if binding_valid and not route_allowed:
        blocking_reasons.append("coding_route_not_allowed")
    if binding_valid and not stale_route_guard_present:
        blocking_reasons.append("stale_route_guard_missing")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif forbidden_fields:
        machine_error_code = "WBP_MCP_DELEGATE_BROWSER_AUTHORITY_REJECTED"
    elif not metadata.get("alias_context_read"):
        machine_error_code = str(
            metadata.get("machine_error_code") or "FAIL_ALIAS_CONTEXT_MISSING"
        )
    else:
        machine_error_code = "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN"
    return _command_packet(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP MCP delegate_to_dip tool call is proven with bounded route evidence."
            if ok
            else "WBP MCP delegate_to_dip tool call is not proven or route evidence is blocked."
        ),
        blocking_reasons=blocking_reasons,
        extra={
            "mcp_server_visible": bool(mcp_tool_called),
            "delegate_to_dip_tool_listed": bool(mcp_tool_called),
            "delegate_to_dip_tool_visible": bool(mcp_tool_called),
            "delegate_to_dip_tool_called": bool(mcp_tool_called),
            "mcp_tool_truth_source": "mcp_tools_call" if mcp_tool_called else "not_observed",
            "alias_context_read": metadata.get("alias_context_read") is True,
            "context_file_present": metadata.get("context_file_present") is True,
            "context_file_sha256_present": metadata.get("context_file_sha256_present") is True,
            "context_sha256": str(metadata.get("context_sha256") or ""),
            "context_path_redacted": True,
            "runtime_context_file_proven": metadata.get("alias_context_read") is True,
            "custom_codex_agent_runtime_context_proven": context_valid,
            "task_digest_preserved": task_digest_preserved,
            "task_sha256": _sha256_text(task) if task else "",
            "tool_call_digest_present": True,
            "tool_call_sha256": tool_call_sha256,
            "prompt_text_recorded": False,
            "raw_prompt_recorded": False,
            "selected_alias": selected_alias,
            "expected_alias": expected_alias,
            "coding_aliases": coding_aliases,
            "coding_alias_bound_to_api_lane": binding_valid,
            "allowed_api_route_ids_enforced": bool(allowed_api_route_ids),
            "allowed_api_route_ids": allowed_api_route_ids,
            "selected_route_id": route_id if route_allowed else "",
            "route_allowed": route_allowed,
            "forbidden_stale_route_ids_enforced": bool(
                stale_route_guard_present and route_id not in forbidden_stale_route_ids
            ),
            "api_lane_called": False,
            "bounded_api_lane_mock_used": ok,
            "api_lane_truth_source": "bounded_mock_no_provider_call" if ok else "not_proven",
            "fallback_used": False,
            "local_imitation_used": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "universal_manual_chat_interception_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_universal_manual_chat_interception": True,
            "browser_authority_contract_enforced": True,
            "browser_can_supply_prompt_authority": False,
            "browser_can_supply_route_authority": False,
            "browser_can_supply_model_authority": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
    )


def delegate_to_dip_tool_descriptor() -> dict[str, Any]:
    return {
        "name": DELEGATE_TO_DIP_TOOL,
        "description": (
            "Delegate a bounded coding task to the WBP-owned API-lane alias from "
            "$WBP_PROFILE_DIR/wbp-agent-runtime-context.json. Returns proof, not "
            "product-ready native free-chat routing."
        ),
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "task": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Task to delegate. Do not include secrets.",
                },
                "expected_alias": {
                    "type": "string",
                    "description": "Optional coding alias expected in runtime context, e.g. DIP.",
                },
                "alias": {
                    "type": "string",
                    "description": "Backward-compatible alias field; expected_alias is preferred.",
                },
            },
            "required": ["task"],
        },
    }


def mcp_initialize_result(protocol_version: str | None = None) -> dict[str, Any]:
    return {
        "protocolVersion": protocol_version or MCP_PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
        "instructions": (
            "Use delegate_to_dip only when the user asks DIP, Agent 2, or another "
            "runtime-context coding alias to handle work. The tool must fail closed "
            "when alias context or route allowlist evidence is missing."
        ),
    }


def mcp_tools_list_result() -> dict[str, Any]:
    return {"tools": [delegate_to_dip_tool_descriptor()]}


def mcp_tools_call_result(
    params: Mapping[str, Any] | None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = params if isinstance(params, Mapping) else {}
    name = str(request.get("name") or "")
    arguments = request.get("arguments")
    if name != DELEGATE_TO_DIP_TOOL:
        packet = _command_packet(
            ok=False,
            machine_error_code="WBP_MCP_TOOL_NOT_FOUND",
            human_message="Requested WBP MCP tool is not available.",
            blocking_reasons=["tool_not_found"],
            extra={
                "mcp_server_visible": True,
                "delegate_to_dip_tool_listed": True,
                "delegate_to_dip_tool_called": False,
                "product_ready": False,
                "fallback_used": False,
                "local_imitation_used": False,
                "raw_backend_details_exposed": False,
                "secret_value_exposed": False,
            },
        )
        return {
            "content": [{"type": "text", "text": json.dumps(packet, sort_keys=True)}],
            "structuredContent": packet,
            "isError": True,
        }
    packet = build_delegate_to_dip_packet(
        arguments if isinstance(arguments, Mapping) else {},
        env=env,
        mcp_tool_called=True,
    )
    return {
        "content": [{"type": "text", "text": json.dumps(packet, sort_keys=True)}],
        "structuredContent": packet,
        "isError": packet.get("status") != "ok",
    }


def _response_result(response: Any) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        return {}
    result = response.get("result")
    return dict(result) if isinstance(result, Mapping) else {}


def _tool_call_packet_from_response(response: Any) -> dict[str, Any]:
    result = _response_result(response)
    structured = result.get("structuredContent")
    return dict(structured) if isinstance(structured, Mapping) else {}


def _config_probe_packet_from_item(response: Any) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        return {}
    packet_kind = str(response.get("packet_kind") or "")
    if packet_kind == CONFIG_PROBE_PACKET_KIND:
        return dict(response)
    result = response.get("result")
    if not isinstance(result, Mapping):
        return {}
    packet_kind = str(result.get("packet_kind") or "")
    return dict(result) if packet_kind == CONFIG_PROBE_PACKET_KIND else {}


def _delegate_tool_call_arguments_from_item(response: Any) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        return {}
    if str(response.get("method") or "") != "tools/call":
        return {}
    params = response.get("params")
    if not isinstance(params, Mapping):
        return {}
    if str(params.get("name") or "") != DELEGATE_TO_DIP_TOOL:
        return {}
    arguments = params.get("arguments")
    return dict(arguments) if isinstance(arguments, Mapping) else {}


def _transcript_prompt_sha256(arguments: Mapping[str, Any] | None) -> str:
    source = arguments if isinstance(arguments, Mapping) else {}
    task = _safe_text(source.get("task") or "", limit=4096)
    if task:
        return _sha256_text(task)
    return _hex_sha256(source.get("task_sha256") or source.get("prompt_sha256") or "")


def _transcript_call_sha256(arguments: Mapping[str, Any] | None) -> str:
    source = arguments if isinstance(arguments, Mapping) else {}
    explicit_digest = _hex_sha256(
        source.get("tool_call_sha256") or source.get("call_sha256") or ""
    )
    if explicit_digest:
        return explicit_digest
    if source:
        return _delegate_call_sha256(source)
    return ""


def _server_name_from_response(response: Any) -> str:
    server_info = _response_result(response).get("serverInfo")
    if not isinstance(server_info, Mapping):
        return ""
    return str(server_info.get("name") or "")


def build_reality_spike_proof_packet(
    transcript: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    transcript_items = [dict(item) for item in transcript if isinstance(item, Mapping)]
    config_packets = [
        packet
        for packet in (_config_probe_packet_from_item(item) for item in transcript_items)
        if packet
    ]
    call_requests = [
        arguments
        for arguments in (
            _delegate_tool_call_arguments_from_item(item) for item in transcript_items
        )
        if arguments
    ]
    mcp_server_visible = any(
        _server_name_from_response(item) == MCP_SERVER_NAME
        for item in transcript_items
    )
    delegate_to_dip_tool_listed = any(
        any(
            isinstance(tool, Mapping) and tool.get("name") == DELEGATE_TO_DIP_TOOL
            for tool in _response_result(item).get("tools", [])
        )
        for item in transcript_items
    )
    call_packets = [
        packet
        for packet in (_tool_call_packet_from_response(item) for item in transcript_items)
        if packet.get("packet_kind") == DELEGATE_PACKET_KIND
    ]
    call_packet = call_packets[-1] if call_packets else {}
    call_request_arguments = call_requests[-1] if call_requests else {}
    codex_mcp_config_loaded = any(
        packet.get("config_loaded") is True for packet in config_packets
    )
    prompt_digest = _transcript_prompt_sha256(call_request_arguments)
    call_digest = _transcript_call_sha256(call_request_arguments)
    prompt_digest_available = bool(prompt_digest and call_packet.get("task_sha256"))
    call_digest_available = bool(call_digest and call_packet.get("tool_call_sha256"))
    prompt_digest_bound_to_tool_packet = (
        call_packet.get("task_sha256") == prompt_digest
        if prompt_digest_available
        else False
    )
    call_digest_bound_to_tool_packet = (
        call_packet.get("tool_call_sha256") == call_digest
        if call_digest_available
        else False
    )
    delegate_to_dip_tool_called = call_packet.get("delegate_to_dip_tool_called") is True
    ok = bool(
        codex_mcp_config_loaded
        and mcp_server_visible
        and delegate_to_dip_tool_listed
        and delegate_to_dip_tool_called
        and call_packet.get("status") == "ok"
        and call_packet.get("alias_context_read") is True
        and call_packet.get("allowed_api_route_ids_enforced") is True
        and call_packet.get("forbidden_stale_route_ids_enforced") is True
        and call_packet.get("task_digest_preserved") is True
        and (not prompt_digest_available or prompt_digest_bound_to_tool_packet)
        and (not call_digest_available or call_digest_bound_to_tool_packet)
        and call_packet.get("local_imitation_used") is False
        and call_packet.get("fallback_used") is False
        and call_packet.get("product_ready") is False
    )
    blocking_reasons: list[str] = []
    if not codex_mcp_config_loaded:
        blocking_reasons.append("codex_mcp_config_not_loaded")
    if not mcp_server_visible:
        blocking_reasons.append("mcp_server_not_visible")
    if not delegate_to_dip_tool_listed:
        blocking_reasons.append("delegate_to_dip_tool_not_listed")
    if not delegate_to_dip_tool_called:
        blocking_reasons.append("delegate_to_dip_tool_not_called")
    if prompt_digest_available and not prompt_digest_bound_to_tool_packet:
        blocking_reasons.append("prompt_digest_not_bound_to_tool_packet")
    if call_digest_available and not call_digest_bound_to_tool_packet:
        blocking_reasons.append("call_digest_not_bound_to_tool_packet")
    if call_packet and call_packet.get("status") != "ok":
        blocking_reasons.extend(
            str(reason) for reason in call_packet.get("blocking_reasons", [])
        )
    if not call_packet:
        blocking_reasons.append("delegate_to_dip_packet_missing")

    transcript_fingerprint = json.dumps(
        [
            {
                "id": item.get("id"),
                "has_result": isinstance(item.get("result"), Mapping),
                "has_error": isinstance(item.get("error"), Mapping),
                "method": item.get("method"),
            }
            for item in transcript_items
        ],
        sort_keys=True,
    )
    return _command_packet(
        ok=ok,
        machine_error_code="OK"
        if ok
        else str(
            call_packet.get("machine_error_code") or "WBP_MCP_REALITY_SPIKE_NOT_PROVEN"
        ),
        human_message=(
            "WBP MCP delegate_to_dip reality spike is proven with tools/list "
            "and tools/call evidence."
            if ok
            else "WBP MCP delegate_to_dip reality spike is not proven by the supplied transcript."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "codex_mcp_config_loaded": codex_mcp_config_loaded,
            "codex_mcp_config_truth_source": (
                "transcript_config_probe" if config_packets else "not_observed"
            ),
            "mcp_server_visible": mcp_server_visible,
            "delegate_to_dip_tool_listed": delegate_to_dip_tool_listed,
            "delegate_to_dip_tool_visible": delegate_to_dip_tool_listed,
            "delegate_to_dip_tool_called": delegate_to_dip_tool_called,
            "alias_context_read": call_packet.get("alias_context_read") is True,
            "allowed_api_route_ids_enforced": (
                call_packet.get("allowed_api_route_ids_enforced") is True
            ),
            "forbidden_stale_route_ids_enforced": (
                call_packet.get("forbidden_stale_route_ids_enforced") is True
            ),
            "task_digest_preserved": call_packet.get("task_digest_preserved") is True,
            "prompt_digest_available": prompt_digest_available,
            "prompt_digest_bound_to_tool_packet": prompt_digest_bound_to_tool_packet,
            "call_digest_available": call_digest_available,
            "call_digest_bound_to_tool_packet": call_digest_bound_to_tool_packet,
            "tool_call_digest_present": call_packet.get("tool_call_digest_present") is True,
            "fallback_used": call_packet.get("fallback_used") is True,
            "local_imitation_used": call_packet.get("local_imitation_used") is True,
            "product_ready": call_packet.get("product_ready") is True,
            "bounded_api_lane_mock_used": call_packet.get("bounded_api_lane_mock_used") is True,
            "api_lane_called": call_packet.get("api_lane_called") is True,
            "tool_packet_status": str(call_packet.get("status") or ""),
            "tool_packet_machine_error_code": str(
                call_packet.get("machine_error_code") or ""
            ),
            "transcript_digest": _sha256_text(transcript_fingerprint),
            "raw_transcript_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
            "native_free_chat_router_proven": False,
            "universal_manual_chat_interception_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_universal_manual_chat_interception": True,
        },
    )


def handle_jsonrpc_message(
    message: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    method = str(message.get("method") or "")
    request_id = message.get("id")
    if request_id is None and method.startswith("notifications/"):
        return None
    if method == "initialize":
        params = message.get("params") if isinstance(message.get("params"), Mapping) else {}
        protocol_version = str(params.get("protocolVersion") or MCP_PROTOCOL_VERSION)
        result = mcp_initialize_result(protocol_version)
    elif method == "tools/list":
        result = mcp_tools_list_result()
    elif method == "tools/call":
        params = message.get("params") if isinstance(message.get("params"), Mapping) else {}
        result = mcp_tools_call_result(params, env=env)
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _read_message(stdin: BinaryIO) -> tuple[dict[str, Any] | None, bool]:
    first_line = stdin.readline()
    if not first_line:
        return None, False
    if first_line.lower().startswith(b"content-length:"):
        length = int(first_line.split(b":", 1)[1].strip())
        while True:
            header = stdin.readline()
            if header in {b"\r\n", b"\n", b""}:
                break
            if header.lower().startswith(b"content-length:"):
                length = int(header.split(b":", 1)[1].strip())
        body = stdin.read(length)
        return json.loads(body.decode("utf-8")), True
    text = first_line.decode("utf-8").strip()
    if not text:
        return {}, False
    return json.loads(text), False


def _write_message(stdout: BinaryIO, payload: Mapping[str, Any], *, framed: bool) -> None:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if framed:
        stdout.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
        stdout.write(body)
    else:
        stdout.write(body + b"\n")
    stdout.flush()


def run_stdio(
    *,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    env: Mapping[str, str] | None = None,
) -> int:
    input_stream = stdin or sys.stdin.buffer
    output_stream = stdout or sys.stdout.buffer
    while True:
        message, framed = _read_message(input_stream)
        if message is None:
            return 0
        if not message:
            continue
        response = handle_jsonrpc_message(message, env=env)
        if response is not None:
            _write_message(output_stream, response, framed=framed)


def main(argv: list[str] | None = None, *, stdout: TextIO | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--describe"]:
        target = stdout or sys.stdout
        print(json.dumps(mcp_tools_list_result(), sort_keys=True), file=target)
        return 0
    return run_stdio(env=os.environ)


if __name__ == "__main__":
    raise SystemExit(main())
