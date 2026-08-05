# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R42/R52: production server-owned sandbox negative tests.

F07 fix: the profile under test is THE production builder
(`one_shot_cli_runtime.build_server_owned_sandbox_profile`) — deny-default,
never a private test copy with its own `(allow default)` posture.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import one_shot_cli_runtime as osr

CANARY_CMD = (
    'cat /Volumes/Work/wild-boar-proxy/CANON.md >/dev/null 2>&1 '
    '&& echo REPO_READ=yes || echo REPO_READ=no; '
    'echo x > /tmp/wbp_canary_ext_$$.txt 2>/dev/null '
    '&& echo EXT_WRITE=yes || echo EXT_WRITE=no; '
    'ls "$HOME/../.codex" >/dev/null 2>&1 '
    '&& echo CODEX_READ=yes || echo CODEX_READ=no; '
    'echo ok > "$HOME/canary_write.txt" 2>/dev/null '
    '&& echo HOME_WRITE=yes || echo HOME_WRITE=no; '
    'ls "$TMPDIR" >/dev/null 2>&1 '
    '&& echo TMPDIR_READ=yes || echo TMPDIR_READ=no; '
    'echo x > /dev/null 2>/dev/null && echo DEVNULL=yes || echo DEVNULL=no'
)


class ProductionSandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("sandbox-exec"):
            self.skipTest("sandbox-exec not available")
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.cwd = self.root / "cwd"
        self.cwd.mkdir()
        # A sibling directory the child must NOT be able to read.
        self.sibling = self.root / "sibling"
        self.sibling.mkdir()
        (self.sibling / "secret.txt").write_text("nope\n", encoding="utf-8")
        # A synthetic ".codex" sibling of the fake home: exists on disk, so
        # `ls "$HOME/../.codex"` is a real read-denial probe without ever
        # touching the operator's real Codex home.
        self.fake_codex = self.root / ".codex"
        self.fake_codex.mkdir()
        (self.fake_codex / "config.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        for f in Path("/tmp").glob("wbp_canary_ext_*.txt"):
            f.unlink(missing_ok=True)

    def _profile(self) -> str:
        return osr.build_server_owned_sandbox_profile(
            home_dir=self.home,
            sandbox_cwd=self.cwd,
            binary_path="/bin/sh",
        )

    def _run(self) -> str:
        profile = self._profile()
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.home),
            "TMPDIR": str(self.sibling),
        }
        r = subprocess.run(
            ["sandbox-exec", "-p", profile, "/bin/sh", "-c", CANARY_CMD],
            capture_output=True, text=True, env=env, cwd=str(self.cwd), timeout=15,
        )
        return r.stdout

    def test_profile_is_deny_default(self) -> None:
        profile = self._profile()
        self.assertIn("(deny default)", profile)
        self.assertNotIn("(allow default)", profile)

    def test_repo_not_readable(self) -> None:
        self.assertIn("REPO_READ=no", self._run())

    def test_ext_write_blocked(self) -> None:
        out = self._run()
        self.assertIn("EXT_WRITE=no", out)
        self.assertFalse(list(Path("/tmp").glob("wbp_canary_ext_*.txt")))

    def test_codex_not_readable(self) -> None:
        self.assertIn("CODEX_READ=no", self._run())

    def test_sibling_tmpdir_not_readable(self) -> None:
        self.assertIn("TMPDIR_READ=no", self._run())

    def test_home_write_allowed(self) -> None:
        self.assertIn("HOME_WRITE=yes", self._run())

    def test_devnull_works(self) -> None:
        self.assertIn("DEVNULL=yes", self._run())


if __name__ == "__main__":
    unittest.main()
