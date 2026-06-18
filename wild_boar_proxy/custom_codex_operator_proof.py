# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_admission import (
    CUSTOM_CODEX_ADMISSION_PACKET_KIND,
    DEFAULT_EXPECTED_TEXT,
    DEFAULT_SANDBOX,
    DEFAULT_TIMEOUT_SECONDS,
    run_custom_codex_admission_command,
)
from .proof_seal import sha256_file
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths, write_json_atomic


REPEATABLE_OPERATOR_PACKET_KIND = "wbp_repeatable_same_turn_operator_proof"

OPERATOR_OK = "OK"
OPERATOR_ADMISSION_FAILED = "WBP_REPEATABLE_OPERATOR_ADMISSION_FAILED"
OPERATOR_RUN_ID_REUSED = "WBP_REPEATABLE_OPERATOR_RUN_ID_REUSED"
OPERATOR_DIGEST_BINDING_FAILED = "WBP_REPEATABLE_OPERATOR_DIGEST_BINDING_FAILED"
OPERATOR_FALSE_CLAIM = "WBP_REPEATABLE_OPERATOR_FALSE_CLAIM"
OPERATOR_UNSAFE_PACKET = "WBP_REPEATABLE_OPERATOR_UNSAFE_PACKET"

OPERATOR_LAUNCH_SURFACE = "wild-boar-proxy codex-runner operator-proof"
RUN_COUNT = 2


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
    return paths.managed_dir / "router-hook" / "operator-proof" / f"same-turn-{stamp}"


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _runtime_secret_values(runtime_context: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    allowed = runtime_context.get("allowed_api_route_ids")
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        values.extend(route for route in allowed if isinstance(route, str) and route)
    routes = runtime_context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        values.extend(route for route in routes.values() if isinstance(route, str) and route)
    return sorted(set(values))


def _run_label(index: int) -> str:
    return f"run_{index + 1}"


def _operator_machine_error_code(
    *,
    admission_failures: Sequence[str],
    reused_run_id: bool,
    binding_failures: Sequence[str],
    false_claim_failures: Sequence[str],
    unsafe: bool,
) -> str:
    if (
        not admission_failures
        and not reused_run_id
        and not binding_failures
        and not false_claim_failures
        and not unsafe
    ):
        return OPERATOR_OK
    if unsafe:
        return OPERATOR_UNSAFE_PACKET
    if false_claim_failures:
        return OPERATOR_FALSE_CLAIM
    if admission_failures:
        return OPERATOR_ADMISSION_FAILED
    if reused_run_id:
        return OPERATOR_RUN_ID_REUSED
    return OPERATOR_DIGEST_BINDING_FAILED


def _operator_invariant_digest(packet: Mapping[str, Any]) -> str:
    stable_fields = {
        "packet_kind": _safe_text(packet.get("packet_kind"), limit=120),
        "admission_scope": _safe_text(packet.get("admission_scope"), limit=120),
        "same_turn_claim_ceiling": _safe_text(
            packet.get("same_turn_claim_ceiling"),
            limit=160,
        ),
        "runner_launch_surface_kind": _safe_text(
            packet.get("runner_launch_surface_kind"),
            limit=120,
        ),
        "codex_exec_command_sha256": _safe_text(
            packet.get("codex_exec_command_sha256"),
            limit=80,
        ),
        "codex_exec_prompt_digest": _safe_text(
            packet.get("codex_exec_prompt_digest"),
            limit=80,
        ),
        "external_models_dir_source": _safe_text(
            packet.get("external_models_dir_source"),
            limit=120,
        ),
        "operator_false_claim_ceiling": {
            "product_ready": packet.get("product_ready") is False,
            "custom_codex_ui_visibility_proven": (
                packet.get("custom_codex_ui_visibility_proven") is False
            ),
            "native_free_chat_router_proven": (
                packet.get("native_free_chat_router_proven") is False
            ),
            "fallback_used": packet.get("fallback_used") is False,
            "local_imitation_used": packet.get("local_imitation_used") is False,
        },
    }
    return _canonical_digest(stable_fields)


def build_repeatable_operator_packet(
    *,
    admission_packets: Sequence[Mapping[str, Any]],
    admission_packet_files: Sequence[Path],
    changed_files: Sequence[str],
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    packets_by_run = [dict(packet) for packet in admission_packets]
    packet_files = [Path(path) for path in admission_packet_files]
    admission_hashes = [sha256_file(path) for path in packet_files]
    admission_run_id_digests = [
        _safe_text(packet.get("admission_run_id_digest"), limit=80)
        for packet in packets_by_run
    ]
    prompt_digests = [
        _safe_text(packet.get("codex_exec_prompt_digest"), limit=80)
        for packet in packets_by_run
    ]
    run_graph_digests = [
        _safe_text(packet.get("run_graph_digest"), limit=80)
        for packet in packets_by_run
    ]
    transcript_digests = [
        _safe_text(packet.get("codex_exec_transcript_sha256"), limit=80)
        for packet in packets_by_run
    ]
    invariant_digests = [_operator_invariant_digest(packet) for packet in packets_by_run]

    admission_failures: list[str] = []
    binding_failures: list[str] = []
    false_claim_failures: list[str] = []

    if len(packets_by_run) != RUN_COUNT:
        admission_failures.append("operator_run_count_not_two")
    if len(packet_files) != RUN_COUNT:
        admission_failures.append("operator_admission_packet_file_count_not_two")

    required_true_fields = (
        "admission_proven",
        "same_turn_custom_codex_flow_proven",
        "admission_run_id_digest_bound",
        "run_id_bound",
        "hook_ledger_fresh",
        "prompt_digest_bound",
        "runtime_context_digest_bound",
        "api_lane_called",
        "external_live_provider_response_proven",
        "codex_exec_transcript_bound",
        "same_codex_exec_jsonl_bound",
        "codex_exec_assistant_continuation_proven",
        "proof_seal_verified",
        "source_seal_runtime_context_digest_bound",
        "source_seal_hook_ledger_digest_bound",
        "source_seal_profile_hook_config_digest_bound",
        "working_flow_seal_input_hashes_bound",
    )
    required_false_fields = (
        "admission_run_id_recorded",
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
    for index, packet in enumerate(packets_by_run):
        label = _run_label(index)
        if packet.get("status") != "ok" or packet.get("machine_error_code") != "OK":
            admission_failures.append(f"{label}_admission_packet_not_ok")
        if packet.get("packet_kind") != CUSTOM_CODEX_ADMISSION_PACKET_KIND:
            admission_failures.append(f"{label}_admission_packet_kind_invalid")
        for field in required_true_fields:
            if packet.get(field) is not True:
                binding_failures.append(f"{label}_{field}_not_true")
        for field in required_false_fields:
            if packet.get(field) is not False:
                false_claim_failures.append(f"{label}_{field}_not_false")
        if not admission_hashes[index]:
            binding_failures.append(f"{label}_admission_packet_hash_missing")
        if not admission_run_id_digests[index]:
            binding_failures.append(f"{label}_admission_run_id_digest_missing")
        if not run_graph_digests[index]:
            binding_failures.append(f"{label}_run_graph_digest_missing")
        if not transcript_digests[index]:
            binding_failures.append(f"{label}_transcript_digest_missing")
        if packet.get("same_turn_binding_failures") not in ([], ()):
            binding_failures.append(f"{label}_same_turn_binding_failures_not_empty")

    reused_run_id = bool(
        len(admission_run_id_digests) == RUN_COUNT
        and all(admission_run_id_digests)
        and len(set(admission_run_id_digests)) != RUN_COUNT
    )
    if len(set(prompt_digests)) > 1:
        binding_failures.append("prompt_digest_not_repeatable_across_runs")
    if any(not digest for digest in prompt_digests):
        binding_failures.append("prompt_digest_missing")
    if len(set(admission_hashes)) != len([item for item in admission_hashes if item]):
        binding_failures.append("admission_packet_hashes_not_distinct")
    if len(invariant_digests) == RUN_COUNT and len(set(invariant_digests)) != 1:
        binding_failures.append("operator_invariant_digest_not_repeatable")

    run_hashes = {
        _run_label(index): admission_hashes[index]
        for index in range(min(len(admission_hashes), RUN_COUNT))
    }
    run_graph_digest = _canonical_digest(
        {
            "admission_packet_hashes": run_hashes,
            "admission_run_id_digests": {
                _run_label(index): admission_run_id_digests[index]
                for index in range(min(len(admission_run_id_digests), RUN_COUNT))
            },
            "run_graph_digests": {
                _run_label(index): run_graph_digests[index]
                for index in range(min(len(run_graph_digests), RUN_COUNT))
            },
            "transcript_digests": {
                _run_label(index): transcript_digests[index]
                for index in range(min(len(transcript_digests), RUN_COUNT))
            },
            "operator_invariant_digest": invariant_digests[0]
            if invariant_digests
            else "",
        }
    )

    unsafe = packets.command_packet_has_secret_leak(
        {
            "packet_kind": REPEATABLE_OPERATOR_PACKET_KIND,
            "admission_packet_hashes": run_hashes,
            "run_graph_digest": run_graph_digest,
        },
        secret_values=list(secret_values or []),
    )
    ok = bool(
        not admission_failures
        and not reused_run_id
        and not binding_failures
        and not false_claim_failures
        and not unsafe
    )
    machine_error_code = _operator_machine_error_code(
        admission_failures=admission_failures,
        reused_run_id=reused_run_id,
        binding_failures=binding_failures,
        false_claim_failures=false_claim_failures,
        unsafe=unsafe,
    )
    blocking_reasons = sorted(
        set(
            list(admission_failures)
            + (["admission_run_id_reused"] if reused_run_id else [])
            + list(binding_failures)
            + list(false_claim_failures)
            + (["operator_packet_secret_leak"] if unsafe else [])
        )
    )
    extra = {
        "schema_version": 1,
        "packet_kind": REPEATABLE_OPERATOR_PACKET_KIND,
        "operator_launch_surface": OPERATOR_LAUNCH_SURFACE,
        "operator_scope": "repeatable_same_turn_custom_codex_proof",
        "repeatable_same_turn_operator_proof_proven": ok,
        "same_turn_custom_codex_flow_proven": ok,
        "operator_run_count": len(packets_by_run),
        "required_operator_run_count": RUN_COUNT,
        "two_live_runs_proven": ok,
        "admission_run_ids_distinct": bool(not reused_run_id and len(set(admission_run_id_digests)) == RUN_COUNT),
        "admission_run_id_reused": reused_run_id,
        "admission_run_id_digests": {
            _run_label(index): admission_run_id_digests[index]
            for index in range(min(len(admission_run_id_digests), RUN_COUNT))
        },
        "admission_run_ids_recorded": False,
        "prompt_digest_consistent": bool(
            prompt_digests and len(set(prompt_digests)) == 1 and all(prompt_digests)
        ),
        "operator_invariant_digest_consistent": bool(
            invariant_digests and len(set(invariant_digests)) == 1
        ),
        "operator_invariant_digest": invariant_digests[0] if invariant_digests else "",
        "operator_run_graph_digest": run_graph_digest,
        "admission_packet_hashes": run_hashes,
        "run_graph_digests": {
            _run_label(index): run_graph_digests[index]
            for index in range(min(len(run_graph_digests), RUN_COUNT))
        },
        "codex_exec_transcript_digests": {
            _run_label(index): transcript_digests[index]
            for index in range(min(len(transcript_digests), RUN_COUNT))
        },
        "hook_ledger_fresh": ok,
        "prompt_digest_bound": ok,
        "runtime_context_digest_bound": ok,
        "api_lane_called": ok,
        "external_live_provider_response_proven": ok,
        "codex_exec_transcript_bound": ok,
        "assistant_continuation_proven": ok,
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
        "admission_failures": sorted(set(admission_failures)),
        "binding_failures": sorted(set(binding_failures)),
        "false_claim_failures": sorted(set(false_claim_failures)),
        "blocking_reasons": blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved two repeatable same-turn Custom Codex operator runs."
            if ok
            else "WBP blocked repeatable same-turn operator proof before product readiness."
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


def run_repeatable_operator_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    expected_text: str = DEFAULT_EXPECTED_TEXT,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    proof_root = _proof_root(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    runtime_context, _metadata = load_runtime_context_packet(
        runtime_context_path(paths=paths, runtime_context_file=None)
    )
    secret_values = [prompt_text, expected_text] + _runtime_secret_values(runtime_context)
    admission_packets: list[dict[str, Any]] = []
    admission_packet_files: list[Path] = []
    changed_files: list[str] = []
    for index in range(RUN_COUNT):
        run_dir = proof_root / _run_label(index)
        run_dir.mkdir(parents=True, exist_ok=True)
        packet = run_custom_codex_admission_command(
            paths=paths,
            prompt_text=prompt_text,
            codex_bin=codex_bin,
            codex_model=codex_model,
            proof_dir=str(run_dir),
            codex_cwd=codex_cwd,
            expected_text=expected_text,
            sandbox=sandbox,
            timeout_seconds=timeout_seconds,
        )
        admission_packets.append(packet)
        changed_files.extend(str(path) for path in packet.get("changed_files", []))
        admission_packet_path = run_dir / "custom-codex-admission.packet.json"
        if not admission_packet_path.exists():
            write_json_atomic(admission_packet_path, packet)
            changed_files.append(str(admission_packet_path))
        admission_packet_files.append(admission_packet_path)

    final_packet_path = proof_root / "repeatable-same-turn-operator-proof.packet.json"
    changed_files.append(str(final_packet_path))
    final_packet = build_repeatable_operator_packet(
        admission_packets=admission_packets,
        admission_packet_files=admission_packet_files,
        changed_files=changed_files,
        secret_values=secret_values,
    )
    write_json_atomic(final_packet_path, final_packet)
    return final_packet
