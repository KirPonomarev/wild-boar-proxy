#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


STATUS_PROVEN_WITH_LIMITS = "LIVE_PROVIDER_RESPONSE_SMOKE_PROVEN_WITH_LIMITS"
STATUS_OWNER_AUTH_REQUIRED = "LIVE_PROVIDER_RESPONSE_SMOKE_KNOWN_BLOCKER_OWNER_AUTH_REQUIRED"
STATUS_BUDGET_POLICY_REQUIRED = "LIVE_PROVIDER_RESPONSE_SMOKE_KNOWN_BLOCKER_BUDGET_POLICY_REQUIRED"
STATUS_ROUTE_OR_PROVIDER_FAILURE = "LIVE_PROVIDER_RESPONSE_SMOKE_KNOWN_BLOCKER_ROUTE_OR_PROVIDER_FAILURE"

FORBIDDEN_BROWSER_BACKEND_FIELDS = {
    "base_url",
    "api_key",
    "secret",
    "secret_ref",
    "auth_path",
    "auth_ref",
    "route_config",
    "account_id",
    "CODEX_HOME",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _bool(value: Any) -> bool:
    return value is True


def _text(value: Any) -> str:
    return str(value or "").strip()


def _forbidden_browser_fields(payload: dict[str, Any]) -> list[str]:
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key) in FORBIDDEN_BROWSER_BACKEND_FIELDS:
                    found.add(str(key))
                walk(child)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return sorted(found)


def _owner_failed_checks(request: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if not _bool(request.get("owner_authorized")):
        failed.append("owner_authorization_missing")
    if not _text(request.get("provider_id")):
        failed.append("provider_id_missing")
    if not (_text(request.get("model_id")) or _text(request.get("server_model_id"))):
        failed.append("model_id_missing")
    if not _text(request.get("route_id")):
        failed.append("route_id_missing")
    if int(request.get("request_limit") or 0) <= 0:
        failed.append("request_limit_missing")
    if not _text(request.get("cost_ceiling")):
        failed.append("cost_ceiling_missing")
    if not _bool(request.get("credential_ref_allowed")):
        failed.append("credential_ref_authorization_missing")
    if not _bool(request.get("fallback_forbidden")):
        failed.append("fallback_must_be_forbidden")
    if not _bool(request.get("parallel_fanout_forbidden")):
        failed.append("parallel_fanout_must_be_forbidden")
    if _forbidden_browser_fields(dict(request.get("browser_payload") or {})):
        failed.append("raw_browser_backend_fields_present")
    return failed


def _budget_failed_checks(request: dict[str, Any]) -> list[str]:
    failed: list[str] = []
    if not _bool(request.get("budget_policy_present")):
        failed.append("budget_policy_missing")
    if int(request.get("request_limit") or 0) != 1:
        failed.append("request_limit_must_be_one")
    if int(request.get("retry_limit") or 0) > 1:
        failed.append("retry_limit_exceeds_bounded_maximum")
    if not _text(request.get("cost_ceiling")):
        failed.append("cost_ceiling_missing")
    if not _bool(request.get("fallback_forbidden")):
        failed.append("fallback_forbidden_policy_missing")
    if not _bool(request.get("parallel_fanout_forbidden")):
        failed.append("parallel_fanout_forbidden_policy_missing")
    return failed


def _final_status(owner_failed: list[str], budget_failed: list[str], live_result: dict[str, Any]) -> str:
    if owner_failed:
        return STATUS_OWNER_AUTH_REQUIRED
    if budget_failed:
        return STATUS_BUDGET_POLICY_REQUIRED
    if live_result.get("upstream_response_observed") is True:
        return STATUS_PROVEN_WITH_LIMITS
    return STATUS_ROUTE_OR_PROVIDER_FAILURE


def validate_packets(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    summary = packets.get("live_provider_response_smoke_summary_packet.json", {})
    owner = packets.get("owner_authorization_packet.json", {})
    budget = packets.get("budget_policy_packet.json", {})
    choice = packets.get("manual_model_choice_packet.json", {})
    evidence = packets.get("live_provider_response_evidence_packet.json", {})
    false_green = packets.get("false_green_boundary_packet.json", {})

    final_status = str(summary.get("final_status") or "")
    if final_status not in {
        STATUS_PROVEN_WITH_LIMITS,
        STATUS_OWNER_AUTH_REQUIRED,
        STATUS_BUDGET_POLICY_REQUIRED,
        STATUS_ROUTE_OR_PROVIDER_FAILURE,
    }:
        violations.append({"violation": "unknown_final_status", "final_status": final_status})
    if final_status == STATUS_PROVEN_WITH_LIMITS and evidence.get("upstream_response_observed") is not True:
        violations.append({"violation": "proven_status_without_upstream_response"})
    if final_status == STATUS_PROVEN_WITH_LIMITS and evidence.get("request_attempted") is not True:
        violations.append({"violation": "proven_status_without_request_attempt"})
    if final_status == STATUS_PROVEN_WITH_LIMITS and owner.get("status") != "ok":
        violations.append({"violation": "proven_status_without_owner_authorization"})
    if final_status == STATUS_PROVEN_WITH_LIMITS and budget.get("status") != "ok":
        violations.append({"violation": "proven_status_without_budget_policy"})

    if choice.get("forbidden_browser_backend_fields"):
        if choice.get("browser_raw_backend_authority_widened") is not True:
            violations.append({"violation": "forbidden_browser_fields_not_classified"})
    if evidence.get("fallback_attempted") is True:
        violations.append({"violation": "fallback_attempted"})
    if evidence.get("parallel_fanout_attempted") is True:
        violations.append({"violation": "parallel_fanout_attempted"})
    if evidence.get("retry_count", 0) > int(budget.get("retry_limit") or 0):
        violations.append({"violation": "retry_count_exceeds_budget"})
    if evidence.get("raw_secret_recorded") is True or evidence.get("secret_value_recorded") is True:
        violations.append({"violation": "secret_recorded"})
    if evidence.get("original_codex_touched") is True:
        violations.append({"violation": "original_codex_touched"})

    for key, value in false_green.items():
        if key in {"captured_at_utc", "packet_kind", "status"}:
            continue
        if value is True:
            violations.append({"violation": "false_green_guard_enabled", "guard": key})

    return {
        "status": "ok" if not violations else "blocked",
        "violation_count": len(violations),
        "violations": violations,
    }


def build_packets(*, repo_root: Path, evidence_dir: Path, request: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    del repo_root, evidence_dir
    req = dict(request or {})
    req.setdefault("owner_authorized", False)
    req.setdefault("provider_id", "")
    req.setdefault("model_id", "")
    req.setdefault("server_model_id", "")
    req.setdefault("route_id", "")
    req.setdefault("request_limit", 0)
    req.setdefault("retry_limit", 0)
    req.setdefault("cost_ceiling", "")
    req.setdefault("cost_class", "unknown")
    req.setdefault("credential_ref_allowed", False)
    req.setdefault("budget_policy_present", False)
    req.setdefault("fallback_forbidden", True)
    req.setdefault("parallel_fanout_forbidden", True)
    req.setdefault("browser_payload", {})
    req.setdefault("live_result", {})

    forbidden_browser_fields = _forbidden_browser_fields(dict(req.get("browser_payload") or {}))
    owner_failed = _owner_failed_checks(req)
    budget_failed = _budget_failed_checks(req)
    live_result = dict(req.get("live_result") or {})
    final_status = _final_status(owner_failed, budget_failed, live_result)

    owner_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "owner_authorization",
        "status": "ok" if not owner_failed else "blocked",
        "failed_checks": owner_failed,
        "owner_authorized": _bool(req.get("owner_authorized")),
        "provider_id": _text(req.get("provider_id")),
        "model_id": _text(req.get("model_id")),
        "server_model_id": _text(req.get("server_model_id")),
        "route_id": _text(req.get("route_id")),
        "request_limit": int(req.get("request_limit") or 0),
        "cost_ceiling": _text(req.get("cost_ceiling")),
        "credential_ref_allowed": _bool(req.get("credential_ref_allowed")),
        "raw_secret_authorized": False,
        "raw_secret_recorded": False,
        "fallback_forbidden": _bool(req.get("fallback_forbidden")),
        "parallel_fanout_forbidden": _bool(req.get("parallel_fanout_forbidden")),
    }
    budget_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "budget_policy",
        "status": "ok" if not budget_failed and not owner_failed else "blocked",
        "failed_checks": budget_failed,
        "budget_policy_present": _bool(req.get("budget_policy_present")),
        "cost_class": _text(req.get("cost_class")) or "unknown",
        "request_limit": int(req.get("request_limit") or 0),
        "retry_limit": int(req.get("retry_limit") or 0),
        "cost_ceiling": _text(req.get("cost_ceiling")),
        "fallback_policy": "forbidden" if _bool(req.get("fallback_forbidden")) else "not_forbidden",
        "parallel_fanout_policy": "forbidden"
        if _bool(req.get("parallel_fanout_forbidden"))
        else "not_forbidden",
        "quota_rate_limit_handling": "classify_without_unbounded_retry",
        "timeout_5xx_handling": "classify_without_fallback_storm",
        "paid_call_without_budget_forbidden": True,
    }
    choice_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "manual_model_choice",
        "status": "ok" if not owner_failed and not forbidden_browser_fields else "blocked",
        "manual_choice_required": True,
        "manual_choice_proven": not owner_failed and bool(_text(req.get("server_model_id")) or _text(req.get("model_id"))),
        "server_issued_id": _text(req.get("server_model_id")) or _text(req.get("model_id")),
        "provider_id": _text(req.get("provider_id")),
        "route_id": _text(req.get("route_id")),
        "auto_routing_used": False,
        "cross_lane_fallback_forbidden": _bool(req.get("fallback_forbidden")),
        "forbidden_browser_backend_fields": forbidden_browser_fields,
        "browser_raw_backend_authority_widened": bool(forbidden_browser_fields),
        "selection_intent_counts_as_execution": False,
    }
    evidence_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "live_provider_response_evidence",
        "status": "ok" if final_status == STATUS_PROVEN_WITH_LIMITS else "blocked",
        "request_attempted": live_result.get("request_attempted") is True,
        "upstream_response_observed": live_result.get("upstream_response_observed") is True,
        "provider_id": _text(req.get("provider_id")),
        "model_id": _text(req.get("model_id")),
        "server_model_id": _text(req.get("server_model_id")),
        "route_id": _text(req.get("route_id")),
        "selected_source_provenance": live_result.get("selected_source_provenance", ""),
        "status_code": live_result.get("status_code"),
        "error_class": live_result.get("error_class", "owner_authorization_required" if owner_failed else ""),
        "latency_ms": live_result.get("latency_ms"),
        "token_metadata_available": live_result.get("token_metadata_available") is True,
        "token_metadata": live_result.get("token_metadata") if live_result.get("token_metadata_available") is True else {},
        "cost_metadata_available": live_result.get("cost_metadata_available") is True,
        "cost_metadata": live_result.get("cost_metadata") if live_result.get("cost_metadata_available") is True else {},
        "secret_value_recorded": live_result.get("secret_value_recorded") is True,
        "raw_secret_recorded": live_result.get("raw_secret_recorded") is True,
        "fallback_attempted": live_result.get("fallback_attempted") is True,
        "retry_count": int(live_result.get("retry_count") or 0),
        "parallel_fanout_attempted": live_result.get("parallel_fanout_attempted") is True,
        "original_codex_touched": live_result.get("original_codex_touched") is True,
        "route_snapshot_counted_as_provider_response": False,
        "recording_runner_counted_as_live_upstream": False,
        "plain_text_response_counts_as_tools_proof": False,
        "plain_text_response_counts_as_streaming_proof": False,
        "provider_family_compatibility_claimed": False,
        "acceleration_claimed": False,
    }
    failure_packet = {
        "captured_at_utc": utc_now(),
        "packet_kind": "failure_classification",
        "status": "ok",
        "final_status": final_status,
        "failure_class": (
            "owner_authorization_missing"
            if final_status == STATUS_OWNER_AUTH_REQUIRED
            else "budget_policy_missing"
            if final_status == STATUS_BUDGET_POLICY_REQUIRED
            else _text(live_result.get("error_class")) or "route_or_provider_failure"
            if final_status == STATUS_ROUTE_OR_PROVIDER_FAILURE
            else ""
        ),
        "known_failure_classes": [
            "owner_authorization_missing",
            "budget_policy_missing",
            "credentials_missing",
            "route_not_visible",
            "route_not_ready",
            "provider_auth_failed",
            "quota_or_rate_limit",
            "upstream_5xx",
            "timeout",
            "response_shape_mismatch",
            "blocked_by_safety_policy",
            "unknown_blocker",
        ],
        "owner_failed_checks": owner_failed,
        "budget_failed_checks": budget_failed,
    }
    false_green = {
        "captured_at_utc": utc_now(),
        "packet_kind": "false_green_boundary",
        "status": "ok",
        "route_snapshot_treated_as_provider_response": False,
        "recording_runner_treated_as_live_upstream": False,
        "selection_intent_treated_as_execution": False,
        "one_provider_row_treated_as_family_compatibility": False,
        "plain_text_treated_as_tools_proof": False,
        "plain_text_treated_as_streaming_proof": False,
        "success_treated_as_acceleration_proof": False,
        "paid_call_without_budget_packet": False,
        "retry_storm_allowed": False,
        "fallback_storm_allowed": False,
        "hidden_model_or_route_substitution_allowed": False,
    }
    summary = {
        "captured_at_utc": utc_now(),
        "packet_kind": "live_provider_response_smoke_summary",
        "status": "ok" if final_status == STATUS_PROVEN_WITH_LIMITS else "blocked",
        "final_status": final_status,
        "live_request_attempted": evidence_packet["request_attempted"],
        "upstream_response_observed": evidence_packet["upstream_response_observed"],
        "owner_authorization_status": owner_packet["status"],
        "budget_policy_status": budget_packet["status"],
        "manual_choice_status": choice_packet["status"],
        "fallback_attempted": evidence_packet["fallback_attempted"],
        "parallel_fanout_attempted": evidence_packet["parallel_fanout_attempted"],
        "original_codex_touched": evidence_packet["original_codex_touched"],
        "with_limits_required": final_status == STATUS_PROVEN_WITH_LIMITS,
    }
    packets = {
        "owner_authorization_packet.json": owner_packet,
        "budget_policy_packet.json": budget_packet,
        "manual_model_choice_packet.json": choice_packet,
        "live_provider_response_evidence_packet.json": evidence_packet,
        "failure_classification_packet.json": failure_packet,
        "false_green_boundary_packet.json": false_green,
        "live_provider_response_smoke_summary_packet.json": summary,
    }
    packets["validation_packet.json"] = {
        "captured_at_utc": utc_now(),
        "packet_kind": "live_provider_response_smoke_validation",
        **validate_packets(packets),
    }
    return packets


def _request_from_args(args: argparse.Namespace) -> dict[str, Any]:
    browser_payload: dict[str, Any] = {}
    if args.browser_payload_json:
        browser_payload = json.loads(args.browser_payload_json)
    return {
        "owner_authorized": args.owner_authorized,
        "provider_id": args.provider_id,
        "model_id": args.model_id,
        "server_model_id": args.server_model_id,
        "route_id": args.route_id,
        "request_limit": args.request_limit,
        "retry_limit": args.retry_limit,
        "cost_ceiling": args.cost_ceiling,
        "cost_class": args.cost_class,
        "credential_ref_allowed": args.credential_ref_allowed,
        "budget_policy_present": args.budget_policy_present,
        "fallback_forbidden": not args.allow_fallback,
        "parallel_fanout_forbidden": not args.allow_parallel_fanout,
        "browser_payload": browser_payload,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--owner-authorized", action="store_true")
    parser.add_argument("--provider-id", default="")
    parser.add_argument("--model-id", default="")
    parser.add_argument("--server-model-id", default="")
    parser.add_argument("--route-id", default="")
    parser.add_argument("--request-limit", type=int, default=0)
    parser.add_argument("--retry-limit", type=int, default=0)
    parser.add_argument("--cost-ceiling", default="")
    parser.add_argument("--cost-class", default="unknown")
    parser.add_argument("--credential-ref-allowed", action="store_true")
    parser.add_argument("--budget-policy-present", action="store_true")
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--allow-parallel-fanout", action="store_true")
    parser.add_argument("--browser-payload-json", default="")
    args = parser.parse_args(argv)

    packets = build_packets(
        repo_root=args.repo_root.resolve(),
        evidence_dir=args.evidence_dir.resolve(),
        request=_request_from_args(args),
    )
    for filename, payload in packets.items():
        json_write(args.evidence_dir / filename, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "packet_count": len(packets),
                "evidence_dir": str(args.evidence_dir.resolve()),
                "packets": sorted(packets),
                "final_status": packets["live_provider_response_smoke_summary_packet.json"][
                    "final_status"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
