# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B09: generic one-shot CLI runtime tests (fake-adapter evidence).

The fake adapter is a shell CLI registered through the test-only
`WBP_ONE_SHOT_FAKE_MANIFEST` hook. It exercises the full runtime: sterile
probes, scrubbed environments, provider homes, bounded process groups,
cancellation, parsers, auth sessions, and the no-resume rule.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import one_shot_cli_runtime as osr

def _load_test_manifest(path):
    """Load fake manifest entries from JSON for _inject_test_config."""
    import json
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    from wild_boar_proxy.one_shot_cli_runtime import OneShotToolManifestEntry
    entries = []
    for item in data.get("tools", []):
        entries.append(OneShotToolManifestEntry(
            tool_id=str(item["tool_id"]),
            binary_name=str(item["binary_name"]),
            display_name=str(item.get("display_name", item["tool_id"])),
            version_args=tuple(str(a) for a in item.get("version_args", ("--version",))),
            output_profiles=tuple(str(p) for p in item.get("output_profiles", ("text",))),
            server_owned=False,
        ))
    return tuple(entries)

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


def _write_fake_cli(root: Path) -> Path:
    script = root / "fake-cli.sh"
    script.write_text(FAKE_CLI_TEXT, encoding="utf-8")
    script.chmod(0o755)
    return script


def _write_fake_manifest(root: Path, script: Path) -> Path:
    manifest = root / "fake-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "tool_id": "fake-cli",
                        "binary_name": str(script),
                        "display_name": "Fake CLI",
                        "version_args": ["--version"],
                        "output_profiles": ["text", "key_value", "json_lines"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest


class FakeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.script = _write_fake_cli(self.root)
        self.manifest = _write_fake_manifest(self.root, self.script)
        self.homes_root = self.root / "homes"
        self._old_env: dict[str, str] = {}
        for name in (
            osr.FAKE_MANIFEST_ENV,
            osr.HOMES_ROOT_ENV,
            "LEAK_TEST_SECRET",
            "LEAK_TEST_TOKEN",
            "LEAK_TEST_PASSWORD",
            "KEPT_VAR",
        ):
            self._old_env[name] = os.environ.get(name, "")
        osr._inject_test_config(homes_root=self.homes_root, fake_manifest=_load_test_manifest(self.manifest))
        os.environ["LEAK_TEST_SECRET"] = "must-not-leak-1"
        os.environ["LEAK_TEST_TOKEN"] = "must-not-leak-2"
        os.environ["LEAK_TEST_PASSWORD"] = "must-not-leak-3"
        os.environ["KEPT_VAR"] = "kept-value"

    def tearDown(self) -> None:
        osr._clear_test_config()
        self.temp_dir.cleanup()

    def test_unknown_tool_fails_closed(self) -> None:
        packet = osr.one_shot_cli_run("no-such-tool")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], osr.ONE_SHOT_TOOL_UNKNOWN)
        self.assertIsNone(osr.resolve_manifest_entry("no-such-tool"))

    def test_manifest_is_server_owned(self) -> None:
        entry = osr.resolve_manifest_entry("fake-cli")
        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertFalse(entry.server_owned)  # fake hook, not server-owned
        self.assertEqual(entry.tool_id, "fake-cli")
        self.assertEqual(entry.version_args, ("--version",))
        self.assertEqual(osr.SERVER_OWNED_TOOL_MANIFEST, ())

    def test_sterile_probe_returns_realpath_version_digest(self) -> None:
        packet = osr.run_sterile_probe("fake-cli")
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
        manifest = self.root / "missing-manifest.json"
        manifest.write_text(
            json.dumps(
                {"tools": [{"tool_id": "ghost", "binary_name": "/nonexistent/ghost"}]}
            ),
            encoding="utf-8",
        )
        osr._inject_test_config(fake_manifest=_load_test_manifest(manifest))
        packet = osr.run_sterile_probe("ghost")
        self.assertEqual(packet["status"], "error")
        # ghost is in the manifest but binary doesn't exist -> TOOL_BINARY_NOT_FOUND
        self.assertEqual(packet["machine_error_code"], osr.TOOL_BINARY_NOT_FOUND)

    def test_scrubbed_environment_never_leaks_secrets(self) -> None:
        env = osr.build_sterile_environment(provider_home=self.homes_root / "probe-home")
        for key in ("LEAK_TEST_SECRET", "LEAK_TEST_TOKEN", "LEAK_TEST_PASSWORD"):
            self.assertNotIn(key, env)
        self.assertTrue(env["PATH"].startswith("/usr/bin"))
        self.assertNotIn("/opt/homebrew", env["PATH"])
        self.assertEqual(env["HOME"], str(self.homes_root / "probe-home"))

        env = osr.build_sterile_environment(
            provider_home=self.homes_root / "run-home",
            keep=("KEPT_VAR",),
        )
        handle = osr.one_shot_cli_handle(
            "fake-cli",
            args=("--env-report",),
            provider_home=self.homes_root / "run-home",
            env=env,
        )
        if isinstance(handle, dict):
            packet = handle
        else:
            result = handle.wait(timeout_seconds=10)
            packet = osr.build_command_payload(
                ok=result.status == "ok",
                human_message="ok" if result.status == "ok" else "fail",
                machine_error_code=result.machine_error_code,
                liveness="healthy", severity="info", operator_action="none",
                changed_files=[], exit_code=result.exit_code,
                extra={"run": result.to_dict()},
            )
        self.assertEqual(packet["status"], "ok")
        stdout = packet["run"]["stdout"]
        self.assertNotIn("must-not-leak-1", stdout)
        self.assertNotIn("must-not-leak-2", stdout)
        self.assertNotIn("must-not-leak-3", stdout)
        self.assertIn("LEAK_TEST_SECRET=<absent>", stdout)
        self.assertIn("KEPT_VAR=kept-value", stdout)
        self.assertIn("HOME=" + str(self.homes_root / "run-home"), stdout)

    def test_provider_home_is_isolated_and_0700(self) -> None:
        packet = osr.create_provider_home("qwen-test")
        self.assertEqual(packet["status"], "ok")
        home = Path(packet["home_path"])
        runtime_dir = Path(packet["runtime_dir"])
        self.assertTrue(home.is_dir())
        self.assertTrue(runtime_dir.is_dir())
        self.assertEqual(oct(home.stat().st_mode & 0o777), "0o700")
        self.assertEqual(oct(runtime_dir.stat().st_mode & 0o777), "0o700")
        self.assertTrue(str(home).startswith(str(self.homes_root)))

    def test_provider_home_rejects_invalid_id(self) -> None:
        packet = osr.create_provider_home("../escape")
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], osr.ONE_SHOT_SCHEMA_INVALID)

    def test_bounded_run_captures_stdin_and_stdout(self) -> None:
        packet = osr.one_shot_cli_run(
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
        packet = osr.one_shot_cli_run(
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
        handle = osr.one_shot_cli_handle("fake-cli", args=("--sleep", "30"))
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
        packet = osr.one_shot_cli_run(
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
        packet = osr.one_shot_cli_run(
            "fake-cli",
            args=("--noise",),
            output_cap_bytes=512,
        )
        self.assertEqual(packet["status"], "ok")
        run = packet["run"]
        self.assertTrue(run["stdout_truncated"])
        self.assertLessEqual(len(run["stdout"]), 512)

    def test_one_shot_never_resumes(self) -> None:
        packet = osr.one_shot_cli_run("fake-cli", args=("--version",))
        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["resume_supported"])
        self.assertFalse(packet["run"]["resume_supported"])
        self.assertEqual(
            packet["resume_reason"], osr.ONE_SHOT_NO_RESUME_REASON
        )
        receipt = osr.build_one_shot_runtime_receipt()
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
        started = osr.one_shot_auth_session("qwen-test", home)
        self.assertEqual(started["status"], "ok")
        self.assertTrue(started["presence_only"])
        self.assertFalse(started["secret_values_exposed"])
        session_file = Path(started["auth_dir"]) / "session.json"
        self.assertEqual(oct(session_file.stat().st_mode & 0o777), "0o600")
        # Packet must not contain session secret material (there is none).
        body = json.dumps(started)
        self.assertNotIn("must-not-leak", body)

        status = osr.one_shot_auth_status(home)
        self.assertTrue(status["auth_present"])
        self.assertFalse(status["secret_values_exposed"])

        ended = osr.end_one_shot_auth_session(home)
        self.assertTrue(ended["removed"])
        status2 = osr.one_shot_auth_status(home)
        self.assertFalse(status2["auth_present"])

    def test_sandbox_profile_is_honest(self) -> None:
        profile = osr.SandboxProfile()
        self.assertEqual(profile.repo_write, "denied")
        self.assertEqual(profile.repo_read, "none")
        probe = osr.probe_os_sandbox()
        self.assertIn("os_sandbox_available", probe)
        self.assertIn(probe["os_enforcement"], {"os_sandbox_available", "declared_not_available"})
        # A caller-supplied profile is reported as given (no simulation).
        supplied = osr.SandboxProfile(os_enforcement=probe["os_enforcement"])
        handle = osr.one_shot_cli_handle(
            "fake-cli",
            args=("--version",),
            sandbox=supplied,
        )
        if isinstance(handle, dict):
            packet = handle
        else:
            result = handle.wait(timeout_seconds=10)
            packet = osr.build_command_payload(
                ok=result.status == "ok",
                human_message="ok" if result.status == "ok" else "fail",
                machine_error_code=result.machine_error_code,
                liveness="healthy", severity="info", operator_action="none",
                changed_files=[], exit_code=result.exit_code,
                extra={"run": result.to_dict(), "sandbox": supplied.to_dict()},
            )
        self.assertEqual(packet["sandbox"]["repo_write"], "denied")
        self.assertEqual(
            packet["sandbox"]["os_enforcement"], probe["os_enforcement"]
        )
        # The runtime default probes the OS honestly instead of lying.
        default = osr.default_sandbox_profile()
        self.assertEqual(default.os_enforcement, probe["os_enforcement"])

    def test_runtime_receipt_declared_not_live(self) -> None:
        receipt = osr.build_one_shot_runtime_receipt()
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["machine_error_code"], "SYNTHETIC_PROVEN")
        self.assertTrue(receipt["declared_not_live_verified"])
        self.assertEqual(receipt["schema_version"], 1)

    def test_handle_env_digest_stable(self) -> None:
        handle = osr.one_shot_cli_handle("fake-cli", args=("--version",))
        self.assertIsInstance(handle, osr.OneShotCliRunHandle)
        assert isinstance(handle, osr.OneShotCliRunHandle)
        digest1 = handle.env_digest
        result = handle.wait()
        self.assertEqual(result.machine_error_code, osr.ONE_SHOT_OK)
        self.assertEqual(len(digest1), 64)
        self.assertEqual(digest1, handle.env_digest)


if __name__ == "__main__":
    unittest.main()
