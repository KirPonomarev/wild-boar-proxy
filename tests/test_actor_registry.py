# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B02: canonical actor registry schema v2, migration, and legacy projection."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import actor_registry as ar
from wild_boar_proxy import codex_custom_sessions as ccs
from wild_boar_proxy import custom_agent_bindings as cab
from wild_boar_proxy.core import packets

from test_codex_custom_sessions import (  # noqa: E402
    api_snapshot,
    commands,
    operator_status,
)
from test_custom_agent_bindings import route_records  # noqa: E402


def _v1_bindings() -> list[dict[str, object]]:
    return [
        {
            "agent_id": "codex",
            "display_name": "Codex",
            "role": "orchestrator",
            "aliases": ["Codex", "Agent 1", "1"],
            "lane": cab.PRIMARY_CHATGPT_LANE,
            "model_id": "gpt-5.5",
            "enabled": True,
            "allowed_actions": ["plan", "inspect", "patch", "verify"],
        },
        {
            "agent_id": "dip",
            "display_name": "DIP",
            "role": "coding_agent",
            "aliases": ["DIP", "Agent 2", "2"],
            "lane": cab.API_ROUTE_LANE,
            "route_id": "wbp-deepseek-chat",
            "enabled": True,
            "allowed_actions": ["code_review", "implementation_help"],
        },
    ]


class BuildDocumentTests(unittest.TestCase):
    def test_build_produces_canonical_v2_sections(self) -> None:
        doc = ar.build_actor_registry_document(_v1_bindings())
        self.assertEqual(doc["schema_version"], 2)
        self.assertEqual(len(doc["actors"]), 2)
        self.assertEqual(len(doc["slot_bindings"]), 2)
        self.assertEqual(len(doc["role_assignments"]), 2)
        primary = next(b for b in doc["slot_bindings"] if b["slot_id"] == "primary")
        external = next(b for b in doc["slot_bindings"] if b["slot_id"] == "agent_1")
        self.assertEqual(primary["actor_id"], "codex")
        self.assertEqual(primary["binding_revision"], 1)
        self.assertEqual(external["actor_id"], "dip")
        self.assertEqual(external["route_id"], "wbp-deepseek-chat")
        codex = next(a for a in doc["actors"] if a["actor_id"] == "codex")
        self.assertEqual(codex["transport_adapter_id"], ar.NATIVE_PRIMARY_ADAPTER)
        self.assertEqual(codex["permission_ceiling"], ar.PERMISSION_CONTEXT_ONLY)
        self.assertIsNone(codex["credential_ref"])
        dip = next(a for a in doc["actors"] if a["actor_id"] == "dip")
        self.assertEqual(dip["transport_adapter_id"], ar.API_ADAPTER)

    def test_build_legacy_projection_round_trips(self) -> None:
        bindings = _v1_bindings()
        doc = ar.build_actor_registry_document(bindings)
        projection = ar.project_legacy_agent_bindings(doc)
        self.assertEqual(projection, doc["agent_bindings"])
        self.assertEqual(
            {(b["agent_id"], b["lane"]) for b in projection},
            {("codex", "primary_chatgpt"), ("dip", "api_route")},
        )
        validation = ar.validate_actor_registry_document(doc)
        self.assertTrue(validation["valid"], validation["reasons"])


class ValidationTests(unittest.TestCase):
    def _valid_document(self) -> dict[str, object]:
        return ar.build_actor_registry_document(_v1_bindings())

    def test_valid_document_passes(self) -> None:
        validation = ar.validate_actor_registry_document(self._valid_document())
        self.assertTrue(validation["valid"], validation["reasons"])

    def test_secret_shaped_fields_rejected(self) -> None:
        doc = self._valid_document()
        doc["actors"][0]["secret"] = "sk-live"
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertIn("actor_0_forbidden_fields", validation["reasons"])

    def test_stale_route_rejected(self) -> None:
        doc = self._valid_document()
        doc["slot_bindings"][1]["route_id"] = "wbp-deepseek-v3"
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertIn("binding_1_route_id_stale", validation["reasons"])

    def test_duplicate_aliases_rejected(self) -> None:
        doc = self._valid_document()
        doc["slot_bindings"][1]["aliases"] = ["Codex"]
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertTrue(any(r.startswith("alias_duplicate:") for r in validation["reasons"]))

    def test_unknown_permission_ceiling_rejected(self) -> None:
        doc = self._valid_document()
        doc["actors"][1]["permission_ceiling"] = "everything"
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertIn("actor_1_permission_ceiling_unknown", validation["reasons"])

    def test_legacy_projection_mismatch_rejected(self) -> None:
        doc = self._valid_document()
        doc["agent_bindings"][1]["route_id"] = "wbp-different-route"
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertIn("legacy_projection_mismatch", validation["reasons"])

    def test_unbound_assignment_rejected(self) -> None:
        doc = self._valid_document()
        doc["role_assignments"][0]["slot_id"] = "ghost_slot"
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertTrue(any(r.startswith("assignment_0_slot_id_unbound") for r in validation["reasons"]))

    def test_missing_primary_slot_rejected(self) -> None:
        doc = self._valid_document()
        doc["slot_bindings"][0]["enabled"] = False
        validation = ar.validate_actor_registry_document(doc)
        self.assertFalse(validation["valid"])
        self.assertIn("primary_slot_enabled_binding_missing", validation["reasons"])


class ReadAndMigrateTests(unittest.TestCase):
    def _write_v1_state(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "packet_kind": "codex_custom_agent_bindings_state",
                    "updated_at_utc": "2026-01-01T00:00:00Z",
                    "agent_bindings": _v1_bindings(),
                    "raw_backend_details_exposed": False,
                    "secret_value_exposed": False,
                }
            ),
            encoding="utf-8",
        )

    def test_read_missing_state_reports_not_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = ar.read_actor_registry_packet(Path(temp_dir) / "missing.json")
        self.assertEqual(packet["status"], "not_initialized")
        self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_NOT_INITIALIZED")
        self.assertEqual(packet["changed_files"], [])
        self.assertEqual(packets.inspect_command_packet_semantics(packet), [])

    def test_read_v1_reports_migration_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "custom-agent-bindings.json"
            self._write_v1_state(path)
            packet = ar.read_actor_registry_packet(path)
        self.assertEqual(packet["status"], "migration_pending")
        self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_MIGRATION_PENDING")
        self.assertEqual(len(packet["agent_bindings"]), 2)

    def test_migrate_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "custom-agent-bindings.json"
            self._write_v1_state(path)
            before = path.read_bytes()
            packet = ar.run_actor_registry_migrate(path, dry_run=True)
            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_MIGRATION_DRY_RUN")
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(packet["changed_files"], [])

    def test_migrate_apply_creates_backup_and_migrates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "custom-agent-bindings.json"
            self._write_v1_state(path)
            packet = ar.run_actor_registry_migrate(path, dry_run=False)
            self.assertEqual(packet["status"], "ok")
            self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_MIGRATED")
            self.assertTrue(packet["rollback_available"])
            backup_path = Path(packet["backup_path"])
            self.assertTrue(backup_path.is_file())
            self.assertTrue(packet["backup_path"].endswith(".v1-to-v2.backup"))
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema_version"], 2)
            self.assertEqual(len(document["actors"]), 2)
            validation = ar.validate_actor_registry_document(document)
            self.assertTrue(validation["valid"], validation["reasons"])
            # rollback = restore backup
            path.write_bytes(backup_path.read_bytes())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_migrate_already_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "custom-agent-bindings.json"
            self._write_v1_state(path)
            ar.run_actor_registry_migrate(path, dry_run=False)
            packet = ar.run_actor_registry_migrate(path, dry_run=False)
        self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_ALREADY_CURRENT")
        self.assertEqual(packet["changed_files"], [])

    def test_migrate_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            packet = ar.run_actor_registry_migrate(
                Path(temp_dir) / "custom-agent-bindings.json", dry_run=False
            )
        self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_MIGRATION_NO_STATE")

    def test_write_bindings_packet_persists_v2_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "managed" / "custom-agent-bindings.json"
            written = cab.write_agent_bindings_packet(
                path,
                {"agent_bindings": _v1_bindings()},
                primary_model_ids=["gpt-5.5"],
                route_records=route_records(),
            )
            self.assertEqual(written["status"], "ok")
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["schema_version"], 2)
            self.assertEqual(len(document["actors"]), 2)
            read_back = cab.read_agent_bindings_packet(
                path,
                default_bindings=[],
                primary_model_ids=["gpt-5.5"],
                route_records=route_records(),
            )
            self.assertEqual(read_back["source"], "persisted_state")
            self.assertEqual(read_back["alias_to_agent_id"]["DIP"], "dip")


class BindingReferenceTests(unittest.TestCase):
    def test_resolve_by_slot(self) -> None:
        doc = ar.build_actor_registry_document(_v1_bindings())
        reference = ar.resolve_binding_reference(doc, slot_id="agent_1")
        self.assertTrue(reference["actor_registry_reference_present"])
        self.assertEqual(reference["binding_id"], "binding-agent_1")
        self.assertEqual(reference["binding_revision"], 1)
        self.assertEqual(reference["actor_id"], "dip")
        self.assertEqual(reference["assignment_id"], "assignment-agent_1")

    def test_resolve_by_alias(self) -> None:
        doc = ar.build_actor_registry_document(_v1_bindings())
        reference = ar.resolve_binding_reference(doc, alias="DIP")
        self.assertEqual(reference["slot_id"], "agent_1")

    def test_resolve_unknown_returns_empty(self) -> None:
        doc = ar.build_actor_registry_document(_v1_bindings())
        self.assertEqual(ar.resolve_binding_reference(doc, alias="ghost"), {})


class SessionReconciliationTests(unittest.TestCase):
    def test_session_create_persists_actor_registry_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ccs.CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.5",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                    "actor_registry_slot_id": "agent_1",
                    "actor_registry_binding_id": "binding-agent_1",
                    "actor_registry_binding_revision": 1,
                    "actor_registry_assignment_id": "assignment-agent_1",
                    "actor_registry_assignment_revision": 1,
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertTrue(packet["session_created"])
            self.assertTrue(packet["actor_registry_reference_present"])
            self.assertEqual(packet["actor_registry_reference"]["binding_id"], "binding-agent_1")
            self.assertEqual(packet["actor_registry_reference"]["assignment_revision"], 1)
            self.assertEqual(
                packet["session"]["actor_registry_reference"]["slot_id"],
                "agent_1",
            )

    def test_session_create_without_reference_keeps_legacy_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ccs.CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.5",
                    "coding_agent_model_id": "wbp-web-primary-openrouter",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )

            self.assertEqual(packet["status"], "ok")
            self.assertFalse(packet["actor_registry_reference_present"])
            self.assertIsNone(packet["session"]["actor_registry_reference"])

    def test_malformed_actor_registry_reference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ccs.CodexCustomSessionManager(Path(temp_dir))
            packet = manager.create_packet(
                {
                    "primary_model_id": "gpt-5.5",
                    "actor_registry_binding_revision": "not-an-int",
                },
                commands(),
                operator_status(),
                api_snapshot=api_snapshot(),
            )
        self.assertEqual(packet["machine_error_code"], "ACTOR_REGISTRY_REFERENCE_INVALID")


if __name__ == "__main__":
    unittest.main()
