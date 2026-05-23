# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Safe Codex Operator surface adapter for WBP web integration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
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

    def run_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
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
        (codex_home / "config.toml").write_text(
            build_codex_config(endpoint=self.config.endpoint, model_id=selected_model),
            encoding="utf-8",
        )
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
            stderr = process.stderr
        except OSError as exc:
            exit_code = 127
            stderr = f"{type(exc).__name__}: {exc}"
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stderr = exc.stderr or ""
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
        return {
            "status": "ok" if ok else "failed",
            "machine_error_code": "OK" if ok else "ENGINE_PROMPT_FAILED",
            "human_message": "Codex Operator prompt completed." if ok else "Codex Operator prompt failed.",
            "selected_model": selected_model,
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
