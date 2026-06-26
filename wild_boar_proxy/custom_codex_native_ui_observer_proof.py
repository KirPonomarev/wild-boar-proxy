# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from .native_window_probe import (
    DEFAULT_PERSISTENT_CUSTOM_PROFILE_ID,
    launch_custom_native_app_packet,
    submit_custom_native_window_prompt_packet,
)
from .native_filesystem_probe import DEFAULT_CUSTOM_NATIVE_MODEL
from .runtime import RuntimePaths, write_json_atomic


NATIVE_UI_OBSERVER_PACKET_FILE_NAME = "native-ui-observer.packet.json"
NATIVE_UI_AUTO_LAUNCH_PACKET_FILE_NAME = "native-ui-auto-launch.packet.json"
DEFAULT_AUTO_LAUNCH_ENDPOINT = "http://127.0.0.1:8318/v1"
DEFAULT_AUTO_LAUNCH_MODEL = DEFAULT_CUSTOM_NATIVE_MODEL

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,256}$")

_AUTO_LAUNCH_MACHINE_ERROR_CODES = frozenset(
    {
        "CUSTOM_CODEX_CUSTOM_PROCESS_NOT_FOUND",
        "CUSTOM_CODEX_WINDOW_USABILITY_NOT_PROVEN",
        "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN",
    }
)


def _proof_root(paths: RuntimePaths, raw_proof_dir: str | None) -> Path:
    if raw_proof_dir:
        return Path(raw_proof_dir).expanduser()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return paths.managed_dir / "codex-runner" / "native-ui-observer-proof" / stamp


def _valid_request_id(value: str) -> bool:
    return bool(_REQUEST_ID_RE.fullmatch(str(value or "")))


def _native_ui_observer_proof_fields(
    packet: dict[str, Any],
    *,
    request_id: str,
    expected_text: str,
) -> dict[str, Any]:
    request_id = str(request_id or "")
    expected_text = str(expected_text or "")
    request_id_valid = _valid_request_id(request_id)
    packet_request_id_matches_input = (
        request_id_valid and packet.get("request_id") == request_id
    )
    expected_text_contains_request_id = bool(
        request_id_valid and request_id in expected_text
    )
    base_submit_ready = (
        packet.get("status") == "ok"
        and packet.get("prompt_submitted") is True
        and packet.get("native_prompt_turn_accepted") is True
        and packet.get("native_codex_subagent_used_as_dip") is not True
        and packet.get("fallback_used") is not True
        and packet.get("local_imitation_used") is not True
    )
    exact_token_observed = (
        packet.get("custom_codex_response_text_read_proven") is True
        and packet.get("custom_response_exact_token_observed") is True
    )
    strict_request_bound = (
        base_submit_ready
        and request_id_valid
        and packet_request_id_matches_input
        and expected_text_contains_request_id
        and packet.get("assistant_turn_machine_error_code") == "OK"
        and packet.get("native_free_text_observer_machine_error_code") == "OK"
        and packet.get("custom_response_bound_to_request") is True
    )
    smoke_only = exact_token_observed and not strict_request_bound
    proof_strength = (
        "strict_request_bound"
        if strict_request_bound
        else "exact_token_smoke_only"
        if smoke_only
        else "not_proven"
    )
    proof_machine_error_code = "OK"
    if not strict_request_bound:
        if not base_submit_ready:
            proof_machine_error_code = "CUSTOM_NATIVE_UI_OBSERVER_SUBMIT_NOT_PROVEN"
        elif not request_id_valid:
            proof_machine_error_code = "CUSTOM_NATIVE_UI_REQUEST_ID_INVALID"
        elif not packet_request_id_matches_input:
            proof_machine_error_code = (
                "CUSTOM_NATIVE_UI_OBSERVER_REQUEST_ID_MISMATCH"
            )
        elif smoke_only and not expected_text_contains_request_id:
            proof_machine_error_code = (
                "CUSTOM_NATIVE_UI_OBSERVER_EXPECTED_TEXT_NOT_REQUEST_BOUND"
            )
        elif smoke_only:
            proof_machine_error_code = "CUSTOM_NATIVE_UI_OBSERVER_EXACT_TOKEN_SMOKE_ONLY"
        elif packet.get("assistant_turn_machine_error_code") != "OK":
            proof_machine_error_code = (
                "CUSTOM_NATIVE_UI_OBSERVER_ASSISTANT_TURN_NOT_PROVEN"
            )
        elif packet.get("native_free_text_observer_machine_error_code") != "OK":
            proof_machine_error_code = (
                "CUSTOM_NATIVE_UI_OBSERVER_REQUEST_BOUND_RESPONSE_NOT_PROVEN"
            )
        else:
            proof_machine_error_code = "CUSTOM_NATIVE_UI_OBSERVER_NOT_PROVEN"
    return {
        "native_ui_request_id_valid": request_id_valid,
        "native_ui_observer_packet_request_id_matches_input": (
            packet_request_id_matches_input
        ),
        "native_ui_expected_text_contains_request_id": (
            expected_text_contains_request_id
        ),
        "native_ui_exact_token_smoke_observed": exact_token_observed,
        "native_ui_strict_request_bound_observed": strict_request_bound,
        "native_ui_observer_proof_strength": proof_strength,
        "native_ui_observer_proof_machine_error_code": proof_machine_error_code,
        "native_ui_observer_packet_proven": strict_request_bound,
    }


def _should_auto_launch_after_submit(packet: dict[str, Any]) -> bool:
    if packet.get("machine_error_code") not in _AUTO_LAUNCH_MACHINE_ERROR_CODES:
        return False
    if packet.get("native_window_observed") is True and packet.get("input_capable_ui_observed") is True:
        return False
    return True


def _auto_launch_summary_fields(
    *,
    enabled: bool,
    attempted: bool,
    launch_packet: dict[str, Any] | None,
    launch_packet_written: bool,
    owner_authorization_phrase: str | None,
) -> dict[str, Any]:
    launch = dict(launch_packet or {})
    return {
        "native_auto_launch_enabled": enabled,
        "native_auto_launch_attempted": attempted,
        "native_auto_launch_status": str(launch.get("status") or ""),
        "native_auto_launch_machine_error_code": str(
            launch.get("machine_error_code") or ""
        ),
        "native_auto_launch_process_started": launch.get("process_started") is True,
        "native_auto_launch_reused_existing_window": (
            launch.get("reused_existing_window") is True
            or launch.get("existing_custom_window_reused") is True
        ),
        "native_auto_launch_running_status": launch.get("running_status") is True,
        "native_auto_launch_native_app_usable": launch.get("native_app_usable") is True,
        "native_auto_launch_packet_file_written": launch_packet_written,
        "native_auto_launch_packet_file_path_recorded": False,
        "native_auto_launch_owner_authorization_phrase_present": bool(
            owner_authorization_phrase
        ),
        "native_auto_launch_owner_authorization_phrase_recorded": False,
        "native_auto_launch_stable_runtime_generated_config_override_used": (
            launch.get("stable_runtime_generated_config_override_used") is True
        ),
        "native_auto_launch_stable_runtime_generated_config_file_present": (
            launch.get("stable_runtime_generated_config_file_present") is True
        ),
        "native_auto_launch_stable_runtime_generated_config_file_path_recorded": False,
        "native_auto_launch_stable_runtime_generated_config_default_present": (
            launch.get("stable_runtime_generated_config_default_present") is True
        ),
        "native_auto_launch_observed_stable_config_fallback_used": (
            launch.get("observed_stable_config_fallback_used") is True
        ),
        "native_auto_launch_observed_stable_config_file_present": (
            launch.get("observed_stable_config_file_present") is True
        ),
        "native_auto_launch_token_config_file_present": (
            launch.get("token_config_file_present") is True
        ),
        "native_auto_launch_token_config_source_kind": str(
            launch.get("token_config_source_kind") or ""
        ),
        "native_auto_launch_local_token_present": launch.get("local_token_present") is True,
        "native_auto_launch_local_token_value_recorded": False,
    }


def _launch_packet_allows_retry(launch_packet: dict[str, Any]) -> bool:
    return bool(
        (
            launch_packet.get("status") == "ok"
            and (
                launch_packet.get("native_app_usable") is True
                or launch_packet.get("running_status") is True
            )
        )
        or (
            launch_packet.get("machine_error_code")
            == "CUSTOM_NATIVE_WINDOW_USABILITY_NOT_PROVEN"
            and launch_packet.get("process_started") is True
            and launch_packet.get("native_window_observed") is True
        )
        or (
            launch_packet.get("machine_error_code")
            == "CUSTOM_NATIVE_WINDOW_NOT_PROVEN"
            and launch_packet.get("process_started") is True
            and (
                launch_packet.get("running_status") is True
                or launch_packet.get("cleanup_deferred_while_running") is True
            )
        )
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
    auto_launch_custom_codex: bool = False,
    auto_launch_endpoint: str = DEFAULT_AUTO_LAUNCH_ENDPOINT,
    auto_launch_model: str = DEFAULT_AUTO_LAUNCH_MODEL,
    auto_launch_owner_authorization_phrase: str | None = None,
    auto_launch_repo_root: str | None = None,
    auto_launch_stable_runtime_generated_config_file: str | None = None,
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
    launch_packet: dict[str, Any] | None = None
    launch_packet_written = False
    auto_launch_attempted = False
    if auto_launch_custom_codex and _should_auto_launch_after_submit(packet):
        auto_launch_attempted = True
        launch_packet = launch_custom_native_app_packet(
            repo_root=Path(auto_launch_repo_root).expanduser()
            if auto_launch_repo_root
            else Path.cwd(),
            endpoint=auto_launch_endpoint,
            model=auto_launch_model,
            owner_authorization_phrase=auto_launch_owner_authorization_phrase,
            persistent_profile_id=persistent_profile_id,
            persistent_profile_base_dir=base_dir,
            keep_running_on_window_observed=True,
            reuse_existing_window_if_present=False,
            stable_runtime_generated_config_file=(
                Path(auto_launch_stable_runtime_generated_config_file).expanduser()
                if auto_launch_stable_runtime_generated_config_file
                else None
            ),
        )
        write_json_atomic(
            proof_root / NATIVE_UI_AUTO_LAUNCH_PACKET_FILE_NAME,
            launch_packet,
        )
        launch_packet_written = True
        if _launch_packet_allows_retry(launch_packet):
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
            packet["native_ui_observer_retry_after_auto_launch"] = True
    packet.update(
        _auto_launch_summary_fields(
            enabled=auto_launch_custom_codex,
            attempted=auto_launch_attempted,
            launch_packet=launch_packet,
            launch_packet_written=launch_packet_written,
            owner_authorization_phrase=auto_launch_owner_authorization_phrase,
        )
    )
    packet["native_ui_observer_packet_file_written"] = True
    packet["native_ui_observer_packet_file_path_recorded"] = False
    packet.update(
        _native_ui_observer_proof_fields(
            packet,
            request_id=request_id,
            expected_text=expected_text,
        )
    )
    packet["exit_code"] = 0 if packet["native_ui_observer_packet_proven"] else 1
    write_json_atomic(proof_root / NATIVE_UI_OBSERVER_PACKET_FILE_NAME, packet)
    return packet
