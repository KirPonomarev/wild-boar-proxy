# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import os
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_PROBE
from .core import packets
from .natural_intent_contract import (
    INTENT_PASS,
    PREFLIGHT_PASS,
    SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
    build_natural_intent_parser_packet,
)
from .real_custom_dip_proof_runner import (
    REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK,
    run_real_custom_dip_proof_runner_command,
)
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths
from .user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    build_user_prompt_submit_readiness_packet,
    expected_hook_trusted_hash,
    hook_command_for_paths,
)
from .wbp_dip_tool import DEFAULT_MODEL, DEFAULT_SANDBOX, default_codex_bin


REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND = "wbp_real_custom_dip_operator_preflight"
REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND = "wbp_real_custom_dip_operator_work"

REAL_CUSTOM_DIP_OPERATOR_OK = "OK"
REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED = (
    "WBP_REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED"
)
REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED = "WBP_REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED"
REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET = "WBP_REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET"

OPERATOR_STATUS_READY = "ready"
OPERATOR_STATUS_BLOCKED = "blocked"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""
    return ""


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _safe_changed_files(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _runtime_secret_values(context: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(context, Mapping):
        return []
    values: list[str] = []
    for key in ("allowed_api_route_ids", "forbidden_stale_route_ids"):
        raw = context.get(key)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend(item for item in raw if isinstance(item, str) and item)
    for key in ("agent_id_to_route",):
        raw_map = context.get(key)
        if isinstance(raw_map, Mapping):
            values.extend(
                item for item in raw_map.values() if isinstance(item, str) and item
            )
    raw_bindings = context.get("agent_bindings")
    if isinstance(raw_bindings, Sequence) and not isinstance(raw_bindings, (str, bytes)):
        for raw_binding in raw_bindings:
            if isinstance(raw_binding, Mapping):
                route = raw_binding.get("route_id")
                if isinstance(route, str) and route:
                    values.append(route)
    return sorted(set(values))


def _repo_root_from_cwd(codex_cwd: str | None) -> Path:
    if codex_cwd:
        return Path(codex_cwd).expanduser().resolve()
    return Path.cwd().resolve()


def _codex_executable(paths: RuntimePaths, codex_bin: str | None) -> Path:
    if codex_bin:
        return Path(codex_bin).expanduser()
    return default_codex_bin({"WBP_PROFILE_DIR": str(paths.profile_dir)})


def _writable_existing_ancestor(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.exists() and os.access(candidate, os.W_OK | os.X_OK)


def _proof_output_parent_writable(paths: RuntimePaths, proof_dir: str | None) -> bool:
    if proof_dir:
        target = Path(proof_dir).expanduser()
        if target.exists():
            return target.is_dir() and os.access(target, os.W_OK | os.X_OK)
        return _writable_existing_ancestor(target.parent)
    target = paths.managed_dir / "codex-runner" / "real-custom-dip-proof"
    if target.exists():
        return target.is_dir() and os.access(target, os.W_OK | os.X_OK)
    return _writable_existing_ancestor(target.parent)


def _hook_ready(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == HOOK_CONFIG_OK
        and packet.get("hook_enabled") is True
        and packet.get("hook_trusted") is True
        and packet.get("hook_config_digest_bound") is True
    )


def _preflight_blocking_reasons(
    *,
    prompt_present: bool,
    context_metadata: Mapping[str, Any],
    intent_packet: Mapping[str, Any],
    hook_readiness_packet: Mapping[str, Any],
    codex_binary_executable: bool,
    wbp_dip_tool_present: bool,
    proof_output_writable: bool,
) -> list[str]:
    reasons: list[str] = []
    if not prompt_present:
        reasons.append("prompt_required")
    if context_metadata.get("runtime_context_file_read") is not True:
        reasons.append("runtime_context_file_not_read")
    if context_metadata.get("runtime_context_file_valid_json") is not True:
        reasons.append("runtime_context_file_json_not_valid")
    if context_metadata.get("runtime_context_file_mapping") is not True:
        reasons.append("runtime_context_file_not_mapping")
    if intent_packet.get("status") != "ok":
        reasons.append("natural_intent_preflight_blocked")
    reasons.extend(_safe_reasons(intent_packet.get("blocking_reasons")))
    if not _hook_ready(hook_readiness_packet):
        reasons.append("user_prompt_submit_hook_not_ready")
    reasons.extend(_safe_reasons(hook_readiness_packet.get("blocking_reasons")))
    if not codex_binary_executable:
        reasons.append("codex_binary_not_executable")
    if not wbp_dip_tool_present:
        reasons.append("wbp_dip_tool_missing")
    if not proof_output_writable:
        reasons.append("proof_output_not_writable")
    return sorted(set(reasons))


def build_real_custom_dip_operator_preflight_packet(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    context_path = runtime_context_path(paths=paths)
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    secret_values = [prompt] if prompt else []
    secret_values.extend(_runtime_secret_values(runtime_context))
    intent_packet = build_natural_intent_parser_packet(
        prompt_text=prompt,
        runtime_context=runtime_context,
        source_surface=SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
        secret_values=secret_values,
    )
    explicit_hook_hash = _safe_text(codex_hook_current_hash, limit=80)
    hook_hash = (
        explicit_hook_hash
        if explicit_hook_hash
        else ""
        if probe_codex_app_server
        else expected_hook_trusted_hash(hook_command_for_paths(paths))
    )
    hook_readiness = build_user_prompt_submit_readiness_packet(
        paths=paths,
        codex_hook_current_hash=hook_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    codex_exe = _codex_executable(paths, codex_bin)
    repo_root = _repo_root_from_cwd(codex_cwd)
    codex_binary_executable = codex_exe.is_file() and os.access(codex_exe, os.X_OK)
    wbp_dip_tool_present = (repo_root / "tools" / "wbp_dip").is_file()
    proof_output_writable = _proof_output_parent_writable(paths, proof_dir)
    blocking_reasons = _preflight_blocking_reasons(
        prompt_present=bool(prompt),
        context_metadata=context_metadata,
        intent_packet=intent_packet,
        hook_readiness_packet=hook_readiness,
        codex_binary_executable=codex_binary_executable,
        wbp_dip_tool_present=wbp_dip_tool_present,
        proof_output_writable=proof_output_writable,
    )
    preflight_ready = not blocking_reasons
    unsafe_payload = {
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "runtime_context_digest": _sha256_file(context_path),
        "selected_alias": intent_packet.get("alias_candidate"),
        "slot_candidate": intent_packet.get("slot_candidate"),
        "intent_status": intent_packet.get("intent_status"),
        "hook_readiness_machine_error_code": hook_readiness.get("machine_error_code"),
        "blocking_reasons": blocking_reasons,
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=secret_values,
    )
    ok = preflight_ready and not unsafe
    machine_error_code = (
        REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET
        if unsafe
        else REAL_CUSTOM_DIP_OPERATOR_OK
        if ok
        else REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED
    )
    selected_alias = _safe_text(intent_packet.get("alias_candidate"), limit=80)
    extra = {
        **dict(context_metadata),
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
        "proof_scope": "real_custom_dip_operator_command_surface_preflight",
        "operator_command_surface": "wild-boar-proxy dip preflight",
        "operator_command_mode": "preflight",
        "operator_status": OPERATOR_STATUS_READY if ok else OPERATOR_STATUS_BLOCKED,
        "preflight_ready": ok,
        "blocked": not ok,
        "reason_codes": sorted(
            set(
                blocking_reasons
                + (["operator_preflight_packet_secret_leak"] if unsafe else [])
            )
        ),
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "prompt_digest_present": bool(prompt),
        "runtime_context_digest": _sha256_file(context_path),
        "runtime_context_file_path_recorded": False,
        "natural_intent_packet_kind": _safe_text(
            intent_packet.get("packet_kind"),
            limit=96,
        ),
        "natural_intent_status": _safe_text(
            intent_packet.get("intent_status"),
            limit=96,
        ),
        "natural_intent_preflight_status": _safe_text(
            intent_packet.get("contract_preflight_status"),
            limit=96,
        ),
        "natural_intent_passed": intent_packet.get("intent_status") == INTENT_PASS,
        "natural_intent_contract_preflight_passed": (
            intent_packet.get("contract_preflight_status") == PREFLIGHT_PASS
        ),
        "parser_used": intent_packet.get("parser_used") is True,
        "parser_selected_alias_from_runtime_context": (
            intent_packet.get("parser_selected_alias_from_runtime_context") is True
        ),
        "ambiguous_intent": intent_packet.get("ambiguous_intent") is True,
        "selected_alias": selected_alias,
        "selected_alias_present": bool(selected_alias),
        "selected_slot": _safe_text(intent_packet.get("slot_candidate"), limit=80),
        "selected_lane": _safe_text(intent_packet.get("lane_candidate"), limit=80),
        "alias_bound": intent_packet.get("alias_bound") is True,
        "alias_context_read": intent_packet.get("alias_context_read") is True,
        "route_id_allowed": intent_packet.get("route_id_allowed") is True,
        "allowed_api_route_ids_enforced": (
            intent_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_count": int(
            intent_packet.get("allowed_api_route_ids_count") or 0
        ),
        "forbidden_stale_route_ids_enforced": (
            intent_packet.get("forbidden_stale_route_ids_enforced") is True
        ),
        "forbidden_stale_route_ids_count": int(
            intent_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "user_prompt_submit_hook_ready": _hook_ready(hook_readiness),
        "hook_readiness_machine_error_code": _safe_text(
            hook_readiness.get("machine_error_code"),
            limit=128,
        ),
        "hook_readiness_status": _safe_text(hook_readiness.get("status"), limit=32),
        "hook_enabled": hook_readiness.get("hook_enabled") is True,
        "hook_trusted": hook_readiness.get("hook_trusted") is True,
        "hook_config_digest_bound": (
            hook_readiness.get("hook_config_digest_bound") is True
        ),
        "codex_binary_executable": codex_binary_executable,
        "codex_binary_path_recorded": False,
        "wbp_dip_tool_present": wbp_dip_tool_present,
        "repo_root_path_recorded": False,
        "proof_output_writable": proof_output_writable,
        "proof_dir_path_recorded": False,
        "provider_preflight_called": False,
        "provider_lane_preflight_is_dispatch_proof": False,
        "work_runner_called": False,
        "api_lane_called": False,
        "dispatch_proven": False,
        "work_mode_proven": False,
        "single_work_run_proven": False,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "custom_codex_flow_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "file_mutation_attempted": False,
        "blocking_reasons": sorted(
            set(
                blocking_reasons
                + (["operator_preflight_packet_secret_leak"] if unsafe else [])
            )
        ),
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP DIP operator preflight is ready; no dispatch was attempted."
            if ok
            else "WBP DIP operator preflight is BLOCKED; no dispatch was attempted."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=secret_values,
        extra=extra,
    )


def run_real_custom_dip_operator_preflight_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    return build_real_custom_dip_operator_preflight_packet(
        paths=paths,
        prompt_text=prompt_text,
        codex_bin=codex_bin,
        proof_dir=proof_dir,
        codex_cwd=codex_cwd,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )


def build_real_custom_dip_operator_work_packet(
    *,
    prompt_text: object,
    preflight_packet: Mapping[str, Any],
    runner_packet: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    runner = dict(runner_packet or {})
    runner_called = bool(runner)
    preflight_ready = preflight_packet.get("preflight_ready") is True
    runner_ok = bool(
        runner_called
        and runner.get("status") == "ok"
        and runner.get("machine_error_code") == "OK"
        and runner.get("operator_command_mode") == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK
        and runner.get("work_mode_proven") is True
        and runner.get("single_work_run_proven") is True
        and runner.get("api_lane_called") is True
        and runner.get("fallback_used") is False
        and runner.get("local_imitation_used") is False
        and runner.get("native_codex_subagent_used_as_dip") is False
        and runner.get("product_ready") is False
    )
    unsafe_payload = {
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND,
        "prompt_digest": _sha256_text(_safe_text(prompt_text, limit=4096))
        if _safe_text(prompt_text, limit=4096)
        else "",
        "preflight_machine_error_code": preflight_packet.get("machine_error_code"),
        "runner_machine_error_code": runner.get("machine_error_code"),
        "runner_changed_files_count": len(_safe_changed_files(runner.get("changed_files"))),
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values or []),
    )
    ok = bool(preflight_ready and runner_ok and not unsafe)
    blocking_reasons = sorted(
        set(
            (
                []
                if preflight_ready
                else ["preflight_not_ready"]
                + _safe_reasons(preflight_packet.get("blocking_reasons"))
            )
            + ([] if runner_ok or not runner_called else ["runner_work_not_proven"])
            + _safe_reasons(runner.get("blocking_reasons"))
            + (["operator_work_packet_secret_leak"] if unsafe else [])
        )
    )
    runner_machine_error = _safe_text(runner.get("machine_error_code"), limit=128)
    machine_error_code = (
        REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET
        if unsafe
        else REAL_CUSTOM_DIP_OPERATOR_OK
        if ok
        else runner_machine_error
        if runner_called and runner_machine_error and runner_machine_error != "OK"
        else REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED
    )
    changed_files = _safe_changed_files(runner.get("changed_files")) if runner_called else []
    extra = {
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND,
        "proof_scope": "real_custom_dip_operator_command_surface_work",
        "operator_command_surface": "wild-boar-proxy dip work",
        "operator_command_mode": "work",
        "operator_status": OPERATOR_STATUS_READY if ok else OPERATOR_STATUS_BLOCKED,
        "work_ready": ok,
        "blocked": not ok,
        "reason_codes": blocking_reasons,
        "preflight_checked": True,
        "preflight_ready": preflight_ready,
        "preflight_packet_kind": _safe_text(
            preflight_packet.get("packet_kind"),
            limit=96,
        ),
        "preflight_machine_error_code": _safe_text(
            preflight_packet.get("machine_error_code"),
            limit=128,
        ),
        "selected_alias": _safe_text(preflight_packet.get("selected_alias"), limit=80),
        "selected_alias_present": preflight_packet.get("selected_alias_present") is True,
        "selected_slot": _safe_text(preflight_packet.get("selected_slot"), limit=80),
        "selected_lane": _safe_text(preflight_packet.get("selected_lane"), limit=80),
        "runner_called": runner_called,
        "runner_packet_kind": _safe_text(runner.get("packet_kind"), limit=96),
        "runner_machine_error_code": runner_machine_error,
        "runner_status": _safe_text(runner.get("status"), limit=32),
        "runner_changed_files_count": len(changed_files),
        "evidence_changed_files_count": len(changed_files),
        "runner_required_run_count": int(runner.get("required_run_count") or 0),
        "runner_run_count": int(runner.get("run_count") or 0),
        "work_mode_proven": ok,
        "single_work_run_proven": bool(ok and runner.get("single_work_run_proven") is True),
        "work_mode_cannot_mint_admission_proof": True,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "real_custom_codex_hook_origin_dip_proof_proven": False,
        "two_runs_proven": False,
        "custom_codex_flow_proven": bool(
            ok and runner.get("custom_codex_flow_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and runner.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": bool(
            ok and runner.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and runner.get("hook_runtime_context_digest_bound") is True
        ),
        "delegate_to_dip_proven": bool(ok and runner.get("delegate_to_dip_proven") is True),
        "api_lane_called": bool(ok and runner.get("api_lane_called") is True),
        "route_bound_dispatch_proven": bool(
            ok and runner.get("route_bound_dispatch_proven") is True
        ),
        "live_result_available": bool(ok and runner.get("live_result_available") is True),
        "direct_provider_auth_proven": bool(
            ok and runner.get("direct_provider_auth_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and runner.get("codex_working_flow_delivery_proven") is True
        ),
        "approved_delivery_surface_proven": bool(
            ok and runner.get("approved_delivery_surface_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": bool(
            ok and runner.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP DIP operator work command completed with proof-backed live dispatch."
            if ok
            else "WBP DIP operator work command is BLOCKED."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_real_custom_dip_operator_work_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = 300,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    context_path = runtime_context_path(paths=paths)
    runtime_context, _context_metadata = load_runtime_context_packet(context_path)
    secret_values = [prompt] if prompt else []
    secret_values.extend(_runtime_secret_values(runtime_context))
    preflight = build_real_custom_dip_operator_preflight_packet(
        paths=paths,
        prompt_text=prompt,
        codex_bin=codex_bin,
        proof_dir=proof_dir,
        codex_cwd=codex_cwd,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    if preflight.get("preflight_ready") is not True:
        return build_real_custom_dip_operator_work_packet(
            prompt_text=prompt,
            preflight_packet=preflight,
            runner_packet=None,
            secret_values=secret_values,
        )
    runner_packet = run_real_custom_dip_proof_runner_command(
        paths=paths,
        prompt_text=prompt,
        codex_bin=codex_bin,
        codex_model=codex_model or DEFAULT_MODEL,
        proof_dir=proof_dir,
        codex_cwd=codex_cwd,
        expected_alias=str(preflight.get("selected_alias") or "DIP"),
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
        run_mode=REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK,
    )
    return build_real_custom_dip_operator_work_packet(
        prompt_text=prompt,
        preflight_packet=preflight,
        runner_packet=runner_packet,
        secret_values=secret_values,
    )
