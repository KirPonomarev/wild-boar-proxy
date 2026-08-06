# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hermetic git fixture for final assurance identity tests.

The final assurance audit validates that each milestone identity resolves to
an existing commit via ``git rev-parse`` run in
``desktop_pilot_contract._REPO_ROOT``. Resolving the real
``v0.1.0`` / ``v0.2.0`` / ``v0.3.0`` release tags is non-hermetic: a clean CI
checkout may not fetch tags, in which case every milestone falls back to
``HEAD``, all three identities collapse to one SHA, and the audit fails with
``FINAL_ASSURANCE_SHA_COLLISION`` instead of the verdict under test.

``install_final_assurance_git_fixture`` builds a tiny isolated git repository
with three tagged commits and patches ``_REPO_ROOT`` so tests exercise the
real audit logic (shape check, existence check, collision check, completeness
check) against a fully controlled fixture world that is independent of the
host checkout's tags, history depth, and global git configuration.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy import desktop_pilot_contract as dpc

MILESTONE_TAGS = {
    "web_v0_1_0": "v0.1.0",
    "provider_v0_2_0": "v0.2.0",
    "desktop_v0_3_0": "v0.3.0",
}


def _git(repo: Path, *args: str) -> str:
    # Isolated from the owner's global/system git config: a host config with
    # commit.gpgsign=true or unusual aliases must not change fixture behaviour.
    env = dict(
        os.environ,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_TERMINAL_PROMPT="0",
    )
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=WBP Final Assurance Fixture",
            "-c",
            "user.email=wbp-final-assurance-fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"final assurance fixture git {' '.join(args)!r} failed: "
            f"{result.returncode}: {result.stderr.strip()}"
        )
    return result.stdout


def install_final_assurance_git_fixture(
    test_class: type[unittest.TestCase],
) -> dict[str, str]:
    """Build the isolated milestone repo and patch ``dpc._REPO_ROOT`` to it.

    Registers class cleanups that restore ``_REPO_ROOT`` and remove the
    temporary repository. Returns the resolved milestone SHAs.
    """
    tmp = tempfile.TemporaryDirectory(prefix="wbp-final-assurance-fixture-")
    repo = Path(tmp.name)
    _git(repo, "init", "-q", "-b", "main")
    for milestone, tag in MILESTONE_TAGS.items():
        (repo / f"{milestone}.txt").write_text(milestone + "\n", encoding="utf-8")
        _git(repo, "add", f"{milestone}.txt")
        _git(repo, "commit", "-q", "-m", milestone)
        _git(repo, "tag", tag)
    patcher = mock.patch.object(dpc, "_REPO_ROOT", str(repo))
    patcher.start()
    test_class.addClassCleanup(patcher.stop)
    test_class.addClassCleanup(tmp.cleanup)
    return {
        milestone: _git(repo, "rev-list", "-n1", tag).strip()
        for milestone, tag in MILESTONE_TAGS.items()
    }
