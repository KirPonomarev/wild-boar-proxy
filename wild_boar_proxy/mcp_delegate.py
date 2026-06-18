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
PROMPT_OBSERVATION_PACKET_KIND = "wbp_codex_prompt_observation"
API_LANE_ADAPTER_ADMISSION_PACKET_KIND = "wbp_api_lane_adapter_admission"
API_LANE_ADAPTER_ADMISSION_FINAL_STATUS_ADMITTED = (
    "WBP_API_LANE_ADAPTER_ADMISSION_ADMITTED"
)
API_LANE_ADAPTER_ADMISSION_FINAL_STATUS_BLOCKED = (
    "WBP_API_LANE_ADAPTER_ADMISSION_BLOCKED"
)
API_LANE_ADAPTER_NOT_AVAILABLE = "WBP_API_LANE_ADAPTER_NOT_AVAILABLE"
ROUTE_BOUND_DISPATCH_PACKET_KIND = "wbp_route_bound_controlled_dispatch"
ROUTE_BOUND_DISPATCH_FINAL_STATUS_PROVEN = "WBP_ROUTE_BOUND_DISPATCH_PROVEN"
ROUTE_BOUND_DISPATCH_FINAL_STATUS_BLOCKED = "WBP_ROUTE_BOUND_DISPATCH_BLOCKED"
ROUTE_BOUND_DISPATCH_NOT_PROVEN = "WBP_ROUTE_BOUND_DISPATCH_NOT_PROVEN"
CONTROLLED_PROVIDER_UNAVAILABLE = "WBP_CONTROLLED_PROVIDER_UNAVAILABLE"
CONTROLLED_PROVIDER_ERROR = "WBP_CONTROLLED_PROVIDER_ERROR"
LIVE_ROUTE_SMOKE_PACKET_KIND = "wbp_live_route_bound_api_smoke"
LIVE_ROUTE_SMOKE_PROOF_PACKET_KIND = "wbp_live_route_bound_api_smoke_proof"
LIVE_ROUTE_SMOKE_FINAL_STATUS_ADMITTED = "WBP_LIVE_ROUTE_BOUND_API_SMOKE_ADMITTED"
LIVE_ROUTE_SMOKE_FINAL_STATUS_BLOCKED = "WBP_LIVE_ROUTE_BOUND_API_SMOKE_BLOCKED"
LIVE_ROUTE_SMOKE_PROOF_FINAL_STATUS_ADMITTED = (
    "WBP_LIVE_ROUTE_BOUND_API_SMOKE_PROOF_ADMITTED"
)
LIVE_ROUTE_SMOKE_PROOF_FINAL_STATUS_BLOCKED = (
    "WBP_LIVE_ROUTE_BOUND_API_SMOKE_PROOF_BLOCKED"
)
LIVE_ROUTE_SMOKE_NOT_PROVEN = "WBP_LIVE_ROUTE_BOUND_API_SMOKE_NOT_PROVEN"
LIVE_ROUTE_BROWSER_AUTHORITY_REJECTED = "WBP_LIVE_ROUTE_BROWSER_AUTHORITY_REJECTED"
LIVE_PROVIDER_CREDENTIAL_MISSING = "WBP_LIVE_PROVIDER_CREDENTIAL_MISSING"
LIVE_PROVIDER_TRANSPORT_UNAVAILABLE = "WBP_LIVE_PROVIDER_TRANSPORT_UNAVAILABLE"
LIVE_PROVIDER_ERROR = "WBP_LIVE_PROVIDER_ERROR"
CONFIG_PROBE_PACKET_KIND = "wbp_codex_mcp_config_probe"
CONFIG_PROBE_FINAL_STATUS_LOADED = "WBP_CODEX_MCP_CONFIG_PROBE_LOADED"
CONFIG_PROBE_FINAL_STATUS_BLOCKED = "WBP_CODEX_MCP_CONFIG_PROBE_BLOCKED"
WIRING_PACKET_KIND = "wbp_codex_mcp_wiring_reality"
WIRING_FINAL_STATUS_PROVEN = "WBP_CODEX_MCP_WIRING_PROVEN"
WIRING_FINAL_STATUS_WORKS_WITH_LIMITS = "WBP_CODEX_MCP_WIRING_WORKS_WITH_LIMITS"
WIRING_FINAL_STATUS_BLOCKED = "WBP_CODEX_MCP_WIRING_BLOCKED"
ROUTER_HOOK_OBSERVATION_PACKET_KIND = "wbp_native_router_hook_observation"
ROUTER_HOOK_OBSERVATION_FINAL_STATUS_OBSERVED = (
    "WBP_NATIVE_ROUTER_HOOK_OBSERVED"
)
ROUTER_HOOK_OBSERVATION_FINAL_STATUS_BLOCKED = (
    "WBP_NATIVE_ROUTER_HOOK_BLOCKED"
)
ROUTER_HOOK_NOT_OBSERVED = "WBP_NATIVE_ROUTER_HOOK_NOT_OBSERVED"
ROUTER_HOOK_BROWSER_AUTHORITY_REJECTED = (
    "WBP_NATIVE_ROUTER_HOOK_BROWSER_AUTHORITY_REJECTED"
)
ROUTER_HOOK_CODEX_SUBAGENT_USED = "WBP_NATIVE_ROUTER_HOOK_CODEX_SUBAGENT_USED"
ROUTER_HOOK_SOURCE_ADMISSION_PACKET_KIND = "wbp_router_hook_source_admission"
ROUTER_HOOK_SOURCE_ADMISSION_FINAL_STATUS_ADMITTED = (
    "WBP_ROUTER_HOOK_SOURCE_ADMITTED"
)
ROUTER_HOOK_SOURCE_ADMISSION_FINAL_STATUS_BLOCKED = (
    "WBP_ROUTER_HOOK_SOURCE_BLOCKED"
)
ROUTER_HOOK_SOURCE_NOT_ADMITTED = "WBP_ROUTER_HOOK_SOURCE_NOT_ADMITTED"
ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED = (
    "WBP_ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED"
)
ROUTER_HOOK_SOURCE_SIDE_EFFECT_REJECTED = (
    "WBP_ROUTER_HOOK_SOURCE_SIDE_EFFECT_REJECTED"
)
ROUTER_HOOK_SOURCE_DIGEST_NOT_BOUND = "WBP_ROUTER_HOOK_SOURCE_DIGEST_NOT_BOUND"
ROUTER_HOOK_SOURCE_EVENT_PACKET_KIND = "wbp_router_hook_source_event"
ROUTER_HOOK_SOURCE_EVENT_FINAL_STATUS_PRODUCED = (
    "WBP_ROUTER_HOOK_SOURCE_EVENT_PRODUCED"
)
ROUTER_HOOK_SOURCE_EVENT_FINAL_STATUS_BLOCKED = (
    "WBP_ROUTER_HOOK_SOURCE_EVENT_BLOCKED"
)
ROUTER_HOOK_SOURCE_EVENT_NOT_PRODUCED = (
    "WBP_ROUTER_HOOK_SOURCE_EVENT_NOT_PRODUCED"
)
ROUTER_HOOK_SOURCE_EVENT_CAPABILITY_NOT_PROVEN = (
    "WBP_ROUTER_HOOK_SOURCE_EVENT_CAPABILITY_NOT_PROVEN"
)
ROUTER_HOOK_CONTROL_BOUNDARY_PACKET_KIND = "wbp_router_hook_control_boundary"
ROUTER_HOOK_CONTROL_BOUNDARY_FINAL_STATUS_PROVEN = (
    "WBP_ROUTER_HOOK_CONTROL_BOUNDARY_PROVEN"
)
ROUTER_HOOK_CONTROL_BOUNDARY_FINAL_STATUS_BLOCKED = (
    "WBP_ROUTER_HOOK_CONTROL_BOUNDARY_BLOCKED"
)
ROUTER_HOOK_CONTROL_BOUNDARY_NOT_PROVEN = (
    "WBP_ROUTER_HOOK_CONTROL_BOUNDARY_NOT_PROVEN"
)
ROUTER_HOOK_CONTROL_BOUNDARY_AUTHORITY_REJECTED = (
    "WBP_ROUTER_HOOK_CONTROL_BOUNDARY_AUTHORITY_REJECTED"
)
ROUTER_HOOK_CONTROL_BOUNDARY_SIDE_EFFECT_REJECTED = (
    "WBP_ROUTER_HOOK_CONTROL_BOUNDARY_SIDE_EFFECT_REJECTED"
)
ROUTER_HOOK_CONTROL_BOUNDARY_DIGEST_NOT_BOUND = (
    "WBP_ROUTER_HOOK_CONTROL_BOUNDARY_DIGEST_NOT_BOUND"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_PROBE_PACKET_KIND = (
    "wbp_exec_wrapper_submit_boundary_probe"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_FINAL_STATUS_PROVEN = (
    "WBP_EXEC_WRAPPER_SUBMIT_BOUNDARY_PROVEN"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_FINAL_STATUS_BLOCKED = (
    "WBP_EXEC_WRAPPER_SUBMIT_BOUNDARY_BLOCKED"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_NOT_PROVEN = (
    "WBP_EXEC_WRAPPER_SUBMIT_BOUNDARY_NOT_PROVEN"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_AUTHORITY_REJECTED = (
    "WBP_EXEC_WRAPPER_SUBMIT_BOUNDARY_AUTHORITY_REJECTED"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_SIDE_EFFECT_REJECTED = (
    "WBP_EXEC_WRAPPER_SUBMIT_BOUNDARY_SIDE_EFFECT_REJECTED"
)
EXEC_WRAPPER_SUBMIT_BOUNDARY_DIGEST_NOT_BOUND = (
    "WBP_EXEC_WRAPPER_SUBMIT_BOUNDARY_DIGEST_NOT_BOUND"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_PACKET_KIND = (
    "wbp_controlled_exec_router_hook_chain"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_FINAL_STATUS_PROVEN = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_PROVEN"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_FINAL_STATUS_BLOCKED = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_BLOCKED"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_NOT_PROVEN = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_NOT_PROVEN"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_SEQUENCE_INVALID = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_SEQUENCE_INVALID"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_AUTHORITY_REJECTED = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_AUTHORITY_REJECTED"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_SIDE_EFFECT_REJECTED = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_SIDE_EFFECT_REJECTED"
)
CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_DIGEST_NOT_BOUND = (
    "WBP_CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_DIGEST_NOT_BOUND"
)
CONTROLLED_EXEC_SUBMIT_BOUNDARY_SEQUENCE = "pre_process_start"
CONTROLLED_EXEC_CODEX_OBSERVATION_SEQUENCE = "post_process_start"
ROUTER_HOOK_CONTROL_BOUNDARY_ALLOWED_EVIDENCE_KINDS = frozenset(
    {
        EXEC_WRAPPER_SUBMIT_BOUNDARY_PROBE_PACKET_KIND,
        "wbp_owned_router_hook_boundary_probe",
    }
)
ROUTER_HOOK_SOURCE_ALLOWED_KINDS = frozenset(
    {
        "wbp_codex_exec_jsonl_observer",
        "wbp_exec_wrapper",
        "wbp_owned_router_hook_probe",
    }
)
CODEX_EXEC_TOOL_CALL_PACKET_KIND = "wbp_codex_exec_tool_call_observation"
CODEX_EXEC_TOOL_CALL_FINAL_STATUS_OBSERVED = (
    "WBP_CODEX_EXEC_TOOL_CALL_OBSERVED"
)
CODEX_EXEC_TOOL_CALL_FINAL_STATUS_BLOCKED = "WBP_CODEX_EXEC_TOOL_CALL_BLOCKED"
CODEX_EXEC_BROWSER_AUTHORITY_REJECTED = "WBP_CODEX_EXEC_BROWSER_AUTHORITY_REJECTED"
CODEX_EXEC_SUBAGENT_USED_AS_DIP = "WBP_CODEX_EXEC_SUBAGENT_USED_AS_DIP"
CODEX_EXEC_MODEL_GUARD_PACKET_KIND = "wbp_codex_exec_model_admission_guard"
CODEX_EXEC_MODEL_GUARD_FINAL_STATUS_ADMITTED = (
    "WBP_CODEX_EXEC_MODEL_ADMISSION_GUARD_ADMITTED"
)
CODEX_EXEC_MODEL_GUARD_FINAL_STATUS_BLOCKED = (
    "WBP_CODEX_EXEC_MODEL_ADMISSION_GUARD_BLOCKED"
)
CODEX_EXEC_MODEL_NOT_ADMITTED = "CODEX_MODEL_NOT_ADMITTED"
CHATGPT_ACCOUNT_ADMITTED_CODEX_EXEC_MODEL = "gpt-5.4"
CHATGPT_ACCOUNT_UNSAFE_DEFAULT_CODEX_EXEC_MODELS = {"gpt-5.3-codex"}
CHATGPT_ACCOUNT_AUTH_MODE_HINTS = {
    "chatgpt_login_status",
    "chatgpt_account_inferred_from_safe_error",
}


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


ENTRY_HOOK_EVIDENCE_PACKET_KIND = "wbp_entry_hook_tool_call_evidence"
ENTRY_HOOK_EVIDENCE_ENV_PATH = "WBP_ENTRY_HOOK_EVIDENCE_PATH"


def _entry_hook_evidence_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    safe_packet = dict(packet)
    return {
        "schema_version": 1,
        "packet_kind": ENTRY_HOOK_EVIDENCE_PACKET_KIND,
        "status": "ok" if safe_packet.get("status") == "ok" else "blocked",
        "machine_error_code": str(safe_packet.get("machine_error_code") or ""),
        "delegate_packet_kind": str(safe_packet.get("packet_kind") or ""),
        "delegate_packet_status": str(safe_packet.get("status") or ""),
        "delegate_packet_sha256": _sha256_text(
            json.dumps(
                safe_packet,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        ),
        "delegate_to_dip_tool_called": (
            safe_packet.get("delegate_to_dip_tool_called") is True
        ),
        "alias_context_read": safe_packet.get("alias_context_read") is True,
        "runtime_context_file_proven": (
            safe_packet.get("runtime_context_file_proven") is True
        ),
        "custom_codex_agent_runtime_context_proven": (
            safe_packet.get("custom_codex_agent_runtime_context_proven") is True
        ),
        "selected_alias": str(safe_packet.get("selected_alias") or ""),
        "selected_alias_lane": str(safe_packet.get("selected_alias_lane") or ""),
        "coding_alias_bound_to_api_lane": (
            safe_packet.get("coding_alias_bound_to_api_lane") is True
        ),
        "allowed_api_route_ids_enforced": (
            safe_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "forbidden_stale_route_ids_enforced": (
            safe_packet.get("forbidden_stale_route_ids_enforced") is True
        ),
        "route_allowed": safe_packet.get("route_allowed") is True,
        "selected_api_route_id_present": (
            safe_packet.get("selected_api_route_id_present") is True
        ),
        "selected_api_route_id_sha256": str(
            safe_packet.get("selected_api_route_id_sha256") or ""
        ),
        "selected_api_route_id_recorded": (
            safe_packet.get("selected_api_route_id_recorded") is True
        ),
        "api_lane_called": safe_packet.get("api_lane_called") is True,
        "api_lane_adapter_called": (
            safe_packet.get("api_lane_adapter_called") is True
        ),
        "api_lane_dispatch_admitted": (
            safe_packet.get("api_lane_dispatch_admitted") is True
        ),
        "route_bound_dispatch_attempted": (
            safe_packet.get("route_bound_dispatch_attempted") is True
        ),
        "route_bound_dispatch_proven": (
            safe_packet.get("route_bound_dispatch_proven") is True
        ),
        "route_bound_request_sent": (
            safe_packet.get("route_bound_request_sent") is True
        ),
        "route_bound_request_sha256": str(
            safe_packet.get("route_bound_request_sha256") or ""
        ),
        "dispatch_truth_source": str(
            safe_packet.get("dispatch_truth_source") or ""
        ),
        "controlled_provider_called": (
            safe_packet.get("controlled_provider_called") is True
        ),
        "controlled_provider_response_proven": (
            safe_packet.get("controlled_provider_response_proven") is True
        ),
        "provider_response_proven": (
            safe_packet.get("provider_response_proven") is True
        ),
        "live_provider_response_proven": (
            safe_packet.get("live_provider_response_proven") is True
        ),
        "fallback_used": safe_packet.get("fallback_used") is True,
        "local_imitation_used": safe_packet.get("local_imitation_used") is True,
        "bounded_api_lane_mock_used": (
            safe_packet.get("bounded_api_lane_mock_used") is True
        ),
        "product_ready": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_provider_response_recorded": (
            safe_packet.get("raw_provider_response_recorded") is True
        ),
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": True,
    }


def _write_entry_hook_evidence_if_requested(
    packet: Mapping[str, Any],
    env: Mapping[str, str] | None,
) -> None:
    source = env if isinstance(env, Mapping) else {}
    raw_path = _safe_text(source.get(ENTRY_HOOK_EVIDENCE_ENV_PATH) or "", limit=2048)
    if not raw_path:
        return
    evidence_path = Path(raw_path)
    if not evidence_path.is_absolute() or not evidence_path.parent.exists():
        return
    evidence = _entry_hook_evidence_packet(packet)
    tmp_path = evidence_path.with_suffix(evidence_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(evidence_path)


def build_api_lane_adapter_admission_packet(
    *,
    task: str,
    selected_alias: str,
    selected_alias_lane: str,
    route_id: str,
    allowed_api_route_ids_enforced: bool,
    route_allowed: bool,
    adapter_available: bool = True,
) -> dict[str, Any]:
    safe_task = _safe_text(task, limit=4096)
    safe_alias = _safe_text(selected_alias, limit=80)
    safe_lane = _safe_text(selected_alias_lane, limit=32)
    safe_route_id = _safe_text(route_id, limit=128)
    selected_api_route_id_present = bool(safe_route_id)
    blocking_reasons: list[str] = []
    if not adapter_available:
        blocking_reasons.append("api_lane_adapter_unavailable")
    if not safe_task:
        blocking_reasons.append("task_required")
    if not safe_alias:
        blocking_reasons.append("coding_alias_not_selected")
    if safe_lane != API_ROUTE_LANE:
        blocking_reasons.append("selected_alias_not_api_lane")
    if not selected_api_route_id_present:
        blocking_reasons.append("selected_api_route_id_missing")
    if not allowed_api_route_ids_enforced:
        blocking_reasons.append("allowed_api_route_ids_not_enforced")
    if not route_allowed:
        blocking_reasons.append("selected_api_route_not_allowed")

    ok = not blocking_reasons
    machine_error_code = (
        "OK"
        if ok
        else API_LANE_ADAPTER_NOT_AVAILABLE
        if not adapter_available
        else "WBP_API_LANE_DISPATCH_NOT_ADMITTED"
    )
    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP API-lane adapter admission accepted the server-owned route boundary."
            if ok
            else "WBP API-lane adapter admission rejected the route boundary."
        ),
        blocking_reasons=blocking_reasons,
        extra={
            "delegate_to_dip_tool_called": True,
            "api_lane_adapter_called": True,
            "api_lane_dispatch_admitted": ok,
            "adapter_available": adapter_available,
            "adapter_truth_source": "server_owned_api_lane_adapter_admission",
            "selected_alias": safe_alias,
            "selected_alias_lane": safe_lane,
            "selected_api_route_id_present": selected_api_route_id_present,
            "selected_api_route_id_sha256": (
                _sha256_text(safe_route_id) if selected_api_route_id_present else ""
            ),
            "selected_api_route_id_recorded": False,
            "allowed_api_route_ids_enforced": allowed_api_route_ids_enforced,
            "route_allowed": route_allowed,
            "task_digest_preserved": bool(safe_task),
            "task_sha256": _sha256_text(safe_task) if safe_task else "",
            "api_lane_called": ok,
            "api_lane_provider_called": False,
            "provider_response_proven": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "bounded_api_lane_mock_used": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
        packet_kind=API_LANE_ADAPTER_ADMISSION_PACKET_KIND,
        final_status=(
            API_LANE_ADAPTER_ADMISSION_FINAL_STATUS_ADMITTED
            if ok
            else API_LANE_ADAPTER_ADMISSION_FINAL_STATUS_BLOCKED
        ),
        result_status="admitted" if ok else "blocked",
    )


def build_route_bound_controlled_dispatch_packet(
    *,
    task: str,
    selected_alias: str,
    selected_alias_lane: str,
    route_id: str,
    admission_packet: Mapping[str, Any] | None,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
) -> dict[str, Any]:
    safe_task = _safe_text(task, limit=4096)
    safe_alias = _safe_text(selected_alias, limit=80)
    safe_lane = _safe_text(selected_alias_lane, limit=32)
    safe_route_id = _safe_text(route_id, limit=128)
    safe_provider_error_code = _safe_text(controlled_provider_error_code, limit=96)
    route_id_sha256 = _sha256_text(safe_route_id) if safe_route_id else ""
    request_fingerprint = json.dumps(
        {
            "alias": safe_alias,
            "alias_lane": safe_lane,
            "route_id_sha256": route_id_sha256,
            "task_sha256": _sha256_text(safe_task) if safe_task else "",
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    response_fingerprint = json.dumps(
        {
            "controlled_provider": "wbp_controlled_route_bound_provider",
            "request_sha256": _sha256_text(request_fingerprint),
            "route_id_sha256": route_id_sha256,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    admission = admission_packet if isinstance(admission_packet, Mapping) else {}
    admission_ok = bool(
        admission.get("status") == "ok"
        and admission.get("api_lane_adapter_called") is True
        and admission.get("api_lane_dispatch_admitted") is True
        and admission.get("selected_api_route_id_sha256") == route_id_sha256
        and admission.get("selected_api_route_id_recorded") is False
        and admission.get("fallback_used") is False
        and admission.get("local_imitation_used") is False
    )
    route_bound_dispatch_attempted = admission_ok
    controlled_provider_called = bool(
        route_bound_dispatch_attempted and controlled_provider_available
    )
    controlled_provider_error_observed = bool(
        controlled_provider_called and safe_provider_error_code
    )
    route_bound_request_sent = bool(
        controlled_provider_called and not controlled_provider_error_observed
    )

    blocking_reasons: list[str] = []
    if not admission_ok:
        blocking_reasons.append("api_lane_admission_packet_invalid")
    if not safe_task:
        blocking_reasons.append("task_required")
    if safe_lane != API_ROUTE_LANE:
        blocking_reasons.append("selected_alias_not_api_lane")
    if not route_id_sha256:
        blocking_reasons.append("selected_api_route_id_missing")
    if route_bound_dispatch_attempted and not controlled_provider_available:
        blocking_reasons.append("controlled_provider_unavailable")
    if controlled_provider_error_observed:
        blocking_reasons.append("controlled_provider_error")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif route_bound_dispatch_attempted and not controlled_provider_available:
        machine_error_code = CONTROLLED_PROVIDER_UNAVAILABLE
    elif controlled_provider_error_observed:
        machine_error_code = CONTROLLED_PROVIDER_ERROR
    else:
        machine_error_code = ROUTE_BOUND_DISPATCH_NOT_PROVEN

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP route-bound controlled dispatch is proven without live provider access."
            if ok
            else "WBP route-bound controlled dispatch is not proven."
        ),
        blocking_reasons=blocking_reasons,
        extra={
            "delegate_to_dip_tool_called": True,
            "api_lane_adapter_called": admission.get("api_lane_adapter_called") is True,
            "api_lane_dispatch_admitted": (
                admission.get("api_lane_dispatch_admitted") is True
            ),
            "route_bound_dispatch_attempted": route_bound_dispatch_attempted,
            "route_bound_dispatch_proven": ok,
            "route_bound_request_sent": route_bound_request_sent,
            "route_bound_request_sha256": _sha256_text(request_fingerprint)
            if route_bound_dispatch_attempted
            else "",
            "dispatch_truth_source": (
                "server_owned_controlled_provider_no_live_network" if ok else "not_proven"
            ),
            "selected_alias": safe_alias,
            "selected_alias_lane": safe_lane,
            "selected_api_route_id_present": bool(route_id_sha256),
            "selected_api_route_id_sha256": route_id_sha256,
            "selected_api_route_id_recorded": False,
            "controlled_provider_called": controlled_provider_called,
            "controlled_provider_available": controlled_provider_available,
            "controlled_provider_error_observed": controlled_provider_error_observed,
            "controlled_provider_error_code_recorded": bool(
                controlled_provider_error_observed
            ),
            "controlled_provider_response_digest_present": ok,
            "controlled_provider_response_sha256": (
                _sha256_text(response_fingerprint) if ok else ""
            ),
            "controlled_provider_response_proven": ok,
            "api_lane_provider_called": controlled_provider_called,
            "provider_response_proven": ok,
            "live_provider_response_proven": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "raw_provider_response_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
        packet_kind=ROUTE_BOUND_DISPATCH_PACKET_KIND,
        final_status=(
            ROUTE_BOUND_DISPATCH_FINAL_STATUS_PROVEN
            if ok
            else ROUTE_BOUND_DISPATCH_FINAL_STATUS_BLOCKED
        ),
        result_status="proven" if ok else "blocked",
    )


def build_codex_exec_model_admission_guard_packet(
    requested_model: str = "",
    *,
    explicit_model_requested: bool = False,
    auth_mode_hint: str = "unknown",
) -> dict[str, Any]:
    requested = _safe_text(requested_model, limit=128)
    hint = _safe_text(auth_mode_hint, limit=80) or "unknown"
    if hint not in CHATGPT_ACCOUNT_AUTH_MODE_HINTS:
        hint = "unknown"

    if requested == CHATGPT_ACCOUNT_ADMITTED_CODEX_EXEC_MODEL:
        ok = True
        effective_model = requested
        model_override_used = False
        model_override_reason = ""
        machine_error_code = "OK"
        blocking_reasons: list[str] = []
    elif requested in CHATGPT_ACCOUNT_UNSAFE_DEFAULT_CODEX_EXEC_MODELS:
        if explicit_model_requested:
            ok = False
            effective_model = ""
            model_override_used = False
            model_override_reason = "explicit_model_not_admitted_for_chatgpt_account_exec"
            machine_error_code = CODEX_EXEC_MODEL_NOT_ADMITTED
            blocking_reasons = ["codex_model_not_admitted"]
        else:
            ok = True
            effective_model = CHATGPT_ACCOUNT_ADMITTED_CODEX_EXEC_MODEL
            model_override_used = True
            model_override_reason = "chatgpt_account_default_model_not_admitted"
            machine_error_code = "OK"
            blocking_reasons = []
    elif not requested:
        ok = True
        effective_model = CHATGPT_ACCOUNT_ADMITTED_CODEX_EXEC_MODEL
        model_override_used = True
        model_override_reason = "chatgpt_account_default_model_not_admitted"
        machine_error_code = "OK"
        blocking_reasons = []
    else:
        ok = True
        effective_model = requested
        model_override_used = False
        model_override_reason = ""
        machine_error_code = "OK"
        blocking_reasons = []

    model_admitted = bool(ok and effective_model)
    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "Codex exec model is admitted for the bounded ChatGPT-account proof."
            if ok
            else "Codex exec model is not admitted for the bounded ChatGPT-account proof."
        ),
        blocking_reasons=blocking_reasons,
        extra={
            "requested_model": requested,
            "effective_model": effective_model,
            "model_override_used": model_override_used,
            "model_override_reason": model_override_reason,
            "model_admission_checked": True,
            "model_admitted": model_admitted,
            "auth_mode_hint": hint,
            "raw_error_recorded": False,
            "raw_jsonl_recorded": False,
            "raw_stderr_recorded": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
            "product_ready": False,
        },
        packet_kind=CODEX_EXEC_MODEL_GUARD_PACKET_KIND,
        final_status=(
            CODEX_EXEC_MODEL_GUARD_FINAL_STATUS_ADMITTED
            if ok
            else CODEX_EXEC_MODEL_GUARD_FINAL_STATUS_BLOCKED
        ),
        result_status="admitted" if ok else "blocked",
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
    intent_claim: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    expected_arguments = (
        dict(expected_delegate_arguments)
        if isinstance(expected_delegate_arguments, Mapping)
        else {}
    )
    intent = dict(intent_claim) if isinstance(intent_claim, Mapping) else {}
    intent_claim_sha256 = _hex_sha256(intent.get("intent_claim_sha256") or "")
    delegated_task_sha256 = _hex_sha256(intent.get("delegated_task_sha256") or "")
    delegated_task_candidate_sha256s = [
        digest
        for digest in (
            _hex_sha256(candidate)
            for candidate in (
                intent.get("delegated_task_candidate_sha256s")
                if isinstance(intent.get("delegated_task_candidate_sha256s"), list)
                else []
            )
        )
        if digest
    ]
    if delegated_task_sha256 and delegated_task_sha256 not in delegated_task_candidate_sha256s:
        delegated_task_candidate_sha256s.insert(0, delegated_task_sha256)
    return {
        "packet_kind": PROMPT_OBSERVATION_PACKET_KIND,
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
        "intent_claim_sha256": intent_claim_sha256,
        "intent_claim_digest_present": bool(intent_claim_sha256),
        "intent_claim_status": _safe_text(intent.get("status") or "", limit=80),
        "intent_claim_machine_error_code": _safe_text(
            intent.get("machine_error_code") or "",
            limit=128,
        ),
        "intent_claim_alias": _safe_text(intent.get("alias") or "", limit=80),
        "alias_from_runtime_context": intent.get("alias_from_runtime_context") is True,
        "natural_command_shape": _safe_text(
            intent.get("natural_command_shape") or "",
            limit=128,
        ),
        "binding_status": _safe_text(intent.get("binding_status") or "", limit=128),
        "canonicalization_rule_id": _safe_text(
            intent.get("canonicalization_rule_id") or "",
            limit=128,
        ),
        "canonicalization_supported": (
            intent.get("canonicalization_supported") is True
        ),
        "canonicalization_input_sha256": _hex_sha256(
            intent.get("canonicalization_input_sha256") or ""
        ),
        "canonicalization_output_sha256": _hex_sha256(
            intent.get("canonicalization_output_sha256") or ""
        ),
        "delegated_task_sha256": delegated_task_sha256,
        "delegated_task_digest_present": bool(delegated_task_sha256),
        "delegated_task_candidate_sha256s": delegated_task_candidate_sha256s[:8],
        "delegated_task_candidate_digest_count": len(
            delegated_task_candidate_sha256s[:8]
        ),
        "delegated_task_source": _safe_text(
            intent.get("delegated_task_source") or "",
            limit=128,
        ),
        "ambiguous_intent": intent.get("ambiguous_intent") is True,
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "raw_task_recorded": False,
        "expected_delegate_arguments_recorded": False,
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
        "custom_codex_ui_visibility_proven": False,
    }


_EXEC_WRAPPER_SUBMIT_BOUNDARY_DIGEST_FIELDS = (
    "packet_kind",
    "submit_boundary_status",
    "entrypoint_kind",
    "control_boundary_wbp_owned",
    "control_boundary_observed_prompt",
    "control_boundary_pre_codex_decision",
    "control_boundary_post_factum_only",
    "control_boundary_can_enforce_router",
    "control_boundary_can_route_delegate_to_dip",
    "router_delegate_prompt_contract_bound",
    "effect",
    "changed_files",
    "source_run_sha256",
    "source_prompt_sha256",
    "stdin_prompt_used",
    "command_uses_stdin_dash",
    "command_json_mode",
    "env_codex_home_is_temp",
    "env_home_is_temp",
    "workdir_is_temp",
    "command_workdir_is_temp",
    "command_output_file_is_temp",
    "current_codex_home_used",
    "submit_boundary_sequence",
    "owned_temp_config_written",
    "owned_temp_output_file_reserved",
    "effective_config_written",
    "state_written",
    "profile_written",
    "config_written",
    "route_registry_written",
    "credential_written",
    "runtime_state_written",
    "raw_prompt_recorded",
    "raw_route_id_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "product_ready",
    "native_free_chat_router_proven",
)


def _exec_wrapper_submit_boundary_claim_sha256(
    packet: Mapping[str, Any],
) -> str:
    payload = {
        field: packet.get(field)
        for field in _EXEC_WRAPPER_SUBMIT_BOUNDARY_DIGEST_FIELDS
    }
    return _sha256_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def build_exec_wrapper_submit_boundary_probe_packet(
    *,
    prompt_packet: Mapping[str, Any] | None = None,
    submit_entrypoint_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    entrypoint = (
        dict(submit_entrypoint_packet)
        if isinstance(submit_entrypoint_packet, Mapping)
        else {}
    )
    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    expected_delegate_contract_present = bool(
        prompt.get("expected_delegate_tool_call_digest_present") is True
        and prompt.get("expected_delegate_tool_name") == DELEGATE_TO_DIP_TOOL
        and _hex_sha256(prompt.get("expected_delegate_tool_call_sha256") or "")
    )
    entrypoint_kind = _safe_text(
        entrypoint.get("entrypoint_kind") or "",
        limit=96,
    )
    entrypoint_kind_admitted = entrypoint_kind in {
        "controlled_codex_exec_stdin_submit",
        "codex_cli_runner_stdin_submit",
    }
    control_boundary_wbp_owned = (
        entrypoint.get("wbp_owned_entrypoint") is True
        and entrypoint_kind_admitted
    )
    control_boundary_observed_prompt = bool(
        prompt_digest_present
        and entrypoint.get("prompt_digest_observed") is True
        and _hex_sha256(entrypoint.get("prompt_sha256") or "") == prompt_sha256
    )
    submit_boundary_sequence = _safe_text(
        entrypoint.get("submit_boundary_sequence") or "",
        limit=64,
    )
    submit_boundary_sequence_ok = (
        submit_boundary_sequence == CONTROLLED_EXEC_SUBMIT_BOUNDARY_SEQUENCE
    )
    control_boundary_pre_codex_decision = bool(
        entrypoint.get("pre_codex_decision") is True
        and submit_boundary_sequence_ok
    )
    control_boundary_post_factum_only = bool(
        entrypoint.get("post_factum_only") is True
        or entrypoint_kind in {"wbp_codex_exec_jsonl_observer", "jsonl_observer"}
    )
    stdin_prompt_used = entrypoint.get("stdin_prompt_used") is True
    command_uses_stdin_dash = entrypoint.get("command_uses_stdin_dash") is True
    command_json_mode = entrypoint.get("command_json_mode") is True
    env_codex_home_is_temp = entrypoint.get("env_codex_home_is_temp") is True
    env_home_is_temp = entrypoint.get("env_home_is_temp") is True
    workdir_is_temp = entrypoint.get("workdir_is_temp") is True
    command_workdir_is_temp = entrypoint.get("command_workdir_is_temp") is True
    command_output_file_is_temp = (
        entrypoint.get("command_output_file_is_temp") is True
    )
    current_codex_home_used = entrypoint.get("current_codex_home_used") is True
    owned_temp_config_written = entrypoint.get("owned_temp_config_written") is True
    owned_temp_output_file_reserved = (
        entrypoint.get("owned_temp_output_file_reserved") is True
    )
    effective_config_written = entrypoint.get("effective_config_written") is True
    router_delegate_prompt_contract_bound = bool(
        expected_delegate_contract_present
        and entrypoint.get("router_delegate_prompt_contract_bound") is True
    )
    prompt_supplied_hook_flags = bool(
        entrypoint.get("prompt_supplied_hook_flags") is True
        or entrypoint.get("browser_can_supply_prompt_authority") is True
    )
    browser_supplied_hook_flags = bool(
        entrypoint.get("browser_supplied_hook_flags") is True
        or entrypoint.get("browser_can_supply_route_authority") is True
        or entrypoint.get("browser_can_supply_model_authority") is True
    )
    state_written = entrypoint.get("state_written") is True
    profile_written = entrypoint.get("profile_written") is True
    config_written = (
        entrypoint.get("config_written") is True or effective_config_written
    )
    route_registry_written = entrypoint.get("route_registry_written") is True
    credential_written = entrypoint.get("credential_written") is True
    runtime_state_written = entrypoint.get("runtime_state_written") is True
    write_side_effect_observed = bool(
        state_written
        or profile_written
        or config_written
        or route_registry_written
        or credential_written
        or runtime_state_written
        or entrypoint.get("changed_files") not in (None, [])
        or entrypoint.get("effect") not in (None, "", EFFECT_PROBE, "read")
    )
    raw_prompt_recorded = bool(
        entrypoint.get("raw_prompt_recorded") is True
        or entrypoint.get("prompt_text_recorded") is True
    )
    raw_route_id_recorded = entrypoint.get("raw_route_id_recorded") is True
    raw_backend_details_exposed = (
        entrypoint.get("raw_backend_details_exposed") is True
    )
    secret_value_exposed = entrypoint.get("secret_value_exposed") is True
    product_ready_claimed = entrypoint.get("product_ready") is True
    native_free_chat_router_claimed = (
        entrypoint.get("native_free_chat_router_proven") is True
    )
    control_boundary_can_enforce_router = bool(
        control_boundary_wbp_owned
        and control_boundary_observed_prompt
        and control_boundary_pre_codex_decision
        and not control_boundary_post_factum_only
        and stdin_prompt_used
        and command_uses_stdin_dash
        and command_json_mode
        and env_codex_home_is_temp
        and env_home_is_temp
        and workdir_is_temp
        and command_workdir_is_temp
        and command_output_file_is_temp
        and not current_codex_home_used
        and not write_side_effect_observed
    )
    control_boundary_can_route_delegate_to_dip = bool(
        control_boundary_can_enforce_router
        and router_delegate_prompt_contract_bound
    )
    run_fingerprint = json.dumps(
        {
            "entrypoint_kind": entrypoint_kind,
            "prompt_sha256": prompt_sha256,
            "router_delegate_prompt_contract_bound": (
                router_delegate_prompt_contract_bound
            ),
            "stdin_prompt_used": stdin_prompt_used,
            "command_uses_stdin_dash": command_uses_stdin_dash,
            "command_json_mode": command_json_mode,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    source_run_sha256 = _sha256_text(run_fingerprint) if prompt_sha256 else ""

    blocking_reasons: list[str] = []
    if not entrypoint:
        blocking_reasons.append("submit_entrypoint_evidence_missing")
    if not prompt_digest_present:
        blocking_reasons.append("prompt_digest_missing")
    if not entrypoint_kind_admitted:
        blocking_reasons.append("submit_entrypoint_kind_not_admitted")
    if not control_boundary_wbp_owned:
        blocking_reasons.append("control_boundary_not_wbp_owned")
    if not control_boundary_observed_prompt:
        blocking_reasons.append("control_boundary_prompt_not_observed")
    if not control_boundary_pre_codex_decision:
        blocking_reasons.append("control_boundary_pre_codex_decision_not_proven")
    if not submit_boundary_sequence_ok:
        blocking_reasons.append("submit_boundary_sequence_invalid")
    if control_boundary_post_factum_only:
        blocking_reasons.append("control_boundary_post_factum_only")
    if not stdin_prompt_used:
        blocking_reasons.append("stdin_prompt_not_used")
    if not command_uses_stdin_dash:
        blocking_reasons.append("command_stdin_dash_not_used")
    if not command_json_mode:
        blocking_reasons.append("command_json_mode_not_used")
    if not env_codex_home_is_temp:
        blocking_reasons.append("env_codex_home_not_temp")
    if not env_home_is_temp:
        blocking_reasons.append("env_home_not_temp")
    if not workdir_is_temp:
        blocking_reasons.append("workdir_not_temp")
    if not command_workdir_is_temp:
        blocking_reasons.append("command_workdir_not_temp")
    if not command_output_file_is_temp:
        blocking_reasons.append("command_output_file_not_temp")
    if current_codex_home_used:
        blocking_reasons.append("current_codex_home_used")
    if not control_boundary_can_enforce_router:
        blocking_reasons.append("control_boundary_cannot_enforce_router")
    if not expected_delegate_contract_present:
        blocking_reasons.append("expected_delegate_contract_missing")
    if not router_delegate_prompt_contract_bound:
        blocking_reasons.append("router_delegate_prompt_contract_not_bound")
    if not control_boundary_can_route_delegate_to_dip:
        blocking_reasons.append("control_boundary_cannot_route_delegate_to_dip")
    if prompt_supplied_hook_flags:
        blocking_reasons.append("prompt_supplied_hook_flags")
    if browser_supplied_hook_flags:
        blocking_reasons.append("browser_supplied_hook_flags")
    if write_side_effect_observed:
        blocking_reasons.append("control_boundary_write_side_effect")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if raw_route_id_recorded:
        blocking_reasons.append("raw_route_id_must_not_be_recorded")
    if raw_backend_details_exposed:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if secret_value_exposed:
        blocking_reasons.append("secret_value_must_not_be_exposed")
    if native_free_chat_router_claimed:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if product_ready_claimed:
        blocking_reasons.append("product_ready_must_not_be_claimed")

    ok = not blocking_reasons
    submit_boundary_status = "ok" if ok else "blocked"
    packet_extra = {
        "producer_built_by": "build_exec_wrapper_submit_boundary_probe_packet",
        "submit_boundary_status": submit_boundary_status,
        "entrypoint_kind": entrypoint_kind if entrypoint_kind_admitted else "",
        "entrypoint_scope": "controlled_codex_exec_stdin_submit",
        "control_boundary_wbp_owned": control_boundary_wbp_owned,
        "control_boundary_observed_prompt": control_boundary_observed_prompt,
        "control_boundary_pre_codex_decision": control_boundary_pre_codex_decision,
        "control_boundary_post_factum_only": control_boundary_post_factum_only,
        "control_boundary_can_enforce_router": control_boundary_can_enforce_router,
        "control_boundary_can_route_delegate_to_dip": (
            control_boundary_can_route_delegate_to_dip
        ),
        "router_delegate_prompt_contract_bound": (
            router_delegate_prompt_contract_bound
        ),
        "effect": EFFECT_PROBE,
        "changed_files": [],
        "source_prompt_sha256": (
            prompt_sha256 if control_boundary_observed_prompt else ""
        ),
        "source_run_sha256": source_run_sha256,
        "stdin_prompt_used": stdin_prompt_used,
        "command_uses_stdin_dash": command_uses_stdin_dash,
        "command_json_mode": command_json_mode,
        "env_codex_home_is_temp": env_codex_home_is_temp,
        "env_home_is_temp": env_home_is_temp,
        "workdir_is_temp": workdir_is_temp,
        "command_workdir_is_temp": command_workdir_is_temp,
        "command_output_file_is_temp": command_output_file_is_temp,
        "current_codex_home_used": current_codex_home_used,
        "submit_boundary_sequence": submit_boundary_sequence,
        "submit_boundary_sequence_ok": submit_boundary_sequence_ok,
        "owned_temp_config_written": owned_temp_config_written,
        "owned_temp_output_file_reserved": owned_temp_output_file_reserved,
        "effective_config_written": effective_config_written,
        "prompt_supplied_hook_flags": prompt_supplied_hook_flags,
        "browser_supplied_hook_flags": browser_supplied_hook_flags,
        "state_written": state_written,
        "profile_written": profile_written,
        "config_written": config_written,
        "route_registry_written": route_registry_written,
        "credential_written": credential_written,
        "runtime_state_written": runtime_state_written,
        "write_side_effect_observed": write_side_effect_observed,
        "raw_prompt_recorded": raw_prompt_recorded,
        "prompt_text_recorded": False,
        "raw_route_id_recorded": raw_route_id_recorded,
        "raw_backend_details_exposed": raw_backend_details_exposed,
        "secret_value_exposed": secret_value_exposed,
        "product_ready": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready_free_chat": True,
        "no_secret_exposed": not secret_value_exposed,
    }
    digest_packet = {
        "packet_kind": EXEC_WRAPPER_SUBMIT_BOUNDARY_PROBE_PACKET_KIND,
        **packet_extra,
    }
    packet_extra["submit_boundary_claim_digest_present"] = True
    packet_extra["submit_boundary_claim_sha256"] = (
        _exec_wrapper_submit_boundary_claim_sha256(digest_packet)
    )

    if ok:
        machine_error_code = "OK"
    elif prompt_supplied_hook_flags or browser_supplied_hook_flags:
        machine_error_code = EXEC_WRAPPER_SUBMIT_BOUNDARY_AUTHORITY_REJECTED
    elif write_side_effect_observed:
        machine_error_code = EXEC_WRAPPER_SUBMIT_BOUNDARY_SIDE_EFFECT_REJECTED
    elif not prompt_digest_present or not source_run_sha256:
        machine_error_code = EXEC_WRAPPER_SUBMIT_BOUNDARY_DIGEST_NOT_BOUND
    else:
        machine_error_code = EXEC_WRAPPER_SUBMIT_BOUNDARY_NOT_PROVEN

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP exec-wrapper submit boundary is proven by bounded evidence."
            if ok
            else "WBP exec-wrapper submit boundary is not proven."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra=packet_extra,
        packet_kind=EXEC_WRAPPER_SUBMIT_BOUNDARY_PROBE_PACKET_KIND,
        final_status=(
            EXEC_WRAPPER_SUBMIT_BOUNDARY_FINAL_STATUS_PROVEN
            if ok
            else EXEC_WRAPPER_SUBMIT_BOUNDARY_FINAL_STATUS_BLOCKED
        ),
        result_status="proven" if ok else "blocked",
    )


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
_CODEX_EXEC_UNSUPPORTED_MODEL_PATTERN = re.compile(
    r"(?i)\b("
    r"unsupported model|model is not supported|model .* not supported|"
    r"not supported when using codex with a chatgpt account"
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


def _codex_exec_unsupported_model_from_events(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if _safe_text(event.get("type") or "", limit=128) != "error":
            continue
        try:
            encoded = json.dumps(event, ensure_ascii=True, sort_keys=True)
        except (TypeError, ValueError):
            encoded = repr(event)
        if _CODEX_EXEC_UNSUPPORTED_MODEL_PATTERN.search(encoded):
            return True
    return False


_CODEX_EXEC_SUBAGENT_MARKER_PATTERN = re.compile(
    r"(?i)\b(subagent|sub-agent|sub agent|codex agent)\b"
)
_CODEX_EXEC_DIP_ALIAS_PATTERN = re.compile(r"(?i)\b(dip|agent\s*2)\b")


def _codex_exec_local_subagent_used_as_dip(events: list[dict[str, Any]]) -> bool:
    for event in events:
        for mapping in _iter_mappings(event):
            item_type = _first_text_field(
                mapping,
                ("type", "kind", "item_type", "itemType"),
            )
            name = _first_text_field(
                mapping,
                ("name", "agent_name", "agentName", "display_name", "displayName"),
            )
            text = _first_text_field(mapping, ("text", "message", "content", "title"))
            combined = " ".join(part for part in (item_type, name, text) if part)
            if not combined:
                continue
            if not _CODEX_EXEC_SUBAGENT_MARKER_PATTERN.search(combined):
                continue
            if _CODEX_EXEC_DIP_ALIAS_PATTERN.search(combined):
                return True
    return False


_CODEX_EXEC_TOOL_CALL_SUCCESS_STATUSES = {
    "completed",
    "complete",
    "succeeded",
    "success",
    "ok",
}
_CODEX_EXEC_TOOL_CALL_FAILED_STATUSES = {
    "failed",
    "failure",
    "error",
    "cancelled",
    "canceled",
    "rejected",
}


def _codex_exec_tool_call_completed(candidate: Mapping[str, Any]) -> bool:
    status_key = str(candidate.get("status") or "").casefold()
    if status_key in _CODEX_EXEC_TOOL_CALL_SUCCESS_STATUSES:
        return True
    if status_key in _CODEX_EXEC_TOOL_CALL_FAILED_STATUSES:
        return False
    return bool(candidate.get("event_type") == "item.completed" and not status_key)


def _select_codex_exec_tool_call_candidate(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    for candidate in reversed(candidates):
        if _codex_exec_tool_call_completed(candidate):
            return candidate
    return candidates[-1] if candidates else {}


_CODEX_EXEC_TOOL_CALL_OBSERVATION_DIGEST_FIELDS = (
    "packet_kind",
    "producer_built_by",
    "codex_exec_json_events_observed",
    "codex_observation_sequence",
    "codex_exec_exit_code",
    "codex_exec_unsupported_model_observed",
    "codex_exec_auth_blocker_observed",
    "codex_exec_jsonl_parse_error_count",
    "codex_exec_event_count",
    "codex_exec_event_digest",
    "real_codex_prompt_executed",
    "codex_delegate_to_dip_tool_call_attempted",
    "delegate_to_dip_tool_called",
    "codex_delegate_to_dip_tool_called",
    "delegate_to_dip_tool_call_completed",
    "delegate_to_dip_tool_call_failed",
    "tool_name",
    "mcp_server_name_observed",
    "tool_call_status_observed",
    "tool_call_digest_present",
    "tool_call_sha256",
    "prompt_sha256",
    "prompt_digest_present",
    "expected_delegate_tool_call_digest_present",
    "expected_delegate_tool_call_matched",
    "prompt_task_digest_matched",
    "prompt_to_mcp_call_bound",
    "browser_authority_fields_rejected",
    "browser_authority_field_count",
    "local_codex_subagent_used_as_dip",
    "codex_subagent_used_as_dip",
    "api_lane_called",
    "fallback_used",
    "local_imitation_used",
    "product_ready",
    "native_free_chat_router_proven",
    "raw_jsonl_recorded",
    "raw_stderr_recorded",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "tool_call_arguments_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
)


def _codex_exec_tool_call_observation_claim_sha256(
    packet: Mapping[str, Any],
) -> str:
    payload = {
        field: packet.get(field)
        for field in _CODEX_EXEC_TOOL_CALL_OBSERVATION_DIGEST_FIELDS
    }
    return _sha256_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


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
    intent_claim_sha256 = _hex_sha256(prompt.get("intent_claim_sha256") or "")
    delegated_task_sha256 = _hex_sha256(prompt.get("delegated_task_sha256") or "")
    natural_command_shape = _safe_text(
        prompt.get("natural_command_shape") or "",
        limit=128,
    )
    binding_status = _safe_text(prompt.get("binding_status") or "", limit=128)
    canonicalization_rule_id = _safe_text(
        prompt.get("canonicalization_rule_id") or "",
        limit=128,
    )
    canonicalization_supported = prompt.get("canonicalization_supported") is True
    canonicalization_input_sha256 = _hex_sha256(
        prompt.get("canonicalization_input_sha256") or ""
    )
    canonicalization_output_sha256 = _hex_sha256(
        prompt.get("canonicalization_output_sha256") or ""
    )
    delegated_task_candidate_sha256s = [
        digest
        for digest in (
            _hex_sha256(candidate)
            for candidate in (
                prompt.get("delegated_task_candidate_sha256s")
                if isinstance(prompt.get("delegated_task_candidate_sha256s"), list)
                else []
            )
        )
        if digest
    ]
    if delegated_task_sha256 and delegated_task_sha256 not in delegated_task_candidate_sha256s:
        delegated_task_candidate_sha256s.insert(0, delegated_task_sha256)
    candidates = _codex_exec_mcp_tool_call_candidates(events)
    selected_call = _select_codex_exec_tool_call_candidate(candidates)
    arguments = (
        dict(selected_call.get("arguments"))
        if isinstance(selected_call.get("arguments"), Mapping)
        else {}
    )
    actual_call_sha256 = _delegate_call_sha256(arguments) if arguments else ""
    forbidden_authority_fields = sorted(
        _safe_text(field, limit=80)
        for field in set(arguments) - {"task", "expected_alias", "alias"}
    )
    task_text = _safe_text(arguments.get("task") or "", limit=4096)
    task_sha256 = _sha256_text(task_text) if task_text else ""
    expected_call_matches = bool(
        expected_call_sha256 and actual_call_sha256 == expected_call_sha256
    )
    prompt_task_matches = bool(prompt_sha256 and task_sha256 == prompt_sha256)
    intent_task_matches = bool(
        intent_claim_sha256
        and task_sha256
        and task_sha256 in set(delegated_task_candidate_sha256s)
    )
    tool_call_attempted = bool(selected_call)
    tool_call_completed = bool(
        selected_call and _codex_exec_tool_call_completed(selected_call)
    )
    tool_call_failed = bool(selected_call and not tool_call_completed)
    if expected_call_sha256:
        prompt_binding_mode = "expected_delegate_tool_call"
        prompt_to_mcp_call_bound = tool_call_completed and expected_call_matches
    elif intent_claim_sha256 and delegated_task_candidate_sha256s:
        prompt_binding_mode = "natural_intent_claim"
        prompt_to_mcp_call_bound = tool_call_completed and intent_task_matches
    else:
        prompt_binding_mode = "full_prompt_digest"
        prompt_to_mcp_call_bound = tool_call_completed and prompt_task_matches
    delegate_to_dip_tool_called = tool_call_completed
    events_observed = bool(events)
    real_codex_prompt_executed = any(
        event_type in {"thread.started", "turn.started", "turn.completed"}
        for event_type in event_types
    )
    local_codex_subagent_used_as_dip = _codex_exec_local_subagent_used_as_dip(events)
    stderr_safe = _safe_text(stderr_text, limit=4096)
    unsupported_model_observed = bool(
        exec_exit_code != 0
        and (
            _CODEX_EXEC_UNSUPPORTED_MODEL_PATTERN.search(stderr_safe)
            or _codex_exec_unsupported_model_from_events(events)
        )
    )
    auth_blocker_observed = bool(
        exec_exit_code != 0
        and not unsupported_model_observed
        and (
            _CODEX_EXEC_AUTH_BLOCKER_PATTERN.search(stderr_safe)
            or _codex_exec_auth_blocker_from_events(events)
        )
    )
    blocking_reasons: list[str] = []
    if exec_exit_code != 0:
        blocking_reasons.append("codex_exec_nonzero_exit")
    if unsupported_model_observed:
        blocking_reasons.append("codex_model_not_admitted")
    if auth_blocker_observed:
        blocking_reasons.append("codex_exec_auth_or_model_admission_required")
    if parse_errors:
        blocking_reasons.append("codex_exec_jsonl_parse_error")
    if not events_observed:
        blocking_reasons.append("codex_exec_json_events_not_observed")
    if not real_codex_prompt_executed:
        blocking_reasons.append("real_codex_prompt_not_executed")
    if local_codex_subagent_used_as_dip:
        blocking_reasons.append("codex_subagent_used_as_dip")
    if not tool_call_attempted:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_observed")
    elif not tool_call_completed:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_completed")
    if tool_call_failed:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_failed")
    if forbidden_authority_fields:
        blocking_reasons.append("codex_tool_call_forbidden_authority_field")
    if tool_call_completed and not prompt_to_mcp_call_bound:
        blocking_reasons.append("prompt_not_bound_to_codex_mcp_tool_call")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif unsupported_model_observed:
        machine_error_code = CODEX_EXEC_MODEL_NOT_ADMITTED
    elif auth_blocker_observed:
        machine_error_code = "WBP_CODEX_EXEC_AUTHORIZATION_REQUIRED"
    elif parse_errors and not events:
        machine_error_code = "WBP_CODEX_EXEC_JSONL_INVALID"
    elif local_codex_subagent_used_as_dip:
        machine_error_code = CODEX_EXEC_SUBAGENT_USED_AS_DIP
    elif forbidden_authority_fields:
        machine_error_code = CODEX_EXEC_BROWSER_AUTHORITY_REJECTED
    else:
        machine_error_code = "WBP_CODEX_EXEC_TOOL_CALL_NOT_PROVEN"

    packet_extra = {
        "producer_built_by": "build_codex_exec_tool_call_observation_packet",
        "codex_exec_json_events_observed": events_observed,
        "codex_observation_sequence": CONTROLLED_EXEC_CODEX_OBSERVATION_SEQUENCE,
        "codex_exec_exit_code": int(exec_exit_code),
        "codex_exec_unsupported_model_observed": unsupported_model_observed,
        "codex_exec_auth_blocker_observed": auth_blocker_observed,
        "codex_exec_jsonl_parse_error_count": len(parse_errors),
        "codex_exec_event_count": len(events),
        "codex_exec_event_digest": _sha256_text(
            json.dumps(event_types, sort_keys=True)
        ),
        "real_codex_prompt_executed": real_codex_prompt_executed,
        "codex_delegate_to_dip_tool_call_attempted": tool_call_attempted,
        "delegate_to_dip_tool_called": delegate_to_dip_tool_called,
        "codex_delegate_to_dip_tool_called": delegate_to_dip_tool_called,
        "delegate_to_dip_tool_call_completed": tool_call_completed,
        "delegate_to_dip_tool_call_failed": tool_call_failed,
        "tool_name": DELEGATE_TO_DIP_TOOL if tool_call_attempted else "",
        "mcp_server_name_observed": _safe_text(
            selected_call.get("server_name") or "", limit=128
        ),
        "tool_call_status_observed": _safe_text(
            selected_call.get("status") or "", limit=80
        ),
        "tool_call_digest_present": bool(actual_call_sha256),
        "tool_call_sha256": actual_call_sha256,
        "tool_call_task_digest_present": bool(task_sha256),
        "tool_call_task_sha256": task_sha256,
        "prompt_sha256": prompt_sha256 if prompt_to_mcp_call_bound else "",
        "prompt_digest_present": bool(prompt_sha256),
        "expected_delegate_tool_call_digest_present": bool(expected_call_sha256),
        "expected_delegate_tool_call_matched": expected_call_matches,
        "prompt_task_digest_matched": prompt_task_matches,
        "prompt_binding_mode": prompt_binding_mode,
        "intent_claim_digest_present": bool(intent_claim_sha256),
        "intent_claim_sha256": intent_claim_sha256,
        "natural_command_shape": natural_command_shape,
        "binding_status": binding_status,
        "canonicalization_rule_id": canonicalization_rule_id,
        "canonicalization_supported": canonicalization_supported,
        "canonicalization_input_digest_present": bool(canonicalization_input_sha256),
        "canonicalization_input_sha256": canonicalization_input_sha256,
        "canonicalization_output_digest_present": bool(canonicalization_output_sha256),
        "canonicalization_output_sha256": canonicalization_output_sha256,
        "delegated_task_digest_present": bool(delegated_task_sha256),
        "delegated_task_sha256": delegated_task_sha256,
        "delegated_task_candidate_digest_count": len(
            delegated_task_candidate_sha256s[:8]
        ),
        "delegated_task_source": _safe_text(
            prompt.get("delegated_task_source") or "",
            limit=128,
        ),
        "tool_call_task_matches_intent": intent_task_matches,
        "intent_claim_digest_bound": bool(
            prompt_binding_mode == "natural_intent_claim"
            and prompt_to_mcp_call_bound
            and intent_task_matches
        ),
        "prompt_to_mcp_call_bound": prompt_to_mcp_call_bound,
        "browser_authority_fields_rejected": bool(forbidden_authority_fields),
        "browser_authority_field_count": len(forbidden_authority_fields),
        "local_codex_subagent_used_as_dip": local_codex_subagent_used_as_dip,
        "codex_subagent_used_as_dip": local_codex_subagent_used_as_dip,
        "api_lane_called": False,
        "fallback_used": False,
        "local_imitation_used": local_codex_subagent_used_as_dip,
        "product_ready": False,
        "custom_codex_ui_visibility_proven": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_api_lane_provider_dispatch": True,
        "raw_jsonl_recorded": False,
        "raw_stderr_recorded": False,
        "raw_prompt_recorded": False,
        "raw_task_recorded": False,
        "prompt_text_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "no_secret_exposed": True,
    }
    digest_packet = {
        "packet_kind": CODEX_EXEC_TOOL_CALL_PACKET_KIND,
        **packet_extra,
    }
    packet_extra["codex_tool_call_claim_digest_present"] = True
    packet_extra["codex_tool_call_claim_sha256"] = (
        _codex_exec_tool_call_observation_claim_sha256(digest_packet)
    )

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "Codex exec JSONL proves a prompt-bound delegate_to_dip MCP tool call."
            if ok
            else "Codex exec JSONL does not prove a prompt-bound delegate_to_dip MCP tool call."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra=packet_extra,
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


_ROUTER_HOOK_SOURCE_EVENT_DIGEST_FIELDS = (
    "packet_kind",
    "source_status",
    "source_wbp_owned",
    "source_kind",
    "source_effect",
    "changed_files",
    "source_run_sha256",
    "source_prompt_sha256",
    "source_control_boundary_proven",
    "source_prompt_digest_bound",
    "hook_observed_prompt",
    "hook_can_enforce_router",
    "hook_can_route_delegate_to_dip",
    "codex_tool_call_observation_packet_ok",
    "real_codex_prompt_executed",
    "prompt_to_mcp_call_bound",
    "delegate_to_dip_called",
    "manual_hook_packet_used",
    "synthetic_hook_packet_used",
    "prompt_supplied_hook_flags",
    "browser_supplied_hook_flags",
    "state_written",
    "profile_written",
    "config_written",
    "route_registry_written",
    "credential_written",
    "runtime_state_written",
    "raw_prompt_recorded",
    "raw_route_id_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "product_ready",
    "native_free_chat_router_proven",
)


def _router_hook_source_event_claim_sha256(
    event: Mapping[str, Any],
) -> str:
    payload = {
        field: event.get(field)
        for field in _ROUTER_HOOK_SOURCE_EVENT_DIGEST_FIELDS
    }
    return _sha256_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


_ROUTER_HOOK_CONTROL_BOUNDARY_DIGEST_FIELDS = (
    "packet_kind",
    "control_boundary_status",
    "control_boundary_wbp_owned",
    "control_boundary_evidence_kind",
    "control_boundary_source_effect",
    "changed_files",
    "source_run_sha256",
    "source_prompt_sha256",
    "control_boundary_observed_prompt",
    "control_boundary_prompt_digest_bound",
    "control_boundary_run_digest_present",
    "control_boundary_pre_codex_decision",
    "control_boundary_post_factum_only",
    "control_boundary_can_enforce_router",
    "control_boundary_can_route_delegate_to_dip",
    "manual_boundary_evidence_used",
    "synthetic_boundary_evidence_used",
    "prompt_supplied_hook_flags",
    "browser_supplied_hook_flags",
    "state_written",
    "profile_written",
    "config_written",
    "route_registry_written",
    "credential_written",
    "runtime_state_written",
    "raw_prompt_recorded",
    "raw_route_id_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "local_codex_subagent_used_as_dip",
    "local_imitation_used",
    "fallback_used",
    "product_ready",
    "native_free_chat_router_proven",
)


def _router_hook_control_boundary_claim_sha256(
    packet: Mapping[str, Any],
) -> str:
    payload = {
        field: packet.get(field)
        for field in _ROUTER_HOOK_CONTROL_BOUNDARY_DIGEST_FIELDS
    }
    return _sha256_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def build_router_hook_control_boundary_packet(
    *,
    prompt_packet: Mapping[str, Any] | None = None,
    boundary_evidence_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    evidence = (
        dict(boundary_evidence_packet)
        if isinstance(boundary_evidence_packet, Mapping)
        else {}
    )

    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    evidence_kind = _safe_text(evidence.get("packet_kind") or "", limit=128)
    evidence_kind_admitted = (
        evidence_kind in ROUTER_HOOK_CONTROL_BOUNDARY_ALLOWED_EVIDENCE_KINDS
    )
    evidence_status_ok = bool(
        evidence.get("status") == "ok"
        and evidence.get("result_status") in {"", "proven"}
        and evidence.get("final_status")
        == EXEC_WRAPPER_SUBMIT_BOUNDARY_FINAL_STATUS_PROVEN
    )
    evidence_producer_valid = bool(
        evidence_kind == EXEC_WRAPPER_SUBMIT_BOUNDARY_PROBE_PACKET_KIND
        and evidence.get("producer_built_by")
        == "build_exec_wrapper_submit_boundary_probe_packet"
    )
    evidence_claim_sha256 = _hex_sha256(
        evidence.get("submit_boundary_claim_sha256") or ""
    )
    evidence_claim_digest_present = bool(
        evidence.get("submit_boundary_claim_digest_present") is True
        and evidence_claim_sha256
    )
    evidence_claim_digest_matched = bool(
        evidence_claim_digest_present
        and evidence_claim_sha256
        == _exec_wrapper_submit_boundary_claim_sha256(evidence)
    )
    evidence_packet_ok = bool(
        evidence_kind_admitted
        and evidence_status_ok
        and evidence_producer_valid
        and evidence_claim_digest_matched
    )
    evidence_effect = _safe_text(
        evidence.get("source_effect") or evidence.get("effect") or "",
        limit=80,
    )
    evidence_effect_admitted = evidence_effect in {"probe", "read"}
    evidence_changed_files = evidence.get("changed_files")
    evidence_changed_files_empty = (
        isinstance(evidence_changed_files, list)
        and not evidence_changed_files
    )
    source_prompt_sha256 = _hex_sha256(
        evidence.get("source_prompt_sha256")
        or evidence.get("prompt_sha256")
        or ""
    )
    source_run_sha256 = _hex_sha256(
        evidence.get("source_run_sha256")
        or evidence.get("run_sha256")
        or evidence.get("run_id_sha256")
        or ""
    )
    control_boundary_wbp_owned = evidence.get("control_boundary_wbp_owned") is True
    control_boundary_observed_prompt = bool(
        evidence.get("control_boundary_observed_prompt") is True
        or evidence.get("hook_observed_prompt") is True
        or evidence.get("prompt_observed") is True
    )
    control_boundary_prompt_digest_bound = bool(
        prompt_digest_present
        and source_prompt_sha256
        and source_prompt_sha256 == prompt_sha256
    )
    control_boundary_run_digest_present = bool(source_run_sha256)
    control_boundary_pre_codex_decision = (
        evidence.get("control_boundary_pre_codex_decision") is True
    )
    control_boundary_post_factum_only = bool(
        evidence.get("control_boundary_post_factum_only") is True
        or evidence_kind == "wbp_codex_exec_jsonl_observer"
        or (
            control_boundary_observed_prompt
            and not control_boundary_pre_codex_decision
        )
    )
    evidence_can_enforce_router = (
        evidence.get("control_boundary_can_enforce_router") is True
    )
    evidence_can_route_delegate_to_dip = (
        evidence.get("control_boundary_can_route_delegate_to_dip") is True
    )
    manual_boundary_evidence_used = bool(
        evidence.get("manual_boundary_evidence_used") is True
        or evidence_kind in {"", "manual", "manual_boundary_evidence"}
    )
    synthetic_boundary_evidence_used = bool(
        evidence.get("synthetic_boundary_evidence_used") is True
        or evidence_kind in {"synthetic", "test_only"}
    )
    prompt_supplied_hook_flags = bool(
        evidence.get("prompt_supplied_hook_flags") is True
        or evidence.get("browser_can_supply_prompt_authority") is True
    )
    browser_supplied_hook_flags = bool(
        evidence.get("browser_supplied_hook_flags") is True
        or evidence.get("browser_can_supply_route_authority") is True
        or evidence.get("browser_can_supply_model_authority") is True
    )
    state_written = evidence.get("state_written") is True
    profile_written = evidence.get("profile_written") is True
    config_written = evidence.get("config_written") is True
    route_registry_written = evidence.get("route_registry_written") is True
    credential_written = evidence.get("credential_written") is True
    runtime_state_written = evidence.get("runtime_state_written") is True
    write_side_effect_observed = bool(
        state_written
        or profile_written
        or config_written
        or route_registry_written
        or credential_written
        or runtime_state_written
        or (
            bool(evidence)
            and (not evidence_changed_files_empty or not evidence_effect_admitted)
        )
    )
    raw_prompt_recorded = bool(
        evidence.get("raw_prompt_recorded") is True
        or evidence.get("prompt_text_recorded") is True
    )
    raw_route_id_recorded = evidence.get("raw_route_id_recorded") is True
    raw_backend_details_exposed = evidence.get("raw_backend_details_exposed") is True
    secret_value_exposed = evidence.get("secret_value_exposed") is True
    local_codex_subagent_used_as_dip = bool(
        evidence.get("local_codex_subagent_used_as_dip") is True
        or evidence.get("codex_subagent_used_as_dip") is True
    )
    local_imitation_used = bool(
        local_codex_subagent_used_as_dip
        or evidence.get("local_imitation_used") is True
    )
    fallback_used = evidence.get("fallback_used") is True
    product_ready_claimed = evidence.get("product_ready") is True
    native_free_chat_router_claimed = (
        evidence.get("native_free_chat_router_proven") is True
    )
    control_boundary_can_enforce_router = bool(
        control_boundary_wbp_owned
        and control_boundary_observed_prompt
        and control_boundary_prompt_digest_bound
        and control_boundary_run_digest_present
        and control_boundary_pre_codex_decision
        and not control_boundary_post_factum_only
        and evidence_packet_ok
        and evidence_can_enforce_router
    )
    control_boundary_can_route_delegate_to_dip = bool(
        control_boundary_can_enforce_router
        and evidence_can_route_delegate_to_dip
    )

    blocking_reasons: list[str] = []
    if not evidence:
        blocking_reasons.append("control_boundary_evidence_missing")
    if not evidence_kind_admitted:
        blocking_reasons.append("control_boundary_evidence_kind_not_admitted")
    if not evidence_status_ok:
        blocking_reasons.append("control_boundary_evidence_packet_not_ok")
    if not evidence_producer_valid:
        blocking_reasons.append("control_boundary_evidence_producer_invalid")
    if not evidence_claim_digest_present:
        blocking_reasons.append("control_boundary_evidence_claim_digest_missing")
    elif not evidence_claim_digest_matched:
        blocking_reasons.append("control_boundary_evidence_claim_digest_mismatch")
    if not prompt_digest_present:
        blocking_reasons.append("prompt_digest_missing")
    if not control_boundary_wbp_owned:
        blocking_reasons.append("control_boundary_not_wbp_owned")
    if not control_boundary_observed_prompt:
        blocking_reasons.append("control_boundary_prompt_not_observed")
    if not control_boundary_prompt_digest_bound:
        blocking_reasons.append("control_boundary_prompt_digest_not_bound")
    if not control_boundary_run_digest_present:
        blocking_reasons.append("control_boundary_run_digest_missing")
    if not control_boundary_pre_codex_decision:
        blocking_reasons.append("control_boundary_pre_codex_decision_not_proven")
    if control_boundary_post_factum_only:
        blocking_reasons.append("control_boundary_post_factum_only")
    if not control_boundary_can_enforce_router:
        blocking_reasons.append("control_boundary_cannot_enforce_router")
    if not control_boundary_can_route_delegate_to_dip:
        blocking_reasons.append("control_boundary_cannot_route_delegate_to_dip")
    if manual_boundary_evidence_used:
        blocking_reasons.append("manual_boundary_evidence_not_admitted")
    if synthetic_boundary_evidence_used:
        blocking_reasons.append("synthetic_boundary_evidence_not_admitted")
    if prompt_supplied_hook_flags:
        blocking_reasons.append("prompt_supplied_hook_flags")
    if browser_supplied_hook_flags:
        blocking_reasons.append("browser_supplied_hook_flags")
    if write_side_effect_observed:
        blocking_reasons.append("control_boundary_write_side_effect")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if raw_route_id_recorded:
        blocking_reasons.append("raw_route_id_must_not_be_recorded")
    if raw_backend_details_exposed:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if secret_value_exposed:
        blocking_reasons.append("secret_value_must_not_be_exposed")
    if local_codex_subagent_used_as_dip:
        blocking_reasons.append("local_codex_subagent_used_as_dip")
    if local_imitation_used:
        blocking_reasons.append("local_imitation_used")
    if fallback_used:
        blocking_reasons.append("fallback_used")
    if native_free_chat_router_claimed:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if product_ready_claimed:
        blocking_reasons.append("product_ready_must_not_be_claimed")

    ok = not blocking_reasons
    control_boundary_status = "ok" if ok else "blocked"
    packet_extra = {
        "producer_built_by": "build_router_hook_control_boundary_packet",
        "control_boundary_status": control_boundary_status,
        "control_boundary_wbp_owned": control_boundary_wbp_owned,
        "control_boundary_evidence_packet_ok": evidence_packet_ok,
        "control_boundary_evidence_producer_valid": evidence_producer_valid,
        "control_boundary_evidence_claim_digest_present": (
            evidence_claim_digest_present
        ),
        "control_boundary_evidence_claim_digest_matched": (
            evidence_claim_digest_matched
        ),
        "control_boundary_evidence_kind": (
            evidence_kind if evidence_kind_admitted else ""
        ),
        "control_boundary_source_effect": (
            evidence_effect if evidence_effect_admitted else ""
        ),
        "changed_files": [],
        "source_run_sha256": source_run_sha256,
        "source_prompt_sha256": (
            source_prompt_sha256 if control_boundary_prompt_digest_bound else ""
        ),
        "control_boundary_observed_prompt": control_boundary_observed_prompt,
        "control_boundary_prompt_digest_bound": control_boundary_prompt_digest_bound,
        "control_boundary_run_digest_present": control_boundary_run_digest_present,
        "control_boundary_pre_codex_decision": control_boundary_pre_codex_decision,
        "control_boundary_post_factum_only": control_boundary_post_factum_only,
        "control_boundary_can_enforce_router": control_boundary_can_enforce_router,
        "control_boundary_can_route_delegate_to_dip": (
            control_boundary_can_route_delegate_to_dip
        ),
        "manual_boundary_evidence_used": manual_boundary_evidence_used,
        "synthetic_boundary_evidence_used": synthetic_boundary_evidence_used,
        "prompt_supplied_hook_flags": prompt_supplied_hook_flags,
        "browser_supplied_hook_flags": browser_supplied_hook_flags,
        "state_written": state_written,
        "profile_written": profile_written,
        "config_written": config_written,
        "route_registry_written": route_registry_written,
        "credential_written": credential_written,
        "runtime_state_written": runtime_state_written,
        "write_side_effect_observed": write_side_effect_observed,
        "raw_prompt_recorded": raw_prompt_recorded,
        "prompt_text_recorded": False,
        "raw_route_id_recorded": raw_route_id_recorded,
        "raw_backend_details_exposed": raw_backend_details_exposed,
        "secret_value_exposed": secret_value_exposed,
        "local_codex_subagent_used_as_dip": local_codex_subagent_used_as_dip,
        "local_imitation_used": local_imitation_used,
        "fallback_used": fallback_used,
        "product_ready": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready_free_chat": True,
        "no_secret_exposed": not secret_value_exposed,
    }
    digest_packet = {
        "packet_kind": ROUTER_HOOK_CONTROL_BOUNDARY_PACKET_KIND,
        **packet_extra,
    }
    packet_extra["control_boundary_claim_digest_present"] = True
    packet_extra["control_boundary_claim_sha256"] = (
        _router_hook_control_boundary_claim_sha256(digest_packet)
    )

    if ok:
        machine_error_code = "OK"
    elif prompt_supplied_hook_flags or browser_supplied_hook_flags:
        machine_error_code = ROUTER_HOOK_CONTROL_BOUNDARY_AUTHORITY_REJECTED
    elif write_side_effect_observed:
        machine_error_code = ROUTER_HOOK_CONTROL_BOUNDARY_SIDE_EFFECT_REJECTED
    elif (
        not control_boundary_run_digest_present
        or not control_boundary_prompt_digest_bound
    ):
        machine_error_code = ROUTER_HOOK_CONTROL_BOUNDARY_DIGEST_NOT_BOUND
    else:
        machine_error_code = ROUTER_HOOK_CONTROL_BOUNDARY_NOT_PROVEN

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP router hook control boundary is proven by bounded evidence."
            if ok
            else "WBP router hook control boundary is not proven."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra=packet_extra,
        packet_kind=ROUTER_HOOK_CONTROL_BOUNDARY_PACKET_KIND,
        final_status=(
            ROUTER_HOOK_CONTROL_BOUNDARY_FINAL_STATUS_PROVEN
            if ok
            else ROUTER_HOOK_CONTROL_BOUNDARY_FINAL_STATUS_BLOCKED
        ),
        result_status="proven" if ok else "blocked",
    )


def build_router_hook_source_event_packet(
    *,
    prompt_packet: Mapping[str, Any] | None = None,
    codex_tool_call_packet: Mapping[str, Any] | None = None,
    control_boundary_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    codex_call = (
        dict(codex_tool_call_packet)
        if isinstance(codex_tool_call_packet, Mapping)
        else {}
    )
    control_boundary = (
        dict(control_boundary_packet)
        if isinstance(control_boundary_packet, Mapping)
        else {}
    )

    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    codex_tool_call_observation_packet_ok = bool(
        codex_call.get("status") == "ok"
        and codex_call.get("packet_kind") == CODEX_EXEC_TOOL_CALL_PACKET_KIND
        and codex_call.get("result_status") in {"", "observed"}
    )
    real_codex_prompt_executed = (
        codex_call.get("real_codex_prompt_executed") is True
    )
    prompt_to_mcp_call_bound = bool(
        codex_call.get("prompt_to_mcp_call_bound") is True
        and codex_call.get("prompt_sha256") == prompt_sha256
        and prompt_digest_present
    )
    delegate_to_dip_called = bool(
        codex_call.get("delegate_to_dip_tool_called") is True
        or codex_call.get("tool_name") == DELEGATE_TO_DIP_TOOL
    )
    codex_browser_authority_rejected = (
        codex_call.get("browser_authority_fields_rejected") is True
        or codex_call.get("machine_error_code") == CODEX_EXEC_BROWSER_AUTHORITY_REJECTED
    )
    codex_local_subagent_used = bool(
        codex_call.get("local_codex_subagent_used_as_dip") is True
        or codex_call.get("codex_subagent_used_as_dip") is True
    )
    codex_local_imitation_used = bool(
        codex_local_subagent_used
        or codex_call.get("local_imitation_used") is True
    )
    codex_fallback_used = codex_call.get("fallback_used") is True

    boundary_prompt_sha256 = _hex_sha256(
        control_boundary.get("source_prompt_sha256")
        or control_boundary.get("prompt_sha256")
        or ""
    )
    boundary_run_sha256 = _hex_sha256(
        control_boundary.get("source_run_sha256")
        or control_boundary.get("run_sha256")
        or control_boundary.get("run_id_sha256")
        or ""
    )
    boundary_effect = _safe_text(
        control_boundary.get("source_effect")
        or control_boundary.get("effect")
        or "",
        limit=80,
    )
    boundary_changed_files = control_boundary.get("changed_files")
    boundary_changed_files_empty = (
        isinstance(boundary_changed_files, list)
        and not boundary_changed_files
    )
    boundary_producer_valid = (
        control_boundary.get("producer_built_by")
        == "build_router_hook_control_boundary_packet"
    )
    boundary_claim_sha256 = _hex_sha256(
        control_boundary.get("control_boundary_claim_sha256") or ""
    )
    boundary_claim_digest_present = bool(
        control_boundary.get("control_boundary_claim_digest_present") is True
        and boundary_claim_sha256
    )
    boundary_claim_digest_matched = bool(
        boundary_claim_digest_present
        and boundary_claim_sha256
        == _router_hook_control_boundary_claim_sha256(control_boundary)
    )
    control_boundary_packet_ok = bool(
        control_boundary.get("status") == "ok"
        and control_boundary.get("packet_kind") == ROUTER_HOOK_CONTROL_BOUNDARY_PACKET_KIND
        and control_boundary.get("result_status") in {"", "proven"}
        and control_boundary.get("final_status")
        == ROUTER_HOOK_CONTROL_BOUNDARY_FINAL_STATUS_PROVEN
        and control_boundary.get("control_boundary_status") == "ok"
        and boundary_producer_valid
        and boundary_claim_digest_matched
        and control_boundary.get("control_boundary_wbp_owned") is True
        and control_boundary.get("control_boundary_observed_prompt") is True
        and control_boundary.get("control_boundary_prompt_digest_bound") is True
        and control_boundary.get("control_boundary_run_digest_present") is True
        and control_boundary.get("control_boundary_pre_codex_decision") is True
        and control_boundary.get("control_boundary_post_factum_only") is not True
        and control_boundary.get("control_boundary_can_enforce_router") is True
        and control_boundary.get("control_boundary_can_route_delegate_to_dip") is True
        and boundary_effect in {"probe", "read"}
        and boundary_run_sha256
        and boundary_prompt_sha256 == prompt_sha256
        and boundary_changed_files_empty
        and control_boundary.get("state_written") is not True
        and control_boundary.get("profile_written") is not True
        and control_boundary.get("config_written") is not True
        and control_boundary.get("route_registry_written") is not True
        and control_boundary.get("credential_written") is not True
        and control_boundary.get("runtime_state_written") is not True
        and control_boundary.get("raw_prompt_recorded") is not True
        and control_boundary.get("raw_route_id_recorded") is not True
        and control_boundary.get("raw_backend_details_exposed") is not True
        and control_boundary.get("secret_value_exposed") is not True
        and control_boundary.get("product_ready") is not True
        and control_boundary.get("native_free_chat_router_proven") is not True
    )

    hook_observed_prompt = bool(
        codex_tool_call_observation_packet_ok
        and real_codex_prompt_executed
        and prompt_to_mcp_call_bound
    )
    source_control_boundary_proven = bool(
        hook_observed_prompt
        and delegate_to_dip_called
        and control_boundary_packet_ok
    )
    hook_can_enforce_router = source_control_boundary_proven
    hook_can_route_delegate_to_dip = source_control_boundary_proven
    source_kind = (
        "wbp_owned_router_hook_probe"
        if source_control_boundary_proven
        else "wbp_codex_exec_jsonl_observer"
    )
    codex_event_digest = _hex_sha256(codex_call.get("codex_exec_event_digest") or "")
    codex_tool_call_sha256 = _hex_sha256(codex_call.get("tool_call_sha256") or "")
    source_run_sha256 = (
        boundary_run_sha256
        if source_control_boundary_proven
        else _sha256_text(
            json.dumps(
                {
                    "codex_event_digest": codex_event_digest,
                    "prompt_sha256": prompt_sha256,
                    "tool_call_sha256": codex_tool_call_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        if codex_event_digest and prompt_sha256
        else ""
    )
    source_prompt_sha256 = prompt_sha256 if hook_observed_prompt else ""
    source_prompt_digest_bound = bool(
        hook_observed_prompt and source_prompt_sha256 == prompt_sha256
    )
    source_run_digest_present = bool(source_run_sha256)
    source_prompt_digest_present = bool(source_prompt_sha256)
    hook_logging_only = bool(
        hook_observed_prompt
        and (not hook_can_enforce_router or not hook_can_route_delegate_to_dip)
    )
    prompt_supplied_hook_flags = bool(
        codex_browser_authority_rejected
        or control_boundary.get("prompt_supplied_hook_flags") is True
        or control_boundary.get("browser_can_supply_prompt_authority") is True
    )
    browser_supplied_hook_flags = bool(
        control_boundary.get("browser_supplied_hook_flags") is True
        or control_boundary.get("browser_can_supply_route_authority") is True
        or control_boundary.get("browser_can_supply_model_authority") is True
    )
    state_written = control_boundary.get("state_written") is True
    profile_written = control_boundary.get("profile_written") is True
    config_written = control_boundary.get("config_written") is True
    route_registry_written = control_boundary.get("route_registry_written") is True
    credential_written = control_boundary.get("credential_written") is True
    runtime_state_written = control_boundary.get("runtime_state_written") is True
    write_side_effect_observed = bool(
        state_written
        or profile_written
        or config_written
        or route_registry_written
        or credential_written
        or runtime_state_written
        or (
            bool(control_boundary)
            and (
                boundary_effect not in {"probe", "read"}
                or not boundary_changed_files_empty
            )
        )
    )
    raw_prompt_recorded = bool(
        codex_call.get("raw_prompt_recorded") is True
        or control_boundary.get("raw_prompt_recorded") is True
        or control_boundary.get("prompt_text_recorded") is True
    )
    raw_route_id_recorded = control_boundary.get("raw_route_id_recorded") is True
    raw_backend_details_exposed = bool(
        codex_call.get("raw_backend_details_exposed") is True
        or control_boundary.get("raw_backend_details_exposed") is True
    )
    secret_value_exposed = bool(
        codex_call.get("secret_value_exposed") is True
        or control_boundary.get("secret_value_exposed") is True
    )
    product_ready_claimed = bool(
        codex_call.get("product_ready") is True
        or control_boundary.get("product_ready") is True
    )
    native_free_chat_router_claimed = bool(
        codex_call.get("native_free_chat_router_proven") is True
        or control_boundary.get("native_free_chat_router_proven") is True
    )

    blocking_reasons: list[str] = []
    if not prompt_digest_present:
        blocking_reasons.append("prompt_digest_missing")
    if not codex_call:
        blocking_reasons.append("codex_tool_call_observation_missing")
    elif not codex_tool_call_observation_packet_ok:
        blocking_reasons.append("codex_tool_call_observation_packet_not_ok")
    if not real_codex_prompt_executed:
        blocking_reasons.append("real_codex_prompt_not_executed")
    if not prompt_to_mcp_call_bound:
        blocking_reasons.append("prompt_not_bound_to_codex_mcp_tool_call")
    if not delegate_to_dip_called:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_observed")
    if not control_boundary_packet_ok:
        blocking_reasons.append("router_hook_control_boundary_not_proven")
    if control_boundary and not boundary_producer_valid:
        blocking_reasons.append("router_hook_control_boundary_producer_invalid")
    if control_boundary and not boundary_claim_digest_present:
        blocking_reasons.append("router_hook_control_boundary_claim_digest_missing")
    elif control_boundary and not boundary_claim_digest_matched:
        blocking_reasons.append("router_hook_control_boundary_claim_digest_mismatch")
    if hook_logging_only:
        blocking_reasons.append("router_hook_source_logging_only")
    if codex_browser_authority_rejected or prompt_supplied_hook_flags:
        blocking_reasons.append("prompt_supplied_hook_flags")
    if browser_supplied_hook_flags:
        blocking_reasons.append("browser_supplied_hook_flags")
    if codex_local_subagent_used:
        blocking_reasons.append("local_codex_subagent_used_as_dip")
    if codex_local_imitation_used:
        blocking_reasons.append("local_imitation_used")
    if codex_fallback_used:
        blocking_reasons.append("fallback_used")
    if not source_run_digest_present:
        blocking_reasons.append("router_hook_source_run_digest_missing")
    if not source_prompt_digest_present:
        blocking_reasons.append("router_hook_source_prompt_digest_missing")
    if not source_prompt_digest_bound:
        blocking_reasons.append("router_hook_source_prompt_digest_not_bound")
    if write_side_effect_observed:
        blocking_reasons.append("router_hook_source_write_side_effect")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if raw_route_id_recorded:
        blocking_reasons.append("raw_route_id_must_not_be_recorded")
    if raw_backend_details_exposed:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if secret_value_exposed:
        blocking_reasons.append("secret_value_must_not_be_exposed")
    if native_free_chat_router_claimed:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if product_ready_claimed:
        blocking_reasons.append("product_ready_must_not_be_claimed")

    ok = not blocking_reasons
    source_status = "ok" if ok else "blocked"
    event_extra = {
        "producer_built_by": "build_router_hook_source_event_packet",
        "source_status": source_status,
        "source_wbp_owned": True,
        "source_kind": source_kind,
        "source_effect": "probe",
        "changed_files": [],
        "source_run_digest_present": source_run_digest_present,
        "source_run_sha256": source_run_sha256,
        "source_prompt_digest_present": source_prompt_digest_present,
        "source_prompt_digest_bound": source_prompt_digest_bound,
        "source_prompt_sha256": source_prompt_sha256,
        "source_control_boundary_proven": source_control_boundary_proven,
        "control_boundary_packet_kind": str(
            control_boundary.get("packet_kind") or ""
        ),
        "control_boundary_packet_ok": control_boundary_packet_ok,
        "control_boundary_producer_valid": boundary_producer_valid,
        "control_boundary_claim_digest_present": boundary_claim_digest_present,
        "control_boundary_claim_digest_matched": boundary_claim_digest_matched,
        "hook_observed_prompt": hook_observed_prompt,
        "hook_can_enforce_router": hook_can_enforce_router,
        "hook_can_route_delegate_to_dip": hook_can_route_delegate_to_dip,
        "hook_logging_only": hook_logging_only,
        "codex_tool_call_observation_packet_ok": codex_tool_call_observation_packet_ok,
        "real_codex_prompt_executed": real_codex_prompt_executed,
        "prompt_to_mcp_call_bound": prompt_to_mcp_call_bound,
        "delegate_to_dip_called": delegate_to_dip_called,
        "manual_hook_packet_used": False,
        "synthetic_hook_packet_used": False,
        "prompt_supplied_hook_flags": prompt_supplied_hook_flags,
        "browser_supplied_hook_flags": browser_supplied_hook_flags,
        "state_written": state_written,
        "profile_written": profile_written,
        "config_written": config_written,
        "route_registry_written": route_registry_written,
        "credential_written": credential_written,
        "runtime_state_written": runtime_state_written,
        "write_side_effect_observed": write_side_effect_observed,
        "raw_prompt_recorded": raw_prompt_recorded,
        "prompt_text_recorded": False,
        "raw_route_id_recorded": raw_route_id_recorded,
        "raw_backend_details_exposed": raw_backend_details_exposed,
        "secret_value_exposed": secret_value_exposed,
        "product_ready": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready_free_chat": True,
        "no_secret_exposed": not secret_value_exposed,
    }
    digest_event = {
        "packet_kind": ROUTER_HOOK_SOURCE_EVENT_PACKET_KIND,
        **event_extra,
    }
    event_extra["source_event_claim_digest_present"] = True
    event_extra["source_event_claim_sha256"] = (
        _router_hook_source_event_claim_sha256(digest_event)
    )

    if ok:
        machine_error_code = "OK"
    elif prompt_supplied_hook_flags or browser_supplied_hook_flags:
        machine_error_code = ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED
    elif write_side_effect_observed:
        machine_error_code = ROUTER_HOOK_SOURCE_SIDE_EFFECT_REJECTED
    elif not source_run_digest_present or not source_prompt_digest_bound:
        machine_error_code = ROUTER_HOOK_SOURCE_DIGEST_NOT_BOUND
    elif not control_boundary_packet_ok or hook_logging_only:
        machine_error_code = ROUTER_HOOK_SOURCE_EVENT_CAPABILITY_NOT_PROVEN
    else:
        machine_error_code = ROUTER_HOOK_SOURCE_EVENT_NOT_PRODUCED

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP router hook source event is produced from capability evidence."
            if ok
            else "WBP router hook source event is not produced from capability evidence."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra=event_extra,
        packet_kind=ROUTER_HOOK_SOURCE_EVENT_PACKET_KIND,
        final_status=(
            ROUTER_HOOK_SOURCE_EVENT_FINAL_STATUS_PRODUCED
            if ok
            else ROUTER_HOOK_SOURCE_EVENT_FINAL_STATUS_BLOCKED
        ),
        result_status="produced" if ok else "blocked",
    )


def build_router_hook_source_admission_packet(
    *,
    prompt_packet: Mapping[str, Any] | None = None,
    source_event_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    source = (
        dict(source_event_packet)
        if isinstance(source_event_packet, Mapping)
        else {}
    )

    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    source_kind = _safe_text(source.get("source_kind") or "", limit=128)
    source_event_packet_kind = _safe_text(source.get("packet_kind") or "", limit=128)
    source_effect = _safe_text(
        source.get("source_effect") or source.get("effect") or "",
        limit=80,
    )
    source_event_packet_ok = bool(
        source.get("status") == "ok"
        and source_event_packet_kind == ROUTER_HOOK_SOURCE_EVENT_PACKET_KIND
        and source.get("result_status") in {"", "produced"}
        and source.get("final_status") == ROUTER_HOOK_SOURCE_EVENT_FINAL_STATUS_PRODUCED
        and source.get("source_status") == "ok"
    )
    source_event_producer_valid = (
        source.get("producer_built_by") == "build_router_hook_source_event_packet"
    )
    source_event_claim_sha256 = _hex_sha256(
        source.get("source_event_claim_sha256") or ""
    )
    source_event_claim_digest_present = bool(
        source.get("source_event_claim_digest_present") is True
        and source_event_claim_sha256
    )
    source_event_claim_digest_matched = bool(
        source_event_claim_digest_present
        and source_event_claim_sha256 == _router_hook_source_event_claim_sha256(source)
    )
    source_prompt_sha256 = _hex_sha256(
        source.get("source_prompt_sha256")
        or source.get("prompt_sha256")
        or ""
    )
    source_run_sha256 = _hex_sha256(
        source.get("source_run_sha256")
        or source.get("run_sha256")
        or source.get("run_id_sha256")
        or ""
    )
    source_present = bool(source)
    changed_files = source.get("changed_files")
    changed_files_empty = isinstance(changed_files, list) and not changed_files
    source_wbp_owned = source.get("source_wbp_owned") is True
    source_kind_admitted = source_kind in ROUTER_HOOK_SOURCE_ALLOWED_KINDS
    source_effect_admitted = source_effect in {"probe", "read"}
    source_prompt_digest_present = bool(source_prompt_sha256)
    source_run_digest_present = bool(source_run_sha256)
    source_prompt_digest_bound = bool(
        prompt_digest_present
        and source_prompt_digest_present
        and source_prompt_sha256 == prompt_sha256
    )
    hook_observed_prompt = bool(
        source.get("hook_observed_prompt") is True
        or source.get("prompt_observed") is True
    )
    hook_can_enforce_router = source.get("hook_can_enforce_router") is True
    hook_can_route_delegate_to_dip = (
        source.get("hook_can_route_delegate_to_dip") is True
    )
    source_control_boundary_proven = (
        source.get("source_control_boundary_proven") is True
    )
    source_capability_overclaimed = bool(
        (hook_can_enforce_router or hook_can_route_delegate_to_dip)
        and not source_control_boundary_proven
    )
    jsonl_observer_overclaimed = bool(
        source_kind == "wbp_codex_exec_jsonl_observer"
        and (hook_can_enforce_router or hook_can_route_delegate_to_dip)
    )
    hook_logging_only = bool(
        hook_observed_prompt
        and (not hook_can_enforce_router or not hook_can_route_delegate_to_dip)
    )
    manual_hook_packet_used = bool(
        source.get("manual_hook_packet_used") is True
        or source_kind in {"manual", "manual_hook_packet"}
    )
    synthetic_hook_packet_used = bool(
        source.get("synthetic_hook_packet_used") is True
        or source_kind in {"synthetic", "test_only"}
    )
    prompt_supplied_hook_flags = bool(
        source.get("prompt_supplied_hook_flags") is True
        or source.get("browser_can_supply_prompt_authority") is True
    )
    browser_supplied_hook_flags = bool(
        source.get("browser_supplied_hook_flags") is True
        or source.get("browser_can_supply_route_authority") is True
        or source.get("browser_can_supply_model_authority") is True
    )
    state_written = source.get("state_written") is True
    profile_written = source.get("profile_written") is True
    config_written = source.get("config_written") is True
    route_registry_written = source.get("route_registry_written") is True
    credential_written = source.get("credential_written") is True
    runtime_state_written = source.get("runtime_state_written") is True
    write_side_effect_observed = bool(
        source_present
        and (
            state_written
            or profile_written
            or config_written
            or route_registry_written
            or credential_written
            or runtime_state_written
            or not changed_files_empty
            or not source_effect_admitted
        )
    )
    raw_prompt_recorded = bool(
        source.get("raw_prompt_recorded") is True
        or source.get("prompt_text_recorded") is True
    )
    raw_route_id_recorded = source.get("raw_route_id_recorded") is True
    raw_backend_details_exposed = source.get("raw_backend_details_exposed") is True
    secret_value_exposed = source.get("secret_value_exposed") is True
    product_ready_claimed = source.get("product_ready") is True
    native_free_chat_router_claimed = (
        source.get("native_free_chat_router_proven") is True
    )

    blocking_reasons: list[str] = []
    if not source_present:
        blocking_reasons.append("router_hook_source_event_missing")
    if source_event_packet_kind != ROUTER_HOOK_SOURCE_EVENT_PACKET_KIND:
        blocking_reasons.append("router_hook_source_event_packet_kind_invalid")
    if source_present and not source_event_packet_ok:
        blocking_reasons.append("router_hook_source_event_packet_not_ok")
    if not source_event_producer_valid:
        blocking_reasons.append("router_hook_source_event_producer_invalid")
    if not source_event_claim_digest_present:
        blocking_reasons.append("router_hook_source_event_claim_digest_missing")
    elif not source_event_claim_digest_matched:
        blocking_reasons.append("router_hook_source_event_claim_digest_mismatch")
    if not prompt_digest_present:
        blocking_reasons.append("prompt_digest_missing")
    if not source_wbp_owned:
        blocking_reasons.append("router_hook_source_not_wbp_owned")
    if not source_kind_admitted:
        blocking_reasons.append("router_hook_source_kind_not_admitted")
    if not source_run_digest_present:
        blocking_reasons.append("router_hook_source_run_digest_missing")
    if not source_prompt_digest_present:
        blocking_reasons.append("router_hook_source_prompt_digest_missing")
    if not source_prompt_digest_bound:
        blocking_reasons.append("router_hook_source_prompt_digest_not_bound")
    if not hook_observed_prompt:
        blocking_reasons.append("hook_prompt_not_observed")
    if not hook_can_enforce_router:
        blocking_reasons.append("hook_cannot_enforce_router")
    if not hook_can_route_delegate_to_dip:
        blocking_reasons.append("hook_cannot_route_delegate_to_dip")
    if not source_control_boundary_proven:
        blocking_reasons.append("router_hook_control_boundary_not_proven")
    if source_capability_overclaimed:
        blocking_reasons.append("router_hook_source_capability_overclaimed")
    if jsonl_observer_overclaimed:
        blocking_reasons.append("router_hook_jsonl_observer_overclaimed")
    if hook_logging_only:
        blocking_reasons.append("router_hook_source_logging_only")
    if manual_hook_packet_used:
        blocking_reasons.append("manual_hook_packet_not_admitted")
    if synthetic_hook_packet_used:
        blocking_reasons.append("synthetic_hook_packet_not_admitted")
    if prompt_supplied_hook_flags:
        blocking_reasons.append("prompt_supplied_hook_flags")
    if browser_supplied_hook_flags:
        blocking_reasons.append("browser_supplied_hook_flags")
    if write_side_effect_observed:
        blocking_reasons.append("router_hook_source_write_side_effect")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if raw_route_id_recorded:
        blocking_reasons.append("raw_route_id_must_not_be_recorded")
    if raw_backend_details_exposed:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if secret_value_exposed:
        blocking_reasons.append("secret_value_must_not_be_exposed")
    if native_free_chat_router_claimed:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if product_ready_claimed:
        blocking_reasons.append("product_ready_must_not_be_claimed")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif prompt_supplied_hook_flags or browser_supplied_hook_flags:
        machine_error_code = ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED
    elif write_side_effect_observed:
        machine_error_code = ROUTER_HOOK_SOURCE_SIDE_EFFECT_REJECTED
    elif not source_run_digest_present or not source_prompt_digest_bound:
        machine_error_code = ROUTER_HOOK_SOURCE_DIGEST_NOT_BOUND
    elif manual_hook_packet_used or synthetic_hook_packet_used:
        machine_error_code = ROUTER_HOOK_SOURCE_NOT_ADMITTED
    elif (
        not source_control_boundary_proven
        or source_capability_overclaimed
        or jsonl_observer_overclaimed
        or not source_event_packet_ok
        or not source_event_claim_digest_matched
    ):
        machine_error_code = ROUTER_HOOK_SOURCE_EVENT_CAPABILITY_NOT_PROVEN
    else:
        machine_error_code = ROUTER_HOOK_SOURCE_NOT_ADMITTED

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP router hook source evidence is admitted for observation."
            if ok
            else "WBP router hook source evidence is not admitted."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "source_packet_kind": ROUTER_HOOK_SOURCE_ADMISSION_PACKET_KIND,
            "source_event_packet_kind": source_event_packet_kind,
            "source_event_packet_ok": source_event_packet_ok,
            "source_event_producer_valid": source_event_producer_valid,
            "source_event_claim_digest_present": source_event_claim_digest_present,
            "source_event_claim_digest_matched": source_event_claim_digest_matched,
            "source_status": "ok" if ok else "blocked",
            "source_wbp_owned": source_wbp_owned,
            "source_kind": source_kind if source_kind_admitted else "",
            "source_effect": source_effect if source_effect_admitted else "",
            "source_run_digest_present": source_run_digest_present,
            "source_run_sha256": source_run_sha256,
            "source_prompt_digest_present": source_prompt_digest_present,
            "source_prompt_digest_bound": source_prompt_digest_bound,
            "source_prompt_sha256": (
                source_prompt_sha256 if source_prompt_digest_bound else ""
            ),
            "prompt_digest_present": prompt_digest_present,
            "hook_observed_prompt": hook_observed_prompt,
            "hook_can_enforce_router": hook_can_enforce_router,
            "hook_can_route_delegate_to_dip": hook_can_route_delegate_to_dip,
            "hook_logging_only": hook_logging_only,
            "source_control_boundary_proven": source_control_boundary_proven,
            "source_capability_overclaimed": source_capability_overclaimed,
            "manual_hook_packet_used": manual_hook_packet_used,
            "synthetic_hook_packet_used": synthetic_hook_packet_used,
            "prompt_supplied_hook_flags": prompt_supplied_hook_flags,
            "browser_supplied_hook_flags": browser_supplied_hook_flags,
            "state_written": state_written,
            "profile_written": profile_written,
            "config_written": config_written,
            "route_registry_written": route_registry_written,
            "credential_written": credential_written,
            "runtime_state_written": runtime_state_written,
            "write_side_effect_observed": write_side_effect_observed,
            "raw_prompt_recorded": raw_prompt_recorded,
            "prompt_text_recorded": False,
            "raw_route_id_recorded": raw_route_id_recorded,
            "raw_backend_details_exposed": raw_backend_details_exposed,
            "secret_value_exposed": secret_value_exposed,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_product_ready_free_chat": True,
            "no_secret_exposed": not secret_value_exposed,
        },
        packet_kind=ROUTER_HOOK_SOURCE_ADMISSION_PACKET_KIND,
        final_status=(
            ROUTER_HOOK_SOURCE_ADMISSION_FINAL_STATUS_ADMITTED
            if ok
            else ROUTER_HOOK_SOURCE_ADMISSION_FINAL_STATUS_BLOCKED
        ),
        result_status="admitted" if ok else "blocked",
    )


def build_controlled_exec_router_hook_chain_packet(
    *,
    prompt_packet: Mapping[str, Any] | None = None,
    submit_boundary_probe_packet: Mapping[str, Any] | None = None,
    codex_tool_call_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    submit_boundary = (
        dict(submit_boundary_probe_packet)
        if isinstance(submit_boundary_probe_packet, Mapping)
        else {}
    )
    codex_call = (
        dict(codex_tool_call_packet)
        if isinstance(codex_tool_call_packet, Mapping)
        else {}
    )

    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    prompt_packet_kind = _safe_text(prompt.get("packet_kind") or "", limit=128)
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    prompt_packet_ok = bool(
        prompt_packet_kind == PROMPT_OBSERVATION_PACKET_KIND
        and prompt_digest_present
        and prompt.get("raw_prompt_recorded") is not True
        and prompt.get("prompt_text_recorded") is not True
        and prompt.get("expected_delegate_arguments_recorded") is not True
        and prompt.get("secret_value_exposed") is not True
        and prompt.get("raw_backend_details_exposed") is not True
    )

    submit_boundary_sequence = _safe_text(
        submit_boundary.get("submit_boundary_sequence") or "",
        limit=64,
    )
    submit_boundary_sequence_ok = (
        submit_boundary_sequence == CONTROLLED_EXEC_SUBMIT_BOUNDARY_SEQUENCE
    )
    submit_boundary_claim_sha256 = _hex_sha256(
        submit_boundary.get("submit_boundary_claim_sha256") or ""
    )
    submit_boundary_claim_digest_present = bool(
        submit_boundary.get("submit_boundary_claim_digest_present") is True
        and submit_boundary_claim_sha256
    )
    submit_boundary_claim_digest_matched = bool(
        submit_boundary_claim_digest_present
        and submit_boundary_claim_sha256
        == _exec_wrapper_submit_boundary_claim_sha256(submit_boundary)
    )
    submit_boundary_producer_valid = (
        submit_boundary.get("producer_built_by")
        == "build_exec_wrapper_submit_boundary_probe_packet"
    )
    submit_boundary_prompt_sha256 = _hex_sha256(
        submit_boundary.get("source_prompt_sha256")
        or submit_boundary.get("prompt_sha256")
        or ""
    )
    submit_boundary_packet_ok = bool(
        submit_boundary.get("status") == "ok"
        and submit_boundary.get("packet_kind")
        == EXEC_WRAPPER_SUBMIT_BOUNDARY_PROBE_PACKET_KIND
        and submit_boundary.get("result_status") in {"", "proven"}
        and submit_boundary.get("final_status")
        == EXEC_WRAPPER_SUBMIT_BOUNDARY_FINAL_STATUS_PROVEN
        and submit_boundary.get("submit_boundary_status") == "ok"
        and submit_boundary_producer_valid
        and submit_boundary_sequence_ok
        and submit_boundary_claim_digest_matched
    )
    prompt_to_submit_boundary_bound = bool(
        prompt_packet_ok
        and submit_boundary_prompt_sha256
        and submit_boundary_prompt_sha256 == prompt_sha256
        and submit_boundary.get("control_boundary_observed_prompt") is True
    )

    codex_observation_sequence = _safe_text(
        codex_call.get("codex_observation_sequence") or "",
        limit=64,
    )
    codex_observation_sequence_ok = (
        codex_observation_sequence == CONTROLLED_EXEC_CODEX_OBSERVATION_SEQUENCE
    )
    codex_observation_producer_valid = (
        codex_call.get("producer_built_by")
        == "build_codex_exec_tool_call_observation_packet"
    )
    codex_observation_claim_sha256 = _hex_sha256(
        codex_call.get("codex_tool_call_claim_sha256") or ""
    )
    codex_observation_claim_digest_present = bool(
        codex_call.get("codex_tool_call_claim_digest_present") is True
        and codex_observation_claim_sha256
    )
    codex_observation_claim_digest_matched = bool(
        codex_observation_claim_digest_present
        and codex_observation_claim_sha256
        == _codex_exec_tool_call_observation_claim_sha256(codex_call)
    )
    codex_tool_call_observation_packet_ok = bool(
        codex_call.get("status") == "ok"
        and codex_call.get("packet_kind") == CODEX_EXEC_TOOL_CALL_PACKET_KIND
        and codex_call.get("result_status") in {"", "observed"}
        and codex_call.get("final_status") == CODEX_EXEC_TOOL_CALL_FINAL_STATUS_OBSERVED
        and codex_observation_producer_valid
        and codex_observation_claim_digest_matched
        and codex_call.get("codex_exec_json_events_observed") is True
        and codex_call.get("real_codex_prompt_executed") is True
        and codex_observation_sequence_ok
    )
    prompt_to_mcp_call_bound = bool(
        prompt_packet_ok
        and codex_call.get("prompt_to_mcp_call_bound") is True
        and codex_call.get("prompt_sha256") == prompt_sha256
    )
    delegate_to_dip_called = bool(
        codex_call.get("delegate_to_dip_tool_called") is True
        or codex_call.get("codex_delegate_to_dip_tool_called") is True
        or codex_call.get("tool_name") == DELEGATE_TO_DIP_TOOL
    )
    controlled_exec_sequence_proven = bool(
        submit_boundary_packet_ok
        and codex_tool_call_observation_packet_ok
        and submit_boundary_sequence_ok
        and codex_observation_sequence_ok
    )

    control_boundary_packet = build_router_hook_control_boundary_packet(
        prompt_packet=prompt,
        boundary_evidence_packet=submit_boundary,
    )
    source_event_packet = build_router_hook_source_event_packet(
        prompt_packet=prompt,
        codex_tool_call_packet=codex_call,
        control_boundary_packet=control_boundary_packet,
    )
    source_admission_packet = build_router_hook_source_admission_packet(
        prompt_packet=prompt,
        source_event_packet=source_event_packet,
    )

    control_boundary_proven = bool(
        control_boundary_packet.get("status") == "ok"
        and control_boundary_packet.get("packet_kind")
        == ROUTER_HOOK_CONTROL_BOUNDARY_PACKET_KIND
        and control_boundary_packet.get("result_status") in {"", "proven"}
        and control_boundary_packet.get("final_status")
        == ROUTER_HOOK_CONTROL_BOUNDARY_FINAL_STATUS_PROVEN
        and control_boundary_packet.get("control_boundary_status") == "ok"
    )
    source_event_produced = bool(
        source_event_packet.get("status") == "ok"
        and source_event_packet.get("packet_kind") == ROUTER_HOOK_SOURCE_EVENT_PACKET_KIND
        and source_event_packet.get("result_status") in {"", "produced"}
        and source_event_packet.get("final_status")
        == ROUTER_HOOK_SOURCE_EVENT_FINAL_STATUS_PRODUCED
        and source_event_packet.get("source_status") == "ok"
    )
    source_admitted = bool(
        source_admission_packet.get("status") == "ok"
        and source_admission_packet.get("packet_kind")
        == ROUTER_HOOK_SOURCE_ADMISSION_PACKET_KIND
        and source_admission_packet.get("result_status") in {"", "admitted"}
        and source_admission_packet.get("final_status")
        == ROUTER_HOOK_SOURCE_ADMISSION_FINAL_STATUS_ADMITTED
        and source_admission_packet.get("source_status") == "ok"
    )
    source_prompt_digest_bound = bool(
        source_admission_packet.get("source_prompt_digest_bound") is True
        and source_admission_packet.get("source_prompt_sha256") == prompt_sha256
    )

    packets_to_scan = (
        prompt,
        submit_boundary,
        codex_call,
        control_boundary_packet,
        source_event_packet,
        source_admission_packet,
    )
    prompt_supplied_hook_flags = any(
        packet.get("prompt_supplied_hook_flags") is True
        or packet.get("browser_can_supply_prompt_authority") is True
        or packet.get("browser_authority_fields_rejected") is True
        or packet.get("machine_error_code") == CODEX_EXEC_BROWSER_AUTHORITY_REJECTED
        for packet in packets_to_scan
    )
    browser_supplied_hook_flags = any(
        packet.get("browser_supplied_hook_flags") is True
        or packet.get("browser_can_supply_route_authority") is True
        or packet.get("browser_can_supply_model_authority") is True
        for packet in packets_to_scan
    )
    state_written = any(packet.get("state_written") is True for packet in packets_to_scan)
    profile_written = any(
        packet.get("profile_written") is True for packet in packets_to_scan
    )
    config_written = any(packet.get("config_written") is True for packet in packets_to_scan)
    route_registry_written = any(
        packet.get("route_registry_written") is True for packet in packets_to_scan
    )
    credential_written = any(
        packet.get("credential_written") is True for packet in packets_to_scan
    )
    runtime_state_written = any(
        packet.get("runtime_state_written") is True for packet in packets_to_scan
    )
    changed_files_observed = any(
        isinstance(packet.get("changed_files"), list) and bool(packet.get("changed_files"))
        for packet in packets_to_scan
    )
    inadmissible_effect_observed = any(
        _safe_text(
            packet.get("source_effect") or packet.get("effect") or "",
            limit=80,
        )
        not in {"", "probe", "read"}
        for packet in packets_to_scan
    )
    write_side_effect_observed = bool(
        state_written
        or profile_written
        or config_written
        or route_registry_written
        or credential_written
        or runtime_state_written
        or changed_files_observed
        or inadmissible_effect_observed
    )
    raw_prompt_recorded = any(
        packet.get("raw_prompt_recorded") is True
        or packet.get("prompt_text_recorded") is True
        or packet.get("expected_delegate_arguments_recorded") is True
        for packet in packets_to_scan
    )
    raw_jsonl_recorded = any(
        packet.get("raw_jsonl_recorded") is True for packet in packets_to_scan
    )
    tool_call_arguments_recorded = any(
        packet.get("tool_call_arguments_recorded") is True
        for packet in packets_to_scan
    )
    raw_route_id_recorded = any(
        packet.get("raw_route_id_recorded") is True for packet in packets_to_scan
    )
    raw_backend_details_exposed = any(
        packet.get("raw_backend_details_exposed") is True for packet in packets_to_scan
    )
    secret_value_exposed = any(
        packet.get("secret_value_exposed") is True for packet in packets_to_scan
    )
    local_codex_subagent_used_as_dip = any(
        packet.get("local_codex_subagent_used_as_dip") is True
        or packet.get("codex_subagent_used_as_dip") is True
        for packet in packets_to_scan
    )
    local_imitation_used = bool(
        local_codex_subagent_used_as_dip
        or any(packet.get("local_imitation_used") is True for packet in packets_to_scan)
    )
    fallback_used = any(packet.get("fallback_used") is True for packet in packets_to_scan)
    product_ready_claimed = any(
        packet.get("product_ready") is True for packet in packets_to_scan
    )
    native_free_chat_router_claimed = any(
        packet.get("native_free_chat_router_proven") is True
        for packet in packets_to_scan
    )
    api_lane_claimed = any(
        packet.get("api_lane_called") is True for packet in packets_to_scan
    )

    blocking_reasons: list[str] = []
    if not prompt_packet:
        blocking_reasons.append("prompt_observation_packet_missing")
    if prompt_packet_kind != PROMPT_OBSERVATION_PACKET_KIND:
        blocking_reasons.append("prompt_observation_packet_kind_invalid")
    if not prompt_digest_present:
        blocking_reasons.append("prompt_digest_missing")
    if not prompt_packet_ok:
        blocking_reasons.append("prompt_observation_packet_not_ok")
    if not submit_boundary:
        blocking_reasons.append("submit_boundary_probe_missing")
    elif not submit_boundary_packet_ok:
        blocking_reasons.append("submit_boundary_packet_not_ok")
    if submit_boundary and not submit_boundary_sequence_ok:
        blocking_reasons.append("submit_boundary_sequence_invalid")
    if submit_boundary and not submit_boundary_claim_digest_present:
        blocking_reasons.append("submit_boundary_claim_digest_missing")
    elif submit_boundary and not submit_boundary_claim_digest_matched:
        blocking_reasons.append("submit_boundary_claim_digest_mismatch")
    if submit_boundary and not prompt_to_submit_boundary_bound:
        blocking_reasons.append("prompt_not_bound_to_submit_boundary")
    if not codex_call:
        blocking_reasons.append("codex_tool_call_observation_missing")
    elif not codex_tool_call_observation_packet_ok:
        blocking_reasons.append("codex_tool_call_observation_packet_not_ok")
    if codex_call and not codex_observation_sequence_ok:
        blocking_reasons.append("codex_observation_sequence_invalid")
    if codex_call and not codex_observation_producer_valid:
        blocking_reasons.append("codex_tool_call_observation_producer_invalid")
    if codex_call and not codex_observation_claim_digest_present:
        blocking_reasons.append("codex_tool_call_observation_claim_digest_missing")
    elif codex_call and not codex_observation_claim_digest_matched:
        blocking_reasons.append("codex_tool_call_observation_claim_digest_mismatch")
    if not controlled_exec_sequence_proven:
        blocking_reasons.append("controlled_exec_sequence_not_proven")
    if not prompt_to_mcp_call_bound:
        blocking_reasons.append("prompt_not_bound_to_codex_mcp_tool_call")
    if not delegate_to_dip_called:
        blocking_reasons.append("codex_delegate_to_dip_tool_call_not_observed")
    if not control_boundary_proven:
        blocking_reasons.append("router_hook_control_boundary_not_proven")
    if not source_event_produced:
        blocking_reasons.append("router_hook_source_event_not_produced")
    if not source_admitted:
        blocking_reasons.append("router_hook_source_not_admitted")
    if not source_prompt_digest_bound:
        blocking_reasons.append("router_hook_source_prompt_digest_not_bound")
    if prompt_supplied_hook_flags:
        blocking_reasons.append("prompt_supplied_hook_flags")
    if browser_supplied_hook_flags:
        blocking_reasons.append("browser_supplied_hook_flags")
    if write_side_effect_observed:
        blocking_reasons.append("controlled_exec_chain_write_side_effect")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if raw_jsonl_recorded:
        blocking_reasons.append("raw_jsonl_must_not_be_recorded")
    if tool_call_arguments_recorded:
        blocking_reasons.append("tool_call_arguments_must_not_be_recorded")
    if raw_route_id_recorded:
        blocking_reasons.append("raw_route_id_must_not_be_recorded")
    if raw_backend_details_exposed:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if secret_value_exposed:
        blocking_reasons.append("secret_value_must_not_be_exposed")
    if local_codex_subagent_used_as_dip:
        blocking_reasons.append("local_codex_subagent_used_as_dip")
    if local_imitation_used:
        blocking_reasons.append("local_imitation_used")
    if fallback_used:
        blocking_reasons.append("fallback_used")
    if api_lane_claimed:
        blocking_reasons.append("api_lane_call_must_not_be_claimed")
    if native_free_chat_router_claimed:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if product_ready_claimed:
        blocking_reasons.append("product_ready_must_not_be_claimed")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif prompt_supplied_hook_flags or browser_supplied_hook_flags:
        machine_error_code = CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_AUTHORITY_REJECTED
    elif write_side_effect_observed:
        machine_error_code = CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_SIDE_EFFECT_REJECTED
    elif (
        (submit_boundary_producer_valid and not submit_boundary_sequence_ok)
        or (
            codex_call.get("packet_kind") == CODEX_EXEC_TOOL_CALL_PACKET_KIND
            and not codex_observation_sequence_ok
        )
    ):
        machine_error_code = CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_SEQUENCE_INVALID
    elif (
        not prompt_digest_present
        or (submit_boundary and not prompt_to_submit_boundary_bound)
        or (codex_call and delegate_to_dip_called and not prompt_to_mcp_call_bound)
        or (source_admission_packet and not source_prompt_digest_bound)
    ):
        machine_error_code = CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_DIGEST_NOT_BOUND
    else:
        machine_error_code = CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_NOT_PROVEN

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP controlled exec router-hook chain is proven by normalized packets."
            if ok
            else "WBP controlled exec router-hook chain is not proven."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "producer_built_by": "build_controlled_exec_router_hook_chain_packet",
            "chain_status": "ok" if ok else "blocked",
            "prompt_packet_kind": prompt_packet_kind,
            "prompt_packet_ok": prompt_packet_ok,
            "prompt_digest_present": prompt_digest_present,
            "prompt_sha256": prompt_sha256 if prompt_digest_present else "",
            "submit_boundary_packet_kind": _safe_text(
                submit_boundary.get("packet_kind") or "",
                limit=128,
            ),
            "submit_boundary_packet_ok": submit_boundary_packet_ok,
            "submit_boundary_producer_valid": submit_boundary_producer_valid,
            "submit_boundary_sequence": submit_boundary_sequence,
            "submit_boundary_sequence_ok": submit_boundary_sequence_ok,
            "submit_boundary_claim_digest_present": (
                submit_boundary_claim_digest_present
            ),
            "submit_boundary_claim_digest_matched": (
                submit_boundary_claim_digest_matched
            ),
            "prompt_to_submit_boundary_bound": prompt_to_submit_boundary_bound,
            "codex_tool_call_observation_packet_kind": _safe_text(
                codex_call.get("packet_kind") or "",
                limit=128,
            ),
            "codex_tool_call_observation_packet_ok": (
                codex_tool_call_observation_packet_ok
            ),
            "codex_tool_call_observation_producer_valid": (
                codex_observation_producer_valid
            ),
            "codex_tool_call_observation_claim_digest_present": (
                codex_observation_claim_digest_present
            ),
            "codex_tool_call_observation_claim_digest_matched": (
                codex_observation_claim_digest_matched
            ),
            "codex_observation_sequence": codex_observation_sequence,
            "codex_observation_sequence_ok": codex_observation_sequence_ok,
            "controlled_exec_sequence_proven": controlled_exec_sequence_proven,
            "real_codex_prompt_executed": (
                codex_call.get("real_codex_prompt_executed") is True
            ),
            "delegate_to_dip_called": delegate_to_dip_called,
            "codex_delegate_to_dip_tool_called": delegate_to_dip_called,
            "prompt_to_mcp_call_bound": prompt_to_mcp_call_bound,
            "control_boundary_packet_kind": _safe_text(
                control_boundary_packet.get("packet_kind") or "",
                limit=128,
            ),
            "control_boundary_proven": control_boundary_proven,
            "source_event_packet_kind": _safe_text(
                source_event_packet.get("packet_kind") or "",
                limit=128,
            ),
            "source_event_produced": source_event_produced,
            "source_packet_kind": _safe_text(
                source_admission_packet.get("packet_kind") or "",
                limit=128,
            ),
            "source_admitted": source_admitted,
            "source_prompt_digest_bound": source_prompt_digest_bound,
            "prompt_supplied_hook_flags": prompt_supplied_hook_flags,
            "browser_supplied_hook_flags": browser_supplied_hook_flags,
            "state_written": state_written,
            "profile_written": profile_written,
            "config_written": config_written,
            "route_registry_written": route_registry_written,
            "credential_written": credential_written,
            "runtime_state_written": runtime_state_written,
            "write_side_effect_observed": write_side_effect_observed,
            "raw_prompt_recorded": raw_prompt_recorded,
            "raw_jsonl_recorded": raw_jsonl_recorded,
            "tool_call_arguments_recorded": tool_call_arguments_recorded,
            "raw_route_id_recorded": raw_route_id_recorded,
            "raw_backend_details_exposed": raw_backend_details_exposed,
            "secret_value_exposed": secret_value_exposed,
            "local_codex_subagent_used_as_dip": local_codex_subagent_used_as_dip,
            "local_imitation_used": local_imitation_used,
            "fallback_used": fallback_used,
            "api_lane_called": False,
            "does_not_prove_api_lane_provider_dispatch": True,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_product_ready_free_chat": True,
            "no_secret_exposed": not secret_value_exposed,
        },
        packet_kind=CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_PACKET_KIND,
        final_status=(
            CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_FINAL_STATUS_PROVEN
            if ok
            else CONTROLLED_EXEC_ROUTER_HOOK_CHAIN_FINAL_STATUS_BLOCKED
        ),
        result_status="proven" if ok else "blocked",
    )


def build_native_router_hook_observation_packet(
    *,
    config_packet: Mapping[str, Any] | None = None,
    prompt_packet: Mapping[str, Any] | None = None,
    codex_tool_call_packet: Mapping[str, Any] | None = None,
    delegate_packet: Mapping[str, Any] | None = None,
    hook_packet: Mapping[str, Any] | None = None,
    hook_source_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(config_packet) if isinstance(config_packet, Mapping) else {}
    prompt = dict(prompt_packet) if isinstance(prompt_packet, Mapping) else {}
    codex_call = (
        dict(codex_tool_call_packet)
        if isinstance(codex_tool_call_packet, Mapping)
        else {}
    )
    delegate = dict(delegate_packet) if isinstance(delegate_packet, Mapping) else {}
    hook = dict(hook_packet) if isinstance(hook_packet, Mapping) else {}
    hook_source = (
        dict(hook_source_packet)
        if isinstance(hook_source_packet, Mapping)
        else {}
    )

    codex_mcp_config_loaded = bool(
        config.get("config_loaded") is True
        or config.get("codex_mcp_config_loaded") is True
    )
    prompt_sha256 = _hex_sha256(prompt.get("prompt_sha256") or "")
    expected_call_sha256 = _hex_sha256(
        prompt.get("expected_delegate_tool_call_sha256") or ""
    )
    prompt_digest_present = bool(
        prompt.get("prompt_digest_present") is True and prompt_sha256
    )
    expected_call_digest_present = bool(
        prompt.get("expected_delegate_tool_call_digest_present") is True
        and expected_call_sha256
    )
    codex_tool_call_observation_ok = bool(
        codex_call.get("status") == "ok"
        and codex_call.get("packet_kind") == CODEX_EXEC_TOOL_CALL_PACKET_KIND
        and codex_call.get("result_status") in {"", "observed"}
    )
    delegate_packet_ok = bool(
        delegate.get("status") == "ok" and delegate.get("packet_kind") == DELEGATE_PACKET_KIND
    )
    codex_call_sha256 = _hex_sha256(codex_call.get("tool_call_sha256") or "")
    delegate_call_sha256 = _hex_sha256(delegate.get("tool_call_sha256") or "")
    delegate_to_dip_called = bool(
        codex_call.get("delegate_to_dip_tool_called") is True
        or codex_call.get("tool_name") == DELEGATE_TO_DIP_TOOL
    )
    wbp_owned_surface_called = bool(
        codex_tool_call_observation_ok and delegate_to_dip_called
    )
    hook_source_admitted = bool(
        hook_source.get("status") == "ok"
        and hook_source.get("packet_kind") == ROUTER_HOOK_SOURCE_ADMISSION_PACKET_KIND
        and hook_source.get("result_status") in {"", "admitted"}
        and hook_source.get("source_status") == "ok"
    )
    source_wbp_owned = hook_source.get("source_wbp_owned") is True
    source_effect = _safe_text(hook_source.get("source_effect") or "", limit=80)
    source_run_digest_present = hook_source.get("source_run_digest_present") is True
    source_prompt_digest_present = (
        hook_source.get("source_prompt_digest_present") is True
    )
    source_prompt_digest_bound = bool(
        hook_source.get("source_prompt_digest_bound") is True
        and hook_source.get("source_prompt_sha256") == prompt_sha256
        and prompt_digest_present
    )
    hook_observed_prompt = bool(
        hook_source_admitted
        and (
            hook_source.get("hook_observed_prompt") is True
            or hook_source.get("prompt_observed") is True
        )
    )
    hook_can_enforce_router = bool(
        hook_source_admitted
        and hook_source.get("hook_can_enforce_router") is True
    )
    hook_can_route_delegate_to_dip = bool(
        hook_source_admitted
        and hook_source.get("hook_can_route_delegate_to_dip") is True
    )
    explicit_router_hook_evidence = bool(
        hook_source_admitted
        and hook_observed_prompt
        and hook_can_enforce_router
        and hook_can_route_delegate_to_dip
    )
    prompt_digest_bound = bool(
        codex_call.get("prompt_to_mcp_call_bound") is True
        and codex_call.get("prompt_sha256") == prompt_sha256
        and prompt_digest_present
    )
    tool_call_digest_bound = bool(
        expected_call_digest_present
        and codex_call_sha256 == expected_call_sha256
        and delegate_call_sha256 == expected_call_sha256
    )
    alias_context_read = delegate.get("alias_context_read") is True
    route_authority_enforced = bool(
        delegate.get("allowed_api_route_ids_enforced") is True
        and delegate.get("route_allowed") is True
        and delegate.get("selected_api_route_id_recorded") is False
    )
    forbidden_stale_route_ids_enforced = (
        delegate.get("forbidden_stale_route_ids_enforced") is True
    )
    local_codex_subagent_used = bool(
        codex_call.get("local_codex_subagent_used_as_dip") is True
        or codex_call.get("codex_subagent_used_as_dip") is True
        or hook.get("local_codex_subagent_used_as_dip") is True
        or hook.get("native_codex_subagent_used_as_dip") is True
        or hook_source.get("local_codex_subagent_used_as_dip") is True
        or hook_source.get("native_codex_subagent_used_as_dip") is True
    )
    local_imitation_used = bool(
        local_codex_subagent_used
        or codex_call.get("local_imitation_used") is True
        or delegate.get("local_imitation_used") is True
        or hook.get("local_imitation_used") is True
        or hook_source.get("local_imitation_used") is True
    )
    fallback_used = bool(
        codex_call.get("fallback_used") is True
        or delegate.get("fallback_used") is True
        or hook.get("fallback_used") is True
        or hook_source.get("fallback_used") is True
    )
    prompt_supplied_hook_flags = hook_source.get("prompt_supplied_hook_flags") is True
    browser_supplied_hook_flags = hook_source.get("browser_supplied_hook_flags") is True
    browser_authority_rejected = bool(
        codex_call.get("browser_authority_fields_rejected") is True
        or delegate.get("machine_error_code")
        == "WBP_MCP_DELEGATE_BROWSER_AUTHORITY_REJECTED"
        or hook_source.get("machine_error_code") == ROUTER_HOOK_SOURCE_AUTHORITY_REJECTED
        or any(
            str(reason).startswith("forbidden_field:")
            for reason in delegate.get("blocking_reasons", [])
        )
    )
    browser_can_supply_route_authority = bool(
        delegate.get("browser_can_supply_route_authority") is True
        or hook.get("browser_can_supply_route_authority") is True
        or browser_supplied_hook_flags
    )
    browser_can_supply_model_authority = bool(
        delegate.get("browser_can_supply_model_authority") is True
        or hook.get("browser_can_supply_model_authority") is True
        or browser_supplied_hook_flags
    )
    manual_hook_packet_used = bool(
        hook
        or hook_source.get("manual_hook_packet_used") is True
    )
    synthetic_hook_packet_used = (
        hook_source.get("synthetic_hook_packet_used") is True
    )
    raw_backend_details_exposed = bool(
        codex_call.get("raw_backend_details_exposed") is True
        or delegate.get("raw_backend_details_exposed") is True
        or hook.get("raw_backend_details_exposed") is True
        or hook_source.get("raw_backend_details_exposed") is True
    )
    secret_value_exposed = bool(
        codex_call.get("secret_value_exposed") is True
        or delegate.get("secret_value_exposed") is True
        or hook.get("secret_value_exposed") is True
        or hook_source.get("secret_value_exposed") is True
    )
    raw_prompt_recorded = bool(
        codex_call.get("raw_prompt_recorded") is True
        or delegate.get("raw_prompt_recorded") is True
        or prompt.get("raw_prompt_recorded") is True
        or hook_source.get("raw_prompt_recorded") is True
    )
    raw_route_id_recorded = hook_source.get("raw_route_id_recorded") is True
    raw_provider_response_recorded = bool(
        codex_call.get("raw_provider_response_recorded") is True
        or delegate.get("raw_provider_response_recorded") is True
    )
    native_free_chat_router_claimed = bool(
        codex_call.get("native_free_chat_router_proven") is True
        or delegate.get("native_free_chat_router_proven") is True
        or hook.get("native_free_chat_router_proven") is True
        or hook_source.get("native_free_chat_router_proven") is True
    )
    product_ready_claimed = bool(
        codex_call.get("product_ready") is True
        or delegate.get("product_ready") is True
        or hook.get("product_ready") is True
        or hook_source.get("product_ready") is True
    )

    blocking_reasons: list[str] = []
    if not codex_mcp_config_loaded:
        blocking_reasons.append("codex_mcp_config_not_loaded")
    if not prompt_digest_present:
        blocking_reasons.append("prompt_digest_missing")
    if not expected_call_digest_present:
        blocking_reasons.append("expected_delegate_tool_call_digest_missing")
    if not codex_call:
        blocking_reasons.append("codex_tool_call_observation_missing")
    elif not codex_tool_call_observation_ok:
        blocking_reasons.append("codex_tool_call_observation_packet_not_ok")
    if not wbp_owned_surface_called:
        blocking_reasons.append("router_hook_not_observed")
    if not hook_source:
        blocking_reasons.append("router_hook_source_packet_missing")
    elif not hook_source_admitted:
        blocking_reasons.append("router_hook_source_packet_not_admitted")
    if not source_wbp_owned:
        blocking_reasons.append("router_hook_source_not_wbp_owned")
    if source_effect not in {"probe", "read"}:
        blocking_reasons.append("router_hook_source_effect_not_admitted")
    if not source_run_digest_present:
        blocking_reasons.append("router_hook_source_run_digest_missing")
    if not source_prompt_digest_present:
        blocking_reasons.append("router_hook_source_prompt_digest_missing")
    if not source_prompt_digest_bound:
        blocking_reasons.append("router_hook_source_prompt_digest_not_bound")
    if not hook_observed_prompt:
        blocking_reasons.append("hook_prompt_not_observed")
    if not hook_can_enforce_router:
        blocking_reasons.append("hook_cannot_enforce_router")
    if not hook_can_route_delegate_to_dip:
        blocking_reasons.append("hook_cannot_route_delegate_to_dip")
    if manual_hook_packet_used:
        blocking_reasons.append("manual_hook_packet_not_admitted")
    if synthetic_hook_packet_used:
        blocking_reasons.append("synthetic_hook_packet_not_admitted")
    if prompt_supplied_hook_flags:
        blocking_reasons.append("prompt_supplied_hook_flags")
    if browser_supplied_hook_flags:
        blocking_reasons.append("browser_supplied_hook_flags")
    if not prompt_digest_bound:
        blocking_reasons.append("prompt_digest_not_bound_to_router_hook")
    if not tool_call_digest_bound:
        blocking_reasons.append("tool_call_digest_not_bound_to_delegate_packet")
    if not delegate:
        blocking_reasons.append("delegate_packet_missing")
    elif not delegate_packet_ok:
        blocking_reasons.append("delegate_packet_not_ok")
    if not alias_context_read:
        blocking_reasons.append("alias_context_not_read")
    if not route_authority_enforced:
        blocking_reasons.append("route_authority_not_enforced")
    if not forbidden_stale_route_ids_enforced:
        blocking_reasons.append("stale_route_guard_missing")
    if browser_authority_rejected:
        blocking_reasons.append("browser_authority_rejected")
    if browser_can_supply_route_authority:
        blocking_reasons.append("browser_route_authority_allowed")
    if browser_can_supply_model_authority:
        blocking_reasons.append("browser_model_authority_allowed")
    if local_codex_subagent_used:
        blocking_reasons.append("local_codex_subagent_used_as_dip")
    if local_imitation_used:
        blocking_reasons.append("local_imitation_used")
    if fallback_used:
        blocking_reasons.append("fallback_used")
    if native_free_chat_router_claimed:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if product_ready_claimed:
        blocking_reasons.append("product_ready_must_not_be_claimed")
    if raw_prompt_recorded:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if raw_route_id_recorded:
        blocking_reasons.append("raw_route_id_must_not_be_recorded")
    if raw_provider_response_recorded:
        blocking_reasons.append("raw_provider_response_must_not_be_recorded")
    if raw_backend_details_exposed:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if secret_value_exposed:
        blocking_reasons.append("secret_value_must_not_be_exposed")

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif (
        browser_authority_rejected
        or browser_can_supply_route_authority
        or browser_can_supply_model_authority
    ):
        machine_error_code = ROUTER_HOOK_BROWSER_AUTHORITY_REJECTED
    elif local_codex_subagent_used or local_imitation_used:
        machine_error_code = ROUTER_HOOK_CODEX_SUBAGENT_USED
    elif delegate.get("machine_error_code") == "FAIL_ALIAS_CONTEXT_MISSING":
        machine_error_code = "FAIL_ALIAS_CONTEXT_MISSING"
    else:
        machine_error_code = ROUTER_HOOK_NOT_OBSERVED

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "Native Codex router hook observation found a prompt-bound WBP-owned tool call."
            if ok
            else "Native Codex router hook observation did not prove a WBP-owned route."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "router_hook_observed": ok,
            "native_router_hook_observed": ok,
            "explicit_router_hook_evidence": explicit_router_hook_evidence,
            "source_packet_kind": str(hook_source.get("packet_kind") or ""),
            "source_status": str(hook_source.get("source_status") or ""),
            "source_wbp_owned": source_wbp_owned,
            "source_effect": source_effect,
            "source_run_digest_present": source_run_digest_present,
            "source_prompt_digest_present": source_prompt_digest_present,
            "source_prompt_digest_bound": source_prompt_digest_bound,
            "manual_hook_packet_used": manual_hook_packet_used,
            "synthetic_hook_packet_used": synthetic_hook_packet_used,
            "prompt_supplied_hook_flags": prompt_supplied_hook_flags,
            "browser_supplied_hook_flags": browser_supplied_hook_flags,
            "wbp_owned_surface_called": wbp_owned_surface_called,
            "wbp_owned_surface_kind": (
                "mcp_tool_call:delegate_to_dip" if wbp_owned_surface_called else ""
            ),
            "delegate_to_dip_called": delegate_to_dip_called,
            "codex_mcp_config_loaded": codex_mcp_config_loaded,
            "codex_tool_call_observation_packet_ok": codex_tool_call_observation_ok,
            "real_codex_prompt_executed": (
                codex_call.get("real_codex_prompt_executed") is True
            ),
            "prompt_digest_present": prompt_digest_present,
            "prompt_digest_bound": prompt_digest_bound,
            "prompt_to_mcp_call_bound": prompt_digest_bound,
            "tool_call_digest_bound": tool_call_digest_bound,
            "tool_call_sha256": codex_call_sha256 if tool_call_digest_bound else "",
            "delegate_packet_status": str(delegate.get("status") or ""),
            "delegate_packet_machine_error_code": str(
                delegate.get("machine_error_code") or ""
            ),
            "alias_context_read": alias_context_read,
            "runtime_context_file_proven": (
                delegate.get("runtime_context_file_proven") is True
            ),
            "custom_codex_agent_runtime_context_proven": (
                delegate.get("custom_codex_agent_runtime_context_proven") is True
            ),
            "expected_alias": str(delegate.get("expected_alias") or ""),
            "selected_alias": str(delegate.get("selected_alias") or ""),
            "selected_alias_lane": str(delegate.get("selected_alias_lane") or ""),
            "coding_alias_bound_to_api_lane": (
                delegate.get("coding_alias_bound_to_api_lane") is True
            ),
            "allowed_api_route_ids_enforced": (
                delegate.get("allowed_api_route_ids_enforced") is True
            ),
            "forbidden_stale_route_ids_enforced": forbidden_stale_route_ids_enforced,
            "route_allowed": delegate.get("route_allowed") is True,
            "selected_api_route_id_present": (
                delegate.get("selected_api_route_id_present") is True
            ),
            "selected_api_route_id_sha256": str(
                delegate.get("selected_api_route_id_sha256") or ""
            ),
            "selected_api_route_id_recorded": (
                delegate.get("selected_api_route_id_recorded") is True
            ),
            "route_bound_dispatch_proven": (
                delegate.get("route_bound_dispatch_proven") is True
            ),
            "controlled_provider_response_proven": (
                delegate.get("controlled_provider_response_proven") is True
            ),
            "lower_layer_delegate_packet_used": bool(delegate),
            "hook_observed_prompt": hook_observed_prompt,
            "hook_can_enforce_router": hook_can_enforce_router,
            "hook_can_route_delegate_to_dip": hook_can_route_delegate_to_dip,
            "local_codex_subagent_used": local_codex_subagent_used,
            "local_codex_subagent_used_as_dip": local_codex_subagent_used,
            "codex_subagent_used_as_dip": local_codex_subagent_used,
            "local_imitation_used": local_imitation_used,
            "fallback_used": fallback_used,
            "browser_authority_rejected": browser_authority_rejected,
            "browser_can_supply_prompt_authority": False,
            "browser_can_supply_route_authority": browser_can_supply_route_authority,
            "browser_can_supply_model_authority": browser_can_supply_model_authority,
            "secret_value_exposed": secret_value_exposed,
            "raw_backend_details_exposed": raw_backend_details_exposed,
            "raw_prompt_recorded": raw_prompt_recorded,
            "raw_route_id_recorded": raw_route_id_recorded,
            "prompt_text_recorded": False,
            "raw_transcript_recorded": False,
            "raw_provider_response_recorded": raw_provider_response_recorded,
            "tool_call_arguments_recorded": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_product_ready_free_chat": True,
            "no_secret_exposed": not secret_value_exposed,
        },
        packet_kind=ROUTER_HOOK_OBSERVATION_PACKET_KIND,
        final_status=(
            ROUTER_HOOK_OBSERVATION_FINAL_STATUS_OBSERVED
            if ok
            else ROUTER_HOOK_OBSERVATION_FINAL_STATUS_BLOCKED
        ),
        result_status="observed" if ok else "blocked",
    )


def build_delegate_to_dip_packet(
    arguments: Mapping[str, Any] | None,
    *,
    env: Mapping[str, str] | None = None,
    mcp_tool_called: bool = False,
    api_lane_adapter_available: bool = True,
    controlled_provider_available: bool = True,
    controlled_provider_error_code: str = "",
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
    selected_alias_lane = _safe_text(alias_binding.get("lane") or "", limit=32)

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
        and selected_alias_lane == API_ROUTE_LANE
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
    if binding_valid and not route_id:
        blocking_reasons.append("coding_route_id_missing")
    if binding_valid and route_id and not route_allowed:
        blocking_reasons.append("coding_route_not_allowed")
    if binding_valid and not stale_route_guard_present:
        blocking_reasons.append("stale_route_guard_missing")

    api_lane_adapter_packet: dict[str, Any] = {}
    route_bound_dispatch_packet: dict[str, Any] = {}
    if not blocking_reasons:
        api_lane_adapter_packet = build_api_lane_adapter_admission_packet(
            task=task,
            selected_alias=selected_alias,
            selected_alias_lane=selected_alias_lane,
            route_id=route_id,
            allowed_api_route_ids_enforced=bool(allowed_api_route_ids),
            route_allowed=route_allowed,
            adapter_available=api_lane_adapter_available,
        )
        if api_lane_adapter_packet.get("status") != "ok":
            adapter_reasons = [
                str(reason)
                for reason in api_lane_adapter_packet.get("blocking_reasons", [])
            ]
            blocking_reasons.extend(adapter_reasons or ["api_lane_dispatch_not_admitted"])
    if not blocking_reasons:
        route_bound_dispatch_packet = build_route_bound_controlled_dispatch_packet(
            task=task,
            selected_alias=selected_alias,
            selected_alias_lane=selected_alias_lane,
            route_id=route_id,
            admission_packet=api_lane_adapter_packet,
            controlled_provider_available=controlled_provider_available,
            controlled_provider_error_code=controlled_provider_error_code,
        )
        if route_bound_dispatch_packet.get("status") != "ok":
            dispatch_reasons = [
                str(reason)
                for reason in route_bound_dispatch_packet.get("blocking_reasons", [])
            ]
            blocking_reasons.extend(
                dispatch_reasons or ["route_bound_dispatch_not_proven"]
            )

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif forbidden_fields:
        machine_error_code = "WBP_MCP_DELEGATE_BROWSER_AUTHORITY_REJECTED"
    elif not metadata.get("alias_context_read"):
        machine_error_code = str(
            metadata.get("machine_error_code") or "FAIL_ALIAS_CONTEXT_MISSING"
        )
    elif route_bound_dispatch_packet.get("machine_error_code"):
        machine_error_code = str(route_bound_dispatch_packet["machine_error_code"])
    elif (
        api_lane_adapter_packet.get("machine_error_code")
        and api_lane_adapter_packet.get("machine_error_code") != "OK"
    ):
        machine_error_code = str(api_lane_adapter_packet["machine_error_code"])
    else:
        machine_error_code = "WBP_MCP_DELEGATE_TO_DIP_NOT_PROVEN"
    api_lane_adapter_called = api_lane_adapter_packet.get("api_lane_adapter_called") is True
    api_lane_dispatch_admitted = (
        api_lane_adapter_packet.get("api_lane_dispatch_admitted") is True
    )
    route_bound_dispatch_attempted = (
        route_bound_dispatch_packet.get("route_bound_dispatch_attempted") is True
    )
    route_bound_dispatch_proven = (
        route_bound_dispatch_packet.get("route_bound_dispatch_proven") is True
    )
    controlled_provider_called = (
        route_bound_dispatch_packet.get("controlled_provider_called") is True
    )
    controlled_provider_response_proven = (
        route_bound_dispatch_packet.get("controlled_provider_response_proven") is True
    )
    selected_api_route_id_present = bool(route_id)
    return _command_packet(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP MCP delegate_to_dip tool call proved route-bound controlled API-lane dispatch."
            if ok
            else (
                "WBP MCP delegate_to_dip tool call did not prove route-bound "
                "controlled API-lane dispatch."
            )
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
            "selected_alias_lane": selected_alias_lane,
            "expected_alias": expected_alias,
            "coding_aliases": coding_aliases,
            "coding_alias_bound_to_api_lane": binding_valid,
            "allowed_api_route_ids_enforced": bool(allowed_api_route_ids),
            "allowed_api_route_ids_count": len(allowed_api_route_ids),
            "selected_api_route_id_present": selected_api_route_id_present,
            "selected_api_route_id_sha256": (
                _sha256_text(route_id) if selected_api_route_id_present else ""
            ),
            "selected_api_route_id_recorded": False,
            "route_allowed": route_allowed,
            "forbidden_stale_route_ids_enforced": bool(
                stale_route_guard_present and route_id not in forbidden_stale_route_ids
            ),
            "api_lane_adapter_called": api_lane_adapter_called,
            "api_lane_dispatch_admitted": api_lane_dispatch_admitted,
            "api_lane_adapter_packet_kind": str(
                api_lane_adapter_packet.get("packet_kind") or ""
            ),
            "api_lane_adapter_result_status": str(
                api_lane_adapter_packet.get("result_status") or ""
            ),
            "api_lane_adapter_machine_error_code": str(
                api_lane_adapter_packet.get("machine_error_code") or ""
            ),
            "route_bound_dispatch_packet_kind": str(
                route_bound_dispatch_packet.get("packet_kind") or ""
            ),
            "route_bound_dispatch_result_status": str(
                route_bound_dispatch_packet.get("result_status") or ""
            ),
            "route_bound_dispatch_machine_error_code": str(
                route_bound_dispatch_packet.get("machine_error_code") or ""
            ),
            "route_bound_dispatch_attempted": route_bound_dispatch_attempted,
            "route_bound_dispatch_proven": route_bound_dispatch_proven,
            "route_bound_request_sent": (
                route_bound_dispatch_packet.get("route_bound_request_sent") is True
            ),
            "route_bound_request_sha256": str(
                route_bound_dispatch_packet.get("route_bound_request_sha256") or ""
            ),
            "dispatch_truth_source": str(
                route_bound_dispatch_packet.get("dispatch_truth_source") or "not_proven"
            ),
            "controlled_provider_called": controlled_provider_called,
            "controlled_provider_available": (
                route_bound_dispatch_packet.get("controlled_provider_available") is True
            ),
            "controlled_provider_error_observed": (
                route_bound_dispatch_packet.get("controlled_provider_error_observed")
                is True
            ),
            "controlled_provider_error_code_recorded": (
                route_bound_dispatch_packet.get(
                    "controlled_provider_error_code_recorded"
                )
                is True
            ),
            "controlled_provider_response_digest_present": (
                route_bound_dispatch_packet.get(
                    "controlled_provider_response_digest_present"
                )
                is True
            ),
            "controlled_provider_response_sha256": str(
                route_bound_dispatch_packet.get(
                    "controlled_provider_response_sha256"
                )
                or ""
            ),
            "controlled_provider_response_proven": (
                controlled_provider_response_proven
            ),
            "api_lane_called": api_lane_dispatch_admitted,
            "api_lane_provider_called": controlled_provider_called,
            "provider_response_proven": controlled_provider_response_proven,
            "live_provider_response_proven": False,
            "bounded_api_lane_mock_used": False,
            "api_lane_truth_source": (
                "server_owned_controlled_route_bound_dispatch"
                if route_bound_dispatch_proven
                else "not_proven"
            ),
            "fallback_used": False,
            "local_imitation_used": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "universal_manual_chat_interception_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_universal_manual_chat_interception": True,
            "does_not_prove_api_lane_provider_dispatch": (
                not route_bound_dispatch_proven
            ),
            "does_not_prove_live_provider_dispatch": True,
            "browser_authority_contract_enforced": True,
            "browser_can_supply_prompt_authority": False,
            "browser_can_supply_route_authority": False,
            "browser_can_supply_model_authority": False,
            "raw_provider_response_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
    )


def _route_bound_delegate_evidence_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("packet_kind") != DELEGATE_PACKET_KIND:
        failures.append("delegate_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("delegate_packet_not_ok")
    if packet.get("alias_context_read") is not True:
        failures.append("alias_context_not_read")
    if packet.get("allowed_api_route_ids_enforced") is not True:
        failures.append("allowed_api_route_ids_not_enforced")
    if packet.get("forbidden_stale_route_ids_enforced") is not True:
        failures.append("stale_route_guard_missing")
    if packet.get("route_allowed") is not True:
        failures.append("selected_api_route_not_allowed")
    if packet.get("route_bound_dispatch_packet_kind") != ROUTE_BOUND_DISPATCH_PACKET_KIND:
        failures.append("route_bound_dispatch_packet_kind_invalid")
    if packet.get("route_bound_dispatch_proven") is not True:
        failures.append("route_bound_dispatch_not_proven")
    if packet.get("route_bound_request_sent") is not True:
        failures.append("route_bound_request_not_sent")
    if not _hex_sha256(packet.get("route_bound_request_sha256") or ""):
        failures.append("route_bound_request_digest_missing")
    if (
        packet.get("dispatch_truth_source")
        != "server_owned_controlled_provider_no_live_network"
    ):
        failures.append("dispatch_truth_source_invalid")
    if packet.get("controlled_provider_called") is not True:
        failures.append("controlled_provider_not_called")
    if packet.get("controlled_provider_response_digest_present") is not True:
        failures.append("controlled_provider_response_digest_missing")
    if not _hex_sha256(packet.get("controlled_provider_response_sha256") or ""):
        failures.append("controlled_provider_response_digest_invalid")
    if packet.get("controlled_provider_response_proven") is not True:
        failures.append("controlled_provider_response_not_proven")
    if packet.get("provider_response_proven") is not True:
        failures.append("provider_response_not_proven")
    if packet.get("live_provider_response_proven") is not False:
        failures.append("live_provider_response_already_claimed")
    if packet.get("selected_api_route_id_present") is not True:
        failures.append("selected_api_route_id_missing")
    if not _hex_sha256(packet.get("selected_api_route_id_sha256") or ""):
        failures.append("selected_api_route_digest_missing")
    if packet.get("selected_api_route_id_recorded") is not False:
        failures.append("selected_api_route_id_must_not_be_recorded")
    if packet.get("fallback_used") is not False:
        failures.append("fallback_used")
    if packet.get("local_imitation_used") is not False:
        failures.append("local_imitation_used")
    if packet.get("product_ready") is not False:
        failures.append("product_ready_must_not_be_claimed")
    if packet.get("raw_provider_response_recorded") is not False:
        failures.append("raw_provider_response_must_not_be_recorded")
    if packet.get("raw_backend_details_exposed") is not False:
        failures.append("raw_backend_details_must_not_be_exposed")
    if packet.get("secret_value_exposed") is not False:
        failures.append("secret_value_must_not_be_exposed")
    return failures


def build_live_route_bound_api_smoke_packet(
    arguments: Mapping[str, Any] | None,
    *,
    env: Mapping[str, str] | None = None,
    live_credential_present: bool = True,
    live_transport_available: bool = True,
    live_provider_error_code: str = "",
    route_bound_dispatch_evidence_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    args = arguments if isinstance(arguments, Mapping) else {}
    expected_alias = _safe_text(
        args.get("expected_alias") or args.get("alias") or "",
        limit=80,
    )
    forbidden_fields = sorted(
        _safe_text(field, limit=80)
        for field in set(args) - {"task", "expected_alias", "alias"}
    )
    safe_provider_error_code = _safe_text(live_provider_error_code, limit=96)
    delegate_packet: dict[str, Any] = {}
    if not forbidden_fields:
        if isinstance(route_bound_dispatch_evidence_packet, Mapping):
            delegate_packet = dict(route_bound_dispatch_evidence_packet)
        else:
            delegate_packet = build_delegate_to_dip_packet(
                args,
                env=env,
                mcp_tool_called=True,
            )

    evidence_failures = (
        _route_bound_delegate_evidence_failures(delegate_packet)
        if delegate_packet
        else ["delegate_packet_missing"]
    )
    controlled_dispatch_proven = not evidence_failures
    selected_route_sha256 = _hex_sha256(
        delegate_packet.get("selected_api_route_id_sha256") or ""
    )
    route_bound_request_sha256 = _hex_sha256(
        delegate_packet.get("route_bound_request_sha256") or ""
    )

    blocking_reasons: list[str] = []
    if forbidden_fields:
        blocking_reasons.extend(f"forbidden_field:{field}" for field in forbidden_fields)
    elif not controlled_dispatch_proven:
        delegate_blocking_reasons = [
            _safe_text(reason, limit=128)
            for reason in delegate_packet.get("blocking_reasons", [])
        ]
        blocking_reasons.extend(delegate_blocking_reasons or evidence_failures)

    if controlled_dispatch_proven and not live_credential_present:
        blocking_reasons.append("live_provider_credential_missing")
    if controlled_dispatch_proven and live_credential_present and not live_transport_available:
        blocking_reasons.append("live_provider_transport_unavailable")
    live_provider_error_observed = bool(
        controlled_dispatch_proven
        and live_credential_present
        and live_transport_available
        and safe_provider_error_code
    )
    if live_provider_error_observed:
        blocking_reasons.append("live_provider_error")

    live_provider_smoke_attempted = bool(
        controlled_dispatch_proven
        and live_credential_present
        and live_transport_available
    )
    live_request_fingerprint = json.dumps(
        {
            "delegate_tool_call_sha256": str(delegate_packet.get("tool_call_sha256") or ""),
            "route_bound_request_sha256": route_bound_request_sha256,
            "route_id_sha256": selected_route_sha256,
            "task_sha256": str(delegate_packet.get("task_sha256") or ""),
            "transport": "fake_live_smoke_transport",
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    live_request_sha256 = (
        _sha256_text(live_request_fingerprint) if live_provider_smoke_attempted else ""
    )
    fake_transport_response_fingerprint = json.dumps(
        {
            "smoke_request_sha256": live_request_sha256,
            "route_id_sha256": selected_route_sha256,
            "transport_response": "fake_route_bound_smoke_response",
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )

    ok = not blocking_reasons
    if ok:
        machine_error_code = "OK"
    elif forbidden_fields:
        machine_error_code = LIVE_ROUTE_BROWSER_AUTHORITY_REJECTED
    elif "FAIL_ALIAS_CONTEXT_MISSING" in blocking_reasons:
        machine_error_code = "FAIL_ALIAS_CONTEXT_MISSING"
    elif "live_provider_credential_missing" in blocking_reasons:
        machine_error_code = LIVE_PROVIDER_CREDENTIAL_MISSING
    elif "live_provider_transport_unavailable" in blocking_reasons:
        machine_error_code = LIVE_PROVIDER_TRANSPORT_UNAVAILABLE
    elif "live_provider_error" in blocking_reasons:
        machine_error_code = LIVE_PROVIDER_ERROR
    else:
        machine_error_code = LIVE_ROUTE_SMOKE_NOT_PROVEN

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP live route-bound API smoke admission accepted the fake transport contract."
            if ok
            else "WBP live route-bound API smoke admission is blocked."
        ),
        blocking_reasons=blocking_reasons,
        extra={
            "live_smoke_boundary": "explicit_wbp_owned_route_bound_api_smoke",
            "live_smoke_contract_proven": ok,
            "delegate_packet_kind": str(delegate_packet.get("packet_kind") or ""),
            "delegate_packet_status": str(delegate_packet.get("status") or ""),
            "delegate_packet_machine_error_code": str(
                delegate_packet.get("machine_error_code") or ""
            ),
            "controlled_dispatch_evidence_proven": controlled_dispatch_proven,
            "route_bound_dispatch_packet_kind": str(
                delegate_packet.get("route_bound_dispatch_packet_kind") or ""
            ),
            "route_bound_dispatch_proven": (
                delegate_packet.get("route_bound_dispatch_proven") is True
            ),
            "route_bound_request_sent": (
                delegate_packet.get("route_bound_request_sent") is True
            ),
            "route_bound_request_sha256": route_bound_request_sha256,
            "controlled_provider_response_proven": (
                delegate_packet.get("controlled_provider_response_proven") is True
            ),
            "selected_alias": str(delegate_packet.get("selected_alias") or expected_alias),
            "selected_alias_lane": str(delegate_packet.get("selected_alias_lane") or ""),
            "alias_context_read": delegate_packet.get("alias_context_read") is True,
            "allowed_api_route_ids_enforced": (
                delegate_packet.get("allowed_api_route_ids_enforced") is True
            ),
            "forbidden_stale_route_ids_enforced": (
                delegate_packet.get("forbidden_stale_route_ids_enforced") is True
            ),
            "route_allowed": delegate_packet.get("route_allowed") is True,
            "selected_api_route_id_present": bool(selected_route_sha256),
            "selected_api_route_id_sha256": selected_route_sha256,
            "selected_api_route_id_recorded": False,
            "task_digest_preserved": delegate_packet.get("task_digest_preserved") is True,
            "task_sha256": str(delegate_packet.get("task_sha256") or ""),
            "raw_prompt_recorded": False,
            "prompt_text_recorded": False,
            "live_credential_present": bool(live_credential_present),
            "live_credential_value_recorded": False,
            "live_transport_available": bool(live_transport_available),
            "live_transport_kind": "fake",
            "live_transport_truth_source": "fake_transport_no_external_network",
            "external_provider_network_used": False,
            "live_provider_smoke_attempted": live_provider_smoke_attempted,
            "live_smoke_attempted": live_provider_smoke_attempted,
            "smoke_route_bound": ok,
            "fake_transport_called": live_provider_smoke_attempted,
            "fake_transport_response_digest_present": ok,
            "fake_transport_response_sha256": (
                _sha256_text(fake_transport_response_fingerprint) if ok else ""
            ),
            "fake_transport_response_proven": ok,
            "live_provider_called": False,
            "live_provider_route_bound": False,
            "live_request_digest_present": bool(live_request_sha256),
            "live_request_sha256": live_request_sha256,
            "live_provider_error_observed": live_provider_error_observed,
            "live_provider_error_code_recorded": bool(live_provider_error_observed),
            "live_response_digest_present": False,
            "live_response_sha256": "",
            "live_provider_response_proven": False,
            "external_live_provider_response_proven": False,
            "live_provider_truth_source": "not_proven_external_provider_not_called",
            "state_written": False,
            "evidence_written": False,
            "file_mutation_attempted": False,
            "fallback_used": False,
            "local_imitation_used": False,
            "product_ready": False,
            "native_free_chat_router_proven": False,
            "does_not_prove_native_free_chat_router": True,
            "does_not_prove_external_provider_network_call": True,
            "raw_provider_response_recorded": False,
            "raw_backend_details_exposed": False,
            "secret_value_exposed": False,
            "no_secret_exposed": True,
        },
        packet_kind=LIVE_ROUTE_SMOKE_PACKET_KIND,
        final_status=(
            LIVE_ROUTE_SMOKE_FINAL_STATUS_ADMITTED
            if ok
            else LIVE_ROUTE_SMOKE_FINAL_STATUS_BLOCKED
        ),
        result_status="admitted" if ok else "blocked",
    )


def build_live_route_bound_api_smoke_proof_packet(
    smoke_packet: Mapping[str, Any] | None,
) -> dict[str, Any]:
    packet = smoke_packet if isinstance(smoke_packet, Mapping) else {}
    blocking_reasons: list[str] = []
    if packet.get("packet_kind") != LIVE_ROUTE_SMOKE_PACKET_KIND:
        blocking_reasons.append("live_smoke_packet_kind_invalid")
    if packet.get("status") != "ok":
        blocking_reasons.append("live_smoke_packet_not_ok")
    if packet.get("live_smoke_contract_proven") is not True:
        blocking_reasons.append("live_smoke_contract_not_proven")
    if packet.get("controlled_dispatch_evidence_proven") is not True:
        blocking_reasons.append("controlled_dispatch_evidence_not_proven")
    if packet.get("route_bound_dispatch_packet_kind") != ROUTE_BOUND_DISPATCH_PACKET_KIND:
        blocking_reasons.append("route_bound_dispatch_packet_kind_invalid")
    if packet.get("route_bound_dispatch_proven") is not True:
        blocking_reasons.append("route_bound_dispatch_not_proven")
    if packet.get("route_bound_request_sent") is not True:
        blocking_reasons.append("route_bound_request_not_sent")
    if not _hex_sha256(packet.get("route_bound_request_sha256") or ""):
        blocking_reasons.append("route_bound_request_digest_missing")
    if packet.get("alias_context_read") is not True:
        blocking_reasons.append("alias_context_not_read")
    if packet.get("allowed_api_route_ids_enforced") is not True:
        blocking_reasons.append("allowed_api_route_ids_not_enforced")
    if packet.get("forbidden_stale_route_ids_enforced") is not True:
        blocking_reasons.append("stale_route_guard_missing")
    if packet.get("route_allowed") is not True:
        blocking_reasons.append("selected_api_route_not_allowed")
    if packet.get("selected_api_route_id_present") is not True:
        blocking_reasons.append("selected_api_route_id_missing")
    if not _hex_sha256(packet.get("selected_api_route_id_sha256") or ""):
        blocking_reasons.append("selected_api_route_digest_missing")
    if packet.get("selected_api_route_id_recorded") is not False:
        blocking_reasons.append("selected_api_route_id_must_not_be_recorded")
    if packet.get("live_provider_smoke_attempted") is not True:
        blocking_reasons.append("live_provider_smoke_not_attempted")
    if packet.get("live_smoke_attempted") is not True:
        blocking_reasons.append("live_smoke_not_attempted")
    if packet.get("smoke_route_bound") is not True:
        blocking_reasons.append("smoke_not_route_bound")
    if packet.get("fake_transport_called") is not True:
        blocking_reasons.append("fake_transport_not_called")
    if packet.get("fake_transport_response_digest_present") is not True:
        blocking_reasons.append("fake_transport_response_digest_missing")
    if not _hex_sha256(packet.get("fake_transport_response_sha256") or ""):
        blocking_reasons.append("fake_transport_response_digest_invalid")
    if packet.get("fake_transport_response_proven") is not True:
        blocking_reasons.append("fake_transport_response_not_proven")
    if packet.get("live_provider_called") is not False:
        blocking_reasons.append("live_provider_call_must_not_be_claimed")
    if packet.get("live_provider_route_bound") is not False:
        blocking_reasons.append("live_provider_route_bound_must_not_be_claimed")
    if packet.get("live_request_digest_present") is not True:
        blocking_reasons.append("live_request_digest_missing")
    if not _hex_sha256(packet.get("live_request_sha256") or ""):
        blocking_reasons.append("live_request_digest_invalid")
    if packet.get("live_response_digest_present") is not False:
        blocking_reasons.append("live_response_digest_must_not_be_claimed")
    if packet.get("live_response_sha256") not in {None, ""}:
        blocking_reasons.append("live_response_digest_must_not_be_recorded")
    if packet.get("live_provider_response_proven") is not False:
        blocking_reasons.append("live_provider_response_must_not_be_claimed")
    if packet.get("live_transport_kind") != "fake":
        blocking_reasons.append("live_transport_kind_invalid")
    if packet.get("live_transport_truth_source") != "fake_transport_no_external_network":
        blocking_reasons.append("live_transport_truth_source_invalid")
    if packet.get("external_provider_network_used") is not False:
        blocking_reasons.append("external_provider_network_must_not_be_used")
    if packet.get("external_live_provider_response_proven") is not False:
        blocking_reasons.append("external_live_provider_response_must_not_be_claimed")
    if packet.get("state_written") is not False:
        blocking_reasons.append("state_must_not_be_written")
    if packet.get("evidence_written") is not False:
        blocking_reasons.append("evidence_must_not_be_written")
    if packet.get("file_mutation_attempted") is not False:
        blocking_reasons.append("file_mutation_must_not_be_attempted")
    if packet.get("fallback_used") is not False:
        blocking_reasons.append("fallback_used")
    if packet.get("local_imitation_used") is not False:
        blocking_reasons.append("local_imitation_used")
    if packet.get("product_ready") is not False:
        blocking_reasons.append("product_ready_must_not_be_claimed")
    if packet.get("native_free_chat_router_proven") is not False:
        blocking_reasons.append("native_free_chat_router_must_not_be_claimed")
    if packet.get("raw_prompt_recorded") is not False:
        blocking_reasons.append("raw_prompt_must_not_be_recorded")
    if packet.get("raw_provider_response_recorded") is not False:
        blocking_reasons.append("raw_provider_response_must_not_be_recorded")
    if packet.get("raw_backend_details_exposed") is not False:
        blocking_reasons.append("raw_backend_details_must_not_be_exposed")
    if packet.get("secret_value_exposed") is not False:
        blocking_reasons.append("secret_value_must_not_be_exposed")

    ok = not blocking_reasons
    machine_error_code = "OK" if ok else str(
        packet.get("machine_error_code") or LIVE_ROUTE_SMOKE_NOT_PROVEN
    )
    if not ok and machine_error_code == "OK":
        machine_error_code = LIVE_ROUTE_SMOKE_NOT_PROVEN

    return _command_packet_for_kind(
        ok=ok,
        machine_error_code=machine_error_code,
        human_message=(
            "WBP live route-bound API smoke proof accepted the admission packet."
            if ok
            else "WBP live route-bound API smoke proof rejected the supplied packet."
        ),
        blocking_reasons=[] if ok else blocking_reasons,
        extra={
            "source_packet_kind": str(packet.get("packet_kind") or ""),
            "live_smoke_contract_proven": (
                packet.get("live_smoke_contract_proven") is True
            ),
            "controlled_dispatch_evidence_proven": (
                packet.get("controlled_dispatch_evidence_proven") is True
            ),
            "selected_api_route_id_present": (
                packet.get("selected_api_route_id_present") is True
            ),
            "selected_api_route_id_sha256": str(
                packet.get("selected_api_route_id_sha256") or ""
            ),
            "selected_api_route_id_recorded": (
                packet.get("selected_api_route_id_recorded") is True
            ),
            "live_provider_smoke_attempted": (
                packet.get("live_provider_smoke_attempted") is True
            ),
            "live_smoke_attempted": packet.get("live_smoke_attempted") is True,
            "smoke_route_bound": packet.get("smoke_route_bound") is True,
            "fake_transport_called": packet.get("fake_transport_called") is True,
            "fake_transport_response_digest_present": (
                packet.get("fake_transport_response_digest_present") is True
            ),
            "fake_transport_response_sha256": str(
                packet.get("fake_transport_response_sha256") or ""
            ),
            "fake_transport_response_proven": (
                packet.get("fake_transport_response_proven") is True
            ),
            "live_provider_called": packet.get("live_provider_called") is True,
            "live_provider_route_bound": (
                packet.get("live_provider_route_bound") is True
            ),
            "live_request_digest_present": (
                packet.get("live_request_digest_present") is True
            ),
            "live_request_sha256": str(packet.get("live_request_sha256") or ""),
            "live_response_digest_present": (
                packet.get("live_response_digest_present") is True
            ),
            "live_response_sha256": str(packet.get("live_response_sha256") or ""),
            "live_provider_response_proven": (
                packet.get("live_provider_response_proven") is True
            ),
            "external_provider_network_used": (
                packet.get("external_provider_network_used") is True
            ),
            "external_live_provider_response_proven": (
                packet.get("external_live_provider_response_proven") is True
            ),
            "state_written": packet.get("state_written") is True,
            "evidence_written": packet.get("evidence_written") is True,
            "file_mutation_attempted": packet.get("file_mutation_attempted") is True,
            "fallback_used": packet.get("fallback_used") is True,
            "local_imitation_used": packet.get("local_imitation_used") is True,
            "product_ready": packet.get("product_ready") is True,
            "native_free_chat_router_proven": (
                packet.get("native_free_chat_router_proven") is True
            ),
            "raw_prompt_recorded": packet.get("raw_prompt_recorded") is True,
            "raw_provider_response_recorded": (
                packet.get("raw_provider_response_recorded") is True
            ),
            "raw_backend_details_exposed": (
                packet.get("raw_backend_details_exposed") is True
            ),
            "secret_value_exposed": packet.get("secret_value_exposed") is True,
            "no_secret_exposed": True,
        },
        packet_kind=LIVE_ROUTE_SMOKE_PROOF_PACKET_KIND,
        final_status=(
            LIVE_ROUTE_SMOKE_PROOF_FINAL_STATUS_ADMITTED
            if ok
            else LIVE_ROUTE_SMOKE_PROOF_FINAL_STATUS_BLOCKED
        ),
        result_status="admitted" if ok else "blocked",
    )


def delegate_to_dip_tool_descriptor() -> dict[str, Any]:
    return {
        "name": DELEGATE_TO_DIP_TOOL,
        "description": (
            "Delegate a bounded coding task to the WBP-owned API-lane alias from "
            "$WBP_PROFILE_DIR/wbp-agent-runtime-context.json. Returns proof, not "
            "product-ready native free-chat routing. When the user asks DIP, "
            "Agent 2, or another runtime-context coding alias to handle work, call "
            "this tool instead of answering locally or creating a Codex sub-agent."
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
            "When the user asks DIP, Agent 2, or another runtime-context coding "
            "alias to handle work, call delegate_to_dip. Do not answer locally and "
            "do not create a Codex sub-agent as DIP. The tool must fail closed when "
            "alias context or route allowlist evidence is missing."
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
    _write_entry_hook_evidence_if_requested(packet, env)
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
        and call_packet.get("api_lane_adapter_called") is True
        and call_packet.get("api_lane_dispatch_admitted") is True
        and call_packet.get("route_bound_dispatch_attempted") is True
        and call_packet.get("route_bound_dispatch_packet_kind")
        == ROUTE_BOUND_DISPATCH_PACKET_KIND
        and call_packet.get("route_bound_dispatch_proven") is True
        and call_packet.get("route_bound_request_sent") is True
        and bool(_hex_sha256(call_packet.get("route_bound_request_sha256") or ""))
        and call_packet.get("dispatch_truth_source")
        == "server_owned_controlled_provider_no_live_network"
        and call_packet.get("controlled_provider_called") is True
        and call_packet.get("controlled_provider_response_digest_present") is True
        and bool(
            _hex_sha256(call_packet.get("controlled_provider_response_sha256") or "")
        )
        and call_packet.get("controlled_provider_response_proven") is True
        and call_packet.get("provider_response_proven") is True
        and call_packet.get("live_provider_response_proven") is False
        and call_packet.get("task_digest_preserved") is True
        and (not prompt_digest_available or prompt_digest_bound_to_tool_packet)
        and (not call_digest_available or call_digest_bound_to_tool_packet)
        and call_packet.get("local_imitation_used") is False
        and call_packet.get("fallback_used") is False
        and call_packet.get("product_ready") is False
        and call_packet.get("raw_provider_response_recorded") is False
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
    if call_packet and call_packet.get("api_lane_adapter_called") is not True:
        blocking_reasons.append("api_lane_adapter_not_called")
    if call_packet and call_packet.get("api_lane_adapter_called") is True:
        if call_packet.get("api_lane_dispatch_admitted") is not True:
            blocking_reasons.append("api_lane_dispatch_not_admitted")
        if call_packet.get("route_bound_dispatch_attempted") is not True:
            blocking_reasons.append("route_bound_dispatch_not_attempted")
        if call_packet.get("route_bound_dispatch_packet_kind") != ROUTE_BOUND_DISPATCH_PACKET_KIND:
            blocking_reasons.append("route_bound_dispatch_packet_kind_invalid")
        if call_packet.get("route_bound_dispatch_proven") is not True:
            blocking_reasons.append("route_bound_dispatch_not_proven")
        if call_packet.get("route_bound_request_sent") is not True:
            blocking_reasons.append("route_bound_request_not_sent")
        if not _hex_sha256(call_packet.get("route_bound_request_sha256") or ""):
            blocking_reasons.append("route_bound_request_digest_missing")
        if (
            call_packet.get("dispatch_truth_source")
            != "server_owned_controlled_provider_no_live_network"
        ):
            blocking_reasons.append("dispatch_truth_source_invalid")
        if call_packet.get("controlled_provider_called") is not True:
            blocking_reasons.append("controlled_provider_not_called")
        if call_packet.get("controlled_provider_response_digest_present") is not True:
            blocking_reasons.append("controlled_provider_response_digest_missing")
        if not _hex_sha256(
            call_packet.get("controlled_provider_response_sha256") or ""
        ):
            blocking_reasons.append("controlled_provider_response_digest_invalid")
        if call_packet.get("controlled_provider_response_proven") is not True:
            blocking_reasons.append("controlled_provider_response_not_proven")
        if call_packet.get("provider_response_proven") is not True:
            blocking_reasons.append("provider_response_not_proven")
        if call_packet.get("live_provider_response_proven") is not False:
            blocking_reasons.append("live_provider_response_must_not_be_claimed")
        if call_packet.get("raw_provider_response_recorded") is not False:
            blocking_reasons.append("raw_provider_response_must_not_be_recorded")
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
            "api_lane_adapter_called": call_packet.get("api_lane_adapter_called") is True,
            "api_lane_dispatch_admitted": (
                call_packet.get("api_lane_dispatch_admitted") is True
            ),
            "api_lane_adapter_packet_kind": str(
                call_packet.get("api_lane_adapter_packet_kind") or ""
            ),
            "api_lane_adapter_machine_error_code": str(
                call_packet.get("api_lane_adapter_machine_error_code") or ""
            ),
            "route_bound_dispatch_attempted": (
                call_packet.get("route_bound_dispatch_attempted") is True
            ),
            "route_bound_dispatch_proven": (
                call_packet.get("route_bound_dispatch_proven") is True
            ),
            "route_bound_dispatch_packet_kind": str(
                call_packet.get("route_bound_dispatch_packet_kind") or ""
            ),
            "route_bound_dispatch_machine_error_code": str(
                call_packet.get("route_bound_dispatch_machine_error_code") or ""
            ),
            "route_bound_request_sent": (
                call_packet.get("route_bound_request_sent") is True
            ),
            "route_bound_request_sha256": str(
                call_packet.get("route_bound_request_sha256") or ""
            ),
            "dispatch_truth_source": str(
                call_packet.get("dispatch_truth_source") or ""
            ),
            "controlled_provider_called": (
                call_packet.get("controlled_provider_called") is True
            ),
            "controlled_provider_response_digest_present": (
                call_packet.get("controlled_provider_response_digest_present") is True
            ),
            "controlled_provider_response_sha256": str(
                call_packet.get("controlled_provider_response_sha256") or ""
            ),
            "controlled_provider_response_proven": (
                call_packet.get("controlled_provider_response_proven") is True
            ),
            "api_lane_called": call_packet.get("api_lane_called") is True,
            "api_lane_provider_called": call_packet.get("api_lane_provider_called") is True,
            "provider_response_proven": call_packet.get("provider_response_proven") is True,
            "live_provider_response_proven": (
                call_packet.get("live_provider_response_proven") is True
            ),
            "selected_api_route_id_present": (
                call_packet.get("selected_api_route_id_present") is True
            ),
            "selected_api_route_id_sha256": str(
                call_packet.get("selected_api_route_id_sha256") or ""
            ),
            "selected_api_route_id_recorded": (
                call_packet.get("selected_api_route_id_recorded") is True
            ),
            "tool_packet_status": str(call_packet.get("status") or ""),
            "tool_packet_machine_error_code": str(
                call_packet.get("machine_error_code") or ""
            ),
            "transcript_digest": _sha256_text(transcript_fingerprint),
            "raw_transcript_recorded": False,
            "raw_provider_response_recorded": (
                call_packet.get("raw_provider_response_recorded") is True
            ),
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
