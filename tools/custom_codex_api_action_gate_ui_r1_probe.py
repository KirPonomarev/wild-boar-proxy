#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from wild_boar_proxy.codex_model_registry import build_custom_api_action_gate_packet  # noqa: E402


FINAL_STATUS = "CUSTOM_CODEX_API_ACTION_GATE_OWNER_AUTH_REQUIRED"


def json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def operator_status() -> dict[str, Any]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.3-codex",
        },
        "claim_gate": {"status": "passed"},
        "models": {
            "ok": True,
            "server_issued": True,
            "model_ids": ["gpt-5.3-codex"],
        },
    }


def api_snapshot() -> dict[str, Any]:
    return {
        "status": "ok",
        "source": "api_connections_readonly",
        "primary_truth_ok": True,
        "routes": [
            {
                "route_id": "wbp-openrouter-smoke",
                "display_name": "OpenRouter smoke",
                "provider": "openrouter",
                "upstream_model": "deepseek/deepseek-chat",
                "cost_class": "paid_or_free_limited",
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
                "secret_status_label": "missing",
            }
        ],
    }


def build_packets() -> dict[str, dict[str, Any]]:
    gate = build_custom_api_action_gate_packet(
        {"api_model_id": "wbp-openrouter-smoke"},
        operator_status(),
        api_snapshot=api_snapshot(),
        owner_authorized=False,
        budget_policy_present=False,
    )
    packets = {
        "custom_codex_api_action_gate_packet.json": gate,
        "manual_api_choice_packet.json": gate["manual_api_choice_packet"],
        "browser_authority_guard_packet.json": gate["browser_authority_guard_packet"],
        "owner_authorization_packet.json": gate["owner_authorization_packet"],
        "budget_policy_packet.json": gate["budget_policy_packet"],
        "live_provider_request_boundary_packet.json": gate[
            "live_provider_request_boundary_packet"
        ],
        "false_green_boundary_packet.json": gate["false_green_boundary_packet"],
        "summary_packet.json": gate["summary_packet"],
    }
    packets["validation_packet.json"] = validate_packets(packets)
    return packets


def validate_packets(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    violations: list[str] = []
    gate = packets["custom_codex_api_action_gate_packet.json"]
    summary = packets["summary_packet.json"]
    boundary = packets["live_provider_request_boundary_packet.json"]
    choice = packets["manual_api_choice_packet.json"]
    browser = packets["browser_authority_guard_packet.json"]
    owner = packets["owner_authorization_packet.json"]
    budget = packets["budget_policy_packet.json"]
    false_green = packets["false_green_boundary_packet.json"]
    if gate.get("final_status") != FINAL_STATUS:
        violations.append("final_status_not_owner_auth_required")
    if summary.get("status") != "blocked":
        violations.append("summary_not_blocked")
    if choice.get("selection_intent_only") is not True:
        violations.append("selection_not_marked_intent_only")
    if choice.get("execution_proven") is True:
        violations.append("selection_counted_as_execution")
    if choice.get("provider_response_observed") is True:
        violations.append("route_counted_as_provider_response")
    if browser.get("browser_raw_backend_authority_widened") is True:
        violations.append("browser_backend_authority_widened")
    if owner.get("owner_live_authorization_present") is True:
        violations.append("owner_authorization_unexpectedly_present")
    if budget.get("budget_policy_present") is True:
        violations.append("budget_policy_unexpectedly_present")
    for field in (
        "live_provider_request_allowed",
        "live_call_attempted",
        "paid_route_used",
        "upstream_response_observed",
        "fallback_attempted",
        "parallel_fanout_attempted",
        "original_codex_touched",
        "raw_secret_recorded",
        "secret_value_recorded",
    ):
        if boundary.get(field) is True:
            violations.append(f"boundary_true:{field}")
    for key, value in false_green.items():
        if key in {"packet_kind", "status"}:
            continue
        if value is True:
            violations.append(f"false_green:{key}")
    return {
        "packet_kind": "custom_codex_api_action_gate_validation",
        "status": "ok" if not violations else "blocked",
        "violation_count": len(violations),
        "violations": violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    packets = build_packets()
    for filename, payload in packets.items():
        json_write(args.evidence_dir / filename, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "packet_count": len(packets),
                "final_status": packets["custom_codex_api_action_gate_packet.json"][
                    "final_status"
                ],
                "evidence_dir": str(args.evidence_dir.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
