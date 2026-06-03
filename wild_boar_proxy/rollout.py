# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class RolloutPaths(Protocol):
    pass


@dataclass(frozen=True)
class RolloutDependencies:
    run_rollout_rotation_inspect_impl: Callable[..., dict[str, Any]]
    run_rollout_posture_inspect_impl: Callable[..., dict[str, Any]]


def run_rollout_rotation_inspect(
    paths: RolloutPaths,
    *,
    lock_acquired: bool = False,
    dependencies: RolloutDependencies,
) -> dict[str, Any]:
    return dependencies.run_rollout_rotation_inspect_impl(
        paths,
        lock_acquired=lock_acquired,
    )


def run_rollout_posture_inspect(
    paths: RolloutPaths,
    stage: str,
    *,
    dependencies: RolloutDependencies,
) -> dict[str, Any]:
    return dependencies.run_rollout_posture_inspect_impl(paths, stage)
