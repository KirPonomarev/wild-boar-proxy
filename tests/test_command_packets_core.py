# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import ast
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

    def test_core_packets_has_no_runtime_or_owner_path_dependencies(self) -> None:
        tree = ast.parse(PACKETS_CORE.read_text(encoding="utf-8"))
        forbidden_imports = {
            "runtime",
            "web_design_live_server",
            "web_ui",
            "runtime_status",
            "runtime_repair",
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
