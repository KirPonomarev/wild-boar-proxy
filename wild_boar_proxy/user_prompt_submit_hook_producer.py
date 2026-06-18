# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import struct
import sys
import tempfile
import time
import tomllib
from typing import Any

from .command_effects import EFFECT_MUTATE, EFFECT_PROBE, EFFECT_READ, EFFECT_REPAIR
from .core import packets
from .real_custom_codex_hook_proof import (
    ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
    ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
    build_user_prompt_submit_hook_ledger,
    runtime_context_digest,
)
from .router_hook_entry import (
    HOOK_SURFACE_USER_PROMPT_SUBMIT,
    RUNTIME_CONTEXT_FILENAME,
    _safe_text,
    build_router_hook_entry_packet,
    load_runtime_context_packet,
    runtime_context_path,
)
from .runtime import RuntimePaths, write_executable_text_atomic, write_json_atomic, write_text_atomic


HOOK_INSTALL_PACKET_KIND = "wbp_user_prompt_submit_hook_install"
HOOK_READINESS_PACKET_KIND = "wbp_user_prompt_submit_hook_readiness"
HOOK_PRODUCER_RUN_PACKET_KIND = "wbp_user_prompt_submit_hook_producer_run"
HOOK_TRUST_REPAIR_PACKET_KIND = "wbp_user_prompt_submit_hook_trust_repair"

HOOK_STATE_READY = "HOOK_READY"
HOOK_STATE_RAN_SYNTHETIC = "HOOK_RAN_SYNTHETIC"
HOOK_STATE_RAN_CODEX_UNPROVEN = "HOOK_RAN_CODEX_UNPROVEN"
HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN = "HOOK_RAN_CUSTOM_CODEX_PROVEN"
HOOK_STATE_BLOCKED_TRUST_REQUIRED = "HOOK_BLOCKED_TRUST_REQUIRED"
HOOK_STATE_READY_TRUSTED = "HOOK_READY_TRUSTED"

HOOK_CONFIG_OK = "OK"
HOOK_CONFIG_NOT_INSTALLED = "WBP_USER_PROMPT_SUBMIT_HOOK_CONFIG_NOT_INSTALLED"
HOOK_CONFIG_DISABLED = "WBP_USER_PROMPT_SUBMIT_HOOK_DISABLED"
HOOK_CONFIG_MISMATCH = "WBP_USER_PROMPT_SUBMIT_HOOK_CONFIG_MISMATCH"
HOOK_BLOCKED_TRUST_REQUIRED = "WBP_USER_PROMPT_SUBMIT_HOOK_BLOCKED_TRUST_REQUIRED"
HOOK_CURRENT_HASH_UNAVAILABLE = "WBP_USER_PROMPT_SUBMIT_HOOK_CURRENT_HASH_UNAVAILABLE"
HOOK_EVENT_INVALID = "WBP_USER_PROMPT_SUBMIT_HOOK_EVENT_INVALID"
HOOK_RUNTIME_CONTEXT_INVALID = "WBP_USER_PROMPT_SUBMIT_RUNTIME_CONTEXT_INVALID"
HOOK_TRUST_REPAIR_BLOCKED = "WBP_USER_PROMPT_SUBMIT_HOOK_TRUST_REPAIR_BLOCKED"

HOOKS_JSON_FILENAME = "hooks.json"
HOOK_SCRIPT_RELATIVE_PATH = "wbp-hooks/user_prompt_submit_hook.sh"
HOOK_LEDGER_RELATIVE_PATH = "managed/router-hook/user-prompt-submit-ledger.json"
HOOK_STATUS_MESSAGE = "WBP routing ledger"
HOOK_TIMEOUT_SECONDS = 30
CODEX_APP_SERVER_BIN_ENV = "WBP_CODEX_APP_SERVER_BIN"
CODEX_BIN_ENV = "WBP_CODEX_BIN"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json_digest(value: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(
            dict(value),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _hex_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text):
        return text
    return ""


def _valid_prefixed_sha256(value: object) -> str:
    text = _safe_text(value, limit=80)
    if (
        text.startswith("sha256:")
        and len(text) == len("sha256:") + 64
        and all(char in "0123456789abcdef" for char in text.removeprefix("sha256:"))
    ):
        return text
    return ""


def _path_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def hook_script_path(paths: RuntimePaths) -> Path:
    return paths.profile_dir / HOOK_SCRIPT_RELATIVE_PATH


def hooks_json_path(paths: RuntimePaths) -> Path:
    return paths.profile_dir / HOOKS_JSON_FILENAME


def hook_ledger_path(paths: RuntimePaths) -> Path:
    return paths.profile_dir / HOOK_LEDGER_RELATIVE_PATH


def hook_command_for_paths(paths: RuntimePaths) -> str:
    return f"/bin/sh {shlex.quote(str(hook_script_path(paths)))}"


def build_hook_definition(command: str) -> dict[str, Any]:
    return {
        "type": "command",
        "command": command,
        "timeout": HOOK_TIMEOUT_SECONDS,
        "statusMessage": HOOK_STATUS_MESSAGE,
    }


def hook_definition_digest(command: str) -> str:
    return _canonical_json_digest(build_hook_definition(command))


def hook_trust_key_for_paths(paths: RuntimePaths) -> str:
    return f"{hooks_json_path(paths)}:user_prompt_submit:0:0"


def expected_hook_trusted_hash(command: str) -> str:
    return "sha256:" + hook_definition_digest(command)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _codex_app_server_binary() -> Path | None:
    candidates = [
        os.environ.get(CODEX_APP_SERVER_BIN_ENV, ""),
        os.environ.get(CODEX_BIN_ENV, ""),
        str(
            Path.home()
            / "Applications"
            / "Codex WBP Clean.app"
            / "Contents"
            / "Resources"
            / "codex"
        ),
        "/Applications/Codex.app/Contents/Resources/codex",
        shutil.which("codex") or "",
    ]
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _websocket_send_json(sock: socket.socket, payload: Mapping[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    header = bytearray([0x81])
    if len(body) < 126:
        header.append(0x80 | len(body))
    elif len(body) < 65536:
        header += bytes([0x80 | 126]) + struct.pack("!H", len(body))
    else:
        header += bytes([0x80 | 127]) + struct.pack("!Q", len(body))
    mask = os.urandom(4)
    masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))
    sock.sendall(bytes(header) + mask + masked)


def _websocket_recv_json(sock: socket.socket, *, timeout_seconds: float) -> dict[str, Any]:
    sock.settimeout(timeout_seconds)
    first = sock.recv(2)
    if len(first) != 2:
        return {}
    opcode = first[0] & 0x0F
    if opcode == 0x8:
        return {}
    masked = bool(first[1] & 0x80)
    length = first[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv(8))[0]
    mask = sock.recv(4) if masked else b""
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            return {}
        body += chunk
    if masked:
        body = bytes(byte ^ mask[index % 4] for index, byte in enumerate(body))
    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _websocket_upgrade(sock: socket.socket, *, timeout_seconds: float) -> bool:
    sock.settimeout(timeout_seconds)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        "GET / HTTP/1.1\r\n"
        "Host: localhost\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    ).encode("ascii")
    sock.sendall(request)
    response = b""
    while b"\r\n\r\n" not in response and len(response) < 8192:
        chunk = sock.recv(1024)
        if not chunk:
            break
        response += chunk
    return b" 101 " in response or response.startswith(b"HTTP/1.1 101")


def _extract_hook_current_hash(
    response: Mapping[str, Any],
    *,
    trust_key: str,
    command: str,
) -> tuple[str, str]:
    result = response.get("result")
    data = result.get("data") if isinstance(result, Mapping) else None
    if not isinstance(data, list):
        return "", ""
    for entry in data:
        if not isinstance(entry, Mapping):
            continue
        hooks = entry.get("hooks")
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, Mapping):
                continue
            if _safe_text(hook.get("key"), limit=2000) != trust_key:
                continue
            if _safe_text(hook.get("command"), limit=4000) != command:
                continue
            return (
                _valid_prefixed_sha256(hook.get("currentHash")),
                _safe_text(hook.get("trustStatus"), limit=32),
            )
    return "", ""


def _probe_codex_hook_current_hash(
    *,
    paths: RuntimePaths,
    command: str,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "codex_hook_current_hash_probe_attempted": False,
        "codex_hook_current_hash_available": False,
        "codex_hook_current_hash_valid": False,
        "codex_hook_current_hash": "",
        "codex_hook_current_hash_source": "",
        "codex_hook_trust_status_from_app_server": "",
        "codex_hook_current_hash_error_code": "",
    }

    codex_bin = _codex_app_server_binary()
    if codex_bin is None:
        metadata["codex_hook_current_hash_error_code"] = "codex_app_server_binary_missing"
        return metadata

    trust_key = hook_trust_key_for_paths(paths)
    temp_dir = tempfile.mkdtemp(prefix="wbp-hook-", dir="/tmp")
    socket_name = "hooks.sock"
    socket_path = Path(temp_dir) / socket_name
    env = os.environ.copy()
    env["CODEX_HOME"] = str(paths.profile_dir)
    env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
    env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
    env["WBP_CONFIG_TOML"] = str(paths.config_toml)
    process: subprocess.Popen[bytes] | None = None
    metadata["codex_hook_current_hash_probe_attempted"] = True
    try:
        process = subprocess.Popen(
            [str(codex_bin), "app-server", "--listen", f"unix://{socket_name}"],
            cwd=temp_dir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if socket_path.exists():
                break
            if process.poll() is not None:
                metadata["codex_hook_current_hash_error_code"] = "codex_app_server_exited"
                return metadata
            time.sleep(0.05)
        if not socket_path.exists():
            metadata["codex_hook_current_hash_error_code"] = "codex_app_server_socket_timeout"
            return metadata
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            if not _websocket_upgrade(sock, timeout_seconds=2.0):
                metadata["codex_hook_current_hash_error_code"] = "websocket_upgrade_failed"
                return metadata
            _websocket_send_json(
                sock,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {"name": "wbp-hook-current-hash", "version": "0"},
                        "capabilities": None,
                    },
                },
            )
            _websocket_send_json(
                sock,
                {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            )
            _websocket_send_json(
                sock,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "hooks/list",
                    "params": {"cwds": [str(_repo_root())]},
                },
            )
            while time.monotonic() < deadline:
                response = _websocket_recv_json(sock, timeout_seconds=2.0)
                if response.get("id") != 2:
                    continue
                current_hash, trust_status = _extract_hook_current_hash(
                    response,
                    trust_key=trust_key,
                    command=command,
                )
                if not current_hash:
                    metadata["codex_hook_current_hash_error_code"] = "hook_not_listed_by_app_server"
                    return metadata
                metadata.update(
                    {
                        "codex_hook_current_hash_available": True,
                        "codex_hook_current_hash_valid": True,
                        "codex_hook_current_hash": current_hash,
                        "codex_hook_current_hash_source": "codex_app_server_hooks_list",
                        "codex_hook_trust_status_from_app_server": trust_status,
                    }
                )
                return metadata
            metadata["codex_hook_current_hash_error_code"] = "hooks_list_timeout"
            return metadata
    except (OSError, subprocess.SubprocessError, TimeoutError, socket.timeout):
        metadata["codex_hook_current_hash_error_code"] = "codex_app_server_probe_failed"
        return metadata
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        shutil.rmtree(temp_dir, ignore_errors=True)


def build_hook_script_text(
    *,
    paths: RuntimePaths,
    hook_config_sha256: str,
) -> str:
    python_executable = shlex.quote(sys.executable)
    repo_root = shlex.quote(str(_repo_root()))
    profile_dir = shlex.quote(str(paths.profile_dir))
    managed_dir = shlex.quote(str(paths.managed_dir))
    config_toml = shlex.quote(str(paths.config_toml))
    ledger_file = shlex.quote(str(hook_ledger_path(paths)))
    runtime_context_file = shlex.quote(
        str(runtime_context_path(paths=paths, runtime_context_file=None))
    )
    hook_hash = shlex.quote(hook_config_sha256)
    return "\n".join(
        [
            "#!/bin/sh",
            "set -eu",
            f"export WBP_PROFILE_DIR={profile_dir}",
            f"export WBP_MANAGED_DIR={managed_dir}",
            f"export WBP_CONFIG_TOML={config_toml}",
            f"export PYTHONPATH={repo_root}:\"${{PYTHONPATH:-}}\"",
            "exec "
            f"{python_executable} -m wild_boar_proxy.user_prompt_submit_hook_producer "
            "run-hook "
            f"--ledger-file {ledger_file} "
            f"--runtime-context-file {runtime_context_file} "
            f"--trusted-hook-config-sha256 {hook_hash} "
            f"--loaded-hook-config-sha256 {hook_hash} "
            f"--origin-state {ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN} "
            "--quiet",
        ]
    )


def _read_hooks_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata: dict[str, Any] = {
        "hooks_json_present": path.exists(),
        "hooks_json_read": False,
        "hooks_json_valid_json": False,
        "hooks_json_mapping": False,
        "hooks_json_path_recorded": False,
        "hooks_json_error_code": "",
    }
    if not path.exists():
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata["hooks_json_error_code"] = "hooks_json_invalid"
        return {}, metadata
    metadata["hooks_json_read"] = True
    metadata["hooks_json_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["hooks_json_error_code"] = "hooks_json_not_mapping"
        return {}, metadata
    metadata["hooks_json_mapping"] = True
    return dict(parsed), metadata


def _is_wbp_user_prompt_hook_group(group: object) -> bool:
    if not isinstance(group, Mapping):
        return False
    handlers = group.get("hooks")
    if not isinstance(handlers, list):
        return False
    for handler in handlers:
        if not isinstance(handler, Mapping):
            continue
        command = _safe_text(handler.get("command"), limit=2000)
        status = _safe_text(handler.get("statusMessage"), limit=200)
        if status == HOOK_STATUS_MESSAGE or "user_prompt_submit_hook_producer" in command:
            return True
    return False


def merge_wbp_hook_definition(
    existing_document: Mapping[str, Any] | None,
    *,
    command: str,
) -> dict[str, Any]:
    document = dict(existing_document or {})
    hooks = document.get("hooks")
    if not isinstance(hooks, Mapping):
        hooks = {}
    merged_hooks = dict(hooks)
    existing_groups = merged_hooks.get("UserPromptSubmit")
    if not isinstance(existing_groups, list):
        existing_groups = []
    kept_groups = [
        group
        for group in existing_groups
        if not _is_wbp_user_prompt_hook_group(group)
    ]
    kept_groups.append({"hooks": [build_hook_definition(command)]})
    merged_hooks["UserPromptSubmit"] = kept_groups
    document["hooks"] = merged_hooks
    return document


def _features_hooks_disabled(config_toml: Path) -> tuple[bool, dict[str, Any]]:
    metadata: dict[str, Any] = {
        "config_toml_present": config_toml.exists(),
        "config_toml_read": False,
        "config_toml_valid_toml": False,
        "config_toml_path_recorded": False,
        "hooks_feature_disabled": False,
        "hooks_feature_source": "",
    }
    if not config_toml.exists():
        return False, metadata
    try:
        parsed = tomllib.loads(config_toml.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False, metadata
    metadata["config_toml_read"] = True
    metadata["config_toml_valid_toml"] = True
    features = parsed.get("features")
    if isinstance(features, Mapping):
        if features.get("hooks") is False:
            metadata["hooks_feature_disabled"] = True
            metadata["hooks_feature_source"] = "features.hooks"
        elif features.get("codex_hooks") is False:
            metadata["hooks_feature_disabled"] = True
            metadata["hooks_feature_source"] = "features.codex_hooks"
    return bool(metadata["hooks_feature_disabled"]), metadata


def _codex_hook_trust_state(
    *,
    config_toml: Path,
    hooks_json: Path,
    hooks_document: Mapping[str, Any],
    command: str,
    codex_hook_current_hash: str,
) -> dict[str, Any]:
    current_hash = _valid_prefixed_sha256(codex_hook_current_hash)
    metadata: dict[str, Any] = {
        "codex_hook_trust_state_present": False,
        "codex_hook_trust_state_matches_hook_slot": False,
        "codex_hook_trusted_hash_present": False,
        "codex_hook_trusted_hash_valid": False,
        "codex_hook_trusted_hash_matches_hook_definition": False,
        "codex_hook_trusted_hash_matches_current_hash": False,
        "codex_hook_trusted_hash_recorded": False,
        "codex_hook_trusted_by_profile_state": False,
    }
    try:
        parsed = tomllib.loads(config_toml.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return metadata
    hooks = parsed.get("hooks")
    state = hooks.get("state") if isinstance(hooks, Mapping) else None
    if not isinstance(state, Mapping):
        return metadata
    metadata["codex_hook_trust_state_present"] = True

    hook_groups = hooks_document.get("hooks")
    event_groups = hook_groups.get("UserPromptSubmit") if isinstance(hook_groups, Mapping) else None
    if not isinstance(event_groups, list):
        return metadata
    for group_index, group in enumerate(event_groups):
        if not isinstance(group, Mapping):
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            continue
        for hook_index, handler in enumerate(handlers):
            if not isinstance(handler, Mapping):
                continue
            if _safe_text(handler.get("command"), limit=2000) != command:
                continue
            trust_key = f"{hooks_json}:user_prompt_submit:{group_index}:{hook_index}"
            trust_entry = state.get(trust_key)
            if not isinstance(trust_entry, Mapping):
                continue
            metadata["codex_hook_trust_state_matches_hook_slot"] = True
            expected_trusted_hash = "sha256:" + _canonical_json_digest(handler)
            trusted_hash = _safe_text(trust_entry.get("trusted_hash"), limit=80)
            trusted_hash_valid = bool(_valid_prefixed_sha256(trusted_hash))
            trusted_hash_matches = trusted_hash_valid and trusted_hash == expected_trusted_hash
            current_hash_matches = bool(
                trusted_hash_valid and current_hash and trusted_hash == current_hash
            )
            metadata["codex_hook_trusted_hash_present"] = bool(trusted_hash)
            metadata["codex_hook_trusted_hash_valid"] = trusted_hash_valid
            metadata["codex_hook_trusted_hash_matches_hook_definition"] = trusted_hash_matches
            metadata["codex_hook_trusted_hash_matches_current_hash"] = current_hash_matches
            metadata["codex_hook_trusted_by_profile_state"] = current_hash_matches
            return metadata
    return metadata


def _toml_table_header(line: str) -> str:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return ""
    return stripped


def _remove_exact_hook_trust_state_section(config_text: str, *, trust_key: str) -> str:
    target_header = f"[hooks.state.{json.dumps(trust_key)}]"
    output: list[str] = []
    skipping = False
    for line in config_text.splitlines():
        header = _toml_table_header(line)
        if header:
            skipping = header == target_header
        if not skipping:
            output.append(line)
    return "\n".join(output).rstrip() + ("\n" if output else "")


def _append_exact_hook_trust_state(config_text: str, *, trust_key: str, trusted_hash: str) -> str:
    base = _remove_exact_hook_trust_state_section(config_text, trust_key=trust_key).rstrip()
    trust_section = (
        f"[hooks.state.{json.dumps(trust_key)}]\n"
        f"trusted_hash = {json.dumps(trusted_hash)}\n"
    )
    return (base + "\n\n" if base else "") + trust_section


def _find_hook_definition(document: Mapping[str, Any], *, command: str) -> dict[str, Any]:
    hooks = document.get("hooks")
    if not isinstance(hooks, Mapping):
        return {}
    groups = hooks.get("UserPromptSubmit")
    if not isinstance(groups, list):
        return {}
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        handlers = group.get("hooks")
        if not isinstance(handlers, list):
            continue
        for handler in handlers:
            if not isinstance(handler, Mapping):
                continue
            if _safe_text(handler.get("command"), limit=2000) == command:
                return dict(handler)
    return {}


def build_user_prompt_submit_install_packet(
    *,
    paths: RuntimePaths,
    apply: bool = False,
) -> dict[str, Any]:
    command = hook_command_for_paths(paths)
    config_sha256 = hook_definition_digest(command)
    script_text = build_hook_script_text(paths=paths, hook_config_sha256=config_sha256)
    current_document, hooks_metadata = _read_hooks_json(hooks_json_path(paths))
    merged_document = merge_wbp_hook_definition(current_document, command=command)
    hooks_json_sha256 = _canonical_json_digest(merged_document)
    script_sha256 = _sha256_text(script_text)

    changed_files: list[str] = []
    if apply:
        write_executable_text_atomic(hook_script_path(paths), script_text)
        write_json_atomic(hooks_json_path(paths), merged_document)
        changed_files = [str(hook_script_path(paths)), str(hooks_json_path(paths))]

    extra = {
        **hooks_metadata,
        "schema_version": 1,
        "packet_kind": HOOK_INSTALL_PACKET_KIND,
        "hook_event_name": "UserPromptSubmit",
        "hook_install_apply": bool(apply),
        "hook_config_present": bool(apply or hooks_metadata["hooks_json_present"]),
        "hook_definition_prepared": True,
        "hook_definition_digest": config_sha256,
        "hook_config_digest_bound": True,
        "hooks_json_sha256": hooks_json_sha256,
        "hook_script_prepared": True,
        "hook_script_sha256": script_sha256,
        "hook_command_path_resolves": (
            hook_script_path(paths).exists() if apply else False
        ),
        "hook_enabled": True,
        "hook_trust_requirement_declared": True,
        "hook_trusted": False,
        "hook_readiness_state": (
            HOOK_STATE_BLOCKED_TRUST_REQUIRED if apply else HOOK_STATE_READY
        ),
        "hook_requires_manual_review": bool(apply),
        "hook_config_path_recorded": False,
        "hook_script_path_recorded": False,
        "ledger_file_path_recorded": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "state_written": bool(apply),
        "product_ready": False,
        "changed_files": changed_files,
    }
    return packets.build_command_packet(
        ok=True,
        human_message=(
            "WBP installed UserPromptSubmit hook producer."
            if apply
            else "WBP prepared UserPromptSubmit hook producer install plan."
        ),
        machine_error_code=HOOK_CONFIG_OK,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=changed_files,
        effect=EFFECT_MUTATE if apply else EFFECT_READ,
        extra=extra,
    )


def build_user_prompt_submit_readiness_packet(
    *,
    paths: RuntimePaths,
    codex_hook_current_hash: str = "",
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    command = hook_command_for_paths(paths)
    expected_digest = hook_definition_digest(command)
    document, hooks_metadata = _read_hooks_json(hooks_json_path(paths))
    hooks_disabled, config_metadata = _features_hooks_disabled(paths.config_toml)
    hook_definition = _find_hook_definition(document, command=command)
    current_hash_metadata = (
        {
            "codex_hook_current_hash_probe_attempted": False,
            "codex_hook_current_hash_available": bool(
                _valid_prefixed_sha256(codex_hook_current_hash)
            ),
            "codex_hook_current_hash_valid": bool(
                _valid_prefixed_sha256(codex_hook_current_hash)
            ),
            "codex_hook_current_hash": _valid_prefixed_sha256(
                codex_hook_current_hash
            ),
            "codex_hook_current_hash_source": "argument",
            "codex_hook_trust_status_from_app_server": "",
            "codex_hook_current_hash_error_code": "",
        }
        if _valid_prefixed_sha256(codex_hook_current_hash)
        else _probe_codex_hook_current_hash(paths=paths, command=command)
        if probe_codex_app_server
        else {
            "codex_hook_current_hash_probe_attempted": False,
            "codex_hook_current_hash_available": False,
            "codex_hook_current_hash_valid": False,
            "codex_hook_current_hash": "",
            "codex_hook_current_hash_source": "",
            "codex_hook_trust_status_from_app_server": "",
            "codex_hook_current_hash_error_code": "codex_current_hash_not_requested",
        }
    )
    trust_metadata = _codex_hook_trust_state(
        config_toml=paths.config_toml,
        hooks_json=hooks_json_path(paths),
        hooks_document=document,
        command=command,
        codex_hook_current_hash=str(
            current_hash_metadata.get("codex_hook_current_hash", "")
        ),
    )
    current_hash_source = str(
        current_hash_metadata.get("codex_hook_current_hash_source", "")
    )
    app_server_trust_status = str(
        current_hash_metadata.get("codex_hook_trust_status_from_app_server", "")
    )
    app_server_trust_status_required = (
        current_hash_source == "codex_app_server_hooks_list"
    )
    app_server_trust_status_trusted = app_server_trust_status == "trusted"
    loaded_digest = (
        _canonical_json_digest(hook_definition) if hook_definition else ""
    )
    script = hook_script_path(paths)
    script_present = script.exists()
    script_executable = bool(script_present and os.access(script, os.X_OK))
    hook_config_present = bool(hooks_metadata["hooks_json_present"] and hook_definition)
    digest_bound = bool(loaded_digest and loaded_digest == expected_digest)

    blocking_reasons: list[str] = []
    if hooks_disabled:
        blocking_reasons.append("hooks_feature_disabled")
    if not hooks_metadata["hooks_json_present"]:
        blocking_reasons.append("hooks_json_missing")
    elif not hooks_metadata["hooks_json_valid_json"]:
        blocking_reasons.append("hooks_json_invalid")
    if not hook_definition:
        blocking_reasons.append("user_prompt_submit_hook_definition_missing")
    if hook_definition and not digest_bound:
        blocking_reasons.append("hook_config_digest_mismatch")
    if not script_present:
        blocking_reasons.append("hook_script_missing")
    elif not script_executable:
        blocking_reasons.append("hook_script_not_executable")
    hook_trusted_by_profile_state = (
        trust_metadata["codex_hook_trusted_by_profile_state"] is True
    )
    hook_trusted = bool(
        hook_trusted_by_profile_state
        and (
            not app_server_trust_status_required
            or app_server_trust_status_trusted
        )
    )
    current_hash_available = current_hash_metadata["codex_hook_current_hash_available"] is True
    if not blocking_reasons and not current_hash_available:
        blocking_reasons.append("codex_hook_current_hash_unavailable")
    if (
        not blocking_reasons
        and hook_trusted_by_profile_state
        and app_server_trust_status_required
        and not app_server_trust_status_trusted
    ):
        blocking_reasons.append("codex_hook_app_server_trust_status_not_trusted")
    if not blocking_reasons and not hook_trusted:
        blocking_reasons.append("hook_trust_review_required")

    if hooks_disabled:
        machine_error_code = HOOK_CONFIG_DISABLED
    elif not hook_config_present or not script_present:
        machine_error_code = HOOK_CONFIG_NOT_INSTALLED
    elif not digest_bound or not script_executable:
        machine_error_code = HOOK_CONFIG_MISMATCH
    elif not current_hash_available:
        machine_error_code = HOOK_CURRENT_HASH_UNAVAILABLE
    elif hook_trusted:
        machine_error_code = HOOK_CONFIG_OK
    else:
        machine_error_code = HOOK_BLOCKED_TRUST_REQUIRED
    ok = machine_error_code == HOOK_CONFIG_OK

    extra = {
        **hooks_metadata,
        **config_metadata,
        **current_hash_metadata,
        **trust_metadata,
        "schema_version": 1,
        "packet_kind": HOOK_READINESS_PACKET_KIND,
        "hook_event_name": "UserPromptSubmit",
        "hook_config_present": hook_config_present,
        "hook_enabled": not hooks_disabled,
        "hook_command_path_resolves": script_present,
        "hook_script_executable": script_executable,
        "hook_script_sha256": _path_sha256(script),
        "expected_hook_definition_sha256": expected_digest,
        "loaded_hook_definition_sha256": loaded_digest,
        "hook_config_digest_bound": digest_bound,
        "hook_trust_requirement_declared": True,
        "codex_hook_app_server_trust_status_required": app_server_trust_status_required,
        "codex_hook_app_server_trust_status_trusted": app_server_trust_status_trusted,
        "hook_trusted": hook_trusted,
        "hook_requires_manual_review": bool(
            hook_config_present and current_hash_available and not hook_trusted
        ),
        "hook_readiness_state": (
            HOOK_STATE_READY_TRUSTED
            if ok
            else "HOOK_BLOCKED_CURRENT_HASH_UNAVAILABLE"
            if machine_error_code == HOOK_CURRENT_HASH_UNAVAILABLE
            else HOOK_STATE_BLOCKED_TRUST_REQUIRED
            if machine_error_code == HOOK_BLOCKED_TRUST_REQUIRED
            else "HOOK_NOT_READY"
        ),
        "hook_config_path_recorded": False,
        "hook_script_path_recorded": False,
        "ledger_file_path_recorded": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "state_written": False,
        "product_ready": False,
        "blocking_reasons": blocking_reasons,
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP UserPromptSubmit hook is installed and trusted by the Custom Codex profile."
            if ok
            else "WBP UserPromptSubmit hook requires operator review/trust before green readiness."
        ),
        machine_error_code=machine_error_code,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "user_action",
        changed_files=[],
        effect=EFFECT_PROBE,
        extra=extra,
    )


def build_user_prompt_submit_trust_repair_packet(
    *,
    paths: RuntimePaths,
    apply: bool = False,
    codex_hook_current_hash: str = "",
    probe_codex_app_server: bool = False,
) -> dict[str, Any]:
    command = hook_command_for_paths(paths)
    expected_digest = hook_definition_digest(command)
    current_hash_metadata = (
        {
            "codex_hook_current_hash_probe_attempted": False,
            "codex_hook_current_hash_available": bool(
                _valid_prefixed_sha256(codex_hook_current_hash)
            ),
            "codex_hook_current_hash_valid": bool(
                _valid_prefixed_sha256(codex_hook_current_hash)
            ),
            "codex_hook_current_hash": _valid_prefixed_sha256(
                codex_hook_current_hash
            ),
            "codex_hook_current_hash_source": "argument",
            "codex_hook_trust_status_from_app_server": "",
            "codex_hook_current_hash_error_code": "",
        }
        if _valid_prefixed_sha256(codex_hook_current_hash)
        else _probe_codex_hook_current_hash(paths=paths, command=command)
        if probe_codex_app_server
        else {
            "codex_hook_current_hash_probe_attempted": False,
            "codex_hook_current_hash_available": False,
            "codex_hook_current_hash_valid": False,
            "codex_hook_current_hash": "",
            "codex_hook_current_hash_source": "",
            "codex_hook_trust_status_from_app_server": "",
            "codex_hook_current_hash_error_code": "codex_current_hash_not_requested",
        }
    )
    expected_trusted_hash = str(current_hash_metadata.get("codex_hook_current_hash", ""))
    document, hooks_metadata = _read_hooks_json(hooks_json_path(paths))
    hook_definition = _find_hook_definition(document, command=command)
    loaded_digest = _canonical_json_digest(hook_definition) if hook_definition else ""
    script = hook_script_path(paths)
    script_present = script.exists()
    script_executable = bool(script_present and os.access(script, os.X_OK))
    trust_key = hook_trust_key_for_paths(paths)

    precondition_failures: list[str] = []
    if not hooks_metadata["hooks_json_present"]:
        precondition_failures.append("hooks_json_missing")
    elif not hooks_metadata["hooks_json_valid_json"]:
        precondition_failures.append("hooks_json_invalid")
    if not hook_definition:
        precondition_failures.append("user_prompt_submit_hook_definition_missing")
    if hook_definition and loaded_digest != expected_digest:
        precondition_failures.append("hook_config_digest_mismatch")
    if not script_present:
        precondition_failures.append("hook_script_missing")
    elif not script_executable:
        precondition_failures.append("hook_script_not_executable")
    if not expected_trusted_hash:
        precondition_failures.append("codex_hook_current_hash_unavailable")

    before_trust = _codex_hook_trust_state(
        config_toml=paths.config_toml,
        hooks_json=hooks_json_path(paths),
        hooks_document=document,
        command=command,
        codex_hook_current_hash=expected_trusted_hash,
    )
    already_trusted = before_trust["codex_hook_trusted_by_profile_state"] is True
    changed_files: list[str] = []
    repair_error = ""
    state_written = False
    if apply and not precondition_failures and not already_trusted:
        try:
            existing_text = (
                paths.config_toml.read_text(encoding="utf-8")
                if paths.config_toml.exists()
                else ""
            )
            repaired_text = _append_exact_hook_trust_state(
                existing_text,
                trust_key=trust_key,
                trusted_hash=expected_trusted_hash,
            )
            write_text_atomic(paths.config_toml, repaired_text)
            changed_files = [str(paths.config_toml)]
            state_written = True
        except OSError:
            repair_error = "config_toml_write_failed"

    after_trust = _codex_hook_trust_state(
        config_toml=paths.config_toml,
        hooks_json=hooks_json_path(paths),
        hooks_document=document,
        command=command,
        codex_hook_current_hash=expected_trusted_hash,
    )
    repaired_or_already = after_trust["codex_hook_trusted_by_profile_state"] is True
    blocking_reasons = sorted(
        set(
            precondition_failures
            + ([repair_error] if repair_error else [])
            + ([] if (not apply or repaired_or_already) else ["hook_trust_repair_not_applied"])
        )
    )
    ok = not blocking_reasons
    extra = {
        **hooks_metadata,
        **current_hash_metadata,
        "schema_version": 1,
        "packet_kind": HOOK_TRUST_REPAIR_PACKET_KIND,
        "hook_event_name": "UserPromptSubmit",
        "hook_trust_repair_apply": bool(apply),
        "hook_trust_repair_planned": True,
        "hook_config_present": bool(hooks_metadata["hooks_json_present"] and hook_definition),
        "hook_command_path_resolves": script_present,
        "hook_script_executable": script_executable,
        "expected_hook_definition_sha256": expected_digest,
        "loaded_hook_definition_sha256": loaded_digest,
        "hook_config_digest_bound": bool(loaded_digest and loaded_digest == expected_digest),
        "expected_hook_trusted_hash_sha256": expected_trusted_hash.removeprefix("sha256:"),
        "codex_hook_trust_state_present_before": before_trust["codex_hook_trust_state_present"],
        "codex_hook_trust_state_matches_hook_slot_before": before_trust[
            "codex_hook_trust_state_matches_hook_slot"
        ],
        "codex_hook_trusted_hash_valid_before": before_trust[
            "codex_hook_trusted_hash_valid"
        ],
        "codex_hook_trusted_hash_matches_hook_definition_before": before_trust[
            "codex_hook_trusted_hash_matches_hook_definition"
        ],
        "codex_hook_trusted_hash_matches_current_hash_before": before_trust[
            "codex_hook_trusted_hash_matches_current_hash"
        ],
        "codex_hook_trusted_before_repair": already_trusted,
        "codex_hook_trust_state_present_after": after_trust["codex_hook_trust_state_present"],
        "codex_hook_trust_state_matches_hook_slot_after": after_trust[
            "codex_hook_trust_state_matches_hook_slot"
        ],
        "codex_hook_trusted_hash_valid_after": after_trust[
            "codex_hook_trusted_hash_valid"
        ],
        "codex_hook_trusted_hash_matches_hook_definition_after": after_trust[
            "codex_hook_trusted_hash_matches_hook_definition"
        ],
        "codex_hook_trusted_hash_matches_current_hash_after": after_trust[
            "codex_hook_trusted_hash_matches_current_hash"
        ],
        "codex_hook_trusted_after_repair": repaired_or_already,
        "hook_trusted": repaired_or_already,
        "state_written": state_written,
        "changed_files": changed_files,
        "blocking_reasons": blocking_reasons,
        "hook_config_path_recorded": False,
        "hook_script_path_recorded": False,
        "ledger_file_path_recorded": False,
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "api_lane_called": False,
        "dispatch_attempted": False,
        "handoff_file_written": False,
        "product_ready": False,
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP repaired the UserPromptSubmit hook trust state."
            if ok and apply
            else "WBP prepared a UserPromptSubmit hook trust repair."
            if ok
            else "WBP blocked UserPromptSubmit hook trust repair."
        ),
        machine_error_code=HOOK_CONFIG_OK if ok else HOOK_TRUST_REPAIR_BLOCKED,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=changed_files,
        effect=EFFECT_REPAIR if apply else EFFECT_PROBE,
        extra=extra,
    )


def _load_event_from_text(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = {
        "hook_event_input_present": bool(text.strip()),
        "hook_event_input_valid_json": False,
        "hook_event_input_mapping": False,
        "hook_event_input_text_recorded": False,
    }
    if not text.strip():
        return {}, metadata
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}, metadata
    metadata["hook_event_input_valid_json"] = True
    if not isinstance(parsed, Mapping):
        return {}, metadata
    metadata["hook_event_input_mapping"] = True
    return dict(parsed), metadata


def _event_secret_values(event: Mapping[str, Any]) -> list[str]:
    prompt = event.get("prompt")
    return [prompt] if isinstance(prompt, str) and prompt else []


def _runtime_secret_values(runtime_context: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for route_id in runtime_context.get("allowed_api_route_ids", []):
        if isinstance(route_id, str) and route_id:
            values.append(route_id)
    routes = runtime_context.get("agent_id_to_route")
    if isinstance(routes, Mapping):
        for route_id in routes.values():
            if isinstance(route_id, str) and route_id:
                values.append(route_id)
    return sorted(set(values))


def _event_digest(value: object) -> str:
    text = _safe_text(value, limit=2048)
    return _sha256_text(text) if text else ""


def _event_transport(event_metadata: Mapping[str, Any]) -> str:
    if event_metadata.get("hook_event_stdin_read") is True:
        return "stdin"
    if event_metadata.get("hook_event_file_read") is True:
        return "event_file"
    return "unknown"


def _ps_field(pid: int, field: str) -> str:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", f"{field}="],
            text=True,
            capture_output=True,
            check=False,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _process_info(pid: int) -> tuple[int, str, str] | None:
    parent_pid_text = _ps_field(pid, "ppid")
    executable_path = _ps_field(pid, "comm")
    command = _ps_field(pid, "args")
    if not parent_pid_text or not executable_path:
        return None
    try:
        parent_pid = int(parent_pid_text)
    except ValueError:
        return None
    return parent_pid, executable_path, command


def _path_has_suffix(path: str, suffix: str) -> bool:
    return path == suffix or path.endswith("/" + suffix)


def _command_class(executable_path: str, command: str = "") -> str:
    if _path_has_suffix(
        executable_path,
        "Codex WBP Clean.app/Contents/Resources/codex",
    ) and command.startswith(executable_path + " app-server"):
        return "wbp_clean_app_server"
    if _path_has_suffix(
        executable_path,
        "Codex WBP Clean.app/Contents/MacOS/Codex",
    ):
        return "wbp_clean_app_root"
    if "/Codex WBP Clean.app/Contents/Frameworks/" in executable_path:
        return "wbp_clean_app_helper"
    if _path_has_suffix(executable_path, "Applications/Codex.app/Contents/MacOS/Codex"):
        return "stock_codex_app_root"
    if _path_has_suffix(
        executable_path,
        "Codex.app/Contents/Resources/codex",
    ) and command.startswith(executable_path + " app-server"):
        return "codex_app_server"
    if "wild_boar_proxy.user_prompt_submit_hook_producer" in command:
        return "wbp_hook_producer"
    if "python" in executable_path:
        return "python"
    if "node" in executable_path:
        return "node"
    if (
        executable_path.endswith("/zsh")
        or executable_path.endswith("/bash")
        or executable_path.endswith("/sh")
    ):
        return "shell"
    return "other"


def _hook_parent_process_observation() -> dict[str, Any]:
    classes: list[str] = []
    current_pid = os.getpid()
    pid = current_pid
    for _ in range(12):
        info = _process_info(pid)
        if info is None:
            break
        parent_pid, executable_path, command = info
        classes.append(_command_class(executable_path, command))
        if parent_pid <= 0 or parent_pid == pid:
            break
        pid = parent_pid
    clean_app_class_present = any(item.startswith("wbp_clean_app_") for item in classes)
    clean_app_server_present = "wbp_clean_app_server" in classes
    clean_app_root_present = "wbp_clean_app_root" in classes
    digest = _sha256_text(
        json.dumps(
            {
                "start_pid": current_pid,
                "classes": classes,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    ) if classes else ""
    return {
        "hook_parent_process_chain_observed": bool(classes),
        "hook_parent_process_chain_digest": digest,
        "hook_parent_process_chain_length": len(classes),
        "hook_parent_process_chain_path_proven": bool(classes),
        "hook_parent_process_chain_exact_path_classified": bool(classes),
        "hook_parent_process_chain_custom_wbp_clean_app": clean_app_class_present,
        "hook_parent_process_chain_app_server": clean_app_server_present,
        "hook_parent_process_chain_clean_root": clean_app_root_present,
        "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound": (
            clean_app_class_present
        ),
        "hook_parent_process_chain_app_server_executable_path_bound": (
            clean_app_server_present
        ),
        "hook_parent_process_chain_clean_root_executable_path_bound": (
            clean_app_root_present
        ),
        "hook_parent_process_chain_stock_codex_app": "stock_codex_app_root" in classes,
        "hook_parent_process_chain_classes_digest": _sha256_text(
            ",".join(classes)
        ) if classes else "",
        "hook_parent_process_chain_command_text_substring_only": False,
        "hook_parent_process_raw_lines_recorded": False,
    }


def _producer_state(*, event_name: str, turn_id: str, origin_state: str) -> str:
    if origin_state == ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN:
        if event_name == "UserPromptSubmit" and turn_id:
            return HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN
        return HOOK_STATE_RAN_CODEX_UNPROVEN
    if event_name == "UserPromptSubmit":
        return HOOK_STATE_RAN_CODEX_UNPROVEN
    return HOOK_STATE_RAN_SYNTHETIC


def build_user_prompt_submit_run_packet(
    *,
    event: Mapping[str, Any],
    paths: RuntimePaths,
    ledger_file: Path | None = None,
    runtime_context_file: str | None = None,
    trusted_hook_config_sha256: str = "",
    loaded_hook_config_sha256: str = "",
    origin_state: str = ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
    event_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(event_metadata or {})
    prompt = event.get("prompt")
    prompt_text = prompt if isinstance(prompt, str) else ""
    event_name = _safe_text(event.get("hook_event_name"), limit=80)
    turn_id = _safe_text(event.get("turn_id"), limit=160)
    session_id = _safe_text(event.get("session_id"), limit=160)
    cwd = _safe_text(event.get("cwd"), limit=512)
    admission_run_id = _safe_text(os.environ.get("WBP_ADMISSION_RUN_ID"), limit=512)
    admission_run_id_digest = _event_digest(admission_run_id)
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    secret_values = _event_secret_values(event) + _runtime_secret_values(runtime_context)
    parent_process = _hook_parent_process_observation()

    blocking_reasons: list[str] = []
    if event_name != "UserPromptSubmit":
        blocking_reasons.append("hook_event_name_not_user_prompt_submit")
    if not prompt_text:
        blocking_reasons.append("hook_prompt_missing")
    if not turn_id:
        blocking_reasons.append("turn_id_missing")
    if context_metadata.get("runtime_context_file_read") is not True:
        blocking_reasons.append("runtime_context_file_not_read")
    if context_metadata.get("runtime_context_file_valid_json") is not True:
        blocking_reasons.append("runtime_context_file_json_not_valid")
    if not _hex_sha256(trusted_hook_config_sha256):
        blocking_reasons.append("trusted_hook_config_digest_missing")
    if not _hex_sha256(loaded_hook_config_sha256):
        blocking_reasons.append("loaded_hook_config_digest_missing")
    if (
        _hex_sha256(trusted_hook_config_sha256)
        and _hex_sha256(loaded_hook_config_sha256)
        and trusted_hook_config_sha256 != loaded_hook_config_sha256
    ):
        blocking_reasons.append("hook_config_digest_mismatch")
    if (
        origin_state == ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN
        and _event_transport(metadata) != "stdin"
    ):
        blocking_reasons.append("custom_codex_origin_requires_stdin_transport")

    ok = not blocking_reasons
    effective_origin_state = (
        origin_state if ok else ORIGIN_STATE_SYNTHETIC_HOOK_FLOW
    )
    producer_state = _producer_state(
        event_name=event_name,
        turn_id=turn_id,
        origin_state=effective_origin_state,
    )
    ledger_path = ledger_file or hook_ledger_path(paths)
    ledger_written = False
    if ok:
        entry_packet = build_router_hook_entry_packet(
            prompt_text=prompt_text,
            runtime_context=runtime_context,
            hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
            secret_values=secret_values,
        )
        ledger = build_user_prompt_submit_hook_ledger(
            prompt_digest=_safe_text(entry_packet.get("prompt_digest"), limit=80),
            runtime_context_digest_value=runtime_context_digest(runtime_context),
            origin_state=effective_origin_state,
            thread_digest=_event_digest(session_id),
            turn_digest=_event_digest(turn_id),
            trusted_hook_config_sha256=trusted_hook_config_sha256,
            loaded_hook_config_sha256=loaded_hook_config_sha256,
            hook_config_present=True,
            hook_enabled=True,
            hook_trusted=effective_origin_state == ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
            hook_hash_current=trusted_hook_config_sha256 == loaded_hook_config_sha256,
            hook_runnable=True,
            user_prompt_submit_hook_ran=True,
            hook_ledger_written=True,
            hook_producer_state=producer_state,
            hook_event_digest=_canonical_json_digest(
                {
                    "hook_event_name": event_name,
                    "session_id_digest": _event_digest(session_id),
                    "turn_id_digest": _event_digest(turn_id),
                    "cwd_digest": _event_digest(cwd),
                    "admission_run_id_digest": admission_run_id_digest,
                    "hook_event_transport": _event_transport(metadata),
                }
            ),
            hook_event_transport=_event_transport(metadata),
            session_digest=_event_digest(session_id),
            cwd_digest=_event_digest(cwd),
            admission_run_id_digest=admission_run_id_digest,
            hook_parent_process_chain_digest=str(
                parent_process["hook_parent_process_chain_digest"]
            ),
            hook_parent_process_chain_length=int(
                parent_process["hook_parent_process_chain_length"]
            ),
            hook_parent_process_chain_observed=(
                parent_process["hook_parent_process_chain_observed"] is True
            ),
            hook_parent_process_chain_path_proven=(
                parent_process["hook_parent_process_chain_path_proven"] is True
            ),
            hook_parent_process_chain_exact_path_classified=(
                parent_process["hook_parent_process_chain_exact_path_classified"]
                is True
            ),
            hook_parent_process_chain_custom_wbp_clean_app=(
                parent_process["hook_parent_process_chain_custom_wbp_clean_app"]
                is True
            ),
            hook_parent_process_chain_app_server=(
                parent_process["hook_parent_process_chain_app_server"] is True
            ),
            hook_parent_process_chain_clean_root=(
                parent_process["hook_parent_process_chain_clean_root"] is True
            ),
            hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound=(
                parent_process[
                    "hook_parent_process_chain_custom_wbp_clean_app_executable_path_bound"
                ]
                is True
            ),
            hook_parent_process_chain_app_server_executable_path_bound=(
                parent_process[
                    "hook_parent_process_chain_app_server_executable_path_bound"
                ]
                is True
            ),
            hook_parent_process_chain_clean_root_executable_path_bound=(
                parent_process[
                    "hook_parent_process_chain_clean_root_executable_path_bound"
                ]
                is True
            ),
            hook_parent_process_chain_stock_codex_app=(
                parent_process["hook_parent_process_chain_stock_codex_app"] is True
            ),
            hook_parent_process_chain_command_text_substring_only=(
                parent_process["hook_parent_process_chain_command_text_substring_only"]
                is True
            ),
            hook_trust_source=(
                "codex_non_managed_hook_execution"
                if effective_origin_state == ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN
                else "not_proven"
            ),
        )
        write_json_atomic(ledger_path, ledger)
        ledger_written = True

    extra = {
        **metadata,
        **context_metadata,
        "schema_version": 1,
        "packet_kind": HOOK_PRODUCER_RUN_PACKET_KIND,
        "hook_event_name": event_name,
        "hook_event_name_is_user_prompt_submit": event_name == "UserPromptSubmit",
        "hook_event_transport": _event_transport(metadata),
        "hook_event_transport_stdin": _event_transport(metadata) == "stdin",
        "hook_producer_state": producer_state,
        "origin_state": effective_origin_state,
        "prompt_digest": (
            _safe_text(
                build_router_hook_entry_packet(
                    prompt_text=prompt_text,
                    runtime_context=runtime_context,
                    hook_surface_kind=HOOK_SURFACE_USER_PROMPT_SUBMIT,
                    secret_values=secret_values,
                ).get("prompt_digest"),
                limit=80,
            )
            if prompt_text and isinstance(runtime_context, Mapping)
            else ""
        ),
        "session_digest_present": bool(_event_digest(session_id)),
        "turn_digest_present": bool(_event_digest(turn_id)),
        "thread_or_turn_digest_bound": bool(_event_digest(session_id) or _event_digest(turn_id)),
        "admission_run_id_digest_present": bool(admission_run_id_digest),
        **parent_process,
        "hook_config_present": bool(_hex_sha256(trusted_hook_config_sha256)),
        "hook_enabled": True,
        "hook_config_digest_bound": bool(
            trusted_hook_config_sha256
            and loaded_hook_config_sha256
            and trusted_hook_config_sha256 == loaded_hook_config_sha256
        ),
        "hook_producer_runnable": True,
        "user_prompt_submit_hook_ran": ok,
        "hook_ledger_written": ledger_written,
        "hook_ledger_file_path_recorded": False,
        "raw_prompt_recorded": False,
        "prompt_text_recorded": False,
        "natural_phrase_recorded": False,
        "raw_route_id_recorded": False,
        "route_candidate_recorded": False,
        "selected_api_route_id_recorded": False,
        "raw_provider_response_recorded": False,
        "provider_response_text_recorded": False,
        "raw_backend_details_exposed": False,
        "secret_value_exposed": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "product_ready": False,
        "state_written": ledger_written,
        "blocking_reasons": blocking_reasons,
        "changed_files": [str(ledger_path)] if ledger_written else [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "WBP UserPromptSubmit hook producer wrote a ledger."
            if ok
            else "WBP blocked UserPromptSubmit hook producer before ledger write."
        ),
        machine_error_code=HOOK_CONFIG_OK if ok else (
            HOOK_RUNTIME_CONTEXT_INVALID
            if any("runtime_context" in reason for reason in blocking_reasons)
            else HOOK_EVENT_INVALID
        ),
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if ok else "stop",
        changed_files=[str(ledger_path)] if ledger_written else [],
        effect=EFFECT_MUTATE,
        secret_values=secret_values,
        extra=extra,
    )


def _read_event_input(event_file: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    if event_file:
        path = Path(event_file).expanduser()
        metadata = {
            "hook_event_file_present": path.exists(),
            "hook_event_file_read": False,
            "hook_event_file_path_recorded": False,
        }
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            event, event_metadata = _load_event_from_text("")
            return event, {**metadata, **event_metadata}
        metadata["hook_event_file_read"] = True
        event, event_metadata = _load_event_from_text(text)
        return event, {**metadata, **event_metadata}
    text = sys.stdin.read()
    event, event_metadata = _load_event_from_text(text)
    return event, {"hook_event_stdin_read": True, **event_metadata}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="user_prompt_submit_hook_producer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_hook = subparsers.add_parser("run-hook")
    run_hook.add_argument("--event-file")
    run_hook.add_argument("--ledger-file")
    run_hook.add_argument("--runtime-context-file")
    run_hook.add_argument("--trusted-hook-config-sha256", required=True)
    run_hook.add_argument("--loaded-hook-config-sha256", required=True)
    run_hook.add_argument(
        "--origin-state",
        choices=[ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN, ORIGIN_STATE_SYNTHETIC_HOOK_FLOW],
        default=ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
    )
    run_hook.add_argument("--json", action="store_true")
    run_hook.add_argument("--quiet", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = RuntimePaths.from_env()
    if args.command == "run-hook":
        event, metadata = _read_event_input(args.event_file)
        packet = build_user_prompt_submit_run_packet(
            event=event,
            paths=paths,
            ledger_file=Path(args.ledger_file).expanduser() if args.ledger_file else None,
            runtime_context_file=args.runtime_context_file,
            trusted_hook_config_sha256=args.trusted_hook_config_sha256,
            loaded_hook_config_sha256=args.loaded_hook_config_sha256,
            origin_state=args.origin_state,
            event_metadata=metadata,
        )
        if args.json and not args.quiet:
            sys.stdout.write(json.dumps(packet, ensure_ascii=True) + "\n")
        return int(packet["exit_code"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
