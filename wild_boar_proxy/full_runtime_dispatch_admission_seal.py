# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256
from .command_effects import EFFECT_READ
from .core import packets
from .full_runtime_dispatch_admission import (
    FULL_RUNTIME_DISPATCH_ADMISSION_OK,
    FULL_RUNTIME_DISPATCH_ADMISSION_PACKET_KIND,
    run_full_runtime_dispatch_admission_command,
)
from .router_hook_entry import _safe_text


FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_PACKET_KIND = (
    "wbp_full_runtime_dispatch_admission_seal"
)

FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_OK = "OK"
FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_INPUT_INVALID = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_INPUT_INVALID"
)
FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED"
)
FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_UNSAFE_SOURCE = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_UNSAFE_SOURCE"
)

_REQUIRED_TRUE_FIELDS = (
    "proof_admitted",
    "feature_proof_admitted",
    "expected_freshness_anchor_digest_bound",
    "external_freshness_proven",
    "full_runtime_dispatch_runner_proven",
    "full_runtime_dispatch_proven",
    "custom_codex_flow_proven",
    "api_lane_called",
    "dispatch_proven",
    "codex_working_flow_delivery_proven",
    "custom_codex_ui_visibility_proven",
)

_REQUIRED_FALSE_FIELDS = (
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "raw_dom_exposed",
    "raw_ax_tree_exposed",
    "raw_jsonl_recorded",
    "tool_call_arguments_recorded",
    "route_candidate_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "raw_freshness_anchor_recorded",
    "proof_dir_path_recorded",
    "artifact_file_paths_recorded",
    "state_written",
    "runtime_effective_truth_written",
    "evidence_written",
    "file_mutation_attempted",
)


def _canonical_packet_sha256(packet: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(packet),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required_true_failures(packet: Mapping[str, Any]) -> list[str]:
    return [
        f"admission_{field}_not_true"
        for field in _REQUIRED_TRUE_FIELDS
        if packet.get(field) is not True
    ]


def _required_false_failures(packet: Mapping[str, Any]) -> list[str]:
    return [
        f"admission_{field}_not_false"
        for field in _REQUIRED_FALSE_FIELDS
        if packet.get(field) is not False
    ]


def _safe_reasons(value: object) -> list[str]:
    reasons: set[str] = set()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            reason = _safe_text(item, limit=96)
            if packets.is_command_value_token(reason):
                reasons.add(reason)
    return sorted(reasons)


def _secret_values_for_proof_dir(proof_dir: str) -> list[str]:
    if not proof_dir:
        return []
    if "/" not in proof_dir and "\\" not in proof_dir:
        return []
    return [proof_dir]


def _input_failures(*, expected_freshness_anchor_digest: str | None) -> list[str]:
    failures: list[str] = []
    if not expected_freshness_anchor_digest:
        failures.append("expected_freshness_anchor_digest_missing")
    elif not _hex_sha256(expected_freshness_anchor_digest):
        failures.append("expected_freshness_anchor_digest_invalid")
    return failures


def _admission_failures(admission_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if admission_packet.get("packet_kind") != FULL_RUNTIME_DISPATCH_ADMISSION_PACKET_KIND:
        failures.append("admission_packet_kind_invalid")
    if admission_packet.get("status") != "ok":
        failures.append("admission_status_not_ok")
    if admission_packet.get("machine_error_code") != FULL_RUNTIME_DISPATCH_ADMISSION_OK:
        failures.append("admission_machine_error_not_ok")
    if admission_packet.get("effect") != EFFECT_READ:
        failures.append("admission_effect_not_read")
    failures.extend(_required_true_failures(admission_packet))
    failures.extend(_required_false_failures(admission_packet))
    if _safe_reasons(admission_packet.get("blocking_reasons")):
        failures.append("admission_blocking_reasons_not_empty")
    return sorted(set(failures))


def _unsafe_failures(
    admission_packet: Mapping[str, Any],
    *,
    proof_dir: str,
) -> list[str]:
    failures: list[str] = []
    for field in _REQUIRED_FALSE_FIELDS:
        if admission_packet.get(field) is True:
            failures.append(f"admission_{field}_unsafe")
    secret_values = _secret_values_for_proof_dir(proof_dir)
    violations = packets.inspect_command_packet_semantics(
        dict(admission_packet),
        secret_values=secret_values,
    )
    if violations:
        failures.append("admission_packet_semantic_violation")
    if packets.command_packet_has_secret_leak(
        admission_packet,
        secret_values=secret_values,
    ):
        failures.append("admission_packet_secret_material_present")
    return sorted(set(failures))


def _machine_error_code(
    *,
    input_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    admission_failures: Sequence[str],
) -> str:
    if unsafe_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_UNSAFE_SOURCE
    if input_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_INPUT_INVALID
    if admission_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_NOT_ADMITTED
    return FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_OK


def build_full_runtime_dispatch_admission_seal_packet(
    *,
    proof_dir: str,
    expected_freshness_anchor_digest: str | None,
    admission_packet: Mapping[str, Any] | None = None,
    input_failures: Sequence[str] | None = None,
    admission_failures: Sequence[str] | None = None,
    unsafe_failures: Sequence[str] | None = None,
) -> dict[str, Any]:
    admission = dict(admission_packet or {})
    input_failure_list = sorted(set(input_failures or []))
    admission_failure_list = sorted(set(admission_failures or []))
    unsafe_failure_list = sorted(set(unsafe_failures or []))
    machine_error_code = _machine_error_code(
        input_failures=input_failure_list,
        unsafe_failures=unsafe_failure_list,
        admission_failures=admission_failure_list,
    )
    ok = machine_error_code == FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_OK
    expected_digest = _hex_sha256(expected_freshness_anchor_digest)
    admission_packet_sha256 = (
        _canonical_packet_sha256(admission) if admission else ""
    )
    blocking_reasons = sorted(
        set(
            input_failure_list
            + unsafe_failure_list
            + admission_failure_list
            + _safe_reasons(admission.get("blocking_reasons"))
        )
    )
    extra = {
        "schema_version": 1,
        "packet_kind": FULL_RUNTIME_DISPATCH_ADMISSION_SEAL_PACKET_KIND,
        "proof_scope": "full_runtime_dispatch_admission_seal_read_only",
        "admission_packet_present": bool(admission),
        "admission_packet_kind": _safe_text(admission.get("packet_kind"), limit=96),
        "admission_packet_sha256": admission_packet_sha256,
        "admission_packet_raw_recorded": False,
        "expected_freshness_anchor_digest_present": bool(expected_digest),
        "expected_freshness_anchor_digest": expected_digest,
        "expected_freshness_anchor_digest_bound": bool(
            ok and admission.get("expected_freshness_anchor_digest_bound") is True
        ),
        "external_freshness_proven": bool(
            ok and admission.get("external_freshness_proven") is True
        ),
        "proof_admission_sealed": ok,
        "feature_runtime_proof_sealed": ok,
        "full_runtime_dispatch_runner_proven": bool(
            ok and admission.get("full_runtime_dispatch_runner_proven") is True
        ),
        "full_runtime_dispatch_proven": bool(
            ok and admission.get("full_runtime_dispatch_proven") is True
        ),
        "custom_codex_flow_proven": bool(
            ok and admission.get("custom_codex_flow_proven") is True
        ),
        "api_lane_called": bool(ok and admission.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and admission.get("dispatch_proven") is True),
        "codex_working_flow_delivery_proven": bool(
            ok and admission.get("codex_working_flow_delivery_proven") is True
        ),
        "custom_codex_ui_visibility_proven": bool(
            ok and admission.get("custom_codex_ui_visibility_proven") is True
        ),
        "handoff_payload_digest": (
            _hex_sha256(admission.get("handoff_payload_digest")) if ok else ""
        ),
        "seal_input_failures": input_failure_list,
        "seal_admission_failures": admission_failure_list,
        "seal_unsafe_failures": unsafe_failure_list,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "route_candidate_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "raw_freshness_anchor_recorded": False,
        "proof_dir_path_recorded": False,
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "changed_files": [],
        "blocking_reasons": [] if ok else blocking_reasons,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP sealed the full runtime dispatch admission proof."
            if ok
            else "WBP blocked full runtime dispatch admission seal."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_READ,
        secret_values=_secret_values_for_proof_dir(proof_dir),
        extra=extra,
    )


def run_full_runtime_dispatch_admission_seal_command(
    *,
    proof_dir: str,
    expected_freshness_anchor_digest: str | None,
) -> dict[str, Any]:
    input_failure_list = _input_failures(
        expected_freshness_anchor_digest=expected_freshness_anchor_digest,
    )
    if input_failure_list:
        return build_full_runtime_dispatch_admission_seal_packet(
            proof_dir=proof_dir,
            expected_freshness_anchor_digest=expected_freshness_anchor_digest,
            input_failures=input_failure_list,
        )

    admission_packet = run_full_runtime_dispatch_admission_command(
        proof_dir=proof_dir,
        expected_freshness_anchor_digest=expected_freshness_anchor_digest,
    )
    unsafe_failure_list = _unsafe_failures(admission_packet, proof_dir=proof_dir)
    admission_failure_list = _admission_failures(admission_packet)
    return build_full_runtime_dispatch_admission_seal_packet(
        proof_dir=proof_dir,
        expected_freshness_anchor_digest=expected_freshness_anchor_digest,
        admission_packet=admission_packet,
        admission_failures=admission_failure_list,
        unsafe_failures=unsafe_failure_list,
    )
