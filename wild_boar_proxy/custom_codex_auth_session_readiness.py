# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from typing import Any

from .command_effects import EFFECT_PROBE
from .core import packets
from .native_filesystem_probe import (
    collect_codex_process_inventory,
    default_persistent_custom_profile_paths,
)
from .real_custom_app_submit_ledger_proof import _process_inventory_observation
from .runtime import RuntimePaths
from .user_prompt_submit_hook_producer import (
    HOOK_CONFIG_OK,
    _codex_app_server_binary,
    _websocket_recv_json,
    _websocket_send_json,
    _websocket_upgrade,
    build_user_prompt_submit_readiness_packet,
)


CUSTOM_CODEX_AUTH_SESSION_READINESS_PACKET_KIND = (
    "wbp_custom_codex_auth_session_readiness"
)

CUSTOM_CODEX_AUTH_SESSION_OK = "OK"
CUSTOM_CODEX_AUTH_SESSION_PROCESS_NOT_LIVE = "WBP_CUSTOM_CODEX_PROCESS_NOT_LIVE"
CUSTOM_CODEX_AUTH_SESSION_HOOK_NOT_READY = "WBP_CUSTOM_CODEX_HOOK_NOT_READY"
CUSTOM_CODEX_AUTH_SESSION_API_KEY_ONLY = "WBP_CUSTOM_CODEX_API_KEY_ONLY"
CUSTOM_CODEX_AUTH_SESSION_LOGIN_REQUIRED = "WBP_CUSTOM_CODEX_LOGIN_REQUIRED"
CUSTOM_CODEX_AUTH_SESSION_UNKNOWN = "WBP_CUSTOM_CODEX_AUTH_UNKNOWN"

SESSION_STATE_READY = "READY"
SESSION_STATE_PROCESS_NOT_LIVE = "PROCESS_NOT_LIVE"
SESSION_STATE_HOOK_NOT_READY = "HOOK_NOT_READY"
SESSION_STATE_API_KEY_ONLY = "API_KEY_ONLY"
SESSION_STATE_LOGIN_REQUIRED = "LOGIN_REQUIRED"
SESSION_STATE_UNKNOWN = "AUTH_UNKNOWN"

ACCOUNT_READ_METHOD = "account/read"


def _safe_account_type(value: object) -> str:
    text = str(value or "").strip()
    return text if text in {"apiKey", "chatgpt", "amazonBedrock"} else ""


def _read_auth_file_classification(auth_file: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "auth_json_present": auth_file.exists(),
        "auth_json_read": False,
        "auth_json_valid_json": False,
        "auth_json_mapping": False,
        "auth_json_path_recorded": False,
        "auth_json_content_recorded": False,
        "auth_json_secret_values_recorded": False,
        "auth_json_error_code": "",
        "auth_mode": "missing" if not auth_file.exists() else "unknown",
        "openai_api_key_present": False,
        "chatgpt_token_material_present": False,
        "auth_json_api_key_only": False,
    }
    if not auth_file.exists():
        metadata["auth_json_error_code"] = "auth_json_missing"
        return metadata
    try:
        parsed = json.loads(auth_file.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        metadata["auth_json_error_code"] = "auth_json_invalid_encoding"
        metadata["auth_mode"] = "invalid"
        return metadata
    except (OSError, json.JSONDecodeError):
        metadata["auth_json_error_code"] = "auth_json_invalid"
        metadata["auth_mode"] = "invalid"
        return metadata
    metadata["auth_json_read"] = True
    metadata["auth_json_valid_json"] = True
    if not isinstance(parsed, Mapping):
        metadata["auth_json_error_code"] = "auth_json_not_mapping"
        metadata["auth_mode"] = "invalid"
        return metadata
    metadata["auth_json_mapping"] = True
    declared = str(parsed.get("auth_mode") or "").strip().lower()
    has_api_key = isinstance(parsed.get("OPENAI_API_KEY"), str) and bool(
        str(parsed.get("OPENAI_API_KEY")).strip()
    )
    token_keys = ("access_token", "refresh_token", "id_token", "auth_token")
    has_chatgpt_token = any(
        isinstance(parsed.get(key), str) and bool(str(parsed.get(key)).strip())
        for key in token_keys
    )
    nested = parsed.get("tokens")
    if isinstance(nested, Mapping):
        has_chatgpt_token = has_chatgpt_token or any(
            isinstance(nested.get(key), str) and bool(str(nested.get(key)).strip())
            for key in token_keys
        )
    declared_chatgpt = declared == "chatgpt"
    declared_apikey = declared in {"apikey", "api_key", "api-key"}
    if has_api_key and (has_chatgpt_token or declared_chatgpt):
        auth_mode = "mixed"
    elif has_chatgpt_token or declared_chatgpt:
        auth_mode = "chatgpt"
    elif has_api_key or declared_apikey:
        auth_mode = "apikey"
    else:
        auth_mode = "missing_credentials"
    metadata.update(
        {
            "auth_mode": auth_mode,
            "openai_api_key_present": has_api_key,
            "chatgpt_token_material_present": has_chatgpt_token,
            "auth_json_api_key_only": auth_mode == "apikey",
        }
    )
    return metadata


def _account_read_summary_from_response(response: Mapping[str, Any]) -> dict[str, Any]:
    error = response.get("error")
    result = response.get("result")
    account = result.get("account") if isinstance(result, Mapping) else None
    account_type = _safe_account_type(account.get("type") if isinstance(account, Mapping) else "")
    requires_openai_auth = (
        bool(result.get("requiresOpenaiAuth")) if isinstance(result, Mapping) else False
    )
    return {
        "app_server_account_response_seen": bool(response),
        "app_server_account_response_has_error": isinstance(error, Mapping),
        "app_server_account_error_code": (
            str(error.get("code", ""))[:96] if isinstance(error, Mapping) else ""
        ),
        "app_server_account_error_message_present": (
            bool(error.get("message")) if isinstance(error, Mapping) else False
        ),
        "app_server_account_response_has_result": isinstance(result, Mapping),
        "app_server_account_type": account_type,
        "app_server_account_chatgpt": account_type == "chatgpt",
        "app_server_account_api_key": account_type == "apiKey",
        "app_server_requires_openai_auth": requires_openai_auth,
        "app_server_account_email_recorded": False,
        "app_server_account_plan_recorded": False,
        "app_server_account_raw_payload_recorded": False,
        "app_server_account_token_recorded": False,
    }


def probe_codex_app_server_account_read(
    paths: RuntimePaths,
    *,
    timeout_seconds: float = 4.0,
) -> dict[str, Any]:
    binary = _codex_app_server_binary()
    summary: dict[str, Any] = {
        "app_server_account_probe_attempted": True,
        "app_server_account_probe_binary_present": bool(binary),
        "app_server_account_probe_process_started": False,
        "app_server_account_probe_socket_present": False,
        "app_server_account_probe_transport_ok": False,
        "app_server_account_probe_error_code": "",
        "app_server_account_notifications_seen": 0,
        **_account_read_summary_from_response({}),
    }
    if binary is None:
        summary["app_server_account_probe_error_code"] = "codex_app_server_binary_missing"
        return summary
    with tempfile.TemporaryDirectory() as temp_dir:
        socket_path = Path(temp_dir) / "codex-app-server.sock"
        env = os.environ.copy()
        env.update(
            {
                "CODEX_HOME": str(paths.profile_dir),
                "WBP_PROFILE_DIR": str(paths.profile_dir),
                "WBP_MANAGED_DIR": str(paths.managed_dir),
                "WBP_CONFIG_TOML": str(paths.config_toml),
            }
        )
        proc = subprocess.Popen(
            [str(binary), "app-server", "--listen", f"unix://{socket_path}"],
            cwd=str(Path.cwd()),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + timeout_seconds
            while time.time() < deadline and not socket_path.exists() and proc.poll() is None:
                time.sleep(0.05)
            summary["app_server_account_probe_process_started"] = proc.poll() is None
            summary["app_server_account_probe_socket_present"] = socket_path.exists()
            if not socket_path.exists():
                summary["app_server_account_probe_error_code"] = "app_server_socket_missing"
                return summary
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(str(socket_path))
                if not _websocket_upgrade(sock, timeout_seconds=timeout_seconds):
                    summary["app_server_account_probe_error_code"] = "websocket_upgrade_failed"
                    return summary
                summary["app_server_account_probe_transport_ok"] = True
                _websocket_send_json(
                    sock,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "wbp-readiness", "version": "0"},
                        },
                    },
                )
                init_deadline = time.time() + timeout_seconds
                while time.time() < init_deadline:
                    message = _websocket_recv_json(sock, timeout_seconds=0.5)
                    if message.get("id") == 1:
                        break
                _websocket_send_json(sock, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
                _websocket_send_json(
                    sock,
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": ACCOUNT_READ_METHOD,
                        "params": {"refreshToken": False},
                    },
                )
                response_deadline = time.time() + timeout_seconds
                while time.time() < response_deadline:
                    message = _websocket_recv_json(sock, timeout_seconds=0.5)
                    if not message:
                        continue
                    if message.get("id") == 2:
                        summary.update(_account_read_summary_from_response(message))
                        return summary
                    if message.get("method"):
                        summary["app_server_account_notifications_seen"] += 1
                summary["app_server_account_probe_error_code"] = "account_read_response_missing"
                return summary
        except (OSError, subprocess.SubprocessError, ValueError):
            summary["app_server_account_probe_error_code"] = "app_server_account_probe_failed"
            return summary
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)


def _default_custom_user_data_dir(paths: RuntimePaths) -> str:
    defaults = default_persistent_custom_profile_paths()
    profile_default = Path(str(defaults["persistent_profile_root"])).expanduser()
    if paths.profile_dir.expanduser().resolve(strict=False) == profile_default.resolve(strict=False):
        return str(Path(str(defaults["user_data_dir"])).expanduser())
    return str((paths.profile_dir / "electron-user-data").expanduser())


def _read_process_inventory_file(path: Path | None) -> tuple[dict[str, Any] | None, bool]:
    if path is None:
        return None, True
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, False
    return dict(parsed) if isinstance(parsed, Mapping) else {}, False


def _hook_ready(hook_readiness_packet: Mapping[str, Any]) -> bool:
    app_server_status_required = (
        hook_readiness_packet.get("codex_hook_app_server_trust_status_required")
        is True
        or hook_readiness_packet.get("codex_hook_current_hash_source")
        == "codex_app_server_hooks_list"
    )
    app_server_status_trusted = (
        hook_readiness_packet.get("codex_hook_app_server_trust_status_trusted")
        is True
        or hook_readiness_packet.get("codex_hook_trust_status_from_app_server")
        == "trusted"
    )
    return (
        hook_readiness_packet.get("status") == "ok"
        and hook_readiness_packet.get("machine_error_code") == HOOK_CONFIG_OK
        and hook_readiness_packet.get("hook_trusted") is True
        and (
            not app_server_status_required
            or app_server_status_trusted
        )
    )


def _safe_reasons(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    reasons: set[str] = set()
    for value in values:
        if packets.is_command_value_token(value):
            reasons.add(str(value))
    return sorted(reasons)


def _machine_state(
    *,
    process_ready: bool,
    hook_ready: bool,
    logged_in_ui_session_proven: bool,
    api_key_only: bool,
    login_required: bool,
) -> tuple[str, str, str]:
    if not process_ready:
        return (
            SESSION_STATE_PROCESS_NOT_LIVE,
            CUSTOM_CODEX_AUTH_SESSION_PROCESS_NOT_LIVE,
            "user_action",
        )
    if not hook_ready:
        return (
            SESSION_STATE_HOOK_NOT_READY,
            CUSTOM_CODEX_AUTH_SESSION_HOOK_NOT_READY,
            "user_action",
        )
    if api_key_only:
        return (
            SESSION_STATE_API_KEY_ONLY,
            CUSTOM_CODEX_AUTH_SESSION_API_KEY_ONLY,
            "user_action",
        )
    if logged_in_ui_session_proven:
        return (SESSION_STATE_READY, CUSTOM_CODEX_AUTH_SESSION_OK, "none")
    if login_required:
        return (
            SESSION_STATE_LOGIN_REQUIRED,
            CUSTOM_CODEX_AUTH_SESSION_LOGIN_REQUIRED,
            "user_action",
        )
    return (SESSION_STATE_UNKNOWN, CUSTOM_CODEX_AUTH_SESSION_UNKNOWN, "retry")


def build_custom_codex_auth_session_readiness_packet(
    *,
    paths: RuntimePaths,
    custom_user_data_dir: str | None = None,
    process_inventory: Mapping[str, Any] | None = None,
    process_inventory_live: bool = True,
    hook_readiness_packet: Mapping[str, Any] | None = None,
    account_read_metadata: Mapping[str, Any] | None = None,
    probe_hook_readiness: bool = True,
    probe_account_app_server: bool = True,
) -> dict[str, Any]:
    user_data_dir = custom_user_data_dir or _default_custom_user_data_dir(paths)
    if process_inventory is None:
        process_inventory = collect_codex_process_inventory(
            custom_user_data_dir=user_data_dir
        )
        process_inventory_live = True
    process_observation = _process_inventory_observation(
        process_inventory,
        process_inventory_live=process_inventory_live,
    )
    auth = _read_auth_file_classification(paths.auth_file)
    if hook_readiness_packet is None and probe_hook_readiness:
        hook_readiness_packet = build_user_prompt_submit_readiness_packet(
            paths=paths,
            probe_codex_app_server=True,
        )
    hook_readiness_packet = hook_readiness_packet or {}
    if account_read_metadata is None and probe_account_app_server:
        account_read_metadata = probe_codex_app_server_account_read(paths)
    account_read_metadata = dict(account_read_metadata or {
        "app_server_account_probe_attempted": False,
        **_account_read_summary_from_response({}),
    })

    process_ready = (
        process_observation.get("process_inventory_live") is True
        and process_observation.get("wbp_clean_app_process_observed") is True
        and process_observation.get("wbp_clean_app_server_process_observed") is True
    )
    hook_trusted_ready = _hook_ready(hook_readiness_packet)
    account_type = str(account_read_metadata.get("app_server_account_type") or "")
    logged_in_ui_session_proven = (
        account_type == "chatgpt"
        and account_read_metadata.get("app_server_requires_openai_auth") is not True
        and account_read_metadata.get("app_server_account_response_has_error") is not True
    )
    api_key_only = bool(
        account_type == "apiKey"
        or (
            auth.get("auth_json_api_key_only") is True
            and not logged_in_ui_session_proven
        )
    )
    login_required = bool(
        not logged_in_ui_session_proven
        and not api_key_only
        and (
            account_read_metadata.get("app_server_requires_openai_auth") is True
            or account_read_metadata.get("app_server_account_type") == ""
            or auth.get("auth_mode") in {"missing", "missing_credentials", "invalid"}
        )
    )
    session_state, machine_error_code, operator_action = _machine_state(
        process_ready=process_ready,
        hook_ready=hook_trusted_ready,
        logged_in_ui_session_proven=logged_in_ui_session_proven,
        api_key_only=api_key_only,
        login_required=login_required,
    )
    ok = machine_error_code == CUSTOM_CODEX_AUTH_SESSION_OK

    blocking_reasons: list[str] = []
    if not process_ready:
        if process_observation.get("wbp_clean_app_process_observed") is not True:
            blocking_reasons.append("wbp_clean_app_process_not_observed")
        if process_observation.get("wbp_clean_app_server_process_observed") is not True:
            blocking_reasons.append("wbp_clean_app_server_process_not_observed")
        if process_observation.get("process_inventory_live") is not True:
            blocking_reasons.append("process_inventory_not_live")
    if not hook_trusted_ready:
        blocking_reasons.append("user_prompt_submit_hook_not_ready")
        blocking_reasons.extend(_safe_reasons(hook_readiness_packet.get("blocking_reasons")))
    if api_key_only:
        blocking_reasons.append("api_key_only_not_ui_session")
    elif login_required:
        blocking_reasons.append("custom_codex_login_required")
    elif not logged_in_ui_session_proven:
        blocking_reasons.append("custom_codex_auth_unknown")

    extra = {
        "schema_version": 1,
        "packet_kind": CUSTOM_CODEX_AUTH_SESSION_READINESS_PACKET_KIND,
        "session_state": session_state,
        "custom_user_data_dir_recorded": False,
        **process_observation,
        **auth,
        **account_read_metadata,
        "hook_readiness_probe_attempted": bool(hook_readiness_packet),
        "hook_readiness_packet_kind": str(hook_readiness_packet.get("packet_kind", ""))[:96],
        "hook_readiness_machine_error_code": str(
            hook_readiness_packet.get("machine_error_code", "")
        )[:128],
        "hook_readiness_trusted": hook_trusted_ready,
        "user_prompt_submit_hook_ready": hook_trusted_ready,
        "logged_in_ui_session_proven": logged_in_ui_session_proven,
        "custom_codex_login_required": login_required,
        "api_key_only": api_key_only,
        "api_key_only_counts_as_ui_session": False,
        "raw_account_payload_recorded": False,
        "auth_json_content_recorded": False,
        "secret_value_exposed": False,
        "browser_secret_intake": False,
        "browser_path_intake": False,
        "api_lane_called": False,
        "dispatch_attempted": False,
        "dispatch_proven": False,
        "fallback_used": False,
        "local_imitation_used": False,
        "native_codex_subagent_used_as_dip": False,
        "fresh_user_prompt_submit_ledger_proven": False,
        "custom_ui_origin_admitted": False,
        "product_ready": False,
        "does_not_prove_dispatch": True,
        "does_not_prove_product_ready": True,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "changed_files": [],
    }
    return packets.build_command_packet(
        ok=ok,
        human_message=(
            "Custom Codex has a logged-in ChatGPT UI session, trusted hook readiness, and live WBP Clean process evidence."
            if ok
            else "Custom Codex is not ready for fresh UserPromptSubmit ledger proof."
        ),
        machine_error_code=machine_error_code,
        liveness="healthy" if ok else "degraded",
        severity="recoverable",
        operator_action=operator_action,
        changed_files=[],
        effect=EFFECT_PROBE,
        extra=extra,
    )


def run_custom_codex_auth_session_readiness_command(
    *,
    paths: RuntimePaths,
    custom_user_data_dir: str | None = None,
    process_inventory_file: str | None = None,
    probe_hook_readiness: bool = True,
    probe_account_app_server: bool = True,
) -> dict[str, Any]:
    inventory, live = _read_process_inventory_file(
        Path(process_inventory_file).expanduser() if process_inventory_file else None
    )
    return build_custom_codex_auth_session_readiness_packet(
        paths=paths,
        custom_user_data_dir=custom_user_data_dir,
        process_inventory=inventory,
        process_inventory_live=live,
        probe_hook_readiness=probe_hook_readiness,
        probe_account_app_server=probe_account_app_server,
    )
