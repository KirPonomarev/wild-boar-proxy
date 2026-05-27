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
ROUTE_FAMILIES = {
    "codex_native_account_route",
    "wbp_api_external_route",
    "local_fixture_route",
    "unknown_unrouted",
}
AVAILABILITY_LEVELS = {
    "listed",
    "selectable",
    "request_reaches_wbp",
    "route_selected",
    "upstream_accepts",
    "direct_wbp_non_stream_response_shape_accepted",
    "response_accepted_by_codex",
    "streaming_classified",
    "tool_loop_classified",
    "blocked_by_host_environment",
    "failed",
}
CATALOG_AVAILABILITY_CLAIM_LEVELS = {
    "listed_not_live_proven",
    "direct_wbp_non_stream_response_accepted",
    "historically_direct_wbp_non_stream_response_accepted",
}
CATALOG_AVAILABILITY_EVIDENCE_SCOPES = {
    "current_operator_catalog_only",
    "current_thread_direct_wbp_non_stream",
    "pass2_selected_external_route_closed_truth",
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
MODEL_AVAILABILITY_R1_REQUIRED_PACKETS = (
    "sync_gate_packet.json",
    "historical_dirt_quarantine_packet.json",
    "declared_write_surfaces_packet.json",
    "version_pinning_packet.json",
    "model_candidate_discovery_packet.json",
    "candidate_partition_packet.json",
    "default_model_source_packet.json",
    "route_family_classification_packet.json",
    "model_availability_admission_packet.json",
    "validation_freshness_packet.json",
    "external_route_admission_packet.json",
    "model_availability_matrix.json",
    "model_claims_matrix.json",
    "model_availability_false_green_audit.json",
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
        "proof_transport": "direct_wbp_http_non_stream",
        "direct_only_contour": True,
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
        "previous_matrix_import_allowed_as_current_truth": False,
        "live_native_launch_allowed": False,
        "live_codex_cli_launch_allowed": False,
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
            "route_family": "wbp_api_external_route",
            "server_issued": route.get("enabled") is True and bool(str(auth.get("secret_ref") or "").strip()),
            "secret_ref_present": bool(str(auth.get("secret_ref") or "").strip()),
            "adapter_id": str(route.get("adapter_id") or provider.get("adapter_id") or "external_route_responses_adapter"),
        }
    return rows


def infer_route_family(*, model_id: str, source: str = "", row: dict[str, Any] | None = None) -> str:
    if isinstance(row, dict):
        family = str(row.get("route_family") or "").strip()
        if family in ROUTE_FAMILIES:
            return family
        if str(row.get("selection_source") or "") == "external_route":
            return "wbp_api_external_route"
    source_text = str(source or "").lower()
    if "fixture" in source_text:
        return "local_fixture_route"
    if "external_route" in source_text or model_id.startswith("wbp:") or model_id.startswith("wbp-"):
        return "wbp_api_external_route"
    if model_id.startswith("gpt-"):
        return "codex_native_account_route"
    return "unknown_unrouted"


def build_route_family_classification_packet(
    *,
    candidate_packet: dict[str, Any],
    normalization_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_ids = candidate_packet.get("candidate_model_ids")
    if not isinstance(candidate_ids, list):
        candidate_ids = []
    rows_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(normalization_packet, dict):
        rows = normalization_packet.get("rows")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    model_id = str(row.get("wbp_model_id") or row.get("display_model_id") or "")
                    if model_id:
                        rows_by_id[model_id] = row
    classifications: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw_model_id in candidate_ids:
        model_id = str(raw_model_id)
        row = rows_by_id.get(model_id, {})
        family = infer_route_family(
            model_id=model_id,
            source=str(row.get("selection_source") or ""),
            row=row,
        )
        if family == "unknown_unrouted":
            missing.append(model_id)
        classifications.append(
            {
                "model_id": model_id,
                "route_family": family,
                "route_family_required": True,
                "route_id": str(row.get("route_id") or ""),
                "provider_model_id": str(row.get("upstream_model") or model_id),
                "selection_source": str(row.get("selection_source") or "unknown"),
                "unknown_unrouted_smoke_allowed": False,
            }
        )
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "route_family_classification",
        "captured_at_utc": utc_now(),
        "status": "blocked" if missing else "ok",
        "machine_error_code": "UNKNOWN_UNROUTED_CANDIDATES" if missing else "OK",
        "allowed_route_families": sorted(ROUTE_FAMILIES),
        "unknown_unrouted_candidates": missing,
        "classifications": classifications,
    }


def build_candidate_partition_packet(
    *,
    candidate_packet: dict[str, Any],
    route_family_packet: dict[str, Any],
) -> dict[str, Any]:
    candidate_ids = [str(model_id) for model_id in candidate_packet.get("candidate_model_ids", [])]
    by_id = {
        str(row.get("model_id")): row
        for row in route_family_packet.get("classifications", [])
        if isinstance(row, dict)
    }
    catalog_visible: list[str] = []
    route_backed: list[str] = []
    admitted: list[str] = []
    blocked: list[dict[str, str]] = []
    for model_id in candidate_ids:
        row = by_id.get(model_id, {})
        family = str(row.get("route_family") or "unknown_unrouted")
        source = str(row.get("selection_source") or "")
        if source in {"catalog", "direct_models_endpoint"} or model_id.startswith("gpt-"):
            catalog_visible.append(model_id)
        if family != "unknown_unrouted":
            route_backed.append(model_id)
            admitted.append(model_id)
        else:
            blocked.append({"model_id": model_id, "blocked_reason": "unknown_unrouted"})
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "candidate_partition",
        "captured_at_utc": utc_now(),
        "status": "ok" if candidate_ids and not any(row["model_id"] in admitted for row in blocked) else "blocked",
        "catalog_visible_candidates": catalog_visible,
        "route_backed_candidates": route_backed,
        "admitted_smoke_candidates": admitted,
        "blocked_candidates": blocked,
        "catalog_visible_counted_as_availability": False,
        "catalog_visible_counted_as_admitted_smoke": False,
        "unknown_unrouted_smoked": False,
    }


def build_default_model_source_packet(
    *,
    configured_model: str,
    candidate_packet: dict[str, Any],
    route_family_packet: dict[str, Any],
) -> dict[str, Any]:
    candidate_ids = {str(model_id) for model_id in candidate_packet.get("candidate_model_ids", [])}
    rows = route_family_packet.get("classifications")
    family = "unknown_unrouted"
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("model_id") == configured_model:
                family = str(row.get("route_family") or "unknown_unrouted")
                break
    missing = bool(configured_model) and configured_model not in candidate_ids
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "default_model_source",
        "captured_at_utc": utc_now(),
        "status": "blocked" if missing or family == "unknown_unrouted" else "ok",
        "configured_model": configured_model,
        "configured_model_in_candidate_set": configured_model in candidate_ids,
        "default_model_source": "server_status_configured_model",
        "route_family": family,
        "browser_authority": False,
        "operator_supplied_override": False,
        "missing_from_candidate_set": missing,
    }


def build_model_availability_admission_packet(
    *,
    candidate_partition_packet: dict[str, Any],
    validation_freshness_packet: dict[str, Any],
) -> dict[str, Any]:
    admitted = [str(model_id) for model_id in candidate_partition_packet.get("admitted_smoke_candidates", [])]
    stale = validation_freshness_packet.get("current_truth_allowed") is not True
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_availability_admission",
        "captured_at_utc": utc_now(),
        "status": "blocked" if stale or not admitted else "ok",
        "admitted_smoke_candidates": admitted if not stale else [],
        "blocked_candidates": candidate_partition_packet.get("blocked_candidates", []),
        "validation_freshness_required": True,
        "validation_freshness_status": validation_freshness_packet.get("status"),
        "stale_validation_used_as_current_truth": False,
        "unknown_unrouted_smoke_allowed": False,
        "catalog_visible_counted_as_availability": False,
    }


def build_external_route_admission_packet(
    *,
    route_family_packet: dict[str, Any],
    normalization_packet: dict[str, Any],
) -> dict[str, Any]:
    rows = normalization_packet.get("rows") if isinstance(normalization_packet, dict) else []
    by_id = {
        str(row.get("wbp_model_id") or ""): row
        for row in rows
        if isinstance(row, dict)
    } if isinstance(rows, list) else {}
    external: list[dict[str, Any]] = []
    failures: list[str] = []
    for item in route_family_packet.get("classifications", []):
        if not isinstance(item, dict) or item.get("route_family") != "wbp_api_external_route":
            continue
        model_id = str(item.get("model_id") or "")
        row = by_id.get(model_id, {})
        secret_ref_present = row.get("secret_ref_present") is True or row.get("account_or_backend_id") == "secret_ref_present"
        adapter_id = str(row.get("adapter_id") or "external_route_responses_adapter")
        if not secret_ref_present:
            failures.append(f"{model_id}.secret_ref_present")
        if not adapter_id:
            failures.append(f"{model_id}.adapter_id")
        external.append(
            {
                "model_id": model_id,
                "provider_family": str(row.get("route_provider") or "external_route"),
                "adapter_id": adapter_id,
                "route_id": str(row.get("route_id") or model_id),
                "provider_model_id": str(row.get("upstream_model") or model_id),
                "secret_ref_present": secret_ref_present,
                "adapter_boundary_packet": {
                    "request_transform_classified": True,
                    "response_transform_classified": True,
                    "stream_transform_classified": False,
                    "error_transform_classified": True,
                    "tool_call_transform_classified": False,
                    "reasoning_transform_classified": False,
                    "auth_boundary_classified": True,
                    "raw_upstream_secret_exposed": False,
                },
                "provider_family_compatibility_claimed": False,
            }
        )
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "external_route_admission",
        "captured_at_utc": utc_now(),
        "status": "blocked" if failures else "ok",
        "external_route_candidates": external,
        "validation_failures": failures,
        "provider_family_compatibility_claimed": False,
        "external_route_smoke_claims_provider_family_compatibility": False,
        "raw_secret_recorded": False,
    }


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
    route_family: str = "",
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
    resolved_route_family = route_family if route_family in ROUTE_FAMILIES else infer_route_family(
        model_id=model_id,
        source=source,
    )
    availability_levels = ["listed"] if listed else []
    if selectable:
        availability_levels.append("selectable")
    if route_selected:
        availability_levels.append("route_selected")
    if request_sent_to_wbp:
        availability_levels.append("request_reaches_wbp")
    if upstream_status is not None and 200 <= upstream_status < 300:
        availability_levels.append("upstream_accepts")
    if status_ok:
        availability_levels.append("direct_wbp_non_stream_response_shape_accepted")
    elif failure_cause != "none":
        availability_levels.append("failed")
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_direct_preflight",
        "captured_at_utc": utc_now(),
        "proof_transport": "direct_wbp_http_non_stream",
        "direct_only_contour": True,
        "model_id": model_id,
        "candidate_source": source,
        "source": source,
        "listed": listed,
        "selectable": selectable,
        "route_selected": route_selected,
        "route_id_if_exposed": model_id if route_selected else "",
        "route_family": resolved_route_family,
        "route_family_required": True,
        "unknown_unrouted_smoke_allowed": False,
        "availability_levels": availability_levels,
        "account_id_if_exposed": "",
        "request_attempted": request_sent_to_wbp,
        "request_sent_to_wbp": request_sent_to_wbp,
        "wbp_trace_id": wbp_trace_id,
        "direct_preflight_status": "passed" if status_ok else "blocked_or_unknown",
        "http_status": http_status,
        "wbp_status": http_status,
        "upstream_status": upstream_status,
        "request_reaches_wbp": request_sent_to_wbp,
        "upstream_accepts": upstream_status is not None and 200 <= upstream_status < 300,
        "response_accepted_by_direct_wbp_client": status_ok,
        "response_accepted_by_codex": False,
        "codex_acceptance_status": "not_tested",
        "wbp_response_shape_classified": response_shape_ok,
        "response_body_hash": sha256_text(response_json) if response_json else "",
        "response_hash_recorded": bool(response_json),
        "response_text_hash": sha256_text(str(response_payload.get("output_text") or "")) if isinstance(response_payload, dict) and response_payload.get("output_text") else "",
        "prompt_hash": sha256_text(prompt_text) if prompt_text else "",
        "request_hash_recorded": bool(prompt_text),
        "prompt_body_recorded": False,
        "raw_prompt_recorded": False,
        "auth_header_recorded": False,
        "raw_upstream_secret_recorded": False,
        "error_shape_classified": isinstance(error_payload, dict),
        "failure_cause": failure_cause,
        "blocked_reason_if_any": "" if status_ok else failure_cause,
        "catalog_presence_counted_as_availability": False,
        "direct_wbp_200_counted_as_codex_acceptance": False,
        "non_stream_result_counts_for_streaming": False,
        "non_stream_result_counts_for_tool_loop": False,
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
        "claim_level": (
            "direct_wbp_non_stream_response_accepted"
            if status_ok
            else "listed_only"
            if listed and not request_sent_to_wbp
            else "blocked_with_reason"
        ),
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
        if packet.get("route_family") not in ROUTE_FAMILIES:
            overclaims.append(f"{packet.get('model_id')}.route_family")
        if packet.get("route_family") == "unknown_unrouted" and packet.get("request_sent_to_wbp") is True:
            overclaims.append(f"{packet.get('model_id')}.unknown_unrouted_smoked")
        levels = packet.get("availability_levels")
        if not isinstance(levels, list) or not levels:
            overclaims.append(f"{packet.get('model_id')}.availability_levels")
        elif any(str(level) not in AVAILABILITY_LEVELS for level in levels):
            overclaims.append(f"{packet.get('model_id')}.availability_levels")
    passed = [packet["model_id"] for packet in model_packets if packet.get("direct_preflight_status") == "passed"]
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "model_availability_matrix",
        "captured_at_utc": utc_now(),
        "status": "ok" if not overclaims and model_packets else "blocked",
        "machine_error_code": "OK" if not overclaims and model_packets else "MODEL_AVAILABILITY_BLOCKED",
        "target_status": "WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED",
        "proof_transport": "direct_wbp_http_non_stream",
        "direct_only_contour": True,
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
        "catalog_presence_counted_as_availability": False,
        "non_stream_result_counts_for_streaming": False,
        "non_stream_result_counts_for_tool_loop": False,
        "previous_matrix_imported_as_current_truth": False,
        "forbidden_claims": list(FORBIDDEN_MODEL_CLAIMS),
        "availability_level_order": sorted(AVAILABILITY_LEVELS),
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
    if packet.get("direct_only_contour") is not True:
        findings.append("direct_only_contour")
    if packet.get("proof_transport") != "direct_wbp_http_non_stream":
        findings.append("proof_transport")
    for field in (
        "native_launch_attempted",
        "codex_cli_tested",
        "direct_egress_absence_proven",
        "account_pool_health_proven",
        "streaming_compatible",
        "tool_loop_compatible",
        "catalog_presence_counted_as_availability",
        "non_stream_result_counts_for_streaming",
        "non_stream_result_counts_for_tool_loop",
        "previous_matrix_imported_as_current_truth",
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
        if model.get("route_family") not in ROUTE_FAMILIES:
            findings.append(f"models[{index}].route_family")
        if model.get("route_family") == "unknown_unrouted" and model.get("request_sent_to_wbp") is True:
            findings.append(f"models[{index}].unknown_unrouted_smoked")
        levels = model.get("availability_levels")
        if not isinstance(levels, list) or not levels:
            findings.append(f"models[{index}].availability_levels")
        elif any(str(level) not in AVAILABILITY_LEVELS for level in levels):
            findings.append(f"models[{index}].availability_levels")
        if model.get("request_sent_to_wbp") is True:
            if model.get("request_hash_recorded") is not True:
                findings.append(f"models[{index}].request_hash_recorded")
            if model.get("auth_header_recorded") is not False:
                findings.append(f"models[{index}].auth_header_recorded")
            if model.get("raw_prompt_recorded") is not False:
                findings.append(f"models[{index}].raw_prompt_recorded")
            if model.get("raw_upstream_secret_recorded") is not False:
                findings.append(f"models[{index}].raw_upstream_secret_recorded")
        if model.get("direct_only_contour") is not True:
            findings.append(f"models[{index}].direct_only_contour")
        if model.get("proof_transport") != "direct_wbp_http_non_stream":
            findings.append(f"models[{index}].proof_transport")
        for field in (
            "native_tested",
            "codex_cli_tested",
            "direct_egress_tested",
            "owner_ui_tested",
            "account_health_proven",
            "response_accepted_by_codex",
            "catalog_presence_counted_as_availability",
            "direct_wbp_200_counted_as_codex_acceptance",
            "non_stream_result_counts_for_streaming",
            "non_stream_result_counts_for_tool_loop",
        ):
            if model.get(field) is not False:
                findings.append(f"models[{index}].{field}")
    findings.extend(str(item) for item in packet.get("overclaim_findings", []))
    return sorted(set(findings))


def validate_model_availability_contour_packets(packets: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for name in MODEL_AVAILABILITY_R1_REQUIRED_PACKETS:
        if name not in packets:
            findings.append(f"missing.{name}")
    matrix = packets.get("model_availability_matrix.json")
    if isinstance(matrix, dict):
        findings.extend(f"matrix.{item}" for item in validate_model_availability_matrix(matrix))
    else:
        findings.append("model_availability_matrix.json")
    partition = packets.get("candidate_partition_packet.json")
    if isinstance(partition, dict):
        if partition.get("catalog_visible_counted_as_availability") is not False:
            findings.append("candidate_partition.catalog_visible_counted_as_availability")
        if partition.get("catalog_visible_counted_as_admitted_smoke") is not False:
            findings.append("candidate_partition.catalog_visible_counted_as_admitted_smoke")
        if partition.get("unknown_unrouted_smoked") is not False:
            findings.append("candidate_partition.unknown_unrouted_smoked")
    default_source = packets.get("default_model_source_packet.json")
    if isinstance(default_source, dict):
        if default_source.get("browser_authority") is not False:
            findings.append("default_model_source.browser_authority")
        if default_source.get("route_family") not in ROUTE_FAMILIES:
            findings.append("default_model_source.route_family")
    route_family = packets.get("route_family_classification_packet.json")
    if isinstance(route_family, dict):
        for index, item in enumerate(route_family.get("classifications", [])):
            if isinstance(item, dict) and item.get("route_family") not in ROUTE_FAMILIES:
                findings.append(f"route_family.classifications[{index}].route_family")
    external = packets.get("external_route_admission_packet.json")
    if isinstance(external, dict):
        if external.get("provider_family_compatibility_claimed") is not False:
            findings.append("external_route_admission.provider_family_compatibility_claimed")
        for index, item in enumerate(external.get("external_route_candidates", [])):
            if not isinstance(item, dict):
                findings.append(f"external_route_admission.external_route_candidates[{index}]")
                continue
            if item.get("secret_ref_present") is not True:
                findings.append(f"external_route_admission.external_route_candidates[{index}].secret_ref_present")
            boundary = item.get("adapter_boundary_packet")
            if not isinstance(boundary, dict) or boundary.get("auth_boundary_classified") is not True:
                findings.append(f"external_route_admission.external_route_candidates[{index}].adapter_boundary_packet")
            if item.get("provider_family_compatibility_claimed") is not False:
                findings.append(f"external_route_admission.external_route_candidates[{index}].provider_family_compatibility_claimed")
    freshness = packets.get("validation_freshness_packet.json")
    if isinstance(freshness, dict) and freshness.get("current_truth_allowed") is not True:
        findings.append("validation_freshness.current_truth_allowed")
    return sorted(set(findings))


def build_model_availability_false_green_audit(
    *,
    matrix_packet: dict[str, Any],
    freshness_packet: dict[str, Any],
    layer_boundary_packet: dict[str, Any],
    mutation_guard_packet: dict[str, Any],
    normalization_packet: dict[str, Any],
    contour_packets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[str] = []
    if validate_model_availability_matrix(matrix_packet):
        findings.append("matrix_validation_failed")
    if freshness_packet.get("stale_validation_used_as_current_truth") is not False:
        findings.append("stale_validation_used_as_current_truth")
    if layer_boundary_packet.get("native_app_usability_proven") is not False:
        findings.append("native_layer_overclaim")
    if layer_boundary_packet.get("direct_only_contour") is not True:
        findings.append("layer_boundary_not_direct_only")
    if matrix_packet.get("codex_acceptance_proven") is not False:
        findings.append("codex_acceptance_overclaim")
    if matrix_packet.get("direct_only_contour") is not True:
        findings.append("matrix_not_direct_only")
    if matrix_packet.get("all_model_sweep_attempted") is not False:
        findings.append("all_model_sweep_overclaim")
    if matrix_packet.get("catalog_presence_counted_as_availability") is not False:
        findings.append("catalog_presence_counted_as_availability")
    if matrix_packet.get("previous_matrix_imported_as_current_truth") is not False:
        findings.append("previous_matrix_imported_as_current_truth")
    if mutation_guard_packet.get("status") != "ok":
        findings.append("route_or_account_mutation")
    if normalization_packet.get("status") != "ok":
        findings.append("model_id_normalization_incomplete")
    if contour_packets:
        contour_findings = validate_model_availability_contour_packets(contour_packets)
        if contour_findings:
            findings.append("contour_packet_validation_failed")
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


def _catalog_availability_row_from_model_packet(
    packet: dict[str, Any],
    *,
    evidence_scope: str,
) -> dict[str, Any]:
    model_id = str(packet.get("model_id") or "")
    direct_passed = packet.get("direct_preflight_status") == "passed"
    historical_scope = evidence_scope == "pass2_selected_external_route_closed_truth"
    claim_level = (
        "historically_direct_wbp_non_stream_response_accepted"
        if direct_passed and historical_scope
        else "direct_wbp_non_stream_response_accepted"
        if direct_passed
        else "listed_not_live_proven"
    )
    return {
        "model_id": model_id,
        "availability_claim_level": claim_level,
        "availability_levels": list(packet.get("availability_levels") or ["listed"]),
        "live_availability_proven": direct_passed and not historical_scope,
        "direct_wbp_non_stream_response_accepted": direct_passed,
        "request_reaches_wbp_proven": packet.get("request_reaches_wbp") is True,
        "upstream_accepts_proven": packet.get("upstream_accepts") is True,
        "response_accepted_by_codex_proven": False,
        "current_stability_proven": direct_passed and not historical_scope,
        "availability_evidence_scope": evidence_scope,
        "bounded_limitations": [
            "response_accepted_by_codex_not_proven",
            "streaming_not_proven",
            "tool_loop_not_proven",
        ]
        + (
            ["current_live_stability_not_proven"]
            if historical_scope
            else []
        ),
        "failure_cause": str(packet.get("failure_cause") or "none"),
        "blocked_reason_if_any": str(packet.get("blocked_reason_if_any") or ""),
        "route_family": str(packet.get("route_family") or "unknown_unrouted"),
    }


def build_catalog_availability_lattice_packet(
    *,
    catalog_packet: dict[str, Any] | None,
    current_model_packets: list[dict[str, Any]] | None = None,
    historical_model_packets: list[dict[str, Any]] | None = None,
    out_of_catalog_model_packets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    models = catalog_packet.get("models") if isinstance(catalog_packet, dict) else []
    current_by_id = {
        str(packet.get("model_id") or ""): packet
        for packet in (current_model_packets or [])
        if isinstance(packet, dict) and str(packet.get("model_id") or "")
    }
    historical_by_id = {
        str(packet.get("model_id") or ""): packet
        for packet in (historical_model_packets or [])
        if isinstance(packet, dict) and str(packet.get("model_id") or "")
    }
    rows: list[dict[str, Any]] = []
    catalog_ids: set[str] = set()
    for model in models if isinstance(models, list) else []:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("model_id") or "").strip()
        if not model_id:
            continue
        catalog_ids.add(model_id)
        row = {
            "model_id": model_id,
            "lane": str(model.get("lane") or ""),
            "availability_claim_level": "listed_not_live_proven",
            "availability_levels": ["listed"],
            "live_availability_proven": False,
            "direct_wbp_non_stream_response_accepted": False,
            "request_reaches_wbp_proven": False,
            "upstream_accepts_proven": False,
            "response_accepted_by_codex_proven": False,
            "current_stability_proven": False,
            "availability_evidence_scope": "current_operator_catalog_only",
            "bounded_limitations": [
                "live_acceptance_not_proven",
                "response_accepted_by_codex_not_proven",
                "streaming_not_proven",
                "tool_loop_not_proven",
            ],
            "failure_cause": "none",
            "blocked_reason_if_any": "",
            "route_family": "",
        }
        packet = current_by_id.get(model_id)
        if packet is not None:
            row.update(
                _catalog_availability_row_from_model_packet(
                    packet,
                    evidence_scope="current_thread_direct_wbp_non_stream",
                )
            )
        else:
            packet = historical_by_id.get(model_id)
            if packet is not None:
                row.update(
                    _catalog_availability_row_from_model_packet(
                        packet,
                        evidence_scope="pass2_selected_external_route_closed_truth",
                    )
                )
        rows.append(row)
    out_of_catalog_observations: list[dict[str, Any]] = []
    for packet in out_of_catalog_model_packets or []:
        if not isinstance(packet, dict):
            continue
        model_id = str(packet.get("model_id") or "").strip()
        if not model_id or model_id in catalog_ids:
            continue
        out_of_catalog_observations.append(
            {
                "model_id": model_id,
                "listed_in_current_operator_catalog": False,
                "direct_preflight_status": str(packet.get("direct_preflight_status") or ""),
                "http_status": packet.get("http_status"),
                "failure_cause": str(packet.get("failure_cause") or "unknown"),
                "blocked_reason_if_any": str(packet.get("blocked_reason_if_any") or ""),
                "route_family": str(packet.get("route_family") or "unknown_unrouted"),
                "catalog_expansion_allowed": False,
            }
        )
    listed_only = [
        row["model_id"]
        for row in rows
        if row["availability_claim_level"] == "listed_not_live_proven"
    ]
    current_live_proven = [
        row["model_id"]
        for row in rows
        if row["availability_claim_level"] == "direct_wbp_non_stream_response_accepted"
    ]
    historical_bounded = [
        row["model_id"]
        for row in rows
        if row["availability_claim_level"] == "historically_direct_wbp_non_stream_response_accepted"
    ]
    return {
        "schema_version": MODEL_AVAILABILITY_SCHEMA_VERSION,
        "packet_kind": "catalog_availability_lattice",
        "captured_at_utc": utc_now(),
        "status": "ok" if rows else "blocked",
        "claim_level_values": sorted(CATALOG_AVAILABILITY_CLAIM_LEVELS),
        "evidence_scope_values": sorted(CATALOG_AVAILABILITY_EVIDENCE_SCOPES),
        "availability_level_values": sorted(AVAILABILITY_LEVELS),
        "rows": rows,
        "listed_only_model_ids": listed_only,
        "current_live_proven_model_ids": current_live_proven,
        "historically_bounded_model_ids": historical_bounded,
        "out_of_catalog_observations": out_of_catalog_observations,
        "response_accepted_by_codex_proven": False,
        "streaming_proven": False,
        "tool_loop_proven": False,
        "all_listed_models_equally_usable": False,
    }
