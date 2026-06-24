# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Final product-readiness join for the GPT+API/DIP Custom Codex feature."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_READ
from .core import packets
from .gpt_api_dip_acceptance_gate import GPT_API_DIP_ACCEPTANCE_PACKET_KIND
from .runtime import RuntimePaths, write_json_atomic
from .runtime_dispatch_mode_truth import (
    DISPATCH_MODE_CHATGPT_API,
    EXECUTOR_DIP_API_ROUTE,
    ORCHESTRATOR_CHATGPT,
    dispatch_mode_truth_fields,
)


GPT_API_DIP_PRODUCT_READY_PACKET_KIND = "wbp_gpt_api_dip_product_ready_gate"
GPT_API_DIP_PRODUCT_READY_FILE_NAME = "gpt-api-dip-product-ready-gate.packet.json"
GPT_API_DIP_PRODUCT_READY_OK = "OK"
GPT_API_DIP_PRODUCT_READY_BLOCKED = "WBP_GPT_API_DIP_PRODUCT_READY_BLOCKED"
GPT_API_DIP_PRODUCT_READY_UNSAFE_PACKET = (
    "WBP_GPT_API_DIP_PRODUCT_READY_UNSAFE_PACKET"
)

_ACCEPTANCE_REQUIRED_TRUE_FIELDS = (
    "feature_ready",
    "gpt_api_dip_ready",
    "dip_action_bridge_proven",
    "dip_code_written",
    "dip_code_verified",
    "custom_codex_ui_visibility_proven",
    "native_custom_codex_visible_flow_proven",
    "full_runtime_dispatch_proven",
    "fresh_sealed_e2e_proven",
    "api_backed_custom_codex_dip_feature_ready",
    "api_backed_custom_codex_auth_session_proven",
    "api_key_only",
    "runtime_dispatch_mode_truth_recorded",
    "dispatch_mode_truth_proven",
    "chatgpt_plus_api_mode_proven",
    "gpt_api_mode_proven",
    "chatgpt_lane_selected",
    "api_route_selected",
    "chatgpt_lane_called",
    "api_route_called",
)

_ACCEPTANCE_REQUIRED_FALSE_FIELDS = (
    "gate_runs_live_dispatch",
    "gate_reads_audit_history",
    "api_key_only_counts_as_ui_session",
    "logged_in_ui_session_proven",
    "custom_codex_ui_session_ready",
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "raw_jsonl_recorded",
    "tool_call_arguments_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "wrapper_substitution_used",
    "wrapper_substitution_detected",
    "wrapper_substitution_allowed",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_packet(path: str | Path | None) -> tuple[dict[str, Any], str, str]:
    if path is None or not str(path).strip():
        return {}, "", "missing_path"
    packet_path = Path(path).expanduser()
    try:
        data = json.loads(packet_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, "", "file_missing"
    except json.JSONDecodeError:
        return {}, "", "invalid_json"
    if not isinstance(data, dict):
        return {}, "", "not_json_object"
    return data, _sha256_file(packet_path), ""


def _acceptance_failures(packet: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if packet.get("packet_kind") != GPT_API_DIP_ACCEPTANCE_PACKET_KIND:
        failures.append("acceptance_packet_kind_not_expected")
    if packet.get("status") != "ok":
        failures.append("acceptance_status_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("acceptance_machine_error_code_not_ok")
    if packet.get("feature_ready_mode") != "gpt_api_dip_custom_codex":
        failures.append("acceptance_feature_ready_mode_not_expected")
    if packet.get("blocking_reasons") != []:
        failures.append("acceptance_blocking_reasons_not_empty")
    for field in (
        "fresh_sealed_failures",
        "dip_feature_failures",
        "dip_action_failures",
    ):
        if packet.get(field) != []:
            failures.append(f"acceptance_{field}_not_empty")
    for field in _ACCEPTANCE_REQUIRED_TRUE_FIELDS:
        if packet.get(field) is not True:
            failures.append(f"acceptance_{field}_not_true")
    for field in _ACCEPTANCE_REQUIRED_FALSE_FIELDS:
        if packet.get(field) is not False:
            failures.append(f"acceptance_{field}_not_false")
    if packet.get("does_not_prove_product_ready") is not True:
        failures.append("acceptance_does_not_prove_product_ready_not_true")
    return failures


def build_gpt_api_dip_product_ready_gate_packet(
    *,
    acceptance_packet: dict[str, Any],
    acceptance_sha256: str = "",
    input_failures: list[str] | None = None,
    evidence_written: bool = False,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    input_failures = input_failures or []
    acceptance_failures = (
        _acceptance_failures(acceptance_packet)
        if acceptance_packet
        else ["acceptance_packet_missing"]
    )
    unsafe = (
        packets.command_packet_has_secret_leak(acceptance_packet)
        if acceptance_packet
        else False
    )
    blocking_reasons = sorted(set(input_failures + acceptance_failures))
    if unsafe:
        blocking_reasons.append("product_ready_input_packet_secret_leak")
    ok = not blocking_reasons
    extra = {
        "schema_version": 1,
        "packet_kind": GPT_API_DIP_PRODUCT_READY_PACKET_KIND,
        "proof_scope": "gpt_api_dip_custom_codex_feature_product_readiness",
        "operator_command_surface": (
            "wild-boar-proxy codex-runner gpt-api-dip-product-ready-gate"
        ),
        "operator_command_mode": "final_join",
        "gate_source": "gpt_api_dip_acceptance_gate_packet",
        "gate_runs_live_dispatch": False,
        "gate_reads_audit_history": False,
        "feature_ready": ok,
        "feature_ready_mode": "gpt_api_dip_custom_codex" if ok else "blocked",
        "gpt_api_dip_ready": ok,
        "product_ready": ok,
        **dispatch_mode_truth_fields(
            execution_mode=DISPATCH_MODE_CHATGPT_API,
            truth_source="gpt_api_dip_product_ready_gate_join",
            orchestrator=ORCHESTRATOR_CHATGPT,
            executor=EXECUTOR_DIP_API_ROUTE,
            mode_proven=ok,
            chatgpt_lane_selected=acceptance_packet.get("chatgpt_lane_selected") is True,
            api_route_selected=acceptance_packet.get("api_route_selected") is True,
            chatgpt_lane_called=acceptance_packet.get("chatgpt_lane_called") is True,
            api_route_called=acceptance_packet.get("api_route_called") is True,
            target_repo_required=acceptance_packet.get("target_repo_required") is True,
            target_repo_available=acceptance_packet.get("target_repo_available") is True,
            target_repo_fallback_used=acceptance_packet.get("target_repo_fallback_used")
            is True,
        ),
        "product_ready_scope": "gpt_api_dip_custom_codex_feature",
        "product_ready_is_feature_scoped": True,
        "production_release_ready": False,
        "production_release_claim": "not_made",
        "distribution_release_ready": False,
        "signing_status": "not_proven",
        "notarization_status": "not_proven",
        "dmg_status": "not_proven",
        "pkg_status": "not_proven",
        "does_not_prove_distribution_release": True,
        "does_not_prove_signing": True,
        "does_not_prove_notarization": True,
        "does_not_prove_packaged_release": True,
        "custom_codex_ui_visibility_proven": bool(
            ok and acceptance_packet.get("custom_codex_ui_visibility_proven") is True
        ),
        "native_custom_codex_visible_flow_proven": bool(
            ok
            and acceptance_packet.get("native_custom_codex_visible_flow_proven")
            is True
        ),
        "full_runtime_dispatch_proven": bool(
            ok and acceptance_packet.get("full_runtime_dispatch_proven") is True
        ),
        "fresh_sealed_e2e_proven": bool(
            ok and acceptance_packet.get("fresh_sealed_e2e_proven") is True
        ),
        "api_backed_custom_codex_dip_feature_ready": bool(
            ok
            and acceptance_packet.get("api_backed_custom_codex_dip_feature_ready")
            is True
        ),
        "dip_action_bridge_proven": bool(
            ok and acceptance_packet.get("dip_action_bridge_proven") is True
        ),
        "dip_code_written": bool(ok and acceptance_packet.get("dip_code_written") is True),
        "dip_code_verified": bool(
            ok and acceptance_packet.get("dip_code_verified") is True
        ),
        "api_key_only": bool(ok and acceptance_packet.get("api_key_only") is True),
        "api_key_only_counts_as_ui_session": False,
        "logged_in_ui_session_proven": False,
        "custom_codex_ui_session_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "wrapper_substitution_used": False,
        "wrapper_substitution_detected": False,
        "wrapper_substitution_allowed": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "acceptance_packet_sha256": acceptance_sha256,
        "input_file_paths_recorded": False,
        "acceptance_failures": acceptance_failures,
        "blocking_reasons": blocking_reasons,
        "evidence_written": evidence_written,
        "created_at_utc": _utc_now(),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP GPT+API/DIP feature product-readiness gate passed."
            if ok
            else "WBP GPT+API/DIP feature product-readiness gate is BLOCKED."
        ),
        machine_error_code=(
            GPT_API_DIP_PRODUCT_READY_OK
            if ok
            else GPT_API_DIP_PRODUCT_READY_UNSAFE_PACKET
            if unsafe
            else GPT_API_DIP_PRODUCT_READY_BLOCKED
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files or [],
        effect=EFFECT_MUTATE if evidence_written else EFFECT_READ,
        extra=extra,
    )


def run_gpt_api_dip_product_ready_gate_command(
    *,
    paths: RuntimePaths,
    acceptance_gate_file: str,
    proof_dir: str | None = None,
) -> dict[str, Any]:
    del paths
    acceptance, acceptance_sha, acceptance_error = _load_json_packet(
        acceptance_gate_file
    )
    input_failures = []
    if acceptance_error:
        input_failures.append(f"acceptance_{acceptance_error}")
    changed_files: list[str] = []
    evidence_written = False
    packet = build_gpt_api_dip_product_ready_gate_packet(
        acceptance_packet=acceptance,
        acceptance_sha256=acceptance_sha,
        input_failures=input_failures,
        evidence_written=False,
        changed_files=[],
    )
    if proof_dir:
        output_dir = Path(proof_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / GPT_API_DIP_PRODUCT_READY_FILE_NAME
        evidence_written = True
        changed_files = [str(output_file)]
        packet = build_gpt_api_dip_product_ready_gate_packet(
            acceptance_packet=acceptance,
            acceptance_sha256=acceptance_sha,
            input_failures=input_failures,
            evidence_written=evidence_written,
            changed_files=changed_files,
        )
        write_json_atomic(output_file, packet)
    return packet
