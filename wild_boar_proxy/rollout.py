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
    run_rollout_evidence_capture_impl: Callable[..., dict[str, Any]]
    run_rollout_stage_prove_impl: Callable[..., dict[str, Any]]
    run_rollout_stage_advance_impl: Callable[..., dict[str, Any]]


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


def run_rollout_evidence_capture(
    paths: RolloutPaths,
    target: str,
    *,
    dependencies: RolloutDependencies,
) -> dict[str, Any]:
    return dependencies.run_rollout_evidence_capture_impl(paths, target)


def run_rollout_stage_prove(
    paths: RolloutPaths,
    stage: str,
    *,
    lock_acquired: bool = False,
    dependencies: RolloutDependencies,
) -> dict[str, Any]:
    return dependencies.run_rollout_stage_prove_impl(
        paths,
        stage,
        lock_acquired=lock_acquired,
    )


def run_rollout_stage_advance(
    paths: RolloutPaths,
    stage: str,
    backend_id: str,
    *,
    dependencies: RolloutDependencies,
) -> dict[str, Any]:
    return dependencies.run_rollout_stage_advance_impl(paths, stage, backend_id)
