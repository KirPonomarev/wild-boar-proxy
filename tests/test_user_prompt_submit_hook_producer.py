# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from wild_boar_proxy import real_custom_codex_hook_proof as proof
from wild_boar_proxy import router_hook_entry as hook_entry
from wild_boar_proxy import user_prompt_submit_hook_producer as producer
from wild_boar_proxy.core import packets
from wild_boar_proxy.natural_intent_contract import packet_contains_text
from wild_boar_proxy.runtime import RuntimePaths


ROOT = Path(__file__).resolve().parents[1]
ROUTE_ID = "wbp-deepseek-chat"
PROMPT = "Codex, дай задачу DIP: сделай hook ledger."


def _runtime_context(*, allowed_routes: list[str] | None = None) -> dict[str, object]:
    allowed_routes = [ROUTE_ID] if allowed_routes is None else allowed_routes
    return {
        "schema_version": 1,
        "packet_kind": "codex_custom_native_agent_runtime_context",
        "context_truth_source": "server_launch_selection_packet",
        "agent_bindings_status": "ok",
        "agent_bindings": [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "role": "orchestrator",
                "aliases": ["Codex", "Agent 1"],
                "lane": "primary_chatgpt",
                "enabled": True,
                "model_id": "gpt-5.4",
                "allowed_actions": ["plan", "inspect"],
            },
            {
                "agent_id": "dip",
                "display_name": "DIP",
                "role": "coding_agent",
                "aliases": ["DIP", "Agent 2", "Worker"],
                "lane": "api_route",
                "enabled": True,
                "route_id": ROUTE_ID,
                "allowed_actions": ["implementation_help"],
            },
        ],
        "alias_to_agent_id": {
            "Codex": "codex",
            "Agent 1": "codex",
            "DIP": "dip",
            "Agent 2": "dip",
        },
        "agent_id_to_route": {"dip": ROUTE_ID},
        "agent_id_to_model": {"codex": "gpt-5.4"},
        "allowed_api_route_ids": allowed_routes,
        "forbidden_stale_route_ids": ["wbp-deepseek-v3"],
        "secret_value_exposed": False,
        "raw_backend_details_exposed": False,
    }


def _paths(root: Path) -> RuntimePaths:
    profile = root / "profile"
    managed = profile / "managed"
    return RuntimePaths(
        profile_dir=profile,
        managed_dir=managed,
        stable_config=root / "stable-config.yaml",
        auth_file=profile / "auth.json",
        config_toml=profile / "config.toml",
        runtime_mode_file=profile / "runtime-mode.txt",
        runtime_effective_mode_file=profile / "runtime-effective-mode.txt",
        registry_file=managed / "backend-registry.json",
        state_file=managed / "supervisor-state.json",
        managed_config_file=managed / "managed-config.yaml",
        launcher_script=managed / "stable-runtime-launcher.sh",
        sync_script=managed / "supervisor-sync.sh",
        accounts_bin=root / "bin" / "codex-accounts",
        onboard_bin=root / "bin" / "codex-account-onboard",
        lock_file=managed / "wild-boar-proxy.lock",
        launcher_lock_file=managed / "stable-runtime-launch.lock",
        repair_target_inventory_dir=managed / "stable-repair-target",
        repair_target_reference_file=managed / "approved-repair-target.json",
        target_switch_transaction_file=managed / "target-switch-transaction.json",
        stable_runtime_generated_config_file=managed / "stable-runtime-config.generated.yaml",
    )


def _write_context(paths: RuntimePaths) -> None:
    paths.profile_dir.mkdir(parents=True, exist_ok=True)
    paths.config_toml.write_text('model = "gpt-5.4"\n', encoding="utf-8")
    (paths.profile_dir / hook_entry.RUNTIME_CONTEXT_FILENAME).write_text(
        json.dumps(_runtime_context()) + "\n",
        encoding="utf-8",
    )


def _event(*, prompt: str = PROMPT, turn_id: str = "turn-hook-1") -> dict[str, object]:
    return {
        "session_id": "session-hook-1",
        "turn_id": turn_id,
        "cwd": str(ROOT),
        "hook_event_name": "UserPromptSubmit",
        "model": "gpt-5.4",
        "permission_mode": "on-request",
        "prompt": prompt,
    }


def _assert_no_prompt_route_or_secret(
    testcase: unittest.TestCase,
    packet: dict[str, object],
    *,
    prompt: str = PROMPT,
) -> None:
    serialized = json.dumps(packet, ensure_ascii=False, sort_keys=True)
    testcase.assertNotIn(prompt, serialized)
    testcase.assertNotIn(ROUTE_ID, serialized)
    testcase.assertFalse(packet_contains_text(packet, prompt))
    testcase.assertFalse(packet["raw_prompt_recorded"])
    testcase.assertFalse(packet["prompt_text_recorded"])
    testcase.assertFalse(packet["raw_route_id_recorded"])
    testcase.assertFalse(packet["secret_value_exposed"])
    testcase.assertFalse(packet["product_ready"])


class UserPromptSubmitHookProducerTests(unittest.TestCase):
    def test_parent_process_classification_uses_executable_path_not_spoofed_args(self) -> None:
        spoofed_command = (
            "/usr/bin/python3 -c 'print(\"Codex WBP Clean.app/Contents/Resources/"
            "codex app-server\")'"
        )

        self.assertEqual(
            producer._command_class("/usr/bin/python3", spoofed_command),
            "python",
        )

    def test_parent_process_classification_accepts_clean_app_exact_paths(self) -> None:
        root = "/Users/me/Applications/Codex WBP Clean.app/Contents/MacOS/Codex"
        server = "/Users/me/Applications/Codex WBP Clean.app/Contents/Resources/codex"

        self.assertEqual(producer._command_class(root, root), "wbp_clean_app_root")
        self.assertEqual(
            producer._command_class(server, f"{server} app-server --analytics-default-enabled"),
            "wbp_clean_app_server",
        )

    def test_install_apply_writes_profile_local_hooks_json_and_script_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            packet = producer.build_user_prompt_submit_install_packet(
                paths=paths,
                apply=True,
            )

            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "OK")
            self.assertEqual(packet["effect"], "mutate")
            self.assertTrue(packet["hook_definition_prepared"])
            self.assertTrue(packet["hook_config_digest_bound"])
            self.assertTrue(packet["hook_trust_requirement_declared"])
            self.assertFalse(packet["hook_trusted"])
            self.assertEqual(
                packet["hook_readiness_state"],
                producer.HOOK_STATE_BLOCKED_TRUST_REQUIRED,
            )
            self.assertTrue(producer.hooks_json_path(paths).exists())
            self.assertTrue(producer.hook_script_path(paths).exists())
            self.assertTrue(os.access(producer.hook_script_path(paths), os.X_OK))
            self.assertEqual(
                set(packet["changed_files"]),
                {str(producer.hooks_json_path(paths)), str(producer.hook_script_path(paths))},
            )
            self.assertNotIn("web_design_ui", json.dumps(packet, sort_keys=True))
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_readiness_after_install_is_blocked_until_codex_hook_trust(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
            packet = producer.build_user_prompt_submit_readiness_packet(paths=paths)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                producer.HOOK_BLOCKED_TRUST_REQUIRED,
            )
            self.assertTrue(packet["hook_config_present"])
            self.assertTrue(packet["hook_enabled"])
            self.assertTrue(packet["hook_command_path_resolves"])
            self.assertTrue(packet["hook_script_executable"])
            self.assertTrue(packet["hook_config_digest_bound"])
            self.assertTrue(packet["hook_trust_requirement_declared"])
            self.assertFalse(packet["hook_trusted"])
            self.assertIn("hook_trust_review_required", packet["blocking_reasons"])
            self.assertFalse(packet["state_written"])
            self.assertFalse(packet["product_ready"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_cli_install_apply_and_readiness_emit_strict_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
            env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
            env["WBP_CONFIG_TOML"] = str(paths.config_toml)
            install = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-install",
                    "--apply",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            readiness = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-readiness",
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            install_packet = json.loads(install.stdout)
            readiness_packet = json.loads(readiness.stdout)
            self.assertEqual(install.returncode, 0, install.stderr)
            self.assertEqual(
                install.stdout.strip(),
                json.dumps(install_packet, ensure_ascii=True),
            )
            self.assertEqual(install_packet["effect"], "mutate")
            self.assertTrue(install_packet["state_written"])
            self.assertEqual(readiness.returncode, 1)
            self.assertEqual(
                readiness_packet["machine_error_code"],
                producer.HOOK_BLOCKED_TRUST_REQUIRED,
            )
            self.assertEqual(readiness_packet["effect"], "probe")
            self.assertTrue(readiness_packet["hook_config_digest_bound"])
            self.assertEqual(packets.inspect_command_packet_semantics(install_packet), [])
            self.assertEqual(packets.inspect_command_packet_semantics(readiness_packet), [])

    def test_readiness_blocks_when_hooks_feature_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            paths.config_toml.write_text(
                '[features]\nhooks = false\n',
                encoding="utf-8",
            )
            producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
            packet = producer.build_user_prompt_submit_readiness_packet(paths=paths)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], producer.HOOK_CONFIG_DISABLED)
            self.assertFalse(packet["hook_enabled"])
            self.assertTrue(packet["hooks_feature_disabled"])
            self.assertIn("hooks_feature_disabled", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_readiness_blocks_when_hook_definition_tampered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = _paths(Path(temp_dir))
            _write_context(paths)
            producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
            document = json.loads(producer.hooks_json_path(paths).read_text(encoding="utf-8"))
            document["hooks"]["UserPromptSubmit"][-1]["hooks"][0]["timeout"] = 31
            producer.hooks_json_path(paths).write_text(
                json.dumps(document),
                encoding="utf-8",
            )
            packet = producer.build_user_prompt_submit_readiness_packet(paths=paths)

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], producer.HOOK_CONFIG_MISMATCH)
            self.assertFalse(packet["hook_config_digest_bound"])
            self.assertIn("hook_config_digest_mismatch", packet["blocking_reasons"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_run_hook_writes_file_backed_ledger_and_existing_verifier_accepts_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
            hook_hash = str(install["hook_definition_digest"])
            event_path = root / "event.json"
            event_path.write_text(json.dumps(_event()) + "\n", encoding="utf-8")
            ledger_path = root / "ledger.json"
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
            env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
            env["WBP_CONFIG_TOML"] = str(paths.config_toml)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy.user_prompt_submit_hook_producer",
                    "run-hook",
                    "--event-file",
                    str(event_path),
                    "--ledger-file",
                    str(ledger_path),
                    "--trusted-hook-config-sha256",
                    hook_hash,
                    "--loaded-hook-config-sha256",
                    hook_hash,
                    "--origin-state",
                    proof.ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)
            self.assertEqual(packet["packet_kind"], producer.HOOK_PRODUCER_RUN_PACKET_KIND)
            self.assertTrue(packet["hook_ledger_written"])
            self.assertEqual(
                packet["hook_producer_state"],
                producer.HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN,
            )
            _assert_no_prompt_route_or_secret(self, packet)
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["origin_state"],
                proof.ORIGIN_STATE_CUSTOM_CODEX_FLOW_PROVEN,
            )
            self.assertFalse(packet_contains_text(ledger, PROMPT))
            self.assertNotIn(ROUTE_ID, json.dumps(ledger, ensure_ascii=False))

            verify = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            verified = json.loads(verify.stdout)
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertEqual(verified["status"], "ok")
            self.assertTrue(verified["hook_producer_ledger_proven"])
            self.assertEqual(
                verified["hook_producer_state"],
                producer.HOOK_STATE_RAN_CUSTOM_CODEX_PROVEN,
            )
            self.assertFalse(verified["custom_codex_flow_proven"])
            self.assertFalse(verified["custom_codex_origin_proven"])
            self.assertTrue(verified["does_not_prove_custom_codex_origin"])
            self.assertTrue(verified["api_lane_called"])
            self.assertFalse(verified["product_ready"])
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])
            self.assertEqual(packets.inspect_command_packet_semantics(verified), [])

    def test_synthetic_run_cannot_claim_custom_codex_origin_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_context(paths)
            install = producer.build_user_prompt_submit_install_packet(paths=paths, apply=True)
            hook_hash = str(install["hook_definition_digest"])
            event_path = root / "event.json"
            event_path.write_text(json.dumps(_event()) + "\n", encoding="utf-8")
            ledger_path = root / "ledger.json"
            env = os.environ.copy()
            env["WBP_PROFILE_DIR"] = str(paths.profile_dir)
            env["WBP_MANAGED_DIR"] = str(paths.managed_dir)
            env["WBP_CONFIG_TOML"] = str(paths.config_toml)
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy.user_prompt_submit_hook_producer",
                    "run-hook",
                    "--event-file",
                    str(event_path),
                    "--ledger-file",
                    str(ledger_path),
                    "--trusted-hook-config-sha256",
                    hook_hash,
                    "--loaded-hook-config-sha256",
                    hook_hash,
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            packet = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                packet["hook_producer_state"],
                producer.HOOK_STATE_RAN_CODEX_UNPROVEN,
            )
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(
                ledger["origin_state"],
                proof.ORIGIN_STATE_SYNTHETIC_HOOK_FLOW,
            )
            verify = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "wild_boar_proxy",
                    "router-hook",
                    "user-prompt-submit-proof",
                    "--prompt",
                    PROMPT,
                    "--hook-ledger-file",
                    str(ledger_path),
                    "--json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            verified = json.loads(verify.stdout)
            self.assertEqual(verify.returncode, 1)
            self.assertFalse(verified["custom_codex_origin_proven"])
            self.assertIn(
                "origin_state_not_custom_codex_flow_proven",
                verified["blocking_reasons"],
            )
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])
            self.assertEqual(packets.inspect_command_packet_semantics(verified), [])

    def test_run_hook_blocks_malformed_event_before_ledger_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            _write_context(paths)
            hook_hash = hashlib.sha256(b"hook").hexdigest()
            packet = producer.build_user_prompt_submit_run_packet(
                event={"hook_event_name": "UserPromptSubmit", "turn_id": "turn-1"},
                paths=paths,
                ledger_file=root / "ledger.json",
                trusted_hook_config_sha256=hook_hash,
                loaded_hook_config_sha256=hook_hash,
            )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(packet["machine_error_code"], producer.HOOK_EVENT_INVALID)
            self.assertIn("hook_prompt_missing", packet["blocking_reasons"])
            self.assertFalse(packet["hook_ledger_written"])
            self.assertFalse((root / "ledger.json").exists())
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_run_hook_blocks_missing_runtime_context_before_ledger_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = _paths(root)
            paths.profile_dir.mkdir(parents=True, exist_ok=True)
            hook_hash = hashlib.sha256(b"hook").hexdigest()
            packet = producer.build_user_prompt_submit_run_packet(
                event=_event(),
                paths=paths,
                ledger_file=root / "ledger.json",
                trusted_hook_config_sha256=hook_hash,
                loaded_hook_config_sha256=hook_hash,
            )

            self.assertEqual(packet["status"], "error")
            self.assertEqual(
                packet["machine_error_code"],
                producer.HOOK_RUNTIME_CONTEXT_INVALID,
            )
            self.assertIn("runtime_context_file_not_read", packet["blocking_reasons"])
            self.assertFalse(packet["hook_ledger_written"])
            self.assertFalse((root / "ledger.json").exists())
            _assert_no_prompt_route_or_secret(self, packet)
            self.assertEqual(packets.inspect_command_packet_semantics(packet), [])


if __name__ == "__main__":
    unittest.main()
