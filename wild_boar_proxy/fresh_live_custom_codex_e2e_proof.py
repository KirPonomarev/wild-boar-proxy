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
from .runtime import RuntimePaths, write_json_atomic


FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND = "wbp_fresh_live_custom_codex_e2e_proof"

FRESH_LIVE_E2E_OK = "OK"
FRESH_LIVE_E2E_ADMISSION_FAILED = "WBP_FRESH_LIVE_E2E_ADMISSION_FAILED"
FRESH_LIVE_E2E_ARTIFACT_MISSING = "WBP_FRESH_LIVE_E2E_ARTIFACT_MISSING"
FRESH_LIVE_E2E_FRESH_RUNNER_FAILED = "WBP_FRESH_LIVE_E2E_FRESH_RUNNER_FAILED"
FRESH_LIVE_E2E_UNSAFE_PACKET = "WBP_FRESH_LIVE_E2E_UNSAFE_PACKET"

FRESH_LIVE_E2E_LAUNCH_SURFACE = "wild-boar-proxy codex-runner fresh-live-e2e-proof"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "router-hook" / "fresh-live-e2e-proof" / stamp


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
) -> str:
    if unsafe:
        return FRESH_LIVE_E2E_UNSAFE_PACKET
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
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    admission = dict(admission_packet)
    fresh_runner = dict(fresh_runner_packet or {})
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
    secret_values = [prompt_text, expected_text] + _runtime_secret_values(runtime_context)
    admission_packet = run_custom_codex_admission_command(
        paths=paths,
        prompt_text=prompt_text,
        codex_bin=codex_bin,
        codex_model=codex_model,
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
        secret_values=secret_values,
    )
    _write_json_packet(final_packet_path, final_packet)
    return final_packet
