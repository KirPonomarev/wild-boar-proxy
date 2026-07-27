from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_root_on_sys_path() -> None:
    """Make `pytest` invocations behave like `python -m pytest`.

    This repo is intentionally lightweight (no packaging/installation step).
    When running `pytest` via the entrypoint script, `sys.path[0]` points at the
    script directory (e.g. /opt/homebrew/bin), so the repo root may not be on
    `sys.path`, causing `ModuleNotFoundError: wild_boar_proxy`.
    """

    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


_ensure_repo_root_on_sys_path()

