# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bounded local token contract for Codex auth.command integration."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .runtime import RuntimeErrorInfo, RuntimePaths, build_command_payload

TOKEN_OUTPUT_SHAPE = "plain_token_stdout"
TOKEN_SCOPE = "owner_local_listener"
TOKEN_SOURCE_KIND = "stable_runtime_generated_config"
TOKEN_AUDIT_STAMP_ENV = "WBP_TOKEN_COMMAND_AUDIT_STAMP_PATH"


def _extract_local_listener_token(config_path: Path) -> str:
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
    raise RuntimeErrorInfo(
        "Stable runtime generated config does not contain a bounded local listener token shape.",
        machine_error_code="WBP_TOKEN_SOURCE_INVALID",
        operator_action="repair_runtime",
        severity="high",
    )


def emit_local_token(paths: RuntimePaths) -> str:
    config_path = paths.stable_runtime_generated_config_file.expanduser()
    if not config_path.exists():
        raise RuntimeErrorInfo(
            "Stable runtime generated config is missing for token command.",
            machine_error_code="WBP_TOKEN_SOURCE_UNAVAILABLE",
            operator_action="repair_runtime",
            severity="high",
        )
    _write_audit_stamp_if_requested()
    return _extract_local_listener_token(config_path)


def token_status_payload(paths: RuntimePaths) -> dict[str, Any]:
    config_path = paths.stable_runtime_generated_config_file.expanduser()
    if not config_path.exists():
        raise RuntimeErrorInfo(
            "Stable runtime generated config is missing for token command.",
            machine_error_code="WBP_TOKEN_SOURCE_UNAVAILABLE",
            operator_action="repair_runtime",
            severity="high",
        )
    _token = _extract_local_listener_token(config_path)
    return build_command_payload(
        ok=True,
        human_message="Local WBP token contract collected without exposing bearer material.",
        machine_error_code="OK",
        liveness="not_applicable",
        severity="recoverable",
        operator_action="none",
        changed_files=[],
        extra={
            "data": {
                "token_source_kind": TOKEN_SOURCE_KIND,
                "token_output_shape": TOKEN_OUTPUT_SHAPE,
                "token_present": True,
                "token_emitted": False,
                "secret_value_exposed": False,
                "browser_secret_intake": False,
                "browser_path_intake": False,
                "scope": TOKEN_SCOPE,
                "local_only": True,
                "short_lived": False,
                "config_path": str(config_path),
            }
        },
    )


def _write_audit_stamp_if_requested() -> None:
    raw_path = os.environ.get(TOKEN_AUDIT_STAMP_ENV, "").strip()
    if not raw_path:
        return
    path = Path(raw_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("invoked\n", encoding="utf-8")
