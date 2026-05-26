# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Model availability packets for bounded WBP direct smoke."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


MODEL_AVAILABILITY_SCHEMA_VERSION = 1
SAMPLE_LIMIT = 5
DEFAULT_VALIDATION_MAX_AGE_SECONDS = 24 * 60 * 60
CANONICAL_SAMPLE_ORDER = (
    "gpt-5.4-mini",
    "gpt-5.4",
    "gpt-5.5",
)
FAILURE_CAUSES = {
    "none",
    "wbp_runtime_unavailable",
    "route_not_found",
    "model_not_listed",
    "account_auth_failed",
    "quota_or_rate_limit",
    "upstream_model_rejected",
    "provider_error",
    "response_shape_error",
    "timeout",
    "unknown",
}
MODEL_FORBIDDEN_BROWSER_FIELDS = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "path",
    "provider",
    "route_id",
    "backend_id",
    "base_url",
    "wire_api",
    "model_provider",
    "http_proxy",
    "https_proxy",
    "all_proxy",
}
FORBIDDEN_MODEL_CLAIMS = (
    "all_models_work",
    "GPT-5.5_works_without_own_packet",
    "native_Custom_works",
    "Codex.app_accepted_model",
    "Codex_CLI_accepted_model",
    "direct_egress_absent",
    "account_pool_valid",
    "streaming_compatible",
    "tool_loop_compatible",
    "model_catalog_proves_model_access",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_utc_timestamp(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_age_seconds(observed_at_utc: str, captured_at_utc: str) -> int | None:
    observed = _parse_utc_timestamp(observed_at_utc)
    captured = _parse_utc_timestamp(captured_at_utc)
    if observed is None or captured is None:
        return None
    return max(0, int((captured - observed).total_seconds()))


def forbidden_model_browser_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in MODEL_FORBIDDEN_BROWSER_FIELDS:
                findings.append(key_path)
            findings.extend(forbidden_model_browser_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_model_browser_fields(value, f"{prefix}[{index}]"))
    return findings


def build_layer_boundary_packet() -> dict[str, Any]:
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_availability_layer_boundary",
        "captured_at_utc": utc_now(),
        "status": "ok",
        "proves_model_availability_only": True,
        "native_app_usability_proven": False,
        "codex_cli_acceptance_proven": False,
        "direct_egress_absence_proven": False,
        "filesystem_safety_proven": False,
        "original_codex_reversibility_proven": False,
        "auth_strategy_reproved": False,
        "account_promotion_allowed": False,
        "wire_fidelity_repair_allowed": False,
        "final_e2e_proven": False,
    }


def build_no_route_account_mutation_packet(
    *,
    route_snapshot_before: dict[str, Any] | None = None,
    route_snapshot_after: dict[str, Any] | None = None,
    account_snapshot_before: dict[str, Any] | None = None,
    account_snapshot_after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route_before_hash = sha256_text(str(route_snapshot_before or {}))
    route_after_hash = sha256_text(str(route_snapshot_after or route_snapshot_before or {}))
    account_before_hash = sha256_text(str(account_snapshot_before or {}))
    account_after_hash = sha256_text(str(account_snapshot_after or account_snapshot_before or {}))
    route_mutated = route_before_hash != route_after_hash
    account_mutated = account_before_hash != account_after_hash
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "route_account_mutation_guard",
        "captured_at_utc": utc_now(),
        "status": "blocked" if route_mutated or account_mutated else "ok",
        "route_account_mutation_allowed": False,
        "route_snapshot_before_hash": route_before_hash,
        "route_snapshot_after_hash": route_after_hash,
        "account_snapshot_before_hash": account_before_hash,
        "account_snapshot_after_hash": account_after_hash,
        "route_mutated": route_mutated,
        "account_mutated": account_mutated,
        "active_route_changed": False,
        "default_model_changed": False,
        "account_promoted": False,
    }


def build_validation_freshness_packet(
    *,
    observed_at_utc: str,
    validation_actor: str,
    validation_scope: str,
    captured_at_utc: str | None = None,
    max_age_seconds: int = DEFAULT_VALIDATION_MAX_AGE_SECONDS,
    revalidation_triggers: list[str] | None = None,
) -> dict[str, Any]:
    captured = captured_at_utc or utc_now()
    age_seconds = _safe_age_seconds(observed_at_utc, captured)
    missing_or_invalid_timestamp = age_seconds is None
    stale = missing_or_invalid_timestamp or age_seconds > max_age_seconds
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "validation_freshness",
        "captured_at_utc": captured,
        "status": "blocked" if stale else "ok",
        "machine_error_code": "STALE_VALIDATION" if stale else "OK",
        "validation_timestamp": observed_at_utc,
        "validation_actor": validation_actor,
        "validation_route_model_scope": validation_scope,
        "maximum_allowed_validation_age_seconds": max_age_seconds,
        "validation_age_seconds": age_seconds,
        "stale_validation_used_as_current_truth": False,
        "current_truth_allowed": not stale,
        "revalidation_trigger_policy": revalidation_triggers
        or ["401", "403", "429", "503", "explicit_route_or_account_change", "long_pause_before_live_contour"],
        "mandatory_revalidation_after": ["401", "403", "429", "503"],
    }


def _catalog_model_rows(catalog_packet: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not isinstance(catalog_packet, dict):
        return rows
    models = catalog_packet.get("models")
    if not isinstance(models, list):
        return rows
    for entry in models:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("model_id") or "").strip()
        if not model_id:
            continue
        rows[model_id] = {
            "display_model_id": str(entry.get("label") or model_id),
            "wbp_model_id": model_id,
            "catalog_model_id": model_id,
            "route_id": "",
            "route_provider": str(entry.get("provider_class") or ""),
            "upstream_model": model_id,
            "account_or_backend_id": "server_owned_unexposed",
            "selection_source": str(entry.get("source") or "catalog"),
            "server_issued": entry.get("server_issued") is True,
        }
    return rows


def _route_model_rows(routes_packet: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not isinstance(routes_packet, dict):
        return rows
    data = routes_packet.get("data") if isinstance(routes_packet.get("data"), dict) else routes_packet
    routes = data.get("routes") if isinstance(data, dict) else None
    if not isinstance(routes, list):
        return rows
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        if not route_id:
            continue
        provider = route.get("provider") if isinstance(route.get("provider"), dict) else {}
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        rows[route_id] = {
            "display_model_id": route_id,
            "wbp_model_id": route_id,
            "catalog_model_id": route_id,
            "route_id": route_id,
            "route_provider": str(provider.get("id") or provider.get("kind") or "external_route"),
            "upstream_model": str(route.get("upstream_model") or ""),
            "account_or_backend_id": "secret_ref_present" if str(auth.get("secret_ref") or "").strip() else "",
            "selection_source": "external_route",
            "server_issued": route.get("enabled") is True and bool(str(auth.get("secret_ref") or "").strip()),
        }
    return rows


def build_model_id_normalization_packet(
    *,
    candidate_packet: dict[str, Any],
    catalog_packet: dict[str, Any] | None = None,
    routes_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_ids = candidate_packet.get("candidate_model_ids")
    if not isinstance(candidate_ids, list):
        candidate_ids = []
    catalog_rows = _catalog_model_rows(catalog_packet)
    route_rows = _route_model_rows(routes_packet)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw_model_id in candidate_ids:
        model_id = str(raw_model_id)
        row = route_rows.get(model_id) or catalog_rows.get(model_id)
        if row is None:
            missing.append(model_id)
            row = {
                "display_model_id": model_id,
                "wbp_model_id": model_id,
                "catalog_model_id": "",
                "route_id": "",
                "route_provider": "",
                "upstream_model": "",
                "account_or_backend_id": "",
                "selection_source": "unknown",
                "server_issued": False,
            }
        rows.append(row)
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_id_normalization",
        "captured_at_utc": utc_now(),
        "status": "ok" if not missing and rows else "blocked",
        "candidate_count": len(candidate_ids),
        "normalized_count": len(rows),
        "missing_model_ids": missing,
        "browser_authority": False,
        "raw_secret_recorded": False,
        "rows": rows,
    }


def build_runtime_readiness_packet(
    status_packet: dict[str, Any] | None,
    health_packet: dict[str, Any] | None,
) -> dict[str, Any]:
    status_packet = status_packet if isinstance(status_packet, dict) else {}
    health_packet = health_packet if isinstance(health_packet, dict) else {}
    launch_readiness = (
        health_packet.get("launch_readiness")
        if isinstance(health_packet.get("launch_readiness"), dict)
        else {}
    )
    endpoint = str(health_packet.get("endpoint") or status_packet.get("endpoint") or "")
    gate_passed = launch_readiness.get("gate_passed") is True
    listener_ready = launch_readiness.get("listener_reachable") is True
    responses_ready = launch_readiness.get("responses_proof_passed") is True
    models_ready = launch_readiness.get("models_surface_reachable") is True
    ready = bool(endpoint) and gate_passed and listener_ready and responses_ready and models_ready
    failed_checks: list[str] = []
    if not endpoint:
        failed_checks.append("endpoint_missing")
    if not gate_passed:
        failed_checks.append("launch_readiness_gate_not_passed")
    if not listener_ready:
        failed_checks.append("listener_not_ready")
    if not models_ready:
        failed_checks.append("models_surface_not_ready")
    if not responses_ready:
        failed_checks.append("responses_surface_not_ready")
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "runtime_readiness",
        "captured_at_utc": utc_now(),
        "status": "ok" if ready else "blocked",
        "machine_error_code": "OK" if ready else "RUNTIME_NOT_READY",
        "endpoint": endpoint,
        "configured_model": str(
            health_packet.get("configured_model") or status_packet.get("configured_model") or ""
        ),
        "liveness": str(health_packet.get("liveness") or status_packet.get("liveness") or ""),
        "runtime_ready": ready,
        "listener_reachable": listener_ready,
        "models_surface_reachable": models_ready,
        "responses_proof_passed": responses_ready,
        "truth_alignment_passed": launch_readiness.get("truth_alignment_passed") is True,
        "claim_gate_status": (
            status_packet.get("claim_gate", {}).get("status")
            if isinstance(status_packet.get("claim_gate"), dict)
            else "not_reported"
        ),
        "claim_gate_blocks_account_pool_claim": True,
        "account_pool_health_proven": False,
        "failed_checks": failed_checks,
    }


def _catalog_ids(catalog_packet: dict[str, Any] | None) -> list[str]:
    if not isinstance(catalog_packet, dict):
        return []
    models = catalog_packet.get("models")
    if not isinstance(models, list):
        return []
    ids: list[str] = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        model_id = str(entry.get("model_id") or "").strip()
        if model_id and entry.get("server_issued") is True:
            ids.append(model_id)
    return sorted(dict.fromkeys(ids))


def _external_route_ids(routes_packet: dict[str, Any] | None) -> list[str]:
    if not isinstance(routes_packet, dict):
        return []
    data = routes_packet.get("data")
    if not isinstance(data, dict):
        return []
    routes = data.get("routes")
    if not isinstance(routes, list):
        return []
    ids: list[str] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("route_id") or "").strip()
        auth = route.get("auth") if isinstance(route.get("auth"), dict) else {}
        if route_id and route.get("enabled") is True and str(auth.get("secret_ref") or "").strip():
            ids.append(route_id)
    return sorted(dict.fromkeys(ids))


def build_candidate_model_list(
    *,
    configured_model: str,
    catalog_packet: dict[str, Any] | None,
    routes_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog_ids = _catalog_ids(catalog_packet)
    route_ids = _external_route_ids(routes_packet)
    server_ids = sorted(dict.fromkeys([*catalog_ids, *route_ids]))
    selected: list[str] = []
    if configured_model and configured_model in server_ids:
        selected.append(configured_model)
    for model_id in CANONICAL_SAMPLE_ORDER:
        if model_id in server_ids and model_id not in selected:
            selected.append(model_id)
    for route_id in route_ids:
        if route_id not in selected:
            selected.append(route_id)
            break
    selected = selected[:SAMPLE_LIMIT]
    return {
        "packet_kind": "candidate_model_list",
        "captured_at_utc": utc_now(),
        "status": "ok" if selected else "blocked",
        "machine_error_code": "OK" if selected else "NO_SERVER_ISSUED_CANDIDATES",
        "sampling_limit": SAMPLE_LIMIT,
        "server_issued_model_ids": server_ids,
        "configured_model": configured_model,
        "candidate_model_ids": selected,
        "candidate_count": len(selected),
        "all_model_sweep_attempted": False,
        "browser_authority": False,
    }


def classify_failure_cause(
    *,
    http_status: int | None,
    machine_error_code: str = "",
    error_type: str = "",
    runtime_ready: bool = True,
    route_selected: bool = True,
    listed: bool = True,
) -> str:
    code = (machine_error_code or "").upper()
    error = (error_type or "").lower()
    if not runtime_ready:
        return "wbp_runtime_unavailable"
    if not listed:
        return "model_not_listed"
    if not route_selected:
        return "route_not_found"
    if http_status in {401, 403} or "auth" in code or "unauthorized" in error or "forbidden" in error:
        return "account_auth_failed"
    if http_status == 429 or "quota" in code or "rate" in code or "rate_limit" in error:
        return "quota_or_rate_limit"
    if http_status == 404 or "model_not" in code or "model" in error and "not" in error:
        return "upstream_model_rejected"
    if http_status == 408 or "timeout" in code or "timeout" in error:
        return "timeout"
    if http_status is not None and 500 <= http_status <= 599:
        return "provider_error"
    if "shape" in code or "schema" in code:
        return "response_shape_error"
    return "unknown"


def classify_response_shape(response_payload: dict[str, Any] | None) -> bool:
    if not isinstance(response_payload, dict):
        return False
    if isinstance(response_payload.get("output_text"), str):
        return True
    output = response_payload.get("output")
    if isinstance(output, list):
        return True
    if response_payload.get("status") == "completed":
        return True
    return False


def build_model_direct_preflight_packet(
    *,
    model_id: str,
    source: str,
    listed: bool,
    selectable: bool,
    route_selected: bool,
    runtime_ready: bool,
    http_status: int | None = None,
    upstream_status: int | None = None,
    response_payload: dict[str, Any] | None = None,
    error_payload: dict[str, Any] | None = None,
    prompt_text: str = "",
    request_sent_to_wbp: bool = False,
    wbp_trace_id: str = "",
) -> dict[str, Any]:
    response_json = str(response_payload or error_payload or "")
    response_shape_ok = classify_response_shape(response_payload)
    status_ok = request_sent_to_wbp and http_status is not None and 200 <= http_status < 300 and response_shape_ok
    error = error_payload.get("error") if isinstance(error_payload, dict) else None
    error_type = str(error.get("type") if isinstance(error, dict) else "")
    machine_error_code = str(error_payload.get("machine_error_code") if isinstance(error_payload, dict) else "")
    failure_cause = "none" if status_ok else classify_failure_cause(
        http_status=http_status,
        machine_error_code=machine_error_code,
        error_type=error_type,
        runtime_ready=runtime_ready,
        route_selected=route_selected,
        listed=listed,
    )
    allowed_claim = (
        f"MODEL_{model_id}_DIRECT_WBP_NON_STREAM_PROVEN"
        if status_ok
        else f"MODEL_{model_id}_LISTED_ONLY"
        if listed and not request_sent_to_wbp
        else f"MODEL_{model_id}_BLOCKED_OR_UNKNOWN"
    )
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_direct_preflight",
        "captured_at_utc": utc_now(),
        "model_id": model_id,
        "source": source,
        "listed": listed,
        "selectable": selectable,
        "route_selected": route_selected,
        "request_sent_to_wbp": request_sent_to_wbp,
        "wbp_trace_id": wbp_trace_id,
        "direct_preflight_status": "passed" if status_ok else "blocked_or_unknown",
        "http_status": http_status,
        "upstream_status": upstream_status,
        "request_reaches_wbp": request_sent_to_wbp,
        "upstream_accepts": upstream_status is not None and 200 <= upstream_status < 300,
        "response_accepted_by_codex": False,
        "codex_acceptance_status": "not_tested",
        "wbp_response_shape_classified": response_shape_ok,
        "response_body_hash": sha256_text(response_json) if response_json else "",
        "response_text_hash": sha256_text(str(response_payload.get("output_text") or "")) if isinstance(response_payload, dict) and response_payload.get("output_text") else "",
        "prompt_hash": sha256_text(prompt_text) if prompt_text else "",
        "prompt_body_recorded": False,
        "auth_header_recorded": False,
        "error_shape_classified": isinstance(error_payload, dict),
        "failure_cause": failure_cause,
        "streaming_tested": False,
        "tool_loop_tested": False,
        "streaming_classified": "live_not_tested",
        "tool_loop_classified": "live_not_tested",
        "native_tested": False,
        "codex_cli_tested": False,
        "direct_egress_tested": False,
        "owner_ui_tested": False,
        "account_health_proven": False,
        "allowed_claim": allowed_claim,
        "forbidden_claims": list(FORBIDDEN_MODEL_CLAIMS),
    }


def build_model_availability_matrix(
    model_packets: list[dict[str, Any]],
    *,
    candidate_packet: dict[str, Any],
    runtime_packet: dict[str, Any],
) -> dict[str, Any]:
    overclaims = []
    for packet in model_packets:
        for field in (
            "native_tested",
            "codex_cli_tested",
            "direct_egress_tested",
            "owner_ui_tested",
            "account_health_proven",
            "response_accepted_by_codex",
            "streaming_tested",
            "tool_loop_tested",
        ):
            if packet.get(field) is not False:
                overclaims.append(f"{packet.get('model_id')}.{field}")
        if packet.get("failure_cause") not in FAILURE_CAUSES:
            overclaims.append(f"{packet.get('model_id')}.failure_cause")
    passed = [packet["model_id"] for packet in model_packets if packet.get("direct_preflight_status") == "passed"]
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_availability_matrix",
        "captured_at_utc": utc_now(),
        "status": "ok" if not overclaims and model_packets else "blocked",
        "machine_error_code": "OK" if not overclaims and model_packets else "MODEL_AVAILABILITY_BLOCKED",
        "target_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        "runtime_ready": runtime_packet.get("runtime_ready") is True,
        "candidate_count": candidate_packet.get("candidate_count", 0),
        "sampling_limit": candidate_packet.get("sampling_limit", SAMPLE_LIMIT),
        "all_model_sweep_attempted": False,
        "models_tested": [packet.get("model_id") for packet in model_packets],
        "direct_wbp_non_stream_passed_models": passed,
        "gpt_5_5_claim": _claim_for_model(model_packets, "gpt-5.5"),
        "native_launch_attempted": False,
        "codex_cli_tested": False,
        "direct_egress_absence_proven": False,
        "account_pool_health_proven": False,
        "streaming_compatible": False,
        "tool_loop_compatible": False,
        "codex_acceptance_proven": False,
        "forbidden_claims": list(FORBIDDEN_MODEL_CLAIMS),
        "overclaim_findings": overclaims,
        "models": model_packets,
    }


def _claim_for_model(model_packets: list[dict[str, Any]], model_id: str) -> str:
    for packet in model_packets:
        if packet.get("model_id") != model_id:
            continue
        if packet.get("direct_preflight_status") == "passed":
            return "own_packet_direct_wbp_non_stream_proven"
        if packet.get("listed") is True:
            return "own_packet_listed_but_not_proven"
        return "own_packet_blocked_or_unknown"
    return "absent_or_not_sampled"


def validate_model_availability_matrix(packet: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if packet.get("schema_version") != MODEL_AVAILABILITY_SCHEMA_VERSION:
        findings.append("schema_version")
    if packet.get("all_model_sweep_attempted") is not False:
        findings.append("all_model_sweep_attempted")
    for field in (
        "native_launch_attempted",
        "codex_cli_tested",
        "direct_egress_absence_proven",
        "account_pool_health_proven",
        "streaming_compatible",
        "tool_loop_compatible",
    ):
        if packet.get(field) is not False:
            findings.append(field)
    models = packet.get("models")
    if not isinstance(models, list) or not models:
        findings.append("models")
        return findings
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            findings.append(f"models[{index}]")
            continue
        if not model.get("model_id"):
            findings.append(f"models[{index}].model_id")
        if model.get("failure_cause") not in FAILURE_CAUSES:
            findings.append(f"models[{index}].failure_cause")
        for field in (
            "native_tested",
            "codex_cli_tested",
            "direct_egress_tested",
            "owner_ui_tested",
            "account_health_proven",
            "response_accepted_by_codex",
        ):
            if model.get(field) is not False:
                findings.append(f"models[{index}].{field}")
    findings.extend(str(item) for item in packet.get("overclaim_findings", []))
    return sorted(set(findings))


def build_model_availability_false_green_audit(
    *,
    matrix_packet: dict[str, Any],
    freshness_packet: dict[str, Any],
    layer_boundary_packet: dict[str, Any],
    mutation_guard_packet: dict[str, Any],
    normalization_packet: dict[str, Any],
) -> dict[str, Any]:
    findings: list[str] = []
    if validate_model_availability_matrix(matrix_packet):
        findings.append("matrix_validation_failed")
    if freshness_packet.get("stale_validation_used_as_current_truth") is not False:
        findings.append("stale_validation_used_as_current_truth")
    if layer_boundary_packet.get("native_app_usability_proven") is not False:
        findings.append("native_layer_overclaim")
    if matrix_packet.get("codex_acceptance_proven") is not False:
        findings.append("codex_acceptance_overclaim")
    if matrix_packet.get("all_model_sweep_attempted") is not False:
        findings.append("all_model_sweep_overclaim")
    if mutation_guard_packet.get("status") != "ok":
        findings.append("route_or_account_mutation")
    if normalization_packet.get("status") != "ok":
        findings.append("model_id_normalization_incomplete")
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_availability_false_green_audit",
        "captured_at_utc": utc_now(),
        "status": "blocked" if findings else "ok",
        "findings": findings,
        "all_models_work_claimed": False,
        "gpt_5_5_claim_without_own_packet": False,
        "catalog_presence_counted_as_availability": False,
        "direct_wbp_200_counted_as_codex_acceptance": False,
        "native_launch_claimed": False,
        "codex_cli_claimed": False,
        "direct_egress_claimed": False,
        "streaming_claimed": False,
        "tool_loop_claimed": False,
        "account_pool_health_claimed": False,
    }
