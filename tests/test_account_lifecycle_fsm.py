from __future__ import annotations

import ast
import unittest
from pathlib import Path

from wild_boar_proxy import accounts_lifecycle


ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS_LIFECYCLE = ROOT / "wild_boar_proxy" / "accounts_lifecycle.py"


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return ""


def _function(path: Path, name: str) -> ast.FunctionDef:
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Function not found: {path}:{name}")


def _call_names(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            dotted = _dotted_name(child.func)
            if dotted:
                calls.add(dotted)
                calls.add(dotted.rsplit(".", 1)[-1])
    return calls


class AccountLifecycleFsmTests(unittest.TestCase):
    def test_effective_state_matrix(self) -> None:
        cases = (
            ("reserve", False, "reserve"),
            ("reserve", True, "held_reserve"),
            ("active", False, "active"),
            ("active", True, "held_active"),
            ("retired", False, "retired"),
            ("retired", True, "retired"),
            ("unexpected", False, "invalid_pool"),
        )

        for pool, manual_hold, expected in cases:
            with self.subTest(pool=pool, manual_hold=manual_hold):
                self.assertEqual(
                    accounts_lifecycle.classify_account_lifecycle_state(
                        pool, manual_hold
                    ),
                    expected,
                )

    def test_allowed_transition_matrix(self) -> None:
        cases = (
            ("new_auth", "onboard", "allowed", "reserve", "new_auth_to_reserve"),
            (
                "reserve",
                "promote",
                "conditional",
                "active",
                "promotion_requires_validation_sync_policy",
            ),
            ("active", "demote", "allowed", "reserve", "eligible"),
            ("active", "hold", "allowed", "held_active", "eligible"),
            ("held_active", "release", "allowed", "reserve", "eligible"),
            ("held_reserve", "release", "allowed", "reserve", "eligible"),
            ("reserve", "retire", "allowed", "retired", "eligible"),
            ("active", "retire", "allowed", "retired", "eligible"),
            ("held_reserve", "retire", "allowed", "retired", "eligible"),
            ("held_active", "retire", "allowed", "retired", "eligible"),
        )

        for source, action, status, target, precondition in cases:
            with self.subTest(source=source, action=action):
                transition = accounts_lifecycle.classify_account_lifecycle_transition(
                    source, action
                )
                self.assertEqual(transition["transition_status"], status)
                self.assertEqual(transition["target_state"], target)
                self.assertEqual(transition["precondition_status"], precondition)

    def test_forbidden_transition_matrix(self) -> None:
        cases = (
            ("new_auth", "promote", "new_auth_active_forbidden"),
            ("held_reserve", "promote", "held_backend_release_required"),
            ("held_active", "promote", "held_backend_release_required"),
            ("retired", "promote", "backend_retired"),
            ("retired", "demote", "backend_retired"),
            ("retired", "hold", "backend_retired"),
            ("retired", "release", "backend_retired"),
            ("held_active", "demote", "held_backend_release_required"),
            ("active", "release", "not_on_hold"),
        )

        for source, action, precondition in cases:
            with self.subTest(source=source, action=action):
                transition = accounts_lifecycle.classify_account_lifecycle_transition(
                    source, action
                )
                self.assertEqual(transition["transition_status"], "forbidden")
                self.assertEqual(transition["target_state"], "")
                self.assertEqual(transition["precondition_status"], precondition)

    def test_retired_is_terminal_without_held_retired_state(self) -> None:
        self.assertNotIn(
            "held_retired", accounts_lifecycle.ACCOUNT_LIFECYCLE_EFFECTIVE_STATES
        )
        self.assertEqual(
            accounts_lifecycle.classify_account_lifecycle_state("retired", True),
            "retired",
        )
        transition = accounts_lifecycle.classify_account_lifecycle_transition(
            "retired", "retire"
        )
        self.assertEqual(transition["transition_status"], "noop")
        self.assertEqual(transition["target_state"], "retired")
        self.assertEqual(transition["precondition_status"], "already_retired")
        self.assertIs(transition["terminal"], True)
        self.assertIs(transition["return_path_allowed"], False)

    def test_promotion_requires_validation_sync_and_policy(self) -> None:
        transition = accounts_lifecycle.classify_account_lifecycle_transition(
            "reserve", "promote"
        )

        self.assertEqual(transition["transition_status"], "conditional")
        self.assertEqual(
            transition["precondition_status"],
            "promotion_requires_validation_sync_policy",
        )
        self.assertIs(transition["requires_validation_sync_policy"], True)

    def test_release_never_returns_to_active(self) -> None:
        for source in ("held_reserve", "held_active"):
            with self.subTest(source=source):
                transition = accounts_lifecycle.classify_account_lifecycle_transition(
                    source, "release"
                )
                self.assertEqual(transition["transition_status"], "allowed")
                self.assertEqual(transition["target_state"], "reserve")

    def test_protective_precondition_adapter_maps_packet_vocabulary(self) -> None:
        cases = (
            ("reserve", False, "hold", "reserve", "eligible_backend_for_hold", True),
            ("active", False, "hold", "active", "eligible_backend_for_hold", True),
            ("reserve", True, "hold", "held_reserve", "already_held", True),
            ("active", True, "hold", "held_active", "already_held", True),
            (
                "reserve",
                True,
                "release",
                "held_reserve",
                "eligible_backend_for_release",
                True,
            ),
            (
                "active",
                True,
                "release",
                "held_active",
                "eligible_backend_for_release",
                True,
            ),
            ("reserve", False, "release", "reserve", "not_on_hold", True),
            ("active", False, "release", "active", "not_on_hold", True),
            ("retired", False, "hold", "retired", "backend_retired", True),
            ("retired", True, "release", "retired", "backend_retired", True),
            (
                "unexpected",
                False,
                "hold",
                "invalid_pool",
                "invalid_lifecycle_precondition",
                False,
            ),
        )

        for pool, manual_hold, action, state, precondition, mapped in cases:
            with self.subTest(pool=pool, manual_hold=manual_hold, action=action):
                result = (
                    accounts_lifecycle.classify_protective_lifecycle_precondition(
                        pool, manual_hold, action
                    )
                )
                self.assertEqual(result["effective_state"], state)
                self.assertEqual(
                    result["protective_precondition_status"], precondition
                )
                self.assertIs(result["mapped_to_packet_vocabulary"], mapped)

    def test_protective_release_adapter_never_targets_active(self) -> None:
        for pool in ("reserve", "active"):
            with self.subTest(pool=pool):
                result = (
                    accounts_lifecycle.classify_protective_lifecycle_precondition(
                        pool, True, "release"
                    )
                )
                self.assertEqual(result["target_state"], "reserve")
                self.assertNotEqual(result["target_state"], "active")

    def test_onboard_precondition_adapter_maps_new_auth_to_reserve(self) -> None:
        result = accounts_lifecycle.classify_onboard_lifecycle_precondition()

        self.assertEqual(result["effective_state"], "new_auth")
        self.assertEqual(result["transition_status"], "allowed")
        self.assertEqual(result["target_state"], "reserve")
        self.assertEqual(result["precondition_status"], "new_auth_to_reserve")
        self.assertEqual(result["onboard_precondition_status"], "new_auth_to_reserve")
        self.assertIs(result["mapped_to_packet_vocabulary"], True)

    def test_onboard_precondition_adapter_rejects_non_new_auth_sources(self) -> None:
        for source_state in ("reserve", "active", "held_reserve", "retired"):
            with self.subTest(source_state=source_state):
                result = accounts_lifecycle.classify_onboard_lifecycle_precondition(
                    source_state
                )
                self.assertEqual(
                    result["onboard_precondition_status"],
                    "invalid_lifecycle_precondition",
                )
                self.assertIs(result["mapped_to_packet_vocabulary"], False)

    def test_onboard_adapter_keeps_runtime_proof_out_of_fsm(self) -> None:
        result = accounts_lifecycle.classify_onboard_lifecycle_precondition()

        self.assertNotIn("selected_backend_id", result)
        self.assertNotIn("reserve_first_enforced", result)
        self.assertNotIn("active_routing_changed", result)
        self.assertNotIn("validate_attempted", result)
        self.assertNotIn("sync_attempted", result)
        self.assertNotIn("status_observed", result)
        self.assertNotIn("machine_error_code", result)
        self.assertNotIn("human_message", result)

    def test_promote_precondition_adapter_maps_packet_vocabulary(self) -> None:
        cases = (
            ("reserve", False, "reserve", "eligible_reserve_backend", True),
            ("reserve", True, "held_reserve", "backend_on_hold", True),
            ("active", False, "active", "backend_not_reserve", True),
            ("active", True, "held_active", "backend_on_hold", True),
            ("retired", False, "retired", "backend_retired", True),
            ("retired", True, "retired", "backend_retired", True),
            (
                "unexpected",
                False,
                "invalid_pool",
                "invalid_lifecycle_precondition",
                False,
            ),
        )

        for pool, manual_hold, state, precondition, mapped in cases:
            with self.subTest(pool=pool, manual_hold=manual_hold):
                result = accounts_lifecycle.classify_promote_lifecycle_precondition(
                    pool, manual_hold
                )
                self.assertEqual(result["effective_state"], state)
                self.assertEqual(result["promote_precondition_status"], precondition)
                self.assertIs(result["mapped_to_packet_vocabulary"], mapped)

    def test_promote_adapter_keeps_policy_and_validation_out_of_fsm(self) -> None:
        result = accounts_lifecycle.classify_promote_lifecycle_precondition(
            "reserve", False
        )

        self.assertEqual(result["promote_precondition_status"], "eligible_reserve_backend")
        self.assertIs(result["requires_validation_sync_policy"], True)
        self.assertNotIn("pool_policy_status", result)
        self.assertNotIn("active_pool_count_before", result)
        self.assertNotIn("validate_attempted", result)
        self.assertNotIn("machine_error_code", result)
        self.assertNotIn("human_message", result)

    def test_demote_precondition_adapter_maps_packet_vocabulary(self) -> None:
        cases = (
            ("active", False, "active", "eligible_active_backend_for_demote", True),
            ("reserve", False, "reserve", "already_reserve", True),
            ("active", True, "held_active", "backend_held", True),
            ("reserve", True, "held_reserve", "backend_held", True),
            ("retired", False, "retired", "backend_retired", True),
            ("retired", True, "retired", "backend_retired", True),
            (
                "unexpected",
                False,
                "invalid_pool",
                "invalid_lifecycle_precondition",
                False,
            ),
        )

        for pool, manual_hold, state, precondition, mapped in cases:
            with self.subTest(pool=pool, manual_hold=manual_hold):
                result = accounts_lifecycle.classify_demote_lifecycle_precondition(
                    pool, manual_hold
                )
                self.assertEqual(result["effective_state"], state)
                self.assertEqual(result["demote_precondition_status"], precondition)
                self.assertIs(result["mapped_to_packet_vocabulary"], mapped)

    def test_demote_adapter_keeps_runtime_proof_out_of_fsm(self) -> None:
        result = accounts_lifecycle.classify_demote_lifecycle_precondition(
            "reserve", False
        )

        self.assertEqual(result["demote_precondition_status"], "already_reserve")
        self.assertNotIn("reserve_return_confirmed", result)
        self.assertNotIn("machine_error_code", result)
        self.assertNotIn("human_message", result)

    def test_retire_precondition_adapter_maps_packet_vocabulary(self) -> None:
        cases = (
            ("active", False, "active", "eligible_active_backend_for_retire", True),
            (
                "active",
                True,
                "held_active",
                "eligible_active_backend_for_retire",
                True,
            ),
            ("reserve", False, "reserve", "eligible_reserve_backend_for_retire", True),
            (
                "reserve",
                True,
                "held_reserve",
                "eligible_reserve_backend_for_retire",
                True,
            ),
            ("retired", False, "retired", "already_retired", True),
            ("retired", True, "retired", "already_retired", True),
            (
                "unexpected",
                False,
                "invalid_pool",
                "invalid_lifecycle_precondition",
                False,
            ),
        )

        for pool, manual_hold, state, precondition, mapped in cases:
            with self.subTest(pool=pool, manual_hold=manual_hold):
                result = accounts_lifecycle.classify_retire_lifecycle_precondition(
                    pool, manual_hold
                )
                self.assertEqual(result["effective_state"], state)
                self.assertEqual(result["retire_precondition_status"], precondition)
                self.assertIs(result["mapped_to_packet_vocabulary"], mapped)

    def test_retire_adapter_keeps_runtime_proof_out_of_fsm(self) -> None:
        result = accounts_lifecycle.classify_retire_lifecycle_precondition(
            "retired", False
        )

        self.assertEqual(result["retire_precondition_status"], "already_retired")
        self.assertNotIn("terminal_no_return_confirmed", result)
        self.assertNotIn("machine_error_code", result)
        self.assertNotIn("human_message", result)

    def test_fsm_helpers_are_pure(self) -> None:
        forbidden_calls = {
            "Path",
            "build_command_payload",
            "open",
            "read_json",
            "read_text",
            "run_bounded_process",
            "serialized_lock",
            "subprocess.run",
            "write_json_atomic",
            "write_text_atomic",
        }

        for function in (
            "classify_account_lifecycle_state",
            "classify_account_lifecycle_transition",
            "classify_protective_lifecycle_precondition",
            "classify_onboard_lifecycle_precondition",
            "classify_promote_lifecycle_precondition",
            "classify_demote_lifecycle_precondition",
            "classify_retire_lifecycle_precondition",
        ):
            with self.subTest(function=function):
                calls = _call_names(_function(ACCOUNTS_LIFECYCLE, function))
                self.assertEqual(calls & forbidden_calls, set())


if __name__ == "__main__":
    unittest.main()
