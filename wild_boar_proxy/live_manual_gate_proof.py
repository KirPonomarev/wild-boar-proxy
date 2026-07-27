# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE
from .core import packets
from .interactive_codex_working_flow_delivery import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
    INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
    WORKING_FLOW_PACKET_FILENAME,
    WORKING_FLOW_SEAL_FILENAME,
    WORKING_FLOW_SEAL_VERIFY_FILENAME,
)
from .proof_seal import (
    PROOF_SEAL_KIND,
    PROOF_SEAL_VERIFY_PACKET_KIND,
    read_json_mapping_file,
)
from .router_hook_entry import _safe_text
from .runtime import RuntimePaths, write_json_atomic


LIVE_MANUAL_GATE_PACKET_KIND = "wbp_live_manual_gate_proof"

LIVE_MANUAL_GATE_OK = "OK"
LIVE_MANUAL_GATE_WORKING_FLOW_INVALID = (
    "WBP_LIVE_MANUAL_GATE_WORKING_FLOW_INVALID"
)
LIVE_MANUAL_GATE_UNSAFE_PACKET = "WBP_LIVE_MANUAL_GATE_UNSAFE_PACKET"

LIVE_MANUAL_GATE_SURFACE = "wild-boar-proxy codex-runner live-manual-gate-proof"
FINAL_PACKET_FILENAME = "live-manual-gate-proof.packet.json"
UPSTREAM_WORKING_FLOW_PRODUCER_KIND = "wbp_interactive_codex_working_flow_delivery"


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None, source_file: Path) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    if source_file.parent.exists():
        return source_file.parent
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "codex-runner" / "live-manual-gate-proof" / stamp


def _sequence_empty(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and not value


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _working_flow_failures(
    packet: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("working_flow_file_read") is not True:
        failures.append("working_flow_file_not_read")
    if metadata.get("working_flow_file_valid_json") is not True:
        failures.append("working_flow_file_json_not_valid")
    if metadata.get("working_flow_file_mapping") is not True:
        failures.append("working_flow_file_not_mapping")
    if packet.get("packet_kind") != INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append("working_flow_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("working_flow_machine_error_not_ok")
    for field, reason in (
        ("interactive_custom_codex_flow_proven", "interactive_custom_codex_flow_not_proven"),
        ("hook_ledger_fresh", "hook_ledger_not_fresh"),
        ("user_prompt_submit_hook_ran", "user_prompt_submit_hook_not_run"),
        ("hook_prompt_digest_bound", "hook_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "hook_runtime_context_digest_not_bound"),
        ("runtime_context_bound", "runtime_context_not_bound"),
        ("alias_context_read", "alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "allowed_routes_not_enforced"),
        ("route_id_allowed", "route_id_not_allowed"),
        ("api_lane_called", "api_lane_not_called"),
        ("external_live_provider_response_proven", "external_live_provider_not_proven"),
        ("live_provider_response_proven", "live_provider_response_not_proven"),
        ("approved_handoff_proven", "approved_handoff_not_proven"),
        ("approved_delivery_surface_proven", "approved_delivery_surface_not_proven"),
        ("assistant_continuation_bound", "assistant_continuation_not_bound"),
        ("handoff_digest_bound", "handoff_digest_not_bound"),
        ("codex_exec_assistant_continuation_proven", "assistant_continuation_not_proven"),
        ("codex_exec_working_flow_delivery_proven", "codex_exec_working_flow_not_proven"),
        ("codex_working_flow_delivery_proven", "codex_working_flow_not_proven"),
        ("strict_sealed_evidence", "strict_sealed_evidence_not_present"),
        ("proof_seal_verified", "proof_seal_not_verified"),
        ("working_flow_seal_input_hashes_bound", "working_flow_seal_input_hashes_not_bound"),
    ):
        if packet.get(field) is not True:
            failures.append(reason)
    for field, reason in (
        ("fallback_used", "fallback_used"),
        ("local_imitation_used", "local_imitation_used"),
        ("native_codex_subagent_used_as_dip", "native_codex_subagent_used_as_dip"),
        ("codex_native_subagent_used_as_dip", "codex_native_subagent_used_as_dip"),
        ("custom_codex_ui_visibility_proven", "custom_ui_visibility_preclaimed"),
        ("delivery_counts_as_custom_codex_ui", "custom_ui_delivery_preclaimed"),
        ("native_free_chat_router_proven", "native_router_preclaimed"),
        ("product_ready", "product_ready_preclaimed"),
        ("raw_prompt_recorded", "raw_prompt_recorded"),
        ("prompt_text_recorded", "prompt_text_recorded"),
        ("natural_phrase_recorded", "natural_phrase_recorded"),
        ("raw_jsonl_recorded", "raw_jsonl_recorded"),
        ("tool_call_arguments_recorded", "tool_call_arguments_recorded"),
        ("raw_route_id_recorded", "raw_route_id_recorded"),
        ("selected_api_route_id_recorded", "selected_api_route_id_recorded"),
        ("raw_provider_response_recorded", "raw_provider_response_recorded"),
        ("provider_response_text_recorded", "provider_response_text_recorded"),
        ("provider_response_preview_recorded", "provider_response_preview_recorded"),
        ("raw_backend_details_exposed", "raw_backend_details_exposed"),
        ("secret_value_exposed", "secret_value_exposed"),
    ):
        if packet.get(field) is True:
            failures.append(reason)
    if not _sequence_empty(packet.get("blocking_reasons")):
        failures.append("working_flow_blocking_reasons_not_empty")
    if not _hex_sha256(metadata.get("working_flow_file_sha256")):
        failures.append("working_flow_file_sha256_missing")
    if not _hex_sha256(packet.get("delivery_source_digest")):
        failures.append("delivery_source_digest_missing")
    return sorted(set(failures))


def _sibling_artifact_failures(
    *,
    interactive_packet: Mapping[str, Any],
    sealed_working_flow_packet: Mapping[str, Any],
    sealed_working_flow_metadata: Mapping[str, Any],
    seal: Mapping[str, Any],
    seal_metadata: Mapping[str, Any],
    seal_verify_packet: Mapping[str, Any],
    seal_verify_metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if sealed_working_flow_metadata.get("sealed_working_flow_file_read") is not True:
        failures.append("sealed_working_flow_file_not_read")
    if (
        sealed_working_flow_metadata.get("sealed_working_flow_file_valid_json")
        is not True
    ):
        failures.append("sealed_working_flow_file_json_not_valid")
    if sealed_working_flow_metadata.get("sealed_working_flow_file_mapping") is not True:
        failures.append("sealed_working_flow_file_not_mapping")
    if sealed_working_flow_packet.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("sealed_working_flow_packet_kind_invalid")
    if sealed_working_flow_packet.get("status") != "ok":
        failures.append("sealed_working_flow_packet_not_ok")
    if sealed_working_flow_packet.get("machine_error_code") != "OK":
        failures.append("sealed_working_flow_machine_error_not_ok")

    sealed_working_flow_sha = _hex_sha256(
        sealed_working_flow_metadata.get("sealed_working_flow_file_sha256")
    )
    declared_working_flow_sha = _hex_sha256(
        interactive_packet.get("working_flow_proof_file_sha256")
    )
    if not sealed_working_flow_sha:
        failures.append("sealed_working_flow_file_sha256_missing")
    if not declared_working_flow_sha:
        failures.append("working_flow_proof_file_sha256_missing")
    if (
        sealed_working_flow_sha
        and declared_working_flow_sha
        and sealed_working_flow_sha != declared_working_flow_sha
    ):
        failures.append("working_flow_proof_file_sha256_mismatch")

    for field, reason in (
        ("codex_exec_jsonl_file_sha256", "codex_exec_jsonl_sha256_mismatch"),
        ("delivery_source_digest", "delivery_source_digest_mismatch"),
    ):
        declared = _hex_sha256(interactive_packet.get(field))
        sealed = _hex_sha256(sealed_working_flow_packet.get(field))
        if declared and sealed and declared != sealed:
            failures.append(reason)

    if seal_metadata.get("working_flow_seal_file_read") is not True:
        failures.append("working_flow_seal_file_not_read")
    if seal_metadata.get("working_flow_seal_file_valid_json") is not True:
        failures.append("working_flow_seal_file_json_not_valid")
    if seal_metadata.get("working_flow_seal_file_mapping") is not True:
        failures.append("working_flow_seal_file_not_mapping")
    if seal.get("seal_kind") != PROOF_SEAL_KIND:
        failures.append("working_flow_seal_kind_invalid")
    if seal.get("sealed_packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_seal_packet_kind_invalid")
    if (
        _safe_text(seal.get("producer_kind"), limit=120)
        != UPSTREAM_WORKING_FLOW_PRODUCER_KIND
    ):
        failures.append("working_flow_seal_producer_kind_invalid")
    if (
        sealed_working_flow_sha
        and _hex_sha256(seal.get("sealed_packet_sha256")) != sealed_working_flow_sha
    ):
        failures.append("working_flow_seal_packet_sha256_mismatch")
    if not _hex_sha256(seal.get("producer_command_digest")):
        failures.append("working_flow_seal_producer_command_digest_missing")
    if not _hex_sha256(seal.get("producer_inputs_digest")):
        failures.append("working_flow_seal_producer_inputs_digest_missing")

    if seal_verify_metadata.get("working_flow_seal_verify_file_read") is not True:
        failures.append("working_flow_seal_verify_file_not_read")
    if seal_verify_metadata.get("working_flow_seal_verify_file_valid_json") is not True:
        failures.append("working_flow_seal_verify_file_json_not_valid")
    if seal_verify_metadata.get("working_flow_seal_verify_file_mapping") is not True:
        failures.append("working_flow_seal_verify_file_not_mapping")
    if seal_verify_packet.get("packet_kind") != PROOF_SEAL_VERIFY_PACKET_KIND:
        failures.append("working_flow_seal_verify_packet_kind_invalid")
    if seal_verify_packet.get("status") != "ok":
        failures.append("working_flow_seal_verify_packet_not_ok")
    if seal_verify_packet.get("machine_error_code") != "OK":
        failures.append("working_flow_seal_verify_machine_error_not_ok")
    if seal_verify_packet.get("proof_seal_verified") is not True:
        failures.append("working_flow_seal_verify_not_verified")
    if seal_verify_packet.get("sealed_packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_seal_verify_packet_kind_mismatch")
    if (
        _safe_text(seal_verify_packet.get("producer_kind"), limit=120)
        != UPSTREAM_WORKING_FLOW_PRODUCER_KIND
    ):
        failures.append("working_flow_seal_verify_producer_kind_invalid")
    if (
        sealed_working_flow_sha
        and _hex_sha256(seal_verify_packet.get("sealed_packet_sha256"))
        != sealed_working_flow_sha
    ):
        failures.append("working_flow_seal_verify_packet_sha256_mismatch")
    if not _sequence_empty(seal_verify_packet.get("blocking_reasons")):
        failures.append("working_flow_seal_verify_blocking_reasons_not_empty")
    if not _sequence_empty(seal_verify_packet.get("proof_seal_failures")):
        failures.append("working_flow_seal_verify_failures_not_empty")
    if not _sequence_empty(seal_verify_packet.get("proof_seal_unsafe_failures")):
        failures.append("working_flow_seal_verify_unsafe_failures_not_empty")

    expected_input_digest = _hex_sha256(
        interactive_packet.get("working_flow_expected_seal_input_hashes_digest")
    )
    final_input_digest = _hex_sha256(
        interactive_packet.get("working_flow_seal_input_hashes_digest")
    )
    verify_input_digest = _hex_sha256(
        seal_verify_packet.get("seal_input_packet_hashes_digest")
    )
    if not expected_input_digest:
        failures.append("working_flow_expected_seal_input_hashes_digest_missing")
    if not final_input_digest:
        failures.append("working_flow_seal_input_hashes_digest_missing")
    if not verify_input_digest:
        failures.append("working_flow_seal_verify_input_hashes_digest_missing")
    if (
        expected_input_digest
        and final_input_digest
        and expected_input_digest != final_input_digest
    ):
        failures.append("working_flow_seal_input_hashes_digest_mismatch")
    if (
        expected_input_digest
        and verify_input_digest
        and expected_input_digest != verify_input_digest
    ):
        failures.append("working_flow_seal_verify_input_hashes_digest_mismatch")
    return sorted(set(failures))


def build_live_manual_gate_packet(
    *,
    working_flow_packet: Mapping[str, Any],
    file_metadata: Mapping[str, Any],
    sealed_working_flow_packet: Mapping[str, Any] | None = None,
    sealed_working_flow_metadata: Mapping[str, Any] | None = None,
    working_flow_seal_packet: Mapping[str, Any] | None = None,
    working_flow_seal_metadata: Mapping[str, Any] | None = None,
    working_flow_seal_verify_packet: Mapping[str, Any] | None = None,
    working_flow_seal_verify_metadata: Mapping[str, Any] | None = None,
    changed_files: Sequence[str],
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    working_flow = dict(working_flow_packet)
    metadata = {
        **dict(file_metadata),
        **dict(sealed_working_flow_metadata or {}),
        **dict(working_flow_seal_metadata or {}),
        **dict(working_flow_seal_verify_metadata or {}),
    }
    working_flow_failures = _working_flow_failures(working_flow, metadata)
    upstream_artifact_failures = _sibling_artifact_failures(
        interactive_packet=working_flow,
        sealed_working_flow_packet=dict(sealed_working_flow_packet or {}),
        sealed_working_flow_metadata=dict(sealed_working_flow_metadata or {}),
        seal=dict(working_flow_seal_packet or {}),
        seal_metadata=dict(working_flow_seal_metadata or {}),
        seal_verify_packet=dict(working_flow_seal_verify_packet or {}),
        seal_verify_metadata=dict(working_flow_seal_verify_metadata or {}),
    )
    unsafe = packets.command_packet_has_secret_leak(
        {
            "packet_kind": LIVE_MANUAL_GATE_PACKET_KIND,
            "working_flow_file_sha256": _hex_sha256(
                metadata.get("working_flow_file_sha256")
            ),
            "delivery_source_digest": _hex_sha256(
                working_flow.get("delivery_source_digest")
            ),
        },
        secret_values=list(secret_values or []),
    )
    blocking_reasons = list(working_flow_failures) + list(upstream_artifact_failures)
    if unsafe:
        blocking_reasons.append("live_manual_gate_packet_secret_leak")
    blocking_reasons = sorted(set(blocking_reasons))
    ok = bool(not blocking_reasons)
    machine_error_code = (
        LIVE_MANUAL_GATE_OK
        if ok
        else (
            LIVE_MANUAL_GATE_UNSAFE_PACKET
            if unsafe
            else LIVE_MANUAL_GATE_WORKING_FLOW_INVALID
        )
    )
    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": LIVE_MANUAL_GATE_PACKET_KIND,
        "runner_launch_surface": LIVE_MANUAL_GATE_SURFACE,
        "proof_scope": "live_manual_custom_codex_prompt_to_codex_working_flow",
        "live_manual_gate_proven": ok,
        "native_free_chat_router_live_manual_gate_proven": False,
        "trusted_user_prompt_submit_hook_ran": bool(
            ok
            and working_flow.get("interactive_custom_codex_flow_proven") is True
            and working_flow.get("user_prompt_submit_hook_ran") is True
        ),
        "real_custom_codex_prompt_submit_proven": bool(
            ok and working_flow.get("interactive_custom_codex_flow_proven") is True
        ),
        "real_custom_codex_prompt_submit_evidence_source": (
            "trusted_user_prompt_submit_ledger_and_interactive_working_flow"
            if ok
            else "not_proven"
        ),
        "working_flow_packet_kind": _safe_text(working_flow.get("packet_kind"), limit=96),
        "working_flow_status": _safe_text(working_flow.get("status"), limit=32),
        "working_flow_machine_error_code": _safe_text(
            working_flow.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_valid": not working_flow_failures,
        "working_flow_failures": working_flow_failures,
        "upstream_artifact_failures": upstream_artifact_failures,
        "working_flow_file_sha256_bound": bool(
            ok and _hex_sha256(metadata.get("working_flow_file_sha256"))
        ),
        "sealed_working_flow_file_sha256_bound": bool(
            ok
            and _hex_sha256(
                (sealed_working_flow_metadata or {}).get(
                    "sealed_working_flow_file_sha256"
                )
            )
            == _hex_sha256(working_flow.get("working_flow_proof_file_sha256"))
        ),
        "working_flow_seal_file_verified": bool(
            ok
            and (working_flow_seal_verify_packet or {}).get("proof_seal_verified")
            is True
        ),
        "interactive_custom_codex_flow_proven": bool(
            ok and working_flow.get("interactive_custom_codex_flow_proven") is True
        ),
        "hook_ledger_fresh": bool(ok and working_flow.get("hook_ledger_fresh") is True),
        "user_prompt_submit_hook_ran": bool(
            ok and working_flow.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": bool(
            ok and working_flow.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and working_flow.get("hook_runtime_context_digest_bound") is True
        ),
        "runtime_context_bound": bool(
            ok and working_flow.get("runtime_context_bound") is True
        ),
        "alias_context_read": bool(ok and working_flow.get("alias_context_read") is True),
        "allowed_api_route_ids_enforced": bool(
            ok and working_flow.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": bool(ok and working_flow.get("route_id_allowed") is True),
        "dispatch_proven": bool(
            ok and working_flow.get("codex_working_flow_delivery_proven") is True
        ),
        "api_lane_called": bool(ok and working_flow.get("api_lane_called") is True),
        "external_live_provider_response_proven": bool(
            ok and working_flow.get("external_live_provider_response_proven") is True
        ),
        "live_provider_response_proven": bool(
            ok and working_flow.get("live_provider_response_proven") is True
        ),
        "approved_handoff_proven": bool(
            ok and working_flow.get("approved_handoff_proven") is True
        ),
        "approved_delivery_surface_proven": bool(
            ok and working_flow.get("approved_delivery_surface_proven") is True
        ),
        "return_path_bound": bool(
            ok
            and working_flow.get("assistant_continuation_bound") is True
            and working_flow.get("handoff_digest_bound") is True
            and working_flow.get("codex_working_flow_delivery_proven") is True
        ),
        "assistant_continuation_bound": bool(
            ok and working_flow.get("assistant_continuation_bound") is True
        ),
        "handoff_digest_bound": bool(
            ok and working_flow.get("handoff_digest_bound") is True
        ),
        "codex_exec_assistant_continuation_proven": bool(
            ok
            and working_flow.get("codex_exec_assistant_continuation_proven") is True
        ),
        "codex_exec_working_flow_delivery_proven": bool(
            ok and working_flow.get("codex_exec_working_flow_delivery_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and working_flow.get("codex_working_flow_delivery_proven") is True
        ),
        "strict_sealed_evidence": bool(
            ok and working_flow.get("strict_sealed_evidence") is True
        ),
        "proof_seal_verified": bool(ok and working_flow.get("proof_seal_verified") is True),
        "working_flow_seal_input_hashes_bound": bool(
            ok and working_flow.get("working_flow_seal_input_hashes_bound") is True
        ),
        "source_file_unforgeable": False,
        "cryptographic_authenticity_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_native_free_chat_router_product_ready": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
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
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "proof_dir_path_recorded": False,
        "working_flow_file_path_recorded": False,
        "final_packet_file_path_recorded": False,
        "state_written": False,
        "evidence_written": True,
        "file_mutation_attempted": True,
        "declared_write_surfaces": ["proof_dir", "proof_packets"],
        "blocking_reasons": blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved the live manual Custom Codex gate without product readiness."
            if ok
            else "WBP blocked the live manual Custom Codex gate before product readiness."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=sorted(set(changed_files)),
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_live_manual_gate_proof_command(
    *,
    paths: RuntimePaths,
    interactive_working_flow_delivery_file: str,
    proof_dir: str | None = None,
) -> dict[str, Any]:
    source_file = Path(interactive_working_flow_delivery_file).expanduser()
    proof_root = _proof_root(paths, proof_dir, source_file)
    proof_root.mkdir(parents=True, exist_ok=True)
    working_flow_packet, metadata = read_json_mapping_file(
        source_file,
        prefix="working_flow",
    )
    artifact_root = source_file.parent
    sealed_working_flow_packet, sealed_working_flow_metadata = read_json_mapping_file(
        artifact_root / WORKING_FLOW_PACKET_FILENAME,
        prefix="sealed_working_flow",
    )
    working_flow_seal_packet, working_flow_seal_metadata = read_json_mapping_file(
        artifact_root / WORKING_FLOW_SEAL_FILENAME,
        prefix="working_flow_seal",
    )
    (
        working_flow_seal_verify_packet,
        working_flow_seal_verify_metadata,
    ) = read_json_mapping_file(
        artifact_root / WORKING_FLOW_SEAL_VERIFY_FILENAME,
        prefix="working_flow_seal_verify",
    )
    final_path = proof_root / FINAL_PACKET_FILENAME
    packet = build_live_manual_gate_packet(
        working_flow_packet=working_flow_packet,
        file_metadata=metadata,
        sealed_working_flow_packet=sealed_working_flow_packet,
        sealed_working_flow_metadata=sealed_working_flow_metadata,
        working_flow_seal_packet=working_flow_seal_packet,
        working_flow_seal_metadata=working_flow_seal_metadata,
        working_flow_seal_verify_packet=working_flow_seal_verify_packet,
        working_flow_seal_verify_metadata=working_flow_seal_verify_metadata,
        changed_files=[str(final_path)],
    )
    write_json_atomic(final_path, packet)
    return packet
