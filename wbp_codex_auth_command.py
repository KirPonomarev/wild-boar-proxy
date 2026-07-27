#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-owned executable auth.command helper for local Codex provider runs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from wild_boar_proxy.runtime import RuntimeErrorInfo, RuntimePaths
from wild_boar_proxy.token_command import (
    emit_local_token,
    emit_local_token_from_config_path,
)


def main() -> int:
    try:
        stable_config_override = os.environ.get("WBP_STABLE_CONFIG", "").strip()
        if stable_config_override:
            sys.stdout.write(
                emit_local_token_from_config_path(
                    Path(stable_config_override).expanduser()
                )
            )
        else:
            sys.stdout.write(emit_local_token(RuntimePaths.from_env()))
        return 0
    except RuntimeErrorInfo as exc:
        sys.stderr.write(f"{exc.message}\n")
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
