# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from .active_project_root import (
    ACTIVE_PROJECT_ROOT_FIELD_NAMES,
    active_project_root_metadata,
    select_active_project_root_candidate,
    target_repo_fields_from_active_project_root,
)
from .api_agent_direct_reply import (
    DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE,
    DEFAULT_DIRECT_REPLY_WORK_MODE,
    DIRECT_REPLY_REPO_BRIDGE_MODES,
    DIRECT_REPLY_WORK_MODES,
    LiveResultRunner,
    build_api_agent_direct_reply_packet,
    resolve_prompt_repo_bridge_mode,
    resolve_prompt_work_mode,
)
from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .core import packets
from .natural_intent_contract import (
    DISPATCH_STATUS_NOT_ATTEMPTED,
    FAIL_ALIAS_CONTEXT_MISSING,
    FAIL_ALIAS_NOT_API_LANE,
    INTENT_AMBIGUOUS_NO_DISPATCH,
    NO_ALIAS_DETECTED,
    SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
    build_natural_intent_parser_packet,
)
from .router_hook_entry import (
    HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import REPO_ROOT, RuntimePaths, write_json_atomic
from .runtime_errors import RuntimeErrorInfo
from .runtime_dispatch_mode_truth import (
    DISPATCH_MODE_API_ONLY,
    DISPATCH_MODE_CHATGPT_ONLY,
    EXECUTOR_API_ROUTE,
    EXECUTOR_CHATGPT,
    ORCHESTRATOR_API_ROUTE,
    ORCHESTRATOR_CHATGPT,
    dispatch_mode_truth_fields,
)
from .wbp_dip_tool import (
    _exact_plain_reply_expected_text,
    _exact_plain_reply_requested,
)


API_AGENT_AUTO_ROUTER_PACKET_KIND = "wbp_api_agent_auto_router"
API_AGENT_AUTO_ROUTER_FILE_NAME = "api-agent-auto-router.packet.json"
API_AGENT_AUTO_ROUTER_OK = "OK"
API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS = "WBP_API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS"
API_AGENT_AUTO_ROUTER_AMBIGUOUS = "WBP_API_AGENT_AUTO_ROUTER_AMBIGUOUS"
API_AGENT_AUTO_ROUTER_DIRECT_REPLY_FAILED = (
    "WBP_API_AGENT_AUTO_ROUTER_DIRECT_REPLY_FAILED"
)

AUTO_ROUTER_DECISION_API_DIRECT_REPLY = "api_direct_reply"
AUTO_ROUTER_DECISION_GPT_LANE = "gpt_lane"
AUTO_ROUTER_DECISION_GPT_PASSTHROUGH = "gpt_passthrough"
AUTO_ROUTER_DECISION_BLOCKED = "blocked"

_LEADING_ADDRESS_RE = re.compile(
    r"^\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9 _.-]{0,78})\s*[:：,]\s*"
)


def _safe_text(value: object, *, limit: int = 4096) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _safe_text_list(value: object, *, limit: int = 80) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item, limit=limit) for item in value]


def _safe_evidence_trace(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    trace: list[dict[str, Any]] = []
    for index, item in enumerate(value[:50], start=1):
        if not isinstance(item, Mapping):
            continue
        trace.append(
            {
                "step": int(item.get("step") or index),
                "tool": _safe_text(item.get("tool"), limit=80),
                "origin": _safe_text(item.get("origin"), limit=80),
                "status": _safe_text(item.get("status"), limit=40),
                "machine_error_code": _safe_text(
                    item.get("machine_error_code"),
                    limit=120,
                ),
                "command_exit_code": item.get("command_exit_code"),
                "result_text_sha256": _safe_text(
                    item.get("result_text_sha256"),
                    limit=80,
                ),
                "result_text_truncated": item.get("result_text_truncated") is True,
                "mutation_applied": item.get("mutation_applied") is True,
                "rollback_applied": item.get("rollback_applied") is True,
            }
        )
    return trace


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_bool(value: object) -> bool:
    return value is True


def _persist_proof_packet(
    packet: Mapping[str, Any],
    *,
    proof_dir: str | Path | None,
    file_name: str = API_AGENT_AUTO_ROUTER_FILE_NAME,
) -> dict[str, Any]:
    if proof_dir is None or not str(proof_dir).strip():
        return dict(packet)
    output_dir = Path(proof_dir).expanduser()
    output_file = output_dir / file_name
    changed_files = [
        str(item)
        for item in (
            packet.get("changed_files") if isinstance(packet.get("changed_files"), list) else []
        )
    ]
    if file_name not in changed_files:
        changed_files.append(file_name)
    persisted = dict(packet)
    persisted.update(
        {
            "changed_files": changed_files,
            "effect": EFFECT_MUTATE,
            "state_written": False,
            "evidence_written": True,
            "proof_file_written": True,
            "proof_file_name": file_name,
            "proof_file_path_recorded": False,
            "proof_dir_path_recorded": False,
        }
    )
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(output_file, persisted)
    except OSError as exc:
        raise RuntimeErrorInfo(
            "Failed to write auto-route proof packet.",
            machine_error_code="WBP_API_AGENT_AUTO_ROUTER_PROOF_WRITE_FAILED",
            operator_action="retry",
        ) from exc
    return persisted


def _command_effect(repo_bridge_mode: str) -> str:
    return EFFECT_PROBE if repo_bridge_mode == "off" else EFFECT_MUTATE


def _safe_reply_proof_summary(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = {
        "route_bound_dispatch_proven",
        "controlled_dispatch_proven",
        "api_agent_provider_called",
        "api_agent_response_observed",
        "provider_response_proven",
        "repo_bridge_evidence_response_proven",
        "final_answer_was_repo_tool_call",
        "fallback_used",
        "local_imitation_used",
        "tools_wbp_dip_invoked",
        "dip_run_invoked",
        "codex_exec_invoked",
        "native_codex_subagent_used_as_dip",
    }
    return {key: value.get(key) is True for key in sorted(allowed)}


def _leading_address_label(prompt_text: object) -> str:
    match = _LEADING_ADDRESS_RE.match(str(prompt_text or ""))
    return _safe_text(match.group(1), limit=80) if match else ""


def _leading_label_looks_like_unknown_alias(label: str) -> bool:
    normalized = _safe_text(label, limit=80).casefold()
    if not normalized:
        return False
    parts = normalized.split()
    if len(parts) == 1:
        return True
    return parts[0] in {
        "agent",
        "агент",
        "api",
        "gpt",
        "codex",
        "dip",
        "deepseek",
    }


def _direct_reply_summary_fields(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "direct_reply_packet_kind": _safe_text(packet.get("packet_kind"), limit=80),
        "direct_reply_status": _safe_text(packet.get("status"), limit=32),
        "direct_reply_machine_error_code": _safe_text(
            packet.get("machine_error_code"),
            limit=128,
        ),
        "direct_reply_selected_alias": _safe_text(packet.get("selected_alias"), limit=80),
        "direct_reply_selected_slot": _safe_text(packet.get("selected_slot"), limit=80),
        "direct_reply_selected_alias_lane": _safe_text(
            packet.get("selected_alias_lane"),
            limit=40,
        ),
        "direct_reply_text": _safe_text(packet.get("direct_reply_text"), limit=65536),
        "direct_reply_text_available": _as_bool(
            packet.get("api_agent_direct_reply_text_available")
        ),
        "direct_reply_text_recorded": _as_bool(
            packet.get("api_agent_direct_reply_text_recorded")
        ),
        "direct_reply_text_sha256": _safe_text(
            packet.get("direct_reply_text_sha256"),
            limit=80,
        ),
        "direct_reply_text_length": int(packet.get("direct_reply_text_length") or 0),
        "direct_reply_text_truncated": _as_bool(
            packet.get("direct_reply_text_truncated")
        ),
        "direct_api_reply_block": _as_bool(packet.get("direct_api_reply_block")),
        "reply_block_kind": _safe_text(packet.get("reply_block_kind"), limit=80),
        "reply_author_alias": _safe_text(packet.get("reply_author_alias"), limit=80),
        "reply_agent_id": _safe_text(packet.get("reply_agent_id"), limit=80),
        "reply_lane": _safe_text(packet.get("reply_lane"), limit=40),
        "reply_provider_label": _safe_text(packet.get("reply_provider_label"), limit=80),
        "reply_text": _safe_text(packet.get("reply_text"), limit=65536),
        "reply_text_sha256": _safe_text(packet.get("reply_text_sha256"), limit=80),
        "reply_text_length": int(packet.get("reply_text_length") or 0),
        "reply_text_truncated": _as_bool(packet.get("reply_text_truncated")),
        "reply_proof_summary": _safe_reply_proof_summary(
            packet.get("reply_proof_summary")
        ),
        "final_answer_was_repo_tool_call": _as_bool(
            packet.get("final_answer_was_repo_tool_call")
        ),
        "route_bound_dispatch_proven": _as_bool(
            packet.get("route_bound_dispatch_proven")
        ),
        "selected_route_id_allowed": _as_bool(packet.get("selected_route_id_allowed")),
        "allowed_api_route_ids_enforced": _as_bool(
            packet.get("allowed_api_route_ids_enforced")
        ),
        "api_agent_provider_called": _as_bool(packet.get("api_agent_provider_called")),
        "api_agent_response_observed": _as_bool(
            packet.get("api_agent_response_observed")
        ),
        "provider_response_proven": _as_bool(
            packet.get("provider_response_proven")
        ),
        "repo_bridge_evidence_response_proven": _as_bool(
            packet.get("repo_bridge_evidence_response_proven")
        ),
        "direct_provider_response_observed": _as_bool(
            packet.get("direct_provider_response_observed")
        ),
        "provider_auth_ok": _as_bool(packet.get("provider_auth_ok")),
        "positive_provider_proof_gate_satisfied": _as_bool(
            packet.get("positive_provider_proof_gate_satisfied")
        ),
        "runtime_context_bridge_used": _as_bool(
            packet.get("runtime_context_bridge_used")
        ),
        "runtime_context_file_bridge_used": _as_bool(
            packet.get("runtime_context_file_bridge_used")
        ),
        "bridge_or_file_bridge_used": _as_bool(packet.get("bridge_or_file_bridge_used")),
        "network_dependent": _as_bool(packet.get("network_dependent")),
        "exact_plain_reply_fast_path": _as_bool(
            packet.get("exact_plain_reply_fast_path")
        ),
        "exact_plain_reply_file_bridge_skipped": _as_bool(
            packet.get("exact_plain_reply_file_bridge_skipped")
        ),
        "exact_plain_reply_matched": _as_bool(packet.get("exact_plain_reply_matched")),
        "exact_plain_reply_expected_text_sha256": _safe_text(
            packet.get("exact_plain_reply_expected_text_sha256"),
            limit=80,
        ),
        "exact_plain_reply_expected_text_recorded": _as_bool(
            packet.get("exact_plain_reply_expected_text_recorded")
        ),
        "exact_plain_reply_observed_text_sha256": _safe_text(
            packet.get("exact_plain_reply_observed_text_sha256"),
            limit=80,
        ),
        "exact_plain_reply_observed_text_recorded": _as_bool(
            packet.get("exact_plain_reply_observed_text_recorded")
        ),
        "file_bridge_attempted": _as_bool(packet.get("file_bridge_attempted")),
        "file_bridge_skipped": _as_bool(packet.get("file_bridge_skipped")),
        "dip_work_mode": _safe_text(packet.get("dip_work_mode"), limit=40),
        "dip_full_work_mode": _as_bool(packet.get("dip_full_work_mode")),
        "live_result_text_limit": int(packet.get("live_result_text_limit") or 0),
        "live_result_output_token_limit": int(
            packet.get("live_result_output_token_limit") or 0
        ),
        "repo_bridge_mode": _safe_text(packet.get("repo_bridge_mode"), limit=40),
        "repo_bridge_required": _as_bool(packet.get("repo_bridge_required")),
        "repo_bridge_available": _as_bool(packet.get("repo_bridge_available")),
        "repo_bridge_used": _as_bool(packet.get("repo_bridge_used")),
        "dip_repo_tool_bridge_required": _as_bool(
            packet.get("dip_repo_tool_bridge_required")
        ),
        "dip_repo_tool_bridge_available": _as_bool(
            packet.get("dip_repo_tool_bridge_available")
        ),
        "dip_repo_tool_bridge_used": _as_bool(
            packet.get("dip_repo_tool_bridge_used")
        ),
        "dip_repo_direct_access": _as_bool(packet.get("dip_repo_direct_access")),
        "repo_bridge_context_pack_used": _as_bool(
            packet.get("repo_bridge_context_pack_used")
        ),
        "repo_bridge_context_pack_recorded": _as_bool(
            packet.get("repo_bridge_context_pack_recorded")
        ),
        "repo_bridge_readonly": _as_bool(packet.get("repo_bridge_readonly")),
        "repo_bridge_mutation_allowed": _as_bool(
            packet.get("repo_bridge_mutation_allowed")
        ),
        "repo_bridge_mutation_controlled": _as_bool(
            packet.get("repo_bridge_mutation_controlled")
        ),
        "repo_bridge_bootstrap_used": _as_bool(
            packet.get("repo_bridge_bootstrap_used")
        ),
        "repo_bridge_bootstrap_tool_call_count": int(
            packet.get("repo_bridge_bootstrap_tool_call_count") or 0
        ),
        "repo_bridge_tool_call_count": int(
            packet.get("repo_bridge_tool_call_count") or 0
        ),
        "repo_bridge_successful_tool_call_count": int(
            packet.get("repo_bridge_successful_tool_call_count") or 0
        ),
        "repo_bridge_tool_names": _safe_text_list(
            packet.get("repo_bridge_tool_names")
        ),
        "repo_bridge_bootstrap_tool_names": _safe_text_list(
            packet.get("repo_bridge_bootstrap_tool_names")
        ),
        "dip_evidence_trace_available": _as_bool(
            packet.get("dip_evidence_trace_available")
        ),
        "dip_evidence_trace_recorded": _as_bool(
            packet.get("dip_evidence_trace_recorded")
        ),
        "dip_evidence_trace_count": int(
            packet.get("dip_evidence_trace_count") or 0
        ),
        "dip_evidence_trace": _safe_evidence_trace(
            packet.get("dip_evidence_trace")
        ),
        "dip_evidence_trace_raw_output_recorded": _as_bool(
            packet.get("dip_evidence_trace_raw_output_recorded")
        ),
        "repo_bridge_raw_tool_results_recorded": _as_bool(
            packet.get("repo_bridge_raw_tool_results_recorded")
        ),
        "dip_action_bridge_required": _as_bool(
            packet.get("dip_action_bridge_required")
        ),
        "dip_action_bridge_available": _as_bool(
            packet.get("dip_action_bridge_available")
        ),
        "dip_action_bridge_used": _as_bool(packet.get("dip_action_bridge_used")),
        "dip_action_bridge_succeeded": _as_bool(
            packet.get("dip_action_bridge_succeeded")
        ),
        "dip_action_tool_call_count": int(
            packet.get("dip_action_tool_call_count") or 0
        ),
        "dip_action_successful_tool_call_count": int(
            packet.get("dip_action_successful_tool_call_count") or 0
        ),
        "dip_action_tool_names": _safe_text_list(
            packet.get("dip_action_tool_names")
        ),
        "dip_action_mutation_applied": _as_bool(
            packet.get("dip_action_mutation_applied")
        ),
        "dip_action_tests_run": _as_bool(packet.get("dip_action_tests_run")),
        "dip_action_commands_run": _as_bool(packet.get("dip_action_commands_run")),
        "dip_action_patch_proposed": _as_bool(
            packet.get("dip_action_patch_proposed")
        ),
        "dip_action_patch_applied": _as_bool(
            packet.get("dip_action_patch_applied")
        ),
        "dip_code_mutation_required": _as_bool(
            packet.get("dip_code_mutation_required")
        ),
        "dip_code_written": _as_bool(packet.get("dip_code_written")),
        "dip_code_patch_applied": _as_bool(packet.get("dip_code_patch_applied")),
        "dip_code_verification_required": _as_bool(
            packet.get("dip_code_verification_required")
        ),
        "dip_code_verified": _as_bool(packet.get("dip_code_verified")),
        "dip_code_verification_failed": _as_bool(
            packet.get("dip_code_verification_failed")
        ),
        "dip_code_failed_verification_count": int(
            packet.get("dip_code_failed_verification_count") or 0
        ),
        "dip_action_mutated_files": [
            _safe_text(path, limit=500)
            for path in (
                packet.get("dip_action_mutated_files")
                if isinstance(packet.get("dip_action_mutated_files"), list)
                else []
            )
        ],
        "repo_bridge_final_answer_synthesized": _as_bool(
            packet.get("repo_bridge_final_answer_synthesized")
        ),
        "file_mutation_attempted": _as_bool(packet.get("file_mutation_attempted")),
        "changed_files": [
            _safe_text(path, limit=500)
            for path in (
                packet.get("changed_files")
                if isinstance(packet.get("changed_files"), list)
                else []
            )
        ],
        "fallback_used": _as_bool(packet.get("fallback_used")),
        "local_imitation_used": _as_bool(packet.get("local_imitation_used")),
        "raw_backend_details_exposed": _as_bool(
            packet.get("raw_backend_details_exposed")
        ),
        "secret_value_exposed": _as_bool(packet.get("secret_value_exposed")),
    }


def _json_output_passthrough_requested(prompt_text: object) -> bool:
    prompt_key = _safe_text(prompt_text, limit=4096).casefold()
    prompt_key = prompt_key.replace("_", " ").replace("-", " ")
    prompt_key = " ".join(prompt_key.split())
    exact_markers = {
        "ответь ровно",
        "ответь только",
        "верни ровно",
        "верни только",
        "output exactly",
        "reply exactly",
        "return exactly",
        "only json",
        "json only",
    }
    return "json" in prompt_key and any(marker in prompt_key for marker in exact_markers)


def _valid_json_text(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, (dict, list))


def _exact_plain_visible_output_allowed(packet: Mapping[str, Any]) -> bool:
    if not _as_bool(packet.get("exact_plain_reply_matched")):
        return False
    if not _as_bool(packet.get("repo_bridge_used")):
        return True
    if _as_bool(packet.get("repo_bridge_evidence_response_proven")):
        return True
    return bool(
        _as_bool(packet.get("direct_provider_response_observed"))
        and _as_bool(packet.get("positive_provider_proof_gate_satisfied"))
    )


def _direct_reply_visible_output_proven(
    *,
    direct_reply_ok: bool,
    direct_summary: Mapping[str, Any],
) -> bool:
    return bool(
        direct_reply_ok
        and direct_summary.get("direct_reply_selected_alias_lane") == "api_route"
        and _as_bool(direct_summary.get("direct_api_reply_block"))
        and _as_bool(direct_summary.get("route_bound_dispatch_proven"))
        and _as_bool(direct_summary.get("selected_route_id_allowed"))
        and _as_bool(direct_summary.get("allowed_api_route_ids_enforced"))
        and _as_bool(direct_summary.get("api_agent_provider_called"))
        and _as_bool(direct_summary.get("api_agent_response_observed"))
        and _as_bool(direct_summary.get("provider_response_proven"))
        and _as_bool(direct_summary.get("direct_provider_response_observed"))
        and _as_bool(direct_summary.get("provider_auth_ok"))
        and _as_bool(direct_summary.get("positive_provider_proof_gate_satisfied"))
        and bool(str(direct_summary.get("reply_text") or ""))
        and not _as_bool(direct_summary.get("repo_bridge_used"))
        and not _as_bool(direct_summary.get("final_answer_was_repo_tool_call"))
        and not _as_bool(direct_summary.get("fallback_used"))
        and not _as_bool(direct_summary.get("local_imitation_used"))
        and not _as_bool(direct_summary.get("raw_backend_details_exposed"))
        and not _as_bool(direct_summary.get("secret_value_exposed"))
    )


def _output_passthrough_fields(
    *,
    prompt_text: object,
    direct_reply_ok: bool,
    direct_summary: Mapping[str, Any],
) -> dict[str, Any]:
    reply_text = _safe_text(direct_summary.get("reply_text"), limit=65536)
    exact_plain = _exact_plain_visible_output_allowed(direct_summary)
    exact_json = (
        _json_output_passthrough_requested(prompt_text)
        and _valid_json_text(reply_text)
    )
    required = bool(direct_reply_ok and (exact_plain or exact_json))
    kind = ""
    text_for_digest = reply_text
    if direct_reply_ok and exact_plain:
        kind = "exact_plain_reply"
    elif direct_reply_ok and exact_json:
        kind = "exact_json_reply"
    return {
        "output_passthrough_required": required,
        "output_passthrough_kind": kind,
        "output_passthrough_text_available": bool(required and text_for_digest),
        "output_passthrough_text_sha256": (
            _sha256_text(text_for_digest) if required and text_for_digest else ""
        ),
        "output_passthrough_text_recorded": False,
    }


def build_api_agent_auto_router_packet(
    *,
    prompt_text: object,
    runtime_context: Mapping[str, Any] | None,
    context_file_metadata: Mapping[str, Any] | None = None,
    profile_dir: Path,
    active_project_root: Path | None = None,
    active_project_root_source: str = "missing",
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    repo_bridge_mode: str = DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE,
    work_mode: str = DEFAULT_DIRECT_REPLY_WORK_MODE,
    timeout_seconds: float = 60.0,
    live_result_runner: LiveResultRunner | None = None,
) -> dict[str, Any]:
    prompt = str(prompt_text or "")
    repo_bridge = resolve_prompt_repo_bridge_mode(
        prompt_text=prompt,
        repo_bridge_mode=(
            repo_bridge_mode
            if repo_bridge_mode in DIRECT_REPLY_REPO_BRIDGE_MODES
            else DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE
        ),
    )
    work = resolve_prompt_work_mode(
        prompt_text=prompt,
        work_mode=(
            work_mode
            if work_mode in DIRECT_REPLY_WORK_MODES
            else DEFAULT_DIRECT_REPLY_WORK_MODE
        ),
        repo_bridge_mode=repo_bridge,
    )
    parser_packet = build_natural_intent_parser_packet(
        prompt_text=prompt,
        runtime_context=runtime_context,
        source_surface=SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
        secret_values=[prompt],
    )
    selected_active_project_root, active_root_fields = active_project_root_metadata(
        active_project_root,
        source=active_project_root_source,
        wbp_repo_root=REPO_ROOT,
        required=False,
    )
    parser_code = _safe_text(parser_packet.get("machine_error_code"), limit=128)
    alias = _safe_text(parser_packet.get("alias_candidate"), limit=80)
    lane = _safe_text(parser_packet.get("lane_candidate"), limit=40)
    slot = _safe_text(parser_packet.get("slot_candidate"), limit=80)
    leading_label = _leading_address_label(prompt)
    leading_label_unknown_alias_candidate = _leading_label_looks_like_unknown_alias(
        leading_label
    )

    direct_packet: Mapping[str, Any] = {}
    blocking_reasons: list[str] = []
    decision = AUTO_ROUTER_DECISION_BLOCKED
    api_direct_selected = False
    gpt_lane_selected = False
    passthrough_to_gpt = False
    ok = False
    machine_error_code = parser_code or API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS

    if parser_packet.get("status") == "ok" and lane == "api_route":
        api_direct_selected = True
        decision = AUTO_ROUTER_DECISION_API_DIRECT_REPLY
        direct_packet = build_api_agent_direct_reply_packet(
            prompt_text=prompt,
            runtime_context=runtime_context,
            context_file_metadata=context_file_metadata,
            profile_dir=profile_dir,
            active_project_root=selected_active_project_root,
            active_project_root_source=active_project_root_source,
            hook_surface_kind=hook_surface_kind,
            repo_bridge_mode=repo_bridge,
            work_mode=work,
            timeout_seconds=timeout_seconds,
            live_result_runner=live_result_runner,
        )
        ok = direct_packet.get("status") == "ok"
        if ok:
            machine_error_code = API_AGENT_AUTO_ROUTER_OK
        else:
            machine_error_code = _safe_text(
                direct_packet.get("machine_error_code")
                or API_AGENT_AUTO_ROUTER_DIRECT_REPLY_FAILED,
                limit=128,
            )
            blocking_reasons.append(machine_error_code)
            blocking_reasons.extend(
                _safe_text(reason, limit=160)
                for reason in (
                    direct_packet.get("blocking_reasons")
                    if isinstance(direct_packet.get("blocking_reasons"), list)
                    else []
                )
            )
    elif parser_code == FAIL_ALIAS_NOT_API_LANE and lane == "primary_chatgpt":
        gpt_lane_selected = True
        passthrough_to_gpt = True
        decision = AUTO_ROUTER_DECISION_GPT_LANE
        ok = True
        machine_error_code = API_AGENT_AUTO_ROUTER_OK
    elif parser_code == NO_ALIAS_DETECTED and not leading_label_unknown_alias_candidate:
        gpt_lane_selected = True
        passthrough_to_gpt = True
        decision = AUTO_ROUTER_DECISION_GPT_PASSTHROUGH
        ok = True
        machine_error_code = API_AGENT_AUTO_ROUTER_OK
    elif parser_code == FAIL_ALIAS_CONTEXT_MISSING:
        machine_error_code = FAIL_ALIAS_CONTEXT_MISSING
        blocking_reasons.append("alias_context_missing_or_invalid")
    elif parser_code == INTENT_AMBIGUOUS_NO_DISPATCH:
        machine_error_code = API_AGENT_AUTO_ROUTER_AMBIGUOUS
        blocking_reasons.append("ambiguous_alias_intent")
    else:
        if alias:
            machine_error_code = parser_code or "alias_intent_not_admitted"
            blocking_reasons.append(machine_error_code)
        elif leading_label_unknown_alias_candidate:
            machine_error_code = API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS
            blocking_reasons.append("unknown_addressed_alias")
        else:
            blocking_reasons.append(parser_code or "alias_intent_not_admitted")

    direct_summary = _direct_reply_summary_fields(direct_packet)
    direct_reply_ok = bool(api_direct_selected and ok)
    direct_reply_output_text = str(direct_packet.get("reply_text") or "")[:65536]
    direct_reply_visible_output_proven = _direct_reply_visible_output_proven(
        direct_reply_ok=direct_reply_ok,
        direct_summary=direct_summary,
    )
    dispatch_proven = direct_reply_ok
    route_bound_dispatch_proven = bool(
        direct_reply_ok and direct_summary["route_bound_dispatch_proven"]
    )
    primary_exact_reply_requested = bool(
        gpt_lane_selected
        and lane == "primary_chatgpt"
        and _exact_plain_reply_requested(prompt)
    )
    primary_exact_reply_visible_output = False
    wrapper_bypassed = bool(api_direct_selected)
    execution_mode = (
        DISPATCH_MODE_API_ONLY if api_direct_selected else DISPATCH_MODE_CHATGPT_ONLY
    )
    orchestrator = ORCHESTRATOR_API_ROUTE if api_direct_selected else ORCHESTRATOR_CHATGPT
    executor = EXECUTOR_API_ROUTE if api_direct_selected else EXECUTOR_CHATGPT
    changed_files = list(direct_summary["changed_files"])

    def _active_root_field(key: str) -> Any:
        return direct_packet.get(key, active_root_fields.get(key))

    target_repo_fields = target_repo_fields_from_active_project_root(
        {
            key: _active_root_field(key)
            for key in ACTIVE_PROJECT_ROOT_FIELD_NAMES
        }
    )

    extra = {
        "schema_version": 1,
        "packet_kind": API_AGENT_AUTO_ROUTER_PACKET_KIND,
        **dispatch_mode_truth_fields(
            execution_mode=execution_mode,
            truth_source=API_AGENT_AUTO_ROUTER_PACKET_KIND,
            orchestrator=orchestrator,
            executor=executor,
            mode_proven=ok,
            chatgpt_lane_selected=gpt_lane_selected,
            api_route_selected=api_direct_selected,
            chatgpt_lane_called=False,
            api_route_called=bool(
                api_direct_selected and direct_summary["api_agent_provider_called"]
            ),
            active_project_root_required=bool(
                _active_root_field("active_project_root_required") is True
            ),
            active_project_root_available=bool(
                _active_root_field("active_project_root_available") is True
            ),
            active_project_root_source=_safe_text(
                _active_root_field("active_project_root_source"),
                limit=80,
            ),
            active_project_root_status=_safe_text(
                _active_root_field("active_project_root_status"),
                limit=120,
            ),
            active_project_root_sha256=_safe_text(
                _active_root_field("active_project_root_sha256"),
                limit=80,
            ),
            active_project_root_path_recorded=bool(
                _active_root_field("active_project_root_path_recorded") is True
            ),
            active_project_root_fallback_used=bool(
                _active_root_field("active_project_root_fallback_used") is True
            ),
            active_project_root_is_wbp_repo=bool(
                _active_root_field("active_project_root_is_wbp_repo") is True
            ),
            active_project_root_git_available=bool(
                _active_root_field("active_project_root_git_available") is True
            ),
            active_project_root_legacy_target_repo_alias_used=bool(
                _active_root_field("active_project_root_legacy_target_repo_alias_used")
                is True
            ),
        ),
        **target_repo_fields,
        "auto_router_used": True,
        "auto_router_proven": ok,
        "auto_router_decision": decision,
        "auto_router_decision_source": "runtime_context_alias_parser",
        "auto_router_fail_closed": not ok,
        "auto_router_unknown_alias_blocked": (
            machine_error_code == API_AGENT_AUTO_ROUTER_UNKNOWN_ALIAS
        ),
        "auto_router_ambiguous_alias_blocked": (
            machine_error_code == API_AGENT_AUTO_ROUTER_AMBIGUOUS
        ),
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "prompt_digest_present": bool(prompt),
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "natural_phrase_recorded": False,
        "leading_address_label_present": bool(leading_label),
        "leading_address_label_recorded": False,
        "leading_address_label_unknown_alias_candidate": bool(
            leading_label_unknown_alias_candidate
        ),
        "parser_packet_kind": _safe_text(parser_packet.get("packet_kind"), limit=80),
        "parser_status": _safe_text(parser_packet.get("parser_status"), limit=80),
        "parser_target_selection_rule": _safe_text(
            parser_packet.get("parser_target_selection_rule"),
            limit=80,
        ),
        "parser_machine_error_code": parser_code,
        "parser_alias_match_count": int(
            parser_packet.get("parser_alias_match_count") or 0
        ),
        "runtime_context_file_required": True,
        "runtime_context_file_present": bool(
            (context_file_metadata or {}).get("runtime_context_file_present", False)
        ),
        "runtime_context_file_read": bool(
            (context_file_metadata or {}).get("runtime_context_file_read", False)
        ),
        "runtime_context_file_path_recorded": False,
        "runtime_context_source": _safe_text(
            parser_packet.get("runtime_context_source"),
            limit=120,
        ),
        "runtime_context_present": _as_bool(parser_packet.get("runtime_context_present")),
        "runtime_context_kind_valid": _as_bool(
            parser_packet.get("runtime_context_kind_valid")
        ),
        "alias_context_read": _as_bool(parser_packet.get("alias_context_read")),
        "selected_alias": alias,
        "selected_slot": slot,
        "selected_alias_lane": lane,
        "selected_api_route_id_present": _as_bool(
            direct_packet.get("selected_api_route_id_present")
        ),
        "selected_api_route_id_sha256": _safe_text(
            direct_packet.get("selected_api_route_id_sha256"),
            limit=80,
        ),
        "selected_api_route_id_recorded": False,
        "selected_route_id_allowed": direct_summary["selected_route_id_allowed"],
        "allowed_api_route_ids_enforced": direct_summary[
            "allowed_api_route_ids_enforced"
        ],
        "forbidden_stale_route_ids_enforced": _as_bool(
            parser_packet.get("forbidden_stale_route_ids_enforced")
        ),
        "forbidden_stale_route_ids_count": int(
            parser_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "natural_alias_command_detected": _as_bool(
            parser_packet.get("natural_alias_command_detected")
        ),
        "natural_api_alias_command_detected": _as_bool(
            parser_packet.get("natural_api_alias_command_detected")
        ),
        "direct_reply_selected": api_direct_selected,
        "direct_reply_proven": direct_reply_ok,
        "direct_reply_visible_output_proven": direct_reply_visible_output_proven,
        "gpt_lane_selected": gpt_lane_selected,
        "gpt_passthrough_to_native_chat": passthrough_to_gpt,
        "gpt_wrapper_bypassed": wrapper_bypassed,
        "route_bound_dispatch_proven": route_bound_dispatch_proven,
        "router_dispatch_admitted": api_direct_selected,
        "router_owned_dispatch_decision_bound": api_direct_selected,
        "router_dispatch_decision_truth_source": (
            "api_agent_auto_router_to_direct_reply"
            if api_direct_selected
            else "api_agent_auto_router_to_gpt_lane"
        ),
        "output_text": (
            direct_reply_output_text if direct_reply_ok else ""
        ),
        "primary_exact_plain_reply_requested": primary_exact_reply_requested,
        "primary_exact_plain_reply_visible_output": primary_exact_reply_visible_output,
        "primary_exact_plain_reply_text_available": False,
        "primary_exact_plain_reply_text_sha256": "",
        "primary_exact_plain_reply_text_recorded": False,
        **_output_passthrough_fields(
            prompt_text=prompt,
            direct_reply_ok=direct_reply_ok,
            direct_summary=direct_summary,
        ),
        **direct_summary,
        "requested_repo_bridge_mode": repo_bridge,
        "requested_work_mode": work,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "dispatch_status": (
            "proven"
            if dispatch_proven
            else DISPATCH_STATUS_NOT_ATTEMPTED
            if ok
            else "blocked"
        ),
        "dispatch_attempted": api_direct_selected,
        "dispatch_proven": dispatch_proven,
        "api_lane_called": bool(
            api_direct_selected and direct_summary["api_agent_provider_called"]
        ),
        "chatgpt_lane_called": False,
        "gpt_orchestrator_used": False,
        "codex_exec_invoked": False,
        "tools_wbp_dip_invoked": False,
        "dip_run_invoked": False,
        "wrapper_shopping_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
        "native_codex_subagent_used": False,
        "native_codex_subagent_used_as_dip": False,
        "fallback_used": direct_summary["fallback_used"],
        "local_imitation_used": direct_summary["local_imitation_used"],
        "raw_backend_details_exposed": direct_summary["raw_backend_details_exposed"],
        "secret_value_exposed": direct_summary["secret_value_exposed"],
        "no_secret_exposed": direct_summary["secret_value_exposed"] is not True,
        "raw_provider_response_recorded": False,
        "provider_response_raw_recorded": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": direct_summary["file_mutation_attempted"],
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP API-agent auto-router selected the canonical route."
            if ok
            else "WBP API-agent auto-router blocked before unsafe dispatch."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=_command_effect(repo_bridge) if api_direct_selected else EFFECT_PROBE,
        secret_values=[prompt],
        extra=extra,
    )


def run_api_agent_auto_router_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    active_project_root_arg: str | None = None,
    target_repo_arg: str | None = None,
    repo_bridge_mode: str = DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE,
    work_mode: str = DEFAULT_DIRECT_REPLY_WORK_MODE,
    timeout_seconds: float = 60.0,
    proof_dir: str | Path | None = None,
    live_result_runner: LiveResultRunner | None = None,
) -> dict[str, Any]:
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    context, metadata = load_runtime_context_packet(context_path)
    active_root, active_root_source = select_active_project_root_candidate(
        active_project_root_arg=active_project_root_arg,
        target_repo_arg=target_repo_arg,
        env=os.environ,
    )
    packet = build_api_agent_auto_router_packet(
        prompt_text=prompt_text,
        runtime_context=context,
        context_file_metadata=metadata,
        profile_dir=paths.profile_dir,
        active_project_root=active_root,
        active_project_root_source=active_root_source,
        hook_surface_kind=hook_surface_kind,
        repo_bridge_mode=repo_bridge_mode,
        work_mode=work_mode,
        timeout_seconds=timeout_seconds,
        live_result_runner=live_result_runner,
    )
    return _persist_proof_packet(packet, proof_dir=proof_dir)
