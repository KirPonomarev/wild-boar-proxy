# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy.keychain_preflight import prepare_isolated_home_keychain
from wild_boar_proxy.process_runner import BoundedProcessResult


def completed(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> BoundedProcessResult:
    return BoundedProcessResult(
        status="ok" if returncode == 0 else "error",
        machine_error_code="OK" if returncode == 0 else "PROCESS_FAILED",
        exit_code=returncode,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=False,
        duration_seconds=0.01,
    )


def timeout_result(*, stderr: str = "timed out") -> BoundedProcessResult:
    return BoundedProcessResult(
        status="error",
        machine_error_code="PROCESS_TIMEOUT",
        exit_code=None,
        stdout="",
        stderr=stderr,
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=True,
        duration_seconds=10.0,
    )


class KeychainPreflightTests(unittest.TestCase):
    def test_skips_on_non_darwin(self) -> None:
        with mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "linux"):
            packet = prepare_isolated_home_keychain(isolated_home=Path("/tmp/test-home"))

        self.assertEqual(packet["status"], "skipped")
        self.assertEqual(packet["machine_error_code"], "KEYCHAIN_PREFLIGHT_UNSUPPORTED_PLATFORM")
        self.assertFalse(packet["real_default_keychain_found"])
        self.assertFalse(packet["keychain_item_read"])

    def test_skips_when_security_command_unavailable(self) -> None:
        with (
            mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
            mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value=None),
        ):
            packet = prepare_isolated_home_keychain(isolated_home=Path("/tmp/test-home"))

        self.assertEqual(packet["status"], "skipped")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_SECURITY_COMMAND_UNAVAILABLE",
        )

    def test_skips_when_default_keychain_missing(self) -> None:
        with (
            mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
            mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
            mock.patch(
                "wild_boar_proxy.keychain_preflight.run_bounded_process",
                return_value=completed(returncode=1, stderr="missing"),
            ),
        ):
            packet = prepare_isolated_home_keychain(isolated_home=Path("/tmp/test-home"))

        self.assertEqual(packet["status"], "skipped")
        self.assertEqual(packet["machine_error_code"], "KEYCHAIN_PREFLIGHT_NO_DEFAULT_KEYCHAIN")

    def test_security_bounded_call_removes_hostile_ambient_env(self) -> None:
        observed_envs: list[dict[str, str]] = []

        def fake_run(
            args: list[str],
            env: dict[str, str],
            cwd: Path,
            timeout_seconds: float,
            output_cap_bytes: int,
        ) -> BoundedProcessResult:
            observed_envs.append(dict(env))
            self.assertEqual(cwd, Path("/"))
            return completed(returncode=1, stderr="missing")

        with (
            mock.patch.dict(
                os.environ,
                {
                    "HTTP_PROXY": "http://example.invalid:1",
                    "HTTPS_PROXY": "http://example.invalid:2",
                    "ALL_PROXY": "http://example.invalid:3",
                    "WBP_CURRENT_PROXY_URL": "http://example.invalid:4",
                    "CODEX_HOME": "/tmp/ambient-codex-home",
                    "OPENAI_API_KEY": "ambient-secret",
                    "PATH": "/definitely/missing",
                    "HOME": "/tmp/ambient-home",
                },
                clear=True,
            ),
            mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
            mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
            mock.patch("wild_boar_proxy.keychain_preflight.run_bounded_process", side_effect=fake_run),
        ):
            packet = prepare_isolated_home_keychain(isolated_home=Path("/tmp/test-home"))

        self.assertEqual(packet["status"], "skipped")
        self.assertEqual(packet["machine_error_code"], "KEYCHAIN_PREFLIGHT_NO_DEFAULT_KEYCHAIN")
        self.assertEqual(len(observed_envs), 1)
        env = observed_envs[0]
        self.assertEqual(env["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")
        self.assertNotIn("HTTP_PROXY", env)
        self.assertNotIn("HTTPS_PROXY", env)
        self.assertNotIn("ALL_PROXY", env)
        self.assertNotIn("WBP_CURRENT_PROXY_URL", env)
        self.assertNotIn("CODEX_HOME", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("HOME", env)

    def test_blocks_when_isolated_home_is_not_absolute_without_invoking_security(self) -> None:
        with (
            mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
            mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
            mock.patch("wild_boar_proxy.keychain_preflight.run_bounded_process") as run,
        ):
            packet = prepare_isolated_home_keychain(isolated_home=Path("relative-home"))

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "KEYCHAIN_PREFLIGHT_HOME_NOT_ABSOLUTE")
        run.assert_not_called()

    def test_blocks_when_search_list_contains_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            real_home = Path(temp_dir)
            default_keychain = real_home / "login.keychain-db"
            default_keychain.write_text("", encoding="utf-8")
            search_missing = real_home / "missing.keychain-db"
            results = [
                completed(stdout=f'"{default_keychain}"\n'),
                completed(stdout=f'"{default_keychain}"\n"{search_missing}"\n'),
            ]
            with (
                mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
                mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
                mock.patch(
                    "wild_boar_proxy.keychain_preflight.run_bounded_process",
                    side_effect=results,
                ),
            ):
                packet = prepare_isolated_home_keychain(isolated_home=real_home / "isolated-home")

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_SEARCH_LIST_UNTRUTHFUL",
        )
        self.assertFalse(packet["isolated_home_keychain_preferences_written"])

    def test_ok_writes_isolated_preferences_and_verifies_default_and_search_list(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            isolated_home = root / "isolated-home"
            default_keychain = root / "login.keychain-db"
            system_keychain = root / "System.keychain"
            default_keychain.write_text("", encoding="utf-8")
            system_keychain.write_text("", encoding="utf-8")
            recorded_commands: list[tuple[str, ...]] = []
            recorded_homes: list[str | None] = []

            def fake_run(
                args: list[str],
                env: dict[str, str],
                cwd: Path,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                self.assertEqual(cwd, Path("/"))
                self.assertEqual(timeout_seconds, 10.0)
                self.assertEqual(output_cap_bytes, 16 * 1024)
                self.assertEqual(env["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")
                self.assertNotIn("HTTP_PROXY", env)
                self.assertNotIn("HTTPS_PROXY", env)
                self.assertNotIn("ALL_PROXY", env)
                self.assertNotIn("WBP_CURRENT_PROXY_URL", env)
                self.assertNotIn("CODEX_HOME", env)
                self.assertNotIn("OPENAI_API_KEY", env)
                command = tuple(args[1:])
                recorded_commands.append(command)
                home_value = env.get("HOME")
                recorded_homes.append(home_value)
                home = Path(home_value) if home_value == str(isolated_home) else None
                if command == ("default-keychain", "-d", "user"):
                    stdout = f'"{default_keychain}"\n' if home is None else f'"{default_keychain}"\n'
                    return completed(stdout=stdout)
                if command == ("list-keychains", "-d", "user"):
                    stdout = f'"{default_keychain}"\n"{system_keychain}"\n'
                    return completed(stdout=stdout)
                if command == ("default-keychain", "-d", "user", "-s", str(default_keychain)):
                    prefs = isolated_home / "Library" / "Preferences" / "com.apple.security.plist"
                    prefs.parent.mkdir(parents=True, exist_ok=True)
                    prefs.write_text("plist", encoding="utf-8")
                    return completed()
                if command == (
                    "list-keychains",
                    "-d",
                    "user",
                    "-s",
                    str(default_keychain),
                    str(system_keychain),
                ):
                    return completed()
                raise AssertionError(f"unexpected command: {args}")

            with (
                mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
                mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
                mock.patch("wild_boar_proxy.keychain_preflight.run_bounded_process", side_effect=fake_run),
            ):
                packet = prepare_isolated_home_keychain(isolated_home=isolated_home)

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertTrue(packet["real_default_keychain_found"])
            self.assertEqual(packet["real_default_keychain_path_redacted"], "<redacted>")
            self.assertTrue(packet["real_search_list_found"])
            self.assertTrue(packet["isolated_home_keychain_preferences_written"])
            self.assertTrue(packet["isolated_default_keychain_verified"])
            self.assertTrue(packet["isolated_search_list_verified"])
            self.assertFalse(packet["real_user_keychain_modified"])
            self.assertFalse(packet["keychain_reset_performed"])
            self.assertEqual(
                packet["prompt_avoidance_claim_scope"],
                "keychain_not_found_prompt_only",
            )
            self.assertTrue(
                (isolated_home / "Library" / "Preferences" / "com.apple.security.plist").exists()
            )
            self.assertFalse(
                any(
                    command and command[0] in {
                        "unlock-keychain",
                        "create-keychain",
                        "delete-keychain",
                        "find-generic-password",
                        "find-internet-password",
                    }
                    for command in recorded_commands
                )
            )
            self.assertEqual(recorded_homes[:2], [None, None])
            self.assertEqual(recorded_homes[2:], [str(isolated_home)] * 4)

    def test_failed_when_set_default_times_out_without_stronger_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            isolated_home = root / "isolated-home"
            default_keychain = root / "login.keychain-db"
            system_keychain = root / "System.keychain"
            default_keychain.write_text("", encoding="utf-8")
            system_keychain.write_text("", encoding="utf-8")
            results = [
                completed(stdout=f'"{default_keychain}"\n'),
                completed(stdout=f'"{default_keychain}"\n"{system_keychain}"\n'),
                timeout_result(),
            ]
            with (
                mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
                mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
                mock.patch(
                    "wild_boar_proxy.keychain_preflight.run_bounded_process",
                    side_effect=results,
                ),
            ):
                packet = prepare_isolated_home_keychain(isolated_home=isolated_home)

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_SET_DEFAULT_FAILED",
        )
        self.assertFalse(packet["isolated_home_keychain_preferences_written"])
        self.assertFalse(packet["isolated_default_keychain_verified"])
        self.assertFalse(packet["isolated_search_list_verified"])
        self.assertFalse(packet["real_user_keychain_modified"])
        self.assertFalse(packet["keychain_item_read"])

    def test_failed_when_isolated_default_verification_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            isolated_home = root / "isolated-home"
            default_keychain = root / "login.keychain-db"
            system_keychain = root / "System.keychain"
            other_keychain = root / "other.keychain-db"
            default_keychain.write_text("", encoding="utf-8")
            system_keychain.write_text("", encoding="utf-8")
            other_keychain.write_text("", encoding="utf-8")

            def fake_run(
                args: list[str],
                env: dict[str, str],
                cwd: Path,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                self.assertEqual(cwd, Path("/"))
                command = tuple(args[1:])
                home = Path(env["HOME"]) if env.get("HOME") == str(isolated_home) else None
                if command == ("default-keychain", "-d", "user"):
                    if home is None:
                        return completed(stdout=f'"{default_keychain}"\n')
                    return completed(stdout=f'"{other_keychain}"\n')
                if command == ("list-keychains", "-d", "user"):
                    return completed(stdout=f'"{default_keychain}"\n"{system_keychain}"\n')
                if command == ("default-keychain", "-d", "user", "-s", str(default_keychain)):
                    prefs = isolated_home / "Library" / "Preferences" / "com.apple.security.plist"
                    prefs.parent.mkdir(parents=True, exist_ok=True)
                    prefs.write_text("plist", encoding="utf-8")
                    return completed()
                if command == (
                    "list-keychains",
                    "-d",
                    "user",
                    "-s",
                    str(default_keychain),
                    str(system_keychain),
                ):
                    return completed()
                raise AssertionError(f"unexpected command: {args}")

            with (
                mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
                mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
                mock.patch("wild_boar_proxy.keychain_preflight.run_bounded_process", side_effect=fake_run),
            ):
                packet = prepare_isolated_home_keychain(isolated_home=isolated_home)

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_VERIFY_DEFAULT_MISMATCH",
        )
        self.assertTrue(packet["isolated_home_keychain_preferences_written"])
        self.assertFalse(packet["isolated_search_list_verified"])

    def test_failed_when_isolated_search_list_verification_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            isolated_home = root / "isolated-home"
            default_keychain = root / "login.keychain-db"
            system_keychain = root / "System.keychain"
            other_keychain = root / "other.keychain-db"
            default_keychain.write_text("", encoding="utf-8")
            system_keychain.write_text("", encoding="utf-8")
            other_keychain.write_text("", encoding="utf-8")

            def fake_run(
                args: list[str],
                env: dict[str, str],
                cwd: Path,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                self.assertEqual(cwd, Path("/"))
                command = tuple(args[1:])
                home = Path(env["HOME"]) if env.get("HOME") == str(isolated_home) else None
                if command == ("default-keychain", "-d", "user"):
                    return completed(stdout=f'"{default_keychain}"\n')
                if command == ("list-keychains", "-d", "user"):
                    if home is None:
                        return completed(stdout=f'"{default_keychain}"\n"{system_keychain}"\n')
                    return completed(stdout=f'"{default_keychain}"\n"{other_keychain}"\n')
                if command == ("default-keychain", "-d", "user", "-s", str(default_keychain)):
                    prefs = isolated_home / "Library" / "Preferences" / "com.apple.security.plist"
                    prefs.parent.mkdir(parents=True, exist_ok=True)
                    prefs.write_text("plist", encoding="utf-8")
                    return completed()
                if command == (
                    "list-keychains",
                    "-d",
                    "user",
                    "-s",
                    str(default_keychain),
                    str(system_keychain),
                ):
                    return completed()
                raise AssertionError(f"unexpected command: {args}")

            with (
                mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
                mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
                mock.patch("wild_boar_proxy.keychain_preflight.run_bounded_process", side_effect=fake_run),
            ):
                packet = prepare_isolated_home_keychain(isolated_home=isolated_home)

        self.assertEqual(packet["status"], "failed")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_VERIFY_SEARCH_LIST_MISMATCH",
        )
        self.assertTrue(packet["isolated_home_keychain_preferences_written"])
        self.assertTrue(packet["isolated_default_keychain_verified"])
        self.assertFalse(packet["isolated_search_list_verified"])

    def test_blocks_when_isolated_home_points_at_real_home(self) -> None:
        real_home = Path("/tmp/real-home").resolve()
        with (
            mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
            mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
            mock.patch("wild_boar_proxy.keychain_preflight.REAL_HOME", real_home),
        ):
            packet = prepare_isolated_home_keychain(isolated_home=real_home)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_REAL_HOME_FORBIDDEN",
        )

    def test_blocks_when_library_preferences_escape_via_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            isolated_home = root / "isolated-home"
            default_keychain = root / "login.keychain-db"
            system_keychain = root / "System.keychain"
            outside = root / "outside"
            default_keychain.write_text("", encoding="utf-8")
            system_keychain.write_text("", encoding="utf-8")
            outside.mkdir()
            isolated_home.mkdir()
            (isolated_home / "Library").symlink_to(outside, target_is_directory=True)

            results = [
                completed(stdout=f'"{default_keychain}"\n'),
                completed(stdout=f'"{default_keychain}"\n"{system_keychain}"\n'),
            ]
            with (
                mock.patch("wild_boar_proxy.keychain_preflight.sys.platform", "darwin"),
                mock.patch("wild_boar_proxy.keychain_preflight.shutil.which", return_value="/usr/bin/security"),
                mock.patch(
                    "wild_boar_proxy.keychain_preflight.run_bounded_process",
                    side_effect=results,
                ),
            ):
                packet = prepare_isolated_home_keychain(isolated_home=isolated_home)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "KEYCHAIN_PREFLIGHT_WRITE_SURFACE_BLOCKED",
        )


if __name__ == "__main__":
    unittest.main()
