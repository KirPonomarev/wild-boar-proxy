#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path


FIXTURE_ROOT = Path("tests/fixtures/historical_audit_results")


def historical_audit_root(repo_root: Path) -> Path:
    fixture_root = repo_root / FIXTURE_ROOT
    if fixture_root.is_dir():
        return fixture_root
    return repo_root


def historical_audit_path(repo_root: Path, relative_path: str | Path) -> Path:
    return historical_audit_root(repo_root) / relative_path
