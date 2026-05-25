#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-owned executable auth.command helper for local Codex provider runs."""

from __future__ import annotations

import sys

from wild_boar_proxy.runtime import RuntimeErrorInfo, RuntimePaths
from wild_boar_proxy.token_command import emit_local_token


def main() -> int:
    try:
        sys.stdout.write(emit_local_token(RuntimePaths.from_env()))
        return 0
    except RuntimeErrorInfo as exc:
        sys.stderr.write(f"{exc.message}\n")
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
