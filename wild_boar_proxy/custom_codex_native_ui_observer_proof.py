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


def run_native_ui_observer_proof_command(
    *,
    paths: RuntimePaths,
    prompt_text: str,
    request_id: str,
    expected_text: str,
    proof_dir: str | None = None,
    persistent_profile_id: str = DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    persistent_profile_base_dir: str | None = None,
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
    )
    packet.setdefault("native_ui_observer_packet_file_written", True)
    packet.setdefault("native_ui_observer_packet_file_path_recorded", False)
    packet.setdefault("native_ui_observer_packet_proven", packet.get("status") == "ok")
    packet.setdefault("exit_code", 0 if packet.get("status") == "ok" else 1)
    write_json_atomic(proof_root / NATIVE_UI_OBSERVER_PACKET_FILE_NAME, packet)
    return packet
