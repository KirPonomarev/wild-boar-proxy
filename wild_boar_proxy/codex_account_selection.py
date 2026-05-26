# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Codex Custom GPT account pool truth and selection packets."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from wild_boar_proxy.codex_model_registry import build_custom_model_registry_packet
from wild_boar_proxy.operator_surface import DEFAULT_MODEL
from wild_boar_proxy.runtime import (
    backend_runtime_ranking_key,
    classify_backend_runtime_eligibility,
)


ACCOUNT_SMOKE_DRY_RUN_ALLOWED_FIELDS = {"model_id"}
ACCOUNT_SMOKE_DRY_RUN_FORBIDDEN_FIELDS = {
    "account_id",
    "api_key",
    "apikey",
    "auth",
    "auth_path",
    "base_url",
    "backend_id",
    "codex_home",
    "endpoint",
    "home",
    "model_provider",
    "openai_base_url",
    "path",
    "profile",
    "provider",
    "route_id",
    "runtime_config",
    "secret",
    "token",
    "wire_api",
}
POOL_CLASS_NAMES = ("active", "reserve", "hold", "problem", "retired")
ELIGIBILITY_CLASS_NAMES = (
    "live_capable",
    "quota_exhausted",
    "auth_invalid",
    "cooldown_only",
    "unknown_unverified",
    "excluded",
)
MODEL_SELECTION_ALLOWED_STATUS = "WBP_MODEL_SELECTION_ACCOUNT_ROUTE_TRUTH_CLASSIFIED"
MODEL_SELECTION_FORBIDDEN_CLAIMS = (
    "live_model_availability_proven",
    "selected_model_usable_live",
    "selected_account_healthy_live",
    "account_token_validity_proven",
    "account_quota_proven",
    "reserve_promoted",
    "native_codex_proven",
    "cli_runner_proven",
    "direct_egress_absent",
    "final_e2e_proven",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def forbidden_account_smoke_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_text = str(key)
            key_path = f"{prefix}.{key_text}" if prefix else key_text
            key_lower = key_text.lower()
            if key_lower in ACCOUNT_SMOKE_DRY_RUN_FORBIDDEN_FIELDS:
                findings.append(key_path)
            elif prefix or key_text not in ACCOUNT_SMOKE_DRY_RUN_ALLOWED_FIELDS:
                findings.append(key_path)
            findings.extend(forbidden_account_smoke_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_account_smoke_fields(value, f"{prefix}[{index}]"))
    return findings


def _packet_from_command(commands: dict[str, dict[str, Any]], command_id: str) -> dict[str, Any]:
    result = commands.get(command_id)
    if isinstance(result, dict) and result.get("status") == "ok":
        packet = result.get("packet")
        if isinstance(packet, dict):
            return packet
    return {}


def _command_error_codes(commands: dict[str, dict[str, Any]]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for command_id, result in commands.items():
        if result.get("status") != "ok":
            errors[command_id] = str(result.get("machine_error_code") or "COMMAND_UNAVAILABLE")
    return errors


def _claim_gate_status(status_packet: dict[str, Any]) -> str:
    claim_gate = status_packet.get("claim_gate")
    if isinstance(claim_gate, dict):
        status = claim_gate.get("status")
        if isinstance(status, str) and status:
            return status
    return "not_reported"


def _accounts(accounts_packet: dict[str, Any]) -> list[dict[str, Any]]:
    accounts = accounts_packet.get("accounts")
    return [item for item in accounts if isinstance(item, dict)] if isinstance(accounts, list) else []


def _pool_classes(accounts: list[dict[str, Any]]) -> dict[str, int]:
    classes = {name: 0 for name in POOL_CLASS_NAMES}
    for account in accounts:
        pool = str(account.get("pool") or "unknown")
        status = str(account.get("status") or "")
        last_error = str(account.get("last_error") or "")
        manual_hold = bool(account.get("manual_hold"))
        if pool in classes:
            classes[pool] += 1
        if manual_hold:
            classes["hold"] += 1
        if status in {"down", "degraded", "failed", "error"} or last_error:
            classes["problem"] += 1
    return classes


def _class_ids(accounts: list[dict[str, Any]]) -> dict[str, list[str]]:
    classes: dict[str, list[str]] = {name: [] for name in ELIGIBILITY_CLASS_NAMES}
    for account in accounts:
        backend_id = str(account.get("id") or "").strip()
        if not backend_id:
            continue
        eligibility, _ = classify_backend_runtime_eligibility(account)
        classes.setdefault(eligibility, []).append(backend_id)
    return {name: sorted(ids) for name, ids in classes.items()}


def _redacted_account_rows(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for account in accounts:
        backend_id = str(account.get("id") or "").strip()
        if not backend_id:
            continue
        eligibility, reasons = classify_backend_runtime_eligibility(account)
        backend_ref = _backend_ref(backend_id)
        rows.append(
            {
                "backend_id": "",
                "backend_ref": backend_ref,
                "label": f"account-{backend_ref[:12]}",
                "pool": str(account.get("pool") or ""),
                "status": str(account.get("status") or ""),
                "manual_hold": bool(account.get("manual_hold")),
                "enabled": bool(account.get("enabled", True)),
                "priority": account.get("priority"),
                "fail_count": int(account.get("fail_count") or 0),
                "success_count": int(account.get("success_count") or 0),
                "last_error_class": str(account.get("last_error_class") or ""),
                "cooldown_present": bool(account.get("cooldown_until")),
                "auth_ref_present": bool(account.get("auth_ref")),
                "eligibility_class": eligibility,
                "not_selected_reasons": reasons,
            }
        )
    return rows


def _launch_capable_accounts(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    capable = [
        account
        for account in accounts
        if str(account.get("id") or "").strip()
        and classify_backend_runtime_eligibility(account)[0] == "live_capable"
    ]
    capable.sort(key=backend_runtime_ranking_key)
    return capable


def _auth_pool_hygiene(status_packet: dict[str, Any]) -> dict[str, Any]:
    hygiene = status_packet.get("auth_pool_hygiene")
    return hygiene if isinstance(hygiene, dict) else {}


def _selected_backend_ids(status_packet: dict[str, Any]) -> list[str]:
    pool_summary = status_packet.get("pool_summary")
    if isinstance(pool_summary, dict) and isinstance(pool_summary.get("selected_backend_ids"), list):
        return [str(item) for item in pool_summary["selected_backend_ids"]]
    hygiene = _auth_pool_hygiene(status_packet)
    selected = hygiene.get("selected_backend_ids_observed")
    return [str(item) for item in selected] if isinstance(selected, list) else []


def _sanitized_accounts_digest(accounts: list[dict[str, Any]]) -> str:
    payload = {
        "accounts": [
            {
                "id": account.get("id"),
                "enabled": account.get("enabled"),
                "pool": account.get("pool"),
                "status": account.get("status"),
                "manual_hold": account.get("manual_hold"),
                "fail_count": account.get("fail_count"),
                "success_count": account.get("success_count"),
                "last_error_class": account.get("last_error_class"),
                "cooldown_present": bool(account.get("cooldown_until")),
                "auth_ref_present": bool(account.get("auth_ref")),
            }
            for account in accounts
        ]
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _backend_ref(backend_id: str) -> str:
    return hashlib.sha256(backend_id.encode("utf-8")).hexdigest()


def _backend_refs(backend_ids: list[str]) -> list[str]:
    return [_backend_ref(backend_id) for backend_id in backend_ids if backend_id]


def _auth_ref_ref(auth_ref: str) -> str:
    return hashlib.sha256(auth_ref.encode("utf-8")).hexdigest()


def _auth_ref_static_classification(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    auth_ref_counts: dict[str, int] = {}
    for account in accounts:
        auth_ref = str(account.get("auth_ref") or "").strip()
        if auth_ref:
            auth_ref_counts[auth_ref] = auth_ref_counts.get(auth_ref, 0) + 1
    duplicate_refs = sorted(ref for ref, count in auth_ref_counts.items() if count > 1)
    unexpected_format_refs = sorted(
        ref
        for ref in auth_ref_counts
        if not (
            ref.startswith("managed:")
            or ".cli-proxy-api" in ref
            or ref.endswith(".json")
        )
    )
    return {
        "classification_scope": "static_dry_run_only",
        "live_validation_performed": False,
        "token_validity_proven": False,
        "quota_proven": False,
        "upstream_credentials_accepted": False,
        "auth_ref_present_count": sum(1 for account in accounts if account.get("auth_ref")),
        "auth_ref_missing_count": sum(1 for account in accounts if not account.get("auth_ref")),
        "duplicate_auth_ref_count": len(duplicate_refs),
        "duplicate_auth_ref_refs": [_auth_ref_ref(ref) for ref in duplicate_refs],
        "unexpected_auth_ref_format_count": len(unexpected_format_refs),
        "unexpected_auth_ref_refs": [_auth_ref_ref(ref) for ref in unexpected_format_refs],
        "raw_auth_refs_exposed": False,
        "missing_auth_ref_is_green": False,
        "duplicate_auth_ref_is_green": False,
    }


def _route_entries(api_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(api_snapshot, dict):
        return []
    routes = api_snapshot.get("routes")
    return [route for route in routes if isinstance(route, dict)] if isinstance(routes, list) else []


def _route_selection_for_model(model_id: str, api_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    route = next(
        (
            item
            for item in _route_entries(api_snapshot)
            if str(item.get("route_id") or "").strip() == model_id
        ),
        None,
    )
    if route is None:
        return {
            "selected_source_class": "none",
            "selected_route_ref": "",
            "selected_route_server_issued": False,
            "route_policy_state": "not_visible",
            "route_provenance_required": False,
            "route_provenance_proven": False,
        }
    route_id = str(route.get("route_id") or "").strip()
    secret_ref = str(route.get("secret_ref") or "").strip()
    enabled = route.get("enabled") is True
    route_ready = enabled and bool(secret_ref)
    return {
        "selected_source_class": "route_backed" if route_ready else "none",
        "selected_route_ref": hashlib.sha256(route_id.encode("utf-8")).hexdigest(),
        "selected_route_server_issued": route_ready,
        "route_policy_state": "route_ready_static" if route_ready else "route_degraded_static",
        "route_provenance_required": route_ready,
        "route_provenance_proven": route_ready,
        "route_enabled": enabled,
        "route_secret_ref_present": bool(secret_ref),
        "raw_route_id_exposed": False,
        "raw_secret_ref_exposed": False,
    }


def build_accounts_truth_packet(commands: dict[str, dict[str, Any]]) -> dict[str, Any]:
    status_packet = _packet_from_command(commands, "status")
    accounts_packet = _packet_from_command(commands, "accounts_list")
    rotation_packet = _packet_from_command(commands, "rollout_rotation_inspect")
    command_errors = _command_error_codes(commands)
    accounts = _accounts(accounts_packet)
    class_ids = _class_ids(accounts)
    pool_classes = _pool_classes(accounts)
    launch_capable = _launch_capable_accounts(accounts)
    hygiene = _auth_pool_hygiene(status_packet)
    claim_gate_status = _claim_gate_status(status_packet)
    status = "ok" if accounts and not command_errors else "degraded"
    machine_error_code = "OK" if status == "ok" else "ACCOUNTS_TRUTH_DEGRADED"
    if "blocked" in claim_gate_status and status == "ok":
        status = "degraded"
        machine_error_code = "CLAIM_GATE_BLOCKED"
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "account_source": "provided_packet_or_fake",
        "account_count_claim_scope": "packet_shape_only",
        "live_account_truth_checked": False,
        "managed_total": len(accounts),
        "accounts_visible": len(accounts),
        "expected_managed_total": 25,
        "managed_total_matches_expected": len(accounts) == 25,
        "launch_capable_count": len(launch_capable),
        "launch_capable_backend_ids": [],
        "launch_capable_backend_refs": _backend_refs([str(account.get("id")) for account in launch_capable]),
        "pool_classes": pool_classes,
        "pool_counts": pool_classes,
        "eligibility_classes": {name: len(ids) for name, ids in class_ids.items()},
        "auth_classes": {
            "auth_ref_present": sum(1 for account in accounts if account.get("auth_ref")),
            "auth_ref_missing": sum(1 for account in accounts if not account.get("auth_ref")),
            "auth_invalid": len(class_ids.get("auth_invalid", [])),
        },
        "auth_ref_static_classification": _auth_ref_static_classification(accounts),
        "cooldown_classes": {
            "cooldown_present": sum(1 for account in accounts if account.get("cooldown_until")),
            "cooldown_only": len(class_ids.get("cooldown_only", [])),
        },
        "quota_classes": {
            "quota_exhausted": sum(
                1
                for account in accounts
                if str(account.get("last_error_class") or "").lower() == "quota"
                or "usage_limit_reached" in str(account.get("last_error") or "").lower()
            ),
        },
        "claim_gate_status": claim_gate_status,
        "selection_alignment_status": str(
            hygiene.get("selection_alignment_status") or "not_reported"
        ),
        "runtime_auth_pool_hygiene_status": str(hygiene.get("status") or "not_reported"),
        "selected_backend_ids_observed": [],
        "selected_backend_refs_observed": _backend_refs(_selected_backend_ids(status_packet)),
        "rotation_packet_present": bool(rotation_packet),
        "fresh_truth": bool(accounts_packet),
        "account_mutation_performed": False,
        "account_ids_redacted": True,
        "raw_backend_ids_exposed": False,
        "raw_auth_refs_exposed": False,
        "raw_auth_visible": False,
        "token_burn": 0,
        "accounts_digest": _sanitized_accounts_digest(accounts),
        "accounts": _redacted_account_rows(accounts),
        "command_error_codes": command_errors,
    }


def build_model_selection_truth_packet(
    payload: dict[str, Any],
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
    *,
    api_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    forbidden = forbidden_account_smoke_fields(payload)
    accounts_truth = build_accounts_truth_packet(commands)
    status_packet = _packet_from_command(commands, "status")
    selected_refs_before = accounts_truth["selected_backend_refs_observed"]
    selected_refs_after = _backend_refs(_selected_backend_ids(status_packet))
    auth_classification = accounts_truth["auth_ref_static_classification"]
    base = {
        "schema_version": 1,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "contract_scope": "model_selection_account_route_truth_only",
        "dry_run": True,
        "selection_not_inference": True,
        "live_model_availability_proven": False,
        "live_account_truth_checked": False,
        "account_token_validity_proven": False,
        "account_quota_proven": False,
        "upstream_credentials_accepted": False,
        "native_codex_proven": False,
        "cli_runner_proven": False,
        "direct_egress_absence_proven": False,
        "final_e2e_proven": False,
        "responses_called": False,
        "chat_completions_called": False,
        "provider_called": False,
        "network_calls_made": False,
        "token_burn": 0,
        "account_mutation_performed": False,
        "reserve_promotion_performed": False,
        "active_routing_before_refs": selected_refs_before,
        "active_routing_after_refs": selected_refs_after,
        "active_routing_changed": selected_refs_before != selected_refs_after,
        "browser_authority": {
            "route_id": False,
            "backend_id": False,
            "account_id": False,
            "provider": False,
            "base_url": False,
            "token": False,
            "auth_path": False,
            "path": False,
        },
        "browser_selected_backend": False,
        "browser_selected_route": False,
        "raw_backend_id_exposed": False,
        "raw_route_id_exposed": False,
        "raw_auth_refs_exposed": False,
        "raw_secret_exposed": False,
        "auth_ref_static_classification": auth_classification,
        "account_pool_truth": {
            "status": accounts_truth["status"],
            "machine_error_code": accounts_truth["machine_error_code"],
            "pool_classes": accounts_truth["pool_classes"],
            "eligibility_classes": accounts_truth["eligibility_classes"],
            "auth_classes": accounts_truth["auth_classes"],
            "launch_capable_count": accounts_truth["launch_capable_count"],
            "account_count_claim_scope": accounts_truth["account_count_claim_scope"],
        },
        "allowed_status": MODEL_SELECTION_ALLOWED_STATUS,
        "forbidden_claims": list(MODEL_SELECTION_FORBIDDEN_CLAIMS),
        "claim_limits": {
            "model_listed_means_usable": False,
            "account_exists_means_healthy": False,
            "static_auth_ref_means_token_valid": False,
            "selection_policy_proves_route_response": False,
            "selection_policy_proves_native": False,
            "selection_policy_proves_egress": False,
        },
    }
    if forbidden:
        return base | {
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "human_message": "Model selection accepts only server-issued model_id.",
            "forbidden_fields": forbidden,
            "model_server_issued": False,
            "selection_policy_proven": False,
        }
    model_registry = build_custom_model_registry_packet(operator_status, api_snapshot=api_snapshot)
    model_ids = [str(entry.get("model_id") or "") for entry in model_registry.get("available_models", [])]
    model_id = payload.get("model_id")
    if not isinstance(model_id, str) or model_id not in model_ids:
        return base | {
            "status": "rejected",
            "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
            "human_message": "Model id was not present in the current server-issued list.",
            "selected_model": model_id if isinstance(model_id, str) else "",
            "model_server_issued": False,
            "selection_policy_proven": False,
            "server_issued_model_ids": model_ids,
        }

    if model_id.startswith("gpt-"):
        selection = build_account_selection_packet(commands, operator_status)
        selection_status = str(selection.get("status") or "degraded")
        selection_machine_error = str(selection.get("machine_error_code") or "SELECTION_DEGRADED")
        policy_state = "gpt_account_policy_classified"
        route_selection: dict[str, Any] = {
            "selected_route_ref": "",
            "selected_route_server_issued": False,
            "route_policy_state": "not_applicable_for_gpt_account",
        }
    else:
        route_selection = _route_selection_for_model(model_id, api_snapshot)
        selection_status = "ok" if route_selection["selected_route_server_issued"] else "degraded"
        selection_machine_error = "OK" if selection_status == "ok" else "ROUTE_POLICY_NOT_READY_STATIC"
        policy_state = str(route_selection["route_policy_state"])
        selection = {
            "selected_source_class": route_selection["selected_source_class"],
            "selected_backend_ref": "",
            "selected_backend_server_issued": False,
            "selected_backend_source": "none",
            "selected_route_ref": route_selection["selected_route_ref"],
            "selected_route_server_issued": route_selection["selected_route_server_issued"],
            "route_provenance_required": route_selection["route_provenance_required"],
            "route_provenance_proven": route_selection["route_provenance_proven"],
            "source_provenance_status": policy_state,
            "selection_dry_run_proven": route_selection["selected_route_server_issued"],
        }

    not_green_reasons: list[str] = []
    if auth_classification["auth_ref_missing_count"]:
        not_green_reasons.append("auth_ref_missing_static")
    if auth_classification["duplicate_auth_ref_count"]:
        not_green_reasons.append("duplicate_auth_ref_static")
    if base["active_routing_changed"]:
        not_green_reasons.append("active_routing_changed")
    if base["reserve_promotion_performed"]:
        not_green_reasons.append("reserve_promotion_performed")
    if selection_status == "ok" and not_green_reasons:
        selection_status = "degraded"
        selection_machine_error = "MODEL_SELECTION_STATIC_CLASSIFICATION_DEGRADED"

    return base | {
        "status": selection_status,
        "machine_error_code": selection_machine_error,
        "human_message": "Model selection account/route policy was classified without live validation.",
        "selected_model": model_id,
        "model_server_issued": True,
        "selection_policy_proven": bool(selection.get("selection_dry_run_proven")),
        "selection_policy_state": policy_state,
        "selected_source_class": selection["selected_source_class"],
        "selected_backend_ref": selection.get("selected_backend_ref", ""),
        "selected_backend_server_issued": bool(selection.get("selected_backend_server_issued")),
        "selected_backend_source": str(selection.get("selected_backend_source") or "none"),
        "selected_route_ref": selection.get("selected_route_ref", ""),
        "selected_route_server_issued": bool(selection.get("selected_route_server_issued")),
        "route_provenance_required": bool(selection.get("route_provenance_required")),
        "route_provenance_proven": bool(selection.get("route_provenance_proven")),
        "source_provenance_status": str(selection.get("source_provenance_status") or policy_state),
        "server_issued_model_ids": model_ids,
        "static_not_green_reasons": not_green_reasons,
        "route_selection_static": route_selection,
        "negative_claim_basis": "model_selection_static_dry_run_no_live_validation_or_inference",
    }


def build_account_selection_packet(
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
) -> dict[str, Any]:
    accounts_truth = build_accounts_truth_packet(commands)
    status_packet = _packet_from_command(commands, "status")
    accounts = _accounts(_packet_from_command(commands, "accounts_list"))
    launch_capable = _launch_capable_accounts(accounts)
    selected_backend = launch_capable[0] if launch_capable else None
    selected_backend_id = str(selected_backend.get("id")) if selected_backend else ""
    selected_backend_ids_observed = _selected_backend_ids(status_packet)
    not_selected_reasons = []
    for account in accounts:
        backend_id = str(account.get("id") or "").strip()
        if not backend_id or backend_id == selected_backend_id:
            continue
        eligibility, reasons = classify_backend_runtime_eligibility(account)
        not_selected_reasons.append(
            {
                "backend_id": "",
                "backend_ref": _backend_ref(backend_id),
                "eligibility_class": eligibility,
                "reasons": reasons or ["ranked_after_selected_backend"],
            }
        )
    model_registry = build_custom_model_registry_packet(operator_status)
    claim_gate_status = accounts_truth["claim_gate_status"]
    selection_proven = bool(selected_backend_id)
    status = "ok" if selection_proven else "degraded"
    machine_error_code = "OK" if selection_proven else "NO_LAUNCH_CAPABLE_GPT_ACCOUNT"
    if "blocked" in claim_gate_status and selection_proven:
        status = "degraded"
        machine_error_code = "CLAIM_GATE_BLOCKED"
    return {
        "schema_version": 1,
        "status": status,
        "machine_error_code": machine_error_code,
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "selection_dry_run_proven": selection_proven,
        "live_selection_proven": False,
        "selection_proven": selection_proven,
        "inference_proven": False,
        "selected_source_class": "gpt_account" if selection_proven else "none",
        "selected_backend_id": "",
        "selected_backend_ref": _backend_ref(selected_backend_id) if selected_backend_id else "",
        "selected_backend_id_redacted": True,
        "selected_backend_server_issued": selection_proven,
        "selected_backend_source": "server" if selection_proven else "none",
        "selected_route_ref": "",
        "selected_route_server_issued": False,
        "route_provenance_required": False,
        "route_provenance_proven": False,
        "source_provenance_status": "backend_proven" if selection_proven else "not_proven",
        "browser_selected_backend": False,
        "selection_reason": (
            "dry-run first live_capable active backend by runtime ranking policy"
            if selection_proven
            else "no live_capable active backend available"
        ),
        "ranking_inputs": {
            "fields": [
                "priority_ascending",
                "fail_count_ascending",
                "success_count_descending",
                "backend_id_ascending",
            ],
            "selected_backend_ids_observed": [],
            "selected_backend_refs_observed": _backend_refs(selected_backend_ids_observed),
            "launch_capable_count": accounts_truth["launch_capable_count"],
        },
        "not_selected_reasons": not_selected_reasons[:50],
        "runtime_meter_attached": False,
        "smoke_admitted": False,
        "smoke_not_admitted_reason": "runtime_meter_not_attached",
        "responses_called": False,
        "chat_completions_called": False,
        "provider_called": False,
        "network_calls_made": False,
        "claim_gate_status": claim_gate_status,
        "model_registry_status": model_registry["status"],
        "server_issued_model_ids": [
            entry["model_id"] for entry in model_registry.get("available_models", [])
        ],
        "account_mutation_performed": False,
        "raw_backend_id_exposed": False,
        "selected_backend_id_redacted": True,
        "token_burn": 0,
        "selection_not_inference": True,
        "account_count_claim_scope": accounts_truth["account_count_claim_scope"],
        "live_account_truth_checked": False,
        "fresh_truth": accounts_truth["fresh_truth"],
        "refresh_packet": accounts_truth,
    }


def build_account_smoke_dry_run_packet(
    payload: dict[str, Any],
    commands: dict[str, dict[str, Any]],
    operator_status: dict[str, Any] | None,
) -> dict[str, Any]:
    forbidden = forbidden_account_smoke_fields(payload)
    selection = build_account_selection_packet(commands, operator_status)
    model_registry = build_custom_model_registry_packet(operator_status)
    if forbidden:
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "dry_run": True,
            "human_message": "Account smoke dry-run accepts only server-issued model_id.",
            "forbidden_fields": forbidden,
            "model_server_issued": False,
            "selection_dry_run_proven": False,
            "live_selection_proven": False,
            "selection_proven": False,
            "inference_proven": False,
            "smoke_admitted": False,
            "runtime_meter_attached": False,
            "responses_called": False,
            "chat_completions_called": False,
            "provider_called": False,
            "network_calls_made": False,
            "account_mutation_performed": False,
            "browser_selected_backend": False,
            "selected_backend_id_redacted": True,
            "token_burn": 0,
            "refresh_packet": selection,
            "next_action": "remove_forbidden_browser_fields",
        }
    model_id = payload.get("model_id")
    model_ids = [entry["model_id"] for entry in model_registry.get("available_models", [])]
    if not isinstance(model_id, str) or model_id not in model_ids:
        return {
            "schema_version": 1,
            "status": "rejected",
            "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
            "captured_at_utc": utc_now(),
            "mode_id": "codex_custom",
            "dry_run": True,
            "human_message": "Model id was not present in the current server-issued list.",
            "selected_model": model_id if isinstance(model_id, str) else "",
            "model_server_issued": False,
            "selection_dry_run_proven": selection["selection_dry_run_proven"],
            "live_selection_proven": False,
            "selection_proven": selection["selection_proven"],
            "inference_proven": False,
            "smoke_admitted": False,
            "runtime_meter_attached": False,
            "responses_called": False,
            "chat_completions_called": False,
            "provider_called": False,
            "network_calls_made": False,
            "account_mutation_performed": False,
            "browser_selected_backend": False,
            "selected_backend_id_redacted": True,
            "token_burn": 0,
            "refresh_packet": selection,
            "next_action": "select_model_from_server_registry",
        }
    return {
        "schema_version": 1,
        "status": selection["status"],
        "machine_error_code": selection["machine_error_code"],
        "captured_at_utc": utc_now(),
        "mode_id": "codex_custom",
        "dry_run": True,
        "selected_model": model_id or DEFAULT_MODEL,
        "model_server_issued": True,
        "selection_dry_run_proven": selection["selection_dry_run_proven"],
        "live_selection_proven": False,
        "selection_proven": selection["selection_proven"],
        "inference_proven": False,
        "selected_source_class": selection["selected_source_class"],
        "selected_backend_id": selection["selected_backend_id"],
        "selected_backend_ref": selection["selected_backend_ref"],
        "selected_backend_id_redacted": True,
        "selected_backend_server_issued": selection["selected_backend_server_issued"],
        "selected_backend_source": selection["selected_backend_source"],
        "selected_route_ref": selection["selected_route_ref"],
        "selected_route_server_issued": selection["selected_route_server_issued"],
        "route_provenance_required": selection["route_provenance_required"],
        "route_provenance_proven": selection["route_provenance_proven"],
        "source_provenance_status": selection["source_provenance_status"],
        "browser_selected_backend": False,
        "selection_reason": selection["selection_reason"],
        "smoke_admitted": False,
        "smoke_not_admitted_reason": "runtime_meter_not_attached",
        "runtime_meter_attached": False,
        "responses_called": False,
        "chat_completions_called": False,
        "provider_called": False,
        "network_calls_made": False,
        "account_mutation_performed": False,
        "raw_backend_id_exposed": False,
        "claim_gate_status": selection["claim_gate_status"],
        "token_burn": 0,
        "negative_claim_basis": "account_smoke_dry_run_static_path_no_inference_adapter",
        "refresh_packet": selection,
        "next_action": "codex_custom_session_manager_contour",
    }
