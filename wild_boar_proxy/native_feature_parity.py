# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Read-only Custom Codex native feature parity diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any


FAST_UNAVAILABLE_API_KEY_AUTH = "FAST_UNAVAILABLE_API_KEY_AUTH"
FAST_CONFIG_MISSING = "FAST_CONFIG_MISSING"
CHATGPT_AUTH_MISSING = "CHATGPT_AUTH_MISSING"
VOICE_STATUS_UNPROVEN = "VOICE_STATUS_UNPROVEN"
NATIVE_PARITY_PROVEN = "NATIVE_PARITY_PROVEN"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> tuple[str, str]:
    try:
        return path.read_text(encoding="utf-8"), ""
    except FileNotFoundError:
        return "", "missing"
    except OSError:
        return "", "unreadable"
    except UnicodeDecodeError:
        return "", "invalid_encoding"


def _json_payload(path: Path) -> tuple[dict[str, Any], str]:
    text, error = _read_text(path)
    if error:
        return {}, error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}, "invalid_json"
    if not isinstance(payload, dict):
        return {}, "not_object"
    return payload, ""


def _truthy_secret(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, str) and bool(value.strip())


def _tokens_contain_secret(tokens: Any) -> bool:
    if not isinstance(tokens, dict):
        return False
    for key in ("access_token", "refresh_token", "id_token", "auth_token"):
        value = tokens.get(key)
        if isinstance(value, str) and value.strip():
            return True
    nested = tokens.get("tokens")
    if isinstance(nested, dict):
        return _tokens_contain_secret(nested)
    return False


def _auth_summary(auth_file: Path) -> dict[str, Any]:
    payload, error = _json_payload(auth_file)
    if error:
        return {
            "auth_file_present": auth_file.exists(),
            "auth_file_readable": False,
            "auth_parse_error": error,
            "auth_mode": "missing" if error == "missing" else "invalid",
            "auth_mode_declared": "",
            "openai_api_key_present": False,
            "chatgpt_token_material_present": False,
            "raw_auth_recorded": False,
            "secret_value_recorded": False,
        }

    declared = str(payload.get("auth_mode") or "").strip().lower()
    has_api_key = _truthy_secret(payload, "OPENAI_API_KEY")
    has_chatgpt_token = (
        _truthy_secret(payload, "access_token")
        or _truthy_secret(payload, "refresh_token")
        or _truthy_secret(payload, "id_token")
        or _tokens_contain_secret(payload.get("tokens"))
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

    return {
        "auth_file_present": True,
        "auth_file_readable": True,
        "auth_parse_error": "",
        "auth_mode": auth_mode,
        "auth_mode_declared": declared,
        "openai_api_key_present": has_api_key,
        "chatgpt_token_material_present": has_chatgpt_token,
        "raw_auth_recorded": False,
        "secret_value_recorded": False,
    }


def _strip_inline_comment(value: str) -> str:
    in_quotes = False
    escaped = False
    result: list[str] = []
    for char in value:
        if escaped:
            result.append(char)
            escaped = False
            continue
        if char == "\\":
            result.append(char)
            escaped = True
            continue
        if char == '"':
            in_quotes = not in_quotes
            result.append(char)
            continue
        if char == "#" and not in_quotes:
            break
        result.append(char)
    return "".join(result).strip()


def _toml_scalar(raw_value: str) -> Any:
    value = _strip_inline_comment(raw_value)
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return value


def _config_summary(config_toml: Path) -> dict[str, Any]:
    text, error = _read_text(config_toml)
    if error:
        return {
            "config_present": config_toml.exists(),
            "config_readable": False,
            "config_parse_error": error,
            "base_url_configured": False,
            "service_tier_fast_configured": False,
            "features_fast_mode_enabled": False,
            "fast_default_configured": False,
            "raw_config_recorded": False,
        }

    section = ""
    top_level: dict[str, Any] = {}
    features: dict[str, Any] = {}
    base_url_configured = False
    section_pattern = re.compile(r"^\[([^\]]+)\]\s*$")
    assignment_pattern = re.compile(r"^([A-Za-z0-9_.-]+)\s*=\s*(.*)$")
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        section_match = section_pattern.match(stripped)
        if section_match:
            section = section_match.group(1).strip()
            continue
        assignment_match = assignment_pattern.match(stripped)
        if not assignment_match:
            continue
        key = assignment_match.group(1).strip()
        value = _toml_scalar(assignment_match.group(2))
        if key == "base_url":
            base_url_configured = True
        if section == "":
            top_level[key] = value
        if section == "features":
            features[key] = value

    service_tier_fast = str(top_level.get("service_tier") or "").strip().lower() == "fast"
    fast_mode_enabled = features.get("fast_mode") is True
    return {
        "config_present": True,
        "config_readable": True,
        "config_parse_error": "",
        "base_url_configured": base_url_configured,
        "service_tier_fast_configured": service_tier_fast,
        "features_fast_mode_enabled": fast_mode_enabled,
        "fast_default_configured": service_tier_fast and fast_mode_enabled,
        "raw_config_recorded": False,
    }


def _launcher_summary(launcher_script: Path) -> dict[str, Any]:
    text, error = _read_text(launcher_script)
    if error:
        return {
            "launcher_present": launcher_script.exists(),
            "launcher_readable": False,
            "launcher_parse_error": error,
            "exports_codex_home": False,
            "exports_home_app_home": False,
            "exports_openai_api_key": False,
            "conditional_openai_api_key_export": False,
            "unsets_openai_api_key_for_chatgpt": False,
            "exports_codex_access_token": False,
            "uses_electron_user_data_dir": False,
            "uses_hash_identical_app_copy_policy": False,
            "raw_launcher_recorded": False,
        }

    exports_openai_api_key = "export OPENAI_API_KEY" in text
    return {
        "launcher_present": True,
        "launcher_readable": True,
        "launcher_parse_error": "",
        "exports_codex_home": 'export CODEX_HOME="$PROFILE_DIR"' in text,
        "exports_home_app_home": 'export HOME="$APP_HOME"' in text,
        "exports_openai_api_key": exports_openai_api_key,
        "conditional_openai_api_key_export": (
            "AUTH_MODE=" in text
            and "OPENAI_API_KEY_FROM_AUTH=" in text
            and 'if [ "$AUTH_MODE" = "chatgpt" ]; then' in text
        ),
        "unsets_openai_api_key_for_chatgpt": 'unset OPENAI_API_KEY' in text,
        "exports_codex_access_token": "CODEX_ACCESS_TOKEN" in text,
        "uses_electron_user_data_dir": '"--user-data-dir=$APP_USER_DATA_DIR"' in text,
        "uses_hash_identical_app_copy_policy": (
            "primary_bin_hash=" in text and "preferred_asar_hash=" in text
        ),
        "raw_launcher_recorded": False,
    }


def _sha256_or_empty(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _app_identity_summary() -> dict[str, Any]:
    primary = Path("/Applications/Codex.app")
    preferred = Path.home() / "Applications" / "Codex WBP Clean.app"
    primary_bin = primary / "Contents" / "MacOS" / "Codex"
    primary_asar = primary / "Contents" / "Resources" / "app.asar"
    preferred_bin = preferred / "Contents" / "MacOS" / "Codex"
    preferred_asar = preferred / "Contents" / "Resources" / "app.asar"

    primary_present = primary_bin.exists() and primary_asar.exists()
    preferred_present = preferred_bin.exists() and preferred_asar.exists()
    primary_bin_hash = _sha256_or_empty(primary_bin)
    primary_asar_hash = _sha256_or_empty(primary_asar)
    preferred_bin_hash = _sha256_or_empty(preferred_bin)
    preferred_asar_hash = _sha256_or_empty(preferred_asar)
    compared = bool(primary_bin_hash and primary_asar_hash and preferred_bin_hash and preferred_asar_hash)

    return {
        "primary_codex_app_observed": primary_present,
        "preferred_clean_app_observed": preferred_present,
        "hash_comparison_run": compared,
        "preferred_binary_matches_primary": compared and primary_bin_hash == preferred_bin_hash,
        "preferred_asar_matches_primary": compared and primary_asar_hash == preferred_asar_hash,
        "binary_hash_recorded": False,
        "asar_hash_recorded": False,
        "app_path_recorded": False,
    }


def _eligibility(
    auth: dict[str, Any],
    config: dict[str, Any],
    launcher: dict[str, Any],
) -> dict[str, Any]:
    auth_mode = str(auth.get("auth_mode") or "")
    chatgpt_auth = (
        auth_mode in {"chatgpt", "mixed"}
        and auth.get("chatgpt_token_material_present") is True
    )
    api_key_only = auth_mode == "apikey"
    fast_configured = config.get("fast_default_configured") is True
    launcher_preserves_chatgpt_auth = (
        launcher.get("conditional_openai_api_key_export") is True
        and launcher.get("unsets_openai_api_key_for_chatgpt") is True
    )

    if api_key_only:
        fast_reason = FAST_UNAVAILABLE_API_KEY_AUTH
    elif not chatgpt_auth:
        fast_reason = CHATGPT_AUTH_MISSING
    elif not fast_configured:
        fast_reason = FAST_CONFIG_MISSING
    elif not launcher_preserves_chatgpt_auth:
        fast_reason = "CHATGPT_LAUNCHER_AUTH_POLICY_UNPROVEN"
    else:
        fast_reason = "OK"

    fast_proven = fast_reason == "OK"
    voice_reason = (
        "VOICE_REQUIRES_NATIVE_PERMISSION_CHECK"
        if chatgpt_auth
        else VOICE_STATUS_UNPROVEN
    )
    voice_proven = False
    parity_proven = fast_proven and voice_proven
    if parity_proven:
        machine_error_code = "OK"
    elif not fast_proven:
        machine_error_code = fast_reason
    else:
        machine_error_code = VOICE_STATUS_UNPROVEN

    return {
        "chatgpt_auth_required_for_native_parity": True,
        "api_key_auth_limits_native_features": api_key_only,
        "fast_eligibility_proven": fast_proven,
        "fast_status": "proven" if fast_proven else "blocked",
        "fast_blocked_reason_code": "" if fast_proven else fast_reason,
        "voice_eligibility_proven": voice_proven,
        "voice_status": "unproven",
        "voice_blocked_reason_code": voice_reason,
        "voice_requires_native_permission_check": True,
        "voice_is_not_locally_imitated": True,
        "native_feature_parity_proven": parity_proven,
        "machine_error_code": machine_error_code,
    }


def build_native_feature_parity_packet(paths: Any) -> dict[str, Any]:
    """Build a read-only packet for Custom Codex Fast/voice feature parity."""

    profile_dir = Path(paths.profile_dir)
    original_profile_dir = Path.home() / ".codex"
    try:
        custom_profile_isolated = (
            profile_dir.expanduser().resolve(strict=False)
            != original_profile_dir.expanduser().resolve(strict=False)
        )
    except OSError:
        custom_profile_isolated = False
    auth = _auth_summary(Path(paths.auth_file))
    config = _config_summary(Path(paths.config_toml))
    launcher = _launcher_summary(Path(paths.launcher_script))
    app_identity = _app_identity_summary()
    eligibility = _eligibility(auth, config, launcher)
    parity_proven = eligibility["native_feature_parity_proven"] is True
    machine_error_code = str(eligibility["machine_error_code"])

    return {
        "schema_version": 1,
        "packet_kind": "custom_codex_native_feature_parity",
        "effect": "read",
        "status": "ok" if parity_proven else "blocked",
        "exit_code": 0 if parity_proven else 1,
        "machine_error_code": "OK" if parity_proven else machine_error_code,
        "human_message": (
            "Custom Codex native Fast/voice parity is proven."
            if parity_proven
            else "Custom Codex native Fast/voice parity is not proven by the current profile."
        ),
        "captured_at_utc": _utc_now(),
        "changed_files": [],
        "operator_action": "none" if parity_proven else "user_action",
        "operator_action_reason_code": "OK" if parity_proven else machine_error_code,
        "next_action": "none" if parity_proven else "user_action",
        "profile_id": profile_dir.name,
        "profile_present": profile_dir.exists(),
        "custom_profile_isolated": custom_profile_isolated,
        "profile_is_original_codex_profile": not custom_profile_isolated,
        "original_codex_profile_read": False,
        "original_codex_profile_touched": False,
        "browser_path_authority": False,
        "auth": auth,
        "config": config,
        "launcher": launcher,
        "app_identity": app_identity,
        "eligibility": eligibility,
        "fast_eligibility_proven": eligibility["fast_eligibility_proven"],
        "voice_eligibility_proven": eligibility["voice_eligibility_proven"],
        "native_feature_parity_proven": parity_proven,
        "no_secret_exposed": True,
        "secret_value_exposed": False,
        "raw_auth_recorded": False,
        "raw_config_recorded": False,
        "raw_launcher_recorded": False,
        "raw_profile_content_recorded": False,
        "raw_backend_details_exposed": False,
        "does_not_patch_codex_binary": app_identity["primary_codex_app_observed"],
        "does_not_patch_codex_asar": app_identity["primary_codex_app_observed"],
        "codex_integrity_claim_scope": (
            "primary_app_observed_without_repo_patch"
            if app_identity["primary_codex_app_observed"]
            else "codex_app_not_observed"
        ),
        "does_not_imitate_fast_or_voice": True,
    }


__all__ = [
    "CHATGPT_AUTH_MISSING",
    "FAST_CONFIG_MISSING",
    "FAST_UNAVAILABLE_API_KEY_AUTH",
    "NATIVE_PARITY_PROVEN",
    "VOICE_STATUS_UNPROVEN",
    "build_native_feature_parity_packet",
]
