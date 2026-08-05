# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B11_CODE: Kimi one-shot CLI tests (fake-adapter evidence).

R5: no module-level state mutations. Each test class builds its own
isolated engine instance from tests/fakes.py; the production facade is
never granted anything and stays fail-closed. All proofs are controlled
and declared-not-live; the real Kimi CLI binary probe is B11_LIVE scope.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import kimi_one_shot_cli as km
from wild_boar_proxy import one_shot_cli_runtime as osr

import fakes

FAKE_KIMI_TEXT = """#!/bin/sh
# fake kimi one-shot CLI for B11_CODE tests
case "$1" in
  --version)
    echo "fake-kimi-cli 0.1.0"
    ;;
  --respond)
    echo "Kimi: $2"
    ;;
  --read-file)
    if [ -f "$2" ]; then
      cat "$2"
    else
      echo "NOT_FOUND:$2" >&2
      exit 3
    fi
    ;;
  --sleep)
    sleep "${2:-5}"
    ;;
  --env-report)
    echo "KIMI_CODE_HOME=$KIMI_CODE_HOME"
    echo "HOME=$HOME"
    ;;
  *)
    echo "usage: fake-kimi-cli <cmd>" >&2
    exit 2
    ;;
esac
"""


class KimiOneShotCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.homes_root = self.root / "homes"
        script = fakes.write_fake_cli(self.root, "fake-kimi-cli.sh", FAKE_KIMI_TEXT)
        manifest = fakes.write_manifest(
            self.root,
            [
                {
                    "tool_id": km.KIMI_CLI_TOOL_ID,
                    "binary_name": str(script),
                    "display_name": "Fake Kimi CLI",
                    "version_args": ["--version"],
                    "output_profiles": ["text", "key_value", "json_lines"],
                }
            ],
        )
        self.runtime = fakes.make_test_runtime(
            self.homes_root, fakes.load_manifest_entries(manifest)
        )
        self.session = km.kimi_one_shot_session(runtime=self.runtime)
        assert self.session["status"] == "ok", self.session

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _project(self, files: dict[str, str]) -> Path:
        project = self.root / "project"
        project.mkdir(exist_ok=True)
        for rel, content in files.items():
            target = project / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return project

    def test_session_isolates_kimi_code_home(self) -> None:
        self.assertEqual(self.session["status"], "ok")
        home = Path(self.session["kimi_code_home"])
        self.assertTrue(home.is_dir())
        self.assertTrue(str(home).startswith(str(self.homes_root)))
        self.assertEqual(oct(home.stat().st_mode & 0o777), "0o700")
        self.assertTrue(self.session["auth_present"])
        self.assertTrue(self.session["auth_presence_only"])
        self.assertEqual(self.session["repo_read_policy"], km.KIMI_READ_MODE_NONE)
        self.assertEqual(self.session["repo_write_policy"], "denied")
        self.assertFalse(self.session["resume_supported"])

    def test_kimi_env_points_inside_provider_home(self) -> None:
        """F08 regression: KIMI_CODE_HOME must actually reach the child
        process, not just be built in a local variable."""
        home = Path(self.session["kimi_code_home"])
        run = self.runtime.one_shot_cli_run(
            km.KIMI_CLI_TOOL_ID,
            args=("--env-report",),
            provider_home=home,
            provider_env=km._kimi_provider_env(self.session),
        )
        self.assertEqual(run["status"], "ok")
        stdout = run["run"]["stdout"]
        self.assertIn("KIMI_CODE_HOME=" + str(home.resolve()), stdout)
        self.assertIn("HOME=" + str(home.resolve()), stdout)

    def test_snapshot_is_immutable_and_bounded(self) -> None:
        project = self._project(
            {"notes.txt": "alpha\n", "docs/readme.md": "beta\n", "secret.env": "k=v\n"}
        )
        (project / ".git").mkdir()
        (project / ".git" / "config").write_text("ignored", encoding="utf-8")
        packet = km.create_kimi_snapshot(project, snapshot_root=self.root / "snap")
        self.assertEqual(packet["status"], "ok")
        snap = packet["snapshot"]
        snap_root = Path(snap["root"])
        self.assertEqual(snap["file_count"], 3)
        self.assertFalse((snap_root / ".git").exists())
        for rel in ("notes.txt", "docs/readme.md", "secret.env"):
            self.assertEqual(oct((snap_root / rel).stat().st_mode & 0o777), "0o444")
        self.assertEqual(oct(snap_root.stat().st_mode & 0o777), "0o555")
        self.assertEqual(len(snap["digest_sha256"]), 64)

    def test_snapshot_fails_closed_on_oversize(self) -> None:
        project = self._project({"big.txt": "x" * 4096})
        packet = km.create_kimi_snapshot(
            project,
            snapshot_root=self.root / "snap2",
            max_total_bytes=1024,
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], km.KIMI_SNAPSHOT_FAILED)

    def test_snapshot_without_root_uses_runtime_homes(self) -> None:
        project = self._project({"notes.txt": "alpha\n"})
        packet = km.create_kimi_snapshot(project, runtime=self.runtime)
        self.assertEqual(packet["status"], "ok")
        snap_root = Path(packet["snapshot"]["root"])
        self.assertTrue(str(snap_root).startswith(str(self.homes_root)))

    def test_snapshot_without_root_or_runtime_is_fail_closed(self) -> None:
        project = self._project({"notes.txt": "alpha\n"})
        before = set(self.root.rglob("*"))
        packet = km.create_kimi_snapshot(project)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION
        )
        after = set(self.root.rglob("*"))
        self.assertEqual(before, after)

    def test_repo_read_policy_requires_snapshot(self) -> None:
        denied = km.kimi_repo_read_policy(session=self.session)
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["machine_error_code"], km.KIMI_READ_DENIED)
        self.assertEqual(denied["repo_read_policy"], km.KIMI_READ_MODE_NONE)

        project = self._project({"notes.txt": "alpha\n"})
        snap = km.create_kimi_snapshot(project, snapshot_root=self.root / "snap3")
        admitted = km.kimi_repo_read_policy(session=self.session, snapshot=snap)
        self.assertEqual(admitted["status"], "ok")
        self.assertEqual(admitted["repo_read_policy"], km.KIMI_READ_MODE_SNAPSHOT)

    def test_repo_read_proof_denies_outside_snapshot(self) -> None:
        project = self._project({"notes.txt": "alpha\n"})
        snap = km.create_kimi_snapshot(project, snapshot_root=self.root / "snap4")
        outside = self.root / "outside.txt"
        outside.write_text("x", encoding="utf-8")
        denied = km.kimi_repo_read_proof(
            session=self.session,
            snapshot=snap,
            snapshot_path=outside,
            runtime=self.runtime,
        )
        self.assertEqual(denied["status"], "error")
        self.assertEqual(denied["machine_error_code"], km.KIMI_READ_DENIED)

    def test_repo_read_proof_via_snapshot(self) -> None:
        project = self._project({"notes.txt": "alpha\n"})
        snap = km.create_kimi_snapshot(project, snapshot_root=self.root / "snap5")
        snap_file = Path(snap["snapshot"]["root"]) / "notes.txt"
        proof = km.kimi_repo_read_proof(
            session=self.session,
            snapshot=snap,
            snapshot_path=snap_file,
            runtime=self.runtime,
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["content_matches_snapshot_file"])
        self.assertEqual(proof["repo_read_policy"], km.KIMI_READ_MODE_SNAPSHOT)
        self.assertEqual(proof["snapshot_digest_sha256"], snap["snapshot"]["digest_sha256"])

    def test_denied_write_proof_observes_real_eacces(self) -> None:
        project = self._project({"notes.txt": "alpha\n"})
        snap = km.create_kimi_snapshot(project, snapshot_root=self.root / "snap6")
        proof = km.kimi_denied_write_proof(snapshot=snap)
        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["observed_errno"], 13)  # EACCES
        self.assertEqual(proof["evidence"], "os_eacces_observed")
        self.assertEqual(proof["repo_write_policy"], "denied")

    def test_text_proof_via_fake_adapter(self) -> None:
        proof = km.kimi_text_proof(
            "hello",
            session=self.session,
            expected_prefix="Kimi: ",
            runtime=self.runtime,
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["text_received"])
        self.assertTrue(proof["expected_prefix_match"])
        self.assertTrue(proof["declared_not_live_verified"])
        self.assertEqual(proof["proof_level"], "SYNTHETIC_PROVEN")

    def test_run_parses_output(self) -> None:
        packet = km.kimi_one_shot_run("hello", session=self.session, runtime=self.runtime)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["parsed_output"]["detected_format"], "text")
        self.assertIn("Kimi: hello", packet["run"]["stdout"])
        self.assertFalse(packet["resume_supported"])

    def test_timeout_proof(self) -> None:
        proof = km.kimi_timeout_cancel_proof(
            session=self.session, timeout_seconds=0.6, runtime=self.runtime
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["timed_out"])
        self.assertEqual(proof["machine_error_code"], osr.ONE_SHOT_RUN_TIMEOUT)

    def test_cancel_proof(self) -> None:
        proof = km.kimi_timeout_cancel_proof(
            session=self.session, cancel_after_seconds=0.6, runtime=self.runtime
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["cancelled"])
        self.assertEqual(proof["machine_error_code"], osr.ONE_SHOT_CANCELLED)

    def test_run_fails_closed_without_session(self) -> None:
        packet = km.kimi_one_shot_run("hi", session={}, runtime=self.runtime)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], km.KIMI_SESSION_INVALID)

    def test_receipt_declared_not_live(self) -> None:
        receipt = km.build_kimi_one_shot_receipt()
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["machine_error_code"], "SYNTHETIC_PROVEN")
        self.assertTrue(receipt["declared_not_live_verified"])
        self.assertEqual(receipt["repo_read_policy"], km.KIMI_READ_MODE_NONE)
        self.assertEqual(
            receipt["repo_read_requires"], "os_read_only_sandbox_or_immutable_snapshot"
        )
        self.assertFalse(receipt["resume_supported"])


class KimiProductionFacadeTests(unittest.TestCase):
    """Without an explicit test engine the production facade answers
    fail-closed before any filesystem or process side effect."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_session_disabled_on_production_facade(self) -> None:
        facade = osr.ProductionOneShotFacade(homes_root=self.root / "homes")
        packet = facade.session("kimi")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION
        )
        self.assertEqual(packet["changed_files"], [])
        self.assertFalse((self.root / "homes").exists())

    def test_default_session_function_uses_fail_closed_facade(self) -> None:
        packet = km.kimi_one_shot_session()
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION
        )
        self.assertEqual(packet["changed_files"], [])

    def test_default_run_function_uses_fail_closed_facade(self) -> None:
        packet = km.kimi_one_shot_run("hi", session={"kimi_code_home": "/nonexistent"})
        self.assertEqual(packet["status"], "error")
        self.assertEqual(
            packet["machine_error_code"], osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION
        )


if __name__ == "__main__":
    unittest.main()
