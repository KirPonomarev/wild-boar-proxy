# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Protocol

from .command_effects import EFFECT_PROBE


class RuntimeHealthPaths(Protocol):
    auth_file: Path
    config_toml: Path
    managed_config_file: Path
    registry_file: Path
    runtime_effective_mode_file: Path
    stable_config: Path
    state_file: Path


@dataclass(frozen=True)
class HealthProbeDependencies:
    run_healthcheck: Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class HealthcheckProbeContract:
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


HEALTHCHECK_PROBE_CONTRACT: Final = HealthcheckProbeContract(
    allow_recovery=False,
    allow_last_known_good_proxy_write=False,
    allow_current_proxy_auto_adoption=False,
    allow_stable_fallback_write=False,
    allow_stale_pid_cleanup=False,
    effect=EFFECT_PROBE,
)


def build_native_auth_recovery_hint_from_inputs(
    *,
    machine_error_code: str,
    launch_capable_backend_count: int,
    selected_backend_observed_count: int,
    selected_backend_runtime_loaded_count: int,
    selected_backend_observation_source: str,
) -> dict[str, Any]:
    base_packet = {
        "launch_capable_backend_count": launch_capable_backend_count,
        "selected_backend_observed_count": selected_backend_observed_count,
        "selected_backend_runtime_loaded_count": (
            selected_backend_runtime_loaded_count
        ),
        "selected_backend_observation_source": selected_backend_observation_source,
        "selection_gap_detected": (
            selected_backend_runtime_loaded_count <= 0
            and selected_backend_observed_count > 0
        ),
        "api_fallback_counts_as_native_recovery": False,
        "claim_scope": "bounded_native_auth_recovery_only",
    }
    if machine_error_code != "AUTH_UNAVAILABLE":
        return {
            "status": "not_needed",
            "machine_error_code": machine_error_code or "OK",
            "owner_action_required": False,
            "next_action": "none",
            "command_surface": "",
            "reason": "",
            **base_packet,
        }
    if launch_capable_backend_count <= 0:
        return {
            "status": "blocked_no_launch_capable_backend",
            "machine_error_code": machine_error_code,
            "owner_action_required": False,
            "next_action": "inspect_accounts_inventory",
            "command_surface": "accounts list --json",
            "reason": "auth_unavailable_without_launch_capable_backend",
            **base_packet,
        }
    if selected_backend_observed_count <= 0:
        return {
            "status": "sync_recommended",
            "machine_error_code": machine_error_code,
            "owner_action_required": False,
            "next_action": "sync",
            "command_surface": "sync --json",
            "reason": "launch_capable_available_without_selected_backend_observation",
            **base_packet,
        }
    if selected_backend_runtime_loaded_count <= 0:
        return {
            "status": "runtime_auth_gap_repair_recommended",
            "machine_error_code": machine_error_code,
            "owner_action_required": False,
            "next_action": "run_healthcheck_repair_if_authorized",
            "command_surface": "healthcheck --repair --json",
            "reason": "auth_unavailable_with_selected_backend_not_loaded",
            **base_packet,
        }
    return {
        "status": "owner_action_required",
        "machine_error_code": machine_error_code,
        "owner_action_required": True,
        "next_action": "accounts_login_start",
        "command_surface": "accounts login start --provider codex --mode device --json",
        "reason": "auth_unavailable_after_selected_backend_observation",
        **base_packet,
    }


def build_launch_readiness_surface(
    *,
    owner_command_surface: str,
    delegated_from_status: bool,
    listener_ok: bool,
    models_ok: bool,
    responses_ok: bool,
    base_url_match: bool,
    effective_mode_match: bool,
    model_match: bool,
    proxy_url_match: bool,
    machine_error_code: str,
    error_detail: str,
    auth_pool_hygiene: dict[str, Any] | None = None,
    identity_proof_required: bool = False,
    identity_proof_ok: bool = True,
    identity_failure_reason: str = "",
) -> dict[str, Any]:
    failed_checks: list[str] = []
    if not listener_ok:
        failed_checks.append("listener_unreachable")
    if listener_ok and not models_ok:
        failed_checks.append("models_surface_unavailable_or_invalid")
    if listener_ok and models_ok and not responses_ok:
        failed_checks.append("responses_probe_failed")
    if not base_url_match:
        failed_checks.append("base_url_mismatch")
    if not effective_mode_match:
        failed_checks.append("effective_mode_truth_drift")
    if not model_match:
        failed_checks.append("model_truth_drift")
    if not proxy_url_match:
        failed_checks.append("proxy_truth_drift")
    if identity_proof_required and not identity_proof_ok:
        failed_checks.append("runtime_identity_unproven")
    auth_pool_hygiene_status = ""
    launch_capable_backend_count = None
    if isinstance(auth_pool_hygiene, dict):
        auth_pool_hygiene_status = str(auth_pool_hygiene.get("status", ""))
        launch_capable_backend_count = auth_pool_hygiene.get(
            "launch_capable_backend_count"
        )
        if (
            listener_ok
            and models_ok
            and not responses_ok
            and auth_pool_hygiene_status == "launch_capable_empty"
        ):
            failed_checks.insert(0, "usable_auth_pool_empty")
    gate_passed = not failed_checks
    return {
        "status": "ready" if gate_passed else "blocked",
        "owner_command_surface": owner_command_surface,
        "delegated_from_status": delegated_from_status,
        "real_inference_required": True,
        "listener_reachable": listener_ok,
        "models_surface_reachable": models_ok,
        "responses_proof_passed": responses_ok,
        "truth_alignment_passed": (
            base_url_match and effective_mode_match and model_match and proxy_url_match
        ),
        "base_url_match": base_url_match,
        "effective_mode_match": effective_mode_match,
        "model_match": model_match,
        "proxy_url_match": proxy_url_match,
        "runtime_identity_required": identity_proof_required,
        "runtime_identity_proof_passed": identity_proof_ok,
        "runtime_identity_failure_reason": identity_failure_reason,
        "gate_passed": gate_passed,
        "blocking_reason": "" if gate_passed else failed_checks[0],
        "failed_checks": failed_checks,
        "machine_error_code": machine_error_code,
        "last_error": error_detail,
        "auth_pool_hygiene_status": auth_pool_hygiene_status,
        "launch_capable_backend_count": launch_capable_backend_count,
    }


def build_runtime_guardrail_surface_from_preflight(
    *,
    lock_preflight: dict[str, Any],
    launch_readiness: dict[str, Any] | None,
    auth_pool_hygiene: dict[str, Any] | None,
    recovery_result: dict[str, Any] | None,
) -> dict[str, Any]:
    failed_checks: list[str] = []
    lock_status = str(lock_preflight.get("status", "unknown"))
    if lock_status == "held":
        failed_checks.append("mutation_lock_held")
    elif lock_status == "stale":
        failed_checks.append("mutation_lock_stale")
    elif lock_status == "invalid":
        failed_checks.append("mutation_lock_invalid")

    launch_status = ""
    launch_blocking_reason = ""
    if isinstance(launch_readiness, dict):
        launch_status = str(launch_readiness.get("status", ""))
        launch_blocking_reason = str(launch_readiness.get("blocking_reason", ""))
        if launch_status == "blocked" and launch_blocking_reason:
            failed_checks.append(launch_blocking_reason)

    auth_pool_status = ""
    auth_pool_blocking_reason = ""
    if isinstance(auth_pool_hygiene, dict):
        auth_pool_status = str(auth_pool_hygiene.get("status", ""))
        auth_pool_blocking_reason = str(auth_pool_hygiene.get("blocking_reason", ""))
        if auth_pool_status == "launch_capable_empty" and auth_pool_blocking_reason:
            if auth_pool_blocking_reason not in failed_checks:
                failed_checks.append(auth_pool_blocking_reason)

    recovery_guardrail_status = ""
    recovery_confirmation_basis = ""
    recovery_effectful_claim_allowed = None
    if isinstance(recovery_result, dict):
        recovery_guardrail_status = str(recovery_result.get("guardrail_status", ""))
        recovery_confirmation_basis = str(recovery_result.get("confirmation_basis", ""))
        recovery_effectful_claim_allowed = recovery_result.get(
            "effectful_claim_allowed"
        )
        if recovery_guardrail_status == "blocked":
            failed_checks.append("recovery_claim_blocked")

    if failed_checks:
        status = "blocked"
    elif recovery_guardrail_status == "observation_only":
        status = "caution"
    else:
        status = "clear"

    return {
        "status": status,
        "owner_command_surface": "healthcheck --json",
        "lock_status": lock_status,
        "launch_readiness_status": launch_status,
        "launch_blocking_reason": launch_blocking_reason,
        "auth_pool_hygiene_status": auth_pool_status,
        "auth_pool_blocking_reason": auth_pool_blocking_reason,
        "recovery_guardrail_status": recovery_guardrail_status,
        "recovery_confirmation_basis": recovery_confirmation_basis,
        "recovery_effectful_claim_allowed": recovery_effectful_claim_allowed,
        "failed_checks": failed_checks,
        "blocking_reason": "" if not failed_checks else failed_checks[0],
    }


def run_healthcheck_probe(
    paths: RuntimeHealthPaths,
    model: str | None = None,
    *,
    dependencies: HealthProbeDependencies,
) -> dict[str, Any]:
    return dependencies.run_healthcheck(
        paths,
        model,
        **HEALTHCHECK_PROBE_CONTRACT.kwargs(),
    )
