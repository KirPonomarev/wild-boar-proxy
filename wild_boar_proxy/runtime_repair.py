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
