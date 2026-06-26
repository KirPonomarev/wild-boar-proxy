# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .active_project_root import (
    active_project_root_metadata,
    select_active_project_root_candidate,
    target_repo_fields_from_active_project_root,
)
from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .controlled_api_dispatch import build_controlled_api_dispatch_packet
from .core import packets
from .router_hook_entry import (
    HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import REPO_ROOT, RuntimePaths
from .runtime_dispatch_mode_truth import (
    DISPATCH_MODE_API_ONLY,
    EXECUTOR_API_ROUTE,
    ORCHESTRATOR_API_ROUTE,
    dispatch_mode_truth_fields,
)
from .wbp_dip_tool import (
    DEFAULT_LIVE_RESULT_TIMEOUT_SECONDS,
    DIP_WORK_MODES,
    REPO_BRIDGE_MODES,
    WBP_DIP_TOOL_OK,
    _repo_bridge_requested,
    request_live_result,
)


API_AGENT_DIRECT_REPLY_PACKET_KIND = "wbp_api_agent_direct_reply"
API_AGENT_DIRECT_REPLY_OK = "OK"
API_AGENT_DIRECT_REPLY_DISPATCH_NOT_PROVEN = (
    "WBP_API_AGENT_DIRECT_REPLY_DISPATCH_NOT_PROVEN"
)
API_AGENT_DIRECT_REPLY_UNAVAILABLE = "WBP_API_AGENT_DIRECT_REPLY_UNAVAILABLE"
API_AGENT_DIRECT_REPLY_FINAL_TOOL_CALL = "WBP_API_AGENT_DIRECT_REPLY_FINAL_TOOL_CALL"
API_AGENT_DIRECT_REPLY_UNSAFE = "WBP_API_AGENT_DIRECT_REPLY_UNSAFE"
API_AGENT_DIRECT_REPLY_UNSAFE_CHANGED_FILE_PATH = "unsafe_changed_file_path"

DEFAULT_DIRECT_REPLY_WORK_MODE = "standard"
DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE = "off"
DIRECT_REPLY_WORK_MODES = DIP_WORK_MODES
DIRECT_REPLY_REPO_BRIDGE_MODES = REPO_BRIDGE_MODES

LiveResultRunner = Callable[..., Mapping[str, Any]]


def _safe_text(value: object, *, limit: int = 4096) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_bool(value: object) -> bool:
    return value is True


def _live_result_bool(live_result: Mapping[str, Any], *field_names: str) -> bool:
    return any(live_result.get(field_name) is True for field_name in field_names)


def _normalize_work_mode(value: object) -> str:
    mode = _safe_text(value, limit=40)
    return mode if mode in DIP_WORK_MODES else DEFAULT_DIRECT_REPLY_WORK_MODE


def _normalize_repo_bridge_mode(value: object) -> str:
    mode = _safe_text(value, limit=40)
    return mode if mode in REPO_BRIDGE_MODES else DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE


def _looks_like_final_repo_tool_call(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, Mapping):
        return False
    raw_call = parsed.get("wbp_repo_tool_call") or parsed.get("tool_call")
    return isinstance(raw_call, Mapping)


def _provider_label_for_selected_route(
    runtime_context: Mapping[str, Any] | None,
    selected_slot: str,
) -> str:
    if not isinstance(runtime_context, Mapping):
        return ""
    agent_id_to_route = runtime_context.get("agent_id_to_route")
    route_providers = runtime_context.get("route_providers")
    if not isinstance(agent_id_to_route, Mapping) or not isinstance(
        route_providers,
        Mapping,
    ):
        return ""
    route_id = str(agent_id_to_route.get(selected_slot) or "")
    if not route_id:
        return ""
    return _safe_text(route_providers.get(route_id), limit=80)


def _result_text(live_result: Mapping[str, Any]) -> str:
    return str(live_result.get("result_text") or "").strip()


def _safe_mutated_file_paths(raw_paths: object) -> tuple[list[str], bool]:
    if not isinstance(raw_paths, list):
        return [], False
    paths: list[str] = []
    unsafe = False
    for raw_path in raw_paths:
        text = _safe_text(raw_path, limit=500)
        if not text:
            continue
        path = Path(text)
        if path.is_absolute() or ".." in path.parts:
            unsafe = True
            continue
        paths.append(text)
    return paths, unsafe


def _base_blocking_reasons(
    *,
    dispatch_packet: Mapping[str, Any],
    live_result: Mapping[str, Any],
    final_tool_call: bool,
) -> list[str]:
    reasons: list[str] = []
    if dispatch_packet.get("status") != "ok":
        reasons.append(
            str(
                dispatch_packet.get("machine_error_code")
                or API_AGENT_DIRECT_REPLY_DISPATCH_NOT_PROVEN
            )
        )
    if dispatch_packet.get("dispatch_proven") is not True:
        reasons.append("controlled_api_dispatch_not_proven")
    if live_result:
        if live_result.get("status") != "ok":
            reasons.append(
                str(
                    live_result.get("machine_error_code")
                    or API_AGENT_DIRECT_REPLY_UNAVAILABLE
                )
            )
        if live_result.get("provider_called") is not True:
            reasons.append("api_agent_provider_not_called")
        if live_result.get("result_available") is not True:
            reasons.append("api_agent_result_unavailable")
        if not _result_text(live_result):
            reasons.append("api_agent_result_text_empty")
        if live_result.get("fallback_used") is not False:
            reasons.append("fallback_used")
        if live_result.get("local_imitation_used") is not False:
            reasons.append("local_imitation_used")
        if live_result.get("raw_backend_details_exposed") is not False:
            reasons.append("raw_backend_details_exposed")
        if live_result.get("secret_value_exposed") is not False:
            reasons.append("secret_value_exposed")
    elif dispatch_packet.get("status") == "ok":
        reasons.append(API_AGENT_DIRECT_REPLY_UNAVAILABLE)
    if final_tool_call:
        reasons.append("final_answer_was_repo_tool_call")
    return [reason for reason in reasons if reason]


def build_api_agent_direct_reply_packet(
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
    timeout_seconds: float = DEFAULT_LIVE_RESULT_TIMEOUT_SECONDS,
    live_result_runner: LiveResultRunner | None = None,
) -> dict[str, Any]:
    prompt = str(prompt_text or "")
    safe_work_mode = _normalize_work_mode(work_mode)
    safe_repo_bridge_mode = _normalize_repo_bridge_mode(repo_bridge_mode)
    repo_bridge_required = _repo_bridge_requested(
        task=prompt,
        mode=safe_repo_bridge_mode,
    )
    command_effect = (
        EFFECT_PROBE if safe_repo_bridge_mode == "off" else EFFECT_MUTATE
    )
    dispatch_packet = build_controlled_api_dispatch_packet(
        prompt_text=prompt,
        runtime_context=runtime_context,
        hook_surface_kind=hook_surface_kind,
        context_file_metadata=context_file_metadata,
        secret_values=[prompt],
    )
    dispatch_proven = (
        dispatch_packet.get("status") == "ok"
        and dispatch_packet.get("dispatch_proven") is True
        and dispatch_packet.get("selected_alias_lane") == "api_route"
    )
    selected_active_project_root, active_root_fields = active_project_root_metadata(
        active_project_root,
        source=active_project_root_source,
        wbp_repo_root=REPO_ROOT,
        required=repo_bridge_required,
    )
    active_root_available = active_root_fields["active_project_root_available"] is True
    selected_alias = _safe_text(dispatch_packet.get("selected_alias"), limit=80)
    selected_slot = _safe_text(dispatch_packet.get("selected_slot"), limit=80)
    selected_lane = _safe_text(dispatch_packet.get("selected_alias_lane"), limit=40)
    reply_provider_label = _provider_label_for_selected_route(
        runtime_context,
        selected_slot,
    )

    live_result: Mapping[str, Any] = {}
    if dispatch_proven and selected_alias and (
        not repo_bridge_required or active_root_available
    ):
        runner = live_result_runner or request_live_result
        live_result = runner(
            task=prompt,
            expected_alias=selected_alias,
            profile_dir=profile_dir,
            repo_root=selected_active_project_root,
            target_repo_source=active_project_root_source,
            wbp_repo_root=REPO_ROOT,
            repo_bridge_mode=safe_repo_bridge_mode,
            dip_work_mode=safe_work_mode,
            timeout_seconds=timeout_seconds,
            runtime_context=runtime_context,
        )
    reply_text = _result_text(live_result)
    final_tool_call = _looks_like_final_repo_tool_call(reply_text)
    mutated_files, unsafe_mutated_file_path = _safe_mutated_file_paths(
        live_result.get("dip_action_mutated_files")
    )
    blocking_reasons = _base_blocking_reasons(
        dispatch_packet=dispatch_packet,
        live_result=live_result,
        final_tool_call=final_tool_call,
    )
    if repo_bridge_required and not active_root_available:
        blocking_reasons.append(str(active_root_fields["active_project_root_status"]))
    if unsafe_mutated_file_path:
        blocking_reasons.append(API_AGENT_DIRECT_REPLY_UNSAFE_CHANGED_FILE_PATH)
    ok = not blocking_reasons
    if ok:
        machine_error_code = API_AGENT_DIRECT_REPLY_OK
    elif not dispatch_proven:
        machine_error_code = str(
            dispatch_packet.get("parser_machine_error_code")
            or dispatch_packet.get("hook_entry_machine_error_code")
            or dispatch_packet.get("machine_error_code")
            or API_AGENT_DIRECT_REPLY_DISPATCH_NOT_PROVEN
        )
    elif repo_bridge_required and not active_root_available:
        machine_error_code = str(active_root_fields["active_project_root_status"])
    elif final_tool_call:
        machine_error_code = API_AGENT_DIRECT_REPLY_FINAL_TOOL_CALL
    elif any(
        reason
        in {
            "fallback_used",
            "local_imitation_used",
            "raw_backend_details_exposed",
            "secret_value_exposed",
            API_AGENT_DIRECT_REPLY_UNSAFE_CHANGED_FILE_PATH,
        }
        for reason in blocking_reasons
    ):
        machine_error_code = API_AGENT_DIRECT_REPLY_UNSAFE
    else:
        machine_error_code = str(
            live_result.get("machine_error_code")
            or API_AGENT_DIRECT_REPLY_UNAVAILABLE
        )
        if machine_error_code == WBP_DIP_TOOL_OK:
            machine_error_code = API_AGENT_DIRECT_REPLY_UNAVAILABLE

    target_repo_fields = target_repo_fields_from_active_project_root(active_root_fields)
    reply_text_recorded = bool(reply_text and not final_tool_call)
    file_mutation_attempted = bool(
        live_result.get("dip_action_mutation_applied") is True
        or live_result.get("dip_code_written") is True
        or mutated_files
    )
    reply_proof_summary = {
        "route_bound_dispatch_proven": _as_bool(
            dispatch_packet.get("route_bound_dispatch_proven")
        ),
        "controlled_dispatch_proven": _as_bool(dispatch_packet.get("dispatch_proven")),
        "api_agent_provider_called": _as_bool(live_result.get("provider_called")),
        "api_agent_response_observed": bool(
            live_result.get("provider_called") is True and reply_text_recorded
        ),
        "provider_response_proven": bool(
            live_result.get("provider_called") is True
            and live_result.get("result_available") is True
            and reply_text_recorded
        ),
        "final_answer_was_repo_tool_call": final_tool_call,
        "fallback_used": _as_bool(live_result.get("fallback_used")),
        "local_imitation_used": _as_bool(live_result.get("local_imitation_used")),
        "tools_wbp_dip_invoked": False,
        "dip_run_invoked": False,
        "codex_exec_invoked": False,
        "native_codex_subagent_used_as_dip": False,
    }
    extra = {
        "schema_version": 1,
        "packet_kind": API_AGENT_DIRECT_REPLY_PACKET_KIND,
        **dispatch_mode_truth_fields(
            execution_mode=DISPATCH_MODE_API_ONLY,
            truth_source=API_AGENT_DIRECT_REPLY_PACKET_KIND,
            orchestrator=ORCHESTRATOR_API_ROUTE,
            executor=EXECUTOR_API_ROUTE,
            mode_proven=ok,
            chatgpt_lane_selected=False,
            api_route_selected=dispatch_proven,
            chatgpt_lane_called=False,
            api_route_called=live_result.get("provider_called") is True,
            **active_root_fields,
        ),
        **target_repo_fields,
        "api_agent_direct_reply_packet": True,
        "api_agent_direct_reply_attempted": dispatch_proven,
        "api_agent_direct_reply_proven": ok,
        "api_agent_direct_reply_text_available": reply_text_recorded,
        "api_agent_direct_reply_text_recorded": reply_text_recorded,
        "output_text": reply_text if reply_text_recorded else "",
        "direct_reply_text": reply_text if reply_text_recorded else "",
        "direct_reply_text_sha256": _sha256_text(reply_text) if reply_text else "",
        "direct_reply_text_length": len(reply_text),
        "direct_reply_text_truncated": _as_bool(live_result.get("result_text_truncated")),
        "direct_api_reply_block": True,
        "reply_block_kind": "api_agent_direct_reply",
        "reply_author_alias": selected_alias,
        "reply_agent_id": selected_slot,
        "reply_lane": selected_lane or "api_route",
        "reply_provider_label": reply_provider_label,
        "reply_text": reply_text if reply_text_recorded else "",
        "reply_text_sha256": _sha256_text(reply_text) if reply_text else "",
        "reply_text_length": len(reply_text) if reply_text_recorded else 0,
        "reply_text_truncated": _as_bool(live_result.get("result_text_truncated")),
        "reply_proof_summary": reply_proof_summary,
        "final_answer_was_repo_tool_call": final_tool_call,
        "final_tool_call_blocked": final_tool_call,
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "prompt_digest_present": bool(prompt),
        "prompt_text_recorded": False,
        "raw_prompt_recorded": False,
        "natural_phrase_recorded": False,
        "runtime_context_file_required": True,
        "runtime_context_file_present": bool(
            (context_file_metadata or {}).get("runtime_context_file_present", False)
        ),
        "runtime_context_file_read": bool(
            (context_file_metadata or {}).get("runtime_context_file_read", False)
        ),
        "runtime_context_file_path_recorded": False,
        "runtime_context_source": _safe_text(
            dispatch_packet.get("runtime_context_source"),
            limit=120,
        ),
        "runtime_context_present": _as_bool(dispatch_packet.get("runtime_context_present")),
        "runtime_context_kind_valid": _as_bool(
            dispatch_packet.get("runtime_context_kind_valid")
        ),
        "alias_context_read": _as_bool(dispatch_packet.get("alias_context_read")),
        "natural_alias_command_detected": _as_bool(
            dispatch_packet.get("natural_alias_command_detected")
        ),
        "natural_api_alias_command_detected": _as_bool(
            dispatch_packet.get("natural_api_alias_command_detected")
        ),
        "selected_alias": selected_alias,
        "selected_slot": selected_slot,
        "selected_alias_lane": selected_lane,
        "selected_api_route_id_present": _as_bool(
            dispatch_packet.get("selected_api_route_id_present")
        ),
        "selected_api_route_id_sha256": _safe_text(
            dispatch_packet.get("selected_api_route_id_sha256"),
            limit=80,
        ),
        "selected_api_route_id_recorded": False,
        "selected_route_id_allowed": _as_bool(
            dispatch_packet.get("selected_route_id_allowed")
        ),
        "allowed_api_route_ids_enforced": _as_bool(
            dispatch_packet.get("allowed_api_route_ids_enforced")
        ),
        "forbidden_stale_route_ids_count": int(
            dispatch_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "forbidden_stale_route_ids_enforced": bool(
            int(dispatch_packet.get("forbidden_stale_route_ids_count") or 0) > 0
        ),
        "route_bound_dispatch_attempted": _as_bool(
            dispatch_packet.get("route_bound_dispatch_attempted")
        ),
        "route_bound_dispatch_proven": _as_bool(
            dispatch_packet.get("route_bound_dispatch_proven")
        ),
        "controlled_dispatch_packet_kind": _safe_text(
            dispatch_packet.get("packet_kind"),
            limit=80,
        ),
        "controlled_dispatch_proven": _as_bool(dispatch_packet.get("dispatch_proven")),
        "api_agent_live_result_source": _safe_text(live_result.get("source"), limit=80),
        "api_agent_provider_called": _as_bool(live_result.get("provider_called")),
        "api_agent_response_observed": bool(
            live_result.get("provider_called") is True and reply_text
        ),
        "provider_response_proven": bool(
            live_result.get("provider_called") is True
            and live_result.get("result_available") is True
            and reply_text
        ),
        "direct_provider_auth_proven": _as_bool(
            live_result.get("direct_provider_auth_proven")
        ),
        "direct_provider_response_observed": _as_bool(
            live_result.get("direct_provider_response_observed")
        ),
        "provider_auth_ok": _as_bool(live_result.get("provider_auth_ok")),
        "positive_provider_proof_gate_satisfied": _as_bool(
            live_result.get("positive_provider_proof_gate_satisfied")
        ),
        "runtime_context_bridge_used": _as_bool(
            live_result.get("runtime_context_bridge_used")
        ),
        "runtime_context_file_bridge_used": _as_bool(
            live_result.get("runtime_context_file_bridge_used")
        ),
        "bridge_or_file_bridge_used": _as_bool(
            live_result.get("bridge_or_file_bridge_used")
        ),
        "network_dependent": bool(
            live_result.get("provider_called") is True
            and live_result.get("bridge_or_file_bridge_used") is not True
        ),
        "exact_plain_reply_fast_path": _as_bool(
            live_result.get("exact_plain_reply_fast_path")
        ),
        "exact_plain_reply_file_bridge_skipped": _as_bool(
            live_result.get("exact_plain_reply_file_bridge_skipped")
        ),
        "exact_plain_reply_matched": _as_bool(
            live_result.get("exact_plain_reply_matched")
        ),
        "exact_plain_reply_expected_text_sha256": _safe_text(
            live_result.get("exact_plain_reply_expected_text_sha256"),
            limit=80,
        ),
        "exact_plain_reply_expected_text_recorded": _as_bool(
            live_result.get("exact_plain_reply_expected_text_recorded")
        ),
        "exact_plain_reply_observed_text_sha256": _safe_text(
            live_result.get("exact_plain_reply_observed_text_sha256"),
            limit=80,
        ),
        "exact_plain_reply_observed_text_recorded": _as_bool(
            live_result.get("exact_plain_reply_observed_text_recorded")
        ),
        "file_bridge_attempted": _as_bool(live_result.get("file_bridge_attempted")),
        "file_bridge_skipped": _as_bool(live_result.get("file_bridge_skipped")),
        "dip_work_mode": _safe_text(
            live_result.get("dip_work_mode") or safe_work_mode,
            limit=40,
        ),
        "dip_full_work_mode": _as_bool(live_result.get("dip_full_work_mode"))
        or safe_work_mode == "full",
        "repo_bridge_mode": safe_repo_bridge_mode,
        "repo_bridge_required": _live_result_bool(
            live_result,
            "repo_bridge_required",
            "dip_repo_tool_bridge_required",
        ),
        "repo_bridge_available": _live_result_bool(
            live_result,
            "repo_bridge_available",
            "dip_repo_tool_bridge_available",
        ),
        "repo_bridge_used": _live_result_bool(
            live_result,
            "repo_bridge_used",
            "dip_repo_tool_bridge_used",
        ),
        "dip_repo_tool_bridge_required": _live_result_bool(
            live_result,
            "dip_repo_tool_bridge_required",
            "repo_bridge_required",
        ),
        "dip_repo_tool_bridge_available": _live_result_bool(
            live_result,
            "dip_repo_tool_bridge_available",
            "repo_bridge_available",
        ),
        "dip_repo_tool_bridge_used": _live_result_bool(
            live_result,
            "dip_repo_tool_bridge_used",
            "repo_bridge_used",
        ),
        "dip_repo_direct_access": _as_bool(live_result.get("dip_repo_direct_access")),
        "repo_bridge_context_pack_used": _as_bool(
            live_result.get("repo_bridge_context_pack_used")
        ),
        "repo_bridge_context_pack_recorded": _as_bool(
            live_result.get("repo_bridge_context_pack_recorded")
        ),
        "repo_bridge_readonly": _as_bool(live_result.get("repo_bridge_readonly")),
        "repo_bridge_mutation_allowed": _as_bool(
            live_result.get("repo_bridge_mutation_allowed")
        ),
        "repo_bridge_mutation_controlled": _as_bool(
            live_result.get("repo_bridge_mutation_controlled")
        ),
        "repo_bridge_bootstrap_used": _as_bool(
            live_result.get("repo_bridge_bootstrap_used")
        ),
        "repo_bridge_bootstrap_tool_call_count": int(
            live_result.get("repo_bridge_bootstrap_tool_call_count") or 0
        ),
        "repo_bridge_tool_call_count": int(
            live_result.get("repo_bridge_tool_call_count") or 0
        ),
        "repo_bridge_successful_tool_call_count": int(
            live_result.get("repo_bridge_successful_tool_call_count") or 0
        ),
        "repo_bridge_raw_tool_results_recorded": _as_bool(
            live_result.get("repo_bridge_raw_tool_results_recorded")
        ),
        "dip_action_bridge_required": _as_bool(
            live_result.get("dip_action_bridge_required")
        ),
        "dip_action_bridge_used": _as_bool(live_result.get("dip_action_bridge_used")),
        "dip_action_mutation_applied": _as_bool(
            live_result.get("dip_action_mutation_applied")
        ),
        "dip_code_mutation_required": _as_bool(
            live_result.get("dip_code_mutation_required")
        ),
        "dip_code_written": _as_bool(live_result.get("dip_code_written")),
        "dip_code_verified": _as_bool(live_result.get("dip_code_verified")),
        "dip_action_mutated_files": mutated_files,
        "repo_bridge_final_answer_required": _live_result_bool(
            live_result,
            "repo_bridge_required",
            "dip_repo_tool_bridge_required",
        ),
        "repo_bridge_final_answer_received": bool(reply_text_recorded),
        "live_result_text_limit": int(live_result.get("live_result_text_limit") or 0),
        "live_result_output_token_limit": int(
            live_result.get("live_result_output_token_limit") or 0
        ),
        "blocking_reasons": blocking_reasons,
        "dispatch_status": "proven" if ok else "blocked",
        "dispatch_attempted": dispatch_proven,
        "dispatch_proven": ok,
        "api_lane_called": _as_bool(live_result.get("provider_called")),
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
        "fallback_used": _as_bool(live_result.get("fallback_used")),
        "local_imitation_used": _as_bool(live_result.get("local_imitation_used")),
        "raw_backend_details_exposed": _as_bool(
            live_result.get("raw_backend_details_exposed")
        ),
        "secret_value_exposed": _as_bool(live_result.get("secret_value_exposed")),
        "no_secret_exposed": live_result.get("secret_value_exposed") is not True,
        "raw_provider_response_recorded": False,
        "provider_response_raw_recorded": False,
        "provider_response_text_recorded": reply_text_recorded,
        "provider_response_preview_recorded": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": file_mutation_attempted,
        "changed_files": mutated_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP direct API-agent reply observed a route-bound provider answer."
            if ok
            else "WBP direct API-agent reply blocked before a safe final answer."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "retry",
        changed_files=mutated_files,
        effect=command_effect,
        secret_values=[prompt],
        extra=extra,
    )


def run_api_agent_direct_reply_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runtime_context_file: str | None = None,
    hook_surface_kind: str = HOOK_SURFACE_LOCAL_PROOF_COMMAND,
    active_project_root_arg: str | None = None,
    target_repo_arg: str | None = None,
    repo_bridge_mode: str = DEFAULT_DIRECT_REPLY_REPO_BRIDGE_MODE,
    work_mode: str = DEFAULT_DIRECT_REPLY_WORK_MODE,
    timeout_seconds: float = DEFAULT_LIVE_RESULT_TIMEOUT_SECONDS,
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
    return build_api_agent_direct_reply_packet(
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
