# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class AccountLifecyclePaths(Protocol):
    pass


@dataclass(frozen=True)
class AccountLifecycleDependencies:
    run_protective_lifecycle_owner_path: Callable[..., dict[str, Any]]
    run_demote_impl: Callable[..., dict[str, Any]]
    run_retire_impl: Callable[..., dict[str, Any]]


def run_hold(
    paths: AccountLifecyclePaths,
    backend_id: str,
    reason: str | None,
    *,
    dry_run: bool = False,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_protective_lifecycle_owner_path(
        paths,
        backend_id,
        action="hold",
        reason=reason,
        dry_run=dry_run,
    )


def run_release(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_protective_lifecycle_owner_path(
        paths,
        backend_id,
        action="release",
    )


def run_demote(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_demote_impl(paths, backend_id)


def run_retire(
    paths: AccountLifecyclePaths,
    backend_id: str,
    *,
    dependencies: AccountLifecycleDependencies,
) -> dict[str, Any]:
    return dependencies.run_retire_impl(paths, backend_id)
