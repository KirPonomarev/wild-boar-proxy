# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from types import SimpleNamespace
import json
from pathlib import Path
import tempfile
import unittest

from wild_boar_proxy.native_feature_parity import (
    FAST_UNAVAILABLE_API_KEY_AUTH,
    VOICE_STATUS_UNPROVEN,
    build_native_feature_parity_packet,
)


def _paths(root: Path) -> SimpleNamespace:
    profile_dir = root / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        profile_dir=profile_dir,
        auth_file=profile_dir / "auth.json",
        config_toml=profile_dir / "config.toml",
        launcher_script=profile_dir / "codex-custom-launch.sh",
    )


def _write_launcher(path: Path, *, conditional_auth: bool) -> None:
    if conditional_auth:
        path.write_text(
            "\n".join(
                [
                    'export CODEX_HOME="$PROFILE_DIR"',
                    'export HOME="$APP_HOME"',
                    'AUTH_MODE="$(python3 - "$AUTH_FILE")"',
                    'OPENAI_API_KEY_FROM_AUTH="$(python3 - "$AUTH_FILE")"',
                    'if [ "$AUTH_MODE" = "chatgpt" ]; then',
                    "  unset OPENAI_API_KEY",
                    "elif [ -n \"$OPENAI_API_KEY_FROM_AUTH\" ]; then",
                    '  export OPENAI_API_KEY="$OPENAI_API_KEY_FROM_AUTH"',
                    "fi",
                    '"--user-data-dir=$APP_USER_DATA_DIR"',
                    "primary_bin_hash=",
                    "preferred_asar_hash=",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            "\n".join(
                [
                    'export CODEX_HOME="$PROFILE_DIR"',
                    'export HOME="$APP_HOME"',
                    'export OPENAI_API_KEY="$(python3 - "$AUTH_FILE")"',
                    '"--user-data-dir=$APP_USER_DATA_DIR"',
                    "primary_bin_hash=",
                    "preferred_asar_hash=",
                ]
            )
            + "\n",
            encoding="utf-8",
        )


class NativeFeatureParityTests(unittest.TestCase):
    def test_api_key_profile_blocks_fast_without_recording_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            sentinel = "NATIVE_FEATURE_PARITY_TEST_VALUE"
            paths.auth_file.write_text(
                json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": sentinel}) + "\n",
                encoding="utf-8",
            )
            paths.config_toml.write_text(
                "\n".join(
                    [
                        'model = "gpt-5.5"',
                        'model_provider = "cliproxy"',
                        "",
                        "[model_providers.cliproxy]",
                        'base_url = "http://127.0.0.1:8318/v1"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            _write_launcher(paths.launcher_script, conditional_auth=False)

            packet = build_native_feature_parity_packet(paths)
            serialized = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], FAST_UNAVAILABLE_API_KEY_AUTH)
        self.assertEqual(packet["auth"]["auth_mode"], "apikey")
        self.assertTrue(packet["auth"]["openai_api_key_present"])
        self.assertFalse(packet["fast_eligibility_proven"])
        self.assertFalse(packet["voice_eligibility_proven"])
        self.assertFalse(packet["native_feature_parity_proven"])
        self.assertFalse(packet["raw_auth_recorded"])
        self.assertFalse(packet["secret_value_exposed"])
        self.assertNotIn(sentinel, serialized)

    def test_chatgpt_fast_config_does_not_claim_voice_without_native_permission_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            sentinel = "CHATGPT_TOKEN_TEST_VALUE"
            paths.auth_file.write_text(
                json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": sentinel}})
                + "\n",
                encoding="utf-8",
            )
            paths.config_toml.write_text(
                "\n".join(
                    [
                        'model = "gpt-5.5"',
                        'service_tier = "fast"',
                        "",
                        "[features]",
                        "fast_mode = true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            _write_launcher(paths.launcher_script, conditional_auth=True)

            packet = build_native_feature_parity_packet(paths)
            serialized = json.dumps(packet, ensure_ascii=False)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], VOICE_STATUS_UNPROVEN)
        self.assertEqual(packet["auth"]["auth_mode"], "chatgpt")
        self.assertTrue(packet["config"]["fast_default_configured"])
        self.assertTrue(packet["launcher"]["conditional_openai_api_key_export"])
        self.assertTrue(packet["fast_eligibility_proven"])
        self.assertFalse(packet["voice_eligibility_proven"])
        self.assertTrue(packet["eligibility"]["voice_requires_native_permission_check"])
        self.assertFalse(packet["native_feature_parity_proven"])
        self.assertNotIn(sentinel, serialized)

    def test_chatgpt_fast_config_with_old_launcher_blocks_on_launcher_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            paths.auth_file.write_text(
                '{"auth_mode":"chatgpt","tokens":{"access_token":"TOKEN_VALUE"}}\n',
                encoding="utf-8",
            )
            paths.config_toml.write_text(
                'service_tier = "fast"\n\n[features]\nfast_mode = true\n',
                encoding="utf-8",
            )
            _write_launcher(paths.launcher_script, conditional_auth=False)

            packet = build_native_feature_parity_packet(paths)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "CHATGPT_LAUNCHER_AUTH_POLICY_UNPROVEN",
        )
        self.assertEqual(packet["operator_action"], "user_action")
        self.assertEqual(packet["operator_action_reason_code"], packet["machine_error_code"])
        self.assertEqual(packet["next_action"], "user_action")
        self.assertFalse(packet["fast_eligibility_proven"])

    def test_missing_chatgpt_auth_blocks_native_parity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            paths.auth_file.write_text("{}\n", encoding="utf-8")
            paths.config_toml.write_text(
                'service_tier = "fast"\n\n[features]\nfast_mode = true\n',
                encoding="utf-8",
            )
            _write_launcher(paths.launcher_script, conditional_auth=True)

            packet = build_native_feature_parity_packet(paths)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "CHATGPT_AUTH_MISSING")
        self.assertFalse(packet["fast_eligibility_proven"])
        self.assertFalse(packet["native_feature_parity_proven"])

    def test_declared_chatgpt_without_token_material_does_not_prove_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            paths.auth_file.write_text('{"auth_mode":"chatgpt"}\n', encoding="utf-8")
            paths.config_toml.write_text(
                'service_tier = "fast"\n\n[features]\nfast_mode = true\n',
                encoding="utf-8",
            )
            _write_launcher(paths.launcher_script, conditional_auth=True)

            packet = build_native_feature_parity_packet(paths)

        self.assertEqual(packet["auth"]["auth_mode"], "chatgpt")
        self.assertFalse(packet["auth"]["chatgpt_token_material_present"])
        self.assertEqual(packet["machine_error_code"], "CHATGPT_AUTH_MISSING")
        self.assertFalse(packet["fast_eligibility_proven"])

    def test_original_codex_profile_path_does_not_count_as_custom_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            paths.profile_dir = Path.home() / ".codex"
            paths.auth_file.write_text(
                '{"auth_mode":"chatgpt","tokens":{"access_token":"secret"}}\n',
                encoding="utf-8",
            )
            paths.config_toml.write_text(
                'service_tier = "fast"\n\n[features]\nfast_mode = true\n',
                encoding="utf-8",
            )
            _write_launcher(paths.launcher_script, conditional_auth=True)

            packet = build_native_feature_parity_packet(paths)

        self.assertFalse(packet["custom_profile_isolated"])
        self.assertTrue(packet["profile_is_original_codex_profile"])


if __name__ == "__main__":
    unittest.main()
