# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class PackagingPaths(Protocol):
    pass


@dataclass(frozen=True)
class PackagingDependencies:
    run_package_experimental_build_impl: Callable[..., dict[str, Any]]
    run_package_experimental_verify_impl: Callable[..., dict[str, Any]]


def run_package_experimental_build(
    paths: PackagingPaths,
    output_dir_raw: str,
    *,
    dependencies: PackagingDependencies,
) -> dict[str, Any]:
    return dependencies.run_package_experimental_build_impl(paths, output_dir_raw)


def run_package_experimental_verify(
    paths: PackagingPaths,
    manifest_raw: str,
    *,
    dependencies: PackagingDependencies,
) -> dict[str, Any]:
    return dependencies.run_package_experimental_verify_impl(paths, manifest_raw)
