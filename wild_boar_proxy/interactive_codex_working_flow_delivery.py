# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import hashlib
import json
from typing import Any

from .codex_working_flow_delivery_proof import (
    CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
    run_codex_working_flow_delivery_proof_command,
)
from .command_effects import EFFECT_MUTATE
from .core import packets
from .interactive_custom_codex_proof import INTERACTIVE_COLLECT_PACKET_KIND
from .proof_seal import (
    read_json_mapping_file,
    run_proof_seal_create_command,
    sha256_file,
    verify_proof_seal,
)
from .real_custom_codex_hook_proof import REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
from .router_hook_entry import _safe_text
from .runtime import write_json_atomic


INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND = (
    "wbp_interactive_codex_working_flow_delivery_proof"
)

INTERACTIVE_WORKING_FLOW_OK = "OK"
INTERACTIVE_WORKING_FLOW_INTERACTIVE_PROOF_INVALID = (
    "WBP_INTERACTIVE_WORKING_FLOW_INTERACTIVE_PROOF_INVALID"
)
INTERACTIVE_WORKING_FLOW_SOURCE_PROOF_INVALID = (
    "WBP_INTERACTIVE_WORKING_FLOW_SOURCE_PROOF_INVALID"
)
INTERACTIVE_WORKING_FLOW_DELIVERY_NOT_PROVEN = (
    "WBP_INTERACTIVE_WORKING_FLOW_DELIVERY_NOT_PROVEN"
)
INTERACTIVE_WORKING_FLOW_SEAL_FAILED = "WBP_INTERACTIVE_WORKING_FLOW_SEAL_FAILED"
INTERACTIVE_WORKING_FLOW_UNSAFE_PACKET = "WBP_INTERACTIVE_WORKING_FLOW_UNSAFE_PACKET"

DELIVERY_SOURCE_CODEX_EXEC_JSONL = "codex_exec_jsonl"
APPROVED_DELIVERY_SOURCE_KINDS = frozenset({DELIVERY_SOURCE_CODEX_EXEC_JSONL})
CLAIM_CEILING_CODEX_EXEC_WORKING_FLOW = (
    "codex_exec_working_flow_delivery_only_no_custom_ui_no_native_router_no_product"
)

WORKING_FLOW_PACKET_FILENAME = "working-flow-delivery-proof.packet.json"
WORKING_FLOW_SEAL_FILENAME = "working-flow-delivery-proof.seal.json"
WORKING_FLOW_SEAL_VERIFY_FILENAME = "working-flow-delivery-proof.seal-verify.packet.json"
FINAL_PACKET_FILENAME = "interactive-working-flow-delivery-proof.packet.json"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _canonical_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256_text(encoded)


def _input_hashes_digest(input_hashes: Mapping[str, str]) -> str:
    return _canonical_digest(dict(input_hashes))


def _proof_root(raw_proof_dir: str | None, interactive_path: Path) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    return interactive_path.parent


def _write_packet(path: Path, packet: Mapping[str, Any]) -> str:
    write_json_atomic(path, dict(packet))
    return str(path)


def _read_packet(path: Path, *, prefix: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return read_json_mapping_file(path, prefix=prefix)


def _is_false(packet: Mapping[str, Any], key: str) -> bool:
    return packet.get(key) is False


def _sequence_empty(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and not value


def _expected_seal_input_hashes(
    *,
    interactive_packet: Mapping[str, Any],
    source_packet: Mapping[str, Any],
    interactive_metadata: Mapping[str, Any],
    source_metadata: Mapping[str, Any],
) -> dict[str, str]:
    return {
        _safe_text(interactive_packet.get("packet_kind"), limit=120): _hex_sha256(
            interactive_metadata.get("interactive_proof_file_sha256")
        ),
        _safe_text(source_packet.get("packet_kind"), limit=120): _hex_sha256(
            source_metadata.get("source_proof_file_sha256")
        ),
    }


def _unsafe_true_failures(packet: Mapping[str, Any], *, prefix: str) -> list[str]:
    checks = {
        "raw_prompt_recorded": "raw_prompt_recorded",
        "prompt_text_recorded": "prompt_text_recorded",
        "natural_phrase_recorded": "natural_phrase_recorded",
        "raw_jsonl_recorded": "raw_jsonl_recorded",
        "tool_call_arguments_recorded": "tool_call_arguments_recorded",
        "route_candidate_recorded": "route_candidate_recorded",
        "raw_route_id_recorded": "raw_route_id_recorded",
        "selected_api_route_id_recorded": "selected_api_route_id_recorded",
        "raw_provider_response_recorded": "raw_provider_response_recorded",
        "provider_response_text_recorded": "provider_response_text_recorded",
        "provider_response_preview_recorded": "provider_response_preview_recorded",
        "raw_backend_details_exposed": "raw_backend_details_exposed",
        "secret_value_exposed": "secret_value_exposed",
        "fallback_used": "fallback_used",
        "local_imitation_used": "local_imitation_used",
        "native_codex_subagent_used_as_dip": "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip": "codex_native_subagent_used_as_dip",
        "custom_codex_ui_visibility_proven": "custom_ui_must_not_be_claimed",
        "delivery_counts_as_custom_codex_ui": "custom_ui_delivery_must_not_be_claimed",
        "native_free_chat_router_proven": "native_router_must_not_be_claimed",
        "product_ready": "product_ready_must_not_be_claimed",
        "state_written": "state_write_not_allowed",
        "evidence_written": "evidence_write_not_allowed",
        "file_mutation_attempted": "file_mutation_not_allowed",
    }
    return sorted(
        {
            f"{prefix}_{reason}"
            for field, reason in checks.items()
            if packet.get(field) is True
        }
    )


def _interactive_failures(
    interactive_packet: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("interactive_proof_file_read") is not True:
        failures.append("interactive_proof_file_not_read")
    if metadata.get("interactive_proof_file_valid_json") is not True:
        failures.append("interactive_proof_file_json_not_valid")
    if metadata.get("interactive_proof_file_mapping") is not True:
        failures.append("interactive_proof_file_not_mapping")
    if interactive_packet.get("packet_kind") != INTERACTIVE_COLLECT_PACKET_KIND:
        failures.append("interactive_proof_packet_kind_invalid")
    if interactive_packet.get("status") != "ok":
        failures.append("interactive_proof_packet_not_ok")
    if interactive_packet.get("machine_error_code") != "OK":
        failures.append("interactive_proof_machine_error_not_ok")
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
        ("approved_handoff_proven", "approved_handoff_not_proven"),
        ("strict_sealed_evidence", "strict_sealed_evidence_not_present"),
        ("proof_seal_verified", "source_proof_seal_not_verified"),
    ):
        if interactive_packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(interactive_packet.get("source_proof_sha256")):
        failures.append("source_proof_sha256_missing")
    if not _hex_sha256(interactive_packet.get("live_provider_packet_sha256")):
        failures.append("live_provider_packet_sha256_missing")
    if interactive_packet.get("codex_working_flow_delivery_proven") is not False:
        failures.append("interactive_proof_must_not_preclaim_working_flow_delivery")
    if interactive_packet.get("does_not_prove_codex_working_flow_delivery") is not True:
        failures.append("interactive_proof_missing_working_flow_boundary")
    for field, reason in (
        ("custom_codex_ui_visibility_proven", "custom_ui_must_not_be_preclaimed"),
        ("native_free_chat_router_proven", "native_router_must_not_be_preclaimed"),
        ("product_ready", "product_ready_must_not_be_preclaimed"),
    ):
        if interactive_packet.get(field) is not False:
            failures.append(reason)
    if not _sequence_empty(interactive_packet.get("blocking_reasons")):
        failures.append("interactive_blocking_reasons_not_empty")
    failures.extend(_unsafe_true_failures(interactive_packet, prefix="interactive"))
    return sorted(set(failures))


def _source_failures(
    source_packet: Mapping[str, Any],
    source_metadata: Mapping[str, Any],
    interactive_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if source_metadata.get("source_proof_file_read") is not True:
        failures.append("source_proof_file_not_read")
    if source_metadata.get("source_proof_file_valid_json") is not True:
        failures.append("source_proof_file_json_not_valid")
    if source_metadata.get("source_proof_file_mapping") is not True:
        failures.append("source_proof_file_not_mapping")
    if source_packet.get("packet_kind") != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND:
        failures.append("source_proof_packet_kind_invalid")
    if source_packet.get("status") != "ok":
        failures.append("source_proof_packet_not_ok")
    if source_packet.get("machine_error_code") != "OK":
        failures.append("source_proof_machine_error_not_ok")
    expected_hash = _hex_sha256(interactive_packet.get("source_proof_sha256"))
    observed_hash = _hex_sha256(source_metadata.get("source_proof_file_sha256"))
    if not expected_hash or not observed_hash or observed_hash != expected_hash:
        failures.append("source_proof_sha256_not_bound_to_interactive_proof")
    if (
        _safe_text(interactive_packet.get("source_proof_packet_kind"), limit=80)
        != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
    ):
        failures.append("interactive_source_proof_kind_not_bound")
    if (
        _safe_text(interactive_packet.get("source_proof_machine_error_code"), limit=96)
        != "OK"
    ):
        failures.append("interactive_source_proof_machine_error_not_ok")
    for field, reason in (
        ("user_prompt_submit_hook_ran", "source_user_prompt_submit_hook_not_run"),
        ("hook_prompt_digest_bound", "source_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "source_runtime_context_not_bound"),
        ("alias_context_read", "source_alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "source_allowed_routes_not_enforced"),
        ("route_id_allowed", "source_route_id_not_allowed"),
        ("api_lane_called", "source_api_lane_not_called"),
        ("dispatch_proven", "source_dispatch_not_proven"),
        ("external_live_provider_response_proven", "source_external_live_provider_not_proven"),
        ("approved_handoff_ready", "source_approved_handoff_not_ready"),
        ("handoff_delivered", "source_handoff_not_delivered"),
        ("delivery_observed", "source_delivery_not_observed"),
    ):
        if source_packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(source_packet.get("handoff_payload_digest")):
        failures.append("source_handoff_payload_digest_missing")
    if not _hex_sha256(source_packet.get("live_provider_response_digest")):
        failures.append("source_live_provider_response_digest_missing")
    failures.extend(_unsafe_true_failures(source_packet, prefix="source"))
    return sorted(set(failures))


def _working_flow_failures(
    working_flow_packet: Mapping[str, Any],
    working_flow_metadata: Mapping[str, Any],
    source_packet: Mapping[str, Any],
    *,
    delivery_source_kind: str,
) -> list[str]:
    failures: list[str] = []
    if delivery_source_kind not in APPROVED_DELIVERY_SOURCE_KINDS:
        failures.append("delivery_source_kind_not_approved")
    if working_flow_metadata.get("working_flow_proof_file_read") is not True:
        failures.append("working_flow_proof_file_not_read")
    if working_flow_metadata.get("working_flow_proof_file_valid_json") is not True:
        failures.append("working_flow_proof_file_json_not_valid")
    if working_flow_metadata.get("working_flow_proof_file_mapping") is not True:
        failures.append("working_flow_proof_file_not_mapping")
    if working_flow_packet.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append("working_flow_proof_packet_kind_invalid")
    if working_flow_packet.get("status") != "ok":
        failures.append("working_flow_proof_packet_not_ok")
    if working_flow_packet.get("machine_error_code") != "OK":
        failures.append("working_flow_proof_machine_error_not_ok")
    for field, reason in (
        ("integrated_live_provider_proof_valid", "working_flow_source_not_valid"),
        ("user_prompt_submit_hook_ran", "working_flow_hook_not_run"),
        ("hook_prompt_digest_bound", "working_flow_prompt_digest_not_bound"),
        ("hook_runtime_context_digest_bound", "working_flow_runtime_context_not_bound"),
        ("alias_context_read", "working_flow_alias_context_not_read"),
        ("allowed_api_route_ids_enforced", "working_flow_allowed_routes_not_enforced"),
        ("route_id_allowed", "working_flow_route_not_allowed"),
        ("api_lane_called", "working_flow_api_lane_not_called"),
        ("dispatch_proven", "working_flow_dispatch_not_proven"),
        ("live_provider_response_proven", "working_flow_live_provider_not_proven"),
        ("external_live_provider_response_proven", "working_flow_external_live_provider_not_proven"),
        ("approved_handoff_ready", "working_flow_approved_handoff_not_ready"),
        ("handoff_delivered", "working_flow_handoff_not_delivered"),
        ("delivery_observed", "working_flow_delivery_not_observed"),
        ("approved_delivery_surface_proven", "working_flow_delivery_surface_not_proven"),
        ("codex_exec_assistant_continuation_proven", "assistant_continuation_not_proven"),
        ("codex_working_flow_delivery_proven", "codex_working_flow_delivery_not_proven"),
    ):
        if working_flow_packet.get(field) is not True:
            failures.append(reason)
    if not _hex_sha256(working_flow_packet.get("codex_exec_transcript_sha256")):
        failures.append("codex_exec_transcript_digest_missing")
    if not _hex_sha256(working_flow_packet.get("handoff_payload_digest")):
        failures.append("working_flow_handoff_payload_digest_missing")
    if (
        _hex_sha256(working_flow_packet.get("source_handoff_payload_digest"))
        != _hex_sha256(source_packet.get("handoff_payload_digest"))
    ):
        failures.append("source_handoff_digest_not_bound_to_working_flow")
    for field, reason in (
        ("custom_codex_ui_visibility_proven", "custom_ui_must_not_be_preclaimed"),
        ("delivery_counts_as_custom_codex_ui", "custom_ui_delivery_must_not_be_preclaimed"),
        ("native_free_chat_router_proven", "native_router_must_not_be_preclaimed"),
        ("product_ready", "product_ready_must_not_be_preclaimed"),
    ):
        if working_flow_packet.get(field) is not False:
            failures.append(reason)
    if not _sequence_empty(working_flow_packet.get("blocking_reasons")):
        failures.append("working_flow_blocking_reasons_not_empty")
    failures.extend(_unsafe_true_failures(working_flow_packet, prefix="working_flow"))
    return sorted(set(failures))


def _seal_failures(
    seal_create_packet: Mapping[str, Any],
    seal_verify_packet: Mapping[str, Any],
    *,
    expected_input_hashes_digest: str,
) -> list[str]:
    failures: list[str] = []
    if seal_create_packet.get("status") != "ok":
        failures.append("working_flow_seal_create_not_ok")
    if seal_verify_packet.get("status") != "ok":
        failures.append("working_flow_seal_verify_not_ok")
    if seal_verify_packet.get("proof_seal_verified") is not True:
        failures.append("working_flow_seal_not_verified")
    if (
        _hex_sha256(seal_verify_packet.get("seal_input_packet_hashes_digest"))
        != _hex_sha256(expected_input_hashes_digest)
    ):
        failures.append("working_flow_seal_input_hashes_not_bound")
    return failures


def _machine_error_code(
    *,
    interactive_failures: Sequence[str],
    source_failures: Sequence[str],
    working_flow_failures: Sequence[str],
    seal_failures: Sequence[str],
    unsafe: bool,
) -> str:
    if (
        not interactive_failures
        and not source_failures
        and not working_flow_failures
        and not seal_failures
        and not unsafe
    ):
        return INTERACTIVE_WORKING_FLOW_OK
    if unsafe:
        return INTERACTIVE_WORKING_FLOW_UNSAFE_PACKET
    if interactive_failures:
        return INTERACTIVE_WORKING_FLOW_INTERACTIVE_PROOF_INVALID
    if source_failures:
        return INTERACTIVE_WORKING_FLOW_SOURCE_PROOF_INVALID
    if working_flow_failures:
        return INTERACTIVE_WORKING_FLOW_DELIVERY_NOT_PROVEN
    if seal_failures:
        return INTERACTIVE_WORKING_FLOW_SEAL_FAILED
    return INTERACTIVE_WORKING_FLOW_DELIVERY_NOT_PROVEN


def build_interactive_codex_working_flow_delivery_packet(
    *,
    interactive_packet: Mapping[str, Any],
    source_packet: Mapping[str, Any],
    working_flow_packet: Mapping[str, Any],
    seal_create_packet: Mapping[str, Any],
    seal_verify_packet: Mapping[str, Any],
    delivery_source_kind: str,
    file_metadata: Mapping[str, Any],
    changed_files: Sequence[str],
    expected_seal_input_hashes_digest: str = "",
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    metadata = dict(file_metadata)
    source_kind = _safe_text(delivery_source_kind, limit=80)
    interactive_blockers = _interactive_failures(interactive_packet, metadata)
    source_blockers = _source_failures(source_packet, metadata, interactive_packet)
    working_flow_blockers = _working_flow_failures(
        working_flow_packet,
        metadata,
        source_packet,
        delivery_source_kind=source_kind,
    )
    seal_blockers = _seal_failures(
        seal_create_packet,
        seal_verify_packet,
        expected_input_hashes_digest=expected_seal_input_hashes_digest,
    )

    delivery_source_digest = _hex_sha256(
        working_flow_packet.get("codex_exec_transcript_sha256")
    )
    handoff_digest_bound = bool(
        _hex_sha256(working_flow_packet.get("source_handoff_payload_digest"))
        and _hex_sha256(working_flow_packet.get("source_handoff_payload_digest"))
        == _hex_sha256(source_packet.get("handoff_payload_digest"))
    )
    assistant_continuation_bound = bool(
        working_flow_packet.get("codex_exec_assistant_continuation_proven") is True
        and (
            working_flow_packet.get("assistant_response_bound_to_handoff_digest") is True
            or working_flow_packet.get(
                "command_assistant_response_bound_to_live_provider_digest"
            )
            is True
        )
    )
    codex_exec_working_flow_delivery_proven = bool(
        source_kind == DELIVERY_SOURCE_CODEX_EXEC_JSONL
        and working_flow_packet.get("codex_working_flow_delivery_proven") is True
        and delivery_source_digest
        and assistant_continuation_bound
        and handoff_digest_bound
    )
    local_subagent_used_as_dip = bool(
        working_flow_packet.get("local_imitation_used") is True
        or working_flow_packet.get("native_codex_subagent_used_as_dip") is True
        or working_flow_packet.get("codex_native_subagent_used_as_dip") is True
    )

    blocking_reasons = sorted(
        set(interactive_blockers + source_blockers + working_flow_blockers + seal_blockers)
    )
    unsafe = packets.command_packet_has_secret_leak(
        {
            "packet_kind": INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
            "delivery_source_digest": delivery_source_digest,
            "interactive_proof_sha256": _hex_sha256(
                metadata.get("interactive_proof_file_sha256")
            ),
            "source_proof_sha256": _hex_sha256(metadata.get("source_proof_file_sha256")),
            "working_flow_proof_sha256": _hex_sha256(
                metadata.get("working_flow_proof_file_sha256")
            ),
        },
        secret_values=list(secret_values or []),
    )
    if unsafe:
        blocking_reasons.append("interactive_working_flow_packet_secret_leak")
    blocking_reasons = sorted(set(blocking_reasons))
    ok = bool(
        not blocking_reasons
        and codex_exec_working_flow_delivery_proven
        and seal_verify_packet.get("proof_seal_verified") is True
    )
    machine_error_code = _machine_error_code(
        interactive_failures=interactive_blockers,
        source_failures=source_blockers,
        working_flow_failures=working_flow_blockers,
        seal_failures=seal_blockers,
        unsafe=unsafe,
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": INTERACTIVE_CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        "delivery_source_kind": source_kind,
        "delivery_source_kind_allowed": source_kind in APPROVED_DELIVERY_SOURCE_KINDS,
        "delivery_source_file_backed": True,
        "delivery_source_digest": delivery_source_digest,
        "source_kind_claim_ceiling": CLAIM_CEILING_CODEX_EXEC_WORKING_FLOW,
        "interactive_proof_kind": _safe_text(interactive_packet.get("packet_kind"), limit=80),
        "interactive_proof_status": _safe_text(interactive_packet.get("status"), limit=32),
        "interactive_proof_machine_error_code": _safe_text(
            interactive_packet.get("machine_error_code"),
            limit=96,
        ),
        "interactive_proof_valid": not interactive_blockers,
        "interactive_proof_failures": interactive_blockers,
        "interactive_custom_codex_flow_proven": (
            interactive_packet.get("interactive_custom_codex_flow_proven") is True
        ),
        "hook_ledger_fresh": interactive_packet.get("hook_ledger_fresh") is True,
        "hook_ledger_sha256_bound": bool(
            _hex_sha256(interactive_packet.get("source_proof_sha256"))
            and _hex_sha256(metadata.get("source_proof_file_sha256"))
            == _hex_sha256(interactive_packet.get("source_proof_sha256"))
        ),
        "source_proof_kind": _safe_text(source_packet.get("packet_kind"), limit=80),
        "source_proof_status": _safe_text(source_packet.get("status"), limit=32),
        "source_proof_machine_error_code": _safe_text(
            source_packet.get("machine_error_code"),
            limit=96,
        ),
        "source_proof_valid": not source_blockers,
        "source_proof_failures": source_blockers,
        "source_proof_sha256_bound_to_interactive_proof": bool(
            _hex_sha256(interactive_packet.get("source_proof_sha256"))
            and _hex_sha256(metadata.get("source_proof_file_sha256"))
            == _hex_sha256(interactive_packet.get("source_proof_sha256"))
        ),
        "working_flow_proof_kind": _safe_text(
            working_flow_packet.get("packet_kind"),
            limit=80,
        ),
        "working_flow_proof_status": _safe_text(
            working_flow_packet.get("status"),
            limit=32,
        ),
        "working_flow_proof_machine_error_code": _safe_text(
            working_flow_packet.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_proof_valid": not working_flow_blockers,
        "working_flow_proof_failures": working_flow_blockers,
        "custom_codex_flow_proven": False,
        "command_origin_proven": False,
        "custom_codex_origin_proven": False,
        "native_custom_codex_flow_proven": False,
        "native_router_hook_observed": False,
        "user_prompt_submit_hook_ran": (
            interactive_packet.get("user_prompt_submit_hook_ran") is True
            and working_flow_packet.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": (
            interactive_packet.get("hook_prompt_digest_bound") is True
            and working_flow_packet.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": (
            interactive_packet.get("hook_runtime_context_digest_bound") is True
            and working_flow_packet.get("hook_runtime_context_digest_bound") is True
        ),
        "runtime_context_bound": (
            interactive_packet.get("runtime_context_bound") is True
            and working_flow_packet.get("hook_runtime_context_digest_bound") is True
        ),
        "alias_context_read": (
            interactive_packet.get("alias_context_read") is True
            and working_flow_packet.get("alias_context_read") is True
        ),
        "allowed_api_route_ids_enforced": (
            interactive_packet.get("allowed_api_route_ids_enforced") is True
            and working_flow_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "route_id_allowed": (
            interactive_packet.get("route_id_allowed") is True
            and working_flow_packet.get("route_id_allowed") is True
        ),
        "api_lane_called": (
            interactive_packet.get("api_lane_called") is True
            and working_flow_packet.get("api_lane_called") is True
        ),
        "external_live_provider_response_proven": (
            interactive_packet.get("external_live_provider_response_proven") is True
            and working_flow_packet.get("external_live_provider_response_proven") is True
        ),
        "live_provider_response_proven": (
            interactive_packet.get("live_provider_response_proven") is True
            and working_flow_packet.get("live_provider_response_proven") is True
        ),
        "approved_handoff_proven": (
            interactive_packet.get("approved_handoff_proven") is True
            and working_flow_packet.get("approved_handoff_ready") is True
            and working_flow_packet.get("handoff_delivered") is True
        ),
        "approved_delivery_surface_proven": (
            working_flow_packet.get("approved_delivery_surface_proven") is True
        ),
        "handoff_digest_bound": handoff_digest_bound,
        "assistant_continuation_bound": assistant_continuation_bound,
        "assistant_response_bound_to_handoff_digest": (
            working_flow_packet.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "command_assistant_response_bound_to_live_provider_digest": (
            working_flow_packet.get(
                "command_assistant_response_bound_to_live_provider_digest"
            )
            is True
        ),
        "codex_exec_assistant_continuation_proven": (
            working_flow_packet.get("codex_exec_assistant_continuation_proven") is True
        ),
        "codex_exec_working_flow_delivery_proven": (
            codex_exec_working_flow_delivery_proven
        ),
        "codex_working_flow_delivery_proven": ok,
        "delivery_counts_as_custom_codex_ui": False,
        "custom_codex_ui_visibility_proven": False,
        "native_free_chat_router_proven": False,
        "native_codex_subagent_used_as_dip": local_subagent_used_as_dip,
        "codex_native_subagent_used_as_dip": local_subagent_used_as_dip,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": local_subagent_used_as_dip,
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
        "no_secret_exposed": True,
        "state_written": False,
        "evidence_written": False,
        "file_mutation_attempted": False,
        "proof_dir_written": True,
        "strict_sealed_evidence": seal_verify_packet.get("proof_seal_verified") is True,
        "proof_seal_verified": seal_verify_packet.get("proof_seal_verified") is True,
        "working_flow_seal_create_machine_error_code": _safe_text(
            seal_create_packet.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_seal_machine_error_code": _safe_text(
            seal_verify_packet.get("machine_error_code"),
            limit=96,
        ),
        "working_flow_seal_input_hashes_bound": bool(
            seal_verify_packet.get("proof_seal_verified") is True
            and _hex_sha256(seal_verify_packet.get("seal_input_packet_hashes_digest"))
            == _hex_sha256(expected_seal_input_hashes_digest)
        ),
        "working_flow_seal_input_hashes_digest": _hex_sha256(
            seal_verify_packet.get("seal_input_packet_hashes_digest")
        ),
        "working_flow_expected_seal_input_hashes_digest": _hex_sha256(
            expected_seal_input_hashes_digest
        ),
        "working_flow_seal_failures": seal_blockers,
        "declared_write_surfaces": ["proof_dir", "proof_packets", "proof_seals"],
        "blocking_reasons": blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved interactive Custom Codex output reached a digest-bound Codex working flow."
            if ok
            else "WBP blocked interactive Codex working-flow delivery before proof."
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


def run_interactive_codex_working_flow_delivery_command(
    *,
    interactive_proof_file: str,
    integrated_live_provider_proof_file: str,
    codex_exec_jsonl_file: str,
    proof_dir: str | None = None,
    delivery_source_kind: str = DELIVERY_SOURCE_CODEX_EXEC_JSONL,
) -> dict[str, Any]:
    interactive_path = Path(interactive_proof_file).expanduser()
    source_path = Path(integrated_live_provider_proof_file).expanduser()
    jsonl_path = Path(codex_exec_jsonl_file).expanduser()
    proof_root = _proof_root(proof_dir, interactive_path)
    proof_root.mkdir(parents=True, exist_ok=True)

    interactive_packet, interactive_metadata = _read_packet(
        interactive_path,
        prefix="interactive_proof",
    )
    source_packet, source_metadata = _read_packet(source_path, prefix="source_proof")
    working_flow_packet = run_codex_working_flow_delivery_proof_command(
        integrated_live_provider_proof_file=str(source_path),
        codex_exec_jsonl_file=str(jsonl_path),
    )
    working_flow_path = proof_root / WORKING_FLOW_PACKET_FILENAME
    changed_files = [_write_packet(working_flow_path, working_flow_packet)]
    working_flow_packet, working_flow_metadata = _read_packet(
        working_flow_path,
        prefix="working_flow_proof",
    )
    expected_input_hashes = _expected_seal_input_hashes(
        interactive_packet=interactive_packet,
        source_packet=source_packet,
        interactive_metadata=interactive_metadata,
        source_metadata=source_metadata,
    )
    expected_input_hashes_digest = _input_hashes_digest(expected_input_hashes)

    producer_command_digest = _sha256_text(
        "codex-runner:interactive-working-flow-delivery:v1"
    )
    working_flow_seal_path = proof_root / WORKING_FLOW_SEAL_FILENAME
    seal_create_packet = run_proof_seal_create_command(
        packet_file=str(working_flow_path),
        seal_file=str(working_flow_seal_path),
        producer_kind="wbp_interactive_codex_working_flow_delivery",
        producer_command_digest=producer_command_digest,
        input_packet_files=[str(interactive_path), str(source_path)],
    )
    changed_files.extend(str(path) for path in seal_create_packet.get("changed_files", []))
    seal_verify_packet, _seal = verify_proof_seal(
        packet_file=str(working_flow_path),
        seal_file=str(working_flow_seal_path),
        expected_packet_kind=CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND,
        expected_input_packet_hashes=expected_input_hashes,
    )
    seal_verify_path = proof_root / WORKING_FLOW_SEAL_VERIFY_FILENAME
    changed_files.append(_write_packet(seal_verify_path, seal_verify_packet))

    file_metadata = {
        **interactive_metadata,
        **source_metadata,
        **working_flow_metadata,
        "codex_exec_jsonl_file_required": True,
        "codex_exec_jsonl_file_present": jsonl_path.exists(),
        "codex_exec_jsonl_file_sha256": sha256_file(jsonl_path),
        "codex_exec_jsonl_file_path_recorded": False,
    }
    packet = build_interactive_codex_working_flow_delivery_packet(
        interactive_packet=interactive_packet,
        source_packet=source_packet,
        working_flow_packet=working_flow_packet,
        seal_create_packet=seal_create_packet,
        seal_verify_packet=seal_verify_packet,
        delivery_source_kind=delivery_source_kind,
        file_metadata=file_metadata,
        changed_files=changed_files + [str(proof_root / FINAL_PACKET_FILENAME)],
        expected_seal_input_hashes_digest=expected_input_hashes_digest,
    )
    final_path = proof_root / FINAL_PACKET_FILENAME
    write_json_atomic(final_path, packet)
    return packet
