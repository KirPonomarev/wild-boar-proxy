# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B10_CODE: Qwen one-shot CLI tests (fake-adapter evidence).

The fake qwen CLI is registered through the B09 test-only manifest hook.
All proofs here are controlled and declared-not-live; the real qwen binary
probe is B10_LIVE scope.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import one_shot_cli_runtime as osr
from wild_boar_proxy import qwen_one_shot_cli as qw

FAKE_QWEN_TEXT = """#!/bin/sh
# fake qwen one-shot CLI for B10_CODE tests
case "$1" in
  --version)
    echo "fake-qwen-cli 0.1.0"
    ;;
  --respond)
    echo "Qwen: $2"
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
    echo "QWEN_HOME=$QWEN_HOME"
    echo "QWEN_RUNTIME_DIR=$QWEN_RUNTIME_DIR"
    echo "HOME=$HOME"
    ;;
  *)
    echo "usage: fake-qwen-cli <cmd>" >&2
    exit 2
    ;;
esac
"""


class QwenOneShotCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.homes_root = self.root / "homes"
        script = self.root / "fake-qwen-cli.sh"
        script.write_text(FAKE_QWEN_TEXT, encoding="utf-8")
        script.chmod(0o755)
        manifest = self.root / "fake-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "tools": [
                        {
                            "tool_id": qw.QWEN_CLI_TOOL_ID,
                            "binary_name": str(script),
                            "display_name": "Fake Qwen CLI",
                            "version_args": ["--version"],
                            "output_profiles": ["text", "key_value", "json_lines"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self._old_env = {
            osr.FAKE_MANIFEST_ENV: os.environ.get(osr.FAKE_MANIFEST_ENV, ""),
            osr.HOMES_ROOT_ENV: os.environ.get(osr.HOMES_ROOT_ENV, ""),
        }
        os.environ[osr.FAKE_MANIFEST_ENV] = str(manifest)
        os.environ[osr.HOMES_ROOT_ENV] = str(self.homes_root)
        self.session = qw.qwen_one_shot_session()
        assert self.session["status"] == "ok", self.session

    def tearDown(self) -> None:
        for name, value in self._old_env.items():
            if value:
                os.environ[name] = value
            else:
                os.environ.pop(name, None)
        self.temp_dir.cleanup()

    def test_session_isolates_qwen_home_and_runtime_dir(self) -> None:
        self.assertEqual(self.session["status"], "ok")
        qwen_home = Path(self.session["qwen_home"])
        runtime_dir = Path(self.session["qwen_runtime_dir"])
        self.assertTrue(qwen_home.is_dir())
        self.assertTrue(runtime_dir.is_dir())
        self.assertTrue(str(qwen_home).startswith(str(self.homes_root)))
        self.assertTrue(str(runtime_dir).startswith(str(qwen_home)))
        self.assertEqual(oct(qwen_home.stat().st_mode & 0o777), "0o700")
        self.assertTrue(self.session["auth_present"])
        self.assertTrue(self.session["auth_presence_only"])
        self.assertFalse(self.session["resume_supported"])
        self.assertEqual(self.session["repo_write_policy"], "denied")

    def test_qwen_env_points_inside_provider_home(self) -> None:
        env = osr.build_sterile_environment(provider_home=self.session["qwen_home"])
        env[qw.QWEN_HOME_ENV] = str(self.session["qwen_home"])
        env[qw.QWEN_RUNTIME_DIR_ENV] = str(self.session["qwen_runtime_dir"])
        packet = osr.one_shot_cli_run(
            qw.QWEN_CLI_TOOL_ID,
            args=("--env-report",),
            provider_home=self.session["qwen_home"],
            env=env,
        )
        self.assertEqual(packet["status"], "ok")
        stdout = packet["run"]["stdout"]
        self.assertIn("QWEN_HOME=" + str(self.session["qwen_home"]), stdout)
        self.assertIn("QWEN_RUNTIME_DIR=" + str(self.session["qwen_runtime_dir"]), stdout)
        self.assertIn("HOME=" + str(self.session["qwen_home"]), stdout)

    def test_project_config_default_denied_and_admission(self) -> None:
        project = self.root / "project"
        project.mkdir()
        env_file = project / ".env"
        env_file.write_text("QWEN_KEY=redacted\n", encoding="utf-8")
        (project / ".qwen").mkdir()

        denied = qw.project_config_policy(self.session["qwen_home"], project)
        self.assertEqual(denied["status"], "error")
        decisions = {d["config_name"]: d for d in denied["decisions"]}
        self.assertEqual(decisions[".env"]["decision"], "denied")
        self.assertEqual(
            decisions[".env"]["machine_error_code"], qw.QWEN_CONFIG_ADMISSION_MISSING
        )
        self.assertEqual(decisions[".qwen"]["decision"], "denied")
        self.assertEqual(
            decisions[".qwen"]["machine_error_code"], qw.QWEN_CONFIG_DENIED
        )

        admitted = qw.admit_project_config(self.session["qwen_home"], env_file)
        self.assertEqual(admitted["status"], "ok")
        self.assertTrue(admitted["admitted"])
        self.assertEqual(len(admitted["digest_sha256"]), 64)

        ok_policy = qw.project_config_policy(self.session["qwen_home"], project)
        # The .qwen directory stays default-denied, so the aggregate is
        # still error while the admitted .env file decision is "admitted".
        self.assertEqual(ok_policy["status"], "error")
        env_decision = next(
            d for d in ok_policy["decisions"] if d["config_name"] == ".env"
        )
        self.assertEqual(env_decision["decision"], "admitted")

        env_file.write_text("QWEN_KEY=changed\n", encoding="utf-8")
        mismatch = qw.project_config_policy(self.session["qwen_home"], project)
        env_decision = next(
            d for d in mismatch["decisions"] if d["config_name"] == ".env"
        )
        self.assertEqual(env_decision["decision"], "denied")
        self.assertEqual(
            env_decision["machine_error_code"], qw.QWEN_CONFIG_DIGEST_MISMATCH
        )

        removed = qw.deny_project_config(self.session["qwen_home"], env_file)
        self.assertTrue(removed["removed"])
        after = qw.project_config_policy(self.session["qwen_home"], project)
        env_decision = next(
            d for d in after["decisions"] if d["config_name"] == ".env"
        )
        self.assertEqual(env_decision["decision"], "denied")

    def test_text_proof_via_fake_adapter(self) -> None:
        proof = qw.qwen_text_proof(
            "hello world", session=self.session, expected_prefix="Qwen: "
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["text_received"])
        self.assertTrue(proof["expected_prefix_match"])
        self.assertTrue(proof["declared_not_live_verified"])
        self.assertEqual(proof["proof_level"], "SYNTHETIC_PROVEN")
        self.assertFalse(proof["resume_supported"])

    def test_repo_read_proof_requires_admission(self) -> None:
        project = self.root / "project"
        project.mkdir()
        config = project / ".env"
        config.write_text("QWEN_KEY=admitted-content\n", encoding="utf-8")

        before = qw.qwen_repo_read_proof(
            session=self.session, project_root=project, config_path=config
        )
        self.assertEqual(before["status"], "error")
        self.assertEqual(
            before["machine_error_code"], qw.QWEN_CONFIG_ADMISSION_MISSING
        )

        qw.admit_project_config(self.session["qwen_home"], config)
        proof = qw.qwen_repo_read_proof(
            session=self.session, project_root=project, config_path=config
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["content_matches_admitted_file"])
        self.assertEqual(len(proof["admitted_digest_sha256"]), 64)

    def test_denied_write_proof_is_policy_level_and_honest(self) -> None:
        project = self.root / "project"
        project.mkdir()
        proof = qw.qwen_denied_write_proof(session=self.session, project_root=project)
        self.assertEqual(proof["status"], "ok")
        self.assertEqual(proof["machine_error_code"], qw.QWEN_WRITE_DENIED)
        self.assertEqual(proof["denied_by"], "permission_policy")
        self.assertEqual(proof["repo_write_policy"], "denied")
        self.assertIn(
            proof["os_enforcement"], {"os_sandbox_available", "declared_not_available"}
        )
        self.assertTrue(proof["declared_not_live_verified"])

    def test_timeout_proof(self) -> None:
        proof = qw.qwen_timeout_cancel_proof(
            session=self.session, timeout_seconds=0.6
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["timed_out"])
        self.assertFalse(proof["cancelled"])
        self.assertEqual(proof["machine_error_code"], osr.ONE_SHOT_RUN_TIMEOUT)

    def test_cancel_proof(self) -> None:
        proof = qw.qwen_timeout_cancel_proof(
            session=self.session, cancel_after_seconds=0.6
        )
        self.assertEqual(proof["status"], "ok")
        self.assertTrue(proof["cancelled"])
        self.assertFalse(proof["timed_out"])
        self.assertEqual(proof["machine_error_code"], osr.ONE_SHOT_CANCELLED)

    def test_run_fails_closed_without_session(self) -> None:
        packet = qw.qwen_one_shot_run("hi", session={})
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], qw.QWEN_SESSION_INVALID)

    def test_run_parses_output(self) -> None:
        packet = qw.qwen_one_shot_run("hello", session=self.session)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["parsed_output"]["detected_format"], "text")
        self.assertIn("Qwen: hello", packet["run"]["stdout"])
        self.assertFalse(packet["resume_supported"])

    def test_receipt_declared_not_live(self) -> None:
        receipt = qw.build_qwen_one_shot_receipt()
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["machine_error_code"], "SYNTHETIC_PROVEN")
        self.assertTrue(receipt["declared_not_live_verified"])
        self.assertEqual(receipt["repo_write_policy"], "denied")
        self.assertFalse(receipt["resume_supported"])


if __name__ == "__main__":
    unittest.main()
