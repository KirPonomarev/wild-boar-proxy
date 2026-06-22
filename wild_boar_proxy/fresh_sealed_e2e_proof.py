# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
from typing import Any

from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_admission import (
    DEFAULT_EXPECTED_TEXT,
    DEFAULT_SANDBOX,
    DEFAULT_TIMEOUT_SECONDS,
)
from .codex_working_flow_delivery_proof import (
    run_codex_working_flow_delivery_proof_command,
)
from .custom_codex_native_ui_observer_proof import (
    NATIVE_UI_OBSERVER_PACKET_FILE_NAME,
    run_native_ui_observer_proof_command,
)
from .custom_codex_ui_visibility_proof import (
    run_custom_codex_ui_visibility_proof_command,
)
from .custom_codex_visible_source_binding_proof import (
    VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
    run_custom_codex_visible_source_binding_proof_command,
)
from .fresh_live_custom_codex_e2e_proof import (
    FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND,
    run_fresh_live_custom_codex_e2e_proof_command,
)
from .full_runtime_dispatch_admission import (
    run_full_runtime_dispatch_admission_command,
)
from .full_runtime_dispatch_admission_seal import (
    run_full_runtime_dispatch_admission_seal_command,
)
from .full_runtime_dispatch_proof_runner import (
    run_full_runtime_dispatch_proof_runner_command,
)
from .proof_seal import sha256_file
from .router_hook_entry import _safe_text
from .runtime import RuntimePaths, write_json_atomic


FRESH_SEALED_E2E_PACKET_KIND = "wbp_fresh_sealed_e2e_proof"

FRESH_SEALED_E2E_OK = "OK"
FRESH_SEALED_E2E_FRESH_LIVE_FAILED = "WBP_FRESH_SEALED_E2E_FRESH_LIVE_FAILED"
FRESH_SEALED_E2E_INPUT_ARTIFACT_MISSING = (
    "WBP_FRESH_SEALED_E2E_INPUT_ARTIFACT_MISSING"
)
FRESH_SEALED_E2E_FULL_RUNTIME_FAILED = (
    "WBP_FRESH_SEALED_E2E_FULL_RUNTIME_FAILED"
)
FRESH_SEALED_E2E_ADMISSION_FAILED = "WBP_FRESH_SEALED_E2E_ADMISSION_FAILED"
FRESH_SEALED_E2E_SEAL_FAILED = "WBP_FRESH_SEALED_E2E_SEAL_FAILED"
FRESH_SEALED_E2E_NEGATIVE_FAILED = "WBP_FRESH_SEALED_E2E_NEGATIVE_FAILED"
FRESH_SEALED_E2E_UNSAFE_PACKET = "WBP_FRESH_SEALED_E2E_UNSAFE_PACKET"
DEFAULT_FRESH_SEALED_VISIBLE_PREFIX = "WBP_FRESH_SEALED_VISIBLE"


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "codex-runner" / "fresh-sealed-e2e-proof" / stamp


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _new_freshness_anchor_digest() -> str:
    return hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def _wrong_digest_for(digest: str) -> str:
    candidate = "b" * 64
    return candidate if candidate != digest else "c" * 64


def _read_json_mapping(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _read_jsonl_mappings(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return events
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, Mapping):
            events.append(dict(parsed))
    return events


def _approved_visible_event_projection(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    approved: list[dict[str, Any]] = []
    for raw_event in events:
        event = dict(raw_event)
        event_type = _safe_text(event.get("type"), limit=96)
        if event_type in {"thread.started", "turn.started", "turn.completed"}:
            approved.append(event)
            continue
        item = event.get("item")
        if not isinstance(item, Mapping):
            continue
        item_type = _safe_text(item.get("type"), limit=96)
        if item_type in {"mcp_tool_call", "mcp_tool_result", "assistant_message"}:
            approved.append(event)
    return approved


def _write_jsonl(path: Path, events: Sequence[Mapping[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(dict(event), ensure_ascii=True) for event in events) + "\n",
        encoding="utf-8",
    )
    return str(path)


def _write_packet(path: Path, packet: Mapping[str, Any]) -> str:
    write_json_atomic(path, dict(packet))
    return str(path)


def _expected_visible_text(*, handoff_digest: str, request_id: str) -> str:
    return f"{DEFAULT_FRESH_SEALED_VISIBLE_PREFIX}_{handoff_digest}_{request_id}"


def _fresh_live_ok(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("packet_kind") == FRESH_LIVE_CUSTOM_CODEX_E2E_PACKET_KIND
        and packet.get("fresh_live_custom_codex_e2e_proven") is True
        and packet.get("user_prompt_submit_hook_ran") is True
        and packet.get("api_lane_called") is True
        and packet.get("dispatch_proven") is True
        and packet.get("codex_working_flow_delivery_proven") is True
    )


def _input_artifacts_present(
    *,
    real_custom_hook_proof_file: Path,
    working_flow_delivery_proof_file: Path,
    codex_exec_jsonl_file: Path,
    custom_codex_ui_visibility_proof_file: Path,
) -> bool:
    return bool(
        real_custom_hook_proof_file.is_file()
        and working_flow_delivery_proof_file.is_file()
        and codex_exec_jsonl_file.is_file()
        and custom_codex_ui_visibility_proof_file.is_file()
    )


def _runner_ok(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("full_runtime_dispatch_runner_proven") is True
        and packet.get("full_runtime_dispatch_proven") is True
        and packet.get("custom_codex_flow_proven") is True
        and packet.get("user_prompt_submit_hook_ran") is True
        and packet.get("api_lane_called") is True
        and packet.get("dispatch_proven") is True
        and packet.get("codex_working_flow_delivery_proven") is True
        and packet.get("custom_codex_ui_visibility_proven") is True
        and packet.get("freshness_anchor_digest_present") is True
    )


def _admission_ok(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("proof_admitted") is True
        and packet.get("feature_proof_admitted") is True
        and packet.get("external_freshness_proven") is True
        and packet.get("expected_freshness_anchor_digest_bound") is True
    )


def _seal_ok(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("proof_admission_sealed") is True
        and packet.get("feature_runtime_proof_sealed") is True
        and packet.get("external_freshness_proven") is True
        and packet.get("admission_packet_sha256")
    )


def _wrong_digest_negative_ok(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "error"
        and packet.get("proof_admission_sealed") is False
        and packet.get("feature_runtime_proof_sealed") is False
    )


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _machine_error_code(
    *,
    fresh_live_ok: bool,
    input_artifacts_present: bool,
    runner_ok: bool,
    admission_ok: bool,
    seal_ok: bool,
    wrong_digest_negative_ok: bool,
    unsafe: bool,
) -> str:
    if unsafe:
        return FRESH_SEALED_E2E_UNSAFE_PACKET
    if not fresh_live_ok:
        return FRESH_SEALED_E2E_FRESH_LIVE_FAILED
    if not input_artifacts_present:
        return FRESH_SEALED_E2E_INPUT_ARTIFACT_MISSING
    if not runner_ok:
        return FRESH_SEALED_E2E_FULL_RUNTIME_FAILED
    if not admission_ok:
        return FRESH_SEALED_E2E_ADMISSION_FAILED
    if not seal_ok:
        return FRESH_SEALED_E2E_SEAL_FAILED
    if not wrong_digest_negative_ok:
        return FRESH_SEALED_E2E_NEGATIVE_FAILED
    return FRESH_SEALED_E2E_OK


def build_fresh_sealed_e2e_packet(
    *,
    proof_run_id: str,
    proof_run_started_at_ns: int,
    proof_root: Path,
    freshness_anchor_digest: str,
    fresh_live_packet: Mapping[str, Any],
    full_runtime_runner_packet: Mapping[str, Any] | None,
    admission_packet: Mapping[str, Any] | None,
    seal_packet: Mapping[str, Any] | None,
    wrong_digest_seal_packet: Mapping[str, Any] | None,
    real_custom_hook_proof_file: Path,
    working_flow_delivery_proof_file: Path,
    codex_exec_jsonl_file: Path,
    custom_codex_ui_visibility_proof_file: Path,
    fresh_live_packet_file: Path,
    admission_packet_file: Path,
    seal_packet_file: Path,
    wrong_digest_seal_packet_file: Path,
    visible_source_binding_proof_file: Path,
    native_ui_observer_packet_file: Path,
    ui_visibility_source: str,
    final_packet_file: Path,
    changed_files: Sequence[str],
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    fresh_live = dict(fresh_live_packet)
    runner = dict(full_runtime_runner_packet or {})
    admission = dict(admission_packet or {})
    seal = dict(seal_packet or {})
    wrong_digest = dict(wrong_digest_seal_packet or {})
    fresh_ok = _fresh_live_ok(fresh_live)
    inputs_present = _input_artifacts_present(
        real_custom_hook_proof_file=real_custom_hook_proof_file,
        working_flow_delivery_proof_file=working_flow_delivery_proof_file,
        codex_exec_jsonl_file=codex_exec_jsonl_file,
        custom_codex_ui_visibility_proof_file=custom_codex_ui_visibility_proof_file,
    )
    full_runtime_ok = _runner_ok(runner)
    strict_admission_ok = _admission_ok(admission)
    admission_seal_ok = _seal_ok(seal)
    negative_ok = _wrong_digest_negative_ok(wrong_digest)
    freshness_bound = bool(
        admission.get("expected_freshness_anchor_digest") == freshness_anchor_digest
        and seal.get("expected_freshness_anchor_digest") == freshness_anchor_digest
        and runner.get("freshness_anchor_digest") == freshness_anchor_digest
    )
    unsafe_payload = {
        "packet_kind": FRESH_SEALED_E2E_PACKET_KIND,
        "proof_run_id": proof_run_id,
        "freshness_anchor_digest": freshness_anchor_digest,
        "fresh_live_packet_sha256": sha256_file(fresh_live_packet_file),
        "full_runtime_runner_packet_sha256": sha256_file(
            proof_root / "full-runtime" / "full-runtime-dispatch-proof-runner.packet.json"
        ),
        "admission_packet_sha256": sha256_file(admission_packet_file),
        "seal_packet_sha256": sha256_file(seal_packet_file),
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values or []),
    )
    machine_error_code = _machine_error_code(
        fresh_live_ok=fresh_ok,
        input_artifacts_present=inputs_present,
        runner_ok=full_runtime_ok,
        admission_ok=strict_admission_ok,
        seal_ok=admission_seal_ok,
        wrong_digest_negative_ok=negative_ok,
        unsafe=unsafe,
    )
    ok = machine_error_code == FRESH_SEALED_E2E_OK
    blocking_reasons = sorted(
        set(
            _safe_reasons(fresh_live.get("blocking_reasons"))
            + _safe_reasons(runner.get("blocking_reasons"))
            + _safe_reasons(admission.get("blocking_reasons"))
            + _safe_reasons(seal.get("blocking_reasons"))
            + _safe_reasons(wrong_digest.get("blocking_reasons"))
            + ([] if fresh_ok else ["fresh_sealed_e2e_fresh_live_not_proven"])
            + ([] if inputs_present else ["fresh_sealed_e2e_input_artifacts_missing"])
            + ([] if full_runtime_ok else ["fresh_sealed_e2e_full_runtime_not_proven"])
            + ([] if strict_admission_ok else ["fresh_sealed_e2e_admission_not_proven"])
            + ([] if admission_seal_ok else ["fresh_sealed_e2e_seal_not_proven"])
            + ([] if negative_ok else ["fresh_sealed_e2e_wrong_digest_negative_not_proven"])
            + ([] if freshness_bound else ["fresh_sealed_e2e_freshness_digest_not_bound"])
            + (["fresh_sealed_e2e_packet_secret_leak"] if unsafe else [])
        )
    )
    extra = {
        "schema_version": 1,
        "packet_kind": FRESH_SEALED_E2E_PACKET_KIND,
        "proof_scope": "fresh_custom_codex_to_sealed_full_runtime_dispatch",
        "fresh_sealed_e2e_proven": ok,
        "fresh_runtime_proof_sealed": ok,
        "proof_run_id": proof_run_id if packets.is_command_value_token(proof_run_id) else "",
        "proof_run_id_digest": _sha256_text(proof_run_id),
        "proof_run_started_at_ns": proof_run_started_at_ns,
        "freshness_anchor_digest": freshness_anchor_digest,
        "freshness_anchor_digest_present": bool(freshness_anchor_digest),
        "freshness_anchor_digest_generated": True,
        "raw_freshness_anchor_recorded": False,
        "freshness_anchor_bound_to_runner": bool(
            ok and runner.get("freshness_anchor_digest") == freshness_anchor_digest
        ),
        "freshness_anchor_bound_to_admission": bool(
            ok and admission.get("expected_freshness_anchor_digest") == freshness_anchor_digest
        ),
        "freshness_anchor_bound_to_seal": bool(
            ok and seal.get("expected_freshness_anchor_digest") == freshness_anchor_digest
        ),
        "fresh_live_packet_kind": _safe_text(fresh_live.get("packet_kind"), limit=96),
        "fresh_live_status": _safe_text(fresh_live.get("status"), limit=32),
        "fresh_live_machine_error_code": _safe_text(
            fresh_live.get("machine_error_code"),
            limit=96,
        ),
        "fresh_live_custom_codex_e2e_proven": bool(
            ok and fresh_live.get("fresh_live_custom_codex_e2e_proven") is True
        ),
        "fresh_live_packet_sha256": sha256_file(fresh_live_packet_file),
        "real_custom_hook_proof_file_present": real_custom_hook_proof_file.is_file(),
        "working_flow_delivery_proof_file_present": working_flow_delivery_proof_file.is_file(),
        "codex_exec_jsonl_file_present": codex_exec_jsonl_file.is_file(),
        "custom_codex_ui_visibility_proof_file_present": (
            custom_codex_ui_visibility_proof_file.is_file()
        ),
        "real_custom_hook_proof_sha256": sha256_file(real_custom_hook_proof_file),
        "working_flow_delivery_proof_sha256": sha256_file(working_flow_delivery_proof_file),
        "codex_exec_jsonl_sha256": sha256_file(codex_exec_jsonl_file),
        "custom_codex_ui_visibility_proof_sha256": sha256_file(
            custom_codex_ui_visibility_proof_file
        ),
        "ui_visibility_source": _safe_text(ui_visibility_source, limit=80),
        "visible_source_binding_proof_file_present": (
            visible_source_binding_proof_file.is_file()
        ),
        "native_ui_observer_packet_file_present": native_ui_observer_packet_file.is_file(),
        "visible_source_binding_proof_sha256": sha256_file(
            visible_source_binding_proof_file
        ),
        "native_ui_observer_packet_sha256": sha256_file(native_ui_observer_packet_file),
        "full_runtime_runner_packet_kind": _safe_text(runner.get("packet_kind"), limit=96),
        "full_runtime_runner_status": _safe_text(runner.get("status"), limit=32),
        "full_runtime_runner_machine_error_code": _safe_text(
            runner.get("machine_error_code"),
            limit=96,
        ),
        "full_runtime_dispatch_runner_proven": bool(
            ok and runner.get("full_runtime_dispatch_runner_proven") is True
        ),
        "full_runtime_dispatch_proven": bool(
            ok and runner.get("full_runtime_dispatch_proven") is True
        ),
        "custom_codex_flow_proven": bool(
            ok and runner.get("custom_codex_flow_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and runner.get("user_prompt_submit_hook_ran") is True
        ),
        "api_lane_called": bool(ok and runner.get("api_lane_called") is True),
        "dispatch_proven": bool(ok and runner.get("dispatch_proven") is True),
        "codex_working_flow_delivery_proven": bool(
            ok and runner.get("codex_working_flow_delivery_proven") is True
        ),
        "custom_codex_ui_visibility_proven": bool(
            ok and runner.get("custom_codex_ui_visibility_proven") is True
        ),
        "full_runtime_runner_packet_sha256": sha256_file(
            proof_root / "full-runtime" / "full-runtime-dispatch-proof-runner.packet.json"
        ),
        "admission_packet_kind": _safe_text(admission.get("packet_kind"), limit=96),
        "admission_status": _safe_text(admission.get("status"), limit=32),
        "admission_machine_error_code": _safe_text(
            admission.get("machine_error_code"),
            limit=96,
        ),
        "strict_admission_proven": strict_admission_ok if ok else False,
        "external_freshness_proven": bool(
            ok and admission.get("external_freshness_proven") is True
        ),
        "admission_packet_sha256": sha256_file(admission_packet_file),
        "admission_seal_packet_kind": _safe_text(seal.get("packet_kind"), limit=96),
        "admission_seal_status": _safe_text(seal.get("status"), limit=32),
        "admission_seal_machine_error_code": _safe_text(
            seal.get("machine_error_code"),
            limit=96,
        ),
        "proof_admission_sealed": bool(
            ok and seal.get("proof_admission_sealed") is True
        ),
        "feature_runtime_proof_sealed": bool(
            ok and seal.get("feature_runtime_proof_sealed") is True
        ),
        "admission_seal_packet_sha256": sha256_file(seal_packet_file),
        "wrong_digest_negative_proven": negative_ok,
        "wrong_digest_seal_status": _safe_text(wrong_digest.get("status"), limit=32),
        "wrong_digest_seal_machine_error_code": _safe_text(
            wrong_digest.get("machine_error_code"),
            limit=96,
        ),
        "wrong_digest_seal_packet_sha256": sha256_file(wrong_digest_seal_packet_file),
        "proof_dir_path_recorded": False,
        "input_file_paths_recorded": False,
        "fresh_live_packet_file_path_recorded": False,
        "admission_packet_file_path_recorded": False,
        "admission_seal_packet_file_path_recorded": False,
        "final_packet_file_path_recorded": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "delivery_counts_as_custom_codex_ui": False,
        "native_free_chat_router_proven": False,
        "native_free_chat_router_product_ready": False,
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
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": True,
        "file_mutation_attempted": True,
        "blocking_reasons": [] if ok else blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP proved a fresh sealed Custom Codex full-runtime E2E chain."
            if ok
            else "WBP blocked fresh sealed Custom Codex full-runtime E2E proof."
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


def run_fresh_sealed_e2e_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    custom_codex_ui_visibility_proof_file: str | None = None,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    expected_text: str = DEFAULT_EXPECTED_TEXT,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    persistent_profile_id: str = "wbp-custom-main",
    persistent_profile_base_dir: str | None = None,
    observer_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    proof_run_started_at_ns = time.time_ns()
    proof_run_id = f"WBP_FRESH_SEALED_E2E_{proof_run_started_at_ns}"
    proof_root = _proof_root(paths, proof_dir)
    fresh_live_root = proof_root / "fresh-live"
    admission_dir = fresh_live_root / "admission"
    approved_visible_flow_dir = proof_root / "approved-visible-flow"
    ui_visibility_dir = proof_root / "ui-visibility"
    native_ui_dir = proof_root / "native-ui-observer"
    full_runtime_dir = proof_root / "full-runtime"
    proof_root.mkdir(parents=True, exist_ok=True)
    freshness_anchor_digest = _new_freshness_anchor_digest()
    changed_files: list[str] = []
    secret_values = [prompt_text, expected_text]

    fresh_live_packet = run_fresh_live_custom_codex_e2e_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        codex_bin=codex_bin,
        codex_model=codex_model,
        proof_dir=str(fresh_live_root),
        codex_cwd=codex_cwd,
        expected_text=expected_text,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
    )
    changed_files.extend(str(path) for path in fresh_live_packet.get("changed_files", []))

    fresh_live_packet_file = fresh_live_root / "fresh-live-e2e-proof.packet.json"
    if not fresh_live_packet_file.is_file():
        changed_files.append(_write_packet(fresh_live_packet_file, fresh_live_packet))

    real_custom_hook_proof_file = admission_dir / "user-prompt-submit-proof.packet.json"
    working_flow_delivery_proof_file = (
        admission_dir / "working-flow-delivery-proof.packet.json"
    )
    codex_exec_jsonl_file = admission_dir / "codex-exec.jsonl"
    approved_visible_jsonl_file = approved_visible_flow_dir / "codex-exec-approved-visible.jsonl"
    approved_visible_working_flow_file = (
        approved_visible_flow_dir / "working-flow-delivery-proof.packet.json"
    )
    visible_source_binding_file = (
        ui_visibility_dir / "visible-source-binding-proof.packet.json"
    )
    native_ui_observer_packet_file = native_ui_dir / NATIVE_UI_OBSERVER_PACKET_FILE_NAME
    ui_visibility_file = (
        Path(custom_codex_ui_visibility_proof_file).expanduser()
        if custom_codex_ui_visibility_proof_file
        else ui_visibility_dir / "custom-codex-ui-visibility-proof.packet.json"
    )
    ui_visibility_source = "external_file" if custom_codex_ui_visibility_proof_file else "auto_native_observer"

    full_runtime_runner_packet: dict[str, Any] = {}
    admission_packet: dict[str, Any] = {}
    seal_packet: dict[str, Any] = {}
    wrong_digest_seal_packet: dict[str, Any] = {}
    if (
        _fresh_live_ok(fresh_live_packet)
        and real_custom_hook_proof_file.is_file()
        and working_flow_delivery_proof_file.is_file()
        and codex_exec_jsonl_file.is_file()
    ):
        source_events = _read_jsonl_mappings(codex_exec_jsonl_file)
        visible_events = _approved_visible_event_projection(source_events)
        if visible_events:
            changed_files.append(_write_jsonl(approved_visible_jsonl_file, visible_events))
            approved_visible_working_flow = run_codex_working_flow_delivery_proof_command(
                integrated_live_provider_proof_file=str(real_custom_hook_proof_file),
                codex_exec_jsonl_file=str(approved_visible_jsonl_file),
            )
            changed_files.append(
                _write_packet(
                    approved_visible_working_flow_file,
                    approved_visible_working_flow,
                )
            )
            working_flow_delivery_proof_file = approved_visible_working_flow_file
            codex_exec_jsonl_file = approved_visible_jsonl_file

    if (
        _fresh_live_ok(fresh_live_packet)
        and not custom_codex_ui_visibility_proof_file
        and real_custom_hook_proof_file.is_file()
        and working_flow_delivery_proof_file.is_file()
        and codex_exec_jsonl_file.is_file()
    ):
        ui_visibility_dir.mkdir(parents=True, exist_ok=True)
        visible_binding_packet = run_custom_codex_visible_source_binding_proof_command(
            paths=paths,
            working_flow_delivery_proof_file=str(working_flow_delivery_proof_file),
            visible_source_kind=VISIBLE_SOURCE_CODEX_EXEC_JSON_ASSISTANT_OUTPUT,
            codex_exec_jsonl_file=str(codex_exec_jsonl_file),
        )
        changed_files.append(_write_packet(visible_source_binding_file, visible_binding_packet))
        handoff_digest = _safe_text(
            visible_binding_packet.get("handoff_payload_digest"),
            limit=80,
        )
        request_id = f"fresh-sealed-{proof_run_started_at_ns}"
        visible_text = _expected_visible_text(
            handoff_digest=handoff_digest,
            request_id=request_id,
        )
        native_packet = run_native_ui_observer_proof_command(
            paths=paths,
            prompt_text=f"Reply exactly with this single line:\n{visible_text}",
            request_id=request_id,
            expected_text=visible_text,
            proof_dir=str(native_ui_dir),
            persistent_profile_id=persistent_profile_id,
            persistent_profile_base_dir=persistent_profile_base_dir,
            observer_timeout_seconds=observer_timeout_seconds,
        )
        if not native_ui_observer_packet_file.is_file():
            changed_files.append(_write_packet(native_ui_observer_packet_file, native_packet))
        else:
            changed_files.append(str(native_ui_observer_packet_file))
        ui_visibility_packet = run_custom_codex_ui_visibility_proof_command(
            visible_source_binding_proof_file=str(visible_source_binding_file),
            native_ui_observer_packet_file=str(native_ui_observer_packet_file),
            expected_visible_text=visible_text,
            request_id=request_id,
        )
        changed_files.append(_write_packet(ui_visibility_file, ui_visibility_packet))

    if _fresh_live_ok(fresh_live_packet) and _input_artifacts_present(
        real_custom_hook_proof_file=real_custom_hook_proof_file,
        working_flow_delivery_proof_file=working_flow_delivery_proof_file,
        codex_exec_jsonl_file=codex_exec_jsonl_file,
        custom_codex_ui_visibility_proof_file=ui_visibility_file,
    ):
        full_runtime_runner_packet = run_full_runtime_dispatch_proof_runner_command(
            real_custom_hook_proof_file=str(real_custom_hook_proof_file),
            working_flow_delivery_proof_file=str(working_flow_delivery_proof_file),
            codex_exec_jsonl_file=str(codex_exec_jsonl_file),
            custom_codex_ui_visibility_proof_file=str(ui_visibility_file),
            proof_dir=str(full_runtime_dir),
            freshness_anchor_digest=freshness_anchor_digest,
        )
        admission_packet = run_full_runtime_dispatch_admission_command(
            proof_dir=str(full_runtime_dir),
            expected_freshness_anchor_digest=freshness_anchor_digest,
        )
        seal_packet = run_full_runtime_dispatch_admission_seal_command(
            proof_dir=str(full_runtime_dir),
            expected_freshness_anchor_digest=freshness_anchor_digest,
        )
        wrong_digest_seal_packet = run_full_runtime_dispatch_admission_seal_command(
            proof_dir=str(full_runtime_dir),
            expected_freshness_anchor_digest=_wrong_digest_for(freshness_anchor_digest),
        )

    admission_packet_file = proof_root / "strict-admission.packet.json"
    seal_packet_file = proof_root / "admission-seal.packet.json"
    wrong_digest_seal_packet_file = proof_root / "wrong-digest-admission-seal.packet.json"
    final_packet_file = proof_root / "fresh-sealed-e2e-proof.packet.json"
    changed_files.append(_write_packet(admission_packet_file, admission_packet))
    changed_files.append(_write_packet(seal_packet_file, seal_packet))
    changed_files.append(_write_packet(wrong_digest_seal_packet_file, wrong_digest_seal_packet))

    final_packet = build_fresh_sealed_e2e_packet(
        proof_run_id=proof_run_id,
        proof_run_started_at_ns=proof_run_started_at_ns,
        proof_root=proof_root,
        freshness_anchor_digest=freshness_anchor_digest,
        fresh_live_packet=fresh_live_packet,
        full_runtime_runner_packet=full_runtime_runner_packet,
        admission_packet=admission_packet,
        seal_packet=seal_packet,
        wrong_digest_seal_packet=wrong_digest_seal_packet,
        real_custom_hook_proof_file=real_custom_hook_proof_file,
        working_flow_delivery_proof_file=working_flow_delivery_proof_file,
        codex_exec_jsonl_file=codex_exec_jsonl_file,
        custom_codex_ui_visibility_proof_file=ui_visibility_file,
        fresh_live_packet_file=fresh_live_packet_file,
        admission_packet_file=admission_packet_file,
        seal_packet_file=seal_packet_file,
        wrong_digest_seal_packet_file=wrong_digest_seal_packet_file,
        visible_source_binding_proof_file=visible_source_binding_file,
        native_ui_observer_packet_file=native_ui_observer_packet_file,
        ui_visibility_source=ui_visibility_source,
        final_packet_file=final_packet_file,
        changed_files=[*changed_files, str(final_packet_file)],
        secret_values=secret_values,
    )
    _write_packet(final_packet_file, final_packet)
    return final_packet
