# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B09: generic one-shot CLI runtime tests (fake-adapter evidence).

R5: no module-level state mutations and no environment hooks. Each test
builds an explicit `OneShotRuntime` instance from tests/fakes.py and
passes it by parameter. The fake adapter is a shell CLI registered in a
test-owned manifest. Tests exercise sterile probes, scrubbed
environments, provider homes, bounded process groups, cancellation,
parsers, auth sessions, and the no-resume rule — all under the
deny-default seatbelt sandbox.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import one_shot_cli_runtime as osr

import fakes

FAKE_CLI_TEXT = """#!/bin/sh
# fake one-shot CLI for B09 tests (pure sh, no interpreter lookup)
case "$1" in
  --version)
    echo "fake-cli 1.0.0"
    ;;
  --sleep)
    sleep "${2:-5}" &
    CHILD=$!
    wait "$CHILD"
    echo "slept"
    ;;
  --env-report)
    echo "PATH=$PATH"
    echo "HOME=$HOME"
    echo "LEAK_TEST_SECRET=${LEAK_TEST_SECRET:-<absent>}"
    echo "LEAK_TEST_TOKEN=${LEAK_TEST_TOKEN:-<absent>}"
    echo "LEAK_TEST_PASSWORD=${LEAK_TEST_PASSWORD:-<absent>}"
    echo "KEPT_VAR=${KEPT_VAR:-<absent>}"
    ;;
  --stdin-echo)
    while IFS= read -r line; do
      echo "echo:$line"
    done
    ;;
  --json-lines)
    i=0
    while [ "$i" -lt "${2:-3}" ]; do
      echo "{\\"n\\":$i,\\"ok\\":true}"
      i=$((i+1))
    done
    ;;
  --cwd)
    pwd
    ;;
  --noise)
    i=0
    while [ "$i" -lt 200 ]; do
      echo "line-$i"
      i=$((i+1))
    done
    ;;
  *)
    echo "usage: fake-cli <cmd>" >&2
    exit 2
    ;;
esac
"""


class FakeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.script = fakes.write_fake_cli(self.root, "fake-cli.sh", FAKE_CLI_TEXT)
        self.manifest = fakes.write_manifest(
            self.root,
            [
                {
                    "tool_id": "fake-cli",
                    "binary_name": str(self.script),
                    "display_name": "Fake CLI",
                    "version_args": ["--version"],
                    "output_profiles": ["text", "key_value", "json_lines"],
                }
            ],
        )
        self.homes_root = self.root / "homes"
        self.runtime = fakes.make_test_runtime(
            self.homes_root, fakes.load_manifest_entries(self.manifest)
        )
        self._old_env: dict[str, str | None] = {}
        for name in (
            "LEAK_TEST_SECRET",
            "LEAK_TEST_TOKEN",
            "LEAK_TEST_PASSWORD",
            "KEPT_VAR",
        ):
            self._old_env[name] = os.environ.get(name)
        os.environ["LEAK_TEST_SECRET"] = "must-not-leak-1"
        os.environ["LEAK_TEST_TOKEN"] = "must-not-leak-2"
        os.environ["LEAK_TEST_PASSWORD"] = "must-not-leak-3"
        os.environ["KEPT_VAR"] = "kept-value"

    def tearDown(self) -> None:
        for name, value in self._old_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_unknown_tool_fails_closed(self) -> None:
        packet = self.runtime.one_shot_cli_run("no-such-tool")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], osr.ONE_SHOT_TOOL_UNKNOWN)
        self.assertIsNone(self.runtime.resolve_manifest_entry("no-such-tool"))

    def test_manifest_is_test_owned_not_server_owned(self) -> None:
        entry = self.runtime.resolve_manifest_entry("fake-cli")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertFalse(entry.server_owned)  # fake hook, not server-owned
        self.assertEqual(entry.tool_id, "fake-cli")
        self.assertEqual(entry.version_args, ("--version",))
        # The production server-owned manifest stays honestly empty.
        self.assertEqual(osr.SERVER_OWNED_TOOL_MANIFEST, ())

    def test_sterile_probe_returns_realpath_version_digest(self) -> None:
        packet = self.runtime.run_sterile_probe("fake-cli")
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["tool_id"], "fake-cli")
        self.assertEqual(packet["version_text"], "fake-cli 1.0.0")
        self.assertEqual(packet["realpath"], str(self.script.resolve()))
        expected_digest = hashlib.sha256(self.script.read_bytes()).hexdigest()
        self.assertEqual(packet["binary_sha256"], expected_digest)
        self.assertIn("env_digest", packet)
        self.assertFalse(packet["resume_supported"])
        self.assertEqual(packet["resume_reason"], osr.ONE_SHOT_NO_RESUME_REASON)

    def test_sterile_probe_fails_when_binary_missing(self) -> None:
        ghost_dir = self.root / "ghost"
        ghost_dir.mkdir()
        ghost_manifest = fakes.write_manifest(
            ghost_dir,
            [{"tool_id": "ghost", "binary_name": "/nonexistent/ghost"}],
        )
        ghost_runtime = fakes.make_test_runtime(
            self.homes_root, fakes.load_manifest_entries(ghost_manifest)
        )
        packet = ghost_runtime.run_sterile_probe("ghost")
        self.assertEqual(packet["status"], "error")
        # ghost is in the manifest but binary doesn't exist -> TOOL_BINARY_NOT_FOUND
        self.assertEqual(packet["machine_error_code"], osr.TOOL_BINARY_NOT_FOUND)

    def test_sterile_environment_has_no_ambient_home(self) -> None:
        """R5: the ambient user HOME must never cross into a child env."""
        env = osr.build_sterile_environment()
        self.assertNotIn("HOME", env)
        self.assertNotEqual(env.get("HOME"), os.environ.get("HOME"))
        env = osr.build_sterile_environment(provider_home=self.homes_root / "probe-home")
        self.assertEqual(env["HOME"], str((self.homes_root / "probe-home").resolve()))

    def test_scrubbed_environment_never_leaks_secrets(self) -> None:
        env = osr.build_sterile_environment(provider_home=self.homes_root / "probe-home")
        for key in ("LEAK_TEST_SECRET", "LEAK_TEST_TOKEN", "LEAK_TEST_PASSWORD"):
            self.assertNotIn(key, env)
        self.assertTrue(env["PATH"].startswith("/usr/bin"))
        self.assertNotIn("/opt/homebrew", env["PATH"])
        self.assertEqual(env["HOME"], str((self.homes_root / "probe-home").resolve()))

        handle = self.runtime.one_shot_cli_handle(
            "fake-cli",
            args=("--env-report",),
            provider_home=self.homes_root / "run-home",
        )
        self.assertIsInstance(handle, osr.OneShotCliRunHandle)
        assert isinstance(handle, osr.OneShotCliRunHandle)
        result = handle.wait(timeout_seconds=10)
        self.assertEqual(result.status, "ok")
        stdout = result.stdout
        self.assertNotIn("must-not-leak-1", stdout)
        self.assertNotIn("must-not-leak-2", stdout)
        self.assertNotIn("must-not-leak-3", stdout)
        self.assertIn("LEAK_TEST_SECRET=<absent>", stdout)
        # KEPT_VAR is ambient but not allowlisted for the child: the
        # runtime accepts no caller env, so it cannot cross either.
        self.assertIn("KEPT_VAR=<absent>", stdout)
        self.assertIn(
            "HOME=" + str((self.homes_root / "run-home").resolve()), stdout
        )

    def test_handle_accepts_no_caller_env_or_sandbox(self) -> None:
        """F04 regression: there is no caller env/sandbox bypass anymore."""
        with self.assertRaises(TypeError):
            self.runtime.one_shot_cli_handle("fake-cli", env={})  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            self.runtime.one_shot_cli_handle(  # type: ignore[call-arg]
                "fake-cli", sandbox=osr.SandboxProfile()
            )
        with self.assertRaises(TypeError):
            self.runtime.one_shot_cli_run("fake-cli", env={})  # type: ignore[call-arg]

    def test_run_without_provider_home_gets_sandbox_cwd_home(self) -> None:
        """A run without a provider home must NOT see the real user HOME."""
        packet = self.runtime.one_shot_cli_run("fake-cli", args=("--env-report",))
        self.assertEqual(packet["status"], "ok")
        stdout = packet["run"]["stdout"]
        real_home = str(Path(os.environ.get("HOME", "/nonexistent")).resolve())
        self.assertNotIn("HOME=" + real_home, stdout)
        for line in stdout.splitlines():
            if line.startswith("HOME="):
                child_home = line[len("HOME="):]
                self.assertIn("wbp-sandbox-ro-", child_home)
                break
        else:
            self.fail("child did not report HOME")

    def test_provider_env_keys_are_allowlisted(self) -> None:
        with self.assertRaises(osr.RuntimeErrorInfo) as ctx:
            self.runtime.one_shot_cli_run(
                "fake-cli",
                provider_home=self.homes_root / "x",
                provider_env={"LEAK_TEST_SECRET": "/tmp/x"},
            )
        self.assertEqual(ctx.exception.machine_error_code, osr.ONE_SHOT_ENV_VIOLATION)
        with self.assertRaises(osr.RuntimeErrorInfo) as ctx:
            self.runtime.one_shot_cli_run(
                "fake-cli",
                provider_home=self.homes_root / "x",
                provider_env={"QWEN_HOME": "relative/path"},
            )
        self.assertEqual(ctx.exception.machine_error_code, osr.ONE_SHOT_ENV_VIOLATION)

    def test_provider_home_must_stay_inside_homes_root(self) -> None:
        with self.assertRaises(osr.RuntimeErrorInfo) as ctx:
            self.runtime.one_shot_cli_run(
                "fake-cli", provider_home=self.root / "outside"
            )
        self.assertEqual(ctx.exception.machine_error_code, osr.ONE_SHOT_PATH_VIOLATION)

    def test_provider_home_is_isolated_and_0700(self) -> None:
        packet = self.runtime.create_provider_home("qwen-test")
        self.assertEqual(packet["status"], "ok")
        home = Path(packet["home_path"])
        runtime_dir = Path(packet["runtime_dir"])
        self.assertTrue(home.is_dir())
        self.assertTrue(runtime_dir.is_dir())
        self.assertEqual(oct(home.stat().st_mode & 0o777), "0o700")
        self.assertEqual(oct(runtime_dir.stat().st_mode & 0o777), "0o700")
        self.assertTrue(str(home).startswith(str(self.homes_root)))

    def test_provider_home_rejects_invalid_id(self) -> None:
        packet = self.runtime.create_provider_home("../escape")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], osr.ONE_SHOT_SCHEMA_INVALID)

    def test_bounded_run_captures_stdin_and_stdout(self) -> None:
        packet = self.runtime.one_shot_cli_run(
            "fake-cli",
            args=("--stdin-echo",),
            stdin_text="hello\nworld\n",
        )
        self.assertEqual(packet["status"], "ok")
        run = packet["run"]
        self.assertEqual(run["stdout"], "echo:hello\necho:world\n")
        self.assertFalse(run["stdout_truncated"])
        self.assertFalse(run["timed_out"])
        self.assertFalse(run["cancelled"])
        self.assertEqual(run["exit_code"], 0)

    def test_cancellation_kills_whole_process_group(self) -> None:
        packet = self.runtime.one_shot_cli_run(
            "fake-cli",
            args=("--sleep", "30"),
            cancel_after_seconds=0.6,
        )
        self.assertEqual(packet["status"], "error")
        run = packet["run"]
        self.assertEqual(run["machine_error_code"], osr.ONE_SHOT_CANCELLED)
        self.assertTrue(run["cancelled"])
        pid = run["pid"]
        with self.assertRaises(ProcessLookupError):
            os.killpg(pid, 0)  # whole group gone, not just the leader

    def test_handle_cancel_terminates_group(self) -> None:
        handle = self.runtime.one_shot_cli_handle("fake-cli", args=("--sleep", "30"))
        self.assertIsInstance(handle, osr.OneShotCliRunHandle)
        assert isinstance(handle, osr.OneShotCliRunHandle)
        cancel = handle.cancel(grace_seconds=2.0)
        self.assertTrue(cancel["cancelled"])
        result = handle.wait()
        self.assertEqual(result.machine_error_code, osr.ONE_SHOT_CANCELLED)
        self.assertTrue(result.cancelled)
        with self.assertRaises(ProcessLookupError):
            os.killpg(handle.pid, 0)

    def test_timeout_is_bounded(self) -> None:
        packet = self.runtime.one_shot_cli_run(
            "fake-cli",
            args=("--sleep", "30"),
            timeout_seconds=0.6,
        )
        self.assertEqual(packet["status"], "error")
        run = packet["run"]
        self.assertEqual(run["machine_error_code"], osr.ONE_SHOT_RUN_TIMEOUT)
        self.assertTrue(run["timed_out"])
        self.assertFalse(run["cancelled"])

    def test_output_cap_truncates_honestly(self) -> None:
        packet = self.runtime.one_shot_cli_run(
            "fake-cli",
            args=("--noise",),
            output_cap_bytes=512,
        )
        self.assertEqual(packet["status"], "ok")
        run = packet["run"]
        self.assertTrue(run["stdout_truncated"])
        self.assertLessEqual(len(run["stdout"]), 512)

    def test_one_shot_never_resumes(self) -> None:
        packet = self.runtime.one_shot_cli_run("fake-cli", args=("--version",))
        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["resume_supported"])
        self.assertFalse(packet["run"]["resume_supported"])
        self.assertEqual(packet["resume_reason"], osr.ONE_SHOT_NO_RESUME_REASON)
        receipt = osr.default_production_facade().receipt()
        self.assertFalse(receipt["resume_supported"])

    def test_parsers_normalize_without_fabrication(self) -> None:
        text = "\x1b[32mname=alice\x1b[0m\nname=bob\nother line\n"
        kv = osr.parse_cli_output(text, profile="key_value")
        self.assertEqual(kv["detected_format"], "key_value")
        self.assertEqual(kv["pairs"], {"name": "bob"})
        self.assertEqual(kv["unmatched_lines"], 1)

        jl = osr.parse_cli_output('{"a": 1}\n{"b": 2}\nnot-json\n', profile="json_lines")
        self.assertEqual(jl["detected_format"], "json_lines")
        self.assertEqual(jl["records"], [{"a": 1}, {"b": 2}])
        self.assertEqual(jl["malformed_lines"], 1)

        auto = osr.parse_cli_output('{"x": 1}\n', profile="auto")
        self.assertEqual(auto["detected_format"], "json_lines")

        plain = osr.parse_cli_output("hello\nworld\n", profile="text")
        self.assertEqual(plain["detected_format"], "text")
        self.assertEqual(plain["text"], "hello\nworld")

        self.assertFalse(kv["resume_supported"])

    def test_auth_session_is_presence_only(self) -> None:
        home = self.homes_root / "auth-home"
        started = self.runtime.one_shot_auth_session("qwen-test", home)
        self.assertEqual(started["status"], "ok")
        self.assertTrue(started["presence_only"])
        self.assertFalse(started["secret_values_exposed"])
        session_file = Path(started["auth_dir"]) / "session.json"
        self.assertEqual(oct(session_file.stat().st_mode & 0o777), "0o600")
        # Packet must not contain session secret material (there is none).
        body = json.dumps(started)
        self.assertNotIn("must-not-leak", body)

        status = self.runtime.one_shot_auth_status(home)
        self.assertTrue(status["auth_present"])
        self.assertFalse(status["secret_values_exposed"])

        ended = self.runtime.end_one_shot_auth_session(home)
        self.assertTrue(ended["removed"])
        status2 = self.runtime.one_shot_auth_status(home)
        self.assertFalse(status2["auth_present"])

    def test_sandbox_profile_is_honest(self) -> None:
        profile = osr.SandboxProfile()
        self.assertEqual(profile.repo_write, "denied")
        self.assertEqual(profile.repo_read, "none")
        probe = osr.probe_os_sandbox()
        self.assertIn("os_sandbox_available", probe)
        self.assertIn(
            probe["os_enforcement"], {"os_sandbox_available", "declared_not_available"}
        )
        # The runtime default probes the OS honestly instead of lying, and
        # every run packet carries that probed profile.
        default = osr.default_sandbox_profile()
        self.assertEqual(default.os_enforcement, probe["os_enforcement"])
        packet = self.runtime.one_shot_cli_run("fake-cli", args=("--version",))
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["sandbox"]["repo_write"], "denied")
        self.assertEqual(packet["sandbox"]["os_enforcement"], probe["os_enforcement"])

    def test_runtime_receipt_declared_not_live(self) -> None:
        receipt = osr.default_production_facade().receipt()
        self.assertEqual(receipt["status"], "ok")
        self.assertTrue(receipt["cli_disabled"])
        self.assertEqual(receipt["disabled_reason"], "pending_security_admission")
        self.assertFalse(receipt["runtime_grant_available"])
        self.assertTrue(receipt["declared_not_live_verified"])
        self.assertEqual(receipt["schema_version"], osr.ONE_SHOT_RUNTIME_SCHEMA_VERSION)

    def test_handle_env_digest_stable(self) -> None:
        handle = self.runtime.one_shot_cli_handle("fake-cli", args=("--version",))
        self.assertIsInstance(handle, osr.OneShotCliRunHandle)
        assert isinstance(handle, osr.OneShotCliRunHandle)
        digest1 = handle.env_digest
        result = handle.wait()
        self.assertEqual(result.machine_error_code, osr.ONE_SHOT_OK)
        self.assertEqual(len(digest1), 64)
        self.assertEqual(digest1, handle.env_digest)


class ProductionFacadeTests(unittest.TestCase):
    """The production facade is disabled before ANY side effect."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.facade = osr.ProductionOneShotFacade(homes_root=self.root / "homes")

    def test_every_operational_surface_is_disabled_without_fs_writes(self) -> None:
        for call in (
            lambda: self.facade.create_home("qwen"),
            lambda: self.facade.session("qwen"),
            lambda: self.facade.auth_session("qwen"),
            lambda: self.facade.probe("qwen-cli"),
            lambda: self.facade.run("qwen-cli"),
        ):
            packet = call()
            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                osr.CLI_DISABLED_PENDING_SECURITY_ADMISSION,
            )
            self.assertEqual(packet["changed_files"], [])
            self.assertTrue(packet["cli_disabled"])
        self.assertFalse((self.root / "homes").exists())
        self.assertEqual(list(self.root.rglob("*")), [])

    def test_receipt_is_read_only(self) -> None:
        receipt = self.facade.receipt()
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["changed_files"], [])
        self.assertFalse((self.root / "homes").exists())


if __name__ == "__main__":
    unittest.main()
