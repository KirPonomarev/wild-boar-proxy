# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_admission import (
    DEFAULT_EXPECTED_TEXT,
    DEFAULT_SANDBOX,
    DEFAULT_TIMEOUT_SECONDS,
    _runtime_secret_values,
    run_custom_codex_admission_command,
)
from .official_e2e_fresh_working_flow_proof_runner import (
    OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND,
    run_official_e2e_fresh_working_flow_proof_runner_command,
)
from .proof_seal import sha256_file
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths, get_model, write_json_atomic


FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND = "wbp_fresh_live_custom_codex_e2e_proof"

FRESH_LIVE_E2E_OK = "OK"
FRESH_LIVE_E2E_ADMISSION_FAILED = "WBP_FRESH_LIVE_E2E_ADMISSION_FAILED"
FRESH_LIVE_E2E_CODEX_LAUNCH_FAILED = "WBP_FRESH_LIVE_E2E_CODEX_LAUNCH_FAILED"
FRESH_LIVE_E2E_STALE_MODEL_PROVIDER_MISMATCH = (
    "WBP_FRESH_LIVE_E2E_STALE_MODEL_PROVIDER_MISMATCH"
)
FRESH_LIVE_E2E_HOOK_NOT_PROVEN = "WBP_FRESH_LIVE_E2E_HOOK_NOT_PROVEN"
FRESH_LIVE_E2E_FILE_BRIDGE_NOT_PROVEN = "WBP_FRESH_LIVE_E2E_FILE_BRIDGE_NOT_PROVEN"
FRESH_LIVE_E2E_ASSISTANT_OUTPUT_NOT_BOUND = (
    "WBP_FRESH_LIVE_E2E_ASSISTANT_OUTPUT_NOT_BOUND"
)
FRESH_LIVE_E2E_ARTIFACT_MISSING = "WBP_FRESH_LIVE_E2E_ARTIFACT_MISSING"
FRESH_LIVE_E2E_FRESH_RUNNER_FAILED = "WBP_FRESH_LIVE_E2E_FRESH_RUNNER_FAILED"
FRESH_LIVE_E2E_UNSAFE_PACKET = "WBP_FRESH_LIVE_E2E_UNSAFE_PACKET"

FRESH_LIVE_E2E_LAUNCH_SURFACE = "wild-boar-proxy codex-runner fresh-live-e2e-proof"
DEFAULT_FRESH_LIVE_CODEX_MODEL = "gpt-5.4"
STALE_FRESH_LIVE_CODEX_MODELS = frozenset({"gpt-5.3-codex"})


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "router-hook" / "fresh-live-e2e-proof" / stamp


def build_canonical_fresh_live_prompt(
    *,
    task_text: str,
    expected_text: str,
) -> str:
    task = " ".join(str(task_text or "").split())
    expected = _safe_text(expected_text, limit=128)
    task_line = f"Task digest: {_sha256_text(task)}" if task else "Task digest: none."
    return " ".join(
        [
            "DIP: real Custom Codex fresh live proof.",
            task_line,
            "Read $WBP_PROFILE_DIR/wbp-agent-runtime-context.json as runtime truth.",
            (
                "Use only the enabled deepseek_live_format_check_file_bridge "
                "shell_command_template from that runtime context."
            ),
            f"Replace only <expected_text> with {expected}.",
            "Do not imitate DIP locally.",
            "Do not use a native Codex subagent as DIP.",
            (
                "After the bridge response is observed, your final assistant message "
                "must be exactly one line and exactly this text, with no extra words:"
            ),
            expected,
        ]
    )


def _resolve_codex_model(
    *,
    requested_codex_model: str | None,
    configured_codex_model: str,
) -> dict[str, Any]:
    requested = _safe_text(requested_codex_model, limit=128)
    configured = _safe_text(configured_codex_model, limit=128)
    stale = bool(configured in STALE_FRESH_LIVE_CODEX_MODELS)
    if requested:
        return {
            "effective_codex_model": requested,
            "codex_model_source": "cli_arg",
            "configured_codex_model": configured,
            "stale_profile_model_detected": stale,
            "codex_model_override_applied": requested != configured,
            "profile_config_mutated": False,
        }
    if stale:
        return {
            "effective_codex_model": DEFAULT_FRESH_LIVE_CODEX_MODEL,
            "codex_model_source": "proof_default_override",
            "configured_codex_model": configured,
            "stale_profile_model_detected": True,
            "codex_model_override_applied": True,
            "profile_config_mutated": False,
        }
    return {
        "effective_codex_model": "",
        "codex_model_source": "profile_config",
        "configured_codex_model": configured,
        "stale_profile_model_detected": False,
        "codex_model_override_applied": False,
        "profile_config_mutated": False,
    }


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _read_text(path: Path, *, limit: int = 65536) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _fresh_live_failure_classification(
    *,
    admission: Mapping[str, Any],
    admission_dir: Path,
    admission_dispatch_proven: bool,
) -> dict[str, Any]:
    admission_machine = _safe_text(admission.get("machine_error_code"), limit=128)
    admission_reasons = [
        _safe_text(reason, limit=160)
        for reason in admission.get("blocking_reasons") or []
    ]
    stderr_text = _read_text(admission_dir / "codex-exec.stderr.txt")
    jsonl_text = _read_text(admission_dir / "codex-exec.jsonl")
    working_flow = _read_json_mapping(
        admission_dir / "working-flow-delivery-proof.packet.json"
    )
    working_reasons = [
        _safe_text(reason, limit=160)
        for reason in working_flow.get("blocking_reasons") or []
    ]
    command_assistant_failures = [
        _safe_text(reason, limit=160)
        for reason in working_flow.get("command_assistant_binding_failures") or []
    ]

    stale_model_provider_mismatch = bool(
        admission_machine.endswith("CODEX_LAUNCH_FAILED")
        and "unknown provider for model" in jsonl_text
    )
    assistant_output_not_bound = bool(
        admission_machine.endswith("WORKING_FLOW_FAILED")
        and (
            "command_assistant_response_not_bound_to_live_provider_digest"
            in command_assistant_failures
            or "command_assistant_response_not_bound_to_live_provider_digest"
            in working_reasons
        )
    )
    file_bridge_not_proven = bool(
        admission_machine.endswith("FILE_BRIDGE_NOT_PROVEN")
        or "managed_file_bridge_no_response" in admission_reasons
        or "managed_file_bridge_response_id_not_bound" in admission_reasons
    )
    hook_not_proven = bool(
        admission_machine.endswith("HOOK_PROOF_FAILED")
        or "user_prompt_submit_proof_not_ok" in admission_reasons
    )
    codex_launch_failed = bool(
        admission_machine.endswith("CODEX_LAUNCH_FAILED")
        and not stale_model_provider_mismatch
    )
    return {
        "fresh_live_failure_classifier_version": 1,
        "fresh_live_stale_model_provider_mismatch": stale_model_provider_mismatch,
        "fresh_live_codex_launch_failed": codex_launch_failed,
        "fresh_live_hook_not_proven": hook_not_proven,
        "fresh_live_file_bridge_not_proven": file_bridge_not_proven,
        "fresh_live_assistant_output_not_bound": assistant_output_not_bound,
        "fresh_live_admission_dispatch_not_proven": not admission_dispatch_proven,
        "fresh_live_classified_admission_machine_error_code": admission_machine,
        "fresh_live_classified_working_flow_machine_error_code": _safe_text(
            working_flow.get("machine_error_code"),
            limit=128,
        ),
        "fresh_live_classified_stderr_sha256": (
            _sha256_text(stderr_text) if stderr_text else ""
        ),
        "fresh_live_classified_jsonl_sha256": (
            _sha256_text(jsonl_text) if jsonl_text else ""
        ),
    }


def _write_json_packet(path: Path, payload: Mapping[str, Any]) -> str:
    write_json_atomic(path, dict(payload))
    return str(path)


def _fresh_runner_inputs(
    *,
    proof_run_id: str,
    proof_run_started_at_ns: int,
    source_proof_path: Path,
    codex_exec_jsonl_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "packet_kind": OFFICIAL_E2E_FRESH_WORKING_FLOW_PROOF_RUNNER_INPUTS_PACKET_KIND,
        "proof_run_id": proof_run_id,
        "proof_run_started_at_ns": proof_run_started_at_ns,
        "real_custom_hook_proof_file": str(source_proof_path),
        "codex_exec_jsonl_file": str(codex_exec_jsonl_path),
        "expected_real_custom_hook_proof_file_sha256": sha256_file(source_proof_path),
        "expected_codex_exec_jsonl_file_sha256": sha256_file(codex_exec_jsonl_path),
    }


def _machine_error_code(
    *,
    admission_ok: bool,
    admission_dispatch_proven: bool,
    artifacts_present: bool,
    fresh_runner_ok: bool,
    unsafe: bool,
    failure_classification: Mapping[str, Any] | None = None,
) -> str:
    classification = dict(failure_classification or {})
    if unsafe:
        return FRESH_LIVE_E2E_UNSAFE_PACKET
    if classification.get("fresh_live_stale_model_provider_mismatch") is True:
        return FRESH_LIVE_E2E_STALE_MODEL_PROVIDER_MISMATCH
    if classification.get("fresh_live_codex_launch_failed") is True:
        return FRESH_LIVE_E2E_CODEX_LAUNCH_FAILED
    if classification.get("fresh_live_hook_not_proven") is True:
        return FRESH_LIVE_E2E_HOOK_NOT_PROVEN
    if classification.get("fresh_live_file_bridge_not_proven") is True:
        return FRESH_LIVE_E2E_FILE_BRIDGE_NOT_PROVEN
    if classification.get("fresh_live_assistant_output_not_bound") is True:
        return FRESH_LIVE_E2E_ASSISTANT_OUTPUT_NOT_BOUND
    if not admission_ok or not admission_dispatch_proven:
        return FRESH_LIVE_E2E_ADMISSION_FAILED
    if not artifacts_present:
        return FRESH_LIVE_E2E_ARTIFACT_MISSING
    if not fresh_runner_ok:
        return FRESH_LIVE_E2E_FRESH_RUNNER_FAILED
    return FRESH_LIVE_E2E_OK


def _fresh_runner_acceptance_failures(packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    required_true = (
        "fresh_e2e_working_flow_proven",
        "official_e2e_working_flow_proven",
        "proof_run_started_at_ns_bound",
        "fresh_inputs_created_after_start",
        "real_custom_hook_proof_file_sha256_bound_to_fresh_inputs",
        "codex_exec_jsonl_file_sha256_bound_to_fresh_inputs",
        "real_custom_hook_contract_valid",
        "official_e2e_runner_valid",
        "custom_codex_hook_to_official_working_flow_bound",
        "custom_codex_flow_origin_proven",
        "user_prompt_submit_hook_ran",
        "api_lane_called",
        "dispatch_proven",
        "live_provider_response_proven",
        "codex_working_flow_delivery_proven",
        "official_delivery_candidate_lineage_proven",
        "official_observation_lineage_file_backed",
    )
    required_false = (
        "product_ready",
        "custom_codex_ui_visibility_proven",
        "delivery_counts_as_custom_codex_ui",
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
        "raw_jsonl_recorded",
        "tool_call_arguments_recorded",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
        "raw_backend_details_exposed",
        "secret_value_exposed",
    )
    if packet.get("status") != "ok":
        failures.append("fresh_runner_packet_not_ok")
    if packet.get("machine_error_code") != "OK":
        failures.append("fresh_runner_machine_error_not_ok")
    for field in required_true:
        if packet.get(field) is not True:
            failures.append(f"fresh_runner_{field}_not_true")
    for field in required_false:
        if packet.get(field) is True:
            failures.append(f"fresh_runner_{field}_not_false")
    if packet.get("blocking_reasons") not in ([], ()):
        failures.append("fresh_runner_blocking_reasons_not_empty")
    return sorted(set(failures))


def build_fresh_live_custom_codex_e2e_packet(
    *,
    admission_packet: Mapping[str, Any],
    fresh_runner_packet: Mapping[str, Any] | None,
    proof_run_id: str,
    proof_run_started_at_ns: int,
    proof_root: Path,
    admission_dir: Path,
    fresh_runner_inputs_file: Path,
    fresh_runner_packet_file: Path,
    source_proof_path: Path,
    codex_exec_jsonl_path: Path,
    final_packet_path: Path,
    changed_files: Sequence[str],
    launch_preflight: Mapping[str, Any] | None = None,
    canonical_prompt_digest: str = "",
    canonical_prompt_builder_used: bool = False,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    admission = dict(admission_packet)
    fresh_runner = dict(fresh_runner_packet or {})
    launch = dict(launch_preflight or {})
    admission_ok = bool(
        admission.get("status") == "ok"
        and admission.get("machine_error_code") == "OK"
        and admission.get("admission_proven") is True
    )
    admission_dispatch_proven = bool(
        admission.get("route_bound_dispatch_proven") is True
        or admission.get("dispatch_proven") is True
        or (
            admission.get("user_prompt_submit_hook_ran") is True
            and admission.get("hook_ledger_fresh") is True
            and admission.get("api_lane_called") is True
            and admission.get("live_provider_response_proven") is True
        )
    )
    artifacts_present = bool(source_proof_path.is_file() and codex_exec_jsonl_path.is_file())
    fresh_runner_failures = _fresh_runner_acceptance_failures(fresh_runner)
    fresh_runner_ok = bool(not fresh_runner_failures)
    unsafe_payload = {
        "packet_kind": FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND,
        "proof_run_id": proof_run_id,
        "prompt_digest": _safe_text(admission.get("codex_exec_prompt_digest"), limit=80),
        "expected_text_digest": _safe_text(admission.get("expected_text_digest"), limit=80),
        "source_proof_sha256": sha256_file(source_proof_path),
        "codex_exec_jsonl_sha256": sha256_file(codex_exec_jsonl_path),
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values or []),
    )
    failure_classification = _fresh_live_failure_classification(
        admission=admission,
        admission_dir=admission_dir,
        admission_dispatch_proven=admission_dispatch_proven,
    )
    ok = bool(
        admission_ok
        and admission_dispatch_proven
        and artifacts_present
        and fresh_runner_ok
        and not unsafe
    )
    blocking_reasons = sorted(
        set(
            list(admission.get("blocking_reasons") or [])
            + list(fresh_runner.get("blocking_reasons") or [])
            + fresh_runner_failures
            + ([] if admission_ok else ["fresh_live_admission_not_proven"])
            + (
                []
                if admission_dispatch_proven
                else ["fresh_live_admission_dispatch_not_proven"]
            )
            + ([] if artifacts_present else ["fresh_live_required_artifacts_missing"])
            + ([] if fresh_runner_ok else ["fresh_live_official_fresh_runner_not_proven"])
            + (["fresh_live_packet_secret_leak"] if unsafe else [])
        )
    )
    machine_error_code = _machine_error_code(
        admission_ok=admission_ok,
        admission_dispatch_proven=admission_dispatch_proven,
        artifacts_present=artifacts_present,
        fresh_runner_ok=fresh_runner_ok,
        unsafe=unsafe,
        failure_classification=failure_classification,
    )
    extra = {
        "schema_version": 1,
        "packet_kind": FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND,
        "runner_launch_surface": FRESH_LIVE_E2E_LAUNCH_SURFACE,
        "proof_scope": "fresh_live_custom_codex_to_official_e2e",
        "fresh_live_custom_codex_e2e_proven": ok,
        "fresh_live_e2e_working_flow_proven": ok,
        "proof_run_id": proof_run_id if packets.is_command_value_token(proof_run_id) else "",
        "proof_run_id_digest": _sha256_text(proof_run_id),
        "proof_run_started_at_ns": proof_run_started_at_ns,
        "proof_run_started_at_ns_bound": bool(
            proof_run_started_at_ns
            and fresh_runner.get("proof_run_started_at_ns_bound") is True
        ),
        "launch_preflight_version": 1,
        "custom_codex_profile_env_expected": True,
        "code_home_bound_to_custom_profile": True,
        "wbp_profile_dir_bound_to_custom_profile": True,
        "configured_codex_model": _safe_text(
            launch.get("configured_codex_model"),
            limit=128,
        ),
        "effective_codex_model": _safe_text(
            launch.get("effective_codex_model"),
            limit=128,
        ),
        "codex_model_source": _safe_text(launch.get("codex_model_source"), limit=80),
        "stale_profile_model_detected": (
            launch.get("stale_profile_model_detected") is True
        ),
        "codex_model_override_applied": (
            launch.get("codex_model_override_applied") is True
        ),
        "profile_config_mutated": launch.get("profile_config_mutated") is True,
        "canonical_prompt_builder_used": canonical_prompt_builder_used,
        "canonical_prompt_digest": _safe_text(canonical_prompt_digest, limit=80),
        "canonical_prompt_raw_recorded": False,
        **failure_classification,
        "admission_packet_kind": _safe_text(admission.get("packet_kind"), limit=96),
        "admission_status": _safe_text(admission.get("status"), limit=32),
        "admission_machine_error_code": _safe_text(
            admission.get("machine_error_code"),
            limit=96,
        ),
        "admission_proven": admission_ok,
        "same_turn_custom_codex_flow_proven": bool(
            ok and admission.get("same_turn_custom_codex_flow_proven") is True
        ),
        "hook_ledger_fresh": bool(ok and admission.get("hook_ledger_fresh") is True),
        "user_prompt_submit_hook_ran": bool(
            ok and admission.get("user_prompt_submit_hook_ran") is True
        ),
        "api_lane_called": bool(ok and admission.get("api_lane_called") is True),
        "dispatch_proven": bool(
            ok
            and admission_dispatch_proven
            and fresh_runner.get("dispatch_proven") is True
        ),
        "live_provider_response_proven": bool(
            ok and admission.get("live_provider_response_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and fresh_runner.get("codex_working_flow_delivery_proven") is True
        ),
        "official_fresh_runner_packet_kind": _safe_text(
            fresh_runner.get("packet_kind"),
            limit=96,
        ),
        "official_fresh_runner_status": _safe_text(
            fresh_runner.get("status"),
            limit=32,
        ),
        "official_fresh_runner_machine_error_code": _safe_text(
            fresh_runner.get("machine_error_code"),
            limit=96,
        ),
        "official_fresh_runner_valid": fresh_runner_ok,
        "official_fresh_runner_acceptance_failures": fresh_runner_failures,
        "official_e2e_working_flow_proven": bool(
            ok and fresh_runner.get("official_e2e_working_flow_proven") is True
        ),
        "custom_codex_hook_to_official_working_flow_bound": bool(
            ok
            and fresh_runner.get("custom_codex_hook_to_official_working_flow_bound")
            is True
        ),
        "source_proof_file_present": source_proof_path.is_file(),
        "codex_exec_jsonl_file_present": codex_exec_jsonl_path.is_file(),
        "fresh_runner_inputs_file_present": fresh_runner_inputs_file.is_file(),
        "fresh_runner_packet_file_present": fresh_runner_packet_file.is_file(),
        "source_proof_sha256": sha256_file(source_proof_path),
        "codex_exec_jsonl_sha256": sha256_file(codex_exec_jsonl_path),
        "fresh_runner_inputs_sha256": sha256_file(fresh_runner_inputs_file),
        "official_fresh_runner_packet_sha256": sha256_file(fresh_runner_packet_file),
        "admission_packet_sha256": sha256_file(admission_dir / "custom-codex-admission.packet.json"),
        "fresh_runner_result_sha256": sha256_file(
            proof_root / "official-fresh-e2e" / "official-e2e-runner.packet.json"
        ),
        "proof_dir_path_recorded": False,
        "admission_dir_path_recorded": False,
        "fresh_runner_inputs_file_path_recorded": False,
        "fresh_runner_packet_file_path_recorded": False,
        "source_proof_file_path_recorded": False,
        "codex_exec_jsonl_file_path_recorded": False,
        "final_packet_file_path_recorded": False,
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
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_task_recorded": False,
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
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": bool(final_packet_path.parent.exists()),
        "file_mutation_attempted": True,
        "blocking_reasons": blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a fresh live Custom Codex E2E working flow."
            if ok
            else "WBP blocked fresh live Custom Codex E2E proof."
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


def run_fresh_live_custom_codex_e2e_proof_command(
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
    proof_run_started_at_ns = time.time_ns()
    proof_root = _proof_root(paths, proof_dir)
    admission_dir = proof_root / "admission"
    fresh_runner_dir = proof_root / "official-fresh-e2e"
    proof_root.mkdir(parents=True, exist_ok=True)
    runtime_context, _metadata = load_runtime_context_packet(
        runtime_context_path(paths=paths, runtime_context_file=None)
    )
    configured_codex_model = get_model(paths)
    model_resolution = _resolve_codex_model(
        requested_codex_model=codex_model,
        configured_codex_model=configured_codex_model,
    )
    effective_codex_model = _safe_text(
        model_resolution.get("effective_codex_model"),
        limit=128,
    )
    canonical_prompt = build_canonical_fresh_live_prompt(
        task_text=prompt_text,
        expected_text=expected_text,
    )
    canonical_prompt_digest = _sha256_text(canonical_prompt)
    secret_values = (
        [prompt_text, canonical_prompt, expected_text]
        + _runtime_secret_values(runtime_context)
    )
    admission_packet = run_custom_codex_admission_command(
        paths=paths,
        prompt_text=canonical_prompt,
        codex_bin=codex_bin,
        codex_model=effective_codex_model or None,
        proof_dir=str(admission_dir),
        codex_cwd=codex_cwd,
        expected_text=expected_text,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
    )
    changed_files = [str(path) for path in admission_packet.get("changed_files", [])]
    source_proof_path = admission_dir / "user-prompt-submit-proof.packet.json"
    codex_exec_jsonl_path = admission_dir / "codex-exec.jsonl"
    fresh_runner_inputs_file = proof_root / "fresh-runner-inputs.packet.json"
    fresh_runner_packet_file = proof_root / "official-fresh-runner.packet.json"
    final_packet_path = proof_root / "fresh-live-e2e-proof.packet.json"
    proof_run_id = f"WBP_FRESH_LIVE_E2E_{proof_run_started_at_ns}"

    fresh_runner_packet: dict[str, Any] = {}
    if (
        admission_packet.get("status") == "ok"
        and admission_packet.get("machine_error_code") == "OK"
        and admission_packet.get("admission_proven") is True
        and source_proof_path.is_file()
        and codex_exec_jsonl_path.is_file()
    ):
        runner_inputs = _fresh_runner_inputs(
            proof_run_id=proof_run_id,
            proof_run_started_at_ns=proof_run_started_at_ns,
            source_proof_path=source_proof_path,
            codex_exec_jsonl_path=codex_exec_jsonl_path,
        )
        changed_files.append(_write_json_packet(fresh_runner_inputs_file, runner_inputs))
        fresh_runner_packet = run_official_e2e_fresh_working_flow_proof_runner_command(
            inputs_file=str(fresh_runner_inputs_file),
            proof_output_dir=str(fresh_runner_dir),
        )
        changed_files.append(_write_json_packet(fresh_runner_packet_file, fresh_runner_packet))
    final_packet = build_fresh_live_custom_codex_e2e_packet(
        admission_packet=admission_packet,
        fresh_runner_packet=fresh_runner_packet,
        proof_run_id=proof_run_id,
        proof_run_started_at_ns=proof_run_started_at_ns,
        proof_root=proof_root,
        admission_dir=admission_dir,
        fresh_runner_inputs_file=fresh_runner_inputs_file,
        fresh_runner_packet_file=fresh_runner_packet_file,
        source_proof_path=source_proof_path,
        codex_exec_jsonl_path=codex_exec_jsonl_path,
        final_packet_path=final_packet_path,
        changed_files=[*changed_files, str(final_packet_path)],
        launch_preflight=model_resolution,
        canonical_prompt_digest=canonical_prompt_digest,
        canonical_prompt_builder_used=True,
        secret_values=secret_values,
    )
    _write_json_packet(final_packet_path, final_packet)
    return final_packet
