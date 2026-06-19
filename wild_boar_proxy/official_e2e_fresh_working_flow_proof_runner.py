# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256
from .codex_working_flow_delivery_proof import (
    run_codex_working_flow_delivery_proof_command,
)
from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_approved_visible_source_observation import (
    VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
)
from .official_e2e_working_flow_proof_join import _read_json_mapping_file
from .official_e2e_working_flow_proof_runner import (
    OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND,
    OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND,
    _file_sha256,
    run_official_e2e_working_flow_proof_runner_command,
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
from .real_custom_codex_hook_proof import REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND
from .router_hook_entry import _safe_text


OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND = (
    "wbp_official_e2e_fresh_working_flow_proof_runner_inputs"
)
OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND = (
    "wbp_official_e2e_fresh_working_flow_proof_runner"
)

OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_OK = "OK"
OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID = (
    "WBP_OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID"
)
OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_STALE_REPLAY = (
    "WBP_OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_STALE_REPLAY"
)
OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE = (
    "WBP_OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE"
)
OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_ARTIFACT_WRITE_FAILED = (
    "WBP_OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_ARTIFACT_WRITE_FAILED"
)
OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_OFFICIAL_CHAIN_INVALID = (
    "WBP_OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_OFFICIAL_CHAIN_INVALID"
)

_INPUT_ALLOWED_FIELDS = {
    "schema_version",
    "packet_kind",
    "proof_run_id",
    "proof_run_started_at_ns",
    "real_custom_hook_proof_file",
    "codex_exec_jsonl_file",
    "expected_real_custom_hook_proof_file_sha256",
    "expected_codex_exec_jsonl_file_sha256",
}
_INPUT_RAW_OR_SECRET_FIELDS = {
    "prompt",
    "raw_prompt",
    "prompt_text",
    "natural_phrase",
    "task",
    "raw_task",
    "route_id",
    "raw_route_id",
    "selected_api_route_id",
    "route_candidate",
    "provider_response",
    "raw_provider_response",
    "provider_response_text",
    "provider_response_preview",
    "backend_details",
    "raw_backend_details",
    "api_key",
    "authorization",
    "bearer_token",
    "secret",
    "token",
}
_HOOK_REQUIRED_TRUE_FIELDS = (
    "hook_producer_ledger_proven",
    "user_prompt_submit_hook_ran",
    "hook_ledger_written",
    "hook_prompt_digest_bound",
    "hook_runtime_context_digest_bound",
    "thread_or_turn_digest_bound",
    "alias_context_read",
    "allowed_api_route_ids_enforced",
    "route_id_allowed",
    "api_lane_called",
    "dispatch_proven",
    "route_bound_dispatch_proven",
    "provider_response_proven",
    "live_provider_proven",
    "live_provider_response_proven",
    "external_live_provider_response_proven",
)
_HOOK_REQUIRED_FALSE_FIELDS = (
    "product_ready",
    "custom_codex_ui_visibility_proven",
    "native_free_chat_router_proven",
    "native_free_chat_router_product_ready",
    "native_free_chat_router_delivery_proven",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "codex_native_subagent_used_as_dip",
    "raw_prompt_recorded",
    "prompt_text_recorded",
    "natural_phrase_recorded",
    "route_candidate_recorded",
    "raw_route_id_recorded",
    "selected_api_route_id_recorded",
    "raw_provider_response_recorded",
    "provider_response_text_recorded",
    "provider_response_preview_recorded",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "state_written",
    "evidence_written",
    "file_mutation_attempted",
)
_HOOK_REQUIRED_DIGEST_FIELDS = (
    "prompt_digest",
    "runtime_context_digest",
    "hook_event_digest",
    "hook_session_digest",
    "selected_api_route_id_sha256",
    "route_bound_request_sha256",
    "live_provider_response_digest",
)
_ARTIFACT_NAMES = (
    "input-real-custom-hook-proof.packet.json",
    "working-flow-delivery-proof.packet.json",
    "official-working-flow-handoff-source.packet.json",
    "official-transcript-observation.packet.json",
    "official-assistant-continuation.packet.json",
    "official-approved-exec-source.packet.json",
    "official-delivery-candidate.packet.json",
    "official-working-flow-delivery-join.packet.json",
    "official-e2e-runner-inputs.packet.json",
    "official-e2e-runner.packet.json",
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _resolve_declared_file(*, inputs_file: Path, declared: object) -> str:
    if not isinstance(declared, str):
        return ""
    path = Path(declared).expanduser()
    if not path.is_absolute():
        path = inputs_file.parent / path
    return str(path)


def _file_mtime_ns(path: Path) -> int:
    try:
        if not path.exists() or not path.is_file():
            return 0
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def _file_metadata(
    path: Path,
    *,
    prefix: str,
    started_at_ns: int,
) -> dict[str, Any]:
    mtime_ns = _file_mtime_ns(path)
    return {
        f"{prefix}_file_present": path.exists() and path.is_file(),
        f"{prefix}_file_sha256": _file_sha256(path),
        f"{prefix}_file_mtime_ns": mtime_ns,
        f"{prefix}_file_created_after_start": bool(
            started_at_ns > 0 and mtime_ns >= started_at_ns
        ),
        f"{prefix}_file_path_recorded": False,
    }


def _proof_run_started_at_ns(inputs: Mapping[str, Any]) -> int:
    value = inputs.get("proof_run_started_at_ns")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _write_json_artifact(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps(dict(payload), ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _artifact_metadata(
    artifacts: Mapping[str, Path],
    *,
    started_at_ns: int,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "proof_artifact_file_paths_recorded": False,
        "proof_artifact_file_names": sorted(artifacts),
    }
    for name, path in artifacts.items():
        key = name.removesuffix(".packet.json").replace("-", "_")
        metadata[f"{key}_artifact_file_sha256"] = _file_sha256(path)
        metadata[f"{key}_artifact_file_mtime_ns"] = _file_mtime_ns(path)
        metadata[f"{key}_artifact_file_created_after_start"] = bool(
            _file_mtime_ns(path) >= started_at_ns > 0
        )
    return metadata


def _input_contract_failures(
    inputs: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if metadata.get("official_e2e_fresh_runner_inputs_file_read") is not True:
        failures.append("fresh_runner_inputs_file_not_read")
    if metadata.get("official_e2e_fresh_runner_inputs_file_valid_json") is not True:
        failures.append("fresh_runner_inputs_file_json_not_valid")
    if metadata.get("official_e2e_fresh_runner_inputs_file_mapping") is not True:
        failures.append("fresh_runner_inputs_file_not_mapping")
    if (
        inputs.get("packet_kind")
        != OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND
    ):
        failures.append("fresh_runner_inputs_packet_kind_invalid")
    if inputs.get("schema_version") != 1:
        failures.append("fresh_runner_inputs_schema_version_invalid")
    unknown_fields = sorted(set(inputs) - _INPUT_ALLOWED_FIELDS)
    if unknown_fields:
        failures.append("fresh_runner_inputs_unknown_fields")
    for key in _INPUT_RAW_OR_SECRET_FIELDS:
        if key in inputs:
            failures.append(f"fresh_runner_inputs_{key}_not_allowed")

    proof_run_id = inputs.get("proof_run_id")
    if not proof_run_id:
        failures.append("proof_run_id_missing")
    elif not packets.is_command_value_token(proof_run_id):
        failures.append("proof_run_id_not_machine_token")
    if not _proof_run_started_at_ns(inputs):
        failures.append("proof_run_started_at_ns_invalid")

    for field, prefix in (
        ("real_custom_hook_proof_file", "real_custom_hook_proof"),
        ("codex_exec_jsonl_file", "codex_exec_jsonl"),
    ):
        value = inputs.get(field)
        if not isinstance(value, str):
            failures.append(f"{field}_not_string")
        elif not value:
            failures.append(f"{field}_empty")
        if metadata.get(f"{prefix}_file_present") is not True:
            failures.append(f"{field}_missing")

    for field, reason in (
        (
            "expected_real_custom_hook_proof_file_sha256",
            "expected_real_custom_hook_proof_file_sha256",
        ),
        (
            "expected_codex_exec_jsonl_file_sha256",
            "expected_codex_exec_jsonl_file_sha256",
        ),
    ):
        expected_digest = inputs.get(field)
        if not expected_digest:
            failures.append(f"{reason}_missing")
        elif not _hex_sha256(expected_digest):
            failures.append(f"{reason}_invalid")

    expected_real_hook_sha = _hex_sha256(
        inputs.get("expected_real_custom_hook_proof_file_sha256")
    )
    observed_real_hook_sha = _hex_sha256(
        metadata.get("real_custom_hook_proof_file_sha256")
    )
    if expected_real_hook_sha and expected_real_hook_sha != observed_real_hook_sha:
        failures.append(
            "real_custom_hook_proof_file_sha256_not_bound_to_fresh_inputs"
        )
    expected_jsonl_sha = _hex_sha256(
        inputs.get("expected_codex_exec_jsonl_file_sha256")
    )
    observed_jsonl_sha = _hex_sha256(metadata.get("codex_exec_jsonl_file_sha256"))
    if expected_jsonl_sha and expected_jsonl_sha != observed_jsonl_sha:
        failures.append("codex_exec_jsonl_file_sha256_not_bound_to_fresh_inputs")
    return sorted(set(failures))


def _freshness_failures(metadata: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if metadata.get("real_custom_hook_proof_file_created_after_start") is not True:
        failures.append("real_custom_hook_proof_file_not_created_after_start")
    if metadata.get("codex_exec_jsonl_file_created_after_start") is not True:
        failures.append("codex_exec_jsonl_file_not_created_after_start")
    return sorted(set(failures))


def _real_hook_contract_failures(real_hook: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if real_hook.get("packet_kind") != REAL_CUSTOM_CODEX_HOOK_PROOF_PACKET_KIND:
        failures.append("real_custom_hook_packet_kind_invalid")
    if real_hook.get("status") != "ok":
        failures.append("real_custom_hook_packet_not_ok")
    if real_hook.get("machine_error_code") != "OK":
        failures.append("real_custom_hook_machine_error_not_ok")
    if real_hook.get("origin_state") != "custom_codex_flow_proven":
        failures.append("real_custom_hook_origin_state_not_custom_codex_flow_proven")
    for field in _HOOK_REQUIRED_TRUE_FIELDS:
        if real_hook.get(field) is not True:
            failures.append(f"real_custom_hook_{field}_not_true")
    for field in _HOOK_REQUIRED_FALSE_FIELDS:
        if real_hook.get(field) is True:
            failures.append(f"real_custom_hook_{field}_not_false")
    for field in _HOOK_REQUIRED_DIGEST_FIELDS:
        if not _hex_sha256(real_hook.get(field)):
            failures.append(f"real_custom_hook_{field}_missing")
    thread_digest = _hex_sha256(real_hook.get("hook_thread_digest"))
    turn_digest = _hex_sha256(real_hook.get("hook_turn_digest"))
    if not thread_digest and not turn_digest:
        failures.append("real_custom_hook_thread_or_turn_digest_missing")
    return sorted(set(failures))


def _input_unsafe_failures(
    inputs: Mapping[str, Any],
    real_hook: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None = None,
) -> list[str]:
    failures: list[str] = []
    for field in (
        "product_ready",
        "custom_codex_ui_visibility_proven",
        "native_free_chat_router_proven",
        "native_free_chat_router_product_ready",
    ):
        if inputs.get(field) is True:
            failures.append(f"fresh_runner_inputs_{field}_claim")
    secret_list = list(secret_values or [])
    if packets.command_packet_has_secret_leak(inputs, secret_values=secret_list):
        failures.append("fresh_runner_inputs_secret_material_present")
    if packets.command_packet_has_secret_leak(real_hook, secret_values=secret_list):
        failures.append("real_custom_hook_secret_material_present")
    return sorted(set(failures))


def _official_runner_failures(
    official_runner_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if (
        official_runner_packet.get("packet_kind")
        != OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND
    ):
        failures.append("official_e2e_runner_packet_kind_invalid")
    if official_runner_packet.get("status") != "ok":
        failures.append("official_e2e_runner_packet_not_ok")
    if official_runner_packet.get("machine_error_code") != "OK":
        failures.append("official_e2e_runner_machine_error_not_ok")
    if official_runner_packet.get("official_e2e_working_flow_proven") is not True:
        failures.append("official_e2e_runner_working_flow_not_proven")
    if official_runner_packet.get("official_e2e_join_valid") is not True:
        failures.append("official_e2e_runner_join_not_valid")
    return sorted(set(failures))


def _machine_error_code(
    *,
    unsafe_failures: Sequence[str],
    input_failures: Sequence[str],
    freshness_failures: Sequence[str],
    hook_failures: Sequence[str],
    artifact_failures: Sequence[str],
    official_runner_failures: Sequence[str],
) -> str:
    if unsafe_failures:
        return OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_UNSAFE_SOURCE
    if input_failures or hook_failures:
        return OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUT_INVALID
    if freshness_failures:
        return OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_STALE_REPLAY
    if artifact_failures:
        return OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_ARTIFACT_WRITE_FAILED
    if official_runner_failures:
        return OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_OFFICIAL_CHAIN_INVALID
    return OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_OK


def _run_official_chain(
    *,
    real_custom_hook_packet: Mapping[str, Any],
    real_custom_hook_proof_file: str,
    codex_exec_jsonl_file: str,
    proof_output_dir: Path,
    proof_run_id: str,
    started_at_ns: int,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    artifacts: dict[str, Path] = {
        name: proof_output_dir / name for name in _ARTIFACT_NAMES
    }
    artifact_failures: list[str] = []
    official_runner_packet: dict[str, Any] = {}
    try:
        proof_output_dir.mkdir(parents=True, exist_ok=True)

        real_hook_snapshot = artifacts["input-real-custom-hook-proof.packet.json"]
        _write_json_artifact(real_hook_snapshot, real_custom_hook_packet)

        working_flow_packet = run_codex_working_flow_delivery_proof_command(
            integrated_live_provider_proof_file=real_custom_hook_proof_file,
            codex_exec_jsonl_file=codex_exec_jsonl_file,
        )
        _write_json_artifact(
            artifacts["working-flow-delivery-proof.packet.json"],
            working_flow_packet,
        )

        handoff_source_packet = (
            run_official_mcp_working_flow_handoff_source_proof_command(
                working_flow_delivery_proof_file=str(
                    artifacts["working-flow-delivery-proof.packet.json"]
                ),
            )
        )
        _write_json_artifact(
            artifacts["official-working-flow-handoff-source.packet.json"],
            handoff_source_packet,
        )

        transcript_observation_packet = (
            run_official_mcp_transcript_tool_result_observation_command(
                handoff_source_file=str(
                    artifacts["official-working-flow-handoff-source.packet.json"]
                ),
                codex_exec_jsonl_file=codex_exec_jsonl_file,
            )
        )
        _write_json_artifact(
            artifacts["official-transcript-observation.packet.json"],
            transcript_observation_packet,
        )

        assistant_continuation_packet = (
            run_official_mcp_assistant_continuation_observation_command(
                transcript_observation_file=str(
                    artifacts["official-transcript-observation.packet.json"]
                ),
                codex_exec_jsonl_file=codex_exec_jsonl_file,
            )
        )
        _write_json_artifact(
            artifacts["official-assistant-continuation.packet.json"],
            assistant_continuation_packet,
        )

        approved_exec_source_packet = (
            run_official_mcp_approved_codex_exec_source_observation_command(
                assistant_continuation_observation_file=str(
                    artifacts["official-assistant-continuation.packet.json"]
                ),
                approved_source_kind=VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
                codex_exec_jsonl_file=codex_exec_jsonl_file,
            )
        )
        _write_json_artifact(
            artifacts["official-approved-exec-source.packet.json"],
            approved_exec_source_packet,
        )

        delivery_candidate_packet = run_official_mcp_delivery_candidate_join_command(
            approved_exec_source_observation_file=str(
                artifacts["official-approved-exec-source.packet.json"]
            ),
        )
        _write_json_artifact(
            artifacts["official-delivery-candidate.packet.json"],
            delivery_candidate_packet,
        )

        delivery_join_packet = run_official_mcp_working_flow_delivery_join_command(
            delivery_candidate_file=str(
                artifacts["official-delivery-candidate.packet.json"]
            ),
            working_flow_delivery_proof_file=str(
                artifacts["working-flow-delivery-proof.packet.json"]
            ),
        )
        _write_json_artifact(
            artifacts["official-working-flow-delivery-join.packet.json"],
            delivery_join_packet,
        )

        official_runner_inputs = {
            "schema_version": 1,
            "packet_kind": OFFICIAL_E2E_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND,
            "proof_run_id": proof_run_id,
            "real_custom_hook_proof_file": real_hook_snapshot.name,
            "official_working_flow_delivery_join_file": (
                artifacts["official-working-flow-delivery-join.packet.json"].name
            ),
            "expected_real_custom_hook_proof_file_sha256": _file_sha256(
                real_hook_snapshot
            ),
            "expected_official_working_flow_delivery_join_file_sha256": _file_sha256(
                artifacts["official-working-flow-delivery-join.packet.json"]
            ),
        }
        _write_json_artifact(
            artifacts["official-e2e-runner-inputs.packet.json"],
            official_runner_inputs,
        )

        official_runner_packet = run_official_e2e_working_flow_proof_runner_command(
            inputs_file=str(artifacts["official-e2e-runner-inputs.packet.json"]),
        )
        _write_json_artifact(
            artifacts["official-e2e-runner.packet.json"],
            official_runner_packet,
        )
    except (OSError, ValueError, TypeError):
        artifact_failures.append("official_chain_artifact_write_failed")

    metadata = _artifact_metadata(artifacts, started_at_ns=started_at_ns)
    metadata["proof_output_dir_path_recorded"] = False
    metadata["proof_output_dir_artifacts_written"] = bool(
        not artifact_failures and all(path.exists() for path in artifacts.values())
    )
    metadata["official_chain_artifact_write_failures"] = sorted(set(artifact_failures))
    metadata["real_custom_hook_snapshot_sha256_matches_source"] = bool(
        _hex_sha256(metadata.get("input_real_custom_hook_proof_artifact_file_sha256"))
        == _hex_sha256(_file_sha256(Path(real_custom_hook_proof_file)))
    )
    return official_runner_packet, metadata, sorted(set(artifact_failures))


def build_official_e2e_fresh_working_flow_proof_runner_packet(
    *,
    fresh_runner_inputs_packet: Mapping[str, Any] | None,
    real_custom_hook_proof_packet: Mapping[str, Any] | None,
    official_e2e_runner_packet: Mapping[str, Any] | None,
    file_metadata: Mapping[str, Any] | None = None,
    artifact_metadata: Mapping[str, Any] | None = None,
    artifact_failures: Sequence[str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    inputs = _mapping(fresh_runner_inputs_packet)
    real_hook = _mapping(real_custom_hook_proof_packet)
    official_runner = _mapping(official_e2e_runner_packet)
    metadata = {**dict(file_metadata or {}), **dict(artifact_metadata or {})}

    input_failures = _input_contract_failures(inputs, metadata)
    freshness_failures = (
        [] if input_failures else _freshness_failures(metadata)
    )
    hook_failures = (
        []
        if input_failures or freshness_failures
        else _real_hook_contract_failures(real_hook)
    )
    unsafe_failures = _input_unsafe_failures(
        inputs,
        real_hook,
        secret_values=secret_values,
    )
    write_failures = sorted(set(artifact_failures or []))
    official_failures = (
        []
        if input_failures
        or freshness_failures
        or hook_failures
        or unsafe_failures
        or write_failures
        else _official_runner_failures(official_runner)
    )
    blocking_reasons = sorted(
        set(
            input_failures
            + freshness_failures
            + hook_failures
            + unsafe_failures
            + write_failures
            + official_failures
            + _safe_reasons(official_runner.get("blocking_reasons"))
        )
    )
    ok = not blocking_reasons
    machine_error_code = _machine_error_code(
        unsafe_failures=unsafe_failures,
        input_failures=input_failures,
        freshness_failures=freshness_failures,
        hook_failures=hook_failures,
        artifact_failures=write_failures,
        official_runner_failures=official_failures,
    )
    proof_run_id = _safe_text(inputs.get("proof_run_id"), limit=96)
    started_at_ns = _proof_run_started_at_ns(inputs)
    expected_real_hook_sha = _hex_sha256(
        inputs.get("expected_real_custom_hook_proof_file_sha256")
    )
    observed_real_hook_sha = _hex_sha256(
        metadata.get("real_custom_hook_proof_file_sha256")
    )
    expected_jsonl_sha = _hex_sha256(inputs.get("expected_codex_exec_jsonl_file_sha256"))
    observed_jsonl_sha = _hex_sha256(metadata.get("codex_exec_jsonl_file_sha256"))

    extra = {
        **metadata,
        "schema_version": 1,
        "packet_kind": OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_PACKET_KIND,
        "proof_scope": "fresh_official_e2e_working_flow_proof_runner",
        "proof_run_id": proof_run_id if packets.is_command_value_token(proof_run_id) else "",
        "proof_run_started_at_ns": started_at_ns,
        "proof_run_started_at_ns_bound": bool(
            started_at_ns
            and metadata.get("real_custom_hook_proof_file_created_after_start") is True
            and metadata.get("codex_exec_jsonl_file_created_after_start") is True
        ),
        "fresh_runner_inputs_packet_kind": _safe_text(
            inputs.get("packet_kind"),
            limit=96,
        ),
        "fresh_runner_inputs_schema_version": inputs.get("schema_version")
        if isinstance(inputs.get("schema_version"), int)
        and not isinstance(inputs.get("schema_version"), bool)
        else 0,
        "fresh_runner_inputs_valid": not input_failures,
        "fresh_runner_input_failures": input_failures,
        "freshness_failures": freshness_failures,
        "fresh_inputs_created_after_start": bool(
            not freshness_failures and not input_failures and started_at_ns
        ),
        "expected_real_custom_hook_proof_file_sha256": expected_real_hook_sha,
        "observed_real_custom_hook_proof_file_sha256": observed_real_hook_sha,
        "real_custom_hook_proof_file_sha256_bound_to_fresh_inputs": bool(
            not input_failures
            and expected_real_hook_sha
            and observed_real_hook_sha
            and expected_real_hook_sha == observed_real_hook_sha
        ),
        "expected_codex_exec_jsonl_file_sha256": expected_jsonl_sha,
        "observed_codex_exec_jsonl_file_sha256": observed_jsonl_sha,
        "codex_exec_jsonl_file_sha256_bound_to_fresh_inputs": bool(
            not input_failures
            and expected_jsonl_sha
            and observed_jsonl_sha
            and expected_jsonl_sha == observed_jsonl_sha
        ),
        "real_custom_hook_contract_valid": not hook_failures
        and not input_failures
        and not freshness_failures,
        "real_custom_hook_failures": hook_failures,
        "real_custom_hook_packet_kind": _safe_text(
            real_hook.get("packet_kind"),
            limit=96,
        ),
        "hook_event_digest": _hex_sha256(real_hook.get("hook_event_digest")),
        "hook_session_digest": _hex_sha256(real_hook.get("hook_session_digest")),
        "hook_thread_digest": _hex_sha256(real_hook.get("hook_thread_digest")),
        "hook_turn_digest": _hex_sha256(real_hook.get("hook_turn_digest")),
        "prompt_digest": _hex_sha256(real_hook.get("prompt_digest")),
        "runtime_context_digest": _hex_sha256(real_hook.get("runtime_context_digest")),
        "hook_event_digest_bound": bool(
            ok and _hex_sha256(real_hook.get("hook_event_digest"))
        ),
        "hook_session_digest_bound": bool(
            ok and _hex_sha256(real_hook.get("hook_session_digest"))
        ),
        "hook_thread_or_turn_digest_bound": bool(
            ok
            and (
                _hex_sha256(real_hook.get("hook_thread_digest"))
                or _hex_sha256(real_hook.get("hook_turn_digest"))
            )
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and real_hook.get("hook_runtime_context_digest_bound") is True
        ),
        "fresh_runner_unsafe_failures": unsafe_failures,
        "official_chain_artifacts_written": bool(
            metadata.get("proof_output_dir_artifacts_written") is True
        ),
        "official_chain_artifact_failures": write_failures,
        "official_e2e_runner_packet_kind": _safe_text(
            official_runner.get("packet_kind"),
            limit=96,
        ),
        "official_e2e_runner_status": _safe_text(
            official_runner.get("status"),
            limit=32,
        ),
        "official_e2e_runner_machine_error_code": _safe_text(
            official_runner.get("machine_error_code"),
            limit=96,
        ),
        "official_e2e_runner_valid": not official_failures
        and not input_failures
        and not freshness_failures
        and not hook_failures
        and not unsafe_failures
        and not write_failures,
        "official_e2e_runner_failures": official_failures,
        "fresh_e2e_working_flow_proven": bool(
            ok and official_runner.get("official_e2e_working_flow_proven") is True
        ),
        "official_e2e_working_flow_proven": bool(
            ok and official_runner.get("official_e2e_working_flow_proven") is True
        ),
        "custom_codex_hook_to_official_working_flow_bound": bool(
            ok
            and official_runner.get("custom_codex_hook_to_official_working_flow_bound")
            is True
        ),
        "custom_codex_flow_origin_proven": bool(
            ok and official_runner.get("custom_codex_flow_origin_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and official_runner.get("user_prompt_submit_hook_ran") is True
        ),
        "api_lane_called": bool(ok and official_runner.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and official_runner.get("dispatch_proven") is True),
        "live_provider_response_proven": bool(
            ok and official_runner.get("live_provider_response_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and official_runner.get("codex_working_flow_delivery_proven") is True
        ),
        "official_delivery_candidate_lineage_proven": bool(
            ok
            and official_runner.get("official_delivery_candidate_lineage_proven")
            is True
        ),
        "official_observation_lineage_file_backed": bool(
            ok and official_runner.get("official_observation_lineage_file_backed") is True
        ),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
        "native_free_chat_router_delivery_proven": False,
        "product_ready": False,
        "does_not_prove_custom_codex_ui": True,
        "does_not_prove_native_free_chat_router": True,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "raw_jsonl_recorded": False,
        "raw_prompt_recorded": False,
        "raw_task_recorded": False,
        "tool_call_arguments_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
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
        "runtime_effective_truth_written": False,
        "evidence_written": bool(
            metadata.get("proof_output_dir_artifacts_written") is True
        ),
        "file_mutation_attempted": bool(
            metadata.get("proof_output_dir_artifacts_written") is True
        ),
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP ran a fresh file-backed official E2E working-flow proof."
            if ok
            else "WBP blocked fresh official E2E working-flow proof runner."
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


def run_official_e2e_fresh_working_flow_proof_runner_command(
    *,
    inputs_file: str,
    proof_output_dir: str,
) -> dict[str, Any]:
    inputs_path = Path(inputs_file).expanduser()
    inputs_packet, inputs_metadata = _read_json_mapping_file(
        inputs_path,
        prefix="official_e2e_fresh_runner_inputs",
    )
    started_at_ns = _proof_run_started_at_ns(inputs_packet)
    real_custom_hook_path = _resolve_declared_file(
        inputs_file=inputs_path,
        declared=inputs_packet.get("real_custom_hook_proof_file"),
    )
    codex_exec_jsonl_path = _resolve_declared_file(
        inputs_file=inputs_path,
        declared=inputs_packet.get("codex_exec_jsonl_file"),
    )
    real_hook_packet, real_hook_metadata = _read_json_mapping_file(
        Path(real_custom_hook_path) if real_custom_hook_path else Path(""),
        prefix="real_custom_hook_proof",
    )
    metadata = {
        **inputs_metadata,
        **real_hook_metadata,
        "official_e2e_fresh_runner_inputs_file_sha256": _file_sha256(inputs_path),
        **(
            _file_metadata(
                Path(real_custom_hook_path),
                prefix="real_custom_hook_proof",
                started_at_ns=started_at_ns,
            )
            if real_custom_hook_path
            else {}
        ),
        **(
            _file_metadata(
                Path(codex_exec_jsonl_path),
                prefix="codex_exec_jsonl",
                started_at_ns=started_at_ns,
            )
            if codex_exec_jsonl_path
            else {}
        ),
    }
    input_failures = _input_contract_failures(inputs_packet, metadata)
    freshness_failures = [] if input_failures else _freshness_failures(metadata)
    hook_failures = (
        []
        if input_failures or freshness_failures
        else _real_hook_contract_failures(real_hook_packet)
    )
    unsafe_failures = _input_unsafe_failures(inputs_packet, real_hook_packet)

    official_runner_packet: dict[str, Any] = {}
    artifact_metadata: dict[str, Any] = {}
    artifact_failures: list[str] = []
    if not input_failures and not freshness_failures and not hook_failures and not unsafe_failures:
        official_runner_packet, artifact_metadata, artifact_failures = _run_official_chain(
            real_custom_hook_packet=real_hook_packet,
            real_custom_hook_proof_file=real_custom_hook_path,
            codex_exec_jsonl_file=codex_exec_jsonl_path,
            proof_output_dir=Path(proof_output_dir).expanduser(),
            proof_run_id=_safe_text(inputs_packet.get("proof_run_id"), limit=96),
            started_at_ns=started_at_ns,
        )

    return build_official_e2e_fresh_working_flow_proof_runner_packet(
        fresh_runner_inputs_packet=inputs_packet,
        real_custom_hook_proof_packet=real_hook_packet,
        official_e2e_runner_packet=official_runner_packet,
        file_metadata=metadata,
        artifact_metadata=artifact_metadata,
        artifact_failures=artifact_failures,
    )
