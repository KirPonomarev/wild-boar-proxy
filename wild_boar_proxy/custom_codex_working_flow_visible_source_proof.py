# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .codex_working_flow_delivery_proof import CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND
from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_admission import CUSTOM_CODEX_ADMISSION_PACKET_KIND
from .custom_codex_operator_proof import (
    REPEATABLE_OPERATOR_PACKET_KIND,
    RUN_COUNT,
    _runtime_secret_values,
    run_repeatable_operator_proof_command,
)
from .proof_seal import sha256_file
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths, write_json_atomic


WORKING_FLOW_VISIBLE_SOURCE_PACKET_KIND = (
    "wbp_custom_codex_working_flow_visible_source_proof"
)

VISIBLE_SOURCE_PROOF_OK = "OK"
VISIBLE_SOURCE_PROOF_OPERATOR_INVALID = "WBP_VISIBLE_SOURCE_PROOF_OPERATOR_INVALID"
VISIBLE_SOURCE_PROOF_ADMISSION_INVALID = "WBP_VISIBLE_SOURCE_PROOF_ADMISSION_INVALID"
VISIBLE_SOURCE_PROOF_WORKING_FLOW_INVALID = (
    "WBP_VISIBLE_SOURCE_PROOF_WORKING_FLOW_INVALID"
)
VISIBLE_SOURCE_PROOF_DIGEST_BINDING_FAILED = (
    "WBP_VISIBLE_SOURCE_PROOF_DIGEST_BINDING_FAILED"
)
VISIBLE_SOURCE_PROOF_FALSE_CLAIM = "WBP_VISIBLE_SOURCE_PROOF_FALSE_CLAIM"
VISIBLE_SOURCE_PROOF_UNSAFE_PACKET = "WBP_VISIBLE_SOURCE_PROOF_UNSAFE_PACKET"

VISIBLE_SOURCE_LAUNCH_SURFACE = (
    "wild-boar-proxy codex-runner working-flow-visible-source-proof"
)
APPROVED_VISIBLE_SOURCE_KIND = "codex_working_flow_delivery_packet"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_digest(value: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(
            dict(value),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        paths.managed_dir
        / "router-hook"
        / "working-flow-visible-source-proof"
        / f"same-turn-{stamp}"
    )


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _contains_secret_value(payload: Any, secret_values: Sequence[str] | None) -> bool:
    values = [value for value in secret_values or [] if isinstance(value, str) and value]
    if not values:
        return False
    try:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        encoded = repr(payload)
    return any(value in encoded for value in values)


def _packet_has_secret_leak(payload: Any, secret_values: Sequence[str] | None) -> bool:
    values = list(secret_values or [])
    return packets.command_packet_has_secret_leak(
        payload,
        secret_values=values,
    ) or _contains_secret_value(payload, values)


def _run_label(index: int) -> str:
    return f"run_{index + 1}"


def _operator_failures(operator_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    required_true = (
        "repeatable_same_turn_operator_proof_proven",
        "same_turn_custom_codex_flow_proven",
        "two_live_runs_proven",
        "admission_run_ids_distinct",
        "prompt_digest_consistent",
        "operator_invariant_digest_consistent",
        "hook_ledger_fresh",
        "runtime_context_digest_bound",
        "api_lane_called",
        "external_live_provider_response_proven",
        "codex_exec_transcript_bound",
        "assistant_continuation_proven",
    )
    if operator_packet.get("packet_kind") != REPEATABLE_OPERATOR_PACKET_KIND:
        failures.append("operator_packet_kind_invalid")
    if operator_packet.get("status") != "ok":
        failures.append("operator_packet_not_ok")
    if operator_packet.get("machine_error_code") != "OK":
        failures.append("operator_machine_error_not_ok")
    if operator_packet.get("operator_run_count") != RUN_COUNT:
        failures.append("operator_run_count_not_two")
    for field in required_true:
        if operator_packet.get(field) is not True:
            failures.append(f"operator_{field}_not_true")
    if operator_packet.get("blocking_reasons") not in ([], ()):
        failures.append("operator_blocking_reasons_not_empty")
    return sorted(set(failures))


def _false_claim_failures(packet: Mapping[str, Any], *, prefix: str) -> list[str]:
    fields = (
        "fallback_used",
        "local_imitation_used",
        "native_codex_subagent_used_as_dip",
        "codex_native_subagent_used_as_dip",
        "product_ready",
        "custom_codex_ui_visibility_proven",
        "delivery_counts_as_custom_codex_ui",
        "native_free_chat_router_proven",
        "raw_prompt_recorded",
        "prompt_text_recorded",
        "natural_phrase_recorded",
        "raw_jsonl_recorded",
        "tool_call_arguments_recorded",
        "route_candidate_recorded",
        "raw_route_id_recorded",
        "selected_api_route_id_recorded",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
        "raw_expected_text_recorded",
        "expected_text_recorded",
        "raw_backend_details_exposed",
        "secret_value_exposed",
    )
    return [
        f"{prefix}_{field}_not_false"
        for field in fields
        if packet.get(field) is True
    ]


def _admission_failures(
    packet: Mapping[str, Any],
    *,
    label: str,
    packet_hash: str,
    operator_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if packet.get("packet_kind") != CUSTOM_CODEX_ADMISSION_PACKET_KIND:
        failures.append(f"{label}_admission_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append(f"{label}_admission_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append(f"{label}_admission_machine_error_not_ok")
    if packet.get("same_turn_custom_codex_flow_proven") is not True:
        failures.append(f"{label}_same_turn_custom_codex_flow_not_proven")
    if packet.get("admission_run_id_recorded") is not False:
        failures.append(f"{label}_admission_run_id_recorded_not_false")
    if packet.get("api_lane_called") is not True:
        failures.append(f"{label}_api_lane_not_called")
    if packet.get("codex_exec_assistant_continuation_proven") is not True:
        failures.append(f"{label}_assistant_continuation_not_proven")
    if packet.get("codex_exec_transcript_bound") is not True:
        failures.append(f"{label}_codex_exec_transcript_not_bound")
    if not packet_hash:
        failures.append(f"{label}_admission_packet_hash_missing")
    operator_hash = _safe_text(
        _mapping_get(operator_packet.get("admission_packet_hashes"), label),
        limit=80,
    )
    if packet_hash and operator_hash and packet_hash != operator_hash:
        failures.append(f"{label}_admission_packet_hash_not_operator_bound")
    operator_run_id = _safe_text(
        _mapping_get(operator_packet.get("admission_run_id_digests"), label),
        limit=80,
    )
    admission_run_id = _safe_text(packet.get("admission_run_id_digest"), limit=80)
    if not admission_run_id:
        failures.append(f"{label}_admission_run_id_digest_missing")
    if operator_run_id and admission_run_id and operator_run_id != admission_run_id:
        failures.append(f"{label}_admission_run_id_not_operator_bound")
    return sorted(set(failures))


def _mapping_get(value: object, key: str) -> object:
    return value.get(key) if isinstance(value, Mapping) else None


def _working_flow_failures(
    packet: Mapping[str, Any],
    *,
    label: str,
    packet_hash: str,
    operator_packet: Mapping[str, Any],
    admission_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    required_true = (
        "codex_working_flow_delivery_proven",
        "codex_exec_assistant_continuation_proven",
        "codex_exec_json_events_observed",
        "codex_exec_jsonl_file_read",
        "approved_delivery_surface_proven",
        "api_lane_called",
        "external_live_provider_response_proven",
        "allowed_api_route_ids_enforced",
        "route_id_allowed",
        "hook_runtime_context_digest_bound",
    )
    if packet.get("packet_kind") != CODEX_WORKING_FLOW_DELIVERY_PACKET_KIND:
        failures.append(f"{label}_working_flow_packet_kind_invalid")
    if packet.get("status") != "ok":
        failures.append(f"{label}_working_flow_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append(f"{label}_working_flow_machine_error_not_ok")
    for field in required_true:
        if packet.get(field) is not True:
            failures.append(f"{label}_{field}_not_true")
    if packet.get("blocking_reasons") not in ([], ()):
        failures.append(f"{label}_working_flow_blocking_reasons_not_empty")
    if not packet_hash:
        failures.append(f"{label}_working_flow_packet_hash_missing")

    assistant_response_observed = packet.get("assistant_response_observed") is True
    command_assistant_bound = (
        packet.get("command_assistant_response_observed") is True
        and packet.get("command_assistant_response_after_command") is True
        and packet.get("command_assistant_response_bound_to_live_provider_digest")
        is True
    )
    mcp_assistant_bound = (
        packet.get("assistant_response_after_tool_result") is True
        and packet.get("assistant_response_bound_to_handoff_digest") is True
    )
    if not assistant_response_observed:
        failures.append(f"{label}_assistant_response_not_observed")
    if not (command_assistant_bound or mcp_assistant_bound):
        failures.append(f"{label}_assistant_response_not_digest_bound")

    transcript_digest = _safe_text(packet.get("codex_exec_transcript_sha256"), limit=80)
    operator_transcript_digest = _safe_text(
        _mapping_get(operator_packet.get("codex_exec_transcript_digests"), label),
        limit=80,
    )
    admission_transcript_digest = _safe_text(
        admission_packet.get("codex_exec_transcript_sha256"),
        limit=80,
    )
    if not transcript_digest:
        failures.append(f"{label}_working_flow_transcript_digest_missing")
    if (
        transcript_digest
        and operator_transcript_digest
        and transcript_digest != operator_transcript_digest
    ):
        failures.append(f"{label}_working_flow_transcript_not_operator_bound")
    if (
        transcript_digest
        and admission_transcript_digest
        and transcript_digest != admission_transcript_digest
    ):
        failures.append(f"{label}_working_flow_transcript_not_admission_bound")
    return sorted(set(failures))


def _machine_error_code(
    *,
    operator_failures: Sequence[str],
    admission_failures: Sequence[str],
    working_flow_failures: Sequence[str],
    binding_failures: Sequence[str],
    false_claim_failures: Sequence[str],
    unsafe_failures: Sequence[str],
) -> str:
    if (
        not operator_failures
        and not admission_failures
        and not working_flow_failures
        and not binding_failures
        and not false_claim_failures
        and not unsafe_failures
    ):
        return VISIBLE_SOURCE_PROOF_OK
    if unsafe_failures:
        return VISIBLE_SOURCE_PROOF_UNSAFE_PACKET
    if false_claim_failures:
        return VISIBLE_SOURCE_PROOF_FALSE_CLAIM
    if operator_failures:
        return VISIBLE_SOURCE_PROOF_OPERATOR_INVALID
    if admission_failures:
        return VISIBLE_SOURCE_PROOF_ADMISSION_INVALID
    if working_flow_failures:
        return VISIBLE_SOURCE_PROOF_WORKING_FLOW_INVALID
    return VISIBLE_SOURCE_PROOF_DIGEST_BINDING_FAILED


def build_working_flow_visible_source_proof_packet(
    *,
    operator_packet: Mapping[str, Any],
    operator_packet_file: Path,
    admission_packets: Sequence[Mapping[str, Any]],
    admission_packet_files: Sequence[Path],
    working_flow_packets: Sequence[Mapping[str, Any]],
    working_flow_packet_files: Sequence[Path],
    changed_files: Sequence[str],
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    operator_data = dict(operator_packet)
    admissions = [dict(packet) for packet in admission_packets]
    working_flows = [dict(packet) for packet in working_flow_packets]
    admission_files = [Path(path) for path in admission_packet_files]
    working_files = [Path(path) for path in working_flow_packet_files]
    operator_hash = sha256_file(Path(operator_packet_file))
    admission_hashes = [sha256_file(path) for path in admission_files]
    working_hashes = [sha256_file(path) for path in working_files]

    operator_failures = _operator_failures(operator_data)
    admission_failures: list[str] = []
    working_flow_failures: list[str] = []
    false_claim_failures: list[str] = []
    binding_failures: list[str] = []
    unsafe_failures: list[str] = []

    if len(admissions) != RUN_COUNT:
        admission_failures.append("admission_packet_count_not_two")
    if len(working_flows) != RUN_COUNT:
        working_flow_failures.append("working_flow_packet_count_not_two")
    if len(admission_files) != RUN_COUNT:
        admission_failures.append("admission_packet_file_count_not_two")
    if len(working_files) != RUN_COUNT:
        working_flow_failures.append("working_flow_packet_file_count_not_two")
    if not operator_hash:
        binding_failures.append("operator_packet_hash_missing")
    if _packet_has_secret_leak(operator_data, secret_values):
        unsafe_failures.append("operator_packet_secret_leak")

    run_visible_source_digests: dict[str, str] = {}
    run_transcript_digests: dict[str, str] = {}
    for index in range(min(len(admissions), len(working_flows), RUN_COUNT)):
        label = _run_label(index)
        admission = admissions[index]
        working = working_flows[index]
        admission_hash = admission_hashes[index] if index < len(admission_hashes) else ""
        working_hash = working_hashes[index] if index < len(working_hashes) else ""
        admission_failures.extend(
            _admission_failures(
                admission,
                label=label,
                packet_hash=admission_hash,
                operator_packet=operator_data,
            )
        )
        working_flow_failures.extend(
            _working_flow_failures(
                working,
                label=label,
                packet_hash=working_hash,
                operator_packet=operator_data,
                admission_packet=admission,
            )
        )
        false_claim_failures.extend(_false_claim_failures(admission, prefix=label))
        false_claim_failures.extend(_false_claim_failures(working, prefix=label))
        if _packet_has_secret_leak(admission, secret_values):
            unsafe_failures.append(f"{label}_admission_packet_secret_leak")
        if _packet_has_secret_leak(working, secret_values):
            unsafe_failures.append(f"{label}_working_flow_packet_secret_leak")
        run_visible_source_digests[label] = _safe_text(
            working.get("command_assistant_binding_digest")
            or working.get("assistant_binding_digest"),
            limit=80,
        )
        run_transcript_digests[label] = _safe_text(
            working.get("codex_exec_transcript_sha256"),
            limit=80,
        )
        if not run_visible_source_digests[label]:
            binding_failures.append(f"{label}_visible_source_digest_missing")

    run_graph_digest = _canonical_digest(
        {
            "operator_packet_hash": operator_hash,
            "admission_packet_hashes": {
                _run_label(index): admission_hashes[index]
                for index in range(min(len(admission_hashes), RUN_COUNT))
            },
            "working_flow_packet_hashes": {
                _run_label(index): working_hashes[index]
                for index in range(min(len(working_hashes), RUN_COUNT))
            },
            "visible_source_digests": run_visible_source_digests,
            "transcript_digests": run_transcript_digests,
        }
    )
    unsafe = _packet_has_secret_leak(
        {
            "packet_kind": WORKING_FLOW_VISIBLE_SOURCE_PACKET_KIND,
            "operator_packet_hash": operator_hash,
            "run_graph_digest": run_graph_digest,
            "visible_source_digests": run_visible_source_digests,
        },
        secret_values,
    )
    if unsafe:
        unsafe_failures.append("working_flow_visible_source_packet_secret_leak")
    ok = bool(
        not operator_failures
        and not admission_failures
        and not working_flow_failures
        and not binding_failures
        and not false_claim_failures
        and not unsafe_failures
    )
    blocking_reasons = sorted(
        set(
            list(operator_failures)
            + list(admission_failures)
            + list(working_flow_failures)
            + list(binding_failures)
            + list(false_claim_failures)
            + list(unsafe_failures)
        )
    )
    machine_error_code = _machine_error_code(
        operator_failures=operator_failures,
        admission_failures=admission_failures,
        working_flow_failures=working_flow_failures,
        binding_failures=binding_failures,
        false_claim_failures=false_claim_failures,
        unsafe_failures=unsafe_failures,
    )
    extra = {
        "schema_version": 1,
        "packet_kind": WORKING_FLOW_VISIBLE_SOURCE_PACKET_KIND,
        "proof_launch_surface": VISIBLE_SOURCE_LAUNCH_SURFACE,
        "proof_scope": "custom_codex_working_flow_visible_source_only",
        "working_flow_visible_source_proven": ok,
        "custom_codex_working_flow_visible_source_proven": ok,
        "same_turn_custom_codex_flow_proven": ok,
        "repeatable_operator_proof_bound": ok,
        "operator_packet_hash": operator_hash,
        "operator_packet_kind": _safe_text(operator_data.get("packet_kind"), limit=80),
        "operator_proof_status": _safe_text(operator_data.get("status"), limit=32),
        "operator_proof_machine_error_code": _safe_text(
            operator_data.get("machine_error_code"),
            limit=96,
        ),
        "operator_proof_valid": not operator_failures,
        "operator_run_count": operator_data.get("operator_run_count"),
        "visible_source_run_count": len(working_flows),
        "required_visible_source_run_count": RUN_COUNT,
        "approved_visible_source_kind": APPROVED_VISIBLE_SOURCE_KIND,
        "approved_visible_source_observed": ok,
        "approved_visible_source_digest_bound": ok,
        "run_graph_digest": run_graph_digest,
        "admission_packet_hashes": {
            _run_label(index): admission_hashes[index]
            for index in range(min(len(admission_hashes), RUN_COUNT))
        },
        "working_flow_packet_hashes": {
            _run_label(index): working_hashes[index]
            for index in range(min(len(working_hashes), RUN_COUNT))
        },
        "visible_source_digests": run_visible_source_digests,
        "codex_exec_transcript_digests": run_transcript_digests,
        "hook_ledger_fresh": ok,
        "runtime_context_digest_bound": ok,
        "route_id_allowed": ok,
        "allowed_api_route_ids_enforced": ok,
        "api_lane_called": ok,
        "external_live_provider_response_proven": ok,
        "assistant_continuation_proven": ok,
        "codex_exec_assistant_continuation_proven": ok,
        "codex_working_flow_delivery_proven": ok,
        "codex_exec_transcript_bound": ok,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "custom_codex_ui_visibility_proven": False,
        "does_not_prove_custom_codex_ui": True,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "does_not_prove_native_free_chat_router": True,
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
        "raw_expected_text_recorded": False,
        "expected_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "operator_failures": operator_failures,
        "admission_failures": sorted(set(admission_failures)),
        "working_flow_failures": sorted(set(working_flow_failures)),
        "binding_failures": sorted(set(binding_failures)),
        "false_claim_failures": sorted(set(false_claim_failures)),
        "unsafe_failures": sorted(set(unsafe_failures)),
        "blocking_reasons": blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved repeatable Custom Codex working-flow visible-source evidence."
            if ok
            else "WBP blocked working-flow visible-source proof before product readiness."
        ),
        machine_error_code=machine_error_code,
        liveness="network_dependent",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=sorted(set(changed_files)),
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_working_flow_visible_source_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    codex_bin: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    expected_text: str,
    sandbox: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    proof_root = _proof_root(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    runtime_context, _metadata = load_runtime_context_packet(
        runtime_context_path(paths=paths, runtime_context_file=None)
    )
    secret_values = [prompt_text, expected_text] + _runtime_secret_values(runtime_context)
    operator_packet = run_repeatable_operator_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        codex_bin=codex_bin,
        proof_dir=str(proof_root),
        codex_cwd=codex_cwd,
        expected_text=expected_text,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
    )
    operator_packet_path = proof_root / "repeatable-same-turn-operator-proof.packet.json"
    if not operator_packet_path.exists():
        write_json_atomic(operator_packet_path, operator_packet)

    admission_packets: list[dict[str, Any]] = []
    admission_packet_files: list[Path] = []
    working_flow_packets: list[dict[str, Any]] = []
    working_flow_packet_files: list[Path] = []
    changed_files: list[str] = [str(path) for path in operator_packet.get("changed_files", [])]
    changed_files.append(str(operator_packet_path))

    for index in range(RUN_COUNT):
        run_dir = proof_root / _run_label(index)
        admission_file = run_dir / "custom-codex-admission.packet.json"
        working_file = run_dir / "working-flow-delivery-proof.packet.json"
        admission_packets.append(_read_json_mapping(admission_file))
        working_flow_packets.append(_read_json_mapping(working_file))
        admission_packet_files.append(admission_file)
        working_flow_packet_files.append(working_file)

    final_packet_path = proof_root / "working-flow-visible-source-proof.packet.json"
    changed_files.append(str(final_packet_path))
    final_packet = build_working_flow_visible_source_proof_packet(
        operator_packet=operator_packet,
        operator_packet_file=operator_packet_path,
        admission_packets=admission_packets,
        admission_packet_files=admission_packet_files,
        working_flow_packets=working_flow_packets,
        working_flow_packet_files=working_flow_packet_files,
        changed_files=changed_files,
        secret_values=secret_values,
    )
    write_json_atomic(final_packet_path, final_packet)
    return final_packet
