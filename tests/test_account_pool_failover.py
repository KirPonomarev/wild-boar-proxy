# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for the dedicated account pool failover.

Covers typed outcome normalization, dedicated-provenance guard, exactly-one
replacement admission, no-eligible-replacement fail-closed, ambiguous-delivery
never-replace, budget exhaustion, failed-account reselection exclusion, and
shared core packet semantics for the failover receipt.
"""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import account_pool_failover as f
from wild_boar_proxy.core import packets


def _assert_packet_semantics(testcase: unittest.TestCase, packet: dict) -> None:
    missing = packets.missing_required_fields(packet, list(packets.COMMAND_PACKET_REQUIRED_FIELDS))
    testcase.assertEqual(missing, [], f"missing required: {missing}")
    violations = packets.inspect_command_packet_semantics(packet)
    testcase.assertEqual(violations, [], f"semantic violations: {violations}")
    if packet["status"] == "ok":
        testcase.assertEqual(packet["exit_code"], packets.COMMAND_EXIT_OK)
    else:
        testcase.assertEqual(packet["status"], "error")
        testcase.assertEqual(packet["exit_code"], packets.COMMAND_EXIT_ERROR)


def _dedicated(backend_id: str, **kw) -> f.AccountRef:
    defaults = dict(
        backend_id=backend_id,
        pool="active",
        status="healthy",
        manual_hold=False,
        cooldown_until=None,
        last_error_class=None,
        dedicated_provenance_proven=True,
    )
    defaults.update(kw)
    return f.AccountRef(**defaults)


class TypedOutcomeNormalizationTests(unittest.TestCase):
    def test_quota_429_normalizes_to_quota(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        self.assertEqual(o.outcome, f.ACCOUNT_OUTCOME_FAILURE)
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_QUOTA)
        self.assertTrue(o.is_typed_eligible_failure)

    def test_auth_401_normalizes_to_auth(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, http_status=401, response_observed=True)
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_AUTH)
        self.assertTrue(o.is_typed_eligible_failure)

    def test_auth_403_normalizes_to_auth(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, http_status=403, response_observed=True)
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_AUTH)

    def test_cooldown_signal_normalizes_to_cooldown(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, cooldown_until="2026-07-27T01:00:00Z")
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_COOLDOWN)
        self.assertTrue(o.is_typed_eligible_failure)

    def test_503_normalizes_to_network_not_eligible(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, http_status=503, response_observed=True)
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_NETWORK)
        self.assertFalse(o.is_typed_eligible_failure)

    def test_502_504_normalizes_to_network(self) -> None:
        for code in (502, 504):
            o = f.normalize_dispatch_outcome(success=False, http_status=code, response_observed=True)
            self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_NETWORK)

    def test_unknown_error_normalizes_to_unknown_not_eligible(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, engine_error_text="odd", response_observed=True)
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_UNKNOWN)
        self.assertFalse(o.is_typed_eligible_failure)

    def test_quota_text_signal_normalizes_to_quota(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, engine_error_text="usage_limit_reached", response_observed=True)
        self.assertEqual(o.failure_class, f.ACCOUNT_FAILURE_QUOTA)

    def test_success_outcome_has_no_failure_class(self) -> None:
        o = f.normalize_dispatch_outcome(success=True, http_status=200, response_observed=True)
        self.assertEqual(o.outcome, f.ACCOUNT_OUTCOME_SUCCESS)
        self.assertIsNone(o.failure_class)
        self.assertFalse(o.is_typed_eligible_failure)

    def test_ambiguous_delivery_forces_ambiguous_even_with_429(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, http_status=429, ambiguous_delivery=True)
        self.assertEqual(o.outcome, f.ACCOUNT_OUTCOME_AMBIGUOUS)
        self.assertIsNone(o.failure_class)
        self.assertFalse(o.is_typed_eligible_failure)

    def test_engine_error_text_is_redacted_to_digest(self) -> None:
        o = f.normalize_dispatch_outcome(success=False, http_status=429, engine_error_text="secret detail")
        self.assertIsNotNone(o.engine_error_text_digest)
        self.assertNotIn("secret", json.dumps(o.__dict__))


class ExactlyOneReplacementAdmissionTests(unittest.TestCase):
    def test_quota_failure_admits_exactly_one_replacement(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[b]
        )
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.replacement_account.backend_id, "acct-b")

    def test_replacement_maximum_is_one_per_request(self) -> None:
        self.assertEqual(f.MAX_REPLACEMENT_DISPATCHES_PER_REQUEST, 1)
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        # First failure admits one replacement.
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        d1 = f.decide_request_bound_replacement(failing_account=a, outcome=outcome, state=state, candidate_pool=[b])
        self.assertTrue(d1.admitted)
        # Second failure on the replacement does NOT admit a third (budget=1).
        state_after = f.FailoverState(
            request_id="r1", failed_account_ids=["acct-a"], replacement_dispatches_admitted=1
        )
        outcome2 = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        d2 = f.decide_request_bound_replacement(
            failing_account=b, outcome=outcome2, state=state_after, candidate_pool=[a, b]
        )
        self.assertFalse(d2.admitted)
        self.assertEqual(d2.machine_error_code, "FAILOVER_REPLACEMENT_BUDGET_EXHAUSTED")

    def test_failed_account_not_reselected_same_request(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=["acct-a"], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[a, b]
        )
        # A is the failing account AND in failed set; only B is eligible.
        self.assertTrue(decision.admitted)
        self.assertEqual(decision.replacement_account.backend_id, "acct-b")

    def test_held_candidate_excluded(self) -> None:
        a = _dedicated("acct-a")
        held_b = _dedicated("acct-b", manual_hold=True)
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[held_b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_NO_ELIGIBLE_REPLACEMENT")

    def test_cooldown_candidate_excluded(self) -> None:
        a = _dedicated("acct-a")
        cool_b = _dedicated("acct-b", cooldown_until="2026-07-27T01:00:00Z")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[cool_b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_NO_ELIGIBLE_REPLACEMENT")

    def test_reserve_candidate_excluded(self) -> None:
        a = _dedicated("acct-a")
        reserve_b = _dedicated("acct-b", pool="reserve")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[reserve_b]
        )
        self.assertFalse(decision.admitted)

    def test_non_dedicated_failing_account_rejected(self) -> None:
        non_dedicated = _dedicated("acct-original", dedicated_provenance_proven=False)
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=non_dedicated, outcome=outcome, state=state, candidate_pool=[b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_FAILING_ACCOUNT_NOT_DEDICATED")

    def test_non_dedicated_candidate_excluded(self) -> None:
        a = _dedicated("acct-a")
        non_dedicated_b = _dedicated("acct-b", dedicated_provenance_proven=False)
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[non_dedicated_b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_NO_ELIGIBLE_REPLACEMENT")

    def test_ambiguous_delivery_never_replaces(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, ambiguous_delivery=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_AMBIGUOUS_DELIVERY")

    def test_network_failure_not_eligible(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=503, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_FAILURE_CLASS_NOT_ELIGIBLE")

    def test_success_outcome_no_replacement(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=True, http_status=200, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[b]
        )
        self.assertFalse(decision.admitted)
        self.assertEqual(decision.machine_error_code, "FAILOVER_SUCCESS_NO_REPLACEMENT")


class FailoverReceiptContractTests(unittest.TestCase):
    def _receipt(self, **decision_kw) -> dict:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        state = f.FailoverState(request_id="r1", failed_account_ids=[], replacement_dispatches_admitted=0)
        outcome = f.normalize_dispatch_outcome(success=False, http_status=429, response_observed=True)
        decision = f.decide_request_bound_replacement(
            failing_account=a, outcome=outcome, state=state, candidate_pool=[b]
        )
        return f.build_failover_receipt(
            request_id="r1", failing_account=a, outcome=outcome, decision=decision, observed_at_utc="2026-07-27T00:00:00Z"
        )

    def test_admitted_receipt_is_ok_with_replacement_ref(self) -> None:
        receipt = self._receipt()
        _assert_packet_semantics(self, receipt)
        self.assertEqual(receipt["status"], "ok")
        self.assertIsNotNone(receipt["decision"]["replacement_account_ref"])
        self.assertEqual(receipt["decision"]["replacement_account_ref"]["backend_id"], "acct-b")

    def test_receipt_never_exposes_auth_material(self) -> None:
        receipt = self._receipt()
        body = json.dumps(receipt)
        self.assertNotIn("auth_ref", body)
        self.assertNotIn("token", body)
        self.assertNotIn("secret", body)
        self.assertNotIn("password", body)

    def test_receipt_effect_is_mutate_and_changed_files_empty(self) -> None:
        receipt = self._receipt()
        self.assertEqual(receipt["effect"], "mutate")
        self.assertEqual(receipt["changed_files"], [])


class SyntheticMatrixContractTests(unittest.TestCase):
    def test_synthetic_matrix_all_scenarios_contract_compliant(self) -> None:
        scenarios = f.run_synthetic_failover_matrix()
        self.assertGreaterEqual(len(scenarios), 11)
        for s in scenarios:
            _assert_packet_semantics(self, s["receipt"])

    def test_synthetic_matrix_quota_auth_cooldown_admit_replacement(self) -> None:
        scenarios = {s["scenario"]: s["receipt"] for s in f.run_synthetic_failover_matrix()}
        for name in (
            "quota_failure_admits_replacement",
            "auth_failure_admits_replacement",
            "cooldown_failure_admits_replacement",
        ):
            self.assertTrue(scenarios[name]["decision"]["admitted"], name)
            self.assertIsNotNone(scenarios[name]["decision"]["replacement_account_ref"], name)

    def test_synthetic_matrix_ineligible_fail_closed(self) -> None:
        scenarios = {s["scenario"]: s["receipt"] for s in f.run_synthetic_failover_matrix()}
        for name in (
            "network_failure_not_eligible",
            "unknown_failure_not_eligible",
            "ambiguous_delivery_never_replaces",
            "non_dedicated_failing_rejected",
            "budget_exhausted_fail_closed",
            "no_eligible_replacement_fail_closed",
            "second_failure_budget_exhausted",
            "success_no_replacement",
        ):
            self.assertFalse(scenarios[name]["decision"]["admitted"], name)

    def test_synthetic_matrix_no_auth_material_anywhere(self) -> None:
        scenarios = f.run_synthetic_failover_matrix()
        for s in scenarios:
            body = json.dumps(s["receipt"])
            for forbidden in ("auth_ref", "token", "secret", "password", "cookie"):
                self.assertNotIn(forbidden, body, f"{forbidden} in {s['scenario']}")


class RequestBoundDispatchAdapterTests(unittest.TestCase):
    def test_quota_failure_dispatches_one_visible_replacement(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        calls: list[str] = []

        def dispatch(account: f.AccountRef) -> dict[str, object]:
            calls.append(account.backend_id)
            if account.backend_id == "acct-a":
                return {"success": False, "http_status": 429, "response_observed": True}
            return {"success": True, "http_status": 200, "response_observed": True}

        packet = f.run_request_bound_failover_dispatch(
            request_id="r1",
            initial_account=a,
            candidate_pool=[b],
            dispatch=dispatch,
            observed_at_utc="2026-07-27T00:00:00Z",
        )

        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(calls, ["acct-a", "acct-b"])
        self.assertEqual(packet["dispatch_attempt_count"], 2)
        self.assertEqual(packet["replacement_dispatch_count"], 1)
        self.assertTrue(packet["serving_account_switched"])
        self.assertTrue(packet["switch_visible"])
        self.assertEqual(packet["serving_account_ref"]["backend_id"], "acct-b")

    def test_ambiguous_delivery_never_calls_replacement(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        calls: list[str] = []

        def dispatch(account: f.AccountRef) -> dict[str, object]:
            calls.append(account.backend_id)
            return {
                "success": False,
                "http_status": 429,
                "ambiguous_delivery": True,
            }

        packet = f.run_request_bound_failover_dispatch(
            request_id="r1",
            initial_account=a,
            candidate_pool=[b],
            dispatch=dispatch,
            observed_at_utc="2026-07-27T00:00:00Z",
        )

        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], "FAILOVER_AMBIGUOUS_DELIVERY")
        self.assertEqual(calls, ["acct-a"])
        self.assertEqual(packet["dispatch_attempt_count"], 1)
        self.assertEqual(packet["ambiguous_retry_count"], 0)

    def test_replacement_failure_does_not_retry_third_account(self) -> None:
        a = _dedicated("acct-a")
        b = _dedicated("acct-b")
        c = _dedicated("acct-c")
        calls: list[str] = []

        def dispatch(account: f.AccountRef) -> dict[str, object]:
            calls.append(account.backend_id)
            if account.backend_id == "acct-a":
                return {"success": False, "http_status": 429, "response_observed": True}
            return {"success": False, "http_status": 401, "response_observed": True}

        packet = f.run_request_bound_failover_dispatch(
            request_id="r1",
            initial_account=a,
            candidate_pool=[b, c],
            dispatch=dispatch,
            observed_at_utc="2026-07-27T00:00:00Z",
        )

        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["machine_error_code"], "FAILOVER_REPLACEMENT_DISPATCH_FAILED")
        self.assertEqual(calls, ["acct-a", "acct-b"])
        self.assertEqual(packet["replacement_dispatch_count"], 1)
        self.assertTrue(packet["no_retry_storm_proven"])

    def test_synthetic_dispatch_proof_packet_is_ok(self) -> None:
        packet = f.run_request_bound_failover_dispatch_synthetic_proof()
        _assert_packet_semantics(self, packet)
        self.assertEqual(packet["status"], "ok")
        self.assertTrue(packet["quota_then_success"])
        self.assertTrue(packet["ambiguous_no_retry"])
        self.assertTrue(packet["network_no_replacement"])
        self.assertTrue(packet["replacement_fails_once"])


if __name__ == "__main__":
    unittest.main()
