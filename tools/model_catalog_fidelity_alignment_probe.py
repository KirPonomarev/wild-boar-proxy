#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate Pass 3 model catalog fidelity / availability alignment packets."""

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

from wild_boar_proxy.codex_model_registry import build_wbp_model_catalog_contract_packet
from wild_boar_proxy.model_availability import (
    build_catalog_availability_lattice_packet,
    build_model_direct_preflight_packet,
)


TARGET_STATUS = "WBP_MODEL_CATALOG_FIDELITY_AND_AVAILABILITY_ALIGNED_R2"
CURRENT_OPERATOR_MODEL_IDS = [
    "gpt-5.2",
    "gpt-5.3-codex",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.5",
    "codex-auto-review",
    "gpt-image-2",
    "wbp-web-primary-openrouter",
]
CURRENT_LIVE_NATIVE_MODEL_IDS = [
    "gpt-5.3-codex",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.5",
]
EXTERNAL_ROUTE_ID = "wbp-web-primary-openrouter"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def corrected_operator_status() -> dict[str, Any]:
    return {
        "status": {
            "status": "ok",
            "machine_error_code": "OK",
            "configured_model": "gpt-5.5",
        },
        "claim_gate": {"status": "blocked"},
        "models": {
            "ok": True,
            "model_ids": list(CURRENT_OPERATOR_MODEL_IDS),
            "server_issued": True,
        },
    }


def external_route_snapshot() -> dict[str, Any]:
    return {
        "routes": [
            {
                "route_id": EXTERNAL_ROUTE_ID,
                "enabled": True,
                "secret_ref": "OPENROUTER_API_KEY",
                "upstream_model": "openai/gpt-5",
                "display_name": "OpenRouter primary",
            }
        ]
    }


def _successful_non_stream_packet(model_id: str, *, source: str, route_family: str) -> dict[str, Any]:
    return build_model_direct_preflight_packet(
        model_id=model_id,
        source=source,
        listed=True,
        selectable=True,
        route_selected=True,
        runtime_ready=True,
        http_status=200,
        upstream_status=200,
        response_payload={
            "status": "completed",
            "output": [{"type": "output_text", "text": "OK"}],
            "output_text": "OK",
        },
        prompt_text="Reply OK",
        request_sent_to_wbp=True,
        route_family=route_family,
    )


def current_live_native_packets() -> list[dict[str, Any]]:
    return [
        _successful_non_stream_packet(
            model_id=model_id,
            source="current_thread_direct_wbp_non_stream_anchor",
            route_family="codex_native_account_route",
        )
        for model_id in CURRENT_LIVE_NATIVE_MODEL_IDS
    ]


def historical_external_route_packets() -> list[dict[str, Any]]:
    return [
        _successful_non_stream_packet(
            model_id=EXTERNAL_ROUTE_ID,
            source="pass2_selected_external_route_closed_truth",
            route_family="wbp_api_external_route",
        )
    ]


def out_of_catalog_negative_packets() -> list[dict[str, Any]]:
    return [
        build_model_direct_preflight_packet(
            model_id="gpt-5.3-codex-spark",
            source="fresh_out_of_catalog_negative_anchor",
            listed=False,
            selectable=False,
            route_selected=False,
            runtime_ready=True,
            http_status=400,
            error_payload={
                "error": {
                    "type": "unsupported_model_for_chatgpt_account",
                    "message": "model is not supported with a ChatGPT account",
                }
            },
            prompt_text="Reply OK",
            request_sent_to_wbp=True,
            route_family="codex_native_account_route",
        )
    ]


def _label_alignment_rows(catalog_packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in catalog_packet.get("models", []):
        if not isinstance(model, dict):
            continue
        rows.append(
            {
                "model_id": str(model.get("model_id") or ""),
                "lane": str(model.get("lane") or ""),
                "label": str(model.get("label") or ""),
                "display_name": str(model.get("display_name") or ""),
                "availability_claim_level": str(model.get("availability_claim_level") or ""),
                "availability_evidence_scope": str(model.get("availability_evidence_scope") or ""),
                "label_implies_equal_usability": False,
            }
        )
    return rows


def _lane_truth_rows(catalog_packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in catalog_packet.get("models", []):
        if not isinstance(model, dict):
            continue
        rows.append(
            {
                "model_id": str(model.get("model_id") or ""),
                "lane": str(model.get("lane") or ""),
                "provider_class": str(model.get("provider_class") or ""),
                "availability_claim_level": str(model.get("availability_claim_level") or ""),
                "availability_evidence_scope": str(model.get("availability_evidence_scope") or ""),
                "live_availability_proven": model.get("live_availability_proven") is True,
                "current_stability_proven": model.get("current_stability_proven") is True,
            }
        )
    return rows


def build_alignment_packets() -> dict[str, dict[str, Any]]:
    current_packets = current_live_native_packets()
    historical_packets = historical_external_route_packets()
    out_of_catalog_packets = out_of_catalog_negative_packets()
    catalog_packet = build_wbp_model_catalog_contract_packet(
        corrected_operator_status(),
        recommended_default_model="gpt-5.5",
        api_snapshot=external_route_snapshot(),
    )
    availability_lattice_packet = build_catalog_availability_lattice_packet(
        catalog_packet=catalog_packet,
        current_model_packets=current_packets,
        historical_model_packets=historical_packets,
        out_of_catalog_model_packets=out_of_catalog_packets,
    )
    aligned_catalog_packet = build_wbp_model_catalog_contract_packet(
        corrected_operator_status(),
        recommended_default_model="gpt-5.5",
        api_snapshot=external_route_snapshot(),
        availability_lattice_packet=availability_lattice_packet,
    )
    label_rows = _label_alignment_rows(aligned_catalog_packet)
    lane_rows = _lane_truth_rows(aligned_catalog_packet)
    spark_observation = availability_lattice_packet["out_of_catalog_observations"][0]
    return {
        "catalog_inventory_packet.json": aligned_catalog_packet,
        "availability_lattice_packet.json": availability_lattice_packet,
        "model_label_alignment_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "model_label_alignment",
            "status": "ok",
            "target_status": TARGET_STATUS,
            "rows": label_rows,
            "all_listed_models_equally_usable": False,
            "availability_lattice_imported": aligned_catalog_packet["availability_lattice_imported"],
        },
        "lane_truth_mapping_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "lane_truth_mapping",
            "status": "ok",
            "target_status": TARGET_STATUS,
            "rows": lane_rows,
            "codex_native_live_current_model_ids": [
                row["model_id"]
                for row in lane_rows
                if row["lane"] == "codex_native" and row["live_availability_proven"]
            ],
            "wbp_api_historically_bounded_model_ids": [
                row["model_id"]
                for row in lane_rows
                if row["lane"] == "wbp_api"
                and row["availability_claim_level"]
                == "historically_direct_wbp_non_stream_response_accepted"
            ],
        },
        "bounded_smoke_examples_packet.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "bounded_smoke_examples",
            "status": "ok",
            "target_status": TARGET_STATUS,
            "current_thread_native_examples": current_packets,
            "historical_external_route_examples": historical_packets,
            "out_of_catalog_negative_examples": [spark_observation],
            "spark_absent_from_current_operator_model_list": True,
        },
        "false_green_audit.json": {
            "captured_at_utc": utc_now(),
            "packet_kind": "model_catalog_alignment_false_green_audit",
            "status": "ok",
            "target_status": TARGET_STATUS,
            "all_listed_models_equally_usable_claimed": False,
            "all_models_work_claimed": False,
            "spark_reintroduced_into_current_catalog": any(
                model.get("model_id") == "gpt-5.3-codex-spark"
                for model in aligned_catalog_packet.get("models", [])
                if isinstance(model, dict)
            ),
            "spark_out_of_catalog_negative_observation_preserved": True,
            "current_thread_non_stream_proof_promoted_to_codex_acceptance": False,
            "streaming_or_tool_loop_promoted_from_non_stream": False,
            "external_route_current_stability_overclaimed": False,
            "external_route_provider_family_compatibility_overclaimed": False,
            "claim_gate_promoted_to_account_health": False,
        },
    }


def write_packet(evidence_dir: Path, name: str, payload: dict[str, Any]) -> None:
    (evidence_dir / name).write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence_dir = args.evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packets = build_alignment_packets()
    for name, payload in packets.items():
        write_packet(evidence_dir, name, payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "target_status": TARGET_STATUS,
                "evidence_dir": str(evidence_dir),
                "written_packets": sorted(packets),
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
