# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R52: adversarial sandbox test suite.

Every probe runs a hostile fake CLI through the REAL engine
(`OneShotRuntime.one_shot_cli_run`), so the child executes under the same
deny-default seatbelt profile production would use. The attacker is given
the strongest position we can offer: realpath-resolved target paths, a
writable home, and knowledge of the layout. Each probe must still fail.

Positive controls prove the sandbox is not simply broken: the child CAN
start, write its own home, and read an explicitly admitted read-only root.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import fakes

from wild_boar_proxy import one_shot_cli_runtime as osr

ADV_CLI_TEXT = """#!/bin/sh
# adversarial one-shot CLI for R52 tests
case "$1" in
  --version)
    echo "adv-cli 1.0.0"
    ;;
  --write)
    if echo x > "$2" 2>/dev/null; then echo "WRITE_OK $2"; else echo "WRITE_DENIED $2"; fi
    ;;
  --read)
    if cat "$2" >/dev/null 2>&1; then echo "READ_OK $2"; else echo "READ_DENIED $2"; fi
    ;;
  --trav-write)
    if echo x > "$HOME/../trav.txt" 2>/dev/null; then echo "TRAV_OK"; else echo "TRAV_DENIED"; fi
    ;;
  --symlink-read)
    ln -s "$2" "$HOME/outlink" 2>/dev/null
    if cat "$HOME/outlink/secret.txt" >/dev/null 2>&1; then
      echo "SYMLINK_READ_OK"
    else
      echo "SYMLINK_READ_DENIED"
    fi
    ;;
  --exec-escape)
    # Two-stage attack: drop a payload into the writable home, execute it,
    # and from INSIDE that second-stage process attempt an escape write to
    # the outside path given as $2. Containment holds only if the payload
    # inherits the same deny-default sandbox.
    printf '#!/bin/sh\\nif echo x > "$1" 2>/dev/null; then echo "STAGE2_ESCAPE_OK"; else echo "STAGE2_ESCAPE_DENIED"; fi\\n' > "$HOME/x.sh" 2>/dev/null
    chmod +x "$HOME/x.sh" 2>/dev/null
    "$HOME/x.sh" "$2" 2>&1 || echo "STAGE2_EXEC_DENIED"
    ;;
  --net-ping)
    out=$(/sbin/ping -c 1 -t 1 127.0.0.1 2>&1)
    case "$out" in
      *"Operation not permitted"*) echo "NET_DENIED" ;;
      *) echo "NET_OTHER: $out" ;;
    esac
    ;;
  --home-write)
    if echo ok > "$HOME/w.txt" 2>/dev/null; then echo "HOME_WRITE_OK"; else echo "HOME_WRITE_DENIED"; fi
    ;;
  *)
    echo "usage: adv-cli <cmd>" >&2
    exit 2
    ;;
esac
exit 0
"""


class AdversarialSandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not shutil.which("sandbox-exec"):
            raise unittest.SkipTest("sandbox-exec not available")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        script = fakes.write_fake_cli(self.root, "adv-cli.sh", ADV_CLI_TEXT)
        manifest = fakes.write_manifest(
            self.root, [{"tool_id": "adv-cli", "binary_name": str(script)}]
        )
        self.runtime = fakes.make_test_runtime(
            self.root / "homes", fakes.load_manifest_entries(manifest)
        )
        home_packet = self.runtime.create_provider_home("adv")
        assert home_packet["status"] == "ok", home_packet
        self.home = Path(home_packet["home_path"])
        # Attacker-visible secrets OUTSIDE every allowed root.
        self.outside = self.root / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_text("top-secret\n", encoding="utf-8")

    def _run(self, *args: str, provider_env: dict[str, str] | None = None) -> str:
        packet = self.runtime.one_shot_cli_run(
            "adv-cli",
            args=args,
            provider_home=self.home,
            provider_env=provider_env,
            timeout_seconds=15.0,
        )
        self.assertEqual(packet["status"], "ok", packet)
        return packet["run"]["stdout"]

    @staticmethod
    def _r(path: Path) -> str:
        """Strongest attacker position: the kernel-resolved path."""
        return os.path.realpath(path)

    # --- positive controls: the sandbox is alive, not just broken ---

    def test_control_child_starts_and_reports_version(self) -> None:
        self.assertIn("adv-cli 1.0.0", self._run("--version"))

    def test_control_home_write_allowed(self) -> None:
        self.assertIn("HOME_WRITE_OK", self._run("--home-write"))

    def test_control_admitted_read_only_root_is_readable(self) -> None:
        project = self.root / "project"
        project.mkdir()
        (project / "doc.txt").write_text("read-me\n", encoding="utf-8")
        env = {"QWEN_PROJECT_ROOT": self._r(project)}
        self.assertIn("READ_OK", self._run("--read", self._r(project / "doc.txt"), provider_env=env))

    # --- adversarial matrix ---

    def test_write_outside_allowed_roots_denied(self) -> None:
        target = self.outside / "escape.txt"
        out = self._run("--write", self._r(target))
        self.assertIn("WRITE_DENIED", out)
        self.assertFalse(target.exists())

    def test_write_repo_path_denied(self) -> None:
        repo_target = Path("/Volumes/Work/wild-boar-proxy/.tmp-r52-canary.txt")
        out = self._run("--write", repo_target.as_posix())
        self.assertIn("WRITE_DENIED", out)
        self.assertFalse(repo_target.exists())

    def test_read_outside_allowed_roots_denied(self) -> None:
        out = self._run("--read", self._r(self.outside / "secret.txt"))
        self.assertIn("READ_DENIED", out)

    def test_read_repo_canon_denied(self) -> None:
        out = self._run("--read", "/Volumes/Work/wild-boar-proxy/CANON.md")
        self.assertIn("READ_DENIED", out)

    def test_parent_traversal_write_denied(self) -> None:
        out = self._run("--trav-write")
        self.assertIn("TRAV_DENIED", out)
        self.assertFalse((self.home.parent / "trav.txt").exists())

    def test_symlink_escape_read_denied(self) -> None:
        out = self._run("--symlink-read", self._r(self.outside))
        self.assertIn("SYMLINK_READ_DENIED", out)

    def test_two_stage_dropper_cannot_escape(self) -> None:
        """Stage-1 dropper executes a stage-2 payload from the writable
        home; the payload inherits the same deny-default sandbox, so its
        escape write must still be denied."""
        target = self.outside / "stage2.txt"
        out = self._run("--exec-escape", self._r(target))
        self.assertNotIn("STAGE2_ESCAPE_OK", out)
        self.assertFalse(target.exists())

    def test_network_denied_by_construction(self) -> None:
        self.assertIn("NET_DENIED", self._run("--net-ping"))

    def test_admitted_read_only_root_stays_read_only(self) -> None:
        project = self.root / "project"
        project.mkdir()
        env = {"QWEN_PROJECT_ROOT": self._r(project)}
        target = project / "forged.txt"
        out = self._run("--write", self._r(target), provider_env=env)
        self.assertIn("WRITE_DENIED", out)
        self.assertFalse(target.exists())

    def test_sandbox_cwd_removed_after_run(self) -> None:
        before = set(Path(tempfile.gettempdir()).glob("wbp-sandbox-ro-*"))
        self._run("--version")
        after = set(Path(tempfile.gettempdir()).glob("wbp-sandbox-ro-*"))
        self.assertEqual(before, after)

    def test_profile_has_no_network_allow_rules(self) -> None:
        profile = osr.build_server_owned_sandbox_profile(
            home_dir=self.home, sandbox_cwd=self.root / "cwd", binary_path="/bin/sh"
        )
        self.assertIn("(deny default)", profile)
        self.assertNotIn("network", profile)


class FailClosedWithoutSandboxExecTests(unittest.TestCase):
    """No sandbox-exec -> no unsandboxed lane, ever."""

    def test_run_fails_closed_when_sandbox_exec_absent(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        script = fakes.write_fake_cli(root, "adv-cli.sh", ADV_CLI_TEXT)
        manifest = fakes.write_manifest(
            root, [{"tool_id": "adv-cli", "binary_name": str(script)}]
        )
        runtime = fakes.make_test_runtime(
            root / "homes", fakes.load_manifest_entries(manifest)
        )
        original_which = shutil.which
        try:
            osr.shutil.which = lambda name, *a, **k: None  # type: ignore[assignment]
            packet = runtime.one_shot_cli_run("adv-cli", args=("--version",))
        finally:
            osr.shutil.which = original_which  # type: ignore[assignment]
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], osr.CLI_UNAVAILABLE_UNSAFE)
        self.assertEqual(packet.get("reason"), "sandbox_exec_absent")
        # No process ran: there is no run payload at all.
        self.assertNotIn("run", packet)


if __name__ == "__main__":
    unittest.main()
