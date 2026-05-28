# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy import runtime


class RuntimeNativeAuthRecoveryTests(unittest.TestCase):
    def test_auth_pool_hygiene_uses_snapshot_as_observed_selection_when_runtime_loaded_ids_empty(
        self,
    ) -> None:
        registry = {
            "backends": [
                {
                    "id": "backend-a",
                    "pool": "active",
                    "status": "healthy",
                    "enabled": True,
                    "auth_ref": "/tmp/backend-a.json",
                    "priority": 10,
                    "fail_count": 0,
                    "success_count": 1,
                },
                {
                    "id": "backend-b",
                    "pool": "active",
                    "status": "healthy",
                    "enabled": True,
                    "auth_ref": "/tmp/backend-b.json",
                    "priority": 20,
                    "fail_count": 0,
                    "success_count": 1,
                },
            ]
        }
        snapshot = runtime.build_selected_backend_snapshot_payload(
            selected_backend_ids=["backend-a", "backend-b"],
            observed_at_utc="2026-05-29T00:00:00+00:00",
            source_class="supervisor_owner_observed",
            source_name="sync --json",
            source_run_id="sync:2026-05-29T00:00:00+00:00",
            producer_version="2",
        )
        state = {
            "selected_backend_ids": [],
            "selected_backend_snapshot": snapshot,
        }

        with unittest.mock.patch("wild_boar_proxy.runtime.now_iso", return_value="2026-05-29T00:00:30+00:00"):
            hygiene = runtime.summarize_auth_pool_hygiene(registry, state)

        self.assertEqual(
            hygiene["selected_backend_ids_observed"],
            ["backend-a", "backend-b"],
        )
        self.assertEqual(hygiene["selected_backend_ids_runtime_loaded"], [])
        self.assertEqual(
            hygiene["selected_backend_observation_source"],
            "runtime_state.selected_backend_snapshot",
        )
        self.assertEqual(hygiene["selected_backend_runtime_loaded_count"], 0)
        self.assertEqual(hygiene["selected_launch_capable_backend_count"], 2)

    def test_native_auth_recovery_hint_requires_owner_action_after_selected_backend_observation(
        self,
    ) -> None:
        hint = runtime.build_native_auth_recovery_hint(
            machine_error_code="AUTH_UNAVAILABLE",
            auth_pool_hygiene={
                "launch_capable_backend_count": 15,
                "selected_backend_ids_observed": ["backend-a"],
                "selected_backend_ids_runtime_loaded": [],
                "selected_backend_observation_source": "runtime_state.selected_backend_snapshot",
            },
        )

        self.assertEqual(hint["status"], "owner_action_required")
        self.assertTrue(hint["owner_action_required"])
        self.assertEqual(hint["next_action"], "accounts_login_start")
        self.assertEqual(
            hint["command_surface"],
            "accounts login start --provider codex --mode device --json",
        )
        self.assertTrue(hint["selection_gap_detected"])

    def test_native_auth_recovery_hint_recommends_sync_without_selected_backend_observation(
        self,
    ) -> None:
        hint = runtime.build_native_auth_recovery_hint(
            machine_error_code="AUTH_UNAVAILABLE",
            auth_pool_hygiene={
                "launch_capable_backend_count": 3,
                "selected_backend_ids_observed": [],
                "selected_backend_ids_runtime_loaded": [],
                "selected_backend_observation_source": "",
            },
        )

        self.assertEqual(hint["status"], "sync_recommended")
        self.assertFalse(hint["owner_action_required"])
        self.assertEqual(hint["next_action"], "sync")
        self.assertEqual(hint["command_surface"], "sync --json")


if __name__ == "__main__":
    unittest.main()
