from __future__ import annotations

import argparse
import ast
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from wild_boar_proxy.process_runner import (
    PROCESS_FAILED,
    PROCESS_OK,
    PROCESS_TIMEOUT,
    BoundedProcessResult,
)
from wild_boar_proxy.runtime import RuntimePaths
from wild_boar_proxy import sandbox_owner_helpers as helpers


ROOT = Path(__file__).resolve().parents[1]
SANDBOX_OWNER_HELPERS = ROOT / "wild_boar_proxy" / "sandbox_owner_helpers.py"


def _runtime_paths(root: Path) -> RuntimePaths:
    profile_dir = root / "profile"
    managed_dir = profile_dir / "managed"
    stable_config = root / "stable" / "config.yaml"
    for path in (profile_dir, managed_dir, stable_config.parent):
        path.mkdir(parents=True, exist_ok=True)
    stable_config.write_text(
        f'host: 127.0.0.1\nport: 8318\nauth-dir: "{managed_dir / "auth-source"}"\n',
        encoding="utf-8",
    )
    return RuntimePaths(
        profile_dir=profile_dir,
        managed_dir=managed_dir,
        stable_config=stable_config,
        auth_file=profile_dir / "auth.json",
        config_toml=profile_dir / "config.toml",
        runtime_mode_file=profile_dir / "runtime-mode.txt",
        runtime_effective_mode_file=profile_dir / "runtime-effective-mode.txt",
        registry_file=managed_dir / "backend-registry.json",
        state_file=managed_dir / "supervisor-state.json",
        managed_config_file=managed_dir / "managed-config.yaml",
        launcher_script=profile_dir / "codex-custom-launch.sh",
        sync_script=managed_dir / "supervisor-sync.sh",
        accounts_bin=managed_dir / "bin" / "codex-accounts",
        onboard_bin=managed_dir / "bin" / "codex-account-onboard",
        lock_file=managed_dir / "wild-boar-proxy.lock",
        launcher_lock_file=managed_dir / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed_dir / "stable-repair-target",
        repair_target_reference_file=managed_dir / "approved-repair-target.json",
        target_switch_transaction_file=managed_dir / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed_dir
        / "stable-runtime-config.generated.yaml",
    )


def _args(*, device_login: bool = False, no_browser: bool = False) -> argparse.Namespace:
    return argparse.Namespace(device_login=device_login, no_browser=no_browser)


def _bounded_result(
    *,
    machine_error_code: str,
    exit_code: int | None,
    stdout: str = "",
    stderr: str = "",
    stdout_truncated: bool = False,
    stderr_truncated: bool = False,
    timed_out: bool = False,
) -> BoundedProcessResult:
    return BoundedProcessResult(
        status="ok" if machine_error_code == PROCESS_OK else "error",
        machine_error_code=machine_error_code,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        timed_out=timed_out,
        duration_seconds=0.01,
    )


def _function(path: Path, name: str) -> ast.FunctionDef:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function not found: {path}:{name}")


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _call_names(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            dotted = _dotted_name(child.func)
            if dotted:
                calls.add(dotted)
                calls.add(dotted.rsplit(".", 1)[-1])
    return calls


def _function_source(path: Path, name: str) -> str:
    source = path.read_text(encoding="utf-8")
    segment = ast.get_source_segment(source, _function(path, name))
    if segment is None:
        raise AssertionError(f"Source segment not found: {path}:{name}")
    return segment


class SandboxOwnerHelpersTests(unittest.TestCase):
    def test_run_login_flow_uses_bounded_runner_with_sanitized_env_and_device_args(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            fake_cli = paths.managed_dir / "fake-cli-proxy-api"
            fake_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_cli.chmod(0o755)
            calls: list[dict[str, object]] = []

            def fake_run_bounded_process(
                command: list[str],
                *,
                env: dict[str, str],
                stdout_passthrough: object,
                stderr_passthrough: object,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                calls.append(
                    {
                        "command": command,
                        "env": env,
                        "stdout_passthrough": stdout_passthrough,
                        "stderr_passthrough": stderr_passthrough,
                        "timeout_seconds": timeout_seconds,
                        "output_cap_bytes": output_cap_bytes,
                    }
                )
                return _bounded_result(machine_error_code=PROCESS_OK, exit_code=0)

            env = {
                "WBP_CLIPROXY_BIN": str(fake_cli),
                "WBP_REQUIRE_SANDBOX_AUTH_DIR": "1",
                "HTTP_PROXY": "http://proxy.invalid",
                "HTTPS_PROXY": "http://proxy.invalid",
                "ALL_PROXY": "http://proxy.invalid",
                "http_proxy": "http://proxy.invalid",
                "https_proxy": "http://proxy.invalid",
                "all_proxy": "http://proxy.invalid",
            }
            with (
                mock.patch.dict(os.environ, env, clear=True),
                mock.patch("sys.stdout", io.StringIO()),
                mock.patch("sys.stderr", io.StringIO()),
                mock.patch.object(
                    helpers,
                    "run_bounded_process",
                    side_effect=fake_run_bounded_process,
                ),
            ):
                exit_code = helpers.run_login_flow(
                    paths,
                    _args(device_login=True, no_browser=True),
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            calls[0]["command"],
            [
                str(fake_cli),
                "-config",
                str(paths.stable_config),
                "-codex-device-login",
                "-no-browser",
            ],
        )
        bounded_env = calls[0]["env"]
        self.assertIsInstance(bounded_env, dict)
        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            self.assertNotIn(key, bounded_env)
        self.assertEqual(bounded_env["NO_PROXY"], "127.0.0.1,localhost,::1")
        self.assertEqual(bounded_env["no_proxy"], "127.0.0.1,localhost,::1")
        self.assertEqual(
            calls[0]["timeout_seconds"],
            helpers.SANDBOX_LOGIN_PROCESS_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            calls[0]["output_cap_bytes"],
            helpers.SANDBOX_LOGIN_PROCESS_OUTPUT_CAP_BYTES,
        )

    def test_run_login_flow_passes_streams_through_and_preserves_nonzero_exit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            fake_cli = paths.managed_dir / "fake-cli-proxy-api"
            fake_cli.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
            fake_cli.chmod(0o755)
            stdout = io.StringIO()
            stderr = io.StringIO()

            def fake_run_bounded_process(
                command: list[str],
                *,
                env: dict[str, str],
                stdout_passthrough: io.StringIO,
                stderr_passthrough: io.StringIO,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                stdout_passthrough.write("login stdout\n")
                stderr_passthrough.write("login stderr\n")
                return _bounded_result(
                    machine_error_code=PROCESS_FAILED,
                    exit_code=7,
                    stdout="login stdout\n",
                    stderr="login stderr\n",
                )

            with (
                mock.patch.dict(os.environ, {"WBP_CLIPROXY_BIN": str(fake_cli)}, clear=True),
                mock.patch.object(
                    helpers,
                    "run_bounded_process",
                    side_effect=fake_run_bounded_process,
                ),
                mock.patch("sys.stdout", stdout),
                mock.patch("sys.stderr", stderr),
            ):
                exit_code = helpers.run_login_flow(paths, _args())

        self.assertEqual(exit_code, 7)
        self.assertEqual(stdout.getvalue(), "login stdout\n")
        self.assertEqual(stderr.getvalue(), "login stderr\n")

    def test_run_login_flow_timeout_returns_124_without_success_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            fake_cli = paths.managed_dir / "fake-cli-proxy-api"
            fake_cli.write_text("#!/bin/sh\nsleep 10\n", encoding="utf-8")
            fake_cli.chmod(0o755)
            stderr = io.StringIO()

            def fake_run_bounded_process(
                command: list[str],
                *,
                env: dict[str, str],
                stdout_passthrough: io.StringIO,
                stderr_passthrough: io.StringIO,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                stderr_passthrough.write("partial login stderr")
                return _bounded_result(
                    machine_error_code=PROCESS_TIMEOUT,
                    exit_code=-9,
                    stderr="partial login stderr",
                    timed_out=True,
                )

            with (
                mock.patch.dict(os.environ, {"WBP_CLIPROXY_BIN": str(fake_cli)}, clear=True),
                mock.patch.object(
                    helpers,
                    "run_bounded_process",
                    side_effect=fake_run_bounded_process,
                ),
                mock.patch("sys.stderr", stderr),
            ):
                exit_code = helpers.run_login_flow(paths, _args())

        self.assertEqual(exit_code, helpers.SANDBOX_LOGIN_TIMEOUT_EXIT_CODE)
        self.assertIn("partial login stderr", stderr.getvalue())
        self.assertIn("sandbox login subprocess timed out", stderr.getvalue())

    def test_run_login_flow_machine_failure_with_zero_exit_is_not_success(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            fake_cli = paths.managed_dir / "fake-cli-proxy-api"
            fake_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_cli.chmod(0o755)
            stderr = io.StringIO()

            with (
                mock.patch.dict(os.environ, {"WBP_CLIPROXY_BIN": str(fake_cli)}, clear=True),
                mock.patch.object(
                    helpers,
                    "run_bounded_process",
                    return_value=_bounded_result(
                        machine_error_code=PROCESS_FAILED,
                        exit_code=0,
                        stderr="process output streams did not close before bounded drain completed",
                    ),
                ),
                mock.patch("sys.stdout", io.StringIO()),
                mock.patch("sys.stderr", stderr),
            ):
                exit_code = helpers.run_login_flow(paths, _args())

        self.assertEqual(exit_code, 1)
        self.assertIn("PROCESS_FAILED", stderr.getvalue())

    def test_run_login_flow_discloses_capped_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _runtime_paths(Path(temp_dir))
            fake_cli = paths.managed_dir / "fake-cli-proxy-api"
            fake_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_cli.chmod(0o755)
            stdout = io.StringIO()
            stderr = io.StringIO()

            def fake_run_bounded_process(
                command: list[str],
                *,
                env: dict[str, str],
                stdout_passthrough: io.StringIO,
                stderr_passthrough: io.StringIO,
                timeout_seconds: float,
                output_cap_bytes: int,
            ) -> BoundedProcessResult:
                stdout_passthrough.write("capped stdout")
                return _bounded_result(
                    machine_error_code=PROCESS_OK,
                    exit_code=0,
                    stdout="capped stdout",
                    stdout_truncated=True,
                )

            with (
                mock.patch.dict(os.environ, {"WBP_CLIPROXY_BIN": str(fake_cli)}, clear=True),
                mock.patch.object(
                    helpers,
                    "run_bounded_process",
                    side_effect=fake_run_bounded_process,
                ),
                mock.patch("sys.stdout", stdout),
                mock.patch("sys.stderr", stderr),
            ):
                exit_code = helpers.run_login_flow(paths, _args())

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "capped stdout")
        self.assertIn("stdout truncated", stderr.getvalue())

    def test_run_login_flow_uses_bounded_runner_without_raw_subprocess(self) -> None:
        calls = _call_names(_function(SANDBOX_OWNER_HELPERS, "run_login_flow"))
        source = _function_source(SANDBOX_OWNER_HELPERS, "run_login_flow")
        self.assertIn("run_bounded_process", calls)
        self.assertIn("SANDBOX_LOGIN_PROCESS_TIMEOUT_SECONDS", source)
        self.assertIn("SANDBOX_LOGIN_PROCESS_OUTPUT_CAP_BYTES", source)
        self.assertIn("stdout_passthrough=sys.stdout", source)
        self.assertIn("stderr_passthrough=sys.stderr", source)
        self.assertNotIn("subprocess.run", calls)
        self.assertNotIn("Popen", calls)


if __name__ == "__main__":
    unittest.main()
