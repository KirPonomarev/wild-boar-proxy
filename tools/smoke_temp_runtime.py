# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.truth_tree_harness import assert_no_truth_mutation, snapshot_truth_tree


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8")


def _strict_json_object(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    payload, index = decoder.raw_decode(raw)
    if raw[index:].strip():
        raise AssertionError("stdout must contain exactly one JSON object")
    if not isinstance(payload, dict):
        raise AssertionError("stdout JSON payload must be an object")
    return payload


class _SmokeRuntimeHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._send_json({"data": [{"id": "gpt-5.4"}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/v1/responses":
            length = int(self.headers.get("content-length", "0"))
            if length:
                self.rfile.read(length)
            self._send_json({"output_text": "OK"})
            return
        self.send_error(404)

    def log_message(self, format: str, *args: Any) -> None:
        return


@contextmanager
def _live_runtime() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SmokeRuntimeHandler)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _truth_paths(profile_dir: Path, managed_dir: Path) -> dict[str, Path]:
    external_dir = managed_dir / "external-models"
    return {
        "backend-registry.json": managed_dir / "backend-registry.json",
        "supervisor-state.json": managed_dir / "supervisor-state.json",
        "managed-config.yaml": managed_dir / "managed-config.yaml",
        "runtime-mode.txt": profile_dir / "runtime-mode.txt",
        "runtime-effective-mode.txt": profile_dir / "runtime-effective-mode.txt",
        "config.toml": profile_dir / "config.toml",
        "external-models/state.json": external_dir / "state.json",
        "external-models/routes.json": external_dir / "routes.json",
        "external-models/secrets.env": external_dir / "secrets.env",
    }


def _run(env: dict[str, str], *args: str) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, "-m", "wild_boar_proxy", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    payload = _strict_json_object(result.stdout)
    if int(payload["exit_code"]) != result.returncode:
        raise AssertionError(
            f"exit_code mismatch for {' '.join(args)}: "
            f"process={result.returncode} payload={payload['exit_code']}"
        )
    return result, payload


def _build_summary(packets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failed_commands: list[dict[str, Any]] = []
    command_summaries: dict[str, dict[str, Any]] = {}
    for name, packet in packets.items():
        status = str(packet["status"])
        exit_code = int(packet["exit_code"])
        machine_error_code = str(packet["machine_error_code"])
        command_summaries[name] = {
            "status": status,
            "exit_code": exit_code,
            "effect": packet.get("effect"),
            "machine_error_code": machine_error_code,
        }
        if status != "ok" or exit_code != 0:
            failed_commands.append(
                {
                    "command": name,
                    "status": status,
                    "exit_code": exit_code,
                    "machine_error_code": machine_error_code,
                }
            )

    if failed_commands:
        return {
            "status": "error",
            "exit_code": 1,
            "machine_error_code": failed_commands[0]["machine_error_code"],
            "failed_commands": failed_commands,
            "commands": command_summaries,
        }
    return {
        "status": "ok",
        "exit_code": 0,
        "machine_error_code": "OK",
        "failed_commands": [],
        "commands": command_summaries,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wbp-smoke-") as raw_root:
        root = Path(raw_root)
        profile_dir = root / "profile"
        managed_dir = root / "managed"
        stable_dir = root / "stable"
        external_dir = managed_dir / "external-models"
        auth_dir = root / "auth"
        for path in (profile_dir, managed_dir, stable_dir, external_dir, auth_dir):
            path.mkdir(parents=True)

        with _live_runtime() as live_listener_port:
            backend_auth = auth_dir / "backend-a.json"
            backend_auth.write_text("{}\n", encoding="utf-8")
            (profile_dir / "config.toml").write_text(
                f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{live_listener_port}/v1"\n',
                encoding="utf-8",
            )
            (profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
            (profile_dir / "runtime-effective-mode.txt").write_text(
                "stable\n", encoding="utf-8"
            )
            (profile_dir / "auth.json").write_text(
                json.dumps({"OPENAI_API_KEY": "smoke-runtime-key"}) + "\n",
                encoding="utf-8",
            )
            _write_json(
                managed_dir / "backend-registry.json",
                {
                    "schema_version": 2,
                    "version": 2,
                    "updated_at": "2026-06-01T00:00:00+00:00",
                    "stable_default_backend_id": "default-backend",
                    "pool_policy": {
                        "active_min": 1,
                        "active_target": 2,
                        "reserve_target": 0,
                    },
                    "backends": [
                        {
                            "id": "backend-a",
                            "label": "Backend A",
                            "pool": "active",
                            "status": "healthy",
                            "manual_hold": False,
                            "auth_ref": str(backend_auth),
                            "fail_count": 0,
                            "success_count": 1,
                        }
                    ],
                },
            )
            _write_json(
                managed_dir / "supervisor-state.json",
                {
                    "schema_version": 2,
                    "version": 2,
                    "status": "healthy",
                    "effective_mode": "stable",
                    "selected_backend_ids": [],
                    "managed_port": live_listener_port,
                    "last_error": "",
                },
            )
            (managed_dir / "managed-config.yaml").write_text(
                f"host: 127.0.0.1\nport: {live_listener_port}\n", encoding="utf-8"
            )
            (stable_dir / "config.yaml").write_text(
                f"host: 127.0.0.1\nport: {live_listener_port}\n", encoding="utf-8"
            )
            _write_json(
                external_dir / "state.json",
                {
                    "schema_version": 2,
                    "policy": {
                        "paid_routes_enabled": False,
                        "paid_route_allowlist": [],
                        "paid_route_default": "blocked",
                    },
                    "adapter": {"state": "stopped"},
                    "local_auth": {"token_present": False},
                    "routes": {},
                },
            )
            _write_json(external_dir / "routes.json", {"schema_version": 1, "routes": []})
            secrets_file = external_dir / "secrets.env"
            secrets_file.write_text("OPENROUTER_API_KEY=smoke-secret\n", encoding="utf-8")
            os.chmod(secrets_file, 0o600)

            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(ROOT),
                    "WBP_PROFILE_DIR": str(profile_dir),
                    "WBP_MANAGED_DIR": str(managed_dir),
                    "WBP_STABLE_CONFIG": str(stable_dir / "config.yaml"),
                    "WBP_AUTH_FILE": str(profile_dir / "auth.json"),
                    "WBP_CONFIG_TOML": str(profile_dir / "config.toml"),
                    "WBP_RUNTIME_MODE_FILE": str(profile_dir / "runtime-mode.txt"),
                    "WBP_RUNTIME_EFFECTIVE_MODE_FILE": str(
                        profile_dir / "runtime-effective-mode.txt"
                    ),
                    "WBP_REGISTRY_FILE": str(managed_dir / "backend-registry.json"),
                    "WBP_STATE_FILE": str(managed_dir / "supervisor-state.json"),
                    "WBP_MANAGED_CONFIG_FILE": str(managed_dir / "managed-config.yaml"),
                    "WBP_EXTERNAL_MODELS_DIR": str(external_dir),
                    "NO_PROXY": "*",
                    "no_proxy": "*",
                }
            )

            truth_paths = _truth_paths(profile_dir, managed_dir)
            before = snapshot_truth_tree(
                truth_paths, secret_labels={"external-models/secrets.env"}
            )
            commands = {
                "status": ("status", "--json"),
                "healthcheck": ("healthcheck", "--json"),
                "mode_get": ("mode", "get", "--json"),
                "accounts_list": ("accounts", "list", "--json"),
            }
            packets: dict[str, dict[str, Any]] = {}
            raw_outputs: list[str] = []
            for name, command in commands.items():
                result, payload = _run(env, *command)
                packets[name] = payload
                raw_outputs.append(result.stdout)
                if result.stderr:
                    raise AssertionError(f"{name} wrote stderr: {result.stderr}")

            after = snapshot_truth_tree(
                truth_paths, secret_labels={"external-models/secrets.env"}
            )
            assert_no_truth_mutation(before, after)

            if packets["status"]["effect"] != "read":
                raise AssertionError("status smoke packet must be read")
            if packets["healthcheck"]["effect"] != "probe":
                raise AssertionError("healthcheck smoke packet must be probe")
            if packets["healthcheck"]["changed_files"] != []:
                raise AssertionError("healthcheck probe smoke must not declare writes")
            if packets["mode_get"]["effect"] != "read":
                raise AssertionError("mode get smoke packet must be read")
            if packets["accounts_list"]["effect"] != "read":
                raise AssertionError("accounts list smoke packet must be read")

            joined_output = "\n".join(raw_outputs)
            forbidden_user_paths = {str(Path.home()), "/Users/kirillponomarev"}
            leaked = [path for path in forbidden_user_paths if path and path in joined_output]
            if leaked:
                raise AssertionError(f"smoke output leaked user paths: {leaked}")

            summary = _build_summary(packets)
            sys.stdout.write(
                json.dumps(summary, ensure_ascii=True, sort_keys=True) + "\n"
            )
    return int(summary["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
