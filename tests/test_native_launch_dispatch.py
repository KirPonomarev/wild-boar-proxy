# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import unittest

from wild_boar_proxy.native_launch_contract import build_native_custom_preflight_packet
from wild_boar_proxy.native_launch_dispatch import (
    build_native_cleanup_rollback_execution_packet,
    build_native_current_codex_protection_packet,
    build_native_custom_dispatch_blocked_packet,
    build_native_custom_dispatch_packet,
    build_native_dispatch_authorization_packet,
    build_native_dispatch_false_green_audit,
    build_native_original_dispatch_deferred_packet,
    build_native_process_observation_packet,
    build_native_window_observation_packet,
    build_native_window_usability_packet,
)


def native_command() -> dict[str, object]:
    return {
        "schema_version": 1,
        "command_id": "cmd-native",
        "launch_mode": "CODEX_CUSTOM_NATIVE_APP",
    }


def custom_admission_plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "target_candidate_source": "repo_or_server_owned_launcher_candidate",
        "isolated_home_plan": True,
        "isolated_codex_home_plan": True,
        "isolated_profile_data_dir_plan": True,
        "server_planned_route_endpoint": True,
        "port_separation_plan": True,
        "cleanup_command_plan": True,
        "rollback_expectation_declared": True,
        "current_codex_snapshot_plan": True,
        "write_surfaces_declared": True,
        "declared_write_surfaces": [
            "server_owned_temp_home",
            "server_owned_temp_codex_home",
            "server_owned_profile_dir",
            "launch_receipt",
        ],
    }
    plan.update(overrides)
    return plan


def admitted_custom_packet(**overrides: object) -> dict[str, object]:
    return build_native_custom_preflight_packet(
        native_command(),
        custom_admission_plan(**overrides),
    )


class NativeLaunchDispatchTests(unittest.TestCase):
    def test_authorization_blocks_without_owner_authorization(self) -> None:
        packet = build_native_dispatch_authorization_packet(
            owner_authorized=False,
            admission_packet=admitted_custom_packet(),
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(
            packet["machine_error_code"],
            "NATIVE_DISPATCH_OWNER_AUTHORIZATION_MISSING",
        )
        self.assertFalse(packet["live_dispatch_allowed"])
        self.assertEqual(packet["blocked_reason_class"], "owner_authorization_missing")

    def test_authorization_blocks_without_admitted_custom_preflight(self) -> None:
        packet = build_native_dispatch_authorization_packet(
            owner_authorized=True,
            admission_packet={"status": "blocked", "admitted": False},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_DISPATCH_ADMISSION_NOT_ADMITTED")

    def test_custom_dispatch_blocked_packet_does_not_attempt_dispatch(self) -> None:
        packet = build_native_custom_dispatch_blocked_packet(
            owner_authorized=False,
            admission_packet=admitted_custom_packet(),
        )

        self.assertEqual(packet["packet_kind"], "native_custom_dispatch_blocked")
        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["dispatch_attempted"])
        self.assertFalse(packet["process_observed"])
        self.assertFalse(packet["window_observed"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertFalse(packet["route_trace_bound"])

    def test_custom_dispatch_full_slice_pass_with_window_observed_still_not_complete(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={
                "before_snapshot_captured": True,
                "after_snapshot_captured": True,
                "current_codex_touched": False,
            },
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["dispatch_slice_pass"])
        self.assertTrue(packet["dispatch_observed"])
        self.assertTrue(packet["process_observed"])
        self.assertTrue(packet["window_observed"])
        self.assertTrue(packet["native_window_usable"])
        self.assertTrue(packet["native_window_usable_claimed"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertFalse(packet["prompt_attempted"])
        self.assertFalse(packet["route_trace_bound"])
        self.assertFalse(packet["route_inference_attempted"])

    def test_custom_dispatch_accepts_honest_window_observation_blocked_reason(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={
                "window_observed": False,
                "blocked_reason_class": "os_window_query_unavailable",
            },
            usability_observation={
                "native_window_usable": False,
                "native_window_usable_claimed": False,
                "blocked_reason_class": "window_usability_unclassifiable_without_os_window",
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["window_observation_blocked_with_reason"])
        self.assertEqual(
            packet["window_observation_blocked_reason_class"],
            "os_window_query_unavailable",
        )
        self.assertTrue(packet["usability_blocked_with_reason"])
        self.assertIn("native_window_usability_required", packet["failed_checks"])
        self.assertFalse(packet["native_launch_complete"])

    def test_custom_dispatch_blocks_process_only_proof(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": False},
            usability_observation={"native_window_usable": False},
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("window_observation_or_blocked_reason_required", packet["failed_checks"])
        self.assertFalse(packet["native_launch_complete"])

    def test_custom_dispatch_blocks_cleanup_failure(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "blocked"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("cleanup_or_rollback_ok_required", packet["failed_checks"])

    def test_custom_dispatch_blocks_current_codex_touch(self) -> None:
        packet = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": True},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertIn("current_codex_must_remain_untouched", packet["failed_checks"])

    def test_observation_packets_do_not_claim_prompt_or_routing(self) -> None:
        process = build_native_process_observation_packet(
            dispatch_observed=True,
            process_observed=True,
        )
        window = build_native_window_observation_packet(window_observed=True)
        usability = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=True,
        )

        self.assertEqual(process["status"], "ok")
        self.assertFalse(process["native_launch_complete"])
        self.assertFalse(process["prompt_attempted"])
        self.assertFalse(process["route_trace_bound"])
        self.assertEqual(window["status"], "ok")
        self.assertFalse(window["native_window_usable"])
        self.assertFalse(window["native_window_usable_claimed"])
        self.assertFalse(window["native_launch_complete"])
        self.assertEqual(usability["status"], "ok")
        self.assertTrue(usability["native_window_usable"])
        self.assertTrue(usability["native_window_usable_claimed"])
        self.assertFalse(usability["prompt_attempted"])
        self.assertFalse(usability["route_trace_bound"])
        self.assertFalse(usability["native_launch_complete"])

    def test_window_observation_requires_window_or_blocked_reason(self) -> None:
        packet = build_native_window_observation_packet(window_observed=False)

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_WINDOW_OBSERVATION_MISSING")

    def test_window_usability_requires_usability_or_blocked_reason(self) -> None:
        packet = build_native_window_usability_packet(
            window_observed=True,
            input_capable_ui_observed=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_WINDOW_USABILITY_NOT_PROVEN")

    def test_window_usability_accepts_honest_blocked_reason(self) -> None:
        packet = build_native_window_usability_packet(
            window_observed=False,
            input_capable_ui_observed=False,
            blocked_reason_class="owner_authorization_missing",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertFalse(packet["native_window_usable"])
        self.assertFalse(packet["native_launch_complete"])
        self.assertEqual(packet["blocked_reason_class"], "owner_authorization_missing")

    def test_current_codex_protection_requires_before_after_and_untouched(self) -> None:
        packet = build_native_current_codex_protection_packet(
            before_snapshot_captured=True,
            after_snapshot_captured=False,
            current_codex_touched=False,
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertFalse(packet["current_codex_protected"])

    def test_current_codex_protection_accepts_no_live_dispatch_basis(self) -> None:
        packet = build_native_current_codex_protection_packet(
            before_snapshot_captured=False,
            after_snapshot_captured=False,
            current_codex_touched=False,
            protection_basis="no_live_dispatch_attempted",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["current_codex_protected"])
        self.assertEqual(packet["protection_basis"], "no_live_dispatch_attempted")

    def test_cleanup_rollback_packet_requires_ok_status(self) -> None:
        packet = build_native_cleanup_rollback_execution_packet(
            cleanup_attempted=True,
            rollback_attempted=False,
            cleanup_or_rollback_status="blocked",
        )

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["machine_error_code"], "NATIVE_CLEANUP_ROLLBACK_NOT_OK")

    def test_cleanup_rollback_accepts_no_process_launched_status(self) -> None:
        packet = build_native_cleanup_rollback_execution_packet(
            cleanup_attempted=False,
            rollback_attempted=False,
            cleanup_or_rollback_status="ok_no_process_launched",
            cleanup_blocked_reason_class="owner_authorization_missing_no_live_dispatch",
        )

        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["cleanup_or_rollback_status"], "ok_no_process_launched")
        self.assertEqual(
            packet["cleanup_blocked_reason_class"],
            "owner_authorization_missing_no_live_dispatch",
        )

    def test_original_deferred_packet_preserves_boundary_without_reversibility_claim(self) -> None:
        packet = build_native_original_dispatch_deferred_packet()

        self.assertEqual(packet["status"], "blocked")
        self.assertTrue(packet["original_contract_preserved"])
        self.assertFalse(packet["original_live_dispatch_attempted"])
        self.assertEqual(packet["reason_class"], "out_of_scope_custom_first")
        self.assertFalse(packet["route_trace_bound"])
        self.assertFalse(packet["reversibility_proof_claimed"])

    def test_false_green_audit_rejects_upgrade_claims(self) -> None:
        custom = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )
        custom["native_launch_complete"] = True
        original = build_native_original_dispatch_deferred_packet()

        audit = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=custom,
            original_deferred_packet=original,
        )

        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["machine_error_code"], "NATIVE_DISPATCH_FALSE_GREEN")

    def test_false_green_audit_passes_for_bounded_dispatch_and_deferred_original(self) -> None:
        custom = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": True},
            window_observation={"window_observed": True},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )
        original = build_native_original_dispatch_deferred_packet()

        audit = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=custom,
            original_deferred_packet=original,
        )

        self.assertEqual(audit["status"], "ok")
        self.assertTrue(audit["original_deferred_honestly"])
        self.assertTrue(audit["no_prompt_attempted"])
        self.assertTrue(audit["no_route_inference_attempted"])
        self.assertTrue(audit["native_window_usability_bounded"])
        self.assertTrue(audit["usability_not_upgraded_to_prompt_or_route"])

    def test_false_green_audit_rejects_usability_without_process_and_window(self) -> None:
        custom = build_native_custom_dispatch_packet(
            owner_authorized=True,
            admission_packet=admitted_custom_packet(),
            dispatch_result={"dispatch_attempted": True, "dispatch_observed": True},
            process_observation={"process_observed": False},
            window_observation={"window_observed": False, "blocked_reason_class": "os_window_query_unavailable"},
            usability_observation={
                "native_window_usable": True,
                "native_window_usable_claimed": True,
            },
            protection_packet={"current_codex_touched": False},
            cleanup_packet={"cleanup_or_rollback_status": "ok"},
        )
        original = build_native_original_dispatch_deferred_packet()

        audit = build_native_dispatch_false_green_audit(
            custom_dispatch_packet=custom,
            original_deferred_packet=original,
        )

        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["machine_error_code"], "NATIVE_DISPATCH_FALSE_GREEN")


if __name__ == "__main__":
    unittest.main()
