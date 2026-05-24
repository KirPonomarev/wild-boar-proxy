# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Safe Codex Operator surface adapter for WBP web integration."""

from __future__ import annotations

import hashlib
import http.server
import json
import os
import re
import shutil
import socket
import threading
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ENDPOINT = "http://127.0.0.1:8318/v1"
DEFAULT_MODEL = "gpt-5.3-codex"
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
    "runtime_config",
    "trace_wbp",
    "trace_observer",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*[:=]\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"secret-key\s*:\s*[^\s\",}]{8,}", re.IGNORECASE),
    re.compile(r"api-keys\s*:\s*[^\n]{8,}", re.IGNORECASE),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    return env


def extract_local_api_key(config_path: Path) -> str:
    text = config_path.read_text(encoding="utf-8", errors="replace")
    api_keys = re.search(
        r"^\s*api-keys\s*:\s*\n\s*-\s*[\"']?([^\"'\s#]+)",
        text,
        re.MULTILINE,
    )
    if api_keys and len(api_keys.group(1).strip()) >= 8:
        return api_keys.group(1).strip()
    secret_key = re.search(r"^\s*secret-key\s*:\s*(.+?)\s*$", text, re.MULTILINE)
    if secret_key:
        value = secret_key.group(1).strip().strip("\"'")
        if value and value != "\"\"" and len(value) >= 8:
            return value
    raise RuntimeError("stable runtime local API key shape invalid")


def forbidden_browser_fields(payload: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in FORBIDDEN_BROWSER_FIELD_NAMES:
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


def _body_digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _forward_request_headers(headers: dict[str, str]) -> dict[str, str]:
    excluded = {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "cookie",
    }
    forwarded: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() not in excluded:
            forwarded[key] = value
    forwarded.setdefault("Content-Type", "application/json")
    return forwarded


def _empty_trace_packet() -> dict[str, Any]:
    return {
        "request_observed": False,
        "response_observed": False,
        "forwarded_to_wbp": False,
        "forwarded_endpoint": "",
        "method": "",
        "path": "",
        "request_body_sha256": "",
        "response_body_sha256": "",
        "upstream_status": None,
        "prompt_body_recorded": False,
        "auth_header_recorded": False,
        "secret_value_recorded": False,
        "raw_account_id_recorded": False,
        "raw_backend_id_recorded": False,
        "machine_error_code": "TRACE_NOT_STARTED",
    }


class _TraceObserverServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler: type[http.server.BaseHTTPRequestHandler], observer: "WbpTraceObserver") -> None:
        super().__init__(server_address, handler)
        self.observer = observer


class _TraceObserverHandler(http.server.BaseHTTPRequestHandler):
    server: _TraceObserverServer

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return

    def do_GET(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def _handle(self) -> None:
        status, body, headers = self.server.observer.forward(
            method=self.command,
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=self.rfile.read(int(self.headers.get("Content-Length", "0") or "0")),
        )
        self.send_response(status)
        for key, value in headers.items():
            if key.lower() not in {"connection", "transfer-encoding", "content-length"}:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WbpTraceObserver:
    """Temporary localhost proxy that records redacted WBP path evidence."""

    def __init__(self, *, downstream_endpoint: str) -> None:
        self.downstream_endpoint = downstream_endpoint.rstrip("/")
        self._httpd: _TraceObserverServer | None = None
        self._thread: threading.Thread | None = None
        self.listen_endpoint = ""
        self._packet = _empty_trace_packet()

    def __enter__(self) -> "WbpTraceObserver":
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = int(sock.getsockname()[1])
        self._httpd = _TraceObserverServer(("127.0.0.1", port), _TraceObserverHandler, self)
        self.listen_endpoint = f"http://127.0.0.1:{port}/v1"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self._packet = {
            **_empty_trace_packet(),
            "machine_error_code": "TRACE_READY",
            "listen_endpoint": self.listen_endpoint,
            "downstream_endpoint": self.downstream_endpoint,
        }
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    def forward(self, *, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, bytes, dict[str, str]]:
        allowed = method == "GET" and path in {"/v1/models", "/models"}
        allowed = allowed or method == "POST" and path in {"/v1/responses", "/responses", "/v1/chat/completions", "/chat/completions"}
        forwarded_url = f"{self.downstream_endpoint}{path[3:] if path.startswith('/v1/') else path}"
        request_digest = _body_digest(body) if body else ""
        self._packet.update(
            {
                "request_observed": True,
                "method": method,
                "path": path,
                "request_body_sha256": request_digest,
                "prompt_body_recorded": False,
                "auth_header_recorded": False,
                "secret_value_recorded": False,
                "raw_account_id_recorded": False,
                "raw_backend_id_recorded": False,
            }
        )
        if not allowed:
            response_body = json.dumps({"error": {"message": "trace observer path not allowed"}}).encode("utf-8")
            self._packet.update({"machine_error_code": "TRACE_PATH_NOT_ALLOWED", "upstream_status": 403})
            return 403, response_body, {"Content-Type": "application/json"}
        request_headers = _forward_request_headers(headers)
        request = urllib.request.Request(forwarded_url, data=body if method != "GET" else None, headers=request_headers, method=method)
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=60) as response:
                response_body = response.read()
                status = int(response.status)
                response_headers = {"Content-Type": response.headers.get("Content-Type", "application/json")}
        except urllib.error.HTTPError as exc:
            response_body = exc.read()
            status = int(exc.code)
            response_headers = {"Content-Type": exc.headers.get("Content-Type", "application/json")}
        except Exception as exc:
            response_body = json.dumps({"error": {"message": "trace observer upstream request failed"}}).encode("utf-8")
            status = 502
            response_headers = {"Content-Type": "application/json"}
            self._packet.update({"machine_error_code": type(exc).__name__})
        if 200 <= status < 400:
            machine_error_code = "OK"
        elif 400 <= status < 500:
            machine_error_code = f"TRACE_UPSTREAM_HTTP_{status}"
        else:
            machine_error_code = self._packet.get("machine_error_code") or "TRACE_UPSTREAM_FAILED"
        self._packet.update(
            {
                "response_observed": True,
                "forwarded_to_wbp": True,
                "forwarded_endpoint": self.downstream_endpoint,
                "upstream_status": status,
                "response_body_sha256": _body_digest(response_body) if response_body else "",
                "machine_error_code": machine_error_code,
            }
        )
        return status, response_body, response_headers

    def packet(self) -> dict[str, Any]:
        packet = dict(self._packet)
        packet["observer_closed"] = self._httpd is None
        return packet


def stat_hash(path: str) -> dict[str, Any]:
    real_path = Path(path)
    record: dict[str, Any] = {
        "path_label": path.replace(str(Path.home()), "~"),
        "exists": real_path.exists(),
    }
    if not real_path.exists():
        return record
    stat = real_path.stat()
    record.update({"is_dir": real_path.is_dir(), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
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
    return {
        key: {
            "exists_unchanged": old.get("exists") == after.get(key, {}).get("exists"),
            "mtime_ns_unchanged": old.get("mtime_ns") == after.get(key, {}).get("mtime_ns"),
            "size_unchanged": old.get("size") == after.get(key, {}).get("size"),
            "sha256_unchanged": (
                old.get("sha256") == after.get(key, {}).get("sha256")
                if ("sha256" in old or "sha256" in after.get(key, {}))
                else None
            ),
        }
        for key, old in before.items()
    }


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


@dataclass
class OperatorSurfaceConfig:
    repo_root: Path = Path(__file__).resolve().parents[1]
    endpoint: str = DEFAULT_ENDPOINT
    default_model: str = DEFAULT_MODEL
    codex_bin: Path = Path(DEFAULT_CODEX_BIN)
    runtime_config: Path = Path(DEFAULT_RUNTIME_CONFIG)
    max_prompt_chars: int = 8000
    timeout_seconds: int = 180


@dataclass
class OperatorSurfaceSession:
    config: OperatorSurfaceConfig = field(default_factory=OperatorSurfaceConfig)
    transcript: list[dict[str, Any]] = field(default_factory=list)
    prompt_counter: int = 0

    def local_api_key(self) -> str:
        return extract_local_api_key(self.config.runtime_config)

    def probe_models(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status_code": None,
            "ok": False,
            "model_ids": [],
            "chosen_model_visible": False,
            "error": "",
            "server_issued": True,
            "captured_at_utc": utc_now(),
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
        except Exception as exc:  # pragma: no cover - live runtime surface
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
        health = self.run_wbp(["healthcheck", "--json"])
        models = self.probe_models()
        status_packet = status.get("json") or {}
        health_packet = health.get("json") or {}
        return {
            "captured_at_utc": utc_now(),
            "status": {
                "status": status_packet.get("status"),
                "machine_error_code": status_packet.get("machine_error_code"),
                "liveness": status_packet.get("liveness"),
                "endpoint": status_packet.get("endpoint"),
                "configured_model": status_packet.get("configured_model"),
                "effective_mode": status_packet.get("effective_mode"),
            },
            "health": {
                "status": health_packet.get("status"),
                "machine_error_code": health_packet.get("machine_error_code"),
                "liveness": health_packet.get("liveness"),
            },
            "claim_gate": status_packet.get("claim_gate", {"status": "not_reported"}),
            "models": models,
            "control_surface": {
                "localhost_only": True,
                "browser_secret_fields": False,
                "raw_path_fields": False,
            },
        }

    def transcript_payload(self) -> dict[str, Any]:
        return {
            "captured_at_utc": utc_now(),
            "entries": self.transcript,
            "secret_value_recorded": False,
        }

    def run_prompt(self, payload: dict[str, Any], *, trace_wbp: bool = False) -> dict[str, Any]:
        forbidden = forbidden_browser_fields(payload)
        if forbidden:
            return {
                "status": "rejected",
                "machine_error_code": "FORBIDDEN_BROWSER_FIELD",
                "human_message": "Browser payload contains forbidden fields.",
                "forbidden_fields": forbidden,
                "refresh_packet": self.status_payload(),
            }
        prompt = payload.get("prompt")
        model_id = payload.get("model_id")
        if not isinstance(prompt, str) or not prompt.strip():
            return {
                "status": "rejected",
                "machine_error_code": "PROMPT_REQUIRED",
                "human_message": "Prompt is required.",
                "refresh_packet": self.status_payload(),
            }
        if len(prompt) > self.config.max_prompt_chars:
            return {
                "status": "rejected",
                "machine_error_code": "PROMPT_TOO_LONG",
                "human_message": "Prompt exceeds bounded operator action limit.",
                "refresh_packet": self.status_payload(),
            }
        if not isinstance(model_id, str):
            return {
                "status": "rejected",
                "machine_error_code": "MODEL_REQUIRED",
                "human_message": "Model must come from server-issued model list.",
                "refresh_packet": self.status_payload(),
            }
        models = self.probe_models()
        try:
            selected_model = select_server_issued_model(model_id, list(models.get("model_ids", [])))
        except ValueError:
            return {
                "status": "rejected",
                "machine_error_code": "MODEL_NOT_SERVER_ISSUED",
                "human_message": "Model id was not present in the current server-issued list.",
                "refresh_packet": self.status_payload(),
            }
        try:
            secret = self.local_api_key()
        except Exception as exc:
            return {
                "status": "failed",
                "machine_error_code": "OPERATOR_LOCAL_API_KEY_UNAVAILABLE",
                "human_message": "Operator local API key is unavailable in owner-side runtime config.",
                "error_class": type(exc).__name__,
                "refresh_packet": self.status_payload(),
                "secret_value_recorded": False,
            }
        if not self.config.codex_bin.exists():
            return {
                "status": "failed",
                "machine_error_code": "OPERATOR_CODEX_BINARY_UNAVAILABLE",
                "human_message": "Codex engine binary is unavailable on this host.",
                "refresh_packet": self.status_payload(),
                "secret_value_recorded": False,
            }

        self.prompt_counter += 1
        tmp_root = Path(tempfile.mkdtemp(prefix="wbp-main-web-operator-"))
        run_root = tmp_root / "run"
        home = run_root / "home"
        codex_home = run_root / "codex-home"
        work = run_root / "work"
        home.mkdir(parents=True)
        codex_home.mkdir()
        work.mkdir()
        trace_observer = WbpTraceObserver(downstream_endpoint=self.config.endpoint) if trace_wbp else None
        effective_endpoint = self.config.endpoint
        if trace_observer:
            trace_observer.__enter__()
            effective_endpoint = trace_observer.listen_endpoint
        config_text = build_codex_config(endpoint=effective_endpoint, model_id=selected_model)
        (codex_home / "config.toml").write_text(config_text, encoding="utf-8")
        last_message = run_root / "last_message.txt"
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
        current_codex_home = (Path.home() / ".codex").resolve()
        env_codex_home = Path(env["CODEX_HOME"]).resolve()
        env_home = Path(env["HOME"]).resolve()
        temp_root_resolved = tmp_root.resolve()
        config_sha256 = hashlib.sha256(config_text.encode("utf-8")).hexdigest()
        timed_out = False
        trace_packet = _empty_trace_packet()
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
            stderr = process.stderr
        except OSError as exc:
            exit_code = 127
            stderr = f"{type(exc).__name__}: {exc}"
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stderr = exc.stderr or ""
        finally:
            if trace_observer:
                trace_packet = trace_observer.packet()
                trace_observer.__exit__(None, None, None)
        final_message = (
            redact_text(last_message.read_text(encoding="utf-8", errors="replace"), [secret]).strip()
            if last_message.exists()
            else ""
        )
        warning_classes = []
        if "Failed to sync remote plugins" in stderr:
            warning_classes.append("remote_plugin_sync_401")
        cleanup_error = remove_tree_with_retry(tmp_root)
        prompt_id = f"operator_prompt_{self.prompt_counter}"
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        entry = {
            "prompt_id": prompt_id,
            "prompt_hash": prompt_hash,
            "selected_model": selected_model,
            "final_message": final_message,
            "exit_code": exit_code,
            "warning_classes": warning_classes,
            "captured_at_utc": utc_now(),
        }
        self.transcript.append(entry)
        ok = exit_code == 0 and bool(final_message)
        trace_machine_error_code = str(trace_packet.get("machine_error_code") or "")
        prompt_machine_error_code = "OK" if ok else "ENGINE_PROMPT_FAILED"
        if (
            not ok
            and trace_wbp
            and trace_packet.get("response_observed") is True
            and trace_machine_error_code.startswith("TRACE_UPSTREAM_HTTP_")
        ):
            prompt_machine_error_code = trace_machine_error_code
        return {
            "status": "ok" if ok else "failed",
            "machine_error_code": prompt_machine_error_code,
            "human_message": "Codex Operator prompt completed." if ok else "Codex Operator prompt failed.",
            "selected_model": selected_model,
            "configured_base_url": effective_endpoint,
            "downstream_wbp_endpoint": self.config.endpoint,
            "configured_wire_api": "responses",
            "configured_provider": "cliproxy",
            "wbp_endpoint_configured": effective_endpoint.startswith("http://127.0.0.1:"),
            "config_sha256": config_sha256,
            "config_endpoint_matches": f'base_url = "{effective_endpoint}"' in config_text,
            "config_provider_matches": 'model_provider = "cliproxy"' in config_text,
            "config_wire_api_matches": 'wire_api = "responses"' in config_text,
            "trace_observer_enabled": trace_wbp,
            "trace_observer_packet": trace_packet,
            "independent_wbp_trace_observed": (
                trace_packet.get("request_observed") is True
                and trace_packet.get("response_observed") is True
                and trace_packet.get("forwarded_to_wbp") is True
                and trace_packet.get("forwarded_endpoint") == self.config.endpoint
                and isinstance(trace_packet.get("upstream_status"), int)
                and 200 <= int(trace_packet.get("upstream_status")) < 400
                and trace_packet.get("secret_value_recorded") is False
                and trace_packet.get("prompt_body_recorded") is False
                and trace_packet.get("auth_header_recorded") is False
            ),
            "env_codex_home_is_temp": temp_root_resolved in env_codex_home.parents,
            "env_home_is_temp": temp_root_resolved in env_home.parents,
            "workdir_is_temp": temp_root_resolved in work.resolve().parents,
            "command_workdir_is_temp": temp_root_resolved in Path(str(work)).resolve().parents,
            "command_uses_stdin_dash": command[-1] == "-",
            "command_json_mode": "--json" in command,
            "command_output_file_is_temp": temp_root_resolved in last_message.resolve().parents,
            "current_codex_home_used": env_codex_home == current_codex_home,
            "prompt_hash": prompt_hash,
            "final_message": final_message,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "duration_seconds": round(time.time() - started, 3),
            "warning_classes": warning_classes,
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
            "temp_root_removed": not tmp_root.exists(),
            "cleanup_error": cleanup_error,
            "refresh_packet": self.status_payload(),
            "transcript": self.transcript_payload(),
            "secret_value_recorded": False,
        }


def run_process_isolation_proof(prompt: str, model_id: str = DEFAULT_MODEL) -> dict[str, Any]:
    session = OperatorSurfaceSession()
    before = protected_snapshot()
    result = session.run_prompt({"prompt": prompt, "model_id": model_id})
    after = protected_snapshot()
    comparisons = compare_snapshots(before, after)
    return {
        "captured_at_utc": utc_now(),
        "run_result": result,
        "transcript": session.transcript_payload(),
        "protected_pre_snapshot": before,
        "protected_post_snapshot": after,
        "comparisons": comparisons,
        "protected_surfaces_unchanged": protected_surfaces_unchanged(comparisons),
        "tmp_root_removed": bool(result.get("temp_root_removed")),
        "secret_value_recorded": False,
    }
