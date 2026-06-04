# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path

from wild_boar_proxy import runtime_modes
from wild_boar_proxy import runtime as runtime_mod
from wild_boar_proxy.core import errors
from wild_boar_proxy.core import packets


ROOT = Path(__file__).resolve().parents[1]
ERRORS_CORE = ROOT / "wild_boar_proxy" / "core" / "errors.py"
PACKETS_CORE = ROOT / "wild_boar_proxy" / "core" / "packets.py"


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return ""


class _OpaqueSecretCarrier:
    def __init__(self, secret: str) -> None:
        self.secret = secret

    def __repr__(self) -> str:
        return f"OpaqueSecretCarrier({self.secret})"


class CommandPacketsCoreTests(unittest.TestCase):
    def test_core_machine_error_codes_match_j2_taxonomy(self) -> None:
        self.assertEqual(errors.OK, "OK")
        self.assertEqual(
            errors.CORE_MACHINE_ERROR_CODES,
            (
                "CONFIG_INVALID",
                "STATE_CORRUPT",
                "STATE_SCHEMA_UNSUPPORTED",
                "STATE_MIGRATION_FAILED",
                "STATE_WRITE_FAILED",
                "PROCESS_NOT_FOUND",
                "PROCESS_TIMEOUT",
                "PROCESS_FAILED",
                "RUNTIME_IDENTITY_MISMATCH",
                "AUTH_REQUIRED",
                "ROUTE_ID_INVALID",
                "REPAIR_REQUIRED",
                "REPAIR_FAILED",
                "LOCK_HELD",
                "LOCK_STALE",
                "COMMAND_PACKET_MALFORMED",
            ),
        )

    def test_machine_error_code_classification_is_additive(self) -> None:
        self.assertEqual(errors.classify_machine_error_code("OK"), "ok")
        self.assertEqual(
            errors.classify_machine_error_code("PROCESS_TIMEOUT"), "core"
        )
        self.assertEqual(errors.classify_machine_error_code("LISTENER_DOWN"), "legacy")
        self.assertEqual(
            errors.classify_machine_error_code("provider_network_failed"), "legacy"
        )
        self.assertEqual(
            errors.classify_machine_error_code("CUSTOM_CODEX_PROCESS_NOT_FOUND"),
            "legacy",
        )
        self.assertEqual(errors.classify_machine_error_code(""), "invalid_shape")
        self.assertEqual(errors.classify_machine_error_code("bad-code"), "invalid_shape")
        self.assertEqual(
            errors.classify_machine_error_code("BAD/CODE"), "invalid_shape"
        )
        self.assertEqual(errors.classify_machine_error_code(None), "invalid_shape")

    def test_machine_error_code_token_shape_is_compatibility_wide(self) -> None:
        self.assertTrue(errors.is_machine_error_code_token("LISTENER_DOWN"))
        self.assertTrue(errors.is_machine_error_code_token("provider_network_failed"))
        self.assertTrue(errors.is_machine_error_code_token("A1_B2"))
        self.assertFalse(errors.is_machine_error_code_token("_LEADING_UNDERSCORE"))
        self.assertFalse(errors.is_machine_error_code_token("1_LEADING_DIGIT"))
        self.assertFalse(errors.is_machine_error_code_token("BAD CODE"))
        self.assertFalse(errors.is_machine_error_code_token("BAD-CODE"))
        self.assertFalse(errors.is_machine_error_code_token("BAD/CODE"))

    def test_required_fields_match_runtime_compatibility_alias(self) -> None:
        self.assertEqual(
            packets.COMMAND_PACKET_REQUIRED_FIELDS,
            [
                "status",
                "exit_code",
                "human_message",
                "machine_error_code",
                "changed_files",
                "next_action",
                "liveness",
                "severity",
                "operator_action",
            ],
        )
        self.assertIs(
            runtime_mod.COMMAND_PAYLOAD_REQUIRED_FIELDS,
            packets.COMMAND_PACKET_REQUIRED_FIELDS,
        )

    def test_packet_value_vocabulary_matches_j4_scope(self) -> None:
        self.assertEqual(packets.COMMAND_STATUS_VALUES, ("ok", "error"))
        self.assertEqual(
            packets.COMMAND_LIVENESS_VALUES,
            ("healthy", "degraded", "down", "unknown", "not_applicable"),
        )
        self.assertEqual(packets.COMMAND_SEVERITY_VALUES, ("recoverable", "fatal", "high"))
        self.assertEqual(
            packets.COMMAND_OPERATOR_ACTION_VALUES,
            ("none", "retry", "user_action", "stop"),
        )
        self.assertEqual(
            packets.COMMAND_NEXT_ACTION_VALUES,
            ("none", "retry", "user_action", "stop"),
        )

    def test_packet_value_classification_is_additive(self) -> None:
        self.assertEqual(packets.classify_command_status("ok"), "core")
        self.assertEqual(packets.classify_command_status("blocked"), "legacy")
        self.assertEqual(packets.classify_command_status("bad-status"), "invalid_shape")
        self.assertEqual(packets.classify_command_liveness("not_applicable"), "core")
        self.assertEqual(packets.classify_command_liveness("warming_up"), "legacy")
        self.assertEqual(packets.classify_command_severity("high"), "core")
        self.assertEqual(packets.classify_command_severity("critical"), "legacy")
        self.assertEqual(packets.classify_command_operator_action("retry"), "core")
        self.assertEqual(
            packets.classify_command_operator_action("repair_runtime"), "legacy"
        )
        self.assertEqual(packets.classify_command_next_action("stop"), "core")
        self.assertEqual(
            packets.classify_command_next_action("accounts_login_start"), "legacy"
        )
        self.assertEqual(packets.classify_command_next_action("bad/action"), "invalid_shape")
        self.assertEqual(packets.classify_command_operator_action(None), "invalid_shape")

    def test_command_value_token_shape_is_compatibility_wide(self) -> None:
        self.assertTrue(packets.is_command_value_token("repair_runtime"))
        self.assertTrue(packets.is_command_value_token("accounts_login_start"))
        self.assertTrue(packets.is_command_value_token("A1_B2"))
        self.assertFalse(packets.is_command_value_token("_leading_underscore"))
        self.assertFalse(packets.is_command_value_token("1_leading_digit"))
        self.assertFalse(packets.is_command_value_token("bad action"))
        self.assertFalse(packets.is_command_value_token("bad-action"))
        self.assertFalse(packets.is_command_value_token("bad/action"))

    def test_command_exit_code_mapping_preserves_compatibility(self) -> None:
        self.assertEqual(packets.COMMAND_EXIT_OK, 0)
        self.assertEqual(packets.COMMAND_EXIT_ERROR, 1)
        self.assertEqual(packets.command_exit_code(True), 0)
        self.assertEqual(packets.command_exit_code(True, 7), 0)
        self.assertEqual(packets.command_exit_code(False), 1)
        self.assertEqual(packets.command_exit_code(False, 7), 7)
        self.assertEqual(packets.command_exit_code(False, 0), 0)

    def test_build_command_packet_matches_runtime_wrapper(self) -> None:
        kwargs = {
            "ok": False,
            "human_message": "runtime failed",
            "machine_error_code": "PROCESS_FAILED",
            "liveness": "degraded",
            "severity": "recoverable",
            "operator_action": "retry",
            "changed_files": ["/tmp/wbp-state.json"],
            "extra": {"detail": "kept"},
            "exit_code": 7,
            "effect": "probe",
        }

        self.assertEqual(
            packets.build_command_packet(**kwargs),
            runtime_mod.build_command_payload(**kwargs),
        )
        self.assertEqual(
            packets.build_command_packet(**kwargs),
            runtime_modes._build_command_payload(**kwargs),
        )

    def test_build_command_packet_exit_code_mapping_matches_runtime_wrappers(self) -> None:
        cases = [
            (True, None, 0),
            (True, 7, 0),
            (False, None, 1),
            (False, 7, 7),
            (False, 0, 0),
        ]
        for ok, exit_code, expected_exit_code in cases:
            with self.subTest(ok=ok, exit_code=exit_code):
                kwargs = {
                    "ok": ok,
                    "human_message": "mapped",
                    "machine_error_code": "OK" if ok else "PROCESS_FAILED",
                    "liveness": "healthy" if ok else "down",
                    "severity": "recoverable",
                    "operator_action": "none" if ok else "retry",
                    "changed_files": [],
                    "exit_code": exit_code,
                }

                self.assertEqual(
                    packets.build_command_packet(**kwargs)["exit_code"],
                    expected_exit_code,
                )
                self.assertEqual(
                    runtime_mod.build_command_payload(**kwargs),
                    packets.build_command_packet(**kwargs),
                )
                self.assertEqual(
                    runtime_modes._build_command_payload(**kwargs),
                    packets.build_command_packet(**kwargs),
                )

    def test_build_command_packet_preserves_extra_override_behavior(self) -> None:
        payload = packets.build_command_packet(
            ok=False,
            human_message="original",
            machine_error_code="PROCESS_FAILED",
            liveness="down",
            severity="fatal",
            operator_action="stop",
            changed_files=[],
            exit_code=7,
            effect="read",
            extra={
                "status": "custom",
                "exit_code": 42,
                "machine_error_code": "OVERRIDDEN",
                "operator_action": "override",
                "effect": "raw-extra-effect",
            },
        )

        self.assertEqual(payload["status"], "custom")
        self.assertEqual(payload["exit_code"], 42)
        self.assertEqual(payload["machine_error_code"], "OVERRIDDEN")
        self.assertEqual(payload["operator_action"], "override")
        self.assertEqual(payload["next_action"], "stop")
        self.assertEqual(payload["effect"], "raw-extra-effect")

    def test_build_command_packet_keeps_legacy_action_values_passthrough(self) -> None:
        payload = packets.build_command_packet(
            ok=True,
            human_message="legacy action",
            machine_error_code="OK",
            liveness="warming_up",
            severity="critical",
            operator_action="repair_runtime",
            changed_files=[],
        )

        self.assertEqual(payload["operator_action"], "repair_runtime")
        self.assertEqual(payload["next_action"], "repair_runtime")
        self.assertEqual(
            packets.classify_command_operator_action(payload["operator_action"]),
            "legacy",
        )
        self.assertEqual(
            packets.classify_command_next_action(payload["next_action"]),
            "legacy",
        )
        self.assertEqual(
            runtime_mod.build_command_payload(
                ok=True,
                human_message="legacy action",
                machine_error_code="OK",
                liveness="warming_up",
                severity="critical",
                operator_action="repair_runtime",
                changed_files=[],
            ),
            payload,
        )
        self.assertEqual(
            runtime_modes._build_command_payload(
                ok=True,
                human_message="legacy action",
                machine_error_code="OK",
                liveness="warming_up",
                severity="critical",
                operator_action="repair_runtime",
                changed_files=[],
            ),
            payload,
        )

    def test_build_command_packet_keeps_action_extra_override_behavior(self) -> None:
        payload = packets.build_command_packet(
            ok=False,
            human_message="override action",
            machine_error_code="PROCESS_FAILED",
            liveness="down",
            severity="fatal",
            operator_action="retry",
            changed_files=[],
            extra={
                "operator_action": "user_action",
                "next_action": "accounts_login_start",
            },
        )

        self.assertEqual(payload["operator_action"], "user_action")
        self.assertEqual(payload["next_action"], "accounts_login_start")

    def test_build_command_packet_keeps_legacy_machine_error_code_passthrough(self) -> None:
        payload = packets.build_command_packet(
            ok=False,
            human_message="legacy failure",
            machine_error_code="provider_network_failed",
            liveness="degraded",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
        )

        self.assertEqual(payload["machine_error_code"], "provider_network_failed")
        self.assertEqual(
            errors.classify_machine_error_code(payload["machine_error_code"]),
            "legacy",
        )

    def test_effect_is_optional_and_not_required_for_shape(self) -> None:
        payload = packets.build_command_packet(
            ok=True,
            human_message="ok",
            machine_error_code="OK",
            liveness="healthy",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
        )

        self.assertNotIn("effect", payload)
        self.assertTrue(packets.has_command_packet_shape(payload))
        self.assertTrue(runtime_mod.has_command_payload_shape(payload))

    def test_invalid_effect_is_rejected_before_extra_override(self) -> None:
        with self.assertRaises(ValueError):
            packets.build_command_packet(
                ok=True,
                human_message="ok",
                machine_error_code="OK",
                liveness="healthy",
                severity="recoverable",
                operator_action="none",
                changed_files=[],
                effect="invalid",
                extra={"effect": "read"},
            )

    def test_build_command_packet_redacts_payload_by_default(self) -> None:
        payload = packets.build_command_packet(
            ok=True,
            human_message="Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
            machine_error_code="OK",
            liveness="healthy",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            extra={
                "data": {
                    "api_key": "plain-fixture-value",
                    "note": "token bucket remains observable",
                }
            },
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["human_message"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(
            payload["data"]["api_key"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(payload["data"]["note"], "token bucket remains observable")
        self.assertFalse(packets.command_packet_has_secret_leak(payload))

    def test_build_command_packet_redacts_explicit_secret_values(self) -> None:
        sentinel = "local-runtime-token-1234567890"

        payload = packets.build_command_packet(
            ok=False,
            human_message=f"token source returned {sentinel}",
            machine_error_code="PROCESS_FAILED",
            liveness="degraded",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={"data": {"message": f"raw={sentinel}"}},
            secret_values=[sentinel],
        )

        encoded = json.dumps(payload, default=str)
        self.assertEqual(payload["status"], "error")
        self.assertNotIn(sentinel, encoded)
        self.assertIn(packets.COMMAND_PACKET_REDACTION_PLACEHOLDER, encoded)
        self.assertFalse(
            packets.command_packet_has_secret_leak(payload, secret_values=[sentinel])
        )

    def test_build_command_packet_preserves_safe_secret_references(self) -> None:
        payload = packets.build_command_packet(
            ok=True,
            human_message="credential reference collected",
            machine_error_code="OK",
            liveness="not_applicable",
            severity="recoverable",
            operator_action="none",
            changed_files=[],
            extra={
                "data": {
                    "secret_ref": "OPENROUTER_API_KEY",
                    "credential_ref": "provider:openrouter",
                    "token_ref": "managed_local_token",
                    "available_secret_refs": ["OPENROUTER_API_KEY"],
                    "secret_value_exposed": False,
                }
            },
        )

        self.assertEqual(payload["data"]["secret_ref"], "OPENROUTER_API_KEY")
        self.assertEqual(payload["data"]["credential_ref"], "provider:openrouter")
        self.assertEqual(payload["data"]["token_ref"], "managed_local_token")
        self.assertEqual(
            payload["data"]["available_secret_refs"],
            ["OPENROUTER_API_KEY"],
        )
        self.assertFalse(payload["data"]["secret_value_exposed"])
        self.assertFalse(packets.command_packet_has_secret_leak(payload))

    def test_build_command_packet_fails_safe_on_unredactable_secret_leak(self) -> None:
        sentinel = "sk-wbp-unredactable-secret-1234567890"

        payload = packets.build_command_packet(
            ok=True,
            human_message="would otherwise be ok",
            machine_error_code="OK",
            liveness="healthy",
            severity="recoverable",
            operator_action="none",
            changed_files=["/tmp/would-have-mutated.json"],
            extra={"data": {"opaque": _OpaqueSecretCarrier(sentinel)}},
            secret_values=[sentinel],
        )

        encoded = json.dumps(payload, default=str)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["exit_code"], 1)
        self.assertEqual(payload["machine_error_code"], "COMMAND_PACKET_MALFORMED")
        self.assertEqual(payload["changed_files"], [])
        self.assertEqual(payload["next_action"], "stop")
        self.assertEqual(payload["operator_action"], "stop")
        self.assertEqual(payload["packet_redaction_status"], "failed")
        self.assertNotIn("data", payload)
        self.assertNotIn(sentinel, encoded)

    def test_runtime_wrappers_inherit_builder_redaction(self) -> None:
        kwargs = {
            "ok": True,
            "human_message": "ok",
            "machine_error_code": "OK",
            "liveness": "healthy",
            "severity": "recoverable",
            "operator_action": "none",
            "changed_files": [],
            "extra": {"data": {"api_key": "plain-fixture-value"}},
        }

        expected = packets.build_command_packet(**kwargs)

        self.assertEqual(runtime_mod.build_command_payload(**kwargs), expected)
        self.assertEqual(runtime_modes._build_command_payload(**kwargs), expected)
        self.assertEqual(
            expected["data"]["api_key"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )

    def test_runtime_wrappers_forward_explicit_secret_values(self) -> None:
        sentinel = "local-runtime-token-wrapper-1234567890"
        kwargs = {
            "ok": True,
            "human_message": f"collected {sentinel}",
            "machine_error_code": "OK",
            "liveness": "healthy",
            "severity": "recoverable",
            "operator_action": "none",
            "changed_files": [],
            "secret_values": [sentinel],
        }

        expected = packets.build_command_packet(**kwargs)

        self.assertEqual(runtime_mod.build_command_payload(**kwargs), expected)
        self.assertEqual(runtime_modes._build_command_payload(**kwargs), expected)
        self.assertNotIn(sentinel, json.dumps(expected))

    def test_missing_required_fields_reports_canonical_order(self) -> None:
        packet = {
            "status": "ok",
            "human_message": "ok",
            "machine_error_code": "OK",
        }

        self.assertEqual(
            packets.missing_required_fields(
                packet, packets.COMMAND_PACKET_REQUIRED_FIELDS
            ),
            [
                "exit_code",
                "changed_files",
                "next_action",
                "liveness",
                "severity",
                "operator_action",
            ],
        )

    def test_redact_command_packet_redacts_nested_explicit_secret_values(self) -> None:
        sentinel = "sk-wbp-command-packet-secret-1234567890"
        payload = packets.build_command_packet(
            ok=False,
            human_message=f"failed with token {sentinel}",
            machine_error_code="PROCESS_FAILED",
            liveness="degraded",
            severity="recoverable",
            operator_action="retry",
            changed_files=[],
            extra={
                "data": {
                    "api_key": sentinel,
                    "message": f"prefix {sentinel} suffix",
                    "nested": ["safe", sentinel],
                    "tuple_value": (sentinel, "kept"),
                }
            },
        )

        redacted = packets.redact_command_packet(payload, secret_values=[sentinel])

        self.assertTrue(packets.has_command_packet_shape(redacted))
        self.assertEqual(
            redacted["data"]["api_key"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(
            redacted["human_message"],
            f"failed with token {packets.COMMAND_PACKET_REDACTION_PLACEHOLDER}",
        )
        self.assertEqual(
            redacted["data"]["message"],
            f"prefix {packets.COMMAND_PACKET_REDACTION_PLACEHOLDER} suffix",
        )
        self.assertEqual(
            redacted["data"]["nested"][1],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(
            redacted["data"]["tuple_value"],
            (packets.COMMAND_PACKET_REDACTION_PLACEHOLDER, "kept"),
        )
        self.assertNotIn(sentinel, json.dumps(redacted, default=str))

    def test_redact_command_packet_does_not_mutate_original_payload(self) -> None:
        sentinel = "sk-wbp-nonmutating-secret-1234567890"
        payload = {
            "status": "ok",
            "exit_code": 0,
            "human_message": sentinel,
            "machine_error_code": "OK",
            "changed_files": [],
            "next_action": "none",
            "liveness": "healthy",
            "severity": "recoverable",
            "operator_action": "none",
            "data": {"token": sentinel},
        }
        original = copy.deepcopy(payload)

        redacted = packets.redact_command_packet(payload, secret_values=[sentinel])

        self.assertEqual(payload, original)
        self.assertNotEqual(redacted, payload)
        self.assertEqual(
            redacted["data"]["token"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )

    def test_redact_command_packet_preserves_safe_secret_references(self) -> None:
        payload = {
            "secret_ref": "OPENROUTER_API_KEY",
            "credential_ref": "provider:openrouter",
            "token_ref": "managed_local_token",
            "available_secret_refs": ["OPENROUTER_API_KEY"],
            "api_key_source": "managed_local_token",
            "token_source_kind": "stable_generated_config",
            "token_output_shape": "plain_token_stdout",
            "token_present": True,
            "token_emitted": False,
            "secret_value_recorded": False,
            "secret_value_exposed": False,
            "profile_dir_redacted": True,
            "api_key_bundle": {"token_ref": "managed_local_token"},
        }

        redacted = packets.redact_command_packet_value(payload)

        self.assertEqual(redacted["secret_ref"], "OPENROUTER_API_KEY")
        self.assertEqual(redacted["credential_ref"], "provider:openrouter")
        self.assertEqual(redacted["token_ref"], "managed_local_token")
        self.assertEqual(redacted["available_secret_refs"], ["OPENROUTER_API_KEY"])
        self.assertEqual(redacted["api_key_source"], "managed_local_token")
        self.assertEqual(
            redacted["api_key_bundle"]["token_ref"],
            "managed_local_token",
        )
        self.assertFalse(packets.command_packet_has_secret_leak(redacted))

    def test_redact_command_packet_preserves_machine_truth_fields(self) -> None:
        payload = packets.build_command_packet(
            ok=False,
            human_message="token bucket remains observable",
            machine_error_code="PROCESS_TIMEOUT",
            liveness="degraded",
            severity="recoverable",
            operator_action="retry",
            changed_files=["/tmp/token-bucket-state.json"],
            exit_code=7,
            effect="probe",
        )

        redacted = packets.redact_command_packet(payload)

        for field in packets.COMMAND_PACKET_REQUIRED_FIELDS + ["effect"]:
            with self.subTest(field=field):
                self.assertEqual(redacted[field], payload[field])

    def test_command_packet_has_secret_leak_detects_explicit_secret_after_serialization(
        self,
    ) -> None:
        sentinel = "sk-wbp-serialized-secret-1234567890"
        payload = {"data": {"messages": ["safe", {"text": f"raw={sentinel}"}]}}

        self.assertTrue(
            packets.command_packet_has_secret_leak(payload, secret_values=[sentinel])
        )

    def test_command_packet_has_secret_leak_ignores_redacted_payload(self) -> None:
        sentinel = "sk-wbp-redacted-secret-1234567890"
        payload = {
            "data": {
                "api_key": sentinel,
                "authorization": f"Bearer {sentinel}",
                "message": f"raw={sentinel}",
            }
        }

        redacted = packets.redact_command_packet(payload, secret_values=[sentinel])

        self.assertFalse(
            packets.command_packet_has_secret_leak(redacted, secret_values=[sentinel])
        )

    def test_redaction_catches_high_confidence_secret_shapes(self) -> None:
        payload = {
            "data": {
                "authorization_header": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
                "env_text": "OPENAI_API_KEY=abcdefghijklmnopqrstuvwxyz",
                "plain_api_key": "plain-fixture-value",
                "sk_value": "sk-wbp-secret-shape-1234567890",
                "url": "https://user:password@example.test/path",
                "note": "token bucket remains observable",
                "next_action": "accounts_login_start",
                "secret_ref": "OPENROUTER_API_KEY",
                "token_ref": "managed_local_token",
            }
        }

        redacted = packets.redact_command_packet(payload)

        self.assertEqual(
            redacted["data"]["authorization_header"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(
            redacted["data"]["env_text"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(
            redacted["data"]["plain_api_key"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertEqual(
            redacted["data"]["sk_value"],
            packets.COMMAND_PACKET_REDACTION_PLACEHOLDER,
        )
        self.assertNotIn("user:password", redacted["data"]["url"])
        self.assertEqual(redacted["data"]["note"], "token bucket remains observable")
        self.assertEqual(redacted["data"]["next_action"], "accounts_login_start")
        self.assertEqual(redacted["data"]["secret_ref"], "OPENROUTER_API_KEY")
        self.assertEqual(redacted["data"]["token_ref"], "managed_local_token")
        self.assertFalse(packets.command_packet_has_secret_leak(redacted))

    def test_core_packets_has_no_runtime_or_owner_path_dependencies(self) -> None:
        tree = ast.parse(PACKETS_CORE.read_text(encoding="utf-8"))
        forbidden_imports = {
            "process_runner",
            "runtime",
            "runtime_modes",
            "web_design_live_server",
            "web_ui",
            "runtime_status",
            "runtime_repair",
            "state_store",
            "state_migration",
        }
        imported: set[str] = set()
        calls: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
            elif isinstance(node, ast.Call):
                dotted = _dotted_name(node.func)
                if dotted:
                    calls.add(dotted)
                    calls.add(dotted.rsplit(".", 1)[-1])

        self.assertEqual(imported & forbidden_imports, set())
        self.assertEqual(
            calls
            & {
                "Path",
                "open",
                "read_json",
                "read_text",
                "run_bounded_process",
                "serialized_lock",
                "subprocess.run",
                "write_json_atomic",
                "write_text_atomic",
            },
            set(),
        )

    def test_core_errors_has_no_owner_path_dependencies(self) -> None:
        tree = ast.parse(ERRORS_CORE.read_text(encoding="utf-8"))
        forbidden_imports = {
            "process_runner",
            "runtime",
            "runtime_modes",
            "runtime_status",
            "runtime_repair",
            "state_store",
            "state_migration",
            "web_design_live_server",
            "web_ui",
        }
        imported: set[str] = set()
        calls: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
            elif isinstance(node, ast.Call):
                dotted = _dotted_name(node.func)
                if dotted:
                    calls.add(dotted)
                    calls.add(dotted.rsplit(".", 1)[-1])

        self.assertEqual(imported & forbidden_imports, set())
        self.assertEqual(
            calls
            & {
                "Path",
                "open",
                "read_json",
                "read_text",
                "run_bounded_process",
                "serialized_lock",
                "subprocess.run",
                "write_json_atomic",
                "write_text_atomic",
            },
            set(),
        )


if __name__ == "__main__":
    unittest.main()
