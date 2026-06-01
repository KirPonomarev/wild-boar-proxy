# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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

        absent_listener_port = _free_port()
        backend_auth = auth_dir / "backend-a.json"
        backend_auth.write_text("{}\n", encoding="utf-8")
        (profile_dir / "config.toml").write_text(
            f'model = "gpt-5.4"\nbase_url = "http://127.0.0.1:{absent_listener_port}/v1"\n',
            encoding="utf-8",
        )
        (profile_dir / "runtime-mode.txt").write_text("stable\n", encoding="utf-8")
        (profile_dir / "runtime-effective-mode.txt").write_text(
            "stable\n", encoding="utf-8"
        )
        (profile_dir / "auth.json").write_text("{}\n", encoding="utf-8")
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
                "selected_backend_ids": ["backend-a"],
                "managed_port": absent_listener_port,
                "last_error": "",
            },
        )
        (managed_dir / "managed-config.yaml").write_text(
            f"host: 127.0.0.1\nport: {absent_listener_port}\n", encoding="utf-8"
        )
        (stable_dir / "config.yaml").write_text(
            f"host: 127.0.0.1\nport: {absent_listener_port}\n", encoding="utf-8"
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

        summary = {
            "status": "ok",
            "commands": {
                name: {
                    "status": packet["status"],
                    "exit_code": packet["exit_code"],
                    "effect": packet.get("effect"),
                    "machine_error_code": packet["machine_error_code"],
                }
                for name, packet in packets.items()
            },
        }
        sys.stdout.write(json.dumps(summary, ensure_ascii=True, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
