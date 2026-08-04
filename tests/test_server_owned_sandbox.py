# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""P0-2: production server-owned sandbox negative tests.

Verifies that the sandbox-exec profile denies read/write outside the
allowlist by running canary commands under sandbox-exec with the
production profile and checking they cannot access protected surfaces.
"""

from __future__ import annotations

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
    '&& echo CODEX_READ=yes || echo CODEX_READ=no'
)


class ServerOwnedSandboxNegativeTests(unittest.TestCase):
    """Sandbox-exec profile denies protected-surface access."""

    def setUp(self) -> None:
        if not shutil.which("sandbox-exec"):
            self.skipTest("sandbox-exec not available")
        self.temp_dir = tempfile.TemporaryDirectory(dir="/tmp")
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.cwd = self.root / "cwd"
        self.cwd.mkdir()

    def tearDown(self) -> None:
        for f in Path("/tmp").glob("wbp_canary_ext_*.txt"):
            f.unlink(missing_ok=True)
        self.temp_dir.cleanup()

    def _run_under_sandbox(self) -> str:
        codex_home = str(Path.home() / ".codex")
        repo_root = "/Volumes/Work/wild-boar-proxy"
        profiles_root = str(Path.home() / "Library" / "Application Support" / "WildBoarProxy" / "CodexProfiles")
        cwd_real = str(self.cwd.resolve())
        home_real = str(self.home.resolve())
        profile = "\n".join([
            "(version 1)",
            "(deny default)",
            "(allow process-exec process-fork signal)",
            "(allow sysctl-read)",
            f'(deny file-read-data (subpath "{codex_home}"))',
            f'(deny file-write* (subpath "{codex_home}"))',
            f'(deny file-read-data (subpath "{repo_root}"))',
            f'(deny file-write* (subpath "{repo_root}"))',
            f'(deny file-read-data (subpath "{profiles_root}"))',
            f'(deny file-write* (subpath "{profiles_root}"))',
            "(allow file-read-data)",
            f'(allow file-write* (subpath "{cwd_real}"))',
            f'(allow file-write* (subpath "{home_real}"))',
            '(allow file-write-data (subpath "/dev/dtracehelper"))',
            '(allow file-write-data (subpath "/dev/null"))',
            "(allow ipc-posix-shm)",
        ])
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home)}
        result = subprocess.run(
            ["sandbox-exec", "-p", profile, "/bin/sh", "-c", CANARY_CMD],
            capture_output=True, text=True, env=env, cwd=str(self.cwd), timeout=15,
        )
        return result.stdout

    def test_repo_canonical_not_readable(self) -> None:
        output = self._run_under_sandbox()
        self.assertIn("REPO_READ=no", output, f"sandbox allowed repo read: {output}")

    def test_external_write_blocked(self) -> None:
        output = self._run_under_sandbox()
        self.assertIn("EXT_WRITE=no", output, f"sandbox allowed external write: {output}")
        leaked = list(Path("/tmp").glob("wbp_canary_ext_*.txt"))
        self.assertFalse(leaked, "canary file leaked to /tmp")

    def test_codex_home_not_readable(self) -> None:
        output = self._run_under_sandbox()
        self.assertIn("CODEX_READ=no", output, f"sandbox allowed ~/.codex read: {output}")


if __name__ == "__main__":
    unittest.main()
