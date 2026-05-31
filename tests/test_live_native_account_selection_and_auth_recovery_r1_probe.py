# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

from tools import live_native_account_selection_and_auth_recovery_r1_probe as probe


def _state_snapshot(
    selected_count: int,
    snapshot_count: int,
) -> dict[str, object]:
    return {
        "selected_backend_ids": [f"backend-{idx}" for idx in range(selected_count)],
        "selected_backend_ids_count": selected_count,
        "selected_backend_ids_observed_at": "2026-05-29T00:00:00+00:00",
        "stable_default_backend_id": "backend-0",
        "selected_backend_snapshot_present": snapshot_count > 0,
        "selected_backend_snapshot_ids": [f"backend-{idx}" for idx in range(snapshot_count)],
        "selected_backend_snapshot_count": snapshot_count,
        "selected_backend_snapshot_observed_at": "2026-05-29T00:00:00+00:00",
    }


class LiveNativeAccountSelectionAndAuthRecoveryProbeTests(unittest.TestCase):
    def test_build_packets_localizes_owner_action_required_after_sync_and_503_probe(
        self,
    ) -> None:
        state_sequence = iter(
            [
                _state_snapshot(0, 15),
                _state_snapshot(15, 15),
                _state_snapshot(0, 15),
            ]
        )

        def fake_state_snapshot() -> dict[str, object]:
            return next(state_sequence)

        def fake_run_json_command(_repo_root: Path, args: list[str]) -> dict[str, object]:
            if args == ["sync", "--json"]:
                return {"stdout_json": {"machine_error_code": "OK", "effective_mode": "stable"}}
            if args == ["healthcheck", "--json"]:
                return {
                    "stdout_json": {
                        "machine_error_code": "AUTH_UNAVAILABLE",
                        "auth_pool_hygiene": {
                            "launch_capable_backend_count": 15,
                            "selected_backend_ids_observed": ["backend-0"],
                            "selected_backend_ids_runtime_loaded": [],
                            "selected_backend_runtime_loaded_count": 0,
                            "selected_backend_observation_source": "runtime_state.selected_backend_snapshot",
                            "selected_backend_snapshot_validation_status": "valid",
                        },
                        "native_auth_recovery_hint": {
                            "status": "owner_action_required",
                            "owner_action_required": True,
                            "next_action": "accounts_login_start",
                            "command_surface": "accounts login start --provider codex --mode device --json",
                            "selection_gap_detected": True,
                        },
                    }
                }
            if args == ["status", "--json"]:
                return {
                    "stdout_json": {
                        "machine_error_code": "AUTH_UNAVAILABLE",
                        "effective_mode": "stable",
                        "endpoint": "http://127.0.0.1:8318/v1",
                        "configured_model": "gpt-5.5",
                        "auth_pool_hygiene": {
                            "selected_backend_ids_observed": ["backend-0"],
                            "selected_backend_observation_source": "runtime_state.selected_backend_snapshot",
                        },
                    }
                }
            return {
                "stdout_json": {
                    "accounts": [{"id": "backend-0"}, {"id": "backend-1"}],
                }
            }

        with (
            mock.patch.object(probe, "_managed_state_snapshot", side_effect=fake_state_snapshot),
            mock.patch.object(probe, "_run_json_command", side_effect=fake_run_json_command),
            mock.patch.object(
                probe,
                "_direct_native_probe",
                return_value={"status": "http_error", "http_status": 503, "body_preview": ""},
            ),
        ):
            packets = probe.build_packets(repo_root=Path("/Volumes/Work/wild-boar-proxy"))

        selection = packets["native_backend_selection_truth_packet.json"]
        recovery = packets["native_auth_recovery_attempt_packet.json"]
        failure = packets["native_auth_failure_taxonomy_packet.json"]
        audit = packets["independent_audit_packet.json"]

        self.assertTrue(selection["sync_repopulated_selected_backend_ids"])
        self.assertEqual(
            selection["health_selected_backend_observation_source"],
            "runtime_state.selected_backend_snapshot",
        )
        self.assertTrue(recovery["owner_action_required"])
        self.assertEqual(recovery["next_action"], "accounts_login_start")
        self.assertTrue(recovery["hard_blocker_precisely_localized"])
        self.assertTrue(failure["auth_unavailable_present"])
        self.assertTrue(audit["selection_truth_recovered_but_runtime_auth_still_blocked"])


if __name__ == "__main__":
    unittest.main()
