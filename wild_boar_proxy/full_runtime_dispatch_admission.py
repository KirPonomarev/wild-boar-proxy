# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from .codex_transcript_delivery_observation import _hex_sha256
from .command_effects import EFFECT_MUTATE, EFFECT_PROBE, EFFECT_READ
from .core import packets
from .full_runtime_dispatch_proof import (
    FULL_RUNTIME_DISPATCH_OK,
    FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND,
)
from .full_runtime_dispatch_proof_runner import (
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_PACKET_KIND,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_PACKET_KIND,
)
from .router_hook_entry import _safe_text


FULL_RUNTIME_DISPATCH_ADMISSION_PACKET_KIND = "wbp_full_runtime_dispatch_admission"

FULL_RUNTIME_DISPATCH_ADMISSION_OK = "OK"
FULL_RUNTIME_DISPATCH_ADMISSION_INPUT_INVALID = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_INPUT_INVALID"
)
FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID"
)
FULL_RUNTIME_DISPATCH_ADMISSION_UNSAFE_SOURCE = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_UNSAFE_SOURCE"
)
FULL_RUNTIME_DISPATCH_ADMISSION_NOT_PROVEN = (
    "WBP_FULL_RUNTIME_DISPATCH_ADMISSION_NOT_PROVEN"
)

_FIXED_PROOF_FILES = (
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME,
    FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME,
)
_RUNNER_REQUIRED_TRUE_FIELDS = (
    "full_runtime_dispatch_runner_proven",
    "full_runtime_dispatch_proven",
    "custom_codex_flow_proven",
    "user_prompt_submit_hook_ran",
    "api_lane_called",
    "dispatch_proven",
    "codex_working_flow_delivery_proven",
    "custom_codex_ui_visibility_proven",
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
    "state_written",
)
_FINAL_REQUIRED_FALSE_FIELDS = _REQUIRED_FALSE_FIELDS + (
    "evidence_written",
    "file_mutation_attempted",
)
_MANIFEST_REQUIRED_FALSE_FIELDS = (
    "product_ready",
    "fallback_used",
    "local_imitation_used",
    "native_codex_subagent_used_as_dip",
    "raw_prompt_recorded",
    "raw_route_id_recorded",
    "raw_provider_response_recorded",
    "raw_dom_exposed",
    "raw_ax_tree_exposed",
    "raw_backend_details_exposed",
    "secret_value_exposed",
    "roadmap_recorded",
    "future_plan_recorded",
    "next_contour_recorded",
)


def _mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _safe_reasons(value: object) -> list[str]:
    reasons: set[str] = set()
    for item in _sequence(value):
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


def _read_json_mapping_file(
    path: Path,
    *,
    prefix: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        f"{prefix}_file_present": path.exists() and path.is_file(),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_sha256": _file_sha256(path),
        f"{prefix}_file_path_recorded": False,
        f"{prefix}_file_error_code": "",
    }
    if not metadata[f"{prefix}_file_present"]:
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata


def _safe_artifact_name(value: object) -> str:
    name = _safe_text(value, limit=128)
    if not name or name != Path(name).name or "/" in name or "\\" in name:
        return ""
    if not name.endswith(".json"):
        return ""
    return name


def _summary_map(value: object) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    summaries: dict[str, Mapping[str, Any]] = {}
    failures: list[str] = []
    for index, item in enumerate(_sequence(value), start=1):
        if not isinstance(item, Mapping):
            failures.append(f"artifact_summary_{index}_not_mapping")
            continue
        name = _safe_artifact_name(item.get("artifact_name") or item.get("name"))
        if not name:
            failures.append(f"artifact_summary_{index}_name_invalid")
            continue
        if name in summaries:
            failures.append(f"{name}_duplicate_summary")
            continue
        summaries[name] = item
    return summaries, sorted(set(failures))


def _input_failures(metadata: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    if metadata.get("proof_dir_present") is not True:
        failures.append("proof_dir_missing")
    if metadata.get("proof_dir_is_dir") is not True:
        failures.append("proof_dir_not_directory")
    for prefix in ("runner_packet", "manifest", "final_full_runtime"):
        if metadata.get(f"{prefix}_file_present") is not True:
            failures.append(f"{prefix}_file_missing")
        if metadata.get(f"{prefix}_file_valid_json") is not True:
            failures.append(f"{prefix}_file_json_invalid")
        if metadata.get(f"{prefix}_file_mapping") is not True:
            failures.append(f"{prefix}_file_not_mapping")
        if not _hex_sha256(metadata.get(f"{prefix}_file_sha256")):
            failures.append(f"{prefix}_file_sha256_missing")
        if metadata.get(f"{prefix}_file_path_recorded") is not False:
            failures.append(f"{prefix}_file_path_recorded")
    return sorted(set(failures))


def _required_true_failures(
    packet: Mapping[str, Any],
    fields: Sequence[str],
    *,
    prefix: str,
) -> list[str]:
    return [
        f"{prefix}_{field}_not_true"
        for field in fields
        if packet.get(field) is not True
    ]


def _required_false_failures(
    packet: Mapping[str, Any],
    fields: Sequence[str],
    *,
    prefix: str,
) -> list[str]:
    return [
        f"{prefix}_{field}_not_false"
        for field in fields
        if packet.get(field) is not False
    ]


def _proof_failures(
    *,
    runner_packet: Mapping[str, Any],
    manifest_packet: Mapping[str, Any],
    final_packet: Mapping[str, Any],
) -> list[str]:
    failures: list[str] = []
    if runner_packet.get("packet_kind") != FULL_RUNTIME_DISPATCH_PROOF_RUNNER_PACKET_KIND:
        failures.append("runner_packet_kind_invalid")
    if runner_packet.get("status") != "ok":
        failures.append("runner_status_not_ok")
    if runner_packet.get("machine_error_code") != FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK:
        failures.append("runner_machine_error_not_ok")
    if runner_packet.get("effect") != EFFECT_MUTATE:
        failures.append("runner_effect_not_mutate")
    failures.extend(
        _required_true_failures(
            runner_packet,
            _RUNNER_REQUIRED_TRUE_FIELDS,
            prefix="runner",
        )
    )
    failures.extend(
        _required_false_failures(
            runner_packet,
            _REQUIRED_FALSE_FIELDS,
            prefix="runner",
        )
    )
    if runner_packet.get("runner_inputs_valid") is not True:
        failures.append("runner_inputs_not_valid")
    if runner_packet.get("manifest_file_written") is not True:
        failures.append("runner_manifest_file_not_written")
    if runner_packet.get("runner_packet_file_written") is not True:
        failures.append("runner_packet_file_not_written")
    if runner_packet.get("evidence_written") is not True:
        failures.append("runner_evidence_not_written")
    if runner_packet.get("file_mutation_attempted") is not True:
        failures.append("runner_file_mutation_not_recorded")
    if _sequence(runner_packet.get("blocking_reasons")):
        failures.append("runner_blocking_reasons_not_empty")

    if (
        manifest_packet.get("packet_kind")
        != FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_PACKET_KIND
    ):
        failures.append("manifest_packet_kind_invalid")
    if manifest_packet.get("final_status") != "ok":
        failures.append("manifest_final_status_not_ok")
    if manifest_packet.get("final_machine_error_code") != FULL_RUNTIME_DISPATCH_OK:
        failures.append("manifest_final_machine_error_not_ok")
    if manifest_packet.get("final_full_runtime_dispatch_proven") is not True:
        failures.append("manifest_final_full_runtime_dispatch_not_proven")
    if manifest_packet.get("runner_status") != "ok":
        failures.append("manifest_runner_status_not_ok")
    if manifest_packet.get("runner_machine_error_code") != FULL_RUNTIME_DISPATCH_PROOF_RUNNER_OK:
        failures.append("manifest_runner_machine_error_not_ok")
    failures.extend(
        _required_false_failures(
            manifest_packet,
            _MANIFEST_REQUIRED_FALSE_FIELDS,
            prefix="manifest",
        )
    )

    if final_packet.get("packet_kind") != FULL_RUNTIME_DISPATCH_PROOF_PACKET_KIND:
        failures.append("final_full_runtime_packet_kind_invalid")
    if final_packet.get("status") != "ok":
        failures.append("final_full_runtime_status_not_ok")
    if final_packet.get("machine_error_code") != FULL_RUNTIME_DISPATCH_OK:
        failures.append("final_full_runtime_machine_error_not_ok")
    if final_packet.get("effect") != EFFECT_PROBE:
        failures.append("final_full_runtime_effect_not_probe")
    failures.extend(
        _required_true_failures(
            final_packet,
            _FINAL_REQUIRED_TRUE_FIELDS,
            prefix="final",
        )
    )
    failures.extend(
        _required_false_failures(
            final_packet,
            _FINAL_REQUIRED_FALSE_FIELDS,
            prefix="final",
        )
    )
    if _sequence(final_packet.get("blocking_reasons")):
        failures.append("final_blocking_reasons_not_empty")
    if not _hex_sha256(final_packet.get("handoff_payload_digest")):
        failures.append("final_handoff_payload_digest_missing")
    return sorted(set(failures))


def _walk_path_recording_failures(
    payload: object,
    *,
    prefix: str,
    key_path: str = "",
) -> list[str]:
    failures: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_text = _safe_text(key, limit=96)
            nested_key = f"{key_path}_{key_text}" if key_path else key_text
            normalized = key_text.lower()
            if (
                normalized.endswith("_path_recorded")
                or normalized.endswith("_paths_recorded")
            ) and value is True:
                failures.append(f"{prefix}_{nested_key}_unsafe")
            failures.extend(
                _walk_path_recording_failures(
                    value,
                    prefix=prefix,
                    key_path=nested_key,
                )
            )
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for index, item in enumerate(payload, start=1):
            failures.extend(
                _walk_path_recording_failures(
                    item,
                    prefix=prefix,
                    key_path=f"{key_path}_{index}" if key_path else str(index),
                )
            )
    return failures


def _unsafe_failures(
    packets_by_name: Mapping[str, Mapping[str, Any]],
    *,
    secret_values: Sequence[str] | None = None,
) -> list[str]:
    failures: list[str] = []
    for name, packet in packets_by_name.items():
        safe_name = name.removesuffix(".packet.json").removesuffix(".json").replace(
            "-",
            "_",
        )
        for field in _REQUIRED_FALSE_FIELDS:
            if packet.get(field) is True:
                failures.append(f"{safe_name}_{field}_unsafe")
        if packet.get("runtime_effective_truth_written") is True:
            failures.append(f"{safe_name}_runtime_effective_truth_written_unsafe")
        failures.extend(_walk_path_recording_failures(packet, prefix=safe_name))
        if packets.command_packet_has_secret_leak(packet, secret_values=list(secret_values or [])):
            failures.append(f"{safe_name}_secret_material_present")
    return sorted(set(failures))


def _coherence_failures(
    *,
    proof_root: Path,
    metadata: Mapping[str, Any],
    runner_packet: Mapping[str, Any],
    manifest_packet: Mapping[str, Any],
    final_packet: Mapping[str, Any],
    artifact_packets: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    failures: list[str] = []
    if runner_packet.get("manifest_packet_kind") != manifest_packet.get("packet_kind"):
        failures.append("runner_manifest_packet_kind_mismatch")
    if (
        _hex_sha256(runner_packet.get("manifest_file_sha256"))
        != metadata.get("manifest_file_sha256")
    ):
        failures.append("manifest_file_sha256_mismatch")
    if (
        manifest_packet.get("final_status") != final_packet.get("status")
        or manifest_packet.get("final_machine_error_code")
        != final_packet.get("machine_error_code")
    ):
        failures.append("manifest_final_status_mismatch")
    if (
        _hex_sha256(manifest_packet.get("final_handoff_payload_digest"))
        != _hex_sha256(final_packet.get("handoff_payload_digest"))
    ):
        failures.append("manifest_final_handoff_payload_digest_mismatch")
    if (
        _hex_sha256(runner_packet.get("handoff_payload_digest"))
        != _hex_sha256(final_packet.get("handoff_payload_digest"))
    ):
        failures.append("runner_final_handoff_payload_digest_mismatch")

    runner_summaries, runner_summary_failures = _summary_map(
        runner_packet.get("artifact_summaries")
    )
    manifest_summaries, manifest_summary_failures = _summary_map(
        manifest_packet.get("artifacts")
    )
    failures.extend(runner_summary_failures)
    failures.extend(manifest_summary_failures)
    runner_names = [_safe_artifact_name(name) for name in _sequence(runner_packet.get("artifact_file_names"))]
    if not runner_names or any(not name for name in runner_names):
        failures.append("runner_artifact_file_names_invalid")
    if runner_names != list(runner_summaries):
        failures.append("runner_artifact_file_names_summary_mismatch")
    if list(runner_summaries) != list(manifest_summaries):
        failures.append("manifest_artifact_names_mismatch")
    if FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME not in runner_summaries:
        failures.append("final_full_runtime_artifact_summary_missing")

    for name, runner_summary in runner_summaries.items():
        manifest_summary = manifest_summaries.get(name)
        if manifest_summary is None:
            failures.append(f"{name}_manifest_summary_missing")
            continue
        artifact_path = proof_root / name
        if artifact_path.parent != proof_root:
            failures.append(f"{name}_artifact_path_not_direct_child")
        if not artifact_path.exists() or not artifact_path.is_file():
            failures.append(f"{name}_artifact_file_missing")
            continue
        actual_sha = _file_sha256(artifact_path)
        runner_sha = _hex_sha256(runner_summary.get("file_sha256"))
        manifest_sha = _hex_sha256(manifest_summary.get("file_sha256"))
        if not actual_sha or actual_sha != runner_sha:
            failures.append(f"{name}_runner_file_sha256_mismatch")
        if not actual_sha or actual_sha != manifest_sha:
            failures.append(f"{name}_manifest_file_sha256_mismatch")
        if runner_sha != manifest_sha:
            failures.append(f"{name}_summary_sha256_mismatch")
        artifact_packet = artifact_packets.get(name, {})
        for summary_prefix, summary in (
            ("runner", runner_summary),
            ("manifest", manifest_summary),
        ):
            if summary.get("status") != artifact_packet.get("status"):
                failures.append(f"{name}_{summary_prefix}_status_mismatch")
            if summary.get("machine_error_code") != artifact_packet.get(
                "machine_error_code"
            ):
                failures.append(f"{name}_{summary_prefix}_machine_error_mismatch")
            packet_kind = _safe_text(summary.get("packet_kind"), limit=96)
            if packet_kind and packet_kind != artifact_packet.get("packet_kind"):
                failures.append(f"{name}_{summary_prefix}_packet_kind_mismatch")
            if summary.get("file_path_recorded") is not False:
                failures.append(f"{name}_{summary_prefix}_file_path_recorded")
    return sorted(set(failures))


def _machine_error_code(
    *,
    input_failures: Sequence[str],
    coherence_failures: Sequence[str],
    unsafe_failures: Sequence[str],
    proof_failures: Sequence[str],
) -> str:
    if unsafe_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_UNSAFE_SOURCE
    if input_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_INPUT_INVALID
    if coherence_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_COHERENCE_INVALID
    if proof_failures:
        return FULL_RUNTIME_DISPATCH_ADMISSION_NOT_PROVEN
    return FULL_RUNTIME_DISPATCH_ADMISSION_OK


def build_full_runtime_dispatch_admission_packet(
    *,
    proof_dir: str,
    metadata: Mapping[str, Any] | None,
    runner_packet: Mapping[str, Any] | None,
    manifest_packet: Mapping[str, Any] | None,
    final_packet: Mapping[str, Any] | None,
    artifact_packets: Mapping[str, Mapping[str, Any]] | None,
    input_failures: Sequence[str] | None = None,
    coherence_failures: Sequence[str] | None = None,
    proof_failures: Sequence[str] | None = None,
    unsafe_failures: Sequence[str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    metadata_dict = dict(metadata or {})
    runner = _mapping(runner_packet)
    manifest = _mapping(manifest_packet)
    final = _mapping(final_packet)
    artifacts = dict(artifact_packets or {})
    input_failure_list = sorted(set(input_failures or []))
    coherence_failure_list = sorted(set(coherence_failures or []))
    proof_failure_list = sorted(set(proof_failures or []))
    unsafe_failure_list = sorted(set(unsafe_failures or []))
    machine_error_code = _machine_error_code(
        input_failures=input_failure_list,
        coherence_failures=coherence_failure_list,
        unsafe_failures=unsafe_failure_list,
        proof_failures=proof_failure_list,
    )
    ok = machine_error_code == FULL_RUNTIME_DISPATCH_ADMISSION_OK
    blocking_reasons = sorted(
        set(
            input_failure_list
            + coherence_failure_list
            + unsafe_failure_list
            + proof_failure_list
            + _safe_reasons(runner.get("blocking_reasons"))
            + _safe_reasons(final.get("blocking_reasons"))
        )
    )
    artifact_names = sorted(artifacts)
    extra = {
        **metadata_dict,
        "schema_version": 1,
        "packet_kind": FULL_RUNTIME_DISPATCH_ADMISSION_PACKET_KIND,
        "proof_scope": "full_runtime_dispatch_proof_dir_admission_gate_only",
        "proof_dir_path_recorded": False,
        "runner_packet_present": metadata_dict.get("runner_packet_file_present") is True,
        "manifest_present": metadata_dict.get("manifest_file_present") is True,
        "final_full_runtime_packet_present": (
            metadata_dict.get("final_full_runtime_file_present") is True
        ),
        "runner_packet_sha256": _hex_sha256(
            metadata_dict.get("runner_packet_file_sha256")
        ),
        "manifest_sha256": _hex_sha256(metadata_dict.get("manifest_file_sha256")),
        "final_full_runtime_packet_sha256": _hex_sha256(
            metadata_dict.get("final_full_runtime_file_sha256")
        ),
        "runner_packet_kind": _safe_text(runner.get("packet_kind"), limit=96),
        "manifest_packet_kind": _safe_text(manifest.get("packet_kind"), limit=96),
        "final_packet_kind": _safe_text(final.get("packet_kind"), limit=96),
        "runner_packet_effect": _safe_text(runner.get("effect"), limit=32),
        "admission_input_failures": input_failure_list,
        "admission_coherence_failures": coherence_failure_list,
        "admission_proof_failures": proof_failure_list,
        "admission_unsafe_failures": unsafe_failure_list,
        "artifact_file_names": artifact_names,
        "artifact_count": len(artifact_names),
        "artifact_file_paths_recorded": False,
        "proof_admitted": ok,
        "feature_proof_admitted": ok,
        "fresh_session_bound": bool(
            ok and metadata_dict.get("proof_dir_is_dir") is True and artifact_names
        ),
        "artifact_set_coherent": bool(ok),
        "full_runtime_dispatch_runner_proven": bool(
            ok and runner.get("full_runtime_dispatch_runner_proven") is True
        ),
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
        "evidence_written": False,
        "file_mutation_attempted": False,
        "changed_files": [],
        "blocking_reasons": [] if ok else blocking_reasons,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP admitted the full runtime dispatch proof directory."
            if ok
            else "WBP blocked full runtime dispatch proof admission."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_READ,
        secret_values=list(secret_values or []) + [proof_dir],
        extra=extra,
    )


def run_full_runtime_dispatch_admission_command(
    *,
    proof_dir: str,
) -> dict[str, Any]:
    proof_root = Path(proof_dir).expanduser()
    metadata: dict[str, Any] = {
        "proof_dir_present": bool(proof_dir),
        "proof_dir_is_dir": bool(proof_dir) and proof_root.exists() and proof_root.is_dir(),
        "proof_dir_path_recorded": False,
    }
    runner_path = proof_root / FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME
    manifest_path = proof_root / FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME
    final_path = proof_root / FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME

    runner_packet, runner_metadata = _read_json_mapping_file(
        runner_path,
        prefix="runner_packet",
    )
    manifest_packet, manifest_metadata = _read_json_mapping_file(
        manifest_path,
        prefix="manifest",
    )
    final_packet, final_metadata = _read_json_mapping_file(
        final_path,
        prefix="final_full_runtime",
    )
    metadata.update(runner_metadata)
    metadata.update(manifest_metadata)
    metadata.update(final_metadata)

    input_failure_list = _input_failures(metadata)
    artifact_packets: dict[str, Mapping[str, Any]] = {}
    artifact_read_failures: list[str] = []
    if not input_failure_list:
        runner_summaries, runner_summary_failures = _summary_map(
            runner_packet.get("artifact_summaries")
        )
        artifact_read_failures.extend(runner_summary_failures)
        for name in runner_summaries:
            path = proof_root / name
            artifact_packet, artifact_metadata = _read_json_mapping_file(
                path,
                prefix=f"artifact_{name.replace('-', '_').replace('.', '_')}",
            )
            if artifact_metadata.get(
                f"artifact_{name.replace('-', '_').replace('.', '_')}_file_valid_json"
            ) is not True:
                artifact_read_failures.append(f"{name}_artifact_file_json_invalid")
            if artifact_metadata.get(
                f"artifact_{name.replace('-', '_').replace('.', '_')}_file_mapping"
            ) is not True:
                artifact_read_failures.append(f"{name}_artifact_file_not_mapping")
            artifact_packets[name] = artifact_packet
    coherence_failure_list = sorted(
        set(
            artifact_read_failures
            + _coherence_failures(
                proof_root=proof_root,
                metadata=metadata,
                runner_packet=runner_packet,
                manifest_packet=manifest_packet,
                final_packet=final_packet,
                artifact_packets=artifact_packets,
            )
        )
    )
    proof_failure_list = _proof_failures(
        runner_packet=runner_packet,
        manifest_packet=manifest_packet,
        final_packet=final_packet,
    )
    unsafe_failure_list = _unsafe_failures(
        {
            FULL_RUNTIME_DISPATCH_PROOF_RUNNER_FILE_NAME: runner_packet,
            FULL_RUNTIME_DISPATCH_PROOF_RUNNER_MANIFEST_FILE_NAME: manifest_packet,
            FULL_RUNTIME_DISPATCH_PROOF_FILE_NAME: final_packet,
            **artifact_packets,
        },
    )
    return build_full_runtime_dispatch_admission_packet(
        proof_dir=proof_dir,
        metadata=metadata,
        runner_packet=runner_packet,
        manifest_packet=manifest_packet,
        final_packet=final_packet,
        artifact_packets=artifact_packets,
        input_failures=input_failure_list,
        coherence_failures=coherence_failure_list,
        proof_failures=proof_failure_list,
        unsafe_failures=unsafe_failure_list,
    )
