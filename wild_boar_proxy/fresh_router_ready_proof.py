# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .command_effects import EFFECT_MUTATE
from .core import packets
from .custom_codex_admission import (
    DEFAULT_EXPECTED_TEXT,
    DEFAULT_SANDBOX,
    DEFAULT_TIMEOUT_SECONDS,
)
from .fresh_sealed_e2e_proof import (
    FRESH_SEALED_E2E_PACKET_KIND,
    run_fresh_sealed_e2e_proof_command,
)
from .native_filesystem_probe import DEFAULT_CUSTOM_NATIVE_MODEL
from .proof_seal import sha256_file
from .repeatable_proof_status import (
    DEFAULT_PROVIDER_PREFLIGHT_MARKER,
    OPERATOR_STATUS_BLOCKED,
    OPERATOR_STATUS_PROOF_ONLY,
    OPERATOR_STATUS_ROUTER_READY,
    REPEATABLE_PROOF_STATUS_OK,
    REPEATABLE_PROOF_STATUS_PACKET_KIND,
    run_repeatable_proof_status_command,
)
from .router_hook_entry import RUNTIME_CONTEXT_FILENAME, _safe_text
from .runtime import RuntimePaths, write_json_atomic
from .user_prompt_submit_hook_producer import HOOKS_JSON_FILENAME


FRESH_ROUTER_READY_PROOF_PACKET_KIND = "wbp_fresh_router_ready_proof"
DESIGN_GATE_READY_TOKEN = "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY"
PERSISTENT_PROFILE_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

FRESH_ROUTER_READY_PROOF_OK = "OK"
FRESH_ROUTER_READY_PROOF_PROOF_ONLY = "WBP_FRESH_ROUTER_READY_PROOF_PROOF_ONLY"
FRESH_ROUTER_READY_PROOF_BLOCKED = "WBP_FRESH_ROUTER_READY_PROOF_BLOCKED"
FRESH_ROUTER_READY_PROOF_UNSAFE_PACKET = "WBP_FRESH_ROUTER_READY_PROOF_UNSAFE_PACKET"


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "codex-runner" / "fresh-router-ready-proof" / stamp


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_packet(path: Path, packet: Mapping[str, Any]) -> str:
    write_json_atomic(path, dict(packet))
    return str(path)


def _default_persistent_profile_base_dir() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "WildBoarProxy"
        / "CodexProfiles"
    )


def _runtime_paths_for_profile_dir(base: RuntimePaths, profile_dir: Path) -> RuntimePaths:
    profile = profile_dir.expanduser()
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=base.stable_config,
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=profile / "codex-custom-launch.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=managed / "bin" / "codex-accounts",
        onboard_bin=managed / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed
        / "stable-runtime-config.generated.yaml",
    )


def _profile_runtime_contract_present(paths: RuntimePaths) -> bool:
    return bool(
        paths.config_toml.is_file()
        and (paths.profile_dir / RUNTIME_CONTEXT_FILENAME).is_file()
        and (paths.profile_dir / HOOKS_JSON_FILENAME).is_file()
    )


def _persistent_profile_candidate(
    *,
    base_paths: RuntimePaths,
    persistent_profile_id: str,
    persistent_profile_base_dir: str | None,
) -> RuntimePaths | None:
    profile_id = _safe_text(persistent_profile_id, limit=128)
    if (
        not profile_id
        or profile_id in {".", ".."}
        or Path(profile_id).name != profile_id
        or not PERSISTENT_PROFILE_ID_PATTERN.fullmatch(profile_id)
    ):
        return None
    base_dir = (
        Path(persistent_profile_base_dir).expanduser()
        if persistent_profile_base_dir
        else _default_persistent_profile_base_dir()
    )
    return _runtime_paths_for_profile_dir(base_paths, base_dir / profile_id)


def _select_admission_paths(
    *,
    paths: RuntimePaths,
    persistent_profile_id: str,
    persistent_profile_base_dir: str | None,
) -> tuple[RuntimePaths, dict[str, Any]]:
    if _profile_runtime_contract_present(paths):
        return paths, {
            "admission_profile_source": "runtime_paths",
            "admission_profile_auto_selected": False,
            "admission_profile_runtime_contract_present": True,
        }
    candidate = _persistent_profile_candidate(
        base_paths=paths,
        persistent_profile_id=persistent_profile_id,
        persistent_profile_base_dir=persistent_profile_base_dir,
    )
    if candidate is not None and _profile_runtime_contract_present(candidate):
        return candidate, {
            "admission_profile_source": "persistent_custom_profile",
            "admission_profile_auto_selected": True,
            "admission_profile_runtime_contract_present": True,
        }
    return paths, {
        "admission_profile_source": "runtime_paths_missing_contract",
        "admission_profile_auto_selected": False,
        "admission_profile_runtime_contract_present": False,
    }


def _routes_file_contains_route(routes_file: Path, route_id: str) -> bool:
    if not route_id or not routes_file.is_file():
        return False
    try:
        parsed = json.loads(routes_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    routes = parsed.get("routes") if isinstance(parsed, Mapping) else None
    if isinstance(routes, (str, bytes)) or not isinstance(routes, Sequence):
        return False
    for route in routes:
        if isinstance(route, Mapping) and route.get("route_id") == route_id:
            return True
    return False


def _default_external_models_dir(paths: RuntimePaths, route_id: str) -> str | None:
    candidate = paths.managed_dir / "external-models"
    if _routes_file_contains_route(candidate / "routes.json", route_id):
        return str(candidate)
    return None


def _default_native_auto_launch_stable_runtime_config(
    *,
    selected_paths: RuntimePaths,
    original_paths: RuntimePaths,
) -> str | None:
    candidates = [
        selected_paths.stable_runtime_generated_config_file,
        original_paths.stable_runtime_generated_config_file,
        Path("~/.codex-custom-cli/managed/stable-runtime-config.generated.yaml").expanduser(),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _safe_reasons(value: object) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return []
    reasons: set[str] = set()
    for item in value:
        reason = _safe_text(item, limit=96)
        if packets.is_command_value_token(reason):
            reasons.add(reason)
    return sorted(reasons)


def _status_router_ready(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("packet_kind") == REPEATABLE_PROOF_STATUS_PACKET_KIND
        and packet.get("status") == "ok"
        and packet.get("machine_error_code") == REPEATABLE_PROOF_STATUS_OK
        and packet.get("operator_status") == OPERATOR_STATUS_ROUTER_READY
        and packet.get("router_ready") is True
        and packet.get("proof_only") is False
        and packet.get("blocked") is False
    )


def _fresh_router_ready_grade(packet: Mapping[str, Any]) -> bool:
    return bool(
        packet.get("packet_kind") == FRESH_SEALED_E2E_PACKET_KIND
        and packet.get("status") == "ok"
        and packet.get("machine_error_code") == "OK"
        and packet.get("fresh_sealed_e2e_proven") is True
        and packet.get("user_prompt_submit_hook_ran") is True
        and packet.get("api_lane_called") is True
        and packet.get("dispatch_proven") is True
        and packet.get("full_runtime_diagnostics_passed") is True
        and packet.get("native_custom_codex_visible_flow_proven") is True
        and packet.get("fallback_used") is False
        and packet.get("local_imitation_used") is False
        and packet.get("native_codex_subagent_used_as_dip") is False
        and packet.get("product_ready") is False
    )


def _operator_status(packet: Mapping[str, Any]) -> str:
    raw = _safe_text(packet.get("operator_status"), limit=64)
    if raw in {
        OPERATOR_STATUS_ROUTER_READY,
        OPERATOR_STATUS_PROOF_ONLY,
        OPERATOR_STATUS_BLOCKED,
    }:
        return raw
    return OPERATOR_STATUS_BLOCKED


def _machine_error_code(
    *,
    unsafe: bool,
    router_ready: bool,
    operator_status: str,
) -> str:
    if unsafe:
        return FRESH_ROUTER_READY_PROOF_UNSAFE_PACKET
    if router_ready:
        return FRESH_ROUTER_READY_PROOF_OK
    if operator_status == OPERATOR_STATUS_PROOF_ONLY:
        return FRESH_ROUTER_READY_PROOF_PROOF_ONLY
    return FRESH_ROUTER_READY_PROOF_BLOCKED


def build_fresh_router_ready_proof_packet(
    *,
    route_id: str,
    proof_root: Path,
    fresh_proof_packet: Mapping[str, Any],
    fresh_proof_file: Path,
    repeatable_status_packet: Mapping[str, Any],
    repeatable_status_file: Path,
    changed_files: Sequence[str],
    productization_metadata: Mapping[str, Any] | None = None,
    secret_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    fresh = dict(fresh_proof_packet)
    status = dict(repeatable_status_packet)
    route_digest = _sha256_text(route_id) if route_id else ""
    fresh_digest = sha256_file(fresh_proof_file)
    status_digest = sha256_file(repeatable_status_file)
    status_bound_to_fresh = bool(
        fresh_digest and status.get("last_fresh_proof_digest") == fresh_digest
    )
    status_operator_status = _operator_status(status)
    fresh_ready_grade = _fresh_router_ready_grade(fresh)
    router_ready = bool(
        _status_router_ready(status)
        and status_bound_to_fresh
        and fresh_ready_grade
    )
    operator_status = (
        OPERATOR_STATUS_ROUTER_READY
        if router_ready
        else OPERATOR_STATUS_PROOF_ONLY
        if status_operator_status == OPERATOR_STATUS_PROOF_ONLY
        else OPERATOR_STATUS_BLOCKED
    )
    unsafe_payload = {
        "packet_kind": FRESH_ROUTER_READY_PROOF_PACKET_KIND,
        "route_id_sha256": route_digest,
        "fresh_proof_sha256": fresh_digest,
        "repeatable_status_sha256": status_digest,
    }
    unsafe = packets.command_packet_has_secret_leak(
        unsafe_payload,
        secret_values=list(secret_values or []),
    )
    blocking_reasons = sorted(
        set(
            (["fresh_router_ready_proof_packet_secret_leak"] if unsafe else [])
            + ([] if fresh_proof_file.is_file() else ["fresh_proof_file_missing"])
            + ([] if repeatable_status_file.is_file() else ["repeatable_status_file_missing"])
            + (
                []
                if status_bound_to_fresh
                else ["repeatable_status_not_bound_to_fresh_proof_file"]
            )
            + ([] if fresh_ready_grade else ["fresh_proof_not_router_ready_grade"])
            + ([] if status.get("status") == "ok" else ["repeatable_status_not_ok"])
            + (
                []
                if status.get("machine_error_code") == REPEATABLE_PROOF_STATUS_OK
                else ["repeatable_status_machine_error_not_ok"]
            )
            + (
                []
                if router_ready
                else ["fresh_router_ready_proof_only"]
                if operator_status == OPERATOR_STATUS_PROOF_ONLY
                else ["fresh_router_ready_blocked"]
            )
            + _safe_reasons(status.get("blocking_reasons"))
            + _safe_reasons(status.get("reason_codes"))
        )
    )
    machine_error_code = _machine_error_code(
        unsafe=unsafe,
        router_ready=router_ready,
        operator_status=operator_status,
    )
    ok = bool(machine_error_code == FRESH_ROUTER_READY_PROOF_OK)
    extra = {
        "schema_version": 1,
        "packet_kind": FRESH_ROUTER_READY_PROOF_PACKET_KIND,
        "proof_scope": "fresh_sealed_proof_to_repeatable_router_ready_gate",
        "operator_status": operator_status,
        "router_ready": router_ready,
        "proof_only": bool(not router_ready and operator_status == OPERATOR_STATUS_PROOF_ONLY),
        "blocked": bool(not router_ready and operator_status == OPERATOR_STATUS_BLOCKED),
        "fresh_proof_orchestrated": True,
        "fresh_proof_packet_kind": _safe_text(fresh.get("packet_kind"), limit=96),
        "fresh_proof_status": _safe_text(fresh.get("status"), limit=32),
        "fresh_proof_machine_error_code": _safe_text(
            fresh.get("machine_error_code"),
            limit=96,
        ),
        "fresh_proof_file_present": fresh_proof_file.is_file(),
        "fresh_proof_file_path_recorded": False,
        "fresh_proof_sha256": fresh_digest,
        "fresh_proof_digest_bound_to_status": status_bound_to_fresh,
        "fresh_proof_router_ready_grade": fresh_ready_grade,
        "repeatable_status_packet_kind": _safe_text(status.get("packet_kind"), limit=96),
        "repeatable_status_status": _safe_text(status.get("status"), limit=32),
        "repeatable_status_machine_error_code": _safe_text(
            status.get("machine_error_code"),
            limit=96,
        ),
        "repeatable_status_file_present": repeatable_status_file.is_file(),
        "repeatable_status_file_path_recorded": False,
        "repeatable_status_sha256": status_digest,
        "proof_dir_path_recorded": False,
        "route_id_allowed": status.get("route_id_allowed") is True,
        "route_id_sha256": route_digest,
        "route_id_recorded": False,
        "raw_route_id_recorded": False,
        "selected_api_route_id_recorded": False,
        "user_prompt_submit_hook_ready": (
            status.get("user_prompt_submit_hook_ready") is True
        ),
        "user_prompt_submit_hook_ran": status.get("user_prompt_submit_hook_ran") is True,
        "provider_health_ok": status.get("provider_health_ok") is True,
        "provider_lane_preflight_attempted": (
            status.get("provider_lane_preflight_attempted") is True
        ),
        "provider_lane_expected_text_exact": (
            status.get("provider_lane_expected_text_exact") is True
        ),
        "provider_lane_preflight_is_dispatch_proof": False,
        "provider_lane_fallback_used": status.get("provider_lane_fallback_used") is True,
        "provider_response_preview_recorded": False,
        "fresh_sealed_e2e_proven": status.get("fresh_sealed_e2e_proven") is True,
        "full_runtime_diagnostics_passed": (
            status.get("full_runtime_diagnostics_passed") is True
        ),
        "native_custom_codex_visible_flow_proven": (
            status.get("native_custom_codex_visible_flow_proven") is True
        ),
        "api_lane_called": status.get("api_lane_called") is True,
        "dispatch_proven": status.get("dispatch_proven") is True,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "codex_native_subagent_used_as_dip": False,
        "product_ready": False,
        "does_not_prove_product_ready": True,
        "custom_codex_ui_visibility_product_ready": False,
        "execution_core_repair_closed_and_design_gate_ready": ok,
        "design_gate_marker_sha256": _sha256_text(DESIGN_GATE_READY_TOKEN) if ok else "",
        "design_gate_marker_recorded": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_jsonl_recorded": False,
        "tool_call_arguments_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "expected_text_recorded": False,
        "provider_expected_text_recorded": False,
        "state_written": False,
        "runtime_effective_truth_written": False,
        "evidence_written": True,
        "file_mutation_attempted": True,
        "orchestrator_truth_layer_created": False,
        "blocking_reasons": [] if ok else blocking_reasons,
        "changed_files": sorted(set(changed_files)),
    }
    extra.update(dict(productization_metadata or {}))
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP fresh sealed proof is bound to a router-ready status gate."
            if ok
            else "WBP fresh sealed proof did not reach router-ready status."
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


def run_fresh_router_ready_proof_command(
    *,
    paths: RuntimePaths,
    route_id: str,
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
    native_auto_launch_custom_codex: bool = False,
    native_auto_launch_endpoint: str = "http://127.0.0.1:8318/v1",
    native_auto_launch_model: str = DEFAULT_CUSTOM_NATIVE_MODEL,
    native_auto_launch_owner_authorization_phrase: str | None = None,
    native_auto_launch_repo_root: str | None = None,
    native_auto_launch_stable_runtime_generated_config_file: str | None = None,
    provider_expected_text: str = DEFAULT_PROVIDER_PREFLIGHT_MARKER,
    external_models_dir: str | None = None,
    codex_hook_current_hash: str = "",
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    original_paths = paths
    paths, productization_metadata = _select_admission_paths(
        paths=paths,
        persistent_profile_id=persistent_profile_id,
        persistent_profile_base_dir=persistent_profile_base_dir,
    )
    effective_codex_model = codex_model or native_auto_launch_model
    effective_native_auto_launch_stable_config = (
        native_auto_launch_stable_runtime_generated_config_file
        or _default_native_auto_launch_stable_runtime_config(
            selected_paths=paths,
            original_paths=original_paths,
        )
    )
    effective_external_models_dir = external_models_dir or _default_external_models_dir(
        paths,
        route_id,
    )
    effective_probe_codex_app_server = bool(
        probe_codex_app_server or not codex_hook_current_hash
    )
    productization_metadata.update(
        {
            "codex_model_auto_defaulted": codex_model is None,
            "codex_model_selection_id": _safe_text(effective_codex_model, limit=128),
            "native_auto_launch_stable_runtime_config_auto_selected": bool(
                not native_auto_launch_stable_runtime_generated_config_file
                and effective_native_auto_launch_stable_config
            ),
            "native_auto_launch_stable_runtime_config_present": bool(
                effective_native_auto_launch_stable_config
            ),
            "native_auto_launch_stable_runtime_config_path_recorded": False,
            "external_models_dir_auto_selected": bool(
                not external_models_dir and effective_external_models_dir
            ),
            "external_models_dir_path_recorded": False,
            "codex_hook_current_hash_probe_auto_enabled": bool(
                not codex_hook_current_hash and effective_probe_codex_app_server
            ),
        }
    )
    proof_root = _proof_root(paths, proof_dir)
    fresh_proof_dir = proof_root / "fresh-sealed"
    proof_root.mkdir(parents=True, exist_ok=True)
    changed_files: list[str] = []
    secret_values = [prompt_text, expected_text, provider_expected_text, route_id]

    fresh_packet = run_fresh_sealed_e2e_proof_command(
        paths=paths,
        prompt_text=prompt_text,
        custom_codex_ui_visibility_proof_file=custom_codex_ui_visibility_proof_file,
        codex_bin=codex_bin,
        codex_model=effective_codex_model,
        proof_dir=str(fresh_proof_dir),
        codex_cwd=codex_cwd,
        expected_text=expected_text,
        sandbox=sandbox,
        timeout_seconds=timeout_seconds,
        persistent_profile_id=persistent_profile_id,
        persistent_profile_base_dir=persistent_profile_base_dir,
        observer_timeout_seconds=observer_timeout_seconds,
        native_auto_launch_custom_codex=native_auto_launch_custom_codex,
        native_auto_launch_endpoint=native_auto_launch_endpoint,
        native_auto_launch_model=native_auto_launch_model,
        native_auto_launch_owner_authorization_phrase=(
            native_auto_launch_owner_authorization_phrase
        ),
        native_auto_launch_repo_root=native_auto_launch_repo_root,
        native_auto_launch_stable_runtime_generated_config_file=(
            effective_native_auto_launch_stable_config
        ),
    )
    changed_files.extend(str(path) for path in fresh_packet.get("changed_files", []))

    fresh_packet_file = fresh_proof_dir / "fresh-sealed-e2e-proof.packet.json"
    if not fresh_packet_file.is_file():
        changed_files.append(_write_packet(fresh_packet_file, fresh_packet))

    status_packet = run_repeatable_proof_status_command(
        paths=paths,
        route_id=route_id,
        fresh_proof_file=str(fresh_packet_file),
        provider_expected_text=provider_expected_text,
        run_provider_preflight=True,
        external_models_dir=effective_external_models_dir,
        codex_hook_current_hash=codex_hook_current_hash,
        probe_codex_app_server=effective_probe_codex_app_server,
    )
    status_packet_file = proof_root / "repeatable-proof-status.packet.json"
    changed_files.append(_write_packet(status_packet_file, status_packet))

    final_packet_file = proof_root / "fresh-router-ready-proof.packet.json"
    final_packet = build_fresh_router_ready_proof_packet(
        route_id=route_id,
        proof_root=proof_root,
        fresh_proof_packet=fresh_packet,
        fresh_proof_file=fresh_packet_file,
        repeatable_status_packet=status_packet,
        repeatable_status_file=status_packet_file,
        changed_files=[*changed_files, str(final_packet_file)],
        productization_metadata=productization_metadata,
        secret_values=secret_values,
    )
    _write_packet(final_packet_file, final_packet)
    return final_packet
