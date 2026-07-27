# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic contract tests for the named dual-lane thread context and
delegation contract (W08)."""

from __future__ import annotations

import json
import unittest

from wild_boar_proxy import dual_lane_context as dc
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


def _turn(label: str, kind: str, text: str) -> dc.VisibleTurn:
    return dc.VisibleTurn(
        actor_label=label,
        turn_kind=kind,
        content_digest=dc._sha256_text(text),
        redacted_summary=text[:60],
    )


class ContextEnvelopeTests(unittest.TestCase):
    def test_envelope_truncates_to_max_visible_turns(self) -> None:
        turns = [_turn("user", "user_request", f"request {i}") for i in range(20)]
        env = dc.build_context_envelope(
            current_request="latest",
            permitted_visible_turns=turns,
            actor_labels=["user"],
            max_visible_turns=8,
        )
        self.assertEqual(len(env.permitted_visible_turns), 8)
        self.assertIn("relayed 8", env.truncation_summary)

    def test_envelope_clean_has_no_forbidden_tokens(self) -> None:
        env = dc.build_context_envelope(
            current_request="Deep: implement helper",
            permitted_visible_turns=[_turn("user", "user_request", "implement helper")],
            actor_labels=["user", "Deep"],
        )
        self.assertEqual(dc.validate_context_envelope(env), [])

    def test_envelope_detects_forbidden_token_in_summary(self) -> None:
        env = dc.ContextEnvelope(
            current_request_digest="x" * 64,
            permitted_visible_turns=(),
            actor_labels=("user",),
            server_bindings={},
            truncation_summary="contains sk-secret-key leak",
            repo_bridge_admitted=False,
        )
        violations = dc.validate_context_envelope(env)
        self.assertIn("sk-", violations)

    def test_envelope_detects_chain_of_thought(self) -> None:
        env = dc.ContextEnvelope(
            current_request_digest="x" * 64,
            permitted_visible_turns=(),
            actor_labels=("user",),
            server_bindings={"note": "includes chain_of_thought"},
            truncation_summary="clean",
            repo_bridge_admitted=False,
        )
        violations = dc.validate_context_envelope(env)
        self.assertIn("chain_of_thought", violations)


class ContextRelayReceiptTests(unittest.TestCase):
    def test_clean_relay_is_ok_contract_compliant(self) -> None:
        env = dc.build_context_envelope(
            current_request="Deep: implement helper",
            permitted_visible_turns=[_turn("user", "user_request", "implement helper")],
            actor_labels=["user", "Deep"],
        )
        receipt = dc.build_context_relay_receipt(envelope=env, target_lane=dc.LANE_DEEPSEEK)
        _assert_packet_semantics(self, receipt)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["target_lane"], dc.LANE_DEEPSEEK)

    def test_forbidden_relay_is_error(self) -> None:
        env = dc.ContextEnvelope(
            current_request_digest="x" * 64,
            permitted_visible_turns=(),
            actor_labels=("user",),
            server_bindings={"leak": "api_key here"},
            truncation_summary="clean",
            repo_bridge_admitted=False,
        )
        receipt = dc.build_context_relay_receipt(envelope=env, target_lane=dc.LANE_DEEPSEEK)
        _assert_packet_semantics(self, receipt)
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["machine_error_code"], "CONTEXT_RELAY_FORBIDDEN_TOKENS")


class DelegationReceiptTests(unittest.TestCase):
    def test_gpt_to_deep_delegation_clean_is_ok(self) -> None:
        env = dc.build_context_envelope(
            current_request="Deep: refine helper",
            permitted_visible_turns=[_turn("GPT", "actor_reply", "review notes")],
            actor_labels=["user", "Deep", "GPT"],
        )
        contract = dc.build_delegation_contract(
            delegating_lane=dc.LANE_GPT,
            delegate_lane=dc.LANE_DEEPSEEK,
            bounded_task="refine helper",
        )
        receipt = dc.build_delegation_receipt(contract=contract, envelope=env)
        _assert_packet_semantics(self, receipt)
        self.assertEqual(receipt["status"], "ok")

    def test_invalid_lane_pair_rejected(self) -> None:
        env = dc.build_context_envelope(
            current_request="task",
            permitted_visible_turns=[],
            actor_labels=["user"],
        )
        contract = dc.build_delegation_contract(
            delegating_lane=dc.LANE_DEEPSEEK,
            delegate_lane=dc.LANE_GPT,
            bounded_task="task",
        )
        receipt = dc.build_delegation_receipt(contract=contract, envelope=env)
        _assert_packet_semantics(self, receipt)
        self.assertEqual(receipt["machine_error_code"], "DELEGATION_LANE_PAIR_INVALID")

    def test_forbidden_envelope_delegation_rejected(self) -> None:
        env = dc.ContextEnvelope(
            current_request_digest="x" * 64,
            permitted_visible_turns=(),
            actor_labels=("user",),
            server_bindings={"leak": "password"},
            truncation_summary="clean",
            repo_bridge_admitted=False,
        )
        contract = dc.build_delegation_contract(
            delegating_lane=dc.LANE_GPT,
            delegate_lane=dc.LANE_DEEPSEEK,
            bounded_task="task",
        )
        receipt = dc.build_delegation_receipt(contract=contract, envelope=env)
        _assert_packet_semantics(self, receipt)
        self.assertEqual(receipt["machine_error_code"], "DELEGATION_FORBIDDEN_TOKENS")


class SyntheticProofTests(unittest.TestCase):
    def test_synthetic_proof_summary_ok_contract_compliant(self) -> None:
        summary = dc.run_dual_lane_synthetic_proof_summary()
        _assert_packet_semantics(self, summary)
        self.assertEqual(summary["status"], "ok")
        self.assertTrue(summary["no_forbidden_tokens"])

    def test_synthetic_proof_receipts_contract_compliant(self) -> None:
        for receipt in dc.run_dual_lane_synthetic_proof():
            _assert_packet_semantics(self, receipt)

    def test_synthetic_proof_no_forbidden_tokens_anywhere(self) -> None:
        for receipt in dc.run_dual_lane_synthetic_proof():
            self.assertEqual(receipt.get("forbidden_token_violations"), [])

    def test_synthetic_proof_never_exposes_secrets(self) -> None:
        for receipt in dc.run_dual_lane_synthetic_proof():
            body = json.dumps(receipt)
            for tok in ("sk-", "password", "refresh_token", "oauth_token", "session_cookie"):
                self.assertNotIn(tok, body)

    def test_synthetic_proof_covers_four_turn_continuity(self) -> None:
        receipts = dc.run_dual_lane_synthetic_proof()
        # At least 2 relay receipts (Deep + GPT) + 2 delegation receipts.
        self.assertGreaterEqual(len(receipts), 4)


if __name__ == "__main__":
    unittest.main()
