# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256
from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_approved_visible_source_observation import (
    VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
)
from .full_runtime_dispatch_proof import (
    FULL_RUNTIME_DISPATCH_OK,
    FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND,
    run_full_runtime_dispatch_proof_command,
)
from .official_e2e_working_flow_proof_join import (
    run_official_e2e_working_flow_proof_join_command,
)
from .official_mcp_approved_codex_exec_source_observation import (
    run_official_mcp_approved_codex_exec_source_observation_command,
)
from .official_mcp_assistant_continuation_observation import (
    run_official_mcp_assistant_continuation_observation_command,
)
from .official_mcp_delivery_candidate_join import (
    run_official_mcp_delivery_candidate_join_command,
)
from .official_mcp_handoff_source_proof import (
    run_official_mcp_working_flow_handoff_source_proof_command,
)
from .official_mcp_transcript_tool_result_observation import (
    run_official_mcp_transcript_tool_result_observation_command,
)
from .official_mcp_working_flow_delivery_join import (
    run_official_mcp_working_flow_delivery_join_command,
)
from .router_hook_entry import _safe_text
from .runtime import write_json_atomic


FULL_RUNTIME_DISPATCH_PROOF_RUNNER_PACKET_KIND = (
    "wbp_full_runtime_dispatch_proof_runner"
)
FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_PACKET_KIND = (
    "wbp_full_runtime_dispatch_proof_runner_manifest"
)

FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK = "OK"
FULL_RUNTIME_DISPATCH_PROOF_RUNNER_INPUT_INVALID = (
    "WBP_FULL_RUNTIME_DISPATCH_PROOF_RUNNER_INPUT_INVALID"
)
FULL_RUNTIME_DISPATCH_PROOF_RUNNER_CHAIN_INVALID = (
    "WBP_FULL_RUNTIME_DISPATCH_PROOF_RUNNER_CHAIN_INVALID"
)
FULL_RUNTIME_DISPATCH_PROOF_RUNNER_UNSAFE_SOURCE = (
    "WBP_FULL_RUNTIME_DISPATCH_PROOF_RUNNER_UNSAFE_SOURCE"
)
FULL_RUNTIME_DISPATCH_PROOF_RUNNER_ARTIFACT_WRITE_FAILED = (
    "WBP_FULL_RUNTIME_DISPATCH_PROOF_RUNNER_ARTIFACT_WRITE_FAILED"
)

FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME = (
    "full-runtime-dispatch-proof-runner-manifest.json"
)
FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME = (
    "full-runtime-dispatch-proof-runner.packet.json"
)

_ARTIFACT_SEQUENCE = (
    "official-working-flow-handoff-source-proof.packet.json",
    "official-transcript-tool-result-observation.packet.json",
    "official-assistant-continuation-observation.packet.json",
    "official-approved-codex-exec-source-observation.packet.json",
    "official-delivery-candidate-join.packet.json",
    "official-working-flow-delivery-join.packet.json",
    "official-e2e-working-flow-proof-join.packet.json",
    FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME,
)
_INPUTS = (
    ("real_custom_hook_proof", "real_custom_hook_proof_file"),
    ("working_flow_delivery_proof", "working_flow_delivery_proof_file"),
    ("codex_exec_jsonl", "codex_exec_jsonl_file"),
    ("custom_codex_ui_visibility_proof", "custom_codex_ui_visibility_proof_file"),
)
_FINAL_REQUIRED_TRUE_FIELDS = (
    "full_runtime_dispatch_proven",
    "custom_codex_flow_proven",
    "user_prompt_submit_hook_ran",
    "hook_prompt_digest_bound",
    "hook_runtime_context_digest_bound",
    "alias_context_read",
    "route_id_allowed",
    "api_lane_called",
    "dispatch_proven",
    "route_bound_dispatch_proven",
    "handoff_bound_to_dispatch",
    "codex_working_flow_delivery_proven",
    "native_response_bound_to_handoff",
    "visible_response_after_dispatch",
    "custom_codex_ui_visibility_proven",
)
_FINAL_REQUIRED_FALSE_FIELDS = (
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "raw_prompt_recorded",
    "raw_dom_exposed",
    "raw_ax_tree_exposed",
    "raw_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "state_written",
    "file_mutation_attempted",
)
_UNSAFE_TRUE_FIELDS = (
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "raw_task_recorded",
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
    "state_written",
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence_nonempty(value: object) -> bool:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return bool(list(value))
    return bool(value)


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _file_sha256(path: Path) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _input_file_metadata(path: Path, *, prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_file_required": True,
        f"{prefix}_file_present": path.exists() and path.is_file(),
        f"{prefix}_file_sha256": _file_sha256(path),
        f"{prefix}_file_path_recorded": False,
    }


def _freshness_anchor_metadata(freshness_anchor_digest: str | None) -> dict[str, Any]:
    provided = bool(freshness_anchor_digest)
    digest = _hex_sha256(freshness_anchor_digest)
    return {
        "freshness_anchor_digest_provided": provided,
        "freshness_anchor_digest_valid": bool(digest) if provided else True,
        "freshness_anchor_digest_present": bool(digest),
        "freshness_anchor_digest": digest,
        "raw_freshness_anchor_recorded": False,
    }


def _input_failures(metadata: Mapping[str, Any], *, proof_dir: str) -> list[str]:
    failures: list[str] = []
    if not proof_dir:
        failures.append("proof_dir_missing")
    if (
        metadata.get("freshness_anchor_digest_provided") is True
        and metadata.get("freshness_anchor_digest_valid") is not True
    ):
        failures.append("freshness_anchor_digest_invalid")
    for prefix, _arg_name in _INPUTS:
        if metadata.get(f"{prefix}_file_present") is not True:
            failures.append(f"{prefix}_file_missing")
        if not _hex_sha256(metadata.get(f"{prefix}_file_sha256")):
            failures.append(f"{prefix}_file_sha256_missing")
        if metadata.get(f"{prefix}_file_path_recorded") is not False:
            failures.append(f"{prefix}_file_path_recorded")
    return sorted(set(failures))


def _write_artifact(path: Path, payload: Mapping[str, Any]) -> None:
    write_json_atomic(path, dict(payload))


def _packet_status_summary(name: str, packet: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "artifact_name": name,
        "packet_kind": _safe_text(packet.get("packet_kind"), limit=96),
        "status": _safe_text(packet.get("status"), limit=32),
        "machine_error_code": _safe_text(packet.get("machine_error_code"), limit=96),
        "file_sha256": _file_sha256(path),
        "file_path_recorded": False,
    }


def _artifact_status_failures(
    artifact_summaries: Sequence[Mapping[str, Any]],
) -> list[str]:
    failures: list[str] = []
    for summary in artifact_summaries:
        name = _safe_text(summary.get("artifact_name"), limit=96)
        if summary.get("status") != "ok":
            failures.append(f"{name}_status_not_ok")
        if summary.get("machine_error_code") != "OK":
            failures.append(f"{name}_machine_error_not_ok")
        if not _hex_sha256(summary.get("file_sha256")):
            failures.append(f"{name}_file_sha256_missing")
        if summary.get("file_path_recorded") is not False:
            failures.append(f"{name}_file_path_recorded")
    return sorted(set(failures))


def _final_packet_failures(final_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if final_packet.get("packet_kind") != FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND:
        failures.append("final_full_runtime_packet_kind_invalid")
    if final_packet.get("status") != "ok":
        failures.append("final_full_runtime_status_not_ok")
    if final_packet.get("machine_error_code") != FULL_RUNTIME_DISPATCH_OK:
        failures.append("final_full_runtime_machine_error_not_ok")
    for field in _FINAL_REQUIRED_TRUE_FIELDS:
        if final_packet.get(field) is not True:
            failures.append(f"final_{field}_not_true")
    for field in _FINAL_REQUIRED_FALSE_FIELDS:
        if final_packet.get(field) is not False:
            failures.append(f"final_{field}_not_false")
    if _sequence_nonempty(final_packet.get("blocking_reasons")):
        failures.append("final_blocking_reasons_not_empty")
    if not _hex_sha256(final_packet.get("handoff_payload_digest")):
        failures.append("final_handoff_payload_digest_missing")
    return sorted(set(failures))


def _unsafe_failures(
    packets_by_name: Mapping[str, Mapping[str, Any]],
    *,
    secret_values: Sequence[str] | None = None,
) -> list[str]:
    failures: list[str] = []
    for name, packet in packets_by_name.items():
        safe_name = name.removesuffix(".packet.json").replace("-", "_")
        for field in _UNSAFE_TRUE_FIELDS:
            if packet.get(field) is True:
                failures.append(f"{safe_name}_{field}_unsafe")
        if packets.command_packet_has_secret_leak(packet, secret_values=list(secret_values or [])):
            failures.append(f"{safe_name}_secret_material_present")
    return sorted(set(failures))


def _machine_error_code(
    *,
    input_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    artifact_failures: Sequence[str],
    chain_failures: Sequence[str],
) -> str:
    if unsafe_failures:
        return FULL_RUNTIME_DISPATCH_PROOF_RUNNER_UNSAFE_SOURCE
    if input_failures:
        return FULL_RUNTIME_DISPATCH_PROOF_RUNNER_INPUT_INVALID
    if artifact_failures:
        return FULL_RUNTIME_DISPATCH_PROOF_RUNNER_ARTIFACT_WRITE_FAILED
    if chain_failures:
        return FULL_RUNTIME_DISPATCH_PROOF_RUNNER_CHAIN_INVALID
    return FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK


def _build_manifest(
    *,
    input_metadata: Mapping[str, Any],
    artifact_summaries: Sequence[Mapping[str, Any]],
    final_packet: Mapping[str, Any],
    runner_status: str,
    runner_machine_error_code: str,
) -> dict[str, Any]:
    freshness_anchor_digest = _hex_sha256(input_metadata.get("freshness_anchor_digest"))
    input_files = []
    for prefix, _arg_name in _INPUTS:
        input_files.append(
            {
                "input_name": prefix,
                "file_present": input_metadata.get(f"{prefix}_file_present") is True,
                "file_sha256": _hex_sha256(input_metadata.get(f"{prefix}_file_sha256")),
                "file_path_recorded": False,
            }
        )
    return {
        "schema_version": 1,
        "packet_kind": FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_PACKET_KIND,
        "proof_scope": "repeatable_full_runtime_dispatch_proof_runner",
        "input_file_paths_recorded": False,
        "artifact_file_paths_recorded": False,
        "input_files": input_files,
        "artifacts": [dict(summary) for summary in artifact_summaries],
        "final_packet_kind": _safe_text(final_packet.get("packet_kind"), limit=96),
        "final_status": _safe_text(final_packet.get("status"), limit=32),
        "final_machine_error_code": _safe_text(
            final_packet.get("machine_error_code"),
            limit=96,
        ),
        "final_full_runtime_dispatch_proven": (
            final_packet.get("full_runtime_dispatch_proven") is True
        ),
        "final_handoff_payload_digest": _hex_sha256(
            final_packet.get("handoff_payload_digest")
        ),
        "runner_status": runner_status,
        "runner_machine_error_code": runner_machine_error_code,
        "freshness_anchor_required": False,
        "freshness_anchor_digest_present": bool(freshness_anchor_digest),
        "freshness_anchor_digest": freshness_anchor_digest,
        "freshness_anchor_bound_to_manifest": bool(freshness_anchor_digest),
        "expected_freshness_anchor_digest_bound": False,
        "external_freshness_proven": False,
        "raw_freshness_anchor_recorded": False,
        "product_ready": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "raw_dom_exposed": False,
        "raw_ax_tree_exposed": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "roadmap_recorded": False,
        "future_plan_recorded": False,
        "next_contour_recorded": False,
    }


def _run_chain(
    *,
    real_custom_hook_proof_file: str,
    working_flow_delivery_proof_file: str,
    codex_exec_jsonl_file: str,
    custom_codex_ui_visibility_proof_file: str,
    proof_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    artifacts = {name: proof_root / name for name in _ARTIFACT_SEQUENCE}
    packets_by_name: dict[str, dict[str, Any]] = {}
    artifact_failures: list[str] = []
    try:
        proof_root.mkdir(parents=True, exist_ok=True)

        handoff_source_packet = (
            run_official_mcp_working_flow_handoff_source_proof_command(
                working_flow_delivery_proof_file=working_flow_delivery_proof_file,
            )
        )
        packets_by_name["official-working-flow-handoff-source-proof.packet.json"] = (
            handoff_source_packet
        )
        _write_artifact(
            artifacts["official-working-flow-handoff-source-proof.packet.json"],
            handoff_source_packet,
        )

        transcript_packet = run_official_mcp_transcript_tool_result_observation_command(
            handoff_source_file=str(
                artifacts["official-working-flow-handoff-source-proof.packet.json"]
            ),
            codex_exec_jsonl_file=codex_exec_jsonl_file,
        )
        packets_by_name["official-transcript-tool-result-observation.packet.json"] = (
            transcript_packet
        )
        _write_artifact(
            artifacts["official-transcript-tool-result-observation.packet.json"],
            transcript_packet,
        )

        assistant_packet = run_official_mcp_assistant_continuation_observation_command(
            transcript_observation_file=str(
                artifacts["official-transcript-tool-result-observation.packet.json"]
            ),
            codex_exec_jsonl_file=codex_exec_jsonl_file,
        )
        packets_by_name["official-assistant-continuation-observation.packet.json"] = (
            assistant_packet
        )
        _write_artifact(
            artifacts["official-assistant-continuation-observation.packet.json"],
            assistant_packet,
        )

        approved_source_packet = (
            run_official_mcp_approved_codex_exec_source_observation_command(
                assistant_continuation_observation_file=str(
                    artifacts["official-assistant-continuation-observation.packet.json"]
                ),
                approved_source_kind=VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                codex_exec_jsonl_file=codex_exec_jsonl_file,
            )
        )
        packets_by_name[
            "official-approved-codex-exec-source-observation.packet.json"
        ] = approved_source_packet
        _write_artifact(
            artifacts["official-approved-codex-exec-source-observation.packet.json"],
            approved_source_packet,
        )

        delivery_candidate_packet = run_official_mcp_delivery_candidate_join_command(
            approved_exec_source_observation_file=str(
                artifacts["official-approved-codex-exec-source-observation.packet.json"]
            ),
        )
        packets_by_name["official-delivery-candidate-join.packet.json"] = (
            delivery_candidate_packet
        )
        _write_artifact(
            artifacts["official-delivery-candidate-join.packet.json"],
            delivery_candidate_packet,
        )

        delivery_join_packet = run_official_mcp_working_flow_delivery_join_command(
            delivery_candidate_file=str(
                artifacts["official-delivery-candidate-join.packet.json"]
            ),
            working_flow_delivery_proof_file=working_flow_delivery_proof_file,
        )
        packets_by_name["official-working-flow-delivery-join.packet.json"] = (
            delivery_join_packet
        )
        _write_artifact(
            artifacts["official-working-flow-delivery-join.packet.json"],
            delivery_join_packet,
        )

        official_delivery_source = str(
            artifacts["official-working-flow-delivery-join.packet.json"]
        )
        if delivery_join_packet.get("status") != "ok":
            official_delivery_source = working_flow_delivery_proof_file

        official_e2e_packet = run_official_e2e_working_flow_proof_join_command(
            real_custom_hook_proof_file=real_custom_hook_proof_file,
            official_working_flow_delivery_join_file=official_delivery_source,
        )
        packets_by_name["official-e2e-working-flow-proof-join.packet.json"] = (
            official_e2e_packet
        )
        _write_artifact(
            artifacts["official-e2e-working-flow-proof-join.packet.json"],
            official_e2e_packet,
        )

        final_packet = run_full_runtime_dispatch_proof_command(
            official_e2e_working_flow_proof_file=str(
                artifacts["official-e2e-working-flow-proof-join.packet.json"]
            ),
            custom_codex_ui_visibility_proof_file=custom_codex_ui_visibility_proof_file,
            proof_dir=str(proof_root),
        )
        packets_by_name[FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME] = final_packet
        return final_packet, packets_by_name, artifact_failures
    except (OSError, TypeError, ValueError):
        artifact_failures.append("full_runtime_runner_artifact_write_failed")
    return {}, packets_by_name, sorted(set(artifact_failures))


def build_full_runtime_dispatch_proof_runner_packet(
    *,
    input_metadata: Mapping[str, Any] | None,
    artifact_summaries: Sequence[Mapping[str, Any]] | None,
    artifact_packets: Mapping[str, Mapping[str, Any]] | None = None,
    final_packet: Mapping[str, Any] | None,
    manifest_packet: Mapping[str, Any] | None,
    manifest_file_sha256: str = "",
    manifest_file_written: bool = False,
    runner_packet_file_written: bool = False,
    artifact_failures: Sequence[str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    metadata = dict(input_metadata or {})
    summaries = list(artifact_summaries or [])
    final = _mapping(final_packet)
    manifest = _mapping(manifest_packet)
    artifact_failure_list = sorted(set(artifact_failures or []))

    input_failure_list = _input_failures(
        metadata,
        proof_dir="present" if metadata.get("proof_dir_present") is True else "",
    )
    artifact_status_failures = _artifact_status_failures(summaries)
    final_failures = _final_packet_failures(final)
    chain_failures = sorted(
        set(
            artifact_status_failures
            + final_failures
            + _safe_reasons(final.get("blocking_reasons"))
        )
    )
    unsafe_failure_list = _unsafe_failures(
        {
            **dict(artifact_packets or {}),
            FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME: final,
            "manifest": manifest,
        },
        secret_values=secret_values,
    )
    if manifest.get("product_ready") is True:
        unsafe_failure_list.append("manifest_product_ready_unsafe")
    machine_error_code = _machine_error_code(
        input_failures=input_failure_list,
        unsafe_failures=unsafe_failure_list,
        artifact_failures=artifact_failure_list,
        chain_failures=chain_failures,
    )
    ok = machine_error_code == FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK
    blocking_reasons = sorted(
        set(
            input_failure_list
            + unsafe_failure_list
            + artifact_failure_list
            + chain_failures
        )
    )
    artifact_files_written = any(
        _hex_sha256(summary.get("file_sha256")) for summary in summaries
    )
    evidence_written = bool(
        runner_packet_file_written or manifest_file_written or artifact_files_written
    )
    freshness_anchor_digest = _hex_sha256(metadata.get("freshness_anchor_digest"))
    manifest_freshness_anchor_digest = _hex_sha256(
        manifest.get("freshness_anchor_digest")
    )

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": FULL_RUNTIME_DISPATCH_PROOF_RUNNER_PACKET_KIND,
        "proof_scope": "repeatable_full_runtime_dispatch_proof_runner",
        "runner_inputs_valid": not input_failure_list,
        "runner_input_failures": input_failure_list,
        "runner_unsafe_failures": sorted(set(unsafe_failure_list)),
        "runner_artifact_failures": artifact_failure_list,
        "runner_chain_failures": chain_failures,
        "artifact_file_paths_recorded": False,
        "artifact_file_names": [summary.get("artifact_name") for summary in summaries],
        "artifact_summaries": [dict(summary) for summary in summaries],
        "manifest_packet_kind": _safe_text(manifest.get("packet_kind"), limit=96),
        "manifest_file_written": manifest_file_written,
        "manifest_file_sha256": _hex_sha256(manifest_file_sha256),
        "manifest_file_path_recorded": False,
        "runner_packet_file_written": runner_packet_file_written,
        "runner_packet_file_path_recorded": False,
        "freshness_anchor_required": False,
        "freshness_anchor_digest_present": bool(freshness_anchor_digest),
        "freshness_anchor_digest": freshness_anchor_digest,
        "freshness_anchor_bound_to_runner": bool(freshness_anchor_digest),
        "freshness_anchor_bound_to_manifest": bool(
            freshness_anchor_digest
            and manifest_freshness_anchor_digest == freshness_anchor_digest
        ),
        "expected_freshness_anchor_digest_bound": False,
        "external_freshness_proven": False,
        "raw_freshness_anchor_recorded": False,
        "full_runtime_dispatch_runner_proven": ok,
        "full_runtime_dispatch_proven": bool(
            ok and final.get("full_runtime_dispatch_proven") is True
        ),
        "custom_codex_flow_proven": bool(
            ok and final.get("custom_codex_flow_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and final.get("user_prompt_submit_hook_ran") is True
        ),
        "api_lane_called": bool(ok and final.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and final.get("dispatch_proven") is True),
        "codex_working_flow_delivery_proven": bool(
            ok and final.get("codex_working_flow_delivery_proven") is True
        ),
        "custom_codex_ui_visibility_proven": bool(
            ok and final.get("custom_codex_ui_visibility_proven") is True
        ),
        "handoff_payload_digest": (
            _hex_sha256(final.get("handoff_payload_digest")) if ok else ""
        ),
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
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": evidence_written,
        "file_mutation_attempted": evidence_written,
        "blocking_reasons": [] if ok else blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP reproduced the full runtime dispatch proof chain."
            if ok
            else "WBP blocked repeatable full runtime dispatch proof runner."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_full_runtime_dispatch_proof_runner_command(
    *,
    real_custom_hook_proof_file: str,
    working_flow_delivery_proof_file: str,
    codex_exec_jsonl_file: str,
    custom_codex_ui_visibility_proof_file: str,
    proof_dir: str,
    freshness_anchor_digest: str | None = None,
) -> dict[str, Any]:
    proof_root = Path(proof_dir).expanduser()
    input_paths = {
        "real_custom_hook_proof": Path(real_custom_hook_proof_file).expanduser(),
        "working_flow_delivery_proof": Path(working_flow_delivery_proof_file).expanduser(),
        "codex_exec_jsonl": Path(codex_exec_jsonl_file).expanduser(),
        "custom_codex_ui_visibility_proof": Path(
            custom_codex_ui_visibility_proof_file
        ).expanduser(),
    }
    metadata: dict[str, Any] = {
        "proof_dir_present": bool(proof_dir),
        "proof_dir_path_recorded": False,
    }
    metadata.update(_freshness_anchor_metadata(freshness_anchor_digest))
    for prefix, path in input_paths.items():
        metadata.update(_input_file_metadata(path, prefix=prefix))

    initial_input_failures = _input_failures(metadata, proof_dir=proof_dir)
    if proof_dir and not initial_input_failures:
        final_packet, packets_by_name, artifact_failures = _run_chain(
            real_custom_hook_proof_file=real_custom_hook_proof_file,
            working_flow_delivery_proof_file=working_flow_delivery_proof_file,
            codex_exec_jsonl_file=codex_exec_jsonl_file,
            custom_codex_ui_visibility_proof_file=custom_codex_ui_visibility_proof_file,
            proof_root=proof_root,
        )
    else:
        final_packet = {}
        packets_by_name = {}
        artifact_failures = []
    artifact_summaries: list[dict[str, Any]] = []
    if proof_dir:
        for name in _ARTIFACT_SEQUENCE:
            if name in (
                FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME,
                FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME,
            ):
                continue
            packet = packets_by_name.get(name, {})
            artifact_summaries.append(
                _packet_status_summary(name, packet, proof_root / name)
            )

    runner_machine_error_code = _machine_error_code(
        input_failures=_input_failures(metadata, proof_dir=proof_dir),
        unsafe_failures=_unsafe_failures(
            {FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME: final_packet}
        ),
        artifact_failures=artifact_failures,
        chain_failures=_artifact_status_failures(artifact_summaries)
        + _final_packet_failures(final_packet),
    )
    runner_status = (
        "ok"
        if runner_machine_error_code == FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK
        else "error"
    )
    manifest_packet = _build_manifest(
        input_metadata=metadata,
        artifact_summaries=artifact_summaries,
        final_packet=final_packet,
        runner_status=runner_status,
        runner_machine_error_code=runner_machine_error_code,
    )
    manifest_path = proof_root / FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME
    runner_path = proof_root / FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
    manifest_file_sha256 = ""
    try:
        if not proof_dir:
            raise OSError("proof_dir missing")
        proof_root.mkdir(parents=True, exist_ok=True)
        _write_artifact(manifest_path, manifest_packet)
        manifest_file_sha256 = _file_sha256(manifest_path)
    except (OSError, TypeError, ValueError):
        artifact_failures = sorted(
            set(list(artifact_failures) + ["runner_manifest_write_failed"])
        )

    runner_packet = build_full_runtime_dispatch_proof_runner_packet(
        input_metadata=metadata,
        artifact_summaries=artifact_summaries,
        artifact_packets=packets_by_name,
        final_packet=final_packet,
        manifest_packet=manifest_packet,
        manifest_file_sha256=manifest_file_sha256,
        manifest_file_written=bool(manifest_file_sha256),
        runner_packet_file_written=True,
        artifact_failures=artifact_failures,
    )
    try:
        if not proof_dir:
            raise OSError("proof_dir missing")
        proof_root.mkdir(parents=True, exist_ok=True)
        _write_artifact(runner_path, runner_packet)
    except (OSError, TypeError, ValueError):
        runner_packet = build_full_runtime_dispatch_proof_runner_packet(
            input_metadata=metadata,
            artifact_summaries=artifact_summaries,
            artifact_packets=packets_by_name,
            final_packet=final_packet,
            manifest_packet=manifest_packet,
            manifest_file_sha256=manifest_file_sha256,
            manifest_file_written=bool(manifest_file_sha256),
            runner_packet_file_written=False,
            artifact_failures=sorted(
                set(list(artifact_failures) + ["runner_packet_write_failed"])
            ),
        )
    return runner_packet
