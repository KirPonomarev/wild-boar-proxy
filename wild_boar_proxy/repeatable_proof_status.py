# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .external_models.paths import ExternalModelsPaths
from .external_models.validate import check_route_provider_once_no_write
from .fresh_sealed_e2e_proof import FRESH_SEALED_E2E_PACKET_KIND
from .proof_seal import sha256_file
from .router_hook_entry import (
    _safe_text,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimeErrorInfo, RuntimePaths
from .user_prompt_submit_hook_producer import build_user_prompt_submit_readiness_packet


REPEATABLE_PROOF_STATUS_PACKET_KIND = "wbp_repeatable_proof_status"

REPEATABLE_PROOF_STATUS_OK = "OK"
REPEATABLE_PROOF_STATUS_PROOF_ONLY = "WBP_REPEATABLE_PROOF_STATUS_PROOF_ONLY"
REPEATABLE_PROOF_STATUS_BLOCKED = "WBP_REPEATABLE_PROOF_STATUS_BLOCKED"
REPEATABLE_PROOF_STATUS_UNSAFE_PACKET = "WBP_REPEATABLE_PROOF_STATUS_UNSAFE_PACKET"

OPERATOR_STATUS_ROUTER_READY = "router_ready"
OPERATOR_STATUS_PROOF_ONLY = "proof_only"
OPERATOR_STATUS_BLOCKED = "blocked"

DEFAULT_PROVIDER_PREFLIGHT_MARKER = "WBP_REPEATABLE_PROOF_PREFLIGHT_OK"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_json_mapping(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "fresh_proof_file_required": False,
        "fresh_proof_file_present": path.is_file(),
        "fresh_proof_file_read": False,
        "fresh_proof_file_valid_json": False,
        "fresh_proof_file_mapping": False,
        "fresh_proof_file_path_recorded": False,
        "fresh_proof_file_error_code": "",
    }
    if not path.is_file():
        metadata["fresh_proof_file_error_code"] = "fresh_proof_file_missing"
        return {}, metadata
    try:
        parsed = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        metadata["fresh_proof_file_error_code"] = "fresh_proof_file_unreadable"
        return {}, metadata
    try:
        payload = json.loads(parsed)
    except ValueError:
        metadata["fresh_proof_file_error_code"] = "fresh_proof_file_invalid_json"
        return {}, metadata
    metadata["fresh_proof_file_read"] = True
    metadata["fresh_proof_file_valid_json"] = True
    if not isinstance(payload, Mapping):
        metadata["fresh_proof_file_error_code"] = "fresh_proof_file_not_mapping"
        return {}, metadata
    metadata["fresh_proof_file_mapping"] = True
    return dict(payload), metadata


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _allowed_route_ids(context: Mapping[str, Any]) -> list[str]:
    allowed = context.get("allowed_api_route_ids")
    if not isinstance(allowed, Sequence) or isinstance(allowed, (str, bytes)):
        return []
    return sorted({route for route in allowed if isinstance(route, str) and route})


def _runtime_secret_values(context: Mapping[str, Any]) -> list[str]:
    values = list(_allowed_route_ids(context))
    agent_routes = context.get("agent_id_to_route")
    if isinstance(agent_routes, Mapping):
        values.extend(route for route in agent_routes.values() if isinstance(route, str) and route)
    return sorted(set(values))


def _fresh_proof_ok(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("packet_kind") == FRESH_SEALED_E2E_PACKET_KIND
        and packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("fresh_sealed_e2e_proven") is True
        and packet.get("user_prompt_submit_hook_ran") is True
        and packet.get("api_lane_called") is True
        and packet.get("dispatch_proven") is True
        and packet.get("full_runtime_diagnostics_passed") is True
        and packet.get("native_custom_codex_visible_flow_proven") is True
        and packet.get("fallback_used") is False
        and packet.get("local_imitation_used") is False
        and packet.get("native_codex_subagent_used_as_dip") is False
        and packet.get("product_ready") is False
        and packet.get("blocking_reasons") in ([], ())
    )


def _fresh_proof_failures(packet: Mapping[str, Any], metadata: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if metadata.get("fresh_proof_file_present") is not True:
        failures.append("fresh_proof_file_missing")
    if metadata.get("fresh_proof_file_present") is True and metadata.get("fresh_proof_file_read") is not True:
        failures.append("fresh_proof_file_not_read")
    if metadata.get("fresh_proof_file_present") is True and metadata.get("fresh_proof_file_valid_json") is not True:
        failures.append("fresh_proof_file_json_not_valid")
    if metadata.get("fresh_proof_file_present") is True and metadata.get("fresh_proof_file_mapping") is not True:
        failures.append("fresh_proof_file_not_mapping")
    if not packet:
        return sorted(set(failures + ["fresh_proof_not_proven"]))
    checks = {
        "fresh_sealed_e2e_proven": "fresh_sealed_e2e_not_proven",
        "user_prompt_submit_hook_ran": "fresh_proof_hook_not_run",
        "api_lane_called": "fresh_proof_api_lane_not_called",
        "dispatch_proven": "fresh_proof_dispatch_not_proven",
        "full_runtime_diagnostics_passed": "fresh_proof_full_runtime_diagnostics_not_passed",
        "native_custom_codex_visible_flow_proven": "fresh_proof_native_visible_flow_not_proven",
    }
    if packet.get("packet_kind") != FRESH_SEALED_E2E_PACKET_KIND:
        failures.append("fresh_proof_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("fresh_proof_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("fresh_proof_machine_error_not_ok")
    for field, reason in checks.items():
        if packet.get(field) is not True:
            failures.append(reason)
    for field, reason in {
        "fallback_used": "fresh_proof_fallback_used",
        "local_imitation_used": "fresh_proof_local_imitation_used",
        "native_codex_subagent_used_as_dip": "fresh_proof_native_subagent_used_as_dip",
        "product_ready": "fresh_proof_product_ready_overclaim",
    }.items():
        if packet.get(field) is not False:
            failures.append(reason)
    failures.extend(_safe_reasons(packet.get("blocking_reasons")))
    return sorted(set(failures))


def _hook_ready(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("hook_enabled") is True
        and packet.get("hook_config_present") is True
        and packet.get("hook_config_digest_bound") is True
        and packet.get("hook_script_executable") is True
        and packet.get("hook_trusted") is True
        and packet.get("product_ready") is False
    )


def _provider_preflight_packet(
    *,
    route_id: str,
    expected_text: str,
    run_provider_preflight: bool,
    external_models_paths: ExternalModelsPaths | None = None,
) -> tuple[dict[str, Any], list[str]]:
    if not run_provider_preflight:
        return {
            "provider_lane_preflight_attempted": False,
            "provider_lane_available": False,
            "provider_lane_machine_error_code": "",
            "provider_lane_expected_text_observed": False,
            "provider_lane_expected_text_exact": False,
            "provider_lane_network_dependent": False,
            "provider_lane_runtime_context_bridge_used": False,
            "provider_lane_runtime_context_file_bridge_used": False,
            "provider_lane_fallback_used": False,
            "provider_lane_request_count": 0,
            "provider_lane_latency_ms": 0,
            "provider_lane_response_preview_recorded": False,
        }, ["provider_lane_preflight_not_attempted"]
    try:
        data = check_route_provider_once_no_write(
            external_models_paths or ExternalModelsPaths.from_env(),
            route_id,
            user_prompt=f"Answer exactly one line: {expected_text}",
            expected_text=expected_text,
        )
    except RuntimeErrorInfo as exc:
        return {
            "provider_lane_preflight_attempted": True,
            "provider_lane_available": False,
            "provider_lane_machine_error_code": _safe_text(
                exc.machine_error_code,
                limit=96,
            ),
            "provider_lane_expected_text_observed": False,
            "provider_lane_expected_text_exact": False,
            "provider_lane_network_dependent": True,
            "provider_lane_runtime_context_bridge_used": False,
            "provider_lane_runtime_context_file_bridge_used": False,
            "provider_lane_fallback_used": False,
            "provider_lane_request_count": 0,
            "provider_lane_latency_ms": 0,
            "provider_lane_response_preview_recorded": False,
        }, ["provider_lane_preflight_failed"]
    expected_observed = data.get("expected_text_observed") is True
    response_text_length = int(data.get("response_text_length") or 0)
    expected_exact = bool(expected_observed and response_text_length == len(expected_text))
    available = bool(
        data.get("check_kind") == "api_only_live_route_format"
        and data.get("route_state") == "live_response_observed_no_write"
        and expected_exact
        and data.get("fallback_used") is False
    )
    return {
        "provider_lane_preflight_attempted": True,
        "provider_lane_available": available,
        "provider_lane_machine_error_code": "OK" if available else "provider_lane_unexpected_response",
        "provider_lane_expected_text_observed": expected_observed,
        "provider_lane_expected_text_exact": expected_exact,
        "provider_lane_network_dependent": data.get("network_dependent") is True,
        "provider_lane_runtime_context_bridge_used": data.get("runtime_context_bridge_used") is True,
        "provider_lane_runtime_context_file_bridge_used": data.get("runtime_context_file_bridge_used") is True,
        "provider_lane_fallback_used": data.get("fallback_used") is True,
        "provider_lane_request_count": int(data.get("request_count") or 0),
        "provider_lane_latency_ms": int(data.get("latency_ms") or 0),
        "provider_lane_response_preview_recorded": False,
    }, [] if available else ["provider_lane_preflight_failed"]


def build_repeatable_proof_status_packet(
    *,
    runtime_context: Mapping[str, Any] | None,
    runtime_context_metadata: Mapping[str, Any] | None,
    runtime_context_file: Path | None = None,
    route_id: str,
    route_id_allowed: bool,
    hook_readiness_packet: Mapping[str, Any] | None,
    provider_preflight: Mapping[str, Any] | None,
    provider_failures: Sequence[str],
    fresh_proof_packet: Mapping[str, Any] | None,
    fresh_proof_metadata: Mapping[str, Any] | None,
    fresh_proof_file: Path | None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    context = dict(runtime_context or {})
    context_metadata = dict(runtime_context_metadata or {})
    hook = dict(hook_readiness_packet or {})
    provider = dict(provider_preflight or {})
    fresh = dict(fresh_proof_packet or {})
    fresh_metadata = dict(fresh_proof_metadata or {})
    allowed_routes = _allowed_route_ids(context)
    route_digest = _sha256_text(route_id) if route_id else ""
    hook_is_ready = _hook_ready(hook)
    provider_available = bool(
        route_id_allowed
        and provider.get("provider_lane_available") is True
        and provider.get("provider_lane_fallback_used") is False
    )
    fresh_ok = _fresh_proof_ok(fresh)
    fresh_failures = _fresh_proof_failures(fresh, fresh_metadata)
    readiness_failures: list[str] = []
    if context_metadata.get("runtime_context_file_read") is not True:
        readiness_failures.append("runtime_context_file_not_read")
    if context_metadata.get("runtime_context_file_valid_json") is not True:
        readiness_failures.append("runtime_context_file_json_not_valid")
    if context_metadata.get("runtime_context_file_mapping") is not True:
        readiness_failures.append("runtime_context_file_not_mapping")
    if not route_id:
        readiness_failures.append("route_id_missing")
    if route_id and not route_id_allowed:
        readiness_failures.append("route_id_not_allowed_by_runtime_context")
    if not hook_is_ready:
        readiness_failures.append("user_prompt_submit_hook_not_ready")
    readiness_failures.extend(_safe_reasons(hook.get("blocking_reasons")))
    if not provider_available:
        readiness_failures.extend(provider_failures)
        if route_id_allowed and provider.get("provider_lane_preflight_attempted") is True:
            readiness_failures.append("provider_lane_not_available")
    if provider_available and not fresh_ok:
        readiness_failures.append("provider_health_ok_not_feature_ready")

    router_ready = bool(fresh_ok and hook_is_ready and provider_available)
    proof_only = bool(fresh_ok and not router_ready)
    operator_status = (
        OPERATOR_STATUS_ROUTER_READY
        if router_ready
        else OPERATOR_STATUS_PROOF_ONLY
        if proof_only
        else OPERATOR_STATUS_BLOCKED
    )
    unsafe_payload = {
        "packet_kind": REPEATABLE_PROOF_STATUS_PACKET_KIND,
        "route_id_sha256": route_digest,
        "fresh_proof_sha256": sha256_file(fresh_proof_file) if fresh_proof_file else "",
        "provider_lane_machine_error_code": provider.get("provider_lane_machine_error_code"),
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values or []),
    )
    blocking_reasons = sorted(
        set(
            (["repeatable_proof_status_packet_secret_leak"] if unsafe else [])
            + ([] if fresh_ok else fresh_failures)
            + readiness_failures
        )
    )
    ok = bool(not unsafe and operator_status == OPERATOR_STATUS_ROUTER_READY)
    machine_error_code = (
        REPEATABLE_PROOF_STATUS_UNSAFE_PACKET
        if unsafe
        else REPEATABLE_PROOF_STATUS_OK
        if ok
        else REPEATABLE_PROOF_STATUS_PROOF_ONLY
        if operator_status == OPERATOR_STATUS_PROOF_ONLY
        else REPEATABLE_PROOF_STATUS_BLOCKED
    )
    extra = {
        **context_metadata,
        "schema_version": 1,
        "packet_kind": REPEATABLE_PROOF_STATUS_PACKET_KIND,
        "proof_scope": "repeatable_runtime_proof_status",
        "operator_status": operator_status,
        "router_ready": router_ready,
        "proof_only": proof_only,
        "blocked": operator_status == OPERATOR_STATUS_BLOCKED,
        "reason_codes": blocking_reasons,
        "runtime_context_digest": sha256_file(
            runtime_context_file
        )
        if runtime_context_file is not None
        and context_metadata.get("runtime_context_file_present") is True
        else "",
        "runtime_context_file_path_recorded": False,
        "route_id_allowed": route_id_allowed,
        "route_id_sha256": route_digest,
        "route_id_recorded": False,
        "allowed_api_route_ids_count": len(allowed_routes),
        "hook_readiness_checked": bool(hook),
        "user_prompt_submit_hook_ready": hook_is_ready,
        "hook_readiness_machine_error_code": _safe_text(
            hook.get("machine_error_code"),
            limit=96,
        ),
        "hook_readiness_product_ready": hook.get("product_ready") is True,
        "provider_health_ok": provider_available,
        "provider_health_ok_not_feature_ready": bool(provider_available and not fresh_ok),
        "provider_lane_preflight_is_dispatch_proof": False,
        **provider,
        "fresh_proof_checked": bool(fresh_metadata.get("fresh_proof_file_present")),
        "fresh_proof_file_present": fresh_metadata.get("fresh_proof_file_present") is True,
        "fresh_proof_file_read": fresh_metadata.get("fresh_proof_file_read") is True,
        "fresh_proof_file_valid_json": fresh_metadata.get("fresh_proof_file_valid_json") is True,
        "fresh_proof_file_mapping": fresh_metadata.get("fresh_proof_file_mapping") is True,
        "fresh_proof_file_path_recorded": False,
        "last_fresh_proof_digest": sha256_file(fresh_proof_file) if fresh_proof_file else "",
        "last_fresh_proof_started_at_ns": int(fresh.get("proof_run_started_at_ns") or 0),
        "fresh_sealed_e2e_proven": fresh_ok,
        "full_runtime_diagnostics_passed": fresh.get("full_runtime_diagnostics_passed") is True,
        "native_custom_codex_visible_flow_proven": fresh.get("native_custom_codex_visible_flow_proven") is True,
        "api_lane_called": fresh.get("api_lane_called") is True,
        "dispatch_proven": fresh.get("dispatch_proven") is True,
        "user_prompt_submit_hook_ran": fresh.get("user_prompt_submit_hook_ran") is True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "custom_codex_ui_visibility_product_ready": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "expected_text_sha256": _sha256_text(str(secret_values[0])) if secret_values else "",
        "expected_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP repeatable proof path is router-ready."
            if router_ready
            else "WBP repeatable proof evidence is proof-only, not product-ready."
            if proof_only
            else "WBP repeatable proof path is blocked before fresh runtime proof."
        ),
        machine_error_code=machine_error_code,
        liveness="network_dependent"
        if provider.get("provider_lane_preflight_attempted") is True
        else "not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_repeatable_proof_status_command(
    *,
    paths: RuntimePaths,
    route_id: str,
    fresh_proof_file: str | None = None,
    provider_expected_text: str = DEFAULT_PROVIDER_PREFLIGHT_MARKER,
    run_provider_preflight: bool = False,
    external_models_dir: str | None = None,
    codex_hook_current_hash: str = "",
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    context_path = runtime_context_path(paths=paths, runtime_context_file=None)
    context, context_metadata = load_runtime_context_packet(context_path)
    route_allowed = bool(route_id and route_id in _allowed_route_ids(context))
    hook_packet = build_user_prompt_submit_readiness_packet(
        paths=paths,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    provider_packet, provider_failures = _provider_preflight_packet(
        route_id=route_id,
        expected_text=provider_expected_text,
        run_provider_preflight=run_provider_preflight and route_allowed,
        external_models_paths=ExternalModelsPaths.from_root(Path(external_models_dir).expanduser())
        if external_models_dir
        else None,
    )
    if run_provider_preflight and not route_allowed:
        provider_failures = ["provider_lane_route_not_allowed_by_runtime_context"]
    proof_path = Path(fresh_proof_file).expanduser() if fresh_proof_file else Path("")
    fresh_packet: dict[str, Any] = {}
    fresh_metadata: dict[str, Any] = {
        "fresh_proof_file_required": False,
        "fresh_proof_file_present": False,
        "fresh_proof_file_read": False,
        "fresh_proof_file_valid_json": False,
        "fresh_proof_file_mapping": False,
        "fresh_proof_file_path_recorded": False,
        "fresh_proof_file_error_code": "fresh_proof_file_not_supplied",
    }
    if fresh_proof_file:
        fresh_packet, fresh_metadata = _read_json_mapping(proof_path)
    secret_values = [provider_expected_text, route_id] + _runtime_secret_values(context)
    return build_repeatable_proof_status_packet(
        runtime_context=context,
        runtime_context_metadata=context_metadata,
        runtime_context_file=context_path,
        route_id=route_id,
        route_id_allowed=route_allowed,
        hook_readiness_packet=hook_packet,
        provider_preflight=provider_packet,
        provider_failures=provider_failures,
        fresh_proof_packet=fresh_packet,
        fresh_proof_metadata=fresh_metadata,
        fresh_proof_file=proof_path if fresh_proof_file else None,
        secret_values=secret_values,
    )
