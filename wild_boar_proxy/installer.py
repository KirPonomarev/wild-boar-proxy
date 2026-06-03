# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class InstallerPaths(Protocol):
    pass


@dataclass(frozen=True)
class InstallerDependencies:
    run_installer_init_impl: Callable[..., dict[str, Any]]


def run_installer_init(
    paths: InstallerPaths,
    *,
    dependencies: InstallerDependencies,
) -> dict[str, Any]:
    return dependencies.run_installer_init_impl(paths)
