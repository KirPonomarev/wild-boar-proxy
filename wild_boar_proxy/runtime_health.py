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
