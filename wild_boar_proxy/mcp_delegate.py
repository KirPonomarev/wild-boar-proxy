# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
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
    aliases = [_safe_text(alias, limit=80) for alias in raw_aliases] if isinstance(raw_aliases, list) else []
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


def _command_packet(
    *,
    ok: bool,
    machine_error_code: str,
    human_message: str,
    blocking_reasons: list[str],
    extra: dict[str, Any],
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
            "packet_kind": DELEGATE_PACKET_KIND,
            "captured_at_utc": utc_now(),
            "final_status": (
                DELEGATE_FINAL_STATUS_WITH_LIMITS
                if ok
                else DELEGATE_FINAL_STATUS_NOT_PROVEN
            ),
            "result_status": "with_limits" if ok else "blocked",
            "blocking_reasons": blocking_reasons,
            **extra,
        },
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
        blocking_reasons.append(str(metadata.get("machine_error_code") or "FAIL_ALIAS_CONTEXT_MISSING"))
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


def _server_name_from_response(response: Any) -> str:
    server_info = _response_result(response).get("serverInfo")
    if not isinstance(server_info, Mapping):
        return ""
    return str(server_info.get("name") or "")


def build_reality_spike_proof_packet(
    transcript: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    transcript_items = [dict(item) for item in transcript if isinstance(item, Mapping)]
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
    delegate_to_dip_tool_called = call_packet.get("delegate_to_dip_tool_called") is True
    ok = bool(
        mcp_server_visible
        and delegate_to_dip_tool_listed
        and delegate_to_dip_tool_called
        and call_packet.get("status") == "ok"
        and call_packet.get("alias_context_read") is True
        and call_packet.get("allowed_api_route_ids_enforced") is True
        and call_packet.get("forbidden_stale_route_ids_enforced") is True
        and call_packet.get("task_digest_preserved") is True
        and call_packet.get("local_imitation_used") is False
        and call_packet.get("fallback_used") is False
        and call_packet.get("product_ready") is False
    )
    blocking_reasons: list[str] = []
    if not mcp_server_visible:
        blocking_reasons.append("mcp_server_not_visible")
    if not delegate_to_dip_tool_listed:
        blocking_reasons.append("delegate_to_dip_tool_not_listed")
    if not delegate_to_dip_tool_called:
        blocking_reasons.append("delegate_to_dip_tool_not_called")
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
        else str(call_packet.get("machine_error_code") or "WBP_MCP_REALITY_SPIKE_NOT_PROVEN"),
        human_message=(
            "WBP MCP delegate_to_dip reality spike is proven with tools/list and tools/call evidence."
            if ok
            else "WBP MCP delegate_to_dip reality spike is not proven by the supplied transcript."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "mcp_server_visible": mcp_server_visible,
            "delegate_to_dip_tool_listed": delegate_to_dip_tool_listed,
            "delegate_to_dip_tool_called": delegate_to_dip_tool_called,
            "alias_context_read": call_packet.get("alias_context_read") is True,
            "allowed_api_route_ids_enforced": (
                call_packet.get("allowed_api_route_ids_enforced") is True
            ),
            "forbidden_stale_route_ids_enforced": (
                call_packet.get("forbidden_stale_route_ids_enforced") is True
            ),
            "task_digest_preserved": call_packet.get("task_digest_preserved") is True,
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
