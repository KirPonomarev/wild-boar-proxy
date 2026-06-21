# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .native_window_probe import (
    DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    submit_custom_native_window_prompt_packet,
)
from .runtime import RuntimePaths, write_json_atomic


NATIVE_UI_OBSERVER_PACKET_FILE_NAME = "native-ui-observer.packet.json"


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "codex-runner" / "native-ui-observer-proof" / stamp


def _native_ui_observer_packet_proven(packet: dict[str, Any]) -> bool:
    return (
        packet.get("status") == "ok"
        and packet.get("prompt_submitted") is True
        and packet.get("native_prompt_turn_accepted") is True
        and packet.get("assistant_turn_machine_error_code") == "OK"
        and packet.get("native_free_text_observer_machine_error_code") == "OK"
        and packet.get("custom_response_exact_token_observed") is True
        and packet.get("custom_response_bound_to_request") is True
        and packet.get("native_codex_subagent_used_as_dip") is not True
        and packet.get("fallback_used") is not True
        and packet.get("local_imitation_used") is not True
    )


def run_native_ui_observer_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    request_id: str,
    expected_text: str,
    proof_dir: str | None = None,
    persistent_profile_id: str = DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    persistent_profile_base_dir: str | None = None,
    observer_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    proof_root = _proof_root(paths, proof_dir)
    proof_root.mkdir(parents=True, exist_ok=True)
    base_dir = Path(persistent_profile_base_dir).expanduser() if persistent_profile_base_dir else None
    packet = submit_custom_native_window_prompt_packet(
        prompt=prompt_text,
        request_id=request_id,
        expected_text=expected_text,
        persistent_profile_id=persistent_profile_id,
        persistent_profile_base_dir=base_dir,
        **(
            {"observer_timeout_seconds": observer_timeout_seconds}
            if observer_timeout_seconds is not None
            else {}
        ),
    )
    packet["native_ui_observer_packet_file_written"] = True
    packet["native_ui_observer_packet_file_path_recorded"] = False
    packet["native_ui_observer_packet_proven"] = _native_ui_observer_packet_proven(packet)
    packet["exit_code"] = 0 if packet["native_ui_observer_packet_proven"] else 1
    write_json_atomic(proof_root / NATIVE_UI_OBSERVER_PACKET_FILE_NAME, packet)
    return packet
