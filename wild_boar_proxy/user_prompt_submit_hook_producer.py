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
import re
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
from .custom_agent_bindings import API_ROUTE_LANE, PRIMARY_CHATGPT_LANE, _canonical_alias_key
from .natural_intent_contract import PARSER_STATUS_MATCHED, parse_natural_alias_intent
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
from .wbp_dip_tool import _exact_plain_reply_requested


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
PRE_TOOL_USE_GUARD_BLOCKED = "WBP_PRE_TOOL_USE_ROUTER_GUARD_BLOCKED"

USER_PROMPT_SUBMIT_EVENT_NAME = "UserPromptSubmit"
PRE_TOOL_USE_EVENT_NAME = "PreToolUse"
HOOK_EVENT_TRUST_KEYS = {
    USER_PROMPT_SUBMIT_EVENT_NAME: "user_prompt_submit",
    PRE_TOOL_USE_EVENT_NAME: "pre_tool_use",
}
REQUIRED_HOOK_EVENT_NAMES = (USER_PROMPT_SUBMIT_EVENT_NAME, PRE_TOOL_USE_EVENT_NAME)
HOOKS_JSON_FILENAME = "hooks.json"
HOOK_SCRIPT_RELATIVE_PATH = "wbp-hooks/user_prompt_submit_hook.sh"
HOOK_LEDGER_RELATIVE_PATH = "managed/router-hook/user-prompt-submit-ledger.json"
PRE_TOOL_USE_GUARD_RELATIVE_PATH = "managed/router-hook/pre-tool-use-api-alias-guard.json"
HOOK_STATUS_MESSAGE = "WBP routing ledger"
HOOK_TIMEOUT_SECONDS = 30
PRE_TOOL_USE_GUARD_TTL_SECONDS = 900
CODEX_APP_SERVER_BIN_ENV = "WBP_CODEX_APP_SERVER_BIN"
CODEX_BIN_ENV = "WBP_CODEX_BIN"
_LEADING_ADDRESS_RE = re.compile(
    r"^\s*([A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9 _.-]{0,78})\s*[:：,]\s*"
)
_CODEX_DESKTOP_REQUEST_MARKER_RE = re.compile(
    r"(?im)^[ \t]*(?:#+[ \t]*)?My request for Codex\s*[:：][ \t]*$"
)


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


def pre_tool_use_guard_path(paths: RuntimePaths) -> Path:
    return paths.profile_dir / PRE_TOOL_USE_GUARD_RELATIVE_PATH


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


def hook_trust_key_for_paths(
    paths: RuntimePaths,
    *,
    event_name: str = USER_PROMPT_SUBMIT_EVENT_NAME,
) -> str:
    event_key = HOOK_EVENT_TRUST_KEYS.get(event_name, "")
    return f"{hooks_json_path(paths)}:{event_key}:0:0" if event_key else ""


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
            "--hook-output",
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


def _is_wbp_hook_group(group: object) -> bool:
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
    for event_name in REQUIRED_HOOK_EVENT_NAMES:
        existing_groups = merged_hooks.get(event_name)
        if not isinstance(existing_groups, list):
            existing_groups = []
        kept_groups = [
            group
            for group in existing_groups
            if not _is_wbp_hook_group(group)
        ]
        kept_groups.append({"hooks": [build_hook_definition(command)]})
        merged_hooks[event_name] = kept_groups
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
    event_name: str = USER_PROMPT_SUBMIT_EVENT_NAME,
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
    event_groups = hook_groups.get(event_name) if isinstance(hook_groups, Mapping) else None
    if not isinstance(event_groups, list):
        return metadata
    event_key = HOOK_EVENT_TRUST_KEYS.get(event_name, "")
    if not event_key:
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
            trust_key = f"{hooks_json}:{event_key}:{group_index}:{hook_index}"
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


def _find_hook_definition(
    document: Mapping[str, Any],
    *,
    command: str,
    event_name: str = USER_PROMPT_SUBMIT_EVENT_NAME,
) -> dict[str, Any]:
    hooks = document.get("hooks")
    if not isinstance(hooks, Mapping):
        return {}
    groups = hooks.get(event_name)
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
    hook_definitions = {
        event_name: _find_hook_definition(
            document,
            command=command,
            event_name=event_name,
        )
        for event_name in REQUIRED_HOOK_EVENT_NAMES
    }
    hook_definition = hook_definitions[USER_PROMPT_SUBMIT_EVENT_NAME]
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
        event_name=USER_PROMPT_SUBMIT_EVENT_NAME,
    )
    pre_tool_use_trust_metadata = _codex_hook_trust_state(
        config_toml=paths.config_toml,
        hooks_json=hooks_json_path(paths),
        hooks_document=document,
        command=command,
        codex_hook_current_hash=str(
            current_hash_metadata.get("codex_hook_current_hash", "")
        ),
        event_name=PRE_TOOL_USE_EVENT_NAME,
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
    loaded_digest = _canonical_json_digest(hook_definition) if hook_definition else ""
    pre_tool_use_hook_definition = hook_definitions[PRE_TOOL_USE_EVENT_NAME]
    pre_tool_use_loaded_digest = (
        _canonical_json_digest(pre_tool_use_hook_definition)
        if pre_tool_use_hook_definition
        else ""
    )
    script = hook_script_path(paths)
    script_present = script.exists()
    script_executable = bool(script_present and os.access(script, os.X_OK))
    hook_config_present = bool(
        hooks_metadata["hooks_json_present"]
        and all(hook_definitions[event_name] for event_name in REQUIRED_HOOK_EVENT_NAMES)
    )
    digest_bound = bool(
        all(
            _canonical_json_digest(hook_definitions[event_name]) == expected_digest
            for event_name in REQUIRED_HOOK_EVENT_NAMES
            if hook_definitions[event_name]
        )
        and all(hook_definitions[event_name] for event_name in REQUIRED_HOOK_EVENT_NAMES)
    )

    blocking_reasons: list[str] = []
    if hooks_disabled:
        blocking_reasons.append("hooks_feature_disabled")
    if not hooks_metadata["hooks_json_present"]:
        blocking_reasons.append("hooks_json_missing")
    elif not hooks_metadata["hooks_json_valid_json"]:
        blocking_reasons.append("hooks_json_invalid")
    if not hook_definition:
        blocking_reasons.append("user_prompt_submit_hook_definition_missing")
    if not pre_tool_use_hook_definition:
        blocking_reasons.append("pre_tool_use_hook_definition_missing")
    if hook_definition and loaded_digest != expected_digest:
        blocking_reasons.append("hook_config_digest_mismatch")
    if pre_tool_use_hook_definition and pre_tool_use_loaded_digest != expected_digest:
        blocking_reasons.append("pre_tool_use_hook_config_digest_mismatch")
    if not script_present:
        blocking_reasons.append("hook_script_missing")
    elif not script_executable:
        blocking_reasons.append("hook_script_not_executable")
    hook_trusted_by_profile_state = (
        trust_metadata["codex_hook_trusted_by_profile_state"] is True
    )
    pre_tool_use_hook_trusted_by_profile_state = (
        pre_tool_use_trust_metadata["codex_hook_trusted_by_profile_state"] is True
    )
    hook_trusted = bool(
        hook_trusted_by_profile_state
        and pre_tool_use_hook_trusted_by_profile_state
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
        "required_hook_events": list(REQUIRED_HOOK_EVENT_NAMES),
        "required_hook_events_present": bool(hook_config_present),
        "pre_tool_use_hook_config_present": bool(pre_tool_use_hook_definition),
        "pre_tool_use_expected_hook_definition_sha256": expected_digest,
        "pre_tool_use_loaded_hook_definition_sha256": pre_tool_use_loaded_digest,
        "pre_tool_use_hook_config_digest_bound": (
            bool(pre_tool_use_loaded_digest)
            and pre_tool_use_loaded_digest == expected_digest
        ),
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
        "pre_tool_use_hook_trusted_by_profile_state": (
            pre_tool_use_hook_trusted_by_profile_state
        ),
        "pre_tool_use_hook_trusted": pre_tool_use_hook_trusted_by_profile_state,
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
    hook_definitions = {
        event_name: _find_hook_definition(
            document,
            command=command,
            event_name=event_name,
        )
        for event_name in REQUIRED_HOOK_EVENT_NAMES
    }
    hook_definition = hook_definitions[USER_PROMPT_SUBMIT_EVENT_NAME]
    loaded_digest = _canonical_json_digest(hook_definition) if hook_definition else ""
    pre_tool_use_hook_definition = hook_definitions[PRE_TOOL_USE_EVENT_NAME]
    pre_tool_use_loaded_digest = (
        _canonical_json_digest(pre_tool_use_hook_definition)
        if pre_tool_use_hook_definition
        else ""
    )
    script = hook_script_path(paths)
    script_present = script.exists()
    script_executable = bool(script_present and os.access(script, os.X_OK))
    trust_keys = {
        event_name: hook_trust_key_for_paths(paths, event_name=event_name)
        for event_name in REQUIRED_HOOK_EVENT_NAMES
    }

    precondition_failures: list[str] = []
    if not hooks_metadata["hooks_json_present"]:
        precondition_failures.append("hooks_json_missing")
    elif not hooks_metadata["hooks_json_valid_json"]:
        precondition_failures.append("hooks_json_invalid")
    if not hook_definition:
        precondition_failures.append("user_prompt_submit_hook_definition_missing")
    if not pre_tool_use_hook_definition:
        precondition_failures.append("pre_tool_use_hook_definition_missing")
    if hook_definition and loaded_digest != expected_digest:
        precondition_failures.append("hook_config_digest_mismatch")
    if pre_tool_use_hook_definition and pre_tool_use_loaded_digest != expected_digest:
        precondition_failures.append("pre_tool_use_hook_config_digest_mismatch")
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
        event_name=USER_PROMPT_SUBMIT_EVENT_NAME,
    )
    pre_tool_use_before_trust = _codex_hook_trust_state(
        config_toml=paths.config_toml,
        hooks_json=hooks_json_path(paths),
        hooks_document=document,
        command=command,
        codex_hook_current_hash=expected_trusted_hash,
        event_name=PRE_TOOL_USE_EVENT_NAME,
    )
    already_trusted = (
        before_trust["codex_hook_trusted_by_profile_state"] is True
        and pre_tool_use_before_trust["codex_hook_trusted_by_profile_state"] is True
    )
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
            repaired_text = existing_text
            for trust_key in trust_keys.values():
                repaired_text = _append_exact_hook_trust_state(
                    repaired_text,
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
        event_name=USER_PROMPT_SUBMIT_EVENT_NAME,
    )
    pre_tool_use_after_trust = _codex_hook_trust_state(
        config_toml=paths.config_toml,
        hooks_json=hooks_json_path(paths),
        hooks_document=document,
        command=command,
        codex_hook_current_hash=expected_trusted_hash,
        event_name=PRE_TOOL_USE_EVENT_NAME,
    )
    repaired_or_already = (
        after_trust["codex_hook_trusted_by_profile_state"] is True
        and pre_tool_use_after_trust["codex_hook_trusted_by_profile_state"] is True
    )
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
        "required_hook_events": list(REQUIRED_HOOK_EVENT_NAMES),
        "required_hook_events_present": bool(
            hooks_metadata["hooks_json_present"]
            and all(hook_definitions[event_name] for event_name in REQUIRED_HOOK_EVENT_NAMES)
        ),
        "pre_tool_use_hook_config_present": bool(pre_tool_use_hook_definition),
        "hook_command_path_resolves": script_present,
        "hook_script_executable": script_executable,
        "expected_hook_definition_sha256": expected_digest,
        "loaded_hook_definition_sha256": loaded_digest,
        "pre_tool_use_loaded_hook_definition_sha256": pre_tool_use_loaded_digest,
        "hook_config_digest_bound": bool(loaded_digest and loaded_digest == expected_digest),
        "pre_tool_use_hook_config_digest_bound": (
            bool(pre_tool_use_loaded_digest)
            and pre_tool_use_loaded_digest == expected_digest
        ),
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
        "pre_tool_use_hook_trusted_before_repair": (
            pre_tool_use_before_trust["codex_hook_trusted_by_profile_state"] is True
        ),
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
        "pre_tool_use_hook_trusted_after_repair": (
            pre_tool_use_after_trust["codex_hook_trusted_by_profile_state"] is True
        ),
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


def _command_uses_wbp_isolated_user_data(command: str) -> bool:
    return (
        "--user-data-dir=" in command
        and "WildBoarProxy/CodexProfiles/" in command
        and "/electron-user-data" in command
    )


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
    if _path_has_suffix(
        executable_path,
        "Applications/ChatGPT.app/Contents/Resources/codex",
    ) and command.startswith(executable_path + " app-server"):
        return "official_codex_app_server"
    if _path_has_suffix(
        executable_path,
        "Applications/Codex.app/Contents/Resources/codex",
    ) and command.startswith(executable_path + " app-server"):
        return "official_codex_app_server"
    if _path_has_suffix(
        executable_path,
        "Applications/ChatGPT.app/Contents/MacOS/ChatGPT",
    ):
        if _command_uses_wbp_isolated_user_data(command):
            return "wbp_isolated_official_app_root"
        return "stock_codex_app_root"
    if _path_has_suffix(executable_path, "Applications/Codex.app/Contents/MacOS/Codex"):
        if _command_uses_wbp_isolated_user_data(command):
            return "wbp_isolated_official_app_root"
        return "stock_codex_app_root"
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
    isolated_official_root_present = "wbp_isolated_official_app_root" in classes
    clean_app_class_present = isolated_official_root_present or any(
        item.startswith("wbp_clean_app_") for item in classes
    )
    clean_app_server_present = (
        "wbp_clean_app_server" in classes
        or "official_codex_app_server" in classes
    )
    clean_app_root_present = (
        "wbp_clean_app_root" in classes or isolated_official_root_present
    )
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
        if event_name == USER_PROMPT_SUBMIT_EVENT_NAME and turn_id:
            return HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN
        return HOOK_STATE_RAN_CODEX_UNPROVEN
    if event_name == USER_PROMPT_SUBMIT_EVENT_NAME:
        return HOOK_STATE_RAN_CODEX_UNPROVEN
    return HOOK_STATE_RAN_SYNTHETIC


def _leading_address_label(prompt_text: str) -> str:
    match = _LEADING_ADDRESS_RE.match(prompt_text)
    return _safe_text(match.group(1), limit=80) if match else ""


def _active_prompt_for_alias_routing(prompt_text: str) -> str:
    text = str(prompt_text or "").replace("\r\n", "\n").replace("\r", "\n")
    markers = list(_CODEX_DESKTOP_REQUEST_MARKER_RE.finditer(text))
    if not markers:
        return prompt_text
    return text[markers[-1].end() :].lstrip()


def _leading_label_looks_like_addressed_alias(label: str) -> bool:
    normalized = _safe_text(label, limit=80).casefold()
    if not normalized:
        return False
    parts = normalized.split()
    if len(parts) == 1:
        return True
    return parts[0] in {
        "agent",
        "агент",
        "api",
        "gpt",
        "codex",
        "dip",
        "deepseek",
    }


def _runtime_aliases(runtime_context: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    alias_map = runtime_context.get("alias_to_agent_id")
    if isinstance(alias_map, Mapping):
        aliases.update(_safe_text(alias, limit=80) for alias in alias_map)
    bindings = runtime_context.get("agent_bindings")
    if isinstance(bindings, list):
        for binding in bindings:
            if not isinstance(binding, Mapping):
                continue
            raw_aliases = binding.get("aliases")
            if isinstance(raw_aliases, list):
                aliases.update(_safe_text(alias, limit=80) for alias in raw_aliases)
            aliases.add(_safe_text(binding.get("display_name"), limit=80))
    return {_canonical_alias_key(alias) for alias in aliases if alias}


def _runtime_alias_lane(runtime_context: Mapping[str, Any], label: str) -> str:
    normalized = _canonical_alias_key(_safe_text(label, limit=80))
    if not normalized:
        return ""
    alias_to_agent_id = runtime_context.get("alias_to_agent_id")
    agent_id = ""
    if isinstance(alias_to_agent_id, Mapping):
        for alias, candidate_agent_id in alias_to_agent_id.items():
            if _canonical_alias_key(_safe_text(alias, limit=80)) == normalized:
                agent_id = _safe_text(candidate_agent_id, limit=80).casefold()
                break
    bindings = runtime_context.get("agent_bindings")
    if agent_id and isinstance(bindings, list):
        for binding in bindings:
            if not isinstance(binding, Mapping):
                continue
            if _safe_text(binding.get("agent_id"), limit=80).casefold() == agent_id:
                return _safe_text(binding.get("lane"), limit=80)
    return ""


def _user_prompt_submit_context_kind(
    *,
    prompt_text: str,
    runtime_context: Mapping[str, Any],
) -> str:
    prompt_text = _active_prompt_for_alias_routing(prompt_text)
    parser_result = parse_natural_alias_intent(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
    )
    if (
        parser_result.get("parser_status") == PARSER_STATUS_MATCHED
        and parser_result.get("parser_api_target_present") is True
    ):
        return API_ROUTE_LANE
    label = _leading_address_label(prompt_text)
    if not label:
        return ""
    lane = _runtime_alias_lane(runtime_context, label)
    if lane in {API_ROUTE_LANE, PRIMARY_CHATGPT_LANE}:
        return lane
    aliases = _runtime_aliases(runtime_context)
    if _canonical_alias_key(label) in aliases or _leading_label_looks_like_addressed_alias(label):
        return API_ROUTE_LANE
    return ""


def _read_pre_tool_use_guard(paths: RuntimePaths) -> tuple[dict[str, Any], dict[str, Any]]:
    path = pre_tool_use_guard_path(paths)
    metadata: dict[str, Any] = {
        "pre_tool_use_guard_present": path.exists(),
        "pre_tool_use_guard_read": False,
        "pre_tool_use_guard_valid_json": False,
        "pre_tool_use_guard_active": False,
        "pre_tool_use_guard_expired": False,
        "pre_tool_use_guard_path_recorded": False,
    }
    if not path.exists():
        return {}, metadata
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, metadata
    metadata["pre_tool_use_guard_read"] = True
    if not isinstance(parsed, Mapping):
        return {}, metadata
    packet = dict(parsed)
    metadata["pre_tool_use_guard_valid_json"] = True
    expires_at = packet.get("expires_at_epoch_seconds")
    if isinstance(expires_at, (int, float)) and expires_at < time.time():
        metadata["pre_tool_use_guard_expired"] = True
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        return {}, metadata
    metadata["pre_tool_use_guard_active"] = True
    return packet, metadata


def _clear_pre_tool_use_guard(paths: RuntimePaths) -> bool:
    try:
        pre_tool_use_guard_path(paths).unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def _write_pre_tool_use_guard(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    runtime_context: Mapping[str, Any],
    turn_id: str,
    session_id: str,
) -> bool:
    guard = {
        "schema_version": 1,
        "packet_kind": "wbp_pre_tool_use_api_alias_guard",
        "created_at_epoch_seconds": time.time(),
        "expires_at_epoch_seconds": time.time() + PRE_TOOL_USE_GUARD_TTL_SECONDS,
        "prompt_digest": _event_digest(prompt_text),
        "runtime_context_digest": runtime_context_digest(runtime_context),
        "turn_digest": _event_digest(turn_id),
        "session_digest": _event_digest(session_id),
        "required_command": "router-hook auto-route-output --prompt-file -",
        "raw_prompt_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
    }
    try:
        guard_path = pre_tool_use_guard_path(paths)
        guard_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(guard_path, guard)
    except OSError:
        return False
    return True


def _string_candidates_from_event(value: object) -> list[str]:
    candidates: list[str] = []

    def visit(node: object, key: str = "") -> None:
        if isinstance(node, Mapping):
            for raw_key, child in node.items():
                visit(child, _safe_text(raw_key, limit=80).casefold())
            return
        if isinstance(node, list):
            for child in node:
                visit(child, key)
            return
        if not isinstance(node, str):
            return
        if key in {
            "command",
            "cmd",
            "parsedcmd",
            "shell_command",
            "shellcommand",
            "input",
            "arguments",
            "args",
        }:
            candidates.append(node)

    visit(value)
    return candidates


def _router_prompt_assignment_value(command: str) -> str:
    match = re.match(r"\s*WBP_ROUTER_PROMPT='([^']*)'\s*;", command)
    return match.group(1) if match else ""


def _router_command_arg(command: str, flag: str) -> str:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return ""
    for index, token in enumerate(tokens[:-1]):
        if token == flag:
            return tokens[index + 1]
    return ""


def _router_command_runtime_context_bound(command: str, guard: Mapping[str, Any]) -> bool:
    expected_digest = _safe_text(guard.get("runtime_context_digest"), limit=80)
    if not expected_digest:
        return False
    context_file = _router_command_arg(command, "--runtime-context-file")
    if not context_file or "$" in context_file:
        return False
    context, metadata = load_runtime_context_packet(Path(context_file).expanduser())
    return bool(
        metadata.get("runtime_context_file_valid_json") is True
        and runtime_context_digest(context) == expected_digest
    )


def _canonical_router_output_command(
    command: str,
    *,
    guard: Mapping[str, Any] | None = None,
) -> bool:
    text = " ".join(_safe_text(command, limit=12000).split())
    if not text:
        return False
    canonical_prefix = re.compile(
        r"^WBP_ROUTER_PROMPT='[^']*'; "
        r'WBP_ROUTER_PROOF_DIR="[^"]*/tmp/user-prompt-submit-router-proof"; '
        r"printf '%s\\n' \"\$WBP_ROUTER_PROMPT\" \| "
        r"(?:python3|\$\{WBP_PYTHON_BIN:-python3\}) -m wild_boar_proxy "
        r"router-hook auto-route-output "
    )
    if canonical_prefix.search(text) is None:
        return False
    required_fragments = [
        "router-hook auto-route-output",
        "--runtime-context-file",
        "--active-project-root",
        "--repo-bridge auto",
        "--work-mode full",
        "--timeout-seconds 300",
        "--proof-dir",
        "--prompt-file -",
    ]
    forbidden_fragments = [
        "router-hook auto-route --json",
        "router-hook auto-route --prompt",
        "router-hook direct-reply",
        "tools/wbp_dip",
        "dip run",
        "codex exec",
        "python3 -c",
        "mktemp",
        "mkdir ",
        "<<",
        "&&",
        "||",
        "`",
        "$(",
        "; echo",
        "| sh",
        "bash -c",
        "zsh -c",
        "curl ",
        "wget ",
    ]
    if not all(fragment in text for fragment in required_fragments):
        return False
    if any(fragment in text for fragment in forbidden_fragments):
        return False
    if text.count("router-hook auto-route-output") != 1:
        return False
    if text.count("--prompt-file -") != 1:
        return False
    if not text.endswith("--prompt-file -"):
        return False
    if "/tmp/user-prompt-submit-router-proof" not in text:
        return False
    guard = guard if isinstance(guard, Mapping) else {}
    expected_prompt_digest = _safe_text(guard.get("prompt_digest"), limit=80)
    prompt_value = _router_prompt_assignment_value(command)
    if expected_prompt_digest and _event_digest(prompt_value) != expected_prompt_digest:
        return False
    if guard and not _router_command_runtime_context_bound(command, guard):
        return False
    return True


def build_pre_tool_use_guard_packet(
    *,
    event: Mapping[str, Any],
    paths: RuntimePaths,
    event_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(event_metadata or {})
    guard, guard_metadata = _read_pre_tool_use_guard(paths)
    command_candidates = _string_candidates_from_event(event)
    allowed = bool(
        guard_metadata.get("pre_tool_use_guard_active") is True
        and any(
            _canonical_router_output_command(command, guard=guard)
            for command in command_candidates
        )
    )
    blocked = bool(
        guard_metadata.get("pre_tool_use_guard_active") is True
        and not allowed
    )
    reason = (
        "WBP blocked non-canonical tool use during addressed API alias router handoff."
        if blocked
        else ""
    )
    extra = {
        **metadata,
        **guard_metadata,
        "schema_version": 1,
        "packet_kind": "wbp_pre_tool_use_router_guard",
        "hook_event_name": PRE_TOOL_USE_EVENT_NAME,
        "pre_tool_use_hook_ran": True,
        "pre_tool_use_guard_packet_present": bool(guard),
        "pre_tool_use_command_candidate_count": len(command_candidates),
        "pre_tool_use_canonical_router_command_allowed": allowed,
        "pre_tool_use_decision": "block" if blocked else "allow",
        "pre_tool_use_block_reason": reason,
        "raw_prompt_recorded": False,
        "raw_command_recorded": False,
        "raw_route_id_recorded": False,
        "secret_value_exposed": False,
        "product_ready": False,
        "blocking_reasons": [PRE_TOOL_USE_GUARD_BLOCKED] if blocked else [],
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=not blocked,
        human_message=(
            "WBP PreToolUse guard allowed tool use."
            if not blocked
            else "WBP PreToolUse guard blocked non-canonical tool use."
        ),
        machine_error_code=HOOK_CONFIG_OK if not blocked else PRE_TOOL_USE_GUARD_BLOCKED,
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none" if not blocked else "stop",
        changed_files=[],
        effect=EFFECT_PROBE,
        extra=extra,
    )


def _addressed_alias_context_needed(
    *,
    prompt_text: str,
    runtime_context: Mapping[str, Any],
) -> bool:
    return bool(
        _user_prompt_submit_context_kind(
            prompt_text=prompt_text,
            runtime_context=runtime_context,
        )
    )


def _router_command_additional_context(*, runtime_context_file: Path) -> str:
    quoted_runtime_context_file = shlex.quote(str(runtime_context_file))
    return (
        "WBP ROUTER HARD OVERRIDE. The active prompt is addressed to a WBP API "
        "agent. This is a deterministic router handoff, not a native Codex task. "
        "Exact visible behavior: say nothing before running the command; run "
        "exactly one shell command: COMMAND below; then return only stdout. Copy "
        "COMMAND literally except replacing <original prompt> inside the "
        "WBP_ROUTER_PROMPT single-quoted assignment with only the active user "
        "request text, after any Codex Desktop envelope such as 'My request for "
        "Codex:'. Send that variable to the "
        "router through stdin; the command must keep --prompt-file - and must "
        "not contain --prompt. "
        "Do not replace WBP_ROUTER_PROOF_DIR with mktemp or any other path. Escape "
        "embedded single quotes only if needed. Do not answer, plan, summarize, "
        "inspect old turns, or write files yourself. Do not say 'I'll process', "
        "'Let me', 'I will', or any other preface. Do not use AGENTS.md examples, "
        "router-hook auto-route --json, router-hook auto-route --prompt, "
        "direct-reply, tools/wbp_dip, codex exec, subagents, direct provider "
        "calls, mkdir, python3 -c, heredocs, mktemp, or wrapper shopping. If "
        "the command returns a machine error, times out, "
        "or prints nothing, output only that machine result/error and stop. Do "
        "not retry through another path and do not run cleanup or helper "
        "commands. No prose, Markdown, table, recap, translation, or extra token "
        "is allowed. If you are about to run any command other than COMMAND, "
        "output exactly WBP_ROUTER_COMMAND_NOT_EXECUTED. Do not alter any literal "
        "command argument; the timeout argument must remain exactly 300 and must "
        "never be changed to 90.\n"
        "COMMAND:\n"
        "WBP_ROUTER_PROMPT='<original prompt>'; "
        'WBP_ROUTER_PROOF_DIR="${WBP_PROFILE_DIR:-${TMPDIR:-/tmp}/wbp-router-proof-profile}/tmp/user-prompt-submit-router-proof"; '
        'printf \'%s\\n\' "$WBP_ROUTER_PROMPT" | '
        "${WBP_PYTHON_BIN:-python3} -m wild_boar_proxy router-hook auto-route-output "
        f"--runtime-context-file {quoted_runtime_context_file} "
        "--active-project-root \"$PWD\" --repo-bridge auto --work-mode full "
        "--timeout-seconds 300 --proof-dir \"$WBP_ROUTER_PROOF_DIR\" "
        "--prompt-file -"
    )


def _exact_reply_additional_context() -> str:
    return (
        "WBP EXACT RESPONSE CONTEXT: the active user prompt asks for an exact "
        "reply. Return exactly the requested content from the active user "
        "prompt and nothing else: no prose, Markdown, acknowledgements, "
        "explanation, code fence, prefix, or suffix."
    )


def _primary_exact_alias_additional_context() -> str:
    return (
        "WBP PRIMARY EXACT ALIAS CONTEXT: the active user prompt is addressed "
        "to this native ChatGPT lane. Use only the active user prompt, ignore "
        "previous turns, and ignore the leading alias prefix. The visible "
        "answer is a physical exact-output proof. Return only the requested "
        "exact content after the colon. Do not explain WBP, runtime context, "
        "routing, alias resolution, prior prompts, or why the answer is valid. "
        "No prose, Markdown, acknowledgements, code fence, prefix, suffix, "
        "alias label, prompt echo, or extra token is allowed."
    )


def _user_prompt_submit_additional_context(
    *,
    prompt_text: str,
    runtime_context: Mapping[str, Any],
    runtime_context_file: Path,
) -> str:
    active_prompt_text = _active_prompt_for_alias_routing(prompt_text)
    context_kind = _user_prompt_submit_context_kind(
        prompt_text=active_prompt_text,
        runtime_context=runtime_context,
    )
    if not context_kind:
        if _exact_plain_reply_requested(active_prompt_text):
            return _exact_reply_additional_context()
        return ""
    if context_kind == PRIMARY_CHATGPT_LANE:
        if _exact_plain_reply_requested(active_prompt_text):
            return _primary_exact_alias_additional_context()
        return (
            "WBP PRIMARY ALIAS CONTEXT: this UserPromptSubmit hook observed a "
            "prompt addressed to a primary ChatGPT alias from the Wild Boar "
            "Proxy runtime context. The leading label names the native ChatGPT "
            "lane, not an API agent. Answer the active user prompt natively in "
            "this Custom Codex turn. Do not call router-hook, direct-reply, "
            "tools/wbp_dip, ordinary subagents, fallback wrappers, or direct "
            "provider APIs. Do not output unknown-alias machine codes. If the "
            "user asks for an exact reply, return exactly the requested content "
            "and nothing else."
        )
    return _router_command_additional_context(
        runtime_context_file=runtime_context_file,
    )


def _safe_hook_additional_context(value: object, *, limit: int = 4000) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()[:limit]


def build_user_prompt_submit_hook_output(packet: Mapping[str, Any]) -> dict[str, Any]:
    if packet.get("hook_event_name") == PRE_TOOL_USE_EVENT_NAME:
        if packet.get("pre_tool_use_decision") == "block":
            reason = _safe_text(
                packet.get("pre_tool_use_block_reason"),
                limit=500,
            )
            return {"decision": "block", "reason": reason or PRE_TOOL_USE_GUARD_BLOCKED}
        return {}
    context = _safe_hook_additional_context(
        packet.get("hook_additional_context"),
        limit=4000,
    )
    if not context:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }


def build_user_prompt_submit_hook_output_for_event(
    *,
    event: Mapping[str, Any],
    paths: RuntimePaths,
    runtime_context_file: str | None = None,
) -> dict[str, Any]:
    prompt = event.get("prompt")
    prompt_text = prompt if isinstance(prompt, str) else ""
    event_name = _safe_text(event.get("hook_event_name"), limit=80)
    if event_name == PRE_TOOL_USE_EVENT_NAME:
        packet = build_pre_tool_use_guard_packet(event=event, paths=paths)
        return build_user_prompt_submit_hook_output(packet)
    if not prompt_text:
        return {}
    context_path = runtime_context_path(
        paths=paths,
        runtime_context_file=runtime_context_file,
    )
    runtime_context, context_metadata = load_runtime_context_packet(context_path)
    if (
        context_metadata.get("runtime_context_file_read") is not True
        or context_metadata.get("runtime_context_file_valid_json") is not True
    ):
        return {}
    context = _user_prompt_submit_additional_context(
        prompt_text=prompt_text,
        runtime_context=runtime_context,
        runtime_context_file=context_path,
    )
    return build_user_prompt_submit_hook_output({"hook_additional_context": context})


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
    if event_name == PRE_TOOL_USE_EVENT_NAME:
        return build_pre_tool_use_guard_packet(
            event=event,
            paths=paths,
            event_metadata=event_metadata,
        )
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
    if event_name != USER_PROMPT_SUBMIT_EVENT_NAME:
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
    active_prompt_text = _active_prompt_for_alias_routing(prompt_text)
    context_kind = (
        _user_prompt_submit_context_kind(
            prompt_text=active_prompt_text,
            runtime_context=runtime_context,
        )
        if ok
        else ""
    )
    hook_additional_context = (
        _user_prompt_submit_additional_context(
            prompt_text=active_prompt_text,
            runtime_context=runtime_context,
            runtime_context_file=context_path,
        )
        if ok
        else ""
    )
    producer_state = _producer_state(
        event_name=event_name,
        turn_id=turn_id,
        origin_state=effective_origin_state,
    )
    ledger_path = ledger_file or hook_ledger_path(paths)
    ledger_written = False
    if ok:
        guard_written = False
        guard_cleared = False
        if context_kind == API_ROUTE_LANE:
            guard_written = _write_pre_tool_use_guard(
                paths=paths,
                prompt_text=active_prompt_text,
                runtime_context=runtime_context,
                turn_id=turn_id,
                session_id=session_id,
            )
        else:
            guard_cleared = _clear_pre_tool_use_guard(paths)
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
    else:
        guard_written = False
        guard_cleared = False

    extra = {
        **metadata,
        **context_metadata,
        "schema_version": 1,
        "packet_kind": HOOK_PRODUCER_RUN_PACKET_KIND,
        "hook_event_name": event_name,
        "hook_event_name_is_user_prompt_submit": event_name == USER_PROMPT_SUBMIT_EVENT_NAME,
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
        "hook_additional_context_available": bool(hook_additional_context),
        "hook_additional_context_recorded": False,
        "hook_additional_context_sha256": (
            _sha256_text(hook_additional_context) if hook_additional_context else ""
        ),
        "pre_tool_use_guard_written": guard_written,
        "pre_tool_use_guard_cleared": guard_cleared,
        "pre_tool_use_guard_required": context_kind == API_ROUTE_LANE,
        "fallback_used": False,
        "local_imitation_used": False,
        "product_ready": False,
        "state_written": bool(ledger_written or guard_written or guard_cleared),
        "blocking_reasons": blocking_reasons,
        "changed_files": (
            [str(ledger_path)]
            + ([str(pre_tool_use_guard_path(paths))] if guard_written else [])
        )
        if ledger_written
        else [],
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
    run_hook.add_argument("--hook-output", action="store_true")

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
        if args.hook_output:
            hook_output = (
                build_user_prompt_submit_hook_output_for_event(
                    event=event,
                    paths=paths,
                    runtime_context_file=args.runtime_context_file,
                )
                if packet.get("status") == "ok"
                else {}
            )
            if hook_output:
                sys.stdout.write(json.dumps(hook_output, ensure_ascii=True) + "\n")
        elif args.json and not args.quiet:
            sys.stdout.write(json.dumps(packet, ensure_ascii=True) + "\n")
        return int(packet["exit_code"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
