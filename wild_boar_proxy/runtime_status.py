# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .command_effects import EFFECT_READ


class RuntimeStatusPaths(Protocol):
    config_toml: Path
    managed_config_file: Path
    registry_file: Path
    repair_target_inventory_dir: Path
    runtime_effective_mode_file: Path
    runtime_mode_file: Path
    stable_config: Path
    state_file: Path
    sync_script: Path


@dataclass(frozen=True)
class StatusSnapshotDependencies:
    get_desired_mode: Callable[[RuntimeStatusPaths], str]
    read_json: Callable[..., dict[str, Any]]
    summarize_registry_pool_counts: Callable[[dict[str, Any]], dict[str, int]]
    get_stable_policy_drift: Callable[[RuntimeStatusPaths, dict[str, Any]], bool]
    get_effective_mode: Callable[[RuntimeStatusPaths, dict[str, Any]], str]
    get_endpoint: Callable[[RuntimeStatusPaths, str], tuple[str, int, str]]
    get_model: Callable[[RuntimeStatusPaths], str]
    get_configured_proxy_url: Callable[[RuntimeStatusPaths, str], str]
    get_reported_current_proxy_url: Callable[
        [RuntimeStatusPaths, dict[str, Any], str], str
    ]
    get_registry_identity: Callable[[dict[str, Any]], dict[str, Any]]
    build_stable_runtime_consumer_contract: Callable[..., dict[str, Any]]
    build_current_proxy_adoption_contract: Callable[[RuntimeStatusPaths], dict[str, Any]]
    build_last_known_good_proxy_contract: Callable[[RuntimeStatusPaths], dict[str, Any]]
    build_last_known_good_proxy_surface: Callable[
        [RuntimeStatusPaths, dict[str, Any], str], dict[str, Any]
    ]
    summarize_auth_pool_hygiene: Callable[
        [dict[str, Any], dict[str, Any]], dict[str, Any]
    ]
    build_native_auth_recovery_hint: Callable[..., dict[str, Any]]
    build_runtime_guardrail_surface: Callable[..., dict[str, Any]]
    build_command_payload: Callable[..., dict[str, Any]]
    summarize_registry_identity: Callable[[dict[str, Any]], dict[str, Any]]
    get_claim_gate: Callable[[bool, dict[str, Any]], dict[str, Any]]
    should_use_approved_target_policy_drift: Callable[..., bool]
    get_stable_policy_drift_for_inventory_source: Callable[
        [dict[str, Any], Path, dict[str, Any]], dict[str, Any]
    ]
    get_approved_target_inventory_source: Callable[
        [RuntimeStatusPaths], dict[str, Any]
    ]


def build_status_snapshot_payload(
    paths: RuntimeStatusPaths,
    *,
    dependencies: StatusSnapshotDependencies,
) -> dict[str, Any]:
    desired_mode = dependencies.get_desired_mode(paths)
    registry = dependencies.read_json(paths.registry_file)
    pool_counts = dependencies.summarize_registry_pool_counts(registry)
    policy_drift_observed = dependencies.get_stable_policy_drift(paths, registry)
    state = dependencies.read_json(paths.state_file, required=False)
    effective_mode = dependencies.get_effective_mode(paths, state)
    _, _, endpoint = dependencies.get_endpoint(paths, effective_mode)
    configured_model = dependencies.get_model(paths)
    configured_proxy_url = dependencies.get_configured_proxy_url(paths, effective_mode)
    current_proxy_url = dependencies.get_reported_current_proxy_url(
        paths, state, effective_mode
    )
    registry_identity = dependencies.get_registry_identity(registry)
    stable_runtime_consumer = dependencies.build_stable_runtime_consumer_contract(
        paths, registry, policy_drift_observed, state
    )
    current_proxy_adoption_contract = {
        **dependencies.build_current_proxy_adoption_contract(paths),
        "status_delegates_to_owner": False,
        "status_snapshot_only": True,
    }
    last_known_good_proxy_contract = {
        **dependencies.build_last_known_good_proxy_contract(paths),
        "status_delegates_to_owner": False,
        "status_snapshot_only": True,
    }
    last_known_good_proxy = dependencies.build_last_known_good_proxy_surface(
        paths, state, current_proxy_url
    )
    pool_summary = {
        "active": int(pool_counts.get("active", 0) or 0),
        "reserve": int(pool_counts.get("reserve", 0) or 0),
        "retired": int(pool_counts.get("retired", 0) or 0),
        "healthy": int(state.get("healthy_count", 0) or 0),
        "degraded": int(state.get("degraded_count", 0) or 0),
        "down": int(state.get("down_count", 0) or 0),
        "selected_backend_ids": state.get("selected_backend_ids") or [],
        "backend_count": len(registry.get("backends") or []),
    }
    auth_pool_hygiene = dependencies.summarize_auth_pool_hygiene(registry, state)
    auth_pool_hygiene["delegated_from_status"] = False
    native_auth_recovery_hint = dependencies.build_native_auth_recovery_hint(
        machine_error_code="OK",
        auth_pool_hygiene=auth_pool_hygiene,
    )
    native_auth_recovery_hint["delegated_from_status"] = False
    launch_readiness = {
        "status": "not_evaluated",
        "owner_command_surface": "status --json",
        "delegated_from_status": False,
        "real_inference_required": True,
        "listener_reachable": None,
        "models_surface_reachable": None,
        "responses_proof_passed": None,
        "truth_alignment_passed": None,
        "base_url_match": None,
        "effective_mode_match": None,
        "model_match": None,
        "proxy_url_match": None,
        "gate_passed": False,
        "blocking_reason": "live_attestation_not_run_by_status",
        "failed_checks": ["live_attestation_not_run_by_status"],
        "machine_error_code": "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
        "last_error": "",
        "auth_pool_hygiene_status": auth_pool_hygiene.get("status", ""),
        "launch_capable_backend_count": auth_pool_hygiene.get(
            "launch_capable_backend_count"
        ),
    }
    runtime_guardrails = dependencies.build_runtime_guardrail_surface(
        paths,
        launch_readiness=launch_readiness,
        auth_pool_hygiene=auth_pool_hygiene,
        recovery_result=None,
    )
    runtime_guardrails["delegated_from_status"] = False
    runtime_guardrails["owner_command_surface"] = "status --json"

    return dependencies.build_command_payload(
        ok=True,
        human_message="Runtime status snapshot is available.",
        machine_error_code="OK",
        liveness="unknown",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        effect=EFFECT_READ,
        extra={
            "desired_mode": desired_mode,
            "effective_mode": effective_mode,
            "endpoint": endpoint,
            "configured_model": configured_model,
            "requested_model": configured_model,
            "configured_proxy_url": configured_proxy_url,
            "current_proxy_url": current_proxy_url,
            "current_proxy_adoption_contract": current_proxy_adoption_contract,
            "last_known_good_proxy_contract": last_known_good_proxy_contract,
            "last_known_good_proxy": last_known_good_proxy,
            "pool_summary": pool_summary,
            "auth_pool_hygiene": auth_pool_hygiene,
            "native_auth_recovery_hint": native_auth_recovery_hint,
            "policy_drift": policy_drift_observed,
            "policy_drift_observed": policy_drift_observed,
            "stable_runtime_consumer": stable_runtime_consumer,
            "launch_readiness": launch_readiness,
            "runtime_guardrails": runtime_guardrails,
            "registry_identity_summary": dependencies.summarize_registry_identity(
                registry_identity
            ),
            "claim_gate": dependencies.get_claim_gate(
                policy_drift_observed, registry_identity
            ),
            "last_error": str(state.get("last_error", "")),
            "attestation_summary": {
                "status": "not_run",
                "machine_error_code": "LIVE_ATTESTATION_NOT_RUN_BY_STATUS",
                "attestation_source": "status --json",
                "observed_at_utc": "",
            },
        },
    )


def build_delegated_health_status_summary_payload(
    paths: RuntimeStatusPaths,
    health_payload: dict[str, Any],
    *,
    dependencies: StatusSnapshotDependencies,
) -> dict[str, Any]:
    desired_mode = dependencies.get_desired_mode(paths)
    registry = dependencies.read_json(paths.registry_file)
    pool_counts = dependencies.summarize_registry_pool_counts(registry)
    policy_drift_observed = dependencies.get_stable_policy_drift(paths, registry)
    state = dependencies.read_json(paths.state_file, required=False)
    stable_runtime_consumer = dependencies.build_stable_runtime_consumer_contract(
        paths, registry, policy_drift_observed, state, health_payload
    )
    if dependencies.should_use_approved_target_policy_drift(
        paths,
        registry,
        policy_drift_observed,
        state,
        require_live_stable_runtime=True,
        health_payload=health_payload,
        stable_runtime_consumer=stable_runtime_consumer,
    ):
        policy_drift = dependencies.get_stable_policy_drift_for_inventory_source(
            registry,
            paths.repair_target_inventory_dir,
            dependencies.get_approved_target_inventory_source(paths),
        )
    else:
        policy_drift = policy_drift_observed
    recovery_result = health_payload.get("deterministic_stable_recovery_result")
    if isinstance(recovery_result, dict):
        stable_runtime_consumer = dict(stable_runtime_consumer)
        stable_runtime_consumer["deterministic_stable_recovery_result"] = {
            **recovery_result,
            "delegated_from_status": True,
        }
    delegated_machine_error_code = str(health_payload["machine_error_code"])
    if (
        isinstance(recovery_result, dict)
        and delegated_machine_error_code == "LISTENER_DOWN"
        and str(recovery_result.get("entry_lane", "")) == "stable_service_disabled"
        and str(health_payload.get("liveness", "")) == "down"
    ):
        delegated_machine_error_code = "STABLE_SERVICE_DISABLED"
    registry_identity = dependencies.get_registry_identity(registry)
    current_proxy_url = str(
        health_payload.get("current_proxy_url", state.get("current_proxy_url", ""))
    )
    current_proxy_adoption_contract = health_payload.get(
        "current_proxy_adoption_contract"
    )
    if not isinstance(current_proxy_adoption_contract, dict):
        current_proxy_adoption_contract = (
            dependencies.build_current_proxy_adoption_contract(paths)
        )
    last_known_good_proxy_contract = health_payload.get(
        "last_known_good_proxy_contract"
    )
    if not isinstance(last_known_good_proxy_contract, dict):
        last_known_good_proxy_contract = (
            dependencies.build_last_known_good_proxy_contract(paths)
        )
    last_known_good_proxy = health_payload.get("last_known_good_proxy")
    if not isinstance(last_known_good_proxy, dict):
        last_known_good_proxy = dependencies.build_last_known_good_proxy_surface(
            paths, state, current_proxy_url
        )
    proxy_reprobe_adoption_result = health_payload.get("proxy_reprobe_adoption_result")
    if not isinstance(proxy_reprobe_adoption_result, dict):
        proxy_reprobe_adoption_result = None
    pool_summary = {
        "active": int(pool_counts.get("active", 0) or 0),
        "reserve": int(pool_counts.get("reserve", 0) or 0),
        "retired": int(pool_counts.get("retired", 0) or 0),
        "healthy": int(state.get("healthy_count", 0) or 0),
        "degraded": int(state.get("degraded_count", 0) or 0),
        "down": int(state.get("down_count", 0) or 0),
        "selected_backend_ids": state.get("selected_backend_ids") or [],
        "backend_count": len(registry.get("backends") or []),
    }
    auth_pool_hygiene = health_payload.get("auth_pool_hygiene")
    if isinstance(auth_pool_hygiene, dict):
        auth_pool_hygiene = {
            **auth_pool_hygiene,
            "delegated_from_status": True,
        }
    else:
        auth_pool_hygiene = dependencies.summarize_auth_pool_hygiene(registry, state)
        auth_pool_hygiene["delegated_from_status"] = False
    launch_readiness = health_payload.get("launch_readiness")
    if isinstance(launch_readiness, dict):
        launch_readiness = {
            **launch_readiness,
            "delegated_from_status": True,
        }
    native_auth_recovery_hint = health_payload.get("native_auth_recovery_hint")
    if isinstance(native_auth_recovery_hint, dict):
        native_auth_recovery_hint = {
            **native_auth_recovery_hint,
            "delegated_from_status": True,
        }
    else:
        native_auth_recovery_hint = dependencies.build_native_auth_recovery_hint(
            machine_error_code=delegated_machine_error_code,
            auth_pool_hygiene=auth_pool_hygiene,
        )
        native_auth_recovery_hint["delegated_from_status"] = False
    runtime_guardrails = health_payload.get("runtime_guardrails")
    if isinstance(runtime_guardrails, dict):
        runtime_guardrails = {
            **runtime_guardrails,
            "delegated_from_status": True,
            "owner_command_surface": "status --json",
        }
    else:
        runtime_guardrails = dependencies.build_runtime_guardrail_surface(
            paths,
            launch_readiness=launch_readiness if isinstance(launch_readiness, dict) else None,
            auth_pool_hygiene=auth_pool_hygiene if isinstance(auth_pool_hygiene, dict) else None,
            recovery_result=recovery_result if isinstance(recovery_result, dict) else None,
        )
        runtime_guardrails["delegated_from_status"] = False
        runtime_guardrails["owner_command_surface"] = "status --json"

    return dependencies.build_command_payload(
        ok=health_payload["status"] == "ok",
        human_message=(
            "Runtime status summary is available."
            if health_payload["status"] == "ok"
            else "Runtime status summary reflects live attestation failure."
        ),
        machine_error_code=delegated_machine_error_code,
        liveness=str(health_payload["liveness"]),
        severity=str(health_payload["severity"]),
        operator_action=(
            "user_action"
            if native_auth_recovery_hint.get("owner_action_required") is True
            and str(health_payload["operator_action"]) == "retry"
            else str(health_payload["operator_action"])
        ),
        changed_files=list(health_payload.get("changed_files") or []),
        exit_code=int(health_payload["exit_code"]),
        extra={
            "desired_mode": desired_mode,
            "effective_mode": health_payload["effective_mode"],
            "endpoint": health_payload["endpoint"],
            "configured_model": health_payload.get("configured_model"),
            "requested_model": health_payload.get("requested_model"),
            "configured_proxy_url": health_payload.get("configured_proxy_url"),
            "current_proxy_url": current_proxy_url,
            "current_proxy_adoption_contract": current_proxy_adoption_contract,
            "last_known_good_proxy_contract": last_known_good_proxy_contract,
            "last_known_good_proxy": last_known_good_proxy,
            **(
                {
                    "proxy_reprobe_adoption_result": proxy_reprobe_adoption_result,
                }
                if proxy_reprobe_adoption_result is not None
                else {}
            ),
            "pool_summary": pool_summary,
            "auth_pool_hygiene": auth_pool_hygiene,
            "native_auth_recovery_hint": native_auth_recovery_hint,
            "policy_drift": policy_drift,
            "policy_drift_observed": policy_drift_observed,
            "stable_runtime_consumer": stable_runtime_consumer,
            **(
                {
                    "launch_readiness": launch_readiness,
                }
                if isinstance(launch_readiness, dict)
                else {}
            ),
            **(
                {
                    "runtime_guardrails": runtime_guardrails,
                }
                if isinstance(runtime_guardrails, dict)
                else {}
            ),
            "registry_identity_summary": dependencies.summarize_registry_identity(
                registry_identity
            ),
            "claim_gate": dependencies.get_claim_gate(policy_drift, registry_identity),
            "last_error": (
                ""
                if health_payload["status"] == "ok"
                else health_payload.get("last_error", state.get("last_error", ""))
            ),
            "attestation_summary": {
                "status": health_payload["status"],
                "machine_error_code": health_payload["machine_error_code"],
                "attestation_source": health_payload["attestation"][
                    "attestation_source"
                ],
                "observed_at_utc": health_payload["attestation"]["observed_at_utc"],
            },
        },
    )
