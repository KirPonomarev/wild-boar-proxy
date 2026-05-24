# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.review_bridge_command_bus import (
    ALLOWLIST,
    execute_review_command,
    review_allowlist_metadata,
)
from wild_boar_proxy.review_bridge_packet_import import ReviewImportContext
from wild_boar_proxy.review_bridge_session_store import ReviewQueryBridge, ReviewSessionStore


IMPORT_CONTEXT = ReviewImportContext(
    project_id="project-alpha",
    baseline_hash="sha256:baseline-alpha",
)


def review_packet(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "project_id": "project-alpha",
        "baseline_hash": "sha256:baseline-alpha",
        "review_items": [{"id": "change-1", "kind": "exact_text"}],
        "orphan_comments": [],
        "diagnostics": [],
    }
    payload.update(overrides)
    return payload


class ReviewBridgeCommandBusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReviewSessionStore()
        self.query = ReviewQueryBridge(self.store)

    def test_allowlist_is_explicit_and_apply_is_reserved(self) -> None:
        self.assertEqual(
            set(ALLOWLIST),
            {"import_review_packet", "clear_review_session", "apply_exact_text_change"},
        )
        self.assertFalse(ALLOWLIST["apply_exact_text_change"].runtime_enabled)
        self.assertIn(
            {
                "command_id": "apply_exact_text_change",
                "required_args": [],
                "allowed_args": [],
                "runtime_enabled": False,
            },
            review_allowlist_metadata(),
        )

    def test_import_review_packet_is_admitted_through_command_bus(self) -> None:
        result = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["machine_error_code"], "OK")
        self.assertEqual(result["changed_files"], [])
        self.assertEqual(result["next_action"], "query_review_surface")

        surface = self.query.get_review_surface()
        self.assertEqual(surface["status"], "ok")
        self.assertTrue(surface["session_present"])
        self.assertEqual(surface["project_id"], "project-alpha")
        self.assertTrue(str(surface["session_id"]).startswith("review-import-"))
        self.assertEqual(surface["baseline_hash"], "sha256:baseline-alpha")
        self.assertTrue(str(surface["source_packet_hash"]).startswith("sha256:"))
        self.assertEqual(surface["review_surface"]["items"][0]["id"], "change-1")
        self.assertEqual(surface["revision_session"]["mode"], "review_only")
        self.assertIsInstance(surface["created_at"], str)

    def test_clear_review_session_runs_through_command_bus(self) -> None:
        execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        cleared = execute_review_command(self.store, "clear_review_session", payload={})

        self.assertEqual(cleared["status"], "ok")
        self.assertEqual(cleared["machine_error_code"], "OK")
        self.assertEqual(cleared["changed_files"], [])
        self.assertEqual(cleared["data"]["cleared"], True)
        self.assertEqual(
            self.query.get_review_surface(),
            {
                "status": "empty",
                "machine_error_code": "REVIEW_SESSION_EMPTY",
                "session_present": False,
                "review_surface": None,
                "revision_session": None,
            },
        )

    def test_apply_exact_text_change_is_reserved_and_not_enabled(self) -> None:
        result = execute_review_command(
            self.store,
            "apply_exact_text_change",
            payload={},
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["machine_error_code"], "REVIEW_APPLY_NOT_ENABLED")
        self.assertEqual(result["changed_files"], [])
        self.assertFalse(self.store.has_active_session())

    def test_query_bridge_is_read_only_and_does_not_expose_mutation_methods(self) -> None:
        self.assertTrue(hasattr(self.query, "get_review_surface"))
        self.assertFalse(hasattr(self.query, "execute_review_command"))
        self.assertFalse(hasattr(self.query, "import_review_packet"))
        self.assertFalse(hasattr(self.query, "clear_review_session"))

    def test_import_rejects_missing_fields_and_unknown_args(self) -> None:
        missing = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": {"schema_version": 1, "project_id": "project-alpha"}},
            import_context=IMPORT_CONTEXT,
        )
        extra = execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet(), "packet_text": "{bad-idea}"},
            import_context=IMPORT_CONTEXT,
        )

        self.assertEqual(missing["status"], "command_error")
        self.assertEqual(missing["machine_error_code"], "REVIEW_PACKET_MISSING_FIELD")
        self.assertEqual(extra["status"], "command_error")
        self.assertEqual(extra["machine_error_code"], "REVIEW_COMMAND_UNSUPPORTED_ARGS")

    def test_repeated_query_reads_do_not_mutate_store_state(self) -> None:
        execute_review_command(
            self.store,
            "import_review_packet",
            payload={"review_packet": review_packet()},
            import_context=IMPORT_CONTEXT,
        )

        first = self.query.get_review_surface()
        second = self.query.get_review_surface()

        self.assertEqual(first, second)

    def test_unknown_command_is_blocked_as_direct_bypass(self) -> None:
        result = execute_review_command(self.store, "launch_client", payload={})
        self.assertEqual(result["status"], "command_error")
        self.assertEqual(result["machine_error_code"], "REVIEW_COMMAND_NOT_ALLOWLISTED")


if __name__ == "__main__":
    unittest.main()
