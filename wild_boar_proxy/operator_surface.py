# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Safe Codex Operator surface adapter for WBP web integration."""

from __future__ import annotations

import hashlib
import http.server
import ipaddress
import json
import os
import re
import shutil
import socket
import threading
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from wild_boar_proxy.external_models import transforms
from wild_boar_proxy.external_models.http_client import request_json
from wild_boar_proxy.external_models.paths import ExternalModelsPaths
from wild_boar_proxy.runtime import RuntimeErrorInfo


DEFAULT_ENDPOINT = "http://127.0.0.1:8318/v1"
DEFAULT_MODEL = "gpt-5.3-codex"
DEFAULT_CODEX_BIN = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_RUNTIME_CONFIG = (
    "/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml"
)
FORBIDDEN_BROWSER_FIELD_NAMES = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "path",
    "backend_id",
    "route_id",
    "runtime_config",
    "trace_wbp",
    "trace_observer",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"secret-key\s*:\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"api-keys\s*:\s*[^\n]{8,}", re.IGNORECASE),
]
WINDOW_SMOKE_PHRASE = "WBP_DEEPSEEK_WINDOW_SMOKE_OK"
WINDOW_TRACE_REFRESH_SMOKE_PHRASE = "WBP_DEEPSEEK_WINDOW_TRACE_REFRESH_OK"
STABLE_BRIDGE_WINDOW_SMOKE_PHRASE = "WBP_STABLE_BRIDGE_SMOKE_OK"
MIXED_DEEPSEEK_CODER_SMOKE_PHRASE = "WBP_MIXED_DEEPSEEK_CODER_OK"
WINDOW_SMOKE_PHRASES = (
    WINDOW_SMOKE_PHRASE,
    WINDOW_TRACE_REFRESH_SMOKE_PHRASE,
    STABLE_BRIDGE_WINDOW_SMOKE_PHRASE,
    MIXED_DEEPSEEK_CODER_SMOKE_PHRASE,
)


def _is_loopback_client_host(client_host: str) -> bool:
    candidate = str(client_host or "").strip()
    if candidate == "localhost":
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    return env


def _external_route_model_ids_from_packet(packet: dict[str, Any] | None) -> list[str]:
    if not isinstance(packet, dict):
        return []
    data = packet.get("data")
    if not isinstance(data, dict):
        return []
    routes = data.get("routes")
    if not isinstance(routes, list):
        return []
    model_ids: list[str] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        secret_ref = str(auth.get("secret_ref") or route.get("secret_ref") or "").strip()
        if route_id and route.get("enabled") is True and secret_ref:
            model_ids.append(route_id)
    return model_ids


def _external_route_from_packet(
    packet: dict[str, Any] | None, model_id: str
) -> dict[str, Any] | None:
    if not isinstance(packet, dict):
        return None
    data = packet.get("data")
    if not isinstance(data, dict):
        return None
    routes = data.get("routes")
    if not isinstance(routes, list):
        return None
    for route in routes:
        if not isinstance(route, dict):
            continue
        if str(route.get("route_id") or "").strip() != model_id:
            continue
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        secret_ref = str(auth.get("secret_ref") or route.get("secret_ref") or "").strip()
        if route.get("enabled") is True and secret_ref:
            return route
    return None


def _parse_simple_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _resolve_external_route_secret_value(route: dict[str, Any]) -> str:
    auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
    secret_ref = str(auth.get("secret_ref") or route.get("secret_ref") or "").strip()
    if not secret_ref:
        raise RuntimeError("route_secret_ref_missing")
    paths = ExternalModelsPaths.from_env()
    secrets_map = _parse_simple_env_file(paths.secrets_file)
    secret_value = str(secrets_map.get(secret_ref) or "").strip()
    if not secret_value:
        raise RuntimeError("route_secret_value_missing")
    return secret_value


def _route_completion_url(route: dict[str, Any]) -> str:
    return str(route.get("base_url") or "").rstrip("/") + str(route.get("endpoint_path") or "")


def _safe_route_digest(route: dict[str, Any]) -> str:
    safe_route = {
        "route_id": str(route.get("route_id") or ""),
        "provider": str(route.get("provider") or ""),
        "upstream_model": str(route.get("upstream_model") or ""),
        "endpoint_path": str(route.get("endpoint_path") or ""),
        "transform_profile": str(route.get("transform_profile") or ""),
        "thinking": route.get("thinking") if isinstance(route.get("thinking"), dict) else {},
    }
    return hashlib.sha256(
        json.dumps(safe_route, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _prompt_trace_hash_and_smoke_match(payload: dict[str, Any]) -> tuple[str, bool]:
    parts: list[str] = []
    instructions = str(payload.get("instructions") or "").strip()
    if instructions:
        parts.append(instructions)
    for message in _responses_payload_to_messages(payload):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            parts.append(content.strip())
    prompt_text = "\n".join(parts)
    prompt_hash = (
        hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        if prompt_text
        else ""
    )
    return prompt_hash, any(phrase in prompt_text for phrase in WINDOW_SMOKE_PHRASES)


def _json_loads_object(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _responses_payload_to_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    instructions = str(payload.get("instructions") or "").strip()
    if instructions:
        messages.append({"role": "developer", "content": instructions})
    raw_input = payload.get("input")
    if isinstance(raw_input, str) and raw_input.strip():
        return [*messages, {"role": "user", "content": raw_input.strip()}]
    if not isinstance(raw_input, list):
        return messages
    pending_tool_calls: list[dict[str, Any]] = []

    def flush_pending_tool_calls() -> None:
        if pending_tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": list(pending_tool_calls),
                }
            )
            pending_tool_calls.clear()

    for item in raw_input:
        if not isinstance(item, dict) or str(item.get("type") or "") != "message":
            item_type = str(item.get("type") or "")
            if item_type in {"input_text", "text"}:
                text = str(item.get("text") or item.get("content") or "").strip()
                if text:
                    flush_pending_tool_calls()
                    messages.append({"role": "user", "content": text})
            elif item_type == "function_call":
                call_id = str(item.get("call_id") or item.get("id") or "call_0")
                pending_tool_calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": str(item.get("name") or ""),
                            "arguments": str(item.get("arguments") or ""),
                        },
                    }
                )
            elif item_type == "function_call_output":
                flush_pending_tool_calls()
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(item.get("call_id") or "call_0"),
                        "content": str(item.get("output") or ""),
                    }
                )
            continue
        flush_pending_tool_calls()
        role = str(item.get("role") or "user").strip() or "user"
        content = item.get("content")
        parts: list[str] = []
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if str(block.get("type") or "") not in {"input_text", "output_text", "text"}:
                    continue
                text = str(block.get("text") or "").strip()
                if text:
                    parts.append(text)
        elif isinstance(content, str) and content.strip():
            parts.append(content.strip())
        if parts:
            messages.append({"role": role, "content": "\n".join(parts)})
    flush_pending_tool_calls()
    return messages


def _with_external_route_runtime_truth(
    messages: list[dict[str, Any]],
    route: dict[str, Any],
) -> list[dict[str, Any]]:
    route_id = str(route.get("route_id") or "").strip()
    provider = str(route.get("provider") or "").strip()
    upstream_model = str(route.get("upstream_model") or "").strip()
    thinking_metadata = transforms.route_thinking_metadata(route)
    thinking = thinking_metadata.get("thinking") if isinstance(thinking_metadata, dict) else {}
    thinking_text = ""
    if isinstance(thinking, dict):
        thinking_type = str(thinking.get("type") or "").strip()
        reasoning_effort = str(thinking.get("reasoning_effort") or "").strip()
        if thinking_type == "enabled":
            thinking_text = f", thinking enabled with reasoning_effort {reasoning_effort!r}"
        elif thinking_type:
            thinking_text = f", thinking {thinking_type!r}"
    if not route_id:
        return messages
    truth = (
        "Wild Boar Proxy runtime routing truth: this response is generated by "
        f"external API route {route_id!r}"
        + (f", provider {provider!r}" if provider else "")
        + (f", upstream model {upstream_model!r}" if upstream_model else "")
        + thinking_text
        + ". The application shell may be Codex Custom, but the answering model "
        "for this request is the external API route above. If the user asks which "
        "model or provider is answering, say the provider/upstream model from "
        "this runtime routing truth first. Do not say 'I am Codex CLI from OpenAI' "
        "or claim to be an OpenAI/Codex-native model unless the route provider or "
        "upstream model says so. Continue behaving as a Codex-compatible coding agent."
    )
    runtime_truth_message = {"role": "developer", "content": truth}
    insert_at = 0
    for index, message in enumerate(messages):
        if str(message.get("role") or "") not in {"system", "developer"}:
            insert_at = index
            break
        insert_at = index + 1
    return [*messages[:insert_at], runtime_truth_message, *messages[insert_at:]]


def _responses_result_payload(
    text: str,
    route_id: str,
    usage: dict[str, Any] | None = None,
    tool_calls: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    created_at = int(time.time())
    normalized_usage = None
    if isinstance(usage, dict):
        normalized_usage = {
            "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    output_items: list[dict[str, Any]] = []
    for index, call in enumerate(tool_calls or []):
        call_id = str(call.get("call_id") or call.get("id") or f"call_{index}")
        output_items.append(
            {
                "id": str(call.get("id") or f"fc_{hashlib.sha256(call_id.encode('utf-8')).hexdigest()[:12]}"),
                "type": "function_call",
                "call_id": call_id,
                "name": str(call.get("name") or ""),
                "arguments": str(call.get("arguments") or "{}"),
                "status": "completed",
            }
        )
    if text:
        output_items.append(
            {
                "id": "msg_wbp_external_route",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        )
    payload: dict[str, Any] = {
        "id": f"resp_{hashlib.sha256((route_id + text).encode('utf-8')).hexdigest()[:16]}",
        "object": "response",
        "created_at": created_at,
        "status": "completed",
        "model": route_id,
        "requested_model": route_id,
        "requested_model_available": True,
        "fallback_used": False,
        "fallback_chain": [route_id],
        "output_text": text,
        "output": output_items,
    }
    if normalized_usage is not None:
        payload["usage"] = normalized_usage
    return payload


def _responses_tools_to_chat_tools(tools: Any) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    if not isinstance(tools, list):
        return [], [], []
    chat_tools: list[dict[str, Any]] = []
    dropped_tool_types: list[str] = []
    unsupported_tool_types: list[str] = []
    text_only_droppable_tool_types = {"namespace", "web_search"}
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_type = str(tool.get("type") or "")
        if tool_type in {"", "function"}:
            function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
            name = str(tool.get("name") or function.get("name") or "").strip()
            if not name:
                continue
            description = str(tool.get("description") or function.get("description") or "").strip()
            parameters = (
                tool.get("parameters")
                if isinstance(tool.get("parameters"), dict)
                else (
                    tool.get("input_schema")
                    if isinstance(tool.get("input_schema"), dict)
                    else (
                        function.get("parameters")
                        if isinstance(function.get("parameters"), dict)
                        else {"type": "object", "properties": {}}
                    )
                )
            )
            chat_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                }
            )
            continue
        if tool_type in text_only_droppable_tool_types:
            dropped_tool_types.append(tool_type)
            continue
        unsupported_tool_types.append(tool_type)
    return chat_tools, sorted(set(dropped_tool_types)), sorted(set(unsupported_tool_types))


def _chat_completion_message_text_and_tool_calls(payload: Any) -> tuple[str, list[dict[str, str]]]:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        return "", []
    first = choices[0]
    if not isinstance(first, dict):
        return "", []
    message = first.get("message")
    if not isinstance(message, dict):
        return "", []
    text = str(message.get("content") or "").strip()
    raw_tool_calls = message.get("tool_calls")
    tool_calls: list[dict[str, str]] = []
    if isinstance(raw_tool_calls, list):
        for index, raw_call in enumerate(raw_tool_calls):
            if not isinstance(raw_call, dict):
                continue
            if str(raw_call.get("type") or "function") != "function":
                continue
            function = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
            name = str(function.get("name") or raw_call.get("name") or "").strip()
            if not name:
                continue
            tool_calls.append(
                {
                    "id": str(raw_call.get("id") or f"call_{index}"),
                    "call_id": str(raw_call.get("id") or f"call_{index}"),
                    "name": name,
                    "arguments": str(function.get("arguments") or raw_call.get("arguments") or "{}"),
                }
            )
    return text, tool_calls


def _responses_stream_body(payload: dict[str, Any]) -> bytes:
    response_id = str(payload.get("id") or "resp_wbp_external_route")
    created_at = int(payload.get("created_at") or int(time.time()))
    model = str(payload.get("model") or "")
    output = payload.get("output") if isinstance(payload.get("output"), list) else []
    item = output[0] if output and isinstance(output[0], dict) else {
        "id": "msg_wbp_external_route",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [],
    }
    item_id = str(item.get("id") or "msg_wbp_external_route")
    text = str(payload.get("output_text") or "")
    events = [
        (
            "response.created",
            {
                "type": "response.created",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "created_at": created_at,
                    "status": "in_progress",
                    "model": model,
                },
            },
        ),
        (
            "response.in_progress",
            {
                "type": "response.in_progress",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "created_at": created_at,
                    "status": "in_progress",
                    "model": model,
                },
            },
        ),
        (
            "response.output_item.added",
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": item_id,
                    "type": "message",
                    "status": "in_progress",
                    "role": "assistant",
                    "content": [],
                },
            },
        ),
        (
            "response.content_part.added",
            {
                "type": "response.content_part.added",
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            },
        ),
        (
            "response.output_text.delta",
            {
                "type": "response.output_text.delta",
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "delta": text,
            },
        ),
        (
            "response.output_text.done",
            {
                "type": "response.output_text.done",
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "text": text,
            },
        ),
        (
            "response.content_part.done",
            {
                "type": "response.content_part.done",
                "item_id": item_id,
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": text, "annotations": []},
            },
        ),
        (
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": item,
            },
        ),
        (
            "response.completed",
            {
                "type": "response.completed",
                "response": payload,
            },
        ),
    ]
    chunks: list[str] = []
    for event_name, event_payload in events:
        chunks.append(f"event: {event_name}\n")
        chunks.append(f"data: {json.dumps(event_payload, ensure_ascii=True)}\n\n")
    return "".join(chunks).encode("utf-8")


def _responses_runtime_error_status(exc: RuntimeErrorInfo) -> int:
    text = f"{exc.machine_error_code} {exc.message}".lower()
    if "timeout" in text or "timed out" in text:
        return 504
    return 502


def _responses_runtime_error_payload(exc: RuntimeErrorInfo) -> dict[str, Any]:
    return {
        "error": {
            "message": exc.message,
            "type": "provider_runtime_error",
            "code": exc.machine_error_code,
            "retryable": exc.operator_action == "retry",
        }
    }


def extract_local_api_key(config_path: Path) -> str:
    text = config_path.read_text(encoding="utf-8", errors="replace")
    api_keys = re.search(
        r"^\s*api-keys\s*:\s*\n\s*-\s*[\"']?([^\"'\s#]+)",
        text,
        re.MULTILINE,
    )
    if api_keys and len(api_keys.group(1).strip()) >= 8:
        return api_keys.group(1).strip()
    secret_key = re.search(r"^\s*secret-key\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    if secret_key:
        value = secret_key.group(1).strip().strip("\"'")
        if value and value != "\"\"" and len(value) >= 8:
            return value
    raise RuntimeError("stable runtime local API key shape invalid")


def forbidden_browser_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in FORBIDDEN_BROWSER_FIELD_NAMES:
                findings.append(key_path)
            findings.extend(forbidden_browser_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_browser_fields(value, f"{prefix}[{index}]"))
    return findings


def select_server_issued_model(model_id: str, allowed_models: list[str]) -> str:
    if model_id not in allowed_models:
        raise ValueError("model_id_not_server_issued")
    return model_id


def redact_text(text: str, secret_values: list[str] | None = None) -> str:
    redacted = text
    for secret in secret_values or []:
        if secret:
            redacted = redacted.replace(secret, "<redacted-secret>")
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("<redacted-secret>", redacted)
    return redacted


def _pid_digest(pid: int) -> str:
    return hashlib.sha256(str(pid).encode("utf-8")).hexdigest()[:16]


def _endpoint_host(endpoint: str) -> str:
    text = endpoint.strip()
    if text.startswith("[") and "]:" in text:
        return text[1:].split("]:", 1)[0].lower()
    if ":" not in text:
        return text.lower()
    return text.rsplit(":", 1)[0].lower()


def _is_local_host(host: str) -> bool:
    normalized = host.strip().lower().strip("[]")
    return normalized in {"127.0.0.1", "::1", "localhost"}


def _allowed_local_endpoints(*urls: str) -> set[str]:
    allowed: set[str] = set()
    for url in urls:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").strip().lower()
        port = parsed.port
        if host and port and _is_local_host(host):
            allowed.add(f"{host}:{port}")
            if host == "127.0.0.1":
                allowed.add(f"localhost:{port}")
            if host == "localhost":
                allowed.add(f"127.0.0.1:{port}")
    return allowed


def _process_tree_snapshot(root_pid: int) -> dict[str, Any]:
    try:
        process = subprocess.run(
            ["ps", "-Ao", "pid=,ppid=,command="],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return {"public_entries": [], "raw_pids": []}
    rows: dict[int, dict[str, Any]] = {}
    children: dict[int, list[int]] = {}
    for raw_line in process.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        pid = int(parts[0])
        ppid = int(parts[1])
        command_text = parts[2].strip() if len(parts) >= 3 else ""
        command_basename = ""
        if command_text:
            command_basename = Path(command_text.split()[0]).name
        rows[pid] = {
            "pid": pid,
            "ppid": ppid,
            "command_present": bool(command_text),
            "command_basename": command_basename,
        }
        children.setdefault(ppid, []).append(pid)
    if root_pid not in rows:
        return {"public_entries": [], "raw_pids": []}
    descendants: list[dict[str, Any]] = []
    raw_pids: list[int] = []
    queue = [root_pid]
    seen: set[int] = set()
    while queue:
        pid = queue.pop(0)
        if pid in seen:
            continue
        seen.add(pid)
        row = rows.get(pid)
        if row is None:
            continue
        raw_pids.append(pid)
        descendants.append(
            {
                "pid_digest": _pid_digest(pid),
                "is_root": pid == root_pid,
                "parent_pid_digest": _pid_digest(row["ppid"]),
                "command_present": row["command_present"],
                "command_basename": row["command_basename"],
            }
        )
        queue.extend(children.get(pid, []))
    return {"public_entries": descendants, "raw_pids": raw_pids}


def _network_sample_for_pid(pid: int) -> dict[str, Any]:
    try:
        process = subprocess.run(
            ["lsof", "-n", "-P", "-a", "-i", "-p", str(pid)],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return {"peer_endpoints": [], "peer_endpoint_count": 0, "local_only": True}
    peer_endpoints: list[dict[str, Any]] = []
    for raw_line in process.stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("COMMAND"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name_token = parts[-2] if parts[-1].startswith("(") and len(parts) >= 2 else parts[-1]
        if "->" not in name_token:
            continue
        peer = name_token.split("->", 1)[1].strip()
        host = _endpoint_host(peer)
        peer_endpoints.append(
            {
                "endpoint": peer,
                "host_class": "local" if _is_local_host(host) else "non_local",
            }
        )
    local_only = all(item["host_class"] == "local" for item in peer_endpoints)
    return {
        "peer_endpoints": peer_endpoints,
        "peer_endpoint_count": len(peer_endpoints),
        "local_only": local_only,
    }


ANCILLARY_COMMAND_BASENAMES = {"git", "git-remote-http", "git-remote-https", "sh", "bash", "zsh"}


class OwnerSideProcessNetworkObserver:
    def __init__(self, *, root_pid: int, allowed_local_endpoints: set[str]) -> None:
        self.root_pid = root_pid
        self.allowed_local_endpoints = set(allowed_local_endpoints)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._samples: list[dict[str, Any]] = []

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._samples.append(self._sample_once())
            time.sleep(0.25)

    def _sample_once(self) -> dict[str, Any]:
        tree_snapshot = _process_tree_snapshot(self.root_pid)
        tree = tree_snapshot.get("public_entries", [])
        raw_pids = tree_snapshot.get("raw_pids", [])
        public_by_digest = {
            str(entry.get("pid_digest") or ""): entry for entry in tree if isinstance(entry, dict)
        }
        peer_endpoints: list[dict[str, Any]] = []
        for pid_value in raw_pids:
            network = _network_sample_for_pid(int(pid_value))
            pid_digest = _pid_digest(int(pid_value))
            entry = public_by_digest.get(pid_digest, {})
            for peer in network.get("peer_endpoints", []):
                if not isinstance(peer, dict):
                    continue
                peer_endpoints.append(
                    {
                        **peer,
                        "pid_digest": pid_digest,
                        "is_root_process": entry.get("is_root") is True,
                        "command_basename": str(entry.get("command_basename") or ""),
                    }
                )
        return {
            "process_tree_seen": bool(tree),
            "process_count": len(tree),
            "process_tree": tree,
            "peer_endpoints": peer_endpoints,
        }

    def packet(self, *, warning_classes: list[str]) -> dict[str, Any]:
        process_tree_observed = any(sample.get("process_tree_seen") for sample in self._samples)
        sample_count = len(self._samples)
        peer_endpoints = [
            item
            for sample in self._samples
            for item in sample.get("peer_endpoints", [])
            if isinstance(item, dict) and str(item.get("endpoint") or "")
        ]
        deduped_endpoints = list(
            {
                (str(item.get("endpoint") or ""), str(item.get("host_class") or "")): item
                for item in peer_endpoints
            }.values()
        )
        non_local = [item for item in deduped_endpoints if item.get("host_class") == "non_local"]
        local = [item for item in deduped_endpoints if item.get("host_class") == "local"]
        allowed_local_observed = any(
            str(item.get("endpoint") or "") in self.allowed_local_endpoints for item in local
        )
        ancillary_non_local = [
            item
            for item in non_local
            if str(item.get("command_basename") or "") in ANCILLARY_COMMAND_BASENAMES
        ]
        model_or_ambiguous_non_local = [
            item for item in non_local if item not in ancillary_non_local
        ]
        if not process_tree_observed or sample_count == 0:
            classification = "insufficient_observation"
        elif not allowed_local_observed:
            classification = "insufficient_observation"
        elif model_or_ambiguous_non_local:
            classification = "direct_model_egress_observed"
        elif ancillary_non_local:
            classification = "ancillary_non_model_egress_observed"
        elif local:
            classification = "wbp_forward_only_proven"
        else:
            classification = "insufficient_observation"
        return {
            "status": "ok",
            "machine_error_code": "OK",
            "process_tree_observed": process_tree_observed,
            "sample_count": sample_count,
            "observed_process_count_max": max(
                (int(sample.get("process_count") or 0) for sample in self._samples),
                default=0,
            ),
            "allowed_local_endpoints": sorted(self.allowed_local_endpoints),
            "allowed_local_endpoint_observed": allowed_local_observed,
            "peer_endpoints": deduped_endpoints,
            "non_local_peer_endpoints_present": bool(non_local),
            "classification": classification,
            "direct_non_wbp_model_egress_absent_proven": classification in {
                "wbp_forward_only_proven",
                "ancillary_non_model_egress_observed",
            },
            "raw_pid_exposed": False,
            "pid_not_exposed_to_browser": True,
            "secret_value_recorded": False,
        }


def _run_command_with_observation(
    command: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    prompt: str,
    timeout_seconds: int,
    allowed_local_endpoints: set[str],
    warning_classes_from_stderr: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    observer = OwnerSideProcessNetworkObserver(
        root_pid=process.pid,
        allowed_local_endpoints=allowed_local_endpoints,
    )
    observer.start()
    timed_out = False
    try:
        _, stderr = process.communicate(
            input=prompt,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        process.kill()
        _, stderr = process.communicate()
        stderr = stderr or exc.stderr or ""
    finally:
        observer.stop()
    warning_classes = (
        warning_classes_from_stderr(stderr) if warning_classes_from_stderr is not None else []
    )
    return {
        "exit_code": process.returncode if process.returncode is not None else 127,
        "stderr": stderr,
        "timed_out": timed_out,
        "process_network_observation_packet": observer.packet(warning_classes=warning_classes),
    }


def build_codex_config(
    *,
    endpoint: str,
    model_id: str,
    provider_name: str = "cliproxy",
    provider_label: str = "CLIProxyAPI via Wild Boar Proxy",
    wire_api: str = "responses",
    sandbox_mode: str = "read-only",
) -> str:
    return (
        f'model = "{model_id}"\n'
        f'model_provider = "{provider_name}"\n'
        'approval_policy = "never"\n'
        f'sandbox_mode = "{sandbox_mode}"\n'
        "disable_response_storage = true\n\n"
        f"[model_providers.{provider_name}]\n"
        f'name = "{provider_label}"\n'
        f'base_url = "{endpoint}"\n'
        'env_key = "OPENAI_API_KEY"\n'
        f'wire_api = "{wire_api}"\n'
    )


def _body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _bounded_trace_error_fields(body: bytes) -> dict[str, str]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return {}
    fields: dict[str, str] = {}
    for source, target in (
        ("type", "response_error_type"),
        ("code", "response_error_code"),
        ("param", "response_error_param"),
    ):
        value = str(error.get(source) or "").strip()
        if value:
            fields[target] = value[:80]
    message = str(error.get("message") or "").strip()
    if message:
        fields["response_error_message_bounded"] = message[:240]
    return fields


def _forward_request_headers(headers: dict[str, str]) -> dict[str, str]:
    excluded = {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "cookie",
    }
    forwarded: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() not in excluded:
            forwarded[key] = value
    forwarded.setdefault("Content-Type", "application/json")
    return forwarded


def _empty_trace_packet() -> dict[str, Any]:
    return {
        "request_observed": False,
        "request_count": 0,
        "response_observed": False,
        "forwarded_to_wbp": False,
        "forwarded_endpoint": "",
        "method": "",
        "path": "",
        "request_body_sha256": "",
        "response_body_sha256": "",
        "upstream_status": None,
        "prompt_body_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_account_id_recorded": False,
        "raw_backend_id_recorded": False,
        "response_error_code": "",
        "response_error_message_bounded": "",
        "response_error_param": "",
        "response_error_type": "",
        "machine_error_code": "TRACE_NOT_STARTED",
    }


class _TraceObserverServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler: type[http.server.BaseHTTPRequestHandler], observer: "WbpTraceObserver") -> None:
        super().__init__(server_address, handler)
        self.observer = observer


class _TraceObserverHandler(http.server.BaseHTTPRequestHandler):
    server: _TraceObserverServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        status, body, headers = self.server.observer.forward(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")),
        )
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() not in {"connection", "transfer-encoding", "content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WbpTraceObserver:
    """Temporary localhost proxy that records redacted WBP path evidence."""

    def __init__(self, *, downstream_endpoint: str) -> None:
        self.downstream_endpoint = downstream_endpoint.rstrip("/")
        self._httpd: _TraceObserverServer | None = None
        self._thread: threading.Thread | None = None
        self.listen_endpoint = ""
        self._packet = _empty_trace_packet()

    def __enter__(self) -> "WbpTraceObserver":
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        self._httpd = _TraceObserverServer(("127.0.0.1", port), _TraceObserverHandler, self)
        self.listen_endpoint = f"http://127.0.0.1:{port}/v1"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self._packet = {
            **_empty_trace_packet(),
            "machine_error_code": "TRACE_READY",
            "listen_endpoint": self.listen_endpoint,
            "downstream_endpoint": self.downstream_endpoint,
        }
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def forward(self, *, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes, dict[str, str]]:
        parsed_path = urllib.parse.urlsplit(path).path
        allowed = method == "GET" and parsed_path in {"/v1/models", "/models"}
        allowed = allowed or method == "POST" and parsed_path in {"/v1/responses", "/responses", "/v1/chat/completions", "/chat/completions"}
        forwarded_url = f"{self.downstream_endpoint}{path[3:] if path.startswith('/v1/') else path}"
        request_digest = _body_digest(body) if body else ""
        request_count = int(self._packet.get("request_count") or 0) + 1
        self._packet.update(
            {
                "request_observed": True,
                "request_count": request_count,
                "method": method,
                "path": path,
                "request_body_sha256": request_digest,
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
                "raw_account_id_recorded": False,
                "raw_backend_id_recorded": False,
            }
        )
        if not allowed:
            response_body = json.dumps({"error": {"message": "trace observer path not allowed"}}).encode("utf-8")
            self._packet.update({"machine_error_code": "TRACE_PATH_NOT_ALLOWED", "upstream_status": 403})
            return 403, response_body, {"Content-Type": "application/json"}
        request_headers = _forward_request_headers(headers)
        request = urllib.request.Request(forwarded_url, data=body if method != "GET" else None, headers=request_headers, method=method)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=60) as response:
                response_body = response.read()
                status = int(response.status)
                response_headers = {"Content-Type": response.headers.get("Content-Type", "application/json")}
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status = int(exc.code)
            response_headers = {"Content-Type": exc.headers.get("Content-Type", "application/json")}
        except Exception as exc:
            response_body = json.dumps({"error": {"message": "trace observer upstream request failed"}}).encode("utf-8")
            status = 502
            response_headers = {"Content-Type": "application/json"}
            self._packet.update({"machine_error_code": type(exc).__name__})
        if 200 <= status < 400:
            machine_error_code = "OK"
        elif 400 <= status < 500:
            machine_error_code = f"TRACE_UPSTREAM_HTTP_{status}"
        else:
            machine_error_code = self._packet.get("machine_error_code") or "TRACE_UPSTREAM_FAILED"
        self._packet.update(
            {
                "response_observed": True,
                "forwarded_to_wbp": True,
                "forwarded_endpoint": self.downstream_endpoint,
                "upstream_status": status,
                "response_body_sha256": _body_digest(response_body) if response_body else "",
                "machine_error_code": machine_error_code,
            }
        )
        if status < 400:
            self._packet.update(
                {
                    "response_error_code": "",
                    "response_error_message_bounded": "",
                    "response_error_param": "",
                    "response_error_type": "",
                }
            )
        elif response_body:
            self._packet.update(_bounded_trace_error_fields(response_body))
        return status, response_body, response_headers

    def packet(self) -> dict[str, Any]:
        packet = dict(self._packet)
        packet["observer_closed"] = self._httpd is None
        return packet


class _ExternalRouteAdapterServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[http.server.BaseHTTPRequestHandler],
        adapter: "ExternalRouteResponsesAdapter",
    ) -> None:
        super().__init__(server_address, handler)
        self.adapter = adapter


class _ExternalRouteAdapterHandler(http.server.BaseHTTPRequestHandler):
    server: _ExternalRouteAdapterServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        status, headers, body = self.server.adapter.handle(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")),
            client_host=str(self.client_address[0] if self.client_address else ""),
        )
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() != "content-length":
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ExternalRouteResponsesAdapter:
    def __init__(
        self,
        *,
        route: dict[str, Any],
        expected_api_key: str,
        route_secret: str,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.route = route
        self.expected_api_key = expected_api_key
        self.route_secret = route_secret
        self.timeout_seconds = timeout_seconds
        self._server: _ExternalRouteAdapterServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def listen_endpoint(self) -> str:
        if self._server is None:
            return "http://127.0.0.1:0/v1"
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    def __enter__(self) -> "ExternalRouteResponsesAdapter":
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        self._server = _ExternalRouteAdapterServer(
            ("127.0.0.1", port),
            _ExternalRouteAdapterHandler,
            self,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def handle(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
        client_host: str = "",
    ) -> tuple[int, dict[str, str], bytes]:
        normalized_path = path.split("?", 1)[0]
        if str(headers.get("Authorization") or "") != f"Bearer {self.expected_api_key}":
            payload = {"error": {"message": "unauthorized", "type": "auth_error"}}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 401, {"Content-Type": "application/json"}, body_bytes
        if method == "GET" and normalized_path in {"/v1/models", "/models"}:
            payload = {"data": [{"id": str(self.route.get("route_id") or "")}]}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 200, {"Content-Type": "application/json"}, body_bytes
        if method != "POST" or normalized_path not in {"/v1/responses", "/responses"}:
            payload = {"error": {"message": "unsupported path", "type": "invalid_request_error"}}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 404, {"Content-Type": "application/json"}, body_bytes
        try:
            request_payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {"error": {"message": "invalid json body", "type": "invalid_request_error"}}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 400, {"Content-Type": "application/json"}, body_bytes
        chat_tools, dropped_tool_types, unsupported_tool_types = _responses_tools_to_chat_tools(
            request_payload.get("tools")
        )
        if unsupported_tool_types:
            payload = {
                "error": {
                    "message": "unsupported Responses tool type for this WBP route: "
                    + ", ".join(unsupported_tool_types)[:160],
                    "type": "invalid_request_error",
                    "code": "unsupported_tool_type",
                    "param": "tools",
                }
            }
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 400, {"Content-Type": "application/json"}, body_bytes
        requested_model = str(request_payload.get("model") or "").strip()
        route_id = str(self.route.get("route_id") or "").strip()
        if requested_model and requested_model != route_id:
            payload = {
                "error": {
                    "message": "unknown model for this WBP route",
                    "type": "invalid_request_error",
                    "code": "model_not_found",
                }
            }
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 404, {"Content-Type": "application/json"}, body_bytes
        messages = _responses_payload_to_messages(request_payload)
        if not messages:
            payload = {"error": {"message": "responses input did not contain prompt text", "type": "invalid_request_error"}}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 400, {"Content-Type": "application/json"}, body_bytes
        messages = _with_external_route_runtime_truth(messages, self.route)
        requested_max_tokens = int(request_payload.get("max_output_tokens") or 256)
        thinking_metadata = transforms.route_thinking_metadata(self.route)
        thinking = thinking_metadata.get("thinking")
        if isinstance(thinking, dict) and thinking.get("type") == "enabled":
            requested_max_tokens = max(requested_max_tokens, 2048)
        upstream_payload: dict[str, Any] = {
            "model": str(self.route.get("upstream_model") or ""),
            "messages": messages,
            "stream": False,
            "max_tokens": requested_max_tokens,
        }
        thinking_metadata = transforms.apply_route_thinking_policy(upstream_payload, self.route)
        if chat_tools:
            upstream_payload["tools"] = chat_tools
            if request_payload.get("tool_choice") is not None:
                upstream_payload["tool_choice"] = request_payload.get("tool_choice")
        transform_profile = str(self.route.get("transform_profile") or "")
        if transform_profile in {
            "openai_chat_system_to_developer",
            "openai_chat_developer_to_system",
        }:
            transformed_messages: list[dict[str, Any]] = []
            for message in messages:
                role = str(message.get("role") or "user")
                if transform_profile == "openai_chat_system_to_developer" and role == "system":
                    role = "developer"
                elif transform_profile == "openai_chat_developer_to_system" and role == "developer":
                    role = "system"
                transformed = dict(message)
                transformed["role"] = role
                transformed_messages.append(transformed)
            upstream_payload["messages"] = transformed_messages
        try:
            response = request_json(
                url=_route_completion_url(self.route),
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.route_secret}",
                    "Accept": "application/json",
                },
                payload=upstream_payload,
                timeout_seconds=self.timeout_seconds,
            )
        except RuntimeErrorInfo as exc:
            body_bytes = json.dumps(
                _responses_runtime_error_payload(exc), ensure_ascii=True
            ).encode("utf-8")
            return (
                _responses_runtime_error_status(exc),
                {"Content-Type": "application/json"},
                body_bytes,
            )
        except Exception as exc:
            body_bytes = json.dumps(
                {
                    "error": {
                        "message": "external route request failed",
                        "type": "upstream_error",
                        "code": type(exc).__name__,
                    }
                },
                ensure_ascii=True,
            ).encode("utf-8")
            return 502, {"Content-Type": "application/json"}, body_bytes
        if response.status_code >= 400:
            body_bytes = json.dumps(response.payload, ensure_ascii=True).encode("utf-8")
            return response.status_code, {"Content-Type": "application/json"}, body_bytes
        text, tool_calls = _chat_completion_message_text_and_tool_calls(response.payload)
        if not text and not tool_calls:
            try:
                text, _response_meta = transforms.extract_check_response(self.route, response.payload)
            except RuntimeErrorInfo as exc:
                body_bytes = json.dumps(
                    _responses_runtime_error_payload(exc), ensure_ascii=True
                ).encode("utf-8")
                return (
                    _responses_runtime_error_status(exc),
                    {"Content-Type": "application/json"},
                    body_bytes,
                )
        payload = _responses_result_payload(
            text,
            str(self.route.get("route_id") or ""),
            response.payload.get("usage") if isinstance(response.payload, dict) else None,
            tool_calls,
        )
        payload["provider"] = str(self.route.get("provider") or "")
        payload["upstream_model"] = str(self.route.get("upstream_model") or "")
        payload["thinking"] = thinking_metadata.get("thinking")
        payload["api_parameter_sent"] = thinking_metadata.get("api_parameter_sent") is True
        payload["max_tokens_sent"] = requested_max_tokens
        payload["intelligence_measured"] = False
        payload["label_source"] = str(thinking_metadata.get("label_source") or "unavailable_unknown")
        if dropped_tool_types:
            payload["wbp_route_tool_policy"] = "unsupported_codex_tools_dropped_for_text_only"
            payload["dropped_responses_tool_types"] = dropped_tool_types
        wants_stream = bool(request_payload.get("stream")) or "text/event-stream" in str(headers.get("Accept") or "")
        if wants_stream:
            body_bytes = _responses_stream_body(payload)
            return 200, {"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}, body_bytes
        body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        return 200, {"Content-Type": "application/json"}, body_bytes


class _HybridOpenAICompatServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[http.server.BaseHTTPRequestHandler],
        adapter: "HybridOpenAICompatAdapter",
    ) -> None:
        super().__init__(server_address, handler)
        self.adapter = adapter


class _HybridOpenAICompatHandler(http.server.BaseHTTPRequestHandler):
    server: _HybridOpenAICompatServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        status, headers, body = self.server.adapter.handle(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")),
            client_host=str(self.client_address[0] if self.client_address else ""),
        )
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() != "content-length":
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class HybridOpenAICompatAdapter:
    """Persistent localhost bridge that merges native and route-backed models."""

    def __init__(
        self,
        *,
        downstream_endpoint: str,
        expected_api_key: str,
        routes: list[dict[str, Any]],
        hidden_downstream_model_ids: list[str] | None = None,
        forced_route_model_id: str = "",
        listen_port: int | None = None,
        timeout_seconds: float = 120.0,
        allow_missing_auth_from_loopback: bool = False,
    ) -> None:
        self.downstream_endpoint = downstream_endpoint.rstrip("/")
        self.expected_api_key = expected_api_key
        self.listen_port = listen_port
        self.timeout_seconds = timeout_seconds
        self.allow_missing_auth_from_loopback = allow_missing_auth_from_loopback
        self._server: _HybridOpenAICompatServer | None = None
        self._thread: threading.Thread | None = None
        self._route_adapters: dict[str, ExternalRouteResponsesAdapter] = {}
        self._route_records: dict[str, dict[str, Any]] = {}
        self._route_model_ids: list[str] = []
        self._trace_records: list[dict[str, Any]] = []
        self._trace_context: dict[str, Any] = {}
        self._trace_lock = threading.Lock()
        self._hidden_downstream_model_ids = {
            str(model_id).strip()
            for model_id in (hidden_downstream_model_ids or [])
            if str(model_id).strip()
        }
        self._forced_route_model_id = str(forced_route_model_id or "").strip()
        for route in routes:
            if not isinstance(route, dict):
                continue
            route_id = str(route.get("route_id") or "").strip()
            auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
            secret_ref = str(auth.get("secret_ref") or route.get("secret_ref") or "").strip()
            if not route_id or route.get("enabled") is not True or not secret_ref:
                continue
            try:
                route_secret = _resolve_external_route_secret_value(route)
            except RuntimeError:
                continue
            self._route_adapters[route_id] = ExternalRouteResponsesAdapter(
                route=route,
                expected_api_key=expected_api_key,
                route_secret=route_secret,
                timeout_seconds=timeout_seconds,
            )
            self._route_records[route_id] = route
            self._route_model_ids.append(route_id)

    @property
    def listen_endpoint(self) -> str:
        if self._server is None:
            return "http://127.0.0.1:0/v1"
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    @property
    def route_model_ids(self) -> list[str]:
        return list(self._route_model_ids)

    def set_trace_context(self, context: dict[str, Any]) -> None:
        safe_context = {
            "launch_id": str(context.get("launch_id") or ""),
            "trace_id": str(context.get("trace_id") or ""),
            "selected_model": str(context.get("selected_model") or ""),
            "api_reasoning_option_id": str(context.get("api_reasoning_option_id") or ""),
            "launch_route_digest": str(context.get("launch_route_digest") or ""),
        }
        with self._trace_lock:
            self._trace_context = safe_context

    def trace_snapshot(self) -> dict[str, Any]:
        with self._trace_lock:
            records = [dict(record) for record in self._trace_records]
            context = dict(self._trace_context)
        last_record = records[-1] if records else {}
        return {
            "schema_version": 1,
            "packet_kind": "hybrid_openai_compat_prompt_trace",
            "captured_at_utc": utc_now(),
            "trace_context": context,
            "request_count": len(records),
            "last_record": last_record,
            "records": records[-5:],
            "raw_prompt_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
        }

    def __enter__(self) -> "HybridOpenAICompatAdapter":
        port = self.listen_port
        if port is None:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = int(sock.getsockname()[1])
        self._server = _HybridOpenAICompatServer(
            ("127.0.0.1", port),
            _HybridOpenAICompatHandler,
            self,
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def handle(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
        client_host: str = "",
    ) -> tuple[int, dict[str, str], bytes]:
        normalized_path = path.split("?", 1)[0]
        authorization = str(headers.get("Authorization") or "")
        auth_matches = authorization == f"Bearer {self.expected_api_key}"
        loopback_missing_auth = (
            self.allow_missing_auth_from_loopback
            and authorization == ""
            and _is_loopback_client_host(client_host)
        )
        if not auth_matches and not loopback_missing_auth:
            payload = {"error": {"message": "unauthorized", "type": "auth_error"}}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 401, {"Content-Type": "application/json"}, body_bytes
        if loopback_missing_auth:
            headers = {**headers, "Authorization": f"Bearer {self.expected_api_key}"}
        if method == "GET" and normalized_path in {"/v1/models", "/models"}:
            return self._handle_models(path, headers)
        if method == "POST" and normalized_path in {"/v1/responses", "/responses"}:
            try:
                request_payload = json.loads(body.decode("utf-8"))
            except Exception:
                payload = {"error": {"message": "invalid json body", "type": "invalid_request_error"}}
                body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                return 400, {"Content-Type": "application/json"}, body_bytes
            requested_model = str(request_payload.get("model") or "").strip()
            prompt_hash, smoke_match = _prompt_trace_hash_and_smoke_match(request_payload)
            route_adapter = self._route_adapters.get(requested_model)
            original_requested_model = requested_model
            forced_route_used = False
            if route_adapter is None and self._forced_route_model_id:
                route_adapter = self._route_adapters.get(self._forced_route_model_id)
                if route_adapter is not None:
                    forced_route_used = True
                    request_payload = dict(request_payload)
                    request_payload["model"] = self._forced_route_model_id
                    body = json.dumps(request_payload, ensure_ascii=True).encode("utf-8")
            if route_adapter is not None:
                effective_model = self._forced_route_model_id if forced_route_used else requested_model
                route_record = self._route_records.get(effective_model, {})
                status, response_headers, response_body = route_adapter.handle(
                    method=method,
                    path=normalized_path,
                    headers=headers,
                    body=body,
                )
                self._record_prompt_trace(
                    status=status,
                    path=normalized_path,
                    requested_model=original_requested_model,
                    effective_route_model=effective_model,
                    forced_route_used=forced_route_used,
                    route=route_record,
                    prompt_hash=prompt_hash,
                    smoke_match=smoke_match,
                    response_body=response_body,
                )
                return status, response_headers, response_body
            status, response_headers, response_body = self._forward_downstream(
                method=method,
                path=path,
                headers=headers,
                body=body,
            )
            self._record_downstream_trace(
                status=status,
                path=normalized_path,
                requested_model=original_requested_model,
                prompt_hash=prompt_hash,
                smoke_match=smoke_match,
                response_body=response_body,
            )
            return status, response_headers, response_body
        return self._forward_downstream(method=method, path=path, headers=headers, body=body)

    def _record_prompt_trace(
        self,
        *,
        status: int,
        path: str,
        requested_model: str,
        effective_route_model: str,
        forced_route_used: bool,
        route: dict[str, Any],
        prompt_hash: str,
        smoke_match: bool,
        response_body: bytes,
    ) -> None:
        route_digest = _safe_route_digest(route) if route else ""
        response_payload = _json_loads_object(response_body)
        response_seen = 200 <= status < 500 and bool(response_body)
        record = {
            **self._trace_context,
            "captured_at_utc": utc_now(),
            "path": path,
            "request_seen_after_launch": bool(self._trace_context.get("launch_id")),
            "requested_model": requested_model,
            "effective_route_model": effective_route_model,
            "forced_route_used": forced_route_used,
            "selected_model": str(self._trace_context.get("selected_model") or ""),
            "route_digest": route_digest,
            "route_digest_matches_launch": bool(
                route_digest
                and route_digest == str(self._trace_context.get("launch_route_digest") or "")
            ),
            "provider_called": True,
            "provider_id": str(route.get("provider") or ""),
            "upstream_model": str(route.get("upstream_model") or ""),
            "api_reasoning_option_id": str(
                self._trace_context.get("api_reasoning_option_id") or ""
            ),
            "upstream_status": int(status),
            "response_seen": response_seen,
            "response_body_sha256": hashlib.sha256(response_body).hexdigest() if response_body else "",
            "prompt_hash": prompt_hash,
            "known_smoke_phrase_matched": smoke_match,
            "chatgpt_route_used": False,
            "api_only_calls_chatgpt": False,
            "fallback_used": False,
            "raw_prompt_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "response_text_counts_as_model_truth": False,
            "model_self_report_counts_as_runtime_truth": False,
        }
        if isinstance(response_payload.get("error"), dict):
            error = response_payload["error"]
            record["response_error_type"] = str(error.get("type") or "")
            record["response_error_code"] = str(error.get("code") or "")
        with self._trace_lock:
            self._trace_records.append(record)
            self._trace_records = self._trace_records[-20:]

    def _record_downstream_trace(
        self,
        *,
        status: int,
        path: str,
        requested_model: str,
        prompt_hash: str,
        smoke_match: bool,
        response_body: bytes,
    ) -> None:
        response_payload = _json_loads_object(response_body)
        response_seen = 200 <= status < 500 and bool(response_body)
        record = {
            **self._trace_context,
            "captured_at_utc": utc_now(),
            "path": path,
            "request_seen_after_launch": bool(self._trace_context.get("launch_id")),
            "requested_model": requested_model,
            "effective_route_model": "",
            "forced_route_used": False,
            "selected_model": str(self._trace_context.get("selected_model") or ""),
            "route_digest": "",
            "route_digest_matches_launch": False,
            "provider_called": False,
            "downstream_called": True,
            "provider_id": "",
            "upstream_model": "",
            "api_reasoning_option_id": str(
                self._trace_context.get("api_reasoning_option_id") or ""
            ),
            "upstream_status": int(status),
            "response_seen": response_seen,
            "response_body_sha256": hashlib.sha256(response_body).hexdigest() if response_body else "",
            "prompt_hash": prompt_hash,
            "known_smoke_phrase_matched": smoke_match,
            "chatgpt_route_used": True,
            "api_only_calls_chatgpt": False,
            "fallback_used": False,
            "raw_prompt_recorded": False,
            "auth_header_recorded": False,
            "secret_value_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "response_text_counts_as_model_truth": False,
            "model_self_report_counts_as_runtime_truth": False,
        }
        if isinstance(response_payload.get("error"), dict):
            error = response_payload["error"]
            record["response_error_type"] = str(error.get("type") or "")
            record["response_error_code"] = str(error.get("code") or "")
        with self._trace_lock:
            self._trace_records.append(record)
            self._trace_records = self._trace_records[-20:]

    def _handle_models(
        self,
        path: str,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        status, response_headers, response_body = self._forward_downstream(
            method="GET",
            path=path,
            headers=headers,
            body=b"",
        )
        if status >= 400:
            return status, response_headers, response_body
        try:
            payload = json.loads(response_body.decode("utf-8"))
        except Exception:
            return status, response_headers, response_body
        data = payload.get("data")
        if not isinstance(data, list):
            return status, response_headers, response_body
        if self._hidden_downstream_model_ids:
            data[:] = [
                item
                for item in data
                if not (
                    isinstance(item, dict)
                    and str(item.get("id") or "").strip() in self._hidden_downstream_model_ids
                )
            ]
        seen_model_ids = {
            str(item.get("id") or "")
            for item in data
            if isinstance(item, dict) and str(item.get("id") or "").strip()
        }
        for route_model_id in self._route_model_ids:
            if route_model_id in seen_model_ids:
                continue
            data.append({"id": route_model_id})
        body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        return status, {"Content-Type": "application/json"}, body_bytes

    def _forward_downstream(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> tuple[int, dict[str, str], bytes]:
        forwarded_url = f"{self.downstream_endpoint}{path[3:] if path.startswith('/v1/') else path}"
        request_headers = _forward_request_headers(headers)
        request = urllib.request.Request(
            forwarded_url,
            data=body if method != "GET" else None,
            headers=request_headers,
            method=method,
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self.timeout_seconds) as response:
                response_body = response.read()
                status = int(response.status)
                response_headers = {
                    "Content-Type": response.headers.get("Content-Type", "application/json")
                }
                return status, response_headers, response_body
        except urllib.error.HTTPError as exc:
            return (
                int(exc.code),
                {"Content-Type": exc.headers.get("Content-Type", "application/json")},
                exc.read(),
            )
        except Exception:
            payload = {"error": {"message": "hybrid bridge upstream request failed", "type": "server_error"}}
            body_bytes = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            return 502, {"Content-Type": "application/json"}, body_bytes


def stat_hash(path: str) -> dict[str, Any]:
    real_path = Path(path)
    record: dict[str, Any] = {
        "path_label": path.replace(str(Path.home()), "~"),
        "exists": real_path.exists(),
    }
    if not real_path.exists():
        return record
    stat = real_path.stat()
    record.update({"is_dir": real_path.is_dir(), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    if real_path.is_file() and stat.st_size <= 5_000_000:
        digest = hashlib.sha256()
        with real_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        record["sha256"] = digest.hexdigest()
    return record


def protected_snapshot() -> dict[str, dict[str, Any]]:
    return {
        "codex_config": stat_hash("/Users/kirillponomarev/.codex/config.toml"),
        "codex_auth": stat_hash("/Users/kirillponomarev/.codex/auth.json"),
        "default_app_support_codex": stat_hash(
            "/Users/kirillponomarev/Library/Application Support/Codex"
        ),
        "default_cache_codex": stat_hash(
            "/Users/kirillponomarev/Library/Caches/com.openai.codex"
        ),
        "default_httpstorage_codex": stat_hash(
            "/Users/kirillponomarev/Library/HTTPStorages/com.openai.codex"
        ),
    }


def compare_snapshots(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "exists_unchanged": old.get("exists") == after.get(key, {}).get("exists"),
            "mtime_ns_unchanged": old.get("mtime_ns") == after.get(key, {}).get("mtime_ns"),
            "size_unchanged": old.get("size") == after.get(key, {}).get("size"),
            "sha256_unchanged": (
                old.get("sha256") == after.get(key, {}).get("sha256")
                if ("sha256" in old or "sha256" in after.get(key, {}))
                else None
            ),
        }
        for key, old in before.items()
    }


def protected_surfaces_unchanged(comparisons: dict[str, dict[str, Any]]) -> bool:
    for result in comparisons.values():
        if not result.get("exists_unchanged"):
            return False
        if not result.get("mtime_ns_unchanged"):
            return False
        if not result.get("size_unchanged"):
            return False
        if result.get("sha256_unchanged") is False:
            return False
    return True


def remove_tree_with_retry(path: Path, *, attempts: int = 8, delay_seconds: float = 0.25) -> str:
    last_error = ""
    for _ in range(attempts):
        if not path.exists():
            return ""
        try:
            shutil.rmtree(path)
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(delay_seconds)
            continue
        if not path.exists():
            return ""
    return last_error


@dataclass
class OperatorSurfaceConfig:
    repo_root: Path = Path(__file__).resolve().parents[1]
    endpoint: str = DEFAULT_ENDPOINT
    default_model: str = DEFAULT_MODEL
    codex_bin: Path = Path(DEFAULT_CODEX_BIN)
    runtime_config: Path = Path(DEFAULT_RUNTIME_CONFIG)
    max_prompt_chars: int = 8000
    timeout_seconds: int = 180


@dataclass
class OperatorSurfaceSession:
    config: OperatorSurfaceConfig = field(default_factory=OperatorSurfaceConfig)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    prompt_counter: int = 0

    def local_api_key(self) -> str:
        return extract_local_api_key(self.config.runtime_config)

    def probe_models(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status_code": None,
            "ok": False,
            "model_ids": [],
            "chosen_model_visible": False,
            "error": "",
            "server_issued": True,
            "captured_at_utc": utc_now(),
        }
        try:
            request = urllib.request.Request(
                f"{self.config.endpoint}/models",
                headers={"Authorization": f"Bearer {self.local_api_key()}"},
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
                model_ids = [
                    item.get("id")
                    for item in data.get("data", [])
                    if isinstance(item, dict) and item.get("id")
                ]
                result.update(
                    {
                        "status_code": response.status,
                        "ok": response.status == 200,
                        "model_ids": model_ids[:100],
                        "chosen_model_visible": self.config.default_model in model_ids,
                    }
                )
        except Exception as exc:  # pragma: no cover - live runtime surface
            result["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        routes_list = self.run_wbp(["external-models", "routes", "list", "--json"])
        route_model_ids = _external_route_model_ids_from_packet(routes_list.get("json"))
        if route_model_ids:
            merged_model_ids = list(dict.fromkeys([*result["model_ids"], *route_model_ids]))
            result["model_ids"] = merged_model_ids[:100]
            if self.config.default_model in route_model_ids:
                result["chosen_model_visible"] = True
        return result

    def run_wbp(self, args: list[str]) -> dict[str, Any]:
        process = subprocess.run(
            ["python3", "-m", "wild_boar_proxy", *args],
            cwd=str(self.config.repo_root),
            env=clean_env(),
            text=True,
            capture_output=True,
            timeout=120,
        )
        packet = None
        if process.stdout.strip():
            try:
                packet = json.loads(process.stdout)
            except json.JSONDecodeError:
                packet = None
        return {
            "exit_code": process.returncode,
            "json": packet,
            "stdout_redacted_len": len(process.stdout),
            "stderr_redacted_len": len(process.stderr),
            "timestamp_utc": utc_now(),
        }

    def status_payload(self) -> dict[str, Any]:
        status = self.run_wbp(["status", "--json"])
        health = self.run_wbp(["healthcheck", "--json"])
        models = self.probe_models()
        status_packet = status.get("json") or {}
        health_packet = health.get("json") or {}
        return {
            "captured_at_utc": utc_now(),
            "status": {
                "status": status_packet.get("status"),
                "machine_error_code": status_packet.get("machine_error_code"),
                "liveness": status_packet.get("liveness"),
                "endpoint": status_packet.get("endpoint"),
                "configured_model": status_packet.get("configured_model"),
                "effective_mode": status_packet.get("effective_mode"),
            },
            "health": {
                "status": health_packet.get("status"),
                "machine_error_code": health_packet.get("machine_error_code"),
                "liveness": health_packet.get("liveness"),
            },
            "claim_gate": status_packet.get("claim_gate", {"status": "not_reported"}),
            "models": models,
            "control_surface": {
                "localhost_only": True,
                "browser_secret_fields": False,
                "raw_path_fields": False,
            },
        }

    def transcript_payload(self) -> dict[str, Any]:
        return {
            "captured_at_utc": utc_now(),
            "entries": self.transcript,
            "secret_value_recorded": False,
        }

    def run_prompt(
        self,
        payload: dict[str, Any],
        *,
        trace_wbp: bool = False,
        sandbox_mode_override: str = "read-only",
        writable_additional_dir: Path | None = None,
        working_dir_override: Path | None = None,
    ) -> dict[str, Any]:
        forbidden = forbidden_browser_fields(payload)
        if forbidden:
            return {
                "status": "rejected",
                "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
                "human_message": "Browser payload contains forbidden fields.",
                "forbidden_fields": forbidden,
                "refresh_packet": self.status_payload(),
            }
        prompt = payload.get("prompt")
        model_id = payload.get("model_id")
        requested_slot_id = payload.get("slot_id")
        requested_slot_id_text = requested_slot_id if isinstance(requested_slot_id, str) else ""
        requested_slot_explicit_value = payload.get("slot_id_explicit")
        requested_slot_explicit = bool(requested_slot_id_text)
        if (
            requested_slot_explicit_value is False
            and requested_slot_id_text == "primary_model_slot"
        ):
            requested_slot_explicit = False
        if not isinstance(prompt, str) or not prompt.strip():
            return {
                "status": "rejected",
                "machine_error_code": "PROMPT_REQUIRED",
                "human_message": "Prompt is required.",
                "refresh_packet": self.status_payload(),
            }
        if len(prompt) > self.config.max_prompt_chars:
            return {
                "status": "rejected",
                "machine_error_code": "PROMPT_TOO_LONG",
                "human_message": "Prompt exceeds bounded operator action limit.",
                "refresh_packet": self.status_payload(),
            }
        if not isinstance(model_id, str):
            return {
                "status": "rejected",
                "machine_error_code": "MODEL_REQUIRED",
                "human_message": "Model must come from server-issued model list.",
                "refresh_packet": self.status_payload(),
            }
        routes_list = self.run_wbp(["external-models", "routes", "list", "--json"])
        route_record = None
        if isinstance(model_id, str):
            route_record = _external_route_from_packet(routes_list.get("json"), model_id)
        models = self.probe_models()
        try:
            selected_model = select_server_issued_model(model_id, list(models.get("model_ids", [])))
        except ValueError:
            return {
                "status": "rejected",
                "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
                "human_message": "Model id was not present in the current server-issued list.",
                "refresh_packet": self.status_payload(),
            }
        try:
            local_api_key = self.local_api_key()
        except Exception as exc:
            return {
                "status": "failed",
                "machine_error_code": "OPERATOR_LOCAL_API_KEY_UNAVAILABLE",
                "human_message": "Operator local API key is unavailable in owner-side runtime config.",
                "error_class": type(exc).__name__,
                "refresh_packet": self.status_payload(),
                "secret_value_recorded": False,
            }
        configured_provider = "cliproxy"
        configured_wire_api = "responses"
        configured_label = "CLIProxyAPI via Wild Boar Proxy"
        downstream_endpoint = self.config.endpoint
        runtime_model = selected_model
        route_provider_endpoint = ""
        route_secret = ""
        if route_record is not None:
            compatibility = str(route_record.get("compatibility") or "").strip()
            endpoint_path = str(route_record.get("endpoint_path") or "").strip()
            if compatibility != "openai_chat_completions" or endpoint_path not in {
                "/chat/completions",
                "/v1/chat/completions",
            }:
                return {
                    "status": "failed",
                    "machine_error_code": "EXTERNAL_ROUTE_WIRE_API_UNSUPPORTED",
                    "human_message": "Selected external route is not compatible with bounded Codex operator wire API.",
                    "refresh_packet": self.status_payload(),
                    "secret_value_recorded": False,
                }
            try:
                secret = _resolve_external_route_secret_value(route_record)
            except Exception as exc:
                return {
                    "status": "failed",
                    "machine_error_code": "EXTERNAL_ROUTE_SECRET_UNAVAILABLE",
                    "human_message": "Selected external route is missing its managed secret value.",
                    "error_class": type(exc).__name__,
                    "refresh_packet": self.status_payload(),
                    "secret_value_recorded": False,
                }
            runtime_model = selected_model
            route_provider_endpoint = str(route_record.get("base_url") or "").rstrip("/")
            route_secret = secret
            configured_provider = "external_route"
            configured_wire_api = "responses"
            configured_label = "Server-owned external route via bounded responses adapter"
        secret = local_api_key
        if not self.config.codex_bin.exists():
            return {
                "status": "failed",
                "machine_error_code": "OPERATOR_CODEX_BINARY_UNAVAILABLE",
                "human_message": "Codex engine binary is unavailable on this host.",
                "refresh_packet": self.status_payload(),
                "secret_value_recorded": False,
            }

        self.prompt_counter += 1
        tmp_root = Path(tempfile.mkdtemp(prefix="wbp-main-web-operator-"))
        run_root = tmp_root / "run"
        home = run_root / "home"
        codex_home = run_root / "codex-home"
        work = run_root / "work"
        home.mkdir(parents=True)
        codex_home.mkdir()
        work.mkdir()
        sandbox_mode = str(sandbox_mode_override or "read-only")
        current_codex_home = (Path.home() / ".codex").resolve()
        if sandbox_mode not in {"read-only", "workspace-write"}:
            remove_tree_with_retry(tmp_root)
            return {
                "status": "rejected",
                "machine_error_code": "SANDBOX_MODE_NOT_ADMITTED",
                "human_message": "Sandbox mode is not admitted for this operator surface.",
                "selected_model": selected_model,
                "requested_slot_id": requested_slot_id_text,
                "requested_slot_explicit": requested_slot_explicit,
                "sandbox_mode": sandbox_mode,
                "allowed_sandbox_modes": ["read-only", "workspace-write"],
                "danger_full_access_admitted": False,
                "secret_value_recorded": False,
            }
        workspace_write_requested = sandbox_mode == "workspace-write"
        temp_root_parent = Path(tempfile.gettempdir()).resolve()
        working_dir_scope = "temp_operator_work"
        if working_dir_override is not None:
            try:
                requested_work = Path(working_dir_override).resolve()
            except OSError as exc:
                remove_tree_with_retry(tmp_root)
                return {
                    "status": "rejected",
                    "machine_error_code": "WORKING_DIR_NOT_ADMITTED",
                    "human_message": "Working directory override is not admitted.",
                    "selected_model": selected_model,
                    "requested_slot_id": requested_slot_id_text,
                    "requested_slot_explicit": requested_slot_explicit,
                    "sandbox_mode": sandbox_mode,
                    "workspace_write_admitted": workspace_write_requested,
                    "working_dir_override_admitted": False,
                    "danger_full_access_admitted": False,
                    "error_class": type(exc).__name__,
                    "secret_value_recorded": False,
                }
            if (
                not workspace_write_requested
                or not requested_work.exists()
                or not requested_work.is_dir()
                or temp_root_parent not in requested_work.parents
                or Path.cwd().resolve() in requested_work.parents
                or requested_work == current_codex_home
            ):
                remove_tree_with_retry(tmp_root)
                return {
                    "status": "rejected",
                    "machine_error_code": "WORKING_DIR_NOT_ADMITTED",
                    "human_message": "Working directory override is not admitted.",
                    "selected_model": selected_model,
                    "requested_slot_id": requested_slot_id_text,
                    "requested_slot_explicit": requested_slot_explicit,
                    "sandbox_mode": sandbox_mode,
                    "workspace_write_admitted": workspace_write_requested,
                    "working_dir_override_admitted": False,
                    "danger_full_access_admitted": False,
                    "secret_value_recorded": False,
                }
            work = requested_work
            working_dir_scope = "safe_worktree_only"
        additional_writable_dir: Path | None = None
        if writable_additional_dir is not None:
            try:
                additional_writable_dir = Path(writable_additional_dir).resolve()
            except OSError as exc:
                remove_tree_with_retry(tmp_root)
                return {
                    "status": "rejected",
                    "machine_error_code": "ADDITIONAL_WRITABLE_DIR_NOT_ADMITTED",
                    "human_message": "Additional writable directory is not admitted.",
                    "selected_model": selected_model,
                    "requested_slot_id": requested_slot_id_text,
                    "requested_slot_explicit": requested_slot_explicit,
                    "sandbox_mode": sandbox_mode,
                    "workspace_write_admitted": workspace_write_requested,
                    "additional_writable_dir_admitted": False,
                    "danger_full_access_admitted": False,
                    "error_class": type(exc).__name__,
                    "secret_value_recorded": False,
                }
            if (
                not workspace_write_requested
                or not additional_writable_dir.exists()
                or not additional_writable_dir.is_dir()
                or temp_root_parent not in additional_writable_dir.parents
                or Path.cwd().resolve() in additional_writable_dir.parents
                or additional_writable_dir == current_codex_home
            ):
                remove_tree_with_retry(tmp_root)
                return {
                    "status": "rejected",
                    "machine_error_code": "ADDITIONAL_WRITABLE_DIR_NOT_ADMITTED",
                    "human_message": "Additional writable directory is not admitted.",
                    "selected_model": selected_model,
                    "requested_slot_id": requested_slot_id_text,
                    "requested_slot_explicit": requested_slot_explicit,
                    "sandbox_mode": sandbox_mode,
                    "workspace_write_admitted": workspace_write_requested,
                    "additional_writable_dir_admitted": False,
                    "danger_full_access_admitted": False,
                    "secret_value_recorded": False,
                }
        route_adapter: ExternalRouteResponsesAdapter | None = None
        trace_observer = None
        effective_endpoint = downstream_endpoint
        config_text = ""
        last_message = run_root / "last_message.txt"
        env = clean_env()
        command: list[str] = []
        started = time.time()
        env_codex_home = codex_home.resolve()
        env_home = home.resolve()
        temp_root_resolved = tmp_root.resolve()
        config_sha256 = ""
        timed_out = False
        trace_packet = _empty_trace_packet()
        process_network_observation = {
            "status": "ok",
            "machine_error_code": "INSUFFICIENT_OBSERVATION",
            "classification": "insufficient_observation",
            "direct_non_wbp_model_egress_absent_proven": False,
            "process_tree_observed": False,
            "sample_count": 0,
            "observed_process_count_max": 0,
            "allowed_local_endpoints": [],
            "peer_endpoints": [],
            "non_local_peer_endpoints_present": False,
            "raw_pid_exposed": False,
            "pid_not_exposed_to_browser": True,
            "secret_value_recorded": False,
        }
        exit_code = 127
        stderr = ""
        try:
            if route_record is not None:
                route_adapter = ExternalRouteResponsesAdapter(
                    route=route_record,
                    expected_api_key=local_api_key,
                    route_secret=route_secret,
                )
                route_adapter.__enter__()
                downstream_endpoint = route_adapter.listen_endpoint
            if trace_wbp:
                trace_observer = WbpTraceObserver(downstream_endpoint=downstream_endpoint)
                trace_observer.__enter__()
                effective_endpoint = trace_observer.listen_endpoint
            else:
                effective_endpoint = downstream_endpoint
            config_text = build_codex_config(
                endpoint=effective_endpoint,
                model_id=runtime_model,
                provider_name=configured_provider,
                provider_label=configured_label,
                wire_api=configured_wire_api,
                sandbox_mode=sandbox_mode,
            )
            (codex_home / "config.toml").write_text(config_text, encoding="utf-8")
            env.update(
                {
                    "HOME": str(home),
                    "CODEX_HOME": str(codex_home),
                    "OPENAI_API_KEY": secret,
                }
            )
            env_codex_home = Path(env["CODEX_HOME"]).resolve()
            env_home = Path(env["HOME"]).resolve()
            config_sha256 = hashlib.sha256(config_text.encode("utf-8")).hexdigest()
            command = [
                str(self.config.codex_bin),
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-rules",
                "--sandbox",
                sandbox_mode,
            ]
            if additional_writable_dir is not None:
                command.extend(["--add-dir", str(additional_writable_dir)])
            command.extend(
                [
                "-C",
                str(work),
                "--json",
                "-o",
                str(last_message),
                "-",
                ]
            )
            observation_result = _run_command_with_observation(
                command,
                cwd=str(work),
                env=env,
                prompt=prompt,
                timeout_seconds=self.config.timeout_seconds,
                allowed_local_endpoints=_allowed_local_endpoints(
                    effective_endpoint,
                    downstream_endpoint,
                ),
                warning_classes_from_stderr=lambda text: (
                    ["remote_plugin_sync_401"] if "Failed to sync remote plugins" in text else []
                ),
            )
            raw_exit_code = observation_result.get("exit_code")
            exit_code = int(raw_exit_code) if isinstance(raw_exit_code, int) else 127
            stderr = str(observation_result.get("stderr") or "")
            timed_out = observation_result.get("timed_out") is True
            process_network_observation = (
                observation_result.get("process_network_observation_packet")
                if isinstance(observation_result.get("process_network_observation_packet"), dict)
                else process_network_observation
            )
        except OSError as exc:
            exit_code = 127
            stderr = f"{type(exc).__name__}: {exc}"
        finally:
            if trace_observer:
                trace_packet = trace_observer.packet()
                trace_observer.__exit__(None, None, None)
            if route_adapter:
                route_adapter.__exit__(None, None, None)
        final_message = (
            redact_text(last_message.read_text(encoding="utf-8", errors="replace"), [secret]).strip()
            if last_message.exists()
            else ""
        )
        warning_classes = []
        if "Failed to sync remote plugins" in stderr:
            warning_classes.append("remote_plugin_sync_401")
        cleanup_error = remove_tree_with_retry(tmp_root)
        prompt_id = f"operator_prompt_{self.prompt_counter}"
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        entry = {
            "prompt_id": prompt_id,
            "prompt_hash": prompt_hash,
            "selected_model": selected_model,
            "requested_slot_id": requested_slot_id_text,
            "final_message": final_message,
            "exit_code": exit_code,
            "warning_classes": warning_classes,
            "captured_at_utc": utc_now(),
        }
        self.transcript.append(entry)
        ok = exit_code == 0 and bool(final_message)
        trace_machine_error_code = str(trace_packet.get("machine_error_code") or "")
        prompt_machine_error_code = "OK" if ok else "ENGINE_PROMPT_FAILED"
        if (
            not ok
            and trace_wbp
            and trace_packet.get("response_observed") is True
            and trace_machine_error_code.startswith("TRACE_UPSTREAM_HTTP_")
        ):
            prompt_machine_error_code = trace_machine_error_code
        return {
            "status": "ok" if ok else "failed",
            "machine_error_code": prompt_machine_error_code,
            "human_message": "Codex Operator prompt completed." if ok else "Codex Operator prompt failed.",
            "selected_model": selected_model,
            "requested_slot_id": requested_slot_id_text,
            "requested_slot_explicit": requested_slot_explicit,
            "runtime_model": runtime_model,
            "configured_base_url": effective_endpoint,
            "downstream_wbp_endpoint": downstream_endpoint,
            "route_provider_endpoint": route_provider_endpoint,
            "route_adapter_used": route_record is not None,
            "configured_wire_api": configured_wire_api,
            "configured_provider": configured_provider,
            "sandbox_mode": sandbox_mode,
            "workspace_write_requested": workspace_write_requested,
            "workspace_write_admitted": workspace_write_requested,
            "additional_writable_dir_admitted": additional_writable_dir is not None,
            "additional_writable_dir_scope": "temp_only" if additional_writable_dir is not None else "none",
            "working_dir_override_admitted": working_dir_override is not None,
            "working_dir_scope": working_dir_scope,
            "danger_full_access_admitted": False,
            "wbp_endpoint_configured": effective_endpoint.startswith("http://127.0.0.1:"),
            "config_sha256": config_sha256,
            "config_endpoint_matches": f'base_url = "{effective_endpoint}"' in config_text,
            "config_provider_matches": f'model_provider = "{configured_provider}"' in config_text,
            "config_wire_api_matches": f'wire_api = "{configured_wire_api}"' in config_text,
            "trace_observer_enabled": trace_wbp,
            "trace_observer_packet": trace_packet,
            "process_network_observation_packet": process_network_observation,
            "independent_wbp_trace_observed": (
                trace_packet.get("request_observed") is True
                and trace_packet.get("response_observed") is True
                and trace_packet.get("forwarded_to_wbp") is True
                and trace_packet.get("forwarded_endpoint") == downstream_endpoint
                and isinstance(trace_packet.get("upstream_status"), int)
                and 200 <= int(trace_packet.get("upstream_status")) < 400
                and trace_packet.get("secret_value_recorded") is False
                and trace_packet.get("prompt_body_recorded") is False
                and trace_packet.get("auth_header_recorded") is False
            ),
            "env_codex_home_is_temp": temp_root_resolved in env_codex_home.parents,
            "env_home_is_temp": temp_root_resolved in env_home.parents,
            "workdir_is_temp": temp_root_resolved in work.resolve().parents,
            "command_workdir_is_temp": temp_root_resolved in Path(str(work)).resolve().parents,
            "command_workdir_scope": working_dir_scope,
            "command_uses_stdin_dash": command[-1] == "-",
            "command_json_mode": "--json" in command,
            "command_output_file_is_temp": temp_root_resolved in last_message.resolve().parents,
            "current_codex_home_used": env_codex_home == current_codex_home,
            "prompt_hash": prompt_hash,
            "final_message": final_message,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": round(time.time() - started, 3),
            "warning_classes": warning_classes,
            "direct_non_wbp_model_egress_absent_proven": (
                process_network_observation.get("direct_non_wbp_model_egress_absent_proven") is True
            ),
            "stdin_prompt_used": True,
            "command_surface": {
                "binary": "<codex>",
                "args_shape": [
                    "exec",
                    "--skip-git-repo-check",
                    "--ephemeral",
                    "--ignore-rules",
                    "--sandbox",
                    sandbox_mode,
                    *(["--add-dir", "<temp-additional-dir>"] if additional_writable_dir is not None else []),
                    "-C",
                    "<safe-worktree>" if working_dir_override is not None else "<temp-work>",
                    "--json",
                    "-o",
                    "<temp-last-message>",
                    "-",
                ],
            },
            "temp_root_removed": not tmp_root.exists(),
            "cleanup_error": cleanup_error,
            "refresh_packet": self.status_payload(),
            "transcript": self.transcript_payload(),
            "secret_value_recorded": False,
        }


def run_process_isolation_proof(prompt: str, model_id: str = DEFAULT_MODEL) -> dict[str, Any]:
    session = OperatorSurfaceSession()
    before = protected_snapshot()
    result = session.run_prompt({"prompt": prompt, "model_id": model_id})
    after = protected_snapshot()
    comparisons = compare_snapshots(before, after)
    return {
        "captured_at_utc": utc_now(),
        "run_result": result,
        "transcript": session.transcript_payload(),
        "protected_pre_snapshot": before,
        "protected_post_snapshot": after,
        "comparisons": comparisons,
        "protected_surfaces_unchanged": protected_surfaces_unchanged(comparisons),
        "tmp_root_removed": bool(result.get("temp_root_removed")),
        "secret_value_recorded": False,
    }
