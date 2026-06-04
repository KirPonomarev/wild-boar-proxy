# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Protocol

from .command_effects import EFFECT_REPAIR


class RuntimeRepairPaths(Protocol):
    auth_file: Path
    config_toml: Path
    managed_config_file: Path
    registry_file: Path
    repair_target_inventory_dir: Path
    repair_target_reference_file: Path
    runtime_effective_mode_file: Path
    stable_config: Path
    stable_runtime_generated_config_file: Path
    state_file: Path
    sync_script: Path


@dataclass(frozen=True)
class HealthcheckRepairDependencies:
    run_healthcheck: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class HealthcheckRepairContract:
    allow_recovery: bool
    allow_last_known_good_proxy_write: bool
    allow_current_proxy_auto_adoption: bool
    allow_stable_fallback_write: bool
    allow_stale_pid_cleanup: bool
    effect: str

    def kwargs(self) -> dict[str, object]:
        return {
            "allow_recovery": self.allow_recovery,
            "allow_last_known_good_proxy_write": (
                self.allow_last_known_good_proxy_write
            ),
            "allow_current_proxy_auto_adoption": (
                self.allow_current_proxy_auto_adoption
            ),
            "allow_stable_fallback_write": self.allow_stable_fallback_write,
            "allow_stale_pid_cleanup": self.allow_stale_pid_cleanup,
            "effect": self.effect,
        }


HEALTHCHECK_REPAIR_CONTRACT: Final = HealthcheckRepairContract(
    allow_recovery=True,
    allow_last_known_good_proxy_write=True,
    allow_current_proxy_auto_adoption=True,
    allow_stable_fallback_write=True,
    allow_stale_pid_cleanup=True,
    effect=EFFECT_REPAIR,
)

STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV: Final = "WBP_STABLE_CONFIG"
STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC: Final = "stable_runtime_consumer_snapshot"
LAST_KNOWN_GOOD_PROXY_URL_FIELD: Final = "last_known_good_proxy_url"
LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD: Final = (
    "last_known_good_proxy_observed_at"
)


def build_deterministic_stable_recovery_contract(
    paths: RuntimeRepairPaths,
) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "entry_owner": "healthcheck_live_attestation_path",
        "owner_command_surface": "healthcheck --repair --json",
        "status_delegates_to_owner": False,
        "sync_hidden_owner_forbidden": True,
        "new_generic_cli_default": False,
        "eligible_failure_lanes": [
            "managed_preflight_failure",
            "stable_service_disabled",
            "explicit_stable_recovery_lane",
        ],
        "entry_lane_surface": {
            "status": "owner_path_emitted",
            "field": "deterministic_stable_recovery_result.entry_lane",
            "nested_recovery_surface": True,
            "top_level_machine_error_code_separate": True,
            "allowed_values": [
                "managed_preflight_failure",
                "stable_service_disabled",
                "explicit_stable_recovery_lane",
                "not_invoked",
            ],
        },
        "failure_taxonomy_redesign_forbidden": True,
        "shared_activation_mechanics": {
            "status": "owner_path_emitted",
            "reuse_existing_launch_smoke_activation_helper": True,
            "generated_config_file": str(paths.stable_runtime_generated_config_file),
            "handoff_env_var": STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
            "snapshot_topic": STABLE_RUNTIME_CONSUMER_SNAPSHOT_TOPIC,
            "owner_paths": ["healthcheck --repair --json", "launch smoke --json"],
        },
        "generated_config_regeneration_status": "owner_path_emitted",
        "generated_config_regeneration_policy": "regenerate_each_recovery_attempt",
        "generated_config_derivation_source": (
            "current_baseline_stable_config_plus_current_approved_target_reference"
        ),
        "generated_config_regeneration_owner_paths": [
            "healthcheck --repair --json",
            "launch smoke --json",
        ],
        "stale_generated_config_authoritative": False,
        "generated_config_existence_alone_sufficient": False,
        "snapshot_refresh_status": "owner_path_emitted",
        "snapshot_refresh_after_stable_live_outcome": True,
        "snapshot_refresh_owner_paths": [
            "healthcheck --repair --json",
            "launch smoke --json",
        ],
        "snapshot_schema_widening_required": False,
        "new_persisted_recovery_metadata_required": False,
        "stable_service_disabled_classification": {
            "status": "owner_path_emitted",
            "classification_surface": "deterministic_stable_recovery_result.entry_lane",
            "control_layer_classification": True,
            "persisted_engine_state_flag": False,
            "positive_evidence_required": True,
            "desired_mode_alone_sufficient": False,
            "generated_config_existence_alone_sufficient": False,
            "snapshot_presence_alone_sufficient": False,
            "bounded_reenable_lane_eligible_required": True,
            "proxy_path_failure_codes_separate": [
                "PROXY_PATH_BROKEN",
                "PROXY_REPROBE_FAILED",
            ],
            "generic_listener_down_fallback": "LISTENER_DOWN",
            "overclassification_forbidden": True,
        },
        "re_enable_method_contract": {
            "status": "owner_path_emitted",
            "owner_path_scope": "bounded_control_layer_recovery_action",
            "owner_command_surface": "healthcheck --repair --json",
            "reuse_private_launch_smoke_helper_allowed": True,
            "launcher_protocol_widening_required": False,
            "launchd_integration_forbidden": True,
            "os_service_manager_integration_forbidden": True,
            "generic_service_supervision_forbidden": True,
        },
        "approved_target_recovery_outcome": "separate",
        "observed_source_fallback_recovery_outcome": "separate",
        "recovery_failure_outcome": "separate",
        "top_level_truth_boundaries": {
            "status": "contract_ready",
            "top_level_final_truth_fields": [
                "status",
                "machine_error_code",
                "liveness",
                "endpoint",
            ],
            "nested_recovery_surface": "deterministic_stable_recovery_result",
            "final_live_truth_separate": True,
            "launch_smoke_owner_lane_fields_forbidden": True,
            "status_second_owner_forbidden": True,
            "sync_owner_lane_forbidden": True,
        },
        "top_level_machine_error_code_rules": {
            "status": "owner_path_emitted",
            "stable_service_disabled_final_code": "STABLE_SERVICE_DISABLED",
            "stable_service_disabled_requires_final_unhealthy": True,
            "ok_after_successful_reenable": "OK",
            "generic_listener_down_fallback": "LISTENER_DOWN",
            "proxy_path_codes_remain_separate": True,
        },
        "live_runtime_observation_required": True,
        "mode_truth_redefinition_forbidden": True,
        "last_known_good_proxy_persistence_in_scope": False,
    }


def build_startup_contract_repair_contract() -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "entry_owner": "healthcheck_startup_contract_repair_path",
        "owner_command_surface": "healthcheck --repair --json",
        "status_delegates_to_owner": False,
        "healthcheck_probe_owner_forbidden": True,
        "status_second_owner_forbidden": True,
        "stable_recovery_surface_redefinition_forbidden": True,
        "same_source_lock_invariant_required": True,
        "schema_auto_migrate_forbidden": True,
        "truth_file_rewrite_forbidden": True,
        "covered_startup_slices": [
            "temp_recovery",
            "lock_slice_recovery",
            "schema_slice_assessment",
            "truth_slice_assessment",
        ],
        "top_level_truth_boundaries": {
            "status": "contract_ready",
            "nested_recovery_surface": "startup_contract_repair_result",
            "final_live_truth_separate": True,
            "startup_cleanup_alone_sufficient": False,
            "top_level_ok_requires_live_attestation": True,
        },
    }


def build_last_known_good_proxy_contract(paths: RuntimeRepairPaths) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "owner_command_surface": "healthcheck --repair --json",
        "status_delegates_to_owner": False,
        "sync_owner_forbidden": True,
        "launch_smoke_owner_forbidden": True,
        "launcher_lane_ineligible_sync_owner_recovery_surface": {
            "status": "available" if paths.sync_script.exists() else "unavailable",
            "command_surface": "sync --json",
            "owner_path_private": True,
            "allowed_when_launcher_lane_ineligible": True,
            "restart_scope": "managed_runtime_restart_with_proxy_refresh",
            "writes_managed_config_proxy_url": True,
            "reproof_required": True,
        },
        "state_file": str(paths.state_file),
        "state_fields": [
            LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            LAST_KNOWN_GOOD_PROXY_OBSERVED_AT_FIELD,
        ],
        "current_proxy_url_field": "current_proxy_url",
        "current_proxy_url_reuse_forbidden": True,
        "separate_metadata_file_default": False,
        "write_owner": "serialized_healthcheck_owner_path",
        "write_path_status": "owner_path_emitted",
        "refresh_requires_positive_managed_proxy_proof": True,
        "refresh_from_candidate_liveness_alone_forbidden": True,
        "refresh_from_current_proxy_url_alone_forbidden": True,
        "failed_reprobe_clears_persisted_value": False,
        "candidate_input_priority": [
            "WBP_PROXY_REPROBE_CANDIDATES",
            LAST_KNOWN_GOOD_PROXY_URL_FIELD,
            "current_proxy_url",
            "legacy.default_local_proxy_candidates",
            "legacy.dynamic_local_listener_candidates",
        ],
        "candidate_inputs_bounded_local_only": True,
        "candidate_input_deduped_after_filter": True,
        "changed_files_visibility_required": True,
        "historical_truth_promotes_live_truth": False,
    }


def build_stable_runtime_launcher_handoff_contract(
    paths: RuntimeRepairPaths,
) -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "handoff_method": "process_local_env_override",
        "env_var": STABLE_RUNTIME_LAUNCHER_HANDOFF_ENV,
        "generated_config_file": str(paths.stable_runtime_generated_config_file),
        "scope": "launcher_subprocess_only",
        "recovery_scope": "explicit_stable_runtime_recovery_only",
        "baseline_config_rewrite_forbidden": True,
        "generic_config_routing_forbidden": True,
    }


def build_stable_runtime_effective_truth_contract() -> dict[str, Any]:
    return {
        "status": "contract_ready",
        "truth_source": "live_runtime_observation_plus_snapshot_evidence",
        "desired_source_alone_sufficient": False,
        "generated_config_existence_alone_sufficient": False,
        "activation_evidence_snapshot_alone_sufficient": False,
        "live_runtime_observation_required": True,
        "baseline_config_is_observation_surface": True,
    }


def build_deterministic_stable_recovery_result(
    *,
    owner_command_surface: str = "healthcheck --repair --json",
    delegated_from_status: bool,
    attempted: bool,
    entry_lane: str,
    outcome: str,
    re_enable_method: str,
    selected_source_kind: str,
    selected_source_path: str,
    generated_config_regenerated: bool,
    snapshot_refreshed: bool,
    fallback_reason: str,
    live_runtime_observation_confirmed: bool,
    confirmation_basis: str,
    effectful_claim_allowed: bool,
    process_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not attempted:
        status = "not_invoked"
        guardrail_status = "not_invoked"
    elif outcome == "recovery_failed_before_stable_healthy":
        status = "failed"
        guardrail_status = "blocked"
    elif effectful_claim_allowed:
        status = "completed"
        guardrail_status = "confirmed"
    else:
        status = "completed"
        guardrail_status = "observation_only"
    result = {
        "status": status,
        "owner_command_surface": owner_command_surface,
        "delegated_from_status": delegated_from_status,
        "attempted": attempted,
        "entry_lane": entry_lane,
        "outcome": outcome,
        "re_enable_method": re_enable_method,
        "selected_source_kind": selected_source_kind,
        "selected_source_path": selected_source_path,
        "generated_config_regenerated": generated_config_regenerated,
        "snapshot_refreshed": snapshot_refreshed,
        "fallback_reason": fallback_reason,
        "live_runtime_observation_confirmed": live_runtime_observation_confirmed,
        "confirmation_basis": confirmation_basis,
        "effectful_claim_allowed": effectful_claim_allowed,
        "guardrail_status": guardrail_status,
    }
    if process_result is not None:
        result["process_result"] = process_result
    return result


def run_healthcheck_repair(
    paths: RuntimeRepairPaths,
    model: str | None = None,
    *,
    dependencies: HealthcheckRepairDependencies,
) -> dict[str, Any]:
    return dependencies.run_healthcheck(
        paths,
        model,
        **HEALTHCHECK_REPAIR_CONTRACT.kwargs(),
    )
