#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Temporary hardened operator surface for isolated Codex/WBP proof contours.

This is a proof harness, not a production web app. It intentionally keeps all
mutable runtime state under a temporary root and exposes only localhost JSON
surfaces suitable for browser proof and process-only isolation proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT = "http://127.0.0.1:8318/v1"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_CODEX_BIN = "/Applications/Codex.app/Contents/Resources/codex"
DEFAULT_RUNTIME_CONFIG = (
    "/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml"
)
FORBIDDEN_BROWSER_FIELD_NAMES = {
    "api_key",
    "apikey",
    "secret",
    "token",
    "auth",
    "auth_path",
    "path",
    "backend_id",
    "route_id",
}
SECRET_PATTERNS = [
    re.compile(r"s" r"k-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"secret" r"-key\s*:\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"api" r"-keys\s*:\s*[^\n]{8,}", re.IGNORECASE),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_local_api_key(config_path: Path) -> str:
    text = config_path.read_text(encoding="utf-8", errors="replace")
    api_keys = re.search(
        r"^\s*api-keys\s*:\s*\n\s*-\s*[\"']?([^\"'\s#]+)",
        text,
        re.MULTILINE,
    )
    if api_keys and len(api_keys.group(1).strip()) >= 8:
        return api_keys.group(1).strip()

    secret_key = re.search(r"^\s*secret" r"-key\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    if secret_key:
        value = secret_key.group(1).strip().strip("\"'")
        if value and value != "\"\"" and len(value) >= 8:
            return value

    raise RuntimeError("stable runtime local API key shape invalid")


def build_codex_config(*, endpoint: str, model_id: str) -> str:
    return (
        f'model = "{model_id}"\n'
        'model_provider = "cliproxy"\n'
        'approval_policy = "never"\n'
        'sandbox_mode = "read-only"\n'
        "disable_response_storage = true\n\n"
        "[model_providers.cliproxy]\n"
        'name = "CLIProxyAPI via Wild Boar Proxy"\n'
        f'base_url = "{endpoint}"\n'
        'env_key = "OPENAI_API_KEY"\n'
        'wire_api = "responses"\n'
    )


def forbidden_browser_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if lowered in FORBIDDEN_BROWSER_FIELD_NAMES:
                findings.append(key_path)
            findings.extend(forbidden_browser_fields(value, key_path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(forbidden_browser_fields(value, f"{prefix}[{index}]"))
    return findings


def select_server_issued_model(model_id: str, allowed_models: list[str]) -> str:
    if model_id not in allowed_models:
        raise ValueError("model_id_not_server_issued")
    return model_id


def redact_text(text: str, secret_values: list[str] | None = None) -> str:
    redacted = text
    for secret in secret_values or []:
        if secret:
            redacted = redacted.replace(secret, "<redacted-secret>")
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("<redacted-secret>", redacted)
    return redacted


def stat_hash(path: str) -> dict[str, Any]:
    real_path = Path(path)
    record: dict[str, Any] = {
        "path_label": path.replace(str(Path.home()), "~"),
        "exists": real_path.exists(),
    }
    if not real_path.exists():
        return record
    stat = real_path.stat()
    record.update(
        {
            "is_dir": real_path.is_dir(),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }
    )
    if real_path.is_file() and stat.st_size <= 5_000_000:
        digest = hashlib.sha256()
        with real_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        record["sha256"] = digest.hexdigest()
    return record


def protected_snapshot() -> dict[str, dict[str, Any]]:
    return {
        "codex_config": stat_hash("/Users/kirillponomarev/.codex/config.toml"),
        "codex_auth": stat_hash("/Users/kirillponomarev/.codex/auth.json"),
        "default_app_support_codex": stat_hash(
            "/Users/kirillponomarev/Library/Application Support/Codex"
        ),
        "default_cache_codex": stat_hash(
            "/Users/kirillponomarev/Library/Caches/com.openai.codex"
        ),
        "default_httpstorage_codex": stat_hash(
            "/Users/kirillponomarev/Library/HTTPStorages/com.openai.codex"
        ),
    }


def compare_snapshots(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    comparisons: dict[str, dict[str, Any]] = {}
    for key, old_value in before.items():
        new_value = after.get(key, {})
        comparisons[key] = {
            "exists_unchanged": old_value.get("exists") == new_value.get("exists"),
            "mtime_ns_unchanged": old_value.get("mtime_ns") == new_value.get("mtime_ns"),
            "size_unchanged": old_value.get("size") == new_value.get("size"),
            "sha256_unchanged": (
                old_value.get("sha256") == new_value.get("sha256")
                if ("sha256" in old_value or "sha256" in new_value)
                else None
            ),
        }
    return comparisons


def protected_surfaces_unchanged(comparisons: dict[str, dict[str, Any]]) -> bool:
    for result in comparisons.values():
        if not result.get("exists_unchanged"):
            return False
        if not result.get("mtime_ns_unchanged"):
            return False
        if not result.get("size_unchanged"):
            return False
        if result.get("sha256_unchanged") is False:
            return False
    return True


def remove_tree_with_retry(path: Path, *, attempts: int = 8, delay_seconds: float = 0.25) -> str:
    """Remove a temp tree while tolerating short-lived child cleanup races."""
    last_error = ""
    for _ in range(attempts):
        if not path.exists():
            return ""
        try:
            shutil.rmtree(path)
        except OSError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(delay_seconds)
            continue
        if not path.exists():
            return ""
    return last_error


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    return env


@dataclass
class HarnessConfig:
    repo_root: Path
    tmp_root: Path
    endpoint: str
    default_model: str
    codex_bin: Path
    runtime_config: Path
    max_prompt_chars: int = 8000
    timeout_seconds: int = 180


class OperatorSurfaceHarness:
    def __init__(self, config: HarnessConfig) -> None:
        self.config = config
        self.packets_dir = config.tmp_root / "packets"
        self.packets_dir.mkdir(parents=True, exist_ok=True)
        self.transcript: list[dict[str, Any]] = []
        self.prompt_counter = 0
        self.allowed_models = self.probe_models()["model_ids"]
        if config.default_model not in self.allowed_models and self.allowed_models:
            self.allowed_models.insert(0, config.default_model)

    def local_api_key(self) -> str:
        return extract_local_api_key(self.config.runtime_config)

    def write_packet(self, name: str, data: dict[str, Any]) -> None:
        json_write(self.packets_dir / name, data)

    def probe_models(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status_code": None,
            "ok": False,
            "model_ids": [],
            "chosen_model_visible": False,
            "error": "",
        }
        try:
            request = urllib.request.Request(
                f"{self.config.endpoint}/models",
                headers={"Authorization": f"Bearer {self.local_api_key()}"},
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
                model_ids = [
                    item.get("id")
                    for item in data.get("data", [])
                    if isinstance(item, dict) and item.get("id")
                ]
                result.update(
                    {
                        "status_code": response.status,
                        "ok": response.status == 200,
                        "model_ids": model_ids[:100],
                        "chosen_model_visible": self.config.default_model in model_ids,
                    }
                )
        except Exception as exc:  # pragma: no cover - exercised in live contour proof
            result["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return result

    def run_wbp(self, args: list[str]) -> dict[str, Any]:
        process = subprocess.run(
            ["python3", "-m", "wild_boar_proxy", *args],
            cwd=str(self.config.repo_root),
            env=clean_env(),
            text=True,
            capture_output=True,
            timeout=120,
        )
        packet = None
        if process.stdout.strip():
            try:
                packet = json.loads(process.stdout)
            except json.JSONDecodeError:
                packet = None
        return {
            "exit_code": process.returncode,
            "json": packet,
            "stdout_redacted_len": len(process.stdout),
            "stderr_redacted_len": len(process.stderr),
            "timestamp_utc": utc_now(),
        }

    def status_payload(self) -> dict[str, Any]:
        status = self.run_wbp(["status", "--json"])
        healthcheck = self.run_wbp(["healthcheck", "--json"])
        models = self.probe_models()
        status_packet = status.get("json") or {}
        health_packet = healthcheck.get("json") or {}
        payload = {
            "captured_at_utc": utc_now(),
            "status": {
                "status": status_packet.get("status"),
                "machine_error_code": status_packet.get("machine_error_code"),
                "liveness": status_packet.get("liveness"),
                "endpoint": status_packet.get("endpoint"),
                "effective_mode": status_packet.get("effective_mode"),
                "configured_model": status_packet.get("configured_model"),
            },
            "health": {
                "status": health_packet.get("status"),
                "machine_error_code": health_packet.get("machine_error_code"),
                "liveness": health_packet.get("liveness"),
            },
            "claim_gate": status_packet.get("claim_gate", {"status": "not_reported"}),
            "models": {
                "status_code": models.get("status_code"),
                "ok": models.get("ok"),
                "model_ids": models.get("model_ids", []),
                "chosen_model_visible": self.config.default_model
                in models.get("model_ids", []),
            },
            "control_surface": {
                "localhost_only": True,
                "browser_secret_fields": False,
                "raw_path_fields": False,
            },
        }
        self.write_packet("status_action_proof.json", payload)
        return payload

    def run_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        forbidden = forbidden_browser_fields(payload)
        if forbidden:
            return {
                "status": "rejected",
                "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
                "forbidden_fields": forbidden,
            }

        prompt = payload.get("prompt")
        model_id = payload.get("model_id")
        if not isinstance(prompt, str) or not prompt.strip():
            return {"status": "rejected", "machine_error_code": "PROMPT_REQUIRED"}
        if len(prompt) > self.config.max_prompt_chars:
            return {"status": "rejected", "machine_error_code": "PROMPT_TOO_LONG"}
        if not isinstance(model_id, str):
            return {"status": "rejected", "machine_error_code": "MODEL_REQUIRED"}
        try:
            selected_model = select_server_issued_model(model_id, self.allowed_models)
        except ValueError:
            return {
                "status": "rejected",
                "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
            }

        self.prompt_counter += 1
        run_root = Path(tempfile.mkdtemp(prefix="operator-run-", dir=str(self.config.tmp_root)))
        home = run_root / "home"
        codex_home = run_root / "codex-home"
        work = run_root / "work"
        home.mkdir()
        work.mkdir()
        codex_home.mkdir()
        (codex_home / "config.toml").write_text(
            build_codex_config(endpoint=self.config.endpoint, model_id=selected_model),
            encoding="utf-8",
        )
        last_message = run_root / "last_message.txt"
        stdout_file = run_root / "stdout.jsonl"
        stderr_file = run_root / "stderr.txt"

        env = clean_env()
        env.update(
            {
                "HOME": str(home),
                "CODEX_HOME": str(codex_home),
                "OPENAI_API_KEY": self.local_api_key(),
            }
        )
        command = [
            str(self.config.codex_bin),
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "-C",
            str(work),
            "--json",
            "-o",
            str(last_message),
            "-",
        ]
        started = time.time()
        timed_out = False
        try:
            process = subprocess.run(
                command,
                cwd=str(work),
                env=env,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.config.timeout_seconds,
            )
            exit_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""

        local_key = self.local_api_key()
        stdout_file.write_text(redact_text(stdout, [local_key]), encoding="utf-8")
        stderr_file.write_text(redact_text(stderr, [local_key]), encoding="utf-8")
        final_message = (
            redact_text(
                last_message.read_text(encoding="utf-8", errors="replace"),
                [local_key],
            ).strip()
            if last_message.exists()
            else ""
        )
        warnings = []
        if "Failed to sync remote plugins" in stderr:
            warnings.append("remote_plugin_sync_401")

        proof = {
            "prompt_id": f"prompt_{self.prompt_counter}",
            "prompt_text_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "selected_model": selected_model,
            "final_message": final_message,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": round(time.time() - started, 3),
            "stderr_warning_classes": warnings,
            "temp_home_under_tmp": str(home).startswith(str(self.config.tmp_root)),
            "temp_codex_home_under_tmp": str(codex_home).startswith(str(self.config.tmp_root)),
            "local_proxy_env_stripped": True,
            "no_proxy_for_localhost": True,
            "stdin_prompt_used": True,
            "command_surface": {
                "binary": "<codex>",
                "args_shape": [
                    "exec",
                    "--skip-git-repo-check",
                    "--ephemeral",
                    "--ignore-rules",
                    "--sandbox",
                    "read-only",
                    "-C",
                    "<temp-work>",
                    "--json",
                    "-o",
                    "<temp-last-message>",
                    "-",
                ],
            },
            "stdout_file_stat": {
                "exists": stdout_file.exists(),
                "size": stdout_file.stat().st_size if stdout_file.exists() else 0,
            },
            "stderr_file_stat": {
                "exists": stderr_file.exists(),
                "size": stderr_file.stat().st_size if stderr_file.exists() else 0,
            },
            "last_message_file_stat": {
                "exists": last_message.exists(),
                "size": last_message.stat().st_size if last_message.exists() else 0,
            },
            "secret_value_recorded": False,
            "captured_at_utc": utc_now(),
        }
        self.write_packet(f"{proof['prompt_id']}_proof.json", proof)
        self.transcript.append(
            {
                "prompt_id": proof["prompt_id"],
                "prompt_sha256": proof["prompt_text_sha256"],
                "selected_model": selected_model,
                "final_message": final_message,
                "exit_code": exit_code,
                "warning_classes": warnings,
                "captured_at_utc": proof["captured_at_utc"],
            }
        )
        transcript_packet = {
            "captured_at_utc": utc_now(),
            "entries": self.transcript,
            "secret_value_recorded": False,
        }
        self.write_packet("transcript_redacted.json", transcript_packet)
        return {
            "status": "ok" if exit_code == 0 and bool(final_message) else "failed",
            "machine_error_code": "OK" if exit_code == 0 and bool(final_message) else "ENGINE_PROMPT_FAILED",
            "prompt_id": proof["prompt_id"],
            "selected_model": selected_model,
            "final_message": final_message,
            "exit_code": exit_code,
            "warning_classes": warnings,
        }

    def transcript_payload(self) -> dict[str, Any]:
        payload = {
            "captured_at_utc": utc_now(),
            "entries": self.transcript,
            "secret_value_recorded": False,
        }
        self.write_packet("transcript_redacted.json", payload)
        return payload

    def html(self) -> str:
        options = "\n".join(
            f'<option value="{model}">{model}</option>' for model in self.allowed_models
        )
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WBP Codex Operator Surface</title>
<style>
:root {{ color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
body {{ margin: 0; background: #f7f7f4; color: #171717; }}
main {{ max-width: 1080px; margin: 0 auto; padding: 24px; }}
header {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid #d7d7d0; padding-bottom: 16px; }}
h1 {{ font-size: 22px; margin: 0; letter-spacing: 0; }}
.status {{ font-size: 13px; padding: 8px 10px; border: 1px solid #cbc9bf; background: #fff; border-radius: 6px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; }}
section {{ border: 1px solid #d4d2c9; background: #fff; border-radius: 8px; padding: 14px; }}
h2 {{ font-size: 15px; margin: 0 0 10px; }}
textarea, select {{ box-sizing: border-box; width: 100%; font: 14px ui-monospace, SFMono-Regular, Menlo, monospace; border: 1px solid #b9b7ad; border-radius: 6px; padding: 10px; }}
textarea {{ min-height: 132px; resize: vertical; margin-top: 10px; }}
button {{ border: 1px solid #2e4a62; background: #355c7d; color: white; border-radius: 6px; padding: 9px 11px; margin: 8px 8px 0 0; font-size: 13px; cursor: pointer; }}
button.secondary {{ background: #fff; color: #253545; border-color: #a9b1b8; }}
pre {{ overflow: auto; white-space: pre-wrap; word-break: break-word; min-height: 136px; border: 1px solid #dedcd4; background: #fbfbf8; border-radius: 6px; padding: 10px; font-size: 12px; }}
@media (max-width: 760px) {{ .grid {{ grid-template-columns: 1fr; }} main {{ padding: 16px; }} header {{ align-items: flex-start; flex-direction: column; }} }}
</style>
</head>
<body>
<main>
<header><h1>WBP Codex Operator Surface</h1><div id="status-line" class="status">not refreshed</div></header>
<div class="grid">
<section>
  <h2>Prompt</h2>
  <select id="model">{options}</select>
  <textarea id="prompt">Reply with exactly HARDENED_OK.</textarea>
  <button id="run">Run Prompt</button>
  <button id="refresh" class="secondary">Refresh Status</button>
  <button id="export" class="secondary">Export Redacted Transcript</button>
</section>
<section><h2>Response</h2><pre id="response">idle</pre></section>
<section><h2>Runtime Status</h2><pre id="runtime">not loaded</pre></section>
<section><h2>Transcript</h2><pre id="transcript">not exported</pre></section>
</div>
</main>
<script>
async function getJson(url, opts) {{
  const res = await fetch(url, opts || {{}});
  const data = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(data));
  return data;
}}
function show(id, value) {{ document.getElementById(id).textContent = JSON.stringify(value, null, 2); }}
async function refreshStatus() {{
  document.getElementById('status-line').textContent = 'refreshing';
  const data = await getJson('/api/status');
  show('runtime', data);
  document.getElementById('status-line').textContent = 'status=' + data.status.status + ' health=' + data.health.status + ' claim_gate=' + data.claim_gate.status;
}}
async function runPrompt() {{
  document.getElementById('response').textContent = 'running';
  const prompt = document.getElementById('prompt').value;
  const model_id = document.getElementById('model').value;
  const data = await getJson('/api/run', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{prompt, model_id}})}});
  show('response', data);
  document.getElementById('status-line').textContent = 'last_response=' + data.final_message;
}}
async function exportTranscript() {{
  const data = await getJson('/api/transcript');
  show('transcript', data);
}}
document.getElementById('refresh').addEventListener('click', refreshStatus);
document.getElementById('run').addEventListener('click', runPrompt);
document.getElementById('export').addEventListener('click', exportTranscript);
window.addEventListener('load', refreshStatus);
</script>
</body>
</html>
"""

    def build_handler(self) -> type[BaseHTTPRequestHandler]:
        harness = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, code: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
                if self.path == "/":
                    data = harness.html().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if self.path == "/api/status":
                    self._json(200, harness.status_payload())
                    return
                if self.path == "/api/models":
                    self._json(
                        200,
                        {
                            "captured_at_utc": utc_now(),
                            "model_ids": harness.allowed_models,
                            "server_issued": True,
                        },
                    )
                    return
                if self.path == "/api/transcript":
                    self._json(200, harness.transcript_payload())
                    return
                self._json(404, {"status": "not_found"})

            def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8", errors="replace")
                try:
                    payload = json.loads(raw or "{}")
                except json.JSONDecodeError:
                    self._json(400, {"status": "rejected", "machine_error_code": "BAD_JSON"})
                    return
                if self.path == "/api/run":
                    result = harness.run_prompt(payload)
                    self._json(200 if result.get("status") != "rejected" else 400, result)
                    return
                self._json(404, {"status": "not_found"})

            def log_message(self, fmt: str, *args: Any) -> None:
                return

        return Handler


def find_free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def create_harness(args: argparse.Namespace) -> OperatorSurfaceHarness:
    tmp_root = Path(args.tmp_root) if args.tmp_root else Path(
        tempfile.mkdtemp(prefix="wbp-operator-surface-hardened-")
    )
    tmp_root.mkdir(parents=True, exist_ok=True)
    return OperatorSurfaceHarness(
        HarnessConfig(
            repo_root=Path(args.repo_root).resolve(),
            tmp_root=tmp_root,
            endpoint=args.endpoint,
            default_model=args.model,
            codex_bin=Path(args.codex_bin),
            runtime_config=Path(args.runtime_config),
            max_prompt_chars=args.max_prompt_chars,
            timeout_seconds=args.timeout_seconds,
        )
    )


def run_server(args: argparse.Namespace) -> int:
    harness = create_harness(args)
    port = int(args.port or find_free_port())
    server = ThreadingHTTPServer(("127.0.0.1", port), harness.build_handler())
    harness.write_packet(
        "server_listen.json",
        {
            "host": "127.0.0.1",
            "port": port,
            "tmp_root": str(harness.config.tmp_root),
            "endpoint": harness.config.endpoint,
            "default_model": harness.config.default_model,
            "localhost_only": True,
            "started_at_utc": utc_now(),
        },
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "url": f"http://127.0.0.1:{port}/",
                "tmp_root": str(harness.config.tmp_root),
                "packets_dir": str(harness.packets_dir),
                "model_ids": harness.allowed_models,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


def run_process_proof(args: argparse.Namespace) -> int:
    harness = create_harness(args)
    before = protected_snapshot()
    status = harness.status_payload()
    run_result = harness.run_prompt({"prompt": args.prompt, "model_id": args.model})
    transcript = harness.transcript_payload()
    after = protected_snapshot()
    comparisons = compare_snapshots(before, after)
    cleanup_error = remove_tree_with_retry(harness.config.tmp_root)
    packet = {
        "captured_at_utc": utc_now(),
        "status_action": status,
        "run_result": run_result,
        "transcript": transcript,
        "protected_pre_snapshot": before,
        "protected_post_snapshot": after,
        "comparisons": comparisons,
        "protected_surfaces_unchanged": protected_surfaces_unchanged(comparisons),
        "tmp_root_removed": not harness.config.tmp_root.exists(),
        "cleanup_error": cleanup_error,
        "secret_value_recorded": False,
    }
    if args.output:
        json_write(Path(args.output), packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if run_result.get("status") == "ok" and packet["protected_surfaces_unchanged"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="operator-control-surface-harness")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--codex-bin", default=DEFAULT_CODEX_BIN)
    parser.add_argument("--runtime-config", default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--tmp-root")
    parser.add_argument("--max-prompt-chars", type=int, default=8000)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve")
    serve.add_argument("--port", type=int)

    process_proof = subparsers.add_parser("process-proof")
    process_proof.add_argument("--prompt", required=True)
    process_proof.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        return run_server(args)
    if args.command == "process-proof":
        return run_process_proof(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
