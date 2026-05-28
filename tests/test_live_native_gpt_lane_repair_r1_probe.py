# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from unittest import mock
import unittest

from wild_boar_proxy.model_availability import (
    build_catalog_availability_lattice_packet,
    build_model_direct_preflight_packet,
)
from tools import live_native_gpt_lane_repair_r1_probe as probe


class _FakeSession:
    def status_payload(self) -> dict[str, object]:
        return {
            "status": {
                "status": "ok",
                "machine_error_code": "AUTH_UNAVAILABLE",
                "configured_model": "gpt-5.5",
                "endpoint": "127.0.0.1:8318",
            },
            "health": {"status": "degraded", "machine_error_code": "AUTH_UNAVAILABLE"},
            "claim_gate": {"status": "passed"},
            "models": {
                "ok": True,
                "model_ids": ["gpt-5.5", "gpt-5.4-mini"],
                "server_issued": True,
            },
        }


def _fake_run_json_command(_repo_root: Path, args: list[str]) -> dict[str, object]:
    if args == ["status", "--json"]:
        return {
            "stdout_json": {
                "machine_error_code": "AUTH_UNAVAILABLE",
                "pool_summary": {"selected_backend_ids": []},
            }
        }
    if args == ["healthcheck", "--json"]:
        return {"stdout_json": {"machine_error_code": "AUTH_UNAVAILABLE"}}
    return {
        "stdout_json": {
            "status": "ok",
            "data": {
                "routes": [
                    {
                        "route_id": "wbp-web-primary-openrouter",
                        "enabled": True,
                        "auth": {"secret_ref": "OPENROUTER_API_KEY"},
                    }
                ]
            },
        }
    }


def _fake_lattice() -> dict[str, object]:
    return build_catalog_availability_lattice_packet(
        catalog_packet={
            "models": [
                {"model_id": "gpt-5.5", "lane": "codex_native"},
                {"model_id": "gpt-5.4-mini", "lane": "codex_native"},
            ]
        },
        current_model_packets=[
            build_model_direct_preflight_packet(
                model_id="gpt-5.5",
                source="current_live_native_probe",
                listed=True,
                selectable=True,
                route_selected=True,
                runtime_ready=True,
                http_status=503,
                error_payload={
                    "machine_error_code": "AUTH_UNAVAILABLE",
                    "error": {"type": "auth_error"},
                },
                prompt_text="Reply OK",
                request_sent_to_wbp=True,
                route_family="codex_native_account_route",
            ),
            build_model_direct_preflight_packet(
                model_id="gpt-5.4-mini",
                source="current_live_native_probe",
                listed=True,
                selectable=True,
                route_selected=True,
                runtime_ready=True,
                http_status=402,
                error_payload={
                    "machine_error_code": "DEACTIVATED_WORKSPACE",
                    "error": {"type": "invalid_request_error"},
                },
                prompt_text="Reply OK",
                request_sent_to_wbp=True,
                route_family="codex_native_account_route",
            ),
        ],
    )


class LiveNativeGptLaneRepairProbeTests(unittest.TestCase):
    def test_build_packets_localizes_native_blocker_and_preserves_api_bridge_visibility(self) -> None:
        with (
            mock.patch.object(probe, "OperatorSurfaceSession", return_value=_FakeSession()),
            mock.patch.object(probe, "_run_json_command", side_effect=_fake_run_json_command),
            mock.patch.object(
                probe,
                "_build_live_native_availability",
                return_value=_fake_lattice(),
            ),
            mock.patch.object(
                probe,
                "_bridge_model_ids",
                return_value=["wbp-web-primary-openrouter"],
            ),
        ):
            packets = probe.build_packets(repo_root=Path("/Volumes/Work/wild-boar-proxy"))

        inventory = packets["native_lane_live_inventory_packet.json"]
        repair = packets["native_lane_repair_packet.json"]
        taxonomy = packets["native_lane_failure_taxonomy_packet.json"]

        self.assertFalse(inventory["native_lane_runnable"])
        self.assertEqual(
            sorted(inventory["blocked_native_model_ids"]),
            ["gpt-5.4-mini", "gpt-5.5"],
        )
        self.assertTrue(inventory["api_lane_visible_after_gate"])
        self.assertTrue(repair["hard_blocker_precisely_localized"])
        self.assertTrue(repair["selector_native_disabled_consistent"])
        self.assertTrue(taxonomy["auth_unavailable_present"])
        self.assertTrue(taxonomy["workspace_deactivated_present"])


if __name__ == "__main__":
    unittest.main()
