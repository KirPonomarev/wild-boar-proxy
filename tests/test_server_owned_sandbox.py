# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R42: production server-owned sandbox negative tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

CANARY_CMD = (
    'cat /Volumes/Work/wild-boar-proxy/CANON.md >/dev/null 2>&1 '
    '&& echo REPO_READ=yes || echo REPO_READ=no; '
    'echo x > /tmp/wbp_canary_ext_$$.txt 2>/dev/null '
    '&& echo EXT_WRITE=yes || echo EXT_WRITE=no; '
    'ls "$HOME/../.codex" >/dev/null 2>&1 '
    '&& echo CODEX_READ=yes || echo CODEX_READ=no; '
    'echo ok > "$HOME/canary_write.txt" 2>/dev/null '
    '&& echo HOME_WRITE=yes || echo HOME_WRITE=no; '
    'echo x > /dev/null 2>/dev/null && echo DEVNULL=yes || echo DEVNULL=no'
)


def _build_production_profile(*, home_dir: str, sandbox_cwd: str) -> str:
    codex = os.path.realpath(os.path.expanduser("~/.codex"))
    repo = "/Volumes/Work/wild-boar-proxy"
    profiles = os.path.realpath(
        os.path.expanduser("~/Library/Application Support/WildBoarProxy/CodexProfiles")
    )
    home_r = os.path.realpath(home_dir)
    cwd_r = os.path.realpath(sandbox_cwd)
    return "\n".join([
        "(version 1)",
        "(allow default)",
        f'(deny file-read-data (subpath "{codex}"))',
        f'(deny file-write* (subpath "{codex}"))',
        f'(deny file-read-data (subpath "{repo}"))',
        f'(deny file-write* (subpath "{repo}"))',
        f'(deny file-read-data (subpath "{profiles}"))',
        f'(deny file-write* (subpath "{profiles}"))',
        "(deny file-write*)",
        f'(allow file-write* (subpath "{cwd_r}"))',
        f'(allow file-write* (subpath "{home_r}"))',
        '(allow file-write-data (subpath "/dev/dtracehelper"))',
        '(allow file-write-data (subpath "/dev/null"))',
        "(allow ipc-posix-shm)",
    ]) + "\n"


class ProductionSandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("sandbox-exec"):
            self.skipTest("sandbox-exec not available")
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp")
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.cwd = self.root / "cwd"
        self.cwd.mkdir()

    def tearDown(self) -> None:
        for f in Path("/tmp").glob("wbp_canary_ext_*.txt"):
            f.unlink(missing_ok=True)
        self.tmp.cleanup()

    def _run(self) -> str:
        profile = _build_production_profile(
            home_dir=str(self.home), sandbox_cwd=str(self.cwd),
        )
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home)}
        r = subprocess.run(
            ["sandbox-exec", "-p", profile, "/bin/sh", "-c", CANARY_CMD],
            capture_output=True, text=True, env=env, cwd=str(self.cwd), timeout=15,
        )
        return r.stdout

    def test_repo_not_readable(self) -> None:
        self.assertIn("REPO_READ=no", self._run())

    def test_ext_write_blocked(self) -> None:
        out = self._run()
        self.assertIn("EXT_WRITE=no", out)
        self.assertFalse(list(Path("/tmp").glob("wbp_canary_ext_*.txt")))

    def test_codex_not_readable(self) -> None:
        self.assertIn("CODEX_READ=no", self._run())

    def test_home_write_allowed(self) -> None:
        self.assertIn("HOME_WRITE=yes", self._run())

    def test_devnull_works(self) -> None:
        self.assertIn("DEVNULL=yes", self._run())


if __name__ == "__main__":
    unittest.main()
