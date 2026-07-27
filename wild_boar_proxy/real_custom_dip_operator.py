# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_PROBE, EFFECT_READ
from .core import packets
from .natural_intent_contract import (
    INTENT_PASS,
    PREFLIGHT_PASS,
    SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
    build_natural_intent_parser_packet,
)
from .real_custom_dip_proof_runner import (
    REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND,
    REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK,
    run_real_custom_dip_proof_runner_command,
)
from .router_hook_entry import _safe_text, load_runtime_context_packet, runtime_context_path
from .runtime import RuntimePaths
from .user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    build_user_prompt_submit_readiness_packet,
)
from .wbp_dip_tool import DEFAULT_MODEL, DEFAULT_SANDBOX, default_codex_bin


REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND = "wbp_real_custom_dip_operator_preflight"
REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND = "wbp_real_custom_dip_operator_work"
REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_PACKET_KIND = "wbp_real_custom_dip_operator_acceptance"
REAL_CUSTOM_DIP_OPERATOR_RUN_PACKET_KIND = "wbp_real_custom_dip_operator_run"
DIP_WORK_CHAIN_JOIN_PACKET_KIND = "wbp_dip_work_chain_join"
DIP_OPERATOR_READINESS_PACKET_KIND = "wbp_dip_operator_readiness"

REAL_CUSTOM_DIP_OPERATOR_OK = "OK"
REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED = (
    "WBP_REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED"
)
REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED = "WBP_REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED"
REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_BLOCKED = (
    "WBP_REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_BLOCKED"
)
REAL_CUSTOM_DIP_OPERATOR_RUN_BLOCKED = "WBP_REAL_CUSTOM_DIP_OPERATOR_RUN_BLOCKED"
REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET = "WBP_REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET"
DIP_OPERATOR_READINESS_BLOCKED = "WBP_DIP_OPERATOR_READINESS_BLOCKED"
DIP_OPERATOR_READINESS_PROOF_MISSING = "WBP_DIP_OPERATOR_READINESS_PROOF_MISSING"
DIP_OPERATOR_READINESS_STALE = "WBP_DIP_OPERATOR_READINESS_STALE"
DIP_OPERATOR_READINESS_UNSAFE = "WBP_DIP_OPERATOR_READINESS_UNSAFE"
DIP_WORK_CHAIN_JOIN_BLOCKED = "WBP_DIP_WORK_CHAIN_JOIN_BLOCKED"
DIP_WORK_CHAIN_JOIN_UNSAFE = "WBP_DIP_WORK_CHAIN_JOIN_UNSAFE"

ACCEPTANCE_RUNS_DEFAULT = 5
ACCEPTANCE_RUNS_MIN = 2
ACCEPTANCE_RUNS_MAX = 10
DIP_OPERATOR_STATUS_MAX_AGE_SECONDS_DEFAULT = 24 * 60 * 60

OPERATOR_STATUS_READY = "ready"
OPERATOR_STATUS_BLOCKED = "blocked"

OPERATOR_RECOVERY_ACTION_RUN_WORK = "run_work"
OPERATOR_RECOVERY_ACTION_REFRESH_ACCEPTANCE = "refresh_acceptance"
OPERATOR_RECOVERY_ACTION_STOP = "stop"

OPERATOR_RECOVERY_COMMAND_DIP_WORK = "dip_work"
OPERATOR_RECOVERY_COMMAND_DIP_ACCEPTANCE = "dip_acceptance"
OPERATOR_RECOVERY_COMMAND_NONE = "none"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    try:
        if path.is_file():
            return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""
    return ""


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _safe_changed_files(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _merge_changed_files(packets_to_merge: Sequence[Mapping[str, Any]]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for packet in packets_to_merge:
        for changed_file in _safe_changed_files(packet.get("changed_files")):
            if changed_file not in seen:
                seen.add(changed_file)
                merged.append(changed_file)
    return merged


def _runtime_secret_values(context: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(context, Mapping):
        return []
    values: list[str] = []
    for key in ("allowed_api_route_ids", "forbidden_stale_route_ids"):
        raw = context.get(key)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend(item for item in raw if isinstance(item, str) and item)
    for key in ("agent_id_to_route",):
        raw_map = context.get(key)
        if isinstance(raw_map, Mapping):
            values.extend(
                item for item in raw_map.values() if isinstance(item, str) and item
            )
    raw_bindings = context.get("agent_bindings")
    if isinstance(raw_bindings, Sequence) and not isinstance(raw_bindings, (str, bytes)):
        for raw_binding in raw_bindings:
            if isinstance(raw_binding, Mapping):
                route = raw_binding.get("route_id")
                if isinstance(route, str) and route:
                    values.append(route)
    return sorted(set(values))


def _repo_root_from_cwd(codex_cwd: str | None) -> Path:
    if codex_cwd:
        return Path(codex_cwd).expanduser().resolve()
    return Path.cwd().resolve()


def _codex_executable(paths: RuntimePaths, codex_bin: str | None) -> Path:
    if codex_bin:
        return Path(codex_bin).expanduser()
    return default_codex_bin({"WBP_PROFILE_DIR": str(paths.profile_dir)})


def _writable_existing_ancestor(path: Path) -> bool:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate.exists() and os.access(candidate, os.W_OK | os.X_OK)


def _proof_output_parent_writable(paths: RuntimePaths, proof_dir: str | None) -> bool:
    if proof_dir:
        target = Path(proof_dir).expanduser()
        if target.exists():
            return target.is_dir() and os.access(target, os.W_OK | os.X_OK)
        return _writable_existing_ancestor(target.parent)
    target = paths.managed_dir / "codex-runner" / "real-custom-dip-proof"
    if target.exists():
        return target.is_dir() and os.access(target, os.W_OK | os.X_OK)
    return _writable_existing_ancestor(target.parent)


def _acceptance_proof_root(paths: RuntimePaths, proof_dir: str | None) -> Path:
    if proof_dir:
        return Path(proof_dir).expanduser()
    return paths.managed_dir / "codex-runner" / "real-custom-dip-acceptance"


def _acceptance_run_proof_dir(base_proof_root: Path, run_number: int) -> Path:
    return base_proof_root / f"run-{run_number:02d}"


def _acceptance_packet_output_path(base_proof_root: Path) -> Path:
    return base_proof_root / "real-custom-dip-operator-acceptance.packet.json"


def _run_proof_root(paths: RuntimePaths, proof_dir: str | None) -> Path:
    if proof_dir:
        return Path(proof_dir).expanduser()
    return paths.managed_dir / "codex-runner" / "real-custom-dip-run"


def _run_status_packet_output_path(base_proof_root: Path) -> Path:
    return base_proof_root / "dip-run-status.packet.json"


def _run_work_packet_output_path(base_proof_root: Path) -> Path:
    return base_proof_root / "dip-run-work.packet.json"


def _run_chain_join_packet_output_path(base_proof_root: Path) -> Path:
    return base_proof_root / "dip-run-chain-join.packet.json"


def _run_packet_output_path(base_proof_root: Path) -> Path:
    return base_proof_root / "real-custom-dip-operator-run.packet.json"


def _acceptance_packet_search_roots(paths: RuntimePaths) -> list[Path]:
    return [
        paths.managed_dir / "codex-runner" / "real-custom-dip-acceptance",
        paths.managed_dir / "direct-provider-positive-proof",
    ]


def _find_latest_acceptance_packet(paths: RuntimePaths) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for root in _acceptance_packet_search_roots(paths):
        try:
            if root.is_dir():
                for path in root.glob(
                    "**/real-custom-dip-operator-acceptance.packet.json"
                ):
                    try:
                        if path.is_file():
                            candidates.append((path.stat().st_mtime, path))
                    except OSError:
                        continue
        except OSError:
            continue
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _evidence_root_from_packet(packet: Mapping[str, Any]) -> str:
    changed_files = _safe_changed_files(packet.get("changed_files"))
    if not changed_files:
        return ""
    return str(Path(changed_files[0]).expanduser().parent)


def _changed_files_present(packet: Mapping[str, Any]) -> bool:
    changed_files = _safe_changed_files(packet.get("changed_files"))
    return bool(changed_files) and all(Path(path).expanduser().is_file() for path in changed_files)


def _packet_file_age_seconds(path: Path, now: float | None = None) -> int:
    try:
        reference = time.time() if now is None else now
        return max(0, int(reference - path.stat().st_mtime))
    except OSError:
        return 0


def _load_json_packet(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None, "read_error"
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return None, "invalid_json"
    if not isinstance(loaded, dict):
        return None, "json_not_object"
    return loaded, ""


def _persist_acceptance_packet(
    packet: Mapping[str, Any],
    *,
    base_proof_root: Path,
) -> dict[str, Any]:
    packet_path = _acceptance_packet_output_path(base_proof_root)
    changed_files = _safe_changed_files(packet.get("changed_files"))
    packet_path_text = str(packet_path)
    if packet_path_text not in changed_files:
        changed_files.append(packet_path_text)
    persisted = dict(packet)
    persisted.update(
        {
            "changed_files": changed_files,
            "acceptance_packet_file_written": True,
            "acceptance_packet_path_digest": _sha256_text(
                str(packet_path.expanduser().resolve(strict=False))
            ),
            "acceptance_packet_path_recorded": False,
        }
    )
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        json.dumps(persisted, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return persisted


def _persist_json_packet(
    path: Path,
    packet: Mapping[str, Any],
    *,
    secret_values: Sequence[str] | None = None,
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    redacted = packets.redact_command_packet(
        dict(packet),
        secret_values=list(secret_values or []),
    )
    path.write_text(
        json.dumps(redacted, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(path)


def _with_persisted_acceptance_packet(
    packet: Mapping[str, Any],
    *,
    base_proof_root: Path,
) -> dict[str, Any]:
    try:
        return _persist_acceptance_packet(packet, base_proof_root=base_proof_root)
    except OSError as exc:
        blocking_reasons = sorted(
            set(
                _safe_reasons(packet.get("blocking_reasons"))
                + ["acceptance_packet_write_failed"]
            )
        )
        failed = dict(packet)
        failed.update(
            {
                "status": "error",
                "exit_code": 1,
                "human_message": (
                    "WBP DIP operator acceptance gate is BLOCKED; "
                    "top-level acceptance packet was not written."
                ),
                "machine_error_code": REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_BLOCKED,
                "next_action": "stop",
                "operator_action": "stop",
                "operator_status": OPERATOR_STATUS_BLOCKED,
                "acceptance_passed": False,
                "blocked": True,
                "acceptance_packet_file_written": False,
                "acceptance_packet_write_error": _safe_text(
                    type(exc).__name__,
                    limit=80,
                ),
                "reason_codes": blocking_reasons,
                "blocking_reasons": blocking_reasons,
            }
        )
        return failed


def _normalize_acceptance_runs(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _hook_ready(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("status") == "ok"
        and packet.get("machine_error_code") == HOOK_CONFIG_OK
        and packet.get("hook_enabled") is True
        and packet.get("hook_trusted") is True
        and packet.get("hook_config_digest_bound") is True
    )


def _preflight_blocking_reasons(
    *,
    prompt_present: bool,
    context_metadata: Mapping[str, Any],
    intent_packet: Mapping[str, Any],
    hook_readiness_packet: Mapping[str, Any],
    codex_binary_executable: bool,
    wbp_dip_tool_present: bool,
    proof_output_writable: bool,
) -> list[str]:
    reasons: list[str] = []
    if not prompt_present:
        reasons.append("prompt_required")
    if context_metadata.get("runtime_context_file_read") is not True:
        reasons.append("runtime_context_file_not_read")
    if context_metadata.get("runtime_context_file_valid_json") is not True:
        reasons.append("runtime_context_file_json_not_valid")
    if context_metadata.get("runtime_context_file_mapping") is not True:
        reasons.append("runtime_context_file_not_mapping")
    if intent_packet.get("status") != "ok":
        reasons.append("natural_intent_preflight_blocked")
    reasons.extend(_safe_reasons(intent_packet.get("blocking_reasons")))
    if not _hook_ready(hook_readiness_packet):
        reasons.append("user_prompt_submit_hook_not_ready")
    reasons.extend(_safe_reasons(hook_readiness_packet.get("blocking_reasons")))
    if not codex_binary_executable:
        reasons.append("codex_binary_not_executable")
    if not wbp_dip_tool_present:
        reasons.append("wbp_dip_tool_missing")
    if not proof_output_writable:
        reasons.append("proof_output_not_writable")
    return sorted(set(reasons))


def build_real_custom_dip_operator_preflight_packet(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    context_path = runtime_context_path(paths=paths)
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    secret_values = [prompt] if prompt else []
    secret_values.extend(_runtime_secret_values(runtime_context))
    intent_packet = build_natural_intent_parser_packet(
        prompt_text=prompt,
        runtime_context=runtime_context,
        source_surface=SOURCE_SURFACE_DECLARED_CUSTOM_CODEX_FLOW,
        secret_values=secret_values,
    )
    explicit_hook_hash = _safe_text(codex_hook_current_hash, limit=80)
    probe_live_hook_state = bool(probe_codex_app_server or not explicit_hook_hash)
    hook_hash = explicit_hook_hash if explicit_hook_hash else ""
    hook_readiness = build_user_prompt_submit_readiness_packet(
        paths=paths,
        codex_hook_current_hash=hook_hash,
        probe_codex_app_server=probe_live_hook_state,
    )
    codex_exe = _codex_executable(paths, codex_bin)
    repo_root = _repo_root_from_cwd(codex_cwd)
    codex_binary_executable = codex_exe.is_file() and os.access(codex_exe, os.X_OK)
    wbp_dip_tool_present = (repo_root / "tools" / "wbp_dip").is_file()
    proof_output_writable = _proof_output_parent_writable(paths, proof_dir)
    blocking_reasons = _preflight_blocking_reasons(
        prompt_present=bool(prompt),
        context_metadata=context_metadata,
        intent_packet=intent_packet,
        hook_readiness_packet=hook_readiness,
        codex_binary_executable=codex_binary_executable,
        wbp_dip_tool_present=wbp_dip_tool_present,
        proof_output_writable=proof_output_writable,
    )
    preflight_ready = not blocking_reasons
    unsafe_payload = {
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "runtime_context_digest": _sha256_file(context_path),
        "selected_alias": intent_packet.get("alias_candidate"),
        "slot_candidate": intent_packet.get("slot_candidate"),
        "intent_status": intent_packet.get("intent_status"),
        "hook_readiness_machine_error_code": hook_readiness.get("machine_error_code"),
        "blocking_reasons": blocking_reasons,
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=secret_values,
    )
    ok = preflight_ready and not unsafe
    machine_error_code = (
        REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET
        if unsafe
        else REAL_CUSTOM_DIP_OPERATOR_OK
        if ok
        else REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_BLOCKED
    )
    selected_alias = _safe_text(intent_packet.get("alias_candidate"), limit=80)
    extra = {
        **dict(context_metadata),
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_PREFLIGHT_PACKET_KIND,
        "proof_scope": "real_custom_dip_operator_command_surface_preflight",
        "operator_command_surface": "wild-boar-proxy dip preflight",
        "operator_command_mode": "preflight",
        "operator_status": OPERATOR_STATUS_READY if ok else OPERATOR_STATUS_BLOCKED,
        "preflight_ready": ok,
        "blocked": not ok,
        "reason_codes": sorted(
            set(
                blocking_reasons
                + (["operator_preflight_packet_secret_leak"] if unsafe else [])
            )
        ),
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "prompt_digest_present": bool(prompt),
        "runtime_context_digest": _sha256_file(context_path),
        "runtime_context_file_path_recorded": False,
        "natural_intent_packet_kind": _safe_text(
            intent_packet.get("packet_kind"),
            limit=96,
        ),
        "natural_intent_status": _safe_text(
            intent_packet.get("intent_status"),
            limit=96,
        ),
        "natural_intent_preflight_status": _safe_text(
            intent_packet.get("contract_preflight_status"),
            limit=96,
        ),
        "natural_intent_passed": intent_packet.get("intent_status") == INTENT_PASS,
        "natural_intent_contract_preflight_passed": (
            intent_packet.get("contract_preflight_status") == PREFLIGHT_PASS
        ),
        "parser_used": intent_packet.get("parser_used") is True,
        "parser_selected_alias_from_runtime_context": (
            intent_packet.get("parser_selected_alias_from_runtime_context") is True
        ),
        "ambiguous_intent": intent_packet.get("ambiguous_intent") is True,
        "selected_alias": selected_alias,
        "selected_alias_present": bool(selected_alias),
        "selected_slot": _safe_text(intent_packet.get("slot_candidate"), limit=80),
        "selected_lane": _safe_text(intent_packet.get("lane_candidate"), limit=80),
        "alias_bound": intent_packet.get("alias_bound") is True,
        "alias_context_read": intent_packet.get("alias_context_read") is True,
        "route_id_allowed": intent_packet.get("route_id_allowed") is True,
        "allowed_api_route_ids_enforced": (
            intent_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "allowed_api_route_ids_count": int(
            intent_packet.get("allowed_api_route_ids_count") or 0
        ),
        "forbidden_stale_route_ids_enforced": (
            intent_packet.get("forbidden_stale_route_ids_enforced") is True
        ),
        "forbidden_stale_route_ids_count": int(
            intent_packet.get("forbidden_stale_route_ids_count") or 0
        ),
        "user_prompt_submit_hook_ready": _hook_ready(hook_readiness),
        "hook_readiness_machine_error_code": _safe_text(
            hook_readiness.get("machine_error_code"),
            limit=128,
        ),
        "hook_readiness_status": _safe_text(hook_readiness.get("status"), limit=32),
        "hook_enabled": hook_readiness.get("hook_enabled") is True,
        "hook_trusted": hook_readiness.get("hook_trusted") is True,
        "hook_config_digest_bound": (
            hook_readiness.get("hook_config_digest_bound") is True
        ),
        "codex_binary_executable": codex_binary_executable,
        "codex_binary_path_recorded": False,
        "wbp_dip_tool_present": wbp_dip_tool_present,
        "repo_root_path_recorded": False,
        "proof_output_writable": proof_output_writable,
        "proof_dir_path_recorded": False,
        "provider_preflight_called": False,
        "provider_lane_preflight_is_dispatch_proof": False,
        "work_runner_called": False,
        "api_lane_called": False,
        "dispatch_proven": False,
        "work_mode_proven": False,
        "single_work_run_proven": False,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "custom_codex_flow_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "file_mutation_attempted": False,
        "blocking_reasons": sorted(
            set(
                blocking_reasons
                + (["operator_preflight_packet_secret_leak"] if unsafe else [])
            )
        ),
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP DIP operator preflight is ready; no dispatch was attempted."
            if ok
            else "WBP DIP operator preflight is BLOCKED; no dispatch was attempted."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        secret_values=secret_values,
        extra=extra,
    )


def run_real_custom_dip_operator_preflight_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    return build_real_custom_dip_operator_preflight_packet(
        paths=paths,
        prompt_text=prompt_text,
        codex_bin=codex_bin,
        proof_dir=proof_dir,
        codex_cwd=codex_cwd,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )


def build_real_custom_dip_operator_work_packet(
    *,
    prompt_text: object,
    preflight_packet: Mapping[str, Any],
    runner_packet: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    runner = dict(runner_packet or {})
    runner_called = bool(runner)
    preflight_ready = preflight_packet.get("preflight_ready") is True
    runner_ok = bool(
        runner_called
        and runner.get("status") == "ok"
        and runner.get("machine_error_code") == "OK"
        and runner.get("operator_command_mode") == REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK
        and runner.get("work_mode_proven") is True
        and runner.get("single_work_run_proven") is True
        and runner.get("api_lane_called") is True
        and runner.get("fallback_used") is False
        and runner.get("local_imitation_used") is False
        and runner.get("native_codex_subagent_used_as_dip") is False
        and runner.get("product_ready") is False
    )
    unsafe_payload = {
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND,
        "prompt_digest": _sha256_text(_safe_text(prompt_text, limit=4096))
        if _safe_text(prompt_text, limit=4096)
        else "",
        "preflight_machine_error_code": preflight_packet.get("machine_error_code"),
        "runner_machine_error_code": runner.get("machine_error_code"),
        "runner_changed_files_count": len(_safe_changed_files(runner.get("changed_files"))),
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values or []),
    )
    ok = bool(preflight_ready and runner_ok and not unsafe)
    blocking_reasons = sorted(
        set(
            (
                []
                if preflight_ready
                else ["preflight_not_ready"]
                + _safe_reasons(preflight_packet.get("blocking_reasons"))
            )
            + ([] if runner_ok or not runner_called else ["runner_work_not_proven"])
            + _safe_reasons(runner.get("blocking_reasons"))
            + (["operator_work_packet_secret_leak"] if unsafe else [])
        )
    )
    runner_machine_error = _safe_text(runner.get("machine_error_code"), limit=128)
    machine_error_code = (
        REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET
        if unsafe
        else REAL_CUSTOM_DIP_OPERATOR_OK
        if ok
        else runner_machine_error
        if runner_called and runner_machine_error and runner_machine_error != "OK"
        else REAL_CUSTOM_DIP_OPERATOR_WORK_BLOCKED
    )
    changed_files = _safe_changed_files(runner.get("changed_files")) if runner_called else []
    extra = {
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND,
        "proof_scope": "real_custom_dip_operator_command_surface_work",
        "operator_command_surface": "wild-boar-proxy dip work",
        "operator_command_mode": "work",
        "operator_status": OPERATOR_STATUS_READY if ok else OPERATOR_STATUS_BLOCKED,
        "work_ready": ok,
        "blocked": not ok,
        "reason_codes": blocking_reasons,
        "status_packet_consulted": False,
        "status_packet_used_as_auth_grant": False,
        "status_recommendation_is_not_auth_grant": True,
        "status_recommendation_bypasses_preflight": False,
        "acceptance_readiness_packet_required": False,
        "acceptance_is_not_dip_work_prerequisite": True,
        "preflight_checked": True,
        "preflight_ready": preflight_ready,
        "work_preflight_rechecked_runtime_context": (
            preflight_packet.get("runtime_context_file_read") is True
        ),
        "work_preflight_rechecked_allowlist": (
            preflight_packet.get("allowed_api_route_ids_enforced") is True
        ),
        "work_alias_context_read_by_preflight": (
            preflight_packet.get("alias_context_read") is True
        ),
        "work_route_allowed_by_preflight": (
            preflight_packet.get("route_id_allowed") is True
        ),
        "preflight_packet_kind": _safe_text(
            preflight_packet.get("packet_kind"),
            limit=96,
        ),
        "preflight_machine_error_code": _safe_text(
            preflight_packet.get("machine_error_code"),
            limit=128,
        ),
        "selected_alias": _safe_text(preflight_packet.get("selected_alias"), limit=80),
        "selected_alias_present": preflight_packet.get("selected_alias_present") is True,
        "selected_slot": _safe_text(preflight_packet.get("selected_slot"), limit=80),
        "selected_lane": _safe_text(preflight_packet.get("selected_lane"), limit=80),
        "runner_called": runner_called,
        "runner_packet_kind": _safe_text(runner.get("packet_kind"), limit=96),
        "runner_machine_error_code": runner_machine_error,
        "runner_status": _safe_text(runner.get("status"), limit=32),
        "runner_changed_files_count": len(changed_files),
        "evidence_changed_files_count": len(changed_files),
        "runner_required_run_count": int(runner.get("required_run_count") or 0),
        "runner_run_count": int(runner.get("run_count") or 0),
        "work_mode_proven": ok,
        "single_work_run_proven": bool(ok and runner.get("single_work_run_proven") is True),
        "work_mode_cannot_mint_admission_proof": True,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "real_custom_codex_hook_origin_dip_proof_proven": False,
        "two_runs_proven": False,
        "custom_codex_flow_proven": bool(
            ok and runner.get("custom_codex_flow_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            ok and runner.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": bool(
            ok and runner.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            ok and runner.get("hook_runtime_context_digest_bound") is True
        ),
        "delegate_to_dip_proven": bool(ok and runner.get("delegate_to_dip_proven") is True),
        "api_lane_called": bool(ok and runner.get("api_lane_called") is True),
        "route_bound_dispatch_proven": bool(
            ok and runner.get("route_bound_dispatch_proven") is True
        ),
        "live_result_available": bool(ok and runner.get("live_result_available") is True),
        "direct_provider_auth_proven": bool(
            ok and runner.get("direct_provider_auth_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            ok and runner.get("codex_working_flow_delivery_proven") is True
        ),
        "approved_delivery_surface_proven": bool(
            ok and runner.get("approved_delivery_surface_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": bool(
            ok and runner.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": runner.get("fallback_used") is True,
        "local_imitation_used": runner.get("local_imitation_used") is True,
        "native_codex_subagent_used_as_dip": (
            runner.get("native_codex_subagent_used_as_dip") is True
        ),
        "codex_native_subagent_used_as_dip": (
            runner.get("codex_native_subagent_used_as_dip") is True
        ),
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP DIP operator work command completed with proof-backed live dispatch."
            if ok
            else "WBP DIP operator work command is BLOCKED."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_real_custom_dip_operator_work_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = 300,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    context_path = runtime_context_path(paths=paths)
    runtime_context, _context_metadata = load_runtime_context_packet(context_path)
    secret_values = [prompt] if prompt else []
    secret_values.extend(_runtime_secret_values(runtime_context))
    preflight = build_real_custom_dip_operator_preflight_packet(
        paths=paths,
        prompt_text=prompt,
        codex_bin=codex_bin,
        proof_dir=proof_dir,
        codex_cwd=codex_cwd,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    if preflight.get("preflight_ready") is not True:
        return build_real_custom_dip_operator_work_packet(
            prompt_text=prompt,
            preflight_packet=preflight,
            runner_packet=None,
            secret_values=secret_values,
        )
    runner_packet = run_real_custom_dip_proof_runner_command(
        paths=paths,
        prompt_text=prompt,
        codex_bin=codex_bin,
        codex_model=codex_model or DEFAULT_MODEL,
        proof_dir=proof_dir,
        codex_cwd=codex_cwd,
        expected_alias=str(preflight.get("selected_alias") or "DIP"),
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
        run_mode=REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK,
    )
    return build_real_custom_dip_operator_work_packet(
        prompt_text=prompt,
        preflight_packet=preflight,
        runner_packet=runner_packet,
        secret_values=secret_values,
    )


def _acceptance_run_failures(index: int, packet: Mapping[str, Any]) -> list[str]:
    prefix = f"run_{index}_"
    failures: list[str] = []
    if packet.get("status") != "ok":
        failures.append(prefix + "status_not_ok")
    if packet.get("machine_error_code") != REAL_CUSTOM_DIP_OPERATOR_OK:
        failures.append(prefix + "machine_error_not_ok")
    if packet.get("work_mode_proven") is not True:
        failures.append(prefix + "work_mode_not_proven")
    if packet.get("single_work_run_proven") is not True:
        failures.append(prefix + "single_work_run_not_proven")
    if packet.get("api_lane_called") is not True:
        failures.append(prefix + "api_lane_not_called")
    if packet.get("codex_working_flow_delivery_proven") is not True:
        failures.append(prefix + "delivery_not_proven")
    if packet.get("fallback_used") is not False:
        failures.append(prefix + "fallback_used")
    if packet.get("local_imitation_used") is not False:
        failures.append(prefix + "local_imitation_used")
    if packet.get("native_codex_subagent_used_as_dip") is not False:
        failures.append(prefix + "native_codex_subagent_used_as_dip")
    if packet.get("proof_mode_admission_proven") is not False:
        failures.append(prefix + "proof_mode_admission_minted")
    if packet.get("repeatable_real_custom_dip_proof_proven") is not False:
        failures.append(prefix + "repeatable_proof_minted")
    if packet.get("real_custom_codex_hook_origin_dip_proof_proven") is not False:
        failures.append(prefix + "admission_origin_proof_minted")
    if packet.get("product_ready") is not False:
        failures.append(prefix + "product_ready_claimed")
    if not _changed_files_present(packet):
        failures.append(prefix + "evidence_files_missing")
    failures.extend(prefix + reason for reason in _safe_reasons(packet.get("blocking_reasons")))
    return sorted(set(failures))


def build_real_custom_dip_operator_acceptance_packet(
    *,
    prompt_text: object,
    requested_runs: int,
    preflight_packet: Mapping[str, Any] | None,
    work_packets: Sequence[Mapping[str, Any]],
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    preflight = dict(preflight_packet or {})
    runs = [dict(packet) for packet in work_packets]
    run_count_valid = ACCEPTANCE_RUNS_MIN <= requested_runs <= ACCEPTANCE_RUNS_MAX
    completed_count = len(runs)
    evidence_roots = [_evidence_root_from_packet(packet) for packet in runs]
    evidence_root_digests = [
        _sha256_text(root) for root in evidence_roots if root
    ]
    evidence_roots_distinct = bool(
        completed_count > 0
        and len(evidence_roots) == completed_count
        and all(evidence_roots)
        and len(set(evidence_roots)) == completed_count
    )
    preflight_ready = preflight.get("preflight_ready") is True
    run_failures = [
        failure
        for index, packet in enumerate(runs, start=1)
        for failure in _acceptance_run_failures(index, packet)
    ]
    unsafe_input = [preflight, *runs]
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_input,
        secret_values=list(secret_values or []),
    )
    blocking_reasons: list[str] = []
    if not run_count_valid:
        blocking_reasons.append("acceptance_run_count_out_of_range")
    if run_count_valid and not preflight_ready:
        blocking_reasons.append("preflight_not_ready")
        blocking_reasons.extend(_safe_reasons(preflight.get("blocking_reasons")))
    if run_count_valid and preflight_ready and completed_count != requested_runs:
        blocking_reasons.append("acceptance_run_count_not_completed")
    if completed_count and not evidence_roots_distinct:
        blocking_reasons.append("evidence_roots_not_distinct")
    blocking_reasons.extend(run_failures)
    if unsafe:
        blocking_reasons.append("operator_acceptance_packet_secret_leak")
    blocking_reasons = sorted(set(blocking_reasons))

    all_runs_work_mode_proven = bool(
        completed_count == requested_runs
        and completed_count > 0
        and all(packet.get("work_mode_proven") is True for packet in runs)
    )
    all_runs_api_lane_called = bool(
        completed_count == requested_runs
        and completed_count > 0
        and all(packet.get("api_lane_called") is True for packet in runs)
    )
    all_runs_delivery_proven = bool(
        completed_count == requested_runs
        and completed_count > 0
        and all(packet.get("codex_working_flow_delivery_proven") is True for packet in runs)
    )
    all_runs_no_fallback = all(packet.get("fallback_used") is False for packet in runs)
    all_runs_no_local_imitation = all(
        packet.get("local_imitation_used") is False for packet in runs
    )
    all_runs_no_native_codex_subagent_as_dip = all(
        packet.get("native_codex_subagent_used_as_dip") is False for packet in runs
    )
    all_runs_no_admission_mint = all(
        packet.get("proof_mode_admission_proven") is False
        and packet.get("repeatable_real_custom_dip_proof_proven") is False
        and packet.get("real_custom_codex_hook_origin_dip_proof_proven") is False
        for packet in runs
    )
    all_runs_product_not_ready = all(packet.get("product_ready") is False for packet in runs)
    acceptance_passed = bool(
        run_count_valid
        and preflight_ready
        and completed_count == requested_runs
        and all_runs_work_mode_proven
        and all_runs_api_lane_called
        and all_runs_delivery_proven
        and all_runs_no_fallback
        and all_runs_no_local_imitation
        and all_runs_no_native_codex_subagent_as_dip
        and all_runs_no_admission_mint
        and all_runs_product_not_ready
        and evidence_roots_distinct
        and not unsafe
        and not blocking_reasons
    )
    changed_files = _merge_changed_files(runs)
    stopped_on_run = 0
    if run_failures:
        first_failure = run_failures[0].split("_", 2)
        if len(first_failure) >= 2 and first_failure[0] == "run":
            try:
                stopped_on_run = int(first_failure[1])
            except ValueError:
                stopped_on_run = completed_count
    elif run_count_valid and preflight_ready and completed_count < requested_runs:
        stopped_on_run = completed_count + 1
    extra = {
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_PACKET_KIND,
        "proof_scope": "real_custom_dip_operator_acceptance_gate",
        "operator_command_surface": "wild-boar-proxy dip acceptance",
        "operator_command_mode": "acceptance",
        "operator_status": OPERATOR_STATUS_READY
        if acceptance_passed
        else OPERATOR_STATUS_BLOCKED,
        "acceptance_passed": acceptance_passed,
        "blocked": not acceptance_passed,
        "acceptance_run_count_requested": requested_runs,
        "acceptance_run_count_min": ACCEPTANCE_RUNS_MIN,
        "acceptance_run_count_max": ACCEPTANCE_RUNS_MAX,
        "acceptance_run_count_valid": run_count_valid,
        "acceptance_run_count_completed": completed_count,
        "acceptance_successful_run_count": sum(
            1 for packet in runs if packet.get("status") == "ok"
        ),
        "acceptance_stopped_on_run": stopped_on_run,
        "preflight_checked": bool(preflight),
        "preflight_ready": preflight_ready,
        "preflight_packet_kind": _safe_text(preflight.get("packet_kind"), limit=96),
        "preflight_machine_error_code": _safe_text(
            preflight.get("machine_error_code"),
            limit=128,
        ),
        "all_runs_work_mode_proven": all_runs_work_mode_proven,
        "all_runs_api_lane_called": all_runs_api_lane_called,
        "all_runs_delivery_proven": all_runs_delivery_proven,
        "all_runs_no_fallback": all_runs_no_fallback,
        "all_runs_no_local_imitation": all_runs_no_local_imitation,
        "all_runs_no_native_codex_subagent_as_dip": (
            all_runs_no_native_codex_subagent_as_dip
        ),
        "all_runs_no_admission_mint": all_runs_no_admission_mint,
        "all_runs_product_not_ready": all_runs_product_not_ready,
        "evidence_roots_distinct": evidence_roots_distinct,
        "evidence_root_count": len(evidence_roots),
        "evidence_root_digests": evidence_root_digests,
        "evidence_root_paths_recorded": False,
        "evidence_changed_files_count": len(changed_files),
        "acceptance_is_not_dip_work_prerequisite": True,
        "custom_codex_flow_proven": bool(
            acceptance_passed
            and all(packet.get("custom_codex_flow_proven") is True for packet in runs)
        ),
        "user_prompt_submit_hook_ran": bool(
            acceptance_passed
            and all(packet.get("user_prompt_submit_hook_ran") is True for packet in runs)
        ),
        "hook_prompt_digest_bound": bool(
            acceptance_passed
            and all(packet.get("hook_prompt_digest_bound") is True for packet in runs)
        ),
        "hook_runtime_context_digest_bound": bool(
            acceptance_passed
            and all(
                packet.get("hook_runtime_context_digest_bound") is True
                for packet in runs
            )
        ),
        "api_lane_called": all_runs_api_lane_called,
        "work_mode_proven": all_runs_work_mode_proven,
        "codex_working_flow_delivery_proven": all_runs_delivery_proven,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "real_custom_codex_hook_origin_dip_proof_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "fallback_used": not all_runs_no_fallback,
        "local_imitation_used": not all_runs_no_local_imitation,
        "native_codex_subagent_used_as_dip": (
            not all_runs_no_native_codex_subagent_as_dip
        ),
        "codex_native_subagent_used_as_dip": (
            not all_runs_no_native_codex_subagent_as_dip
        ),
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "run_summaries_recorded": True,
        "run_summaries": [
            {
                "run_index": index,
                "status": _safe_text(packet.get("status"), limit=32),
                "machine_error_code": _safe_text(
                    packet.get("machine_error_code"),
                    limit=128,
                ),
                "work_mode_proven": packet.get("work_mode_proven") is True,
                "api_lane_called": packet.get("api_lane_called") is True,
                "codex_working_flow_delivery_proven": (
                    packet.get("codex_working_flow_delivery_proven") is True
                ),
                "fallback_used": packet.get("fallback_used") is True,
                "local_imitation_used": packet.get("local_imitation_used") is True,
                "native_codex_subagent_used_as_dip": (
                    packet.get("native_codex_subagent_used_as_dip") is True
                ),
                "proof_mode_admission_proven": (
                    packet.get("proof_mode_admission_proven") is True
                ),
                "repeatable_real_custom_dip_proof_proven": (
                    packet.get("repeatable_real_custom_dip_proof_proven") is True
                ),
                "product_ready": packet.get("product_ready") is True,
                "evidence_root_digest": _sha256_text(evidence_roots[index - 1])
                if index - 1 < len(evidence_roots) and evidence_roots[index - 1]
                else "",
                "evidence_root_path_recorded": False,
                "changed_files_count": len(_safe_changed_files(packet.get("changed_files"))),
            }
            for index, packet in enumerate(runs, start=1)
        ],
        "reason_codes": blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=acceptance_passed,
        human_message=(
            "WBP DIP operator acceptance gate passed."
            if acceptance_passed
            else "WBP DIP operator acceptance gate is BLOCKED."
        ),
        machine_error_code=REAL_CUSTOM_DIP_OPERATOR_OK
        if acceptance_passed
        else REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET
        if unsafe
        else REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_BLOCKED,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if acceptance_passed else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=list(secret_values or []),
        extra=extra,
    )


def run_real_custom_dip_operator_acceptance_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    runs: int = ACCEPTANCE_RUNS_DEFAULT,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = 300,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    selected_runs = _normalize_acceptance_runs(runs)
    context_path = runtime_context_path(paths=paths)
    runtime_context, _context_metadata = load_runtime_context_packet(context_path)
    secret_values = [prompt] if prompt else []
    secret_values.extend(_runtime_secret_values(runtime_context))
    base_proof_root = _acceptance_proof_root(paths, proof_dir)
    if not (ACCEPTANCE_RUNS_MIN <= selected_runs <= ACCEPTANCE_RUNS_MAX):
        return _with_persisted_acceptance_packet(
            build_real_custom_dip_operator_acceptance_packet(
                prompt_text=prompt,
                requested_runs=selected_runs,
                preflight_packet=None,
                work_packets=[],
                secret_values=secret_values,
            ),
            base_proof_root=base_proof_root,
        )
    preflight = build_real_custom_dip_operator_preflight_packet(
        paths=paths,
        prompt_text=prompt,
        codex_bin=codex_bin,
        proof_dir=str(base_proof_root),
        codex_cwd=codex_cwd,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=probe_codex_app_server,
    )
    work_packets: list[dict[str, Any]] = []
    if preflight.get("preflight_ready") is True:
        for run_index in range(1, selected_runs + 1):
            work_packet = run_real_custom_dip_operator_work_command(
                paths=paths,
                prompt_text=prompt,
                codex_bin=codex_bin,
                codex_model=codex_model,
                proof_dir=str(_acceptance_run_proof_dir(base_proof_root, run_index)),
                codex_cwd=codex_cwd,
                sandbox=sandbox,
                timeout_seconds=timeout_seconds,
                codex_hook_current_hash=codex_hook_current_hash,
                probe_codex_app_server=probe_codex_app_server,
            )
            work_packets.append(work_packet)
            if _acceptance_run_failures(run_index, work_packet):
                break
    return _with_persisted_acceptance_packet(
        build_real_custom_dip_operator_acceptance_packet(
            prompt_text=prompt,
            requested_runs=selected_runs,
            preflight_packet=preflight,
            work_packets=work_packets,
            secret_values=secret_values,
        ),
        base_proof_root=base_proof_root,
    )


def _readiness_operator_status(
    *,
    ready: bool,
    proof_found: bool,
    stale: bool,
    unsafe: bool,
) -> str:
    if ready:
        return OPERATOR_STATUS_READY
    if not proof_found:
        return "proof_missing"
    if unsafe:
        return "unsafe"
    if stale:
        return "stale"
    return OPERATOR_STATUS_BLOCKED


def _readiness_machine_error_code(
    *,
    ready: bool,
    proof_found: bool,
    stale: bool,
    unsafe: bool,
) -> str:
    if ready:
        return REAL_CUSTOM_DIP_OPERATOR_OK
    if not proof_found:
        return DIP_OPERATOR_READINESS_PROOF_MISSING
    if unsafe:
        return DIP_OPERATOR_READINESS_UNSAFE
    if stale:
        return DIP_OPERATOR_READINESS_STALE
    return DIP_OPERATOR_READINESS_BLOCKED


def _dip_operator_recovery_decision(
    *,
    ready: bool,
    proof_found: bool,
    blocking_reasons: Sequence[str],
    unsafe: bool,
) -> dict[str, Any]:
    reason_set = set(blocking_reasons)
    invalid_reasons = {
        "acceptance_packet_invalid_json",
        "acceptance_packet_semantic_violation",
        "acceptance_packet_wrong_kind",
        "max_age_seconds_invalid",
    }
    unsafe_reasons = {
        "fallback_used",
        "local_imitation_used",
        "native_codex_subagent_used_as_dip",
        "admission_proof_minted",
        "product_ready_claimed",
        "unsafe_secret_or_raw_backend_claim",
    }
    blocked_reasons = {
        "acceptance_not_passed",
        "acceptance_run_count_not_5",
        "acceptance_work_mode_not_proven",
        "acceptance_api_lane_not_called",
        "acceptance_delivery_not_proven",
        "acceptance_evidence_files_missing",
        "acceptance_evidence_roots_not_distinct",
    }

    recovery_reason_codes: list[str]
    if ready:
        action = OPERATOR_RECOVERY_ACTION_RUN_WORK
        command_kind = OPERATOR_RECOVERY_COMMAND_DIP_WORK
        recovery_reason_codes = ["recovery_ready_run_work"]
    elif reason_set.intersection(invalid_reasons):
        action = OPERATOR_RECOVERY_ACTION_STOP
        command_kind = OPERATOR_RECOVERY_COMMAND_NONE
        recovery_reason_codes = ["recovery_invalid_stop"]
    elif unsafe or reason_set.intersection(unsafe_reasons):
        action = OPERATOR_RECOVERY_ACTION_STOP
        command_kind = OPERATOR_RECOVERY_COMMAND_NONE
        recovery_reason_codes = ["recovery_unsafe_stop"]
    elif reason_set.intersection(blocked_reasons):
        action = OPERATOR_RECOVERY_ACTION_STOP
        command_kind = OPERATOR_RECOVERY_COMMAND_NONE
        recovery_reason_codes = ["recovery_blocked_stop"]
    elif not proof_found or "acceptance_packet_missing" in reason_set:
        action = OPERATOR_RECOVERY_ACTION_REFRESH_ACCEPTANCE
        command_kind = OPERATOR_RECOVERY_COMMAND_DIP_ACCEPTANCE
        recovery_reason_codes = ["recovery_missing_refresh_acceptance"]
    elif "acceptance_packet_stale" in reason_set:
        action = OPERATOR_RECOVERY_ACTION_REFRESH_ACCEPTANCE
        command_kind = OPERATOR_RECOVERY_COMMAND_DIP_ACCEPTANCE
        recovery_reason_codes = ["recovery_stale_refresh_acceptance"]
    else:
        action = OPERATOR_RECOVERY_ACTION_STOP
        command_kind = OPERATOR_RECOVERY_COMMAND_NONE
        recovery_reason_codes = ["recovery_blocked_stop"]

    return {
        "operator_may_run_dip_work": action == OPERATOR_RECOVERY_ACTION_RUN_WORK,
        "operator_may_refresh_acceptance": (
            action == OPERATOR_RECOVERY_ACTION_REFRESH_ACCEPTANCE
        ),
        "operator_must_stop": action == OPERATOR_RECOVERY_ACTION_STOP,
        "recommended_operator_action": action,
        "recommended_command_kind": command_kind,
        "recommended_command_safe_to_show": True,
        "recommended_command_text_recorded": False,
        "raw_prompt_required_from_operator": action == OPERATOR_RECOVERY_ACTION_RUN_WORK,
        "auto_recovery_started": False,
        "auto_dispatch_started": False,
        "auto_acceptance_started": False,
        "recovery_reason_codes": recovery_reason_codes,
    }


def _acceptance_raw_or_secret_claim_present(packet: Mapping[str, Any]) -> bool:
    unsafe_flag_names = (
        "raw_prompt_recorded",
        "prompt_text_recorded",
        "natural_phrase_recorded",
        "raw_route_id_recorded",
        "selected_api_route_id_recorded",
        "raw_provider_response_recorded",
        "provider_response_text_recorded",
        "provider_response_preview_recorded",
        "raw_backend_details_exposed",
        "secret_value_exposed",
    )
    return any(packet.get(flag_name) is True for flag_name in unsafe_flag_names)


def _acceptance_raw_material_present(value: object, *, key: str = "") -> bool:
    normalized_key = key.strip().lower()
    unsafe_key_tokens = (
        "leaked_prompt",
        "raw_prompt",
        "prompt_text",
        "natural_phrase",
        "leaked_route",
        "raw_route_id",
        "selected_api_route_id",
        "provider_response_text",
        "provider_response_preview",
        "raw_provider_response",
        "raw_backend_details",
    )
    unsafe_context = any(token in normalized_key for token in unsafe_key_tokens)
    if isinstance(value, Mapping):
        return any(
            _acceptance_raw_material_present(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(
            _acceptance_raw_material_present(item, key=key)
            for item in value
        )
    return unsafe_context and isinstance(value, str) and bool(value)


def run_dip_operator_status_command(
    *,
    paths: RuntimePaths,
    proof_file: str | None = None,
    max_age_seconds: int | None = DIP_OPERATOR_STATUS_MAX_AGE_SECONDS_DEFAULT,
) -> dict[str, Any]:
    context_path = runtime_context_path(paths=paths)
    runtime_context, _context_metadata = load_runtime_context_packet(context_path)
    secret_values = _runtime_secret_values(runtime_context)
    selected_path = (
        Path(proof_file).expanduser()
        if proof_file
        else _find_latest_acceptance_packet(paths)
    )
    proof_found = bool(selected_path and selected_path.is_file())
    packet: dict[str, Any] = {}
    load_error = ""
    if proof_found and selected_path is not None:
        loaded_packet, load_error = _load_json_packet(selected_path)
        if loaded_packet is not None:
            packet = loaded_packet

    age_seconds = (
        _packet_file_age_seconds(selected_path)
        if proof_found and selected_path is not None
        else 0
    )
    max_age_valid = bool(
        max_age_seconds is None
        or (
            isinstance(max_age_seconds, int)
            and not isinstance(max_age_seconds, bool)
            and max_age_seconds > 0
        )
    )
    fresh = bool(max_age_seconds is None or (max_age_valid and age_seconds <= max_age_seconds))
    semantic_violations = (
        packets.inspect_command_packet_semantics(packet, secret_values=secret_values)
        if packet
        else []
    )
    changed_files = _safe_changed_files(packet.get("changed_files")) if packet else []
    evidence_files_present = bool(changed_files) and all(
        Path(changed_file).expanduser().is_file() for changed_file in changed_files
    )
    unsafe = bool(
        packet
        and (
            packets.command_packet_has_secret_leak(
                packet,
                secret_values=secret_values,
            )
            or _acceptance_raw_or_secret_claim_present(packet)
            or _acceptance_raw_material_present(packet)
        )
    )

    blocking_reasons: list[str] = []
    if not proof_found:
        blocking_reasons.append("acceptance_packet_missing")
    elif load_error:
        reason = (
            "acceptance_packet_invalid_json"
            if load_error in {"invalid_json", "json_not_object"}
            else "acceptance_packet_missing"
        )
        blocking_reasons.append(reason)
    if packet and semantic_violations:
        blocking_reasons.append("acceptance_packet_semantic_violation")
    if packet and packet.get("packet_kind") != REAL_CUSTOM_DIP_OPERATOR_ACCEPTANCE_PACKET_KIND:
        blocking_reasons.append("acceptance_packet_wrong_kind")
    if packet and packet.get("acceptance_passed") is not True:
        blocking_reasons.append("acceptance_not_passed")
    if packet and packet.get("acceptance_run_count_completed") != ACCEPTANCE_RUNS_DEFAULT:
        blocking_reasons.append("acceptance_run_count_not_5")
    if packet and packet.get("all_runs_work_mode_proven") is not True:
        blocking_reasons.append("acceptance_work_mode_not_proven")
    if packet and packet.get("all_runs_api_lane_called") is not True:
        blocking_reasons.append("acceptance_api_lane_not_called")
    if packet and packet.get("all_runs_delivery_proven") is not True:
        blocking_reasons.append("acceptance_delivery_not_proven")
    if packet and not evidence_files_present:
        blocking_reasons.append("acceptance_evidence_files_missing")
    if packet and packet.get("evidence_roots_distinct") is not True:
        blocking_reasons.append("acceptance_evidence_roots_not_distinct")
    if not max_age_valid:
        blocking_reasons.append("max_age_seconds_invalid")
    if packet and max_age_valid and not fresh:
        blocking_reasons.append("acceptance_packet_stale")
    if packet and packet.get("all_runs_no_fallback") is not True:
        blocking_reasons.append("fallback_used")
    if packet and packet.get("all_runs_no_local_imitation") is not True:
        blocking_reasons.append("local_imitation_used")
    if packet and packet.get("all_runs_no_native_codex_subagent_as_dip") is not True:
        blocking_reasons.append("native_codex_subagent_used_as_dip")
    if packet and packet.get("all_runs_no_admission_mint") is not True:
        blocking_reasons.append("admission_proof_minted")
    if packet and packet.get("product_ready") is not False:
        blocking_reasons.append("product_ready_claimed")
    if unsafe:
        blocking_reasons.append("unsafe_secret_or_raw_backend_claim")
    blocking_reasons = sorted(set(blocking_reasons))

    dip_operator_ready = bool(packet and not blocking_reasons)
    operator_status = _readiness_operator_status(
        ready=dip_operator_ready,
        proof_found=proof_found,
        stale="acceptance_packet_stale" in blocking_reasons,
        unsafe=unsafe,
    )
    recovery_decision = _dip_operator_recovery_decision(
        ready=dip_operator_ready,
        proof_found=proof_found,
        blocking_reasons=blocking_reasons,
        unsafe=unsafe,
    )
    selected_path_digest = (
        _sha256_text(str(selected_path.expanduser().resolve(strict=False)))
        if selected_path
        else ""
    )
    extra = {
        "schema_version": 1,
        "packet_kind": DIP_OPERATOR_READINESS_PACKET_KIND,
        "proof_scope": "dip_operator_readiness_from_last_acceptance",
        "operator_command_surface": "wild-boar-proxy dip status",
        "operator_command_mode": "status",
        "operator_status": operator_status,
        "dip_operator_ready": dip_operator_ready,
        "blocked": not dip_operator_ready,
        "last_acceptance_packet_found": proof_found,
        "last_acceptance_packet_valid": bool(packet and not semantic_violations),
        "last_acceptance_packet_valid_json": bool(packet),
        "last_acceptance_packet_semantics_valid": not bool(semantic_violations),
        "last_acceptance_packet_path_digest": selected_path_digest,
        "last_acceptance_packet_path_recorded": False,
        "last_acceptance_passed": packet.get("acceptance_passed") is True,
        "last_acceptance_run_count": int(
            packet.get("acceptance_run_count_completed") or 0
        )
        if packet
        else 0,
        "required_acceptance_run_count": ACCEPTANCE_RUNS_DEFAULT,
        "last_acceptance_api_lane_called": packet.get("all_runs_api_lane_called") is True,
        "last_acceptance_delivery_proven": packet.get("all_runs_delivery_proven") is True,
        "last_acceptance_custom_codex_flow_proven": (
            packet.get("custom_codex_flow_proven") is True
        ),
        "last_acceptance_evidence_roots_distinct": (
            packet.get("evidence_roots_distinct") is True
        ),
        "last_acceptance_evidence_files_present": evidence_files_present,
        "last_acceptance_age_seconds": age_seconds,
        "last_acceptance_max_age_seconds": max_age_seconds or 0,
        "last_acceptance_fresh": fresh,
        "historical_acceptance_passed": packet.get("acceptance_passed") is True,
        "status_command_dispatches": False,
        "status_command_runs_acceptance": False,
        "status_command_reads_audit_history": False,
        "acceptance_is_not_dip_work_prerequisite": True,
        **recovery_decision,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "proof_mode_admission_proven": False,
        "repeatable_real_custom_dip_proof_proven": False,
        "real_custom_codex_hook_origin_dip_proof_proven": False,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "reason_codes": blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=dip_operator_ready,
        human_message=(
            "WBP DIP operator readiness is ready."
            if dip_operator_ready
            else "WBP DIP operator readiness is BLOCKED."
        ),
        machine_error_code=_readiness_machine_error_code(
            ready=dip_operator_ready,
            proof_found=proof_found,
            stale="acceptance_packet_stale" in blocking_reasons,
            unsafe=unsafe,
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if dip_operator_ready else "stop",
        changed_files=[],
        effect=EFFECT_READ,
        secret_values=secret_values,
        extra=extra,
    )


def _read_chain_json_mapping_file(
    path_text: str | None,
    *,
    prefix: str,
) -> tuple[dict[str, Any], dict[str, Any], Path | None]:
    path = Path(path_text).expanduser() if path_text else None
    metadata: dict[str, Any] = {
        f"{prefix}_file_required": True,
        f"{prefix}_file_present": bool(path and path.is_file()),
        f"{prefix}_file_read": False,
        f"{prefix}_file_valid_json": False,
        f"{prefix}_file_mapping": False,
        f"{prefix}_file_error_code": "",
        f"{prefix}_file_sha256": "",
        f"{prefix}_file_path_recorded": False,
    }
    if path is None or not path.is_file():
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_missing"
        return {}, metadata, path
    metadata[f"{prefix}_file_sha256"] = _sha256_file(path)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_invalid"
        return {}, metadata, path
    metadata[f"{prefix}_file_read"] = True
    metadata[f"{prefix}_file_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata[f"{prefix}_file_error_code"] = f"{prefix}_file_not_mapping"
        return {}, metadata, path
    metadata[f"{prefix}_file_mapping"] = True
    return dict(parsed), metadata, path


def _chain_file_failures(metadata: Mapping[str, Any], *, prefix: str) -> list[str]:
    if metadata.get(f"{prefix}_file_mapping") is True:
        return []
    error_code = _safe_text(metadata.get(f"{prefix}_file_error_code"), limit=96)
    if packets.is_command_value_token(error_code) and error_code:
        return [error_code]
    return [f"{prefix}_file_invalid"]


def _chain_packet_semantic_failures(
    packet: Mapping[str, Any],
    *,
    prefix: str,
) -> list[str]:
    if not packet:
        return []
    return (
        [f"{prefix}_packet_semantic_violation"]
        if packets.inspect_command_packet_semantics(packet, secret_values=[])
        else []
    )


def _chain_unsafe_failures(
    named_packets: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    failures: list[str] = []
    for prefix, packet in named_packets.items():
        if not packet:
            continue
        if (
            _acceptance_raw_or_secret_claim_present(packet)
            or _acceptance_raw_material_present(packet)
            or packets.command_packet_has_secret_leak(packet, secret_values=[])
        ):
            failures.append(f"{prefix}_unsafe_secret_or_raw_backend_claim")
    return sorted(set(failures))


def _chain_work_changed_file_paths(work_packet: Mapping[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for changed_file in _safe_changed_files(work_packet.get("changed_files")):
        paths.append(Path(changed_file).expanduser())
    return paths


def _resolve_chain_runner_file(
    work_packet: Mapping[str, Any],
    *,
    runner_file: str | None,
) -> tuple[str | None, str]:
    if runner_file:
        return runner_file, "explicit"
    for changed_path in _chain_work_changed_file_paths(work_packet):
        if changed_path.name == "real-custom-dip-proof-runner.packet.json":
            return str(changed_path), "work_changed_files"
    return None, "missing"


def _chain_path_in_changed_files(
    target: Path | None,
    work_packet: Mapping[str, Any],
) -> bool:
    if target is None:
        return False
    target_key = str(target.expanduser().resolve(strict=False))
    for changed_path in _chain_work_changed_file_paths(work_packet):
        if str(changed_path.resolve(strict=False)) == target_key:
            return True
    return False


def _status_chain_failures(
    status_packet: Mapping[str, Any],
    metadata: Mapping[str, Any],
    status_path: Path | None,
    *,
    max_status_age_seconds: int | None,
) -> tuple[list[str], bool, int, bool]:
    failures = _chain_file_failures(metadata, prefix="status_packet")
    failures.extend(_chain_packet_semantic_failures(status_packet, prefix="status"))
    age_seconds = (
        _packet_file_age_seconds(status_path)
        if status_path is not None and metadata.get("status_packet_file_present") is True
        else 0
    )
    max_age_valid = bool(
        max_status_age_seconds is None
        or (
            isinstance(max_status_age_seconds, int)
            and not isinstance(max_status_age_seconds, bool)
            and max_status_age_seconds > 0
        )
    )
    fresh_by_file = bool(
        max_status_age_seconds is None
        or (max_age_valid and age_seconds <= max_status_age_seconds)
    )
    status_fresh = bool(
        status_packet
        and max_age_valid
        and fresh_by_file
        and status_packet.get("last_acceptance_fresh") is True
    )
    if status_packet:
        if status_packet.get("packet_kind") != DIP_OPERATOR_READINESS_PACKET_KIND:
            failures.append("status_packet_wrong_kind")
        if status_packet.get("status") != "ok":
            failures.append("status_packet_status_not_ok")
        if status_packet.get("machine_error_code") != REAL_CUSTOM_DIP_OPERATOR_OK:
            failures.append("status_packet_machine_error_not_ok")
        if status_packet.get("effect") != EFFECT_READ:
            failures.append("status_packet_not_read_only")
        if _safe_changed_files(status_packet.get("changed_files")):
            failures.append("status_packet_changed_files_present")
        if status_packet.get("dip_operator_ready") is not True:
            failures.append("status_packet_operator_not_ready")
        if status_packet.get("operator_status") != OPERATOR_STATUS_READY:
            failures.append("status_packet_operator_status_not_ready")
        if status_packet.get("last_acceptance_passed") is not True:
            failures.append("status_packet_acceptance_not_passed")
        if status_packet.get("last_acceptance_api_lane_called") is not True:
            failures.append("status_packet_api_lane_not_called")
        if status_packet.get("last_acceptance_delivery_proven") is not True:
            failures.append("status_packet_delivery_not_proven")
        if status_packet.get("last_acceptance_evidence_files_present") is not True:
            failures.append("status_packet_evidence_files_missing")
        if status_packet.get("last_acceptance_fresh") is not True:
            failures.append("status_packet_last_acceptance_stale")
        if status_packet.get("status_command_dispatches") is not False:
            failures.append("status_packet_dispatches")
        if status_packet.get("status_command_runs_acceptance") is not False:
            failures.append("status_packet_runs_acceptance")
        if status_packet.get("status_command_reads_audit_history") is not False:
            failures.append("status_packet_reads_audit_history")
        if status_packet.get("product_ready") is not False:
            failures.append("status_packet_product_ready_claimed")
    if not max_age_valid:
        failures.append("status_packet_max_age_invalid")
    if status_packet and max_age_valid and not fresh_by_file:
        failures.append("status_packet_stale_by_file_mtime")
    return sorted(set(failures)), status_fresh, age_seconds, max_age_valid


def _work_chain_failures(work_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    failures.extend(_chain_packet_semantic_failures(work_packet, prefix="work"))
    changed_files = _safe_changed_files(work_packet.get("changed_files"))
    if work_packet:
        if work_packet.get("packet_kind") != REAL_CUSTOM_DIP_OPERATOR_WORK_PACKET_KIND:
            failures.append("work_packet_wrong_kind")
        if work_packet.get("status") != "ok":
            failures.append("work_packet_status_not_ok")
        if work_packet.get("machine_error_code") != REAL_CUSTOM_DIP_OPERATOR_OK:
            failures.append("work_packet_machine_error_not_ok")
        if work_packet.get("effect") != EFFECT_MUTATE:
            failures.append("work_packet_effect_not_mutate")
        if work_packet.get("operator_command_mode") != "work":
            failures.append("work_packet_mode_not_work")
        if work_packet.get("work_ready") is not True:
            failures.append("work_packet_not_ready")
        if work_packet.get("runner_called") is not True:
            failures.append("work_packet_runner_not_called")
        if work_packet.get("runner_packet_kind") != REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND:
            failures.append("work_packet_runner_wrong_kind")
        if work_packet.get("runner_status") != "ok":
            failures.append("work_packet_runner_status_not_ok")
        if work_packet.get("runner_machine_error_code") != REAL_CUSTOM_DIP_OPERATOR_OK:
            failures.append("work_packet_runner_machine_error_not_ok")
        if work_packet.get("runner_required_run_count") != 1:
            failures.append("work_packet_runner_required_run_count_not_1")
        if work_packet.get("runner_run_count") != 1:
            failures.append("work_packet_runner_run_count_not_1")
        if work_packet.get("work_mode_proven") is not True:
            failures.append("work_packet_work_mode_not_proven")
        if work_packet.get("single_work_run_proven") is not True:
            failures.append("work_packet_single_work_run_not_proven")
        if work_packet.get("api_lane_called") is not True:
            failures.append("work_packet_api_lane_not_called")
        if work_packet.get("codex_working_flow_delivery_proven") is not True:
            failures.append("work_packet_delivery_not_proven")
        if work_packet.get("approved_delivery_surface_proven") is not True:
            failures.append("work_packet_approved_delivery_not_proven")
        if work_packet.get("assistant_response_bound_to_handoff_digest") is not True:
            failures.append("work_packet_assistant_response_not_bound")
        if work_packet.get("status_packet_used_as_auth_grant") is not False:
            failures.append("work_packet_status_used_as_auth_grant")
        if work_packet.get("status_recommendation_bypasses_preflight") is not False:
            failures.append("work_packet_status_bypasses_preflight")
        if work_packet.get("acceptance_is_not_dip_work_prerequisite") is not True:
            failures.append("work_packet_acceptance_used_as_prerequisite")
        if work_packet.get("fallback_used") is not False:
            failures.append("work_packet_fallback_used")
        if work_packet.get("local_imitation_used") is not False:
            failures.append("work_packet_local_imitation_used")
        if work_packet.get("native_codex_subagent_used_as_dip") is not False:
            failures.append("work_packet_native_codex_subagent_used_as_dip")
        if work_packet.get("proof_mode_admission_proven") is not False:
            failures.append("work_packet_admission_proof_minted")
        if work_packet.get("repeatable_real_custom_dip_proof_proven") is not False:
            failures.append("work_packet_repeatable_proof_minted")
        if work_packet.get("real_custom_codex_hook_origin_dip_proof_proven") is not False:
            failures.append("work_packet_hook_origin_proof_minted")
        if work_packet.get("custom_codex_ui_visibility_proven") is not False:
            failures.append("work_packet_custom_codex_ui_claimed")
        if work_packet.get("delivery_counts_as_custom_codex_ui") is not False:
            failures.append("work_packet_delivery_counts_as_custom_ui")
        if work_packet.get("product_ready") is not False:
            failures.append("work_packet_product_ready_claimed")
        if not changed_files:
            failures.append("work_packet_changed_files_missing")
        elif not all(Path(path).expanduser().is_file() for path in changed_files):
            failures.append("work_packet_evidence_files_missing")
        if work_packet.get("runner_changed_files_count") != len(changed_files):
            failures.append("work_packet_runner_changed_files_count_mismatch")
    return sorted(set(failures))


def _runner_chain_failures(runner_packet: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    failures.extend(_chain_packet_semantic_failures(runner_packet, prefix="runner"))
    if runner_packet:
        if runner_packet.get("packet_kind") != REAL_CUSTOM_DIP_PROOF_RUNNER_PACKET_KIND:
            failures.append("runner_packet_wrong_kind")
        if runner_packet.get("status") != "ok":
            failures.append("runner_packet_status_not_ok")
        if runner_packet.get("machine_error_code") != REAL_CUSTOM_DIP_OPERATOR_OK:
            failures.append("runner_packet_machine_error_not_ok")
        if runner_packet.get("effect") != EFFECT_MUTATE:
            failures.append("runner_packet_effect_not_mutate")
        if runner_packet.get("operator_command_mode") != REAL_CUSTOM_DIP_PROOF_RUNNER_MODE_WORK:
            failures.append("runner_packet_mode_not_work")
        if runner_packet.get("work_mode_proven") is not True:
            failures.append("runner_packet_work_mode_not_proven")
        if runner_packet.get("single_work_run_proven") is not True:
            failures.append("runner_packet_single_work_run_not_proven")
        if runner_packet.get("required_run_count") != 1:
            failures.append("runner_packet_required_run_count_not_1")
        if runner_packet.get("run_count") != 1:
            failures.append("runner_packet_run_count_not_1")
        if runner_packet.get("custom_codex_flow_proven") is not True:
            failures.append("runner_packet_custom_codex_flow_not_proven")
        if runner_packet.get("user_prompt_submit_hook_ran") is not True:
            failures.append("runner_packet_hook_not_ran")
        if runner_packet.get("hook_prompt_digest_bound") is not True:
            failures.append("runner_packet_prompt_digest_not_bound")
        if runner_packet.get("hook_runtime_context_digest_bound") is not True:
            failures.append("runner_packet_runtime_context_digest_not_bound")
        if runner_packet.get("delegate_to_dip_proven") is not True:
            failures.append("runner_packet_delegate_to_dip_not_proven")
        if runner_packet.get("api_lane_called") is not True:
            failures.append("runner_packet_api_lane_not_called")
        if runner_packet.get("route_bound_dispatch_proven") is not True:
            failures.append("runner_packet_route_bound_dispatch_not_proven")
        if runner_packet.get("live_result_available") is not True:
            failures.append("runner_packet_live_result_missing")
        if runner_packet.get("direct_provider_auth_proven") is not True:
            failures.append("runner_packet_provider_auth_not_proven")
        if runner_packet.get("codex_working_flow_delivery_proven") is not True:
            failures.append("runner_packet_delivery_not_proven")
        if runner_packet.get("approved_delivery_surface_proven") is not True:
            failures.append("runner_packet_approved_delivery_not_proven")
        if runner_packet.get("assistant_response_bound_to_handoff_digest") is not True:
            failures.append("runner_packet_assistant_response_not_bound")
        if runner_packet.get("fallback_used") is not False:
            failures.append("runner_packet_fallback_used")
        if runner_packet.get("local_imitation_used") is not False:
            failures.append("runner_packet_local_imitation_used")
        if runner_packet.get("native_codex_subagent_used_as_dip") is not False:
            failures.append("runner_packet_native_codex_subagent_used_as_dip")
        if runner_packet.get("proof_mode_admission_proven") is not False:
            failures.append("runner_packet_admission_proof_minted")
        if runner_packet.get("repeatable_real_custom_dip_proof_proven") is not False:
            failures.append("runner_packet_repeatable_proof_minted")
        if runner_packet.get("real_custom_codex_hook_origin_dip_proof_proven") is not False:
            failures.append("runner_packet_hook_origin_proof_minted")
        if runner_packet.get("custom_codex_ui_visibility_proven") is not False:
            failures.append("runner_packet_custom_codex_ui_claimed")
        if runner_packet.get("product_ready") is not False:
            failures.append("runner_packet_product_ready_claimed")
    return sorted(set(failures))


def run_dip_work_chain_join_command(
    *,
    status_file: str | None,
    work_file: str | None,
    runner_file: str | None = None,
    max_status_age_seconds: int | None = DIP_OPERATOR_STATUS_MAX_AGE_SECONDS_DEFAULT,
) -> dict[str, Any]:
    status_packet, status_metadata, status_path = _read_chain_json_mapping_file(
        status_file,
        prefix="status_packet",
    )
    work_packet, work_metadata, work_path = _read_chain_json_mapping_file(
        work_file,
        prefix="work_packet",
    )
    resolved_runner_file, runner_file_source = _resolve_chain_runner_file(
        work_packet,
        runner_file=runner_file,
    )
    runner_packet, runner_metadata, runner_path = _read_chain_json_mapping_file(
        resolved_runner_file,
        prefix="runner_packet",
    )

    status_failures, status_fresh, status_age_seconds, max_age_valid = (
        _status_chain_failures(
            status_packet,
            status_metadata,
            status_path,
            max_status_age_seconds=max_status_age_seconds,
        )
    )
    work_failures = _chain_file_failures(work_metadata, prefix="work_packet")
    work_failures.extend(_work_chain_failures(work_packet))
    runner_failures = _chain_file_failures(runner_metadata, prefix="runner_packet")
    runner_failures.extend(_runner_chain_failures(runner_packet))
    if work_packet and not _chain_path_in_changed_files(runner_path, work_packet):
        runner_failures.append("runner_packet_not_listed_in_work_changed_files")
    unsafe_failures = _chain_unsafe_failures(
        {
            "status_packet": status_packet,
            "work_packet": work_packet,
            "runner_packet": runner_packet,
        }
    )

    status_packet_ok = bool(status_packet and not status_failures)
    work_packet_ok = bool(work_packet and not work_failures)
    runner_packet_ok = bool(runner_packet and not runner_failures)
    explicit_dip_work_proven = bool(work_packet_ok and runner_packet_ok and not unsafe_failures)
    api_lane_called = bool(
        explicit_dip_work_proven
        and work_packet.get("api_lane_called") is True
        and runner_packet.get("api_lane_called") is True
    )
    delivery_proven = bool(
        explicit_dip_work_proven
        and work_packet.get("codex_working_flow_delivery_proven") is True
        and runner_packet.get("codex_working_flow_delivery_proven") is True
        and work_packet.get("approved_delivery_surface_proven") is True
        and runner_packet.get("approved_delivery_surface_proven") is True
        and work_packet.get("assistant_response_bound_to_handoff_digest") is True
        and runner_packet.get("assistant_response_bound_to_handoff_digest") is True
    )
    custom_codex_hook_origin_bound = bool(
        explicit_dip_work_proven
        and work_packet.get("custom_codex_flow_proven") is True
        and runner_packet.get("custom_codex_flow_proven") is True
        and work_packet.get("user_prompt_submit_hook_ran") is True
        and runner_packet.get("user_prompt_submit_hook_ran") is True
        and work_packet.get("hook_prompt_digest_bound") is True
        and runner_packet.get("hook_prompt_digest_bound") is True
        and work_packet.get("hook_runtime_context_digest_bound") is True
        and runner_packet.get("hook_runtime_context_digest_bound") is True
    )
    full_custom_codex_working_flow_proven = bool(
        status_packet_ok
        and status_fresh
        and explicit_dip_work_proven
        and api_lane_called
        and delivery_proven
        and custom_codex_hook_origin_bound
    )

    blocking_reasons = sorted(
        set(status_failures + work_failures + runner_failures + unsafe_failures)
    )
    ok = bool(full_custom_codex_working_flow_proven and not blocking_reasons)
    machine_error_code = (
        DIP_WORK_CHAIN_JOIN_UNSAFE
        if unsafe_failures
        else REAL_CUSTOM_DIP_OPERATOR_OK
        if ok
        else DIP_WORK_CHAIN_JOIN_BLOCKED
    )

    raw_prompt_recorded = any(
        packet.get("raw_prompt_recorded") is True
        for packet in (status_packet, work_packet, runner_packet)
    )
    local_imitation_used = any(
        packet.get("local_imitation_used") is True
        for packet in (status_packet, work_packet, runner_packet)
    )
    fallback_used = any(
        packet.get("fallback_used") is True
        for packet in (status_packet, work_packet, runner_packet)
    )
    native_subagent_used = any(
        packet.get("native_codex_subagent_used_as_dip") is True
        for packet in (status_packet, work_packet, runner_packet)
    )
    secret_value_exposed = any(
        packet.get("secret_value_exposed") is True
        for packet in (status_packet, work_packet, runner_packet)
    )

    extra = {
        "schema_version": 1,
        "packet_kind": DIP_WORK_CHAIN_JOIN_PACKET_KIND,
        "proof_scope": "explicit_dip_work_chain_join",
        "operator_command_surface": "wild-boar-proxy dip chain-join",
        "operator_command_mode": "chain_join",
        "operator_status": OPERATOR_STATUS_READY if ok else OPERATOR_STATUS_BLOCKED,
        "join_reads_audit_history": False,
        "join_runs_status": False,
        "join_runs_work": False,
        "join_calls_api": False,
        "join_dispatches": False,
        **status_metadata,
        **work_metadata,
        **runner_metadata,
        "status_packet_found": status_metadata.get("status_packet_file_present") is True,
        "status_packet_ok": status_packet_ok,
        "status_packet_fresh": status_fresh,
        "status_packet_age_seconds": status_age_seconds,
        "status_packet_max_age_seconds": max_status_age_seconds or 0,
        "status_packet_max_age_valid": max_age_valid,
        "status_packet_used_as_auth_grant": False,
        "work_packet_found": work_metadata.get("work_packet_file_present") is True,
        "work_packet_ok": work_packet_ok,
        "work_packet_mode": _safe_text(work_packet.get("operator_command_mode"), limit=64),
        "work_packet_status_used_as_auth_grant": (
            work_packet.get("status_packet_used_as_auth_grant") is True
        ),
        "runner_packet_found": runner_metadata.get("runner_packet_file_present") is True,
        "runner_packet_ok": runner_packet_ok,
        "runner_packet_mode": _safe_text(runner_packet.get("operator_command_mode"), limit=64),
        "runner_packet_file_source": runner_file_source,
        "runner_packet_listed_in_work_changed_files": _chain_path_in_changed_files(
            runner_path,
            work_packet,
        ),
        "explicit_dip_work_proven": explicit_dip_work_proven,
        "historical_explicit_dip_work_proven": bool(
            explicit_dip_work_proven and not status_fresh
        ),
        "partial_chain_proven": bool(
            explicit_dip_work_proven and not full_custom_codex_working_flow_proven
        ),
        "custom_codex_hook_origin_bound": custom_codex_hook_origin_bound,
        "custom_codex_flow_proven": custom_codex_hook_origin_bound,
        "user_prompt_submit_hook_ran": bool(
            custom_codex_hook_origin_bound
            and runner_packet.get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": bool(
            custom_codex_hook_origin_bound
            and runner_packet.get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            custom_codex_hook_origin_bound
            and runner_packet.get("hook_runtime_context_digest_bound") is True
        ),
        "api_lane_called": api_lane_called,
        "delivery_proven": delivery_proven,
        "codex_working_flow_delivery_proven": delivery_proven,
        "approved_delivery_surface_proven": bool(
            delivery_proven
            and runner_packet.get("approved_delivery_surface_proven") is True
        ),
        "assistant_response_bound_to_handoff_digest": bool(
            delivery_proven
            and runner_packet.get("assistant_response_bound_to_handoff_digest") is True
        ),
        "full_custom_codex_working_flow_proven": full_custom_codex_working_flow_proven,
        "fallback_used": fallback_used,
        "local_imitation_used": local_imitation_used,
        "native_codex_subagent_used_as_dip": native_subagent_used,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "raw_prompt_recorded": raw_prompt_recorded,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": secret_value_exposed,
        "status_failures": sorted(set(status_failures)),
        "work_failures": sorted(set(work_failures)),
        "runner_failures": sorted(set(runner_failures)),
        "unsafe_failures": unsafe_failures,
        "reason_codes": blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP DIP explicit work chain is proven."
            if ok
            else "WBP DIP explicit work chain is BLOCKED."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[],
        effect=EFFECT_READ,
        secret_values=[],
        extra=extra,
    )


def _run_source_packet_unsafe(
    packet: Mapping[str, Any],
    *,
    secret_values: Sequence[str],
) -> bool:
    return bool(
        packets.command_packet_has_secret_leak(packet, secret_values=secret_values)
        or _acceptance_raw_or_secret_claim_present(packet)
        or _acceptance_raw_material_present(packet)
        or packet.get("product_ready") is True
    )


def build_real_custom_dip_operator_run_packet(
    *,
    prompt_text: object,
    status_packet: Mapping[str, Any],
    work_packet: Mapping[str, Any] | None = None,
    chain_join_packet: Mapping[str, Any] | None = None,
    status_packet_path: Path | None = None,
    work_packet_path: Path | None = None,
    chain_join_packet_path: Path | None = None,
    run_packet_path: Path | None = None,
    status_packet_written: bool = False,
    work_packet_written: bool = False,
    chain_join_packet_written: bool = False,
    run_packet_file_written: bool = True,
    write_failures: Sequence[str] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    source_packets = [
        packet
        for packet in (status_packet, work_packet or {}, chain_join_packet or {})
        if packet
    ]
    secret_values_list = [value for value in (secret_values or []) if value]
    status_ready = bool(
        status_packet.get("status") == "ok"
        and status_packet.get("machine_error_code") == REAL_CUSTOM_DIP_OPERATOR_OK
        and status_packet.get("dip_operator_ready") is True
    )
    work_called = bool(work_packet)
    work_ok = bool(
        work_packet
        and work_packet.get("status") == "ok"
        and work_packet.get("machine_error_code") == REAL_CUSTOM_DIP_OPERATOR_OK
        and work_packet.get("work_mode_proven") is True
    )
    chain_join_called = bool(chain_join_packet)
    chain_join_ok = bool(
        chain_join_packet
        and chain_join_packet.get("status") == "ok"
        and chain_join_packet.get("machine_error_code") == REAL_CUSTOM_DIP_OPERATOR_OK
        and chain_join_packet.get("full_custom_codex_working_flow_proven") is True
    )
    unsafe_sources = [
        index
        for index, packet in enumerate(source_packets, start=1)
        if _run_source_packet_unsafe(packet, secret_values=secret_values_list)
    ]
    raw_prompt_recorded = any(
        packet.get("raw_prompt_recorded") is True for packet in source_packets
    )
    fallback_used = any(packet.get("fallback_used") is True for packet in source_packets)
    local_imitation_used = any(
        packet.get("local_imitation_used") is True for packet in source_packets
    )
    native_subagent_used = any(
        packet.get("native_codex_subagent_used_as_dip") is True
        for packet in source_packets
    )
    secret_value_exposed = any(
        packet.get("secret_value_exposed") is True for packet in source_packets
    )
    blocking_reasons = sorted(
        set(
            ([] if status_ready else ["status_not_ready"])
            + _safe_reasons(status_packet.get("blocking_reasons"))
            + ([] if work_called or not status_ready else ["work_not_run"])
            + ([] if work_ok or not work_called else ["work_not_proven"])
            + _safe_reasons((work_packet or {}).get("blocking_reasons"))
            + (
                []
                if chain_join_called or not work_called
                else ["chain_join_not_run"]
            )
            + (
                []
                if chain_join_ok or not chain_join_called
                else ["chain_join_not_proven"]
            )
            + _safe_reasons((chain_join_packet or {}).get("blocking_reasons"))
            + list(write_failures or [])
            + (["unsafe_source_packet"] if unsafe_sources else [])
            + (["fallback_used"] if fallback_used else [])
            + (["local_imitation_used"] if local_imitation_used else [])
            + (
                ["native_codex_subagent_used_as_dip"]
                if native_subagent_used
                else []
            )
            + (["raw_prompt_recorded"] if raw_prompt_recorded else [])
            + (["secret_value_exposed"] if secret_value_exposed else [])
        )
    )
    ok = bool(status_ready and work_ok and chain_join_ok and not blocking_reasons)
    machine_error_code = (
        REAL_CUSTOM_DIP_OPERATOR_UNSAFE_PACKET
        if unsafe_sources or raw_prompt_recorded or secret_value_exposed
        else REAL_CUSTOM_DIP_OPERATOR_OK
        if ok
        else REAL_CUSTOM_DIP_OPERATOR_RUN_BLOCKED
    )
    status_path_digest = (
        _sha256_text(str(status_packet_path.expanduser().resolve(strict=False)))
        if status_packet_path
        else ""
    )
    work_path_digest = (
        _sha256_text(str(work_packet_path.expanduser().resolve(strict=False)))
        if work_packet_path
        else ""
    )
    chain_join_path_digest = (
        _sha256_text(str(chain_join_packet_path.expanduser().resolve(strict=False)))
        if chain_join_packet_path
        else ""
    )
    run_path_digest = (
        _sha256_text(str(run_packet_path.expanduser().resolve(strict=False)))
        if run_packet_path
        else ""
    )
    changed_files = _merge_changed_files(source_packets)
    for candidate_path, written in (
        (status_packet_path, status_packet_written),
        (work_packet_path, work_packet_written),
        (chain_join_packet_path, chain_join_packet_written),
        (run_packet_path, run_packet_file_written),
    ):
        if candidate_path is None or not written:
            continue
        candidate_text = str(candidate_path)
        if candidate_text not in changed_files:
            changed_files.append(candidate_text)

    extra = {
        "schema_version": 1,
        "packet_kind": REAL_CUSTOM_DIP_OPERATOR_RUN_PACKET_KIND,
        "proof_scope": "real_custom_dip_operator_run_wrapper",
        "operator_command_surface": "wild-boar-proxy dip run",
        "operator_command_mode": "run",
        "operator_status": OPERATOR_STATUS_READY if ok else OPERATOR_STATUS_BLOCKED,
        "run_ready": ok,
        "blocked": not ok,
        "run_status_checked": True,
        "status_packet_found": bool(status_packet),
        "status_packet_ok": status_ready,
        "status_packet_written": status_packet_written,
        "status_packet_path_digest": status_path_digest,
        "status_packet_path_recorded": False,
        "status_packet_machine_error_code": _safe_text(
            status_packet.get("machine_error_code"),
            limit=128,
        ),
        "status_packet_used_as_auth_grant": False,
        "status_recommendation_is_not_auth_grant": True,
        "status_recommendation_bypasses_preflight": False,
        "status_allows_dispatch": False,
        "work_called": work_called,
        "work_packet_ok": work_ok,
        "work_packet_written": work_packet_written,
        "work_packet_path_digest": work_path_digest,
        "work_packet_path_recorded": False,
        "work_packet_machine_error_code": _safe_text(
            (work_packet or {}).get("machine_error_code"),
            limit=128,
        ),
        "preflight_checked": (work_packet or {}).get("preflight_checked") is True,
        "preflight_ready": (work_packet or {}).get("preflight_ready") is True,
        "work_mode_proven": work_ok,
        "single_work_run_proven": bool(
            work_ok and (work_packet or {}).get("single_work_run_proven") is True
        ),
        "work_status_packet_used_as_auth_grant": (
            (work_packet or {}).get("status_packet_used_as_auth_grant") is True
        ),
        "chain_join_called": chain_join_called,
        "chain_join_packet_ok": chain_join_ok,
        "chain_join_packet_written": chain_join_packet_written,
        "chain_join_packet_path_digest": chain_join_path_digest,
        "chain_join_packet_path_recorded": False,
        "chain_join_machine_error_code": _safe_text(
            (chain_join_packet or {}).get("machine_error_code"),
            limit=128,
        ),
        "chain_join_reads_audit_history": (
            (chain_join_packet or {}).get("join_reads_audit_history") is True
        ),
        "chain_join_runs_status": (
            (chain_join_packet or {}).get("join_runs_status") is True
        ),
        "chain_join_runs_work": (
            (chain_join_packet or {}).get("join_runs_work") is True
        ),
        "chain_join_calls_api": (
            (chain_join_packet or {}).get("join_calls_api") is True
        ),
        "chain_join_dispatches": (
            (chain_join_packet or {}).get("join_dispatches") is True
        ),
        "explicit_dip_work_proven": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("explicit_dip_work_proven") is True
        ),
        "custom_codex_hook_origin_bound": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("custom_codex_hook_origin_bound") is True
        ),
        "custom_codex_flow_proven": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("custom_codex_flow_proven") is True
        ),
        "user_prompt_submit_hook_ran": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("user_prompt_submit_hook_ran") is True
        ),
        "hook_prompt_digest_bound": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("hook_prompt_digest_bound") is True
        ),
        "hook_runtime_context_digest_bound": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("hook_runtime_context_digest_bound") is True
        ),
        "delegate_to_dip_proven": bool(
            work_ok and (work_packet or {}).get("delegate_to_dip_proven") is True
        ),
        "api_lane_called": bool(
            chain_join_ok and (chain_join_packet or {}).get("api_lane_called") is True
        ),
        "route_bound_dispatch_proven": bool(
            work_ok and (work_packet or {}).get("route_bound_dispatch_proven") is True
        ),
        "live_result_available": bool(
            work_ok and (work_packet or {}).get("live_result_available") is True
        ),
        "delivery_proven": bool(
            chain_join_ok and (chain_join_packet or {}).get("delivery_proven") is True
        ),
        "codex_working_flow_delivery_proven": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("codex_working_flow_delivery_proven")
            is True
        ),
        "approved_delivery_surface_proven": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("approved_delivery_surface_proven")
            is True
        ),
        "assistant_response_bound_to_handoff_digest": bool(
            chain_join_ok
            and (chain_join_packet or {}).get(
                "assistant_response_bound_to_handoff_digest"
            )
            is True
        ),
        "full_custom_codex_working_flow_proven": bool(
            chain_join_ok
            and (chain_join_packet or {}).get("full_custom_codex_working_flow_proven")
            is True
        ),
        "run_packet_file_written": run_packet_file_written,
        "run_packet_path_digest": run_path_digest,
        "run_packet_path_recorded": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "custom_codex_ui_visibility_proven": False,
        "delivery_counts_as_custom_codex_ui": False,
        "fallback_used": fallback_used,
        "local_imitation_used": local_imitation_used,
        "native_codex_subagent_used_as_dip": native_subagent_used,
        "codex_native_subagent_used_as_dip": native_subagent_used,
        "raw_prompt_recorded": raw_prompt_recorded,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "provider_response_preview_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": secret_value_exposed,
        "source_packet_unsafe": bool(unsafe_sources),
        "unsafe_source_packet_count": len(unsafe_sources),
        "prompt_digest": _sha256_text(prompt) if prompt else "",
        "reason_codes": blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP DIP run completed with proof-backed live dispatch."
            if ok
            else "WBP DIP run is BLOCKED."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_MUTATE,
        secret_values=secret_values_list,
        extra=extra,
    )


def run_real_custom_dip_operator_run_command(
    *,
    paths: RuntimePaths,
    prompt_text: object,
    codex_bin: str | None = None,
    codex_model: str | None = None,
    proof_dir: str | None = None,
    codex_cwd: str | None = None,
    sandbox: str = DEFAULT_SANDBOX,
    timeout_seconds: int = 300,
    codex_hook_current_hash: str | None = None,
    probe_codex_app_server: bool = False,
    max_status_age_seconds: int | None = DIP_OPERATOR_STATUS_MAX_AGE_SECONDS_DEFAULT,
) -> dict[str, Any]:
    prompt = _safe_text(prompt_text, limit=4096)
    context_path = runtime_context_path(paths=paths)
    runtime_context, _context_metadata = load_runtime_context_packet(context_path)
    secret_values = [prompt] if prompt else []
    secret_values.extend(_runtime_secret_values(runtime_context))
    base_proof_root = _run_proof_root(paths, proof_dir)
    status_path = _run_status_packet_output_path(base_proof_root)
    work_path = _run_work_packet_output_path(base_proof_root)
    chain_join_path = _run_chain_join_packet_output_path(base_proof_root)
    run_path = _run_packet_output_path(base_proof_root)
    write_failures: list[str] = []
    status_written = False
    work_written = False
    chain_join_written = False
    status_packet = run_dip_operator_status_command(
        paths=paths,
        proof_file=None,
        max_age_seconds=max_status_age_seconds,
    )
    try:
        _persist_json_packet(status_path, status_packet, secret_values=secret_values)
        status_written = True
    except OSError:
        write_failures.append("status_packet_write_failed")

    work_packet: dict[str, Any] | None = None
    chain_join_packet: dict[str, Any] | None = None
    status_unsafe = _run_source_packet_unsafe(status_packet, secret_values=secret_values)
    if not status_unsafe and not write_failures:
        work_packet = run_real_custom_dip_operator_work_command(
            paths=paths,
            prompt_text=prompt,
            codex_bin=codex_bin,
            codex_model=codex_model,
            proof_dir=str(base_proof_root / "work"),
            codex_cwd=codex_cwd,
            sandbox=sandbox,
            timeout_seconds=timeout_seconds,
            codex_hook_current_hash=codex_hook_current_hash,
            probe_codex_app_server=probe_codex_app_server,
        )
        try:
            _persist_json_packet(work_path, work_packet, secret_values=secret_values)
            work_written = True
        except OSError:
            write_failures.append("work_packet_write_failed")
        if work_written:
            chain_join_packet = run_dip_work_chain_join_command(
                status_file=str(status_path),
                work_file=str(work_path),
                runner_file=None,
                max_status_age_seconds=max_status_age_seconds,
            )
            try:
                _persist_json_packet(
                    chain_join_path,
                    chain_join_packet,
                    secret_values=secret_values,
                )
                chain_join_written = True
            except OSError:
                write_failures.append("chain_join_packet_write_failed")

    packet = build_real_custom_dip_operator_run_packet(
        prompt_text=prompt,
        status_packet=status_packet,
        work_packet=work_packet,
        chain_join_packet=chain_join_packet,
        status_packet_path=status_path,
        work_packet_path=work_path if work_packet is not None else None,
        chain_join_packet_path=(
            chain_join_path if chain_join_packet is not None else None
        ),
        run_packet_path=run_path,
        status_packet_written=status_written,
        work_packet_written=work_written,
        chain_join_packet_written=chain_join_written,
        run_packet_file_written=True,
        write_failures=write_failures,
        secret_values=secret_values,
    )
    try:
        _persist_json_packet(run_path, packet, secret_values=secret_values)
        return packet
    except OSError:
        return build_real_custom_dip_operator_run_packet(
            prompt_text=prompt,
            status_packet=status_packet,
            work_packet=work_packet,
            chain_join_packet=chain_join_packet,
            status_packet_path=status_path,
            work_packet_path=work_path if work_packet is not None else None,
            chain_join_packet_path=(
                chain_join_path if chain_join_packet is not None else None
            ),
            run_packet_path=run_path,
            status_packet_written=status_written,
            work_packet_written=work_written,
            chain_join_packet_written=chain_join_written,
            run_packet_file_written=False,
            write_failures=write_failures + ["run_packet_write_failed"],
            secret_values=secret_values,
        )
