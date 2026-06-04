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
