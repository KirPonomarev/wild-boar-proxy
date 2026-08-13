# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B13: sequential workflow runner tests (fake dispatch seam)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import sequential_workflow_runner as wf
from wild_boar_proxy.repo_lease import RepoLease


def _step(
    step_id: str,
    provider: str = "deepseek",
    policy: str = wf.CONTEXT_POLICY_FRESH,
    fork_from: str = "",
    repo_touching: bool = False,
    prompt: str = "prompt",
) -> wf.WorkflowStep:
    return wf.WorkflowStep(
        step_request_id=step_id,
        slot_id="slot-a",
        binding_id="binding-1",
        binding_revision=2,
        assignment_id="assignment-7",
        provider=provider,
        prompt=prompt,
        role_instruction=f"role:{step_id}",
        context_policy=policy,
        fork_from=fork_from,
        repo_touching=repo_touching,
    )


class SequentialWorkflowRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.lease_root = self.root / "lease"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _ok_dispatch(self, log: list[str]):
        def dispatch(step: wf.WorkflowStep, incoming_digest: str) -> dict:
            log.append(step.step_request_id)
            return {
                "status": "ok",
                "provider": step.provider,
                "output_text": f"out:{step.step_request_id}",
                "machine_error_code": "OK",
            }

        return dispatch

    def test_sequential_steps_get_distinct_receipts(self) -> None:
        log: list[str] = []
        steps = [
            _step("s1"),
            _step("s2", policy=wf.CONTEXT_POLICY_CONTINUE),
            _step("s3", policy=wf.CONTEXT_POLICY_CONTINUE),
        ]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch(log), lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], wf.WF_OK)
        self.assertTrue(packet["all_steps_delivered"])
        self.assertEqual(packet["dispatched_steps"], 3)
        self.assertTrue(packet["visible_delivery"])
        receipts = packet["receipts"]
        self.assertEqual([r["step_request_id"] for r in receipts], ["s1", "s2", "s3"])
        self.assertEqual(log, ["s1", "s2", "s3"])
        run_ids = {r["workflow_run_id"] for r in receipts}
        self.assertEqual(len(run_ids), 1)
        dispatch_ids = {r["dispatch_id"] for r in receipts}
        turn_ids = {r["turn_id"] for r in receipts}
        self.assertEqual(len(dispatch_ids), 3)
        self.assertEqual(len(turn_ids), 3)
        self.assertTrue(dispatch_ids.isdisjoint(turn_ids))
        for receipt in receipts:
            self.assertEqual(
                receipt["role_instruction"], f"role:{receipt['step_request_id']}"
            )
            self.assertEqual(receipt["binding_id"], "binding-1")
            self.assertEqual(receipt["binding_revision"], 2)
            self.assertEqual(receipt["assignment_id"], "assignment-7")

    def test_continue_chains_context_digest(self) -> None:
        steps = [
            _step("s1"),
            _step("s2", policy=wf.CONTEXT_POLICY_CONTINUE),
            _step("s3", policy=wf.CONTEXT_POLICY_CONTINUE),
        ]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        receipts = packet["receipts"]
        # s1 starts fresh; s2/s3 continue the previous outgoing digest.
        self.assertNotEqual(receipts[0]["incoming_context_digest"], "")
        self.assertEqual(
            receipts[1]["incoming_context_digest"],
            receipts[0]["outgoing_context_digest"],
        )
        self.assertEqual(
            receipts[2]["incoming_context_digest"],
            receipts[1]["outgoing_context_digest"],
        )

    def test_fresh_restarts_context_digest(self) -> None:
        steps = [
            _step("s1"),
            _step("s2", policy=wf.CONTEXT_POLICY_FRESH),
        ]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        receipts = packet["receipts"]
        self.assertNotEqual(
            receipts[1]["incoming_context_digest"],
            receipts[0]["outgoing_context_digest"],
        )

    def test_fork_branches_from_named_step(self) -> None:
        steps = [
            _step("s1"),
            _step("s2", policy=wf.CONTEXT_POLICY_CONTINUE),
            _step("s3", policy=wf.CONTEXT_POLICY_FORK, fork_from="s1"),
        ]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        receipts = packet["receipts"]
        self.assertEqual(
            receipts[2]["incoming_context_digest"],
            receipts[0]["outgoing_context_digest"],
        )

    def test_fork_unknown_target_fails(self) -> None:
        steps = [
            _step("s1"),
            _step("s2", policy=wf.CONTEXT_POLICY_FORK, fork_from="missing"),
        ]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_FORK_TARGET_UNKNOWN)

    def test_ambiguous_step_fails_fast_and_keeps_receipts(self) -> None:
        def dispatch(step: wf.WorkflowStep, incoming_digest: str) -> dict:
            if step.step_request_id == "s2":
                return {
                    "status": "ambiguous",
                    "provider": step.provider,
                    "human_message": "provider response is ambiguous",
                    "machine_error_code": "AMBIGUOUS",
                }
            return {
                "status": "ok",
                "provider": step.provider,
                "output_text": "out",
                "machine_error_code": "OK",
            }

        steps = [_step("s1"), _step("s2"), _step("s3")]
        packet = wf.run_sequential_workflow(
            steps, dispatch=dispatch, lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_AMBIGUOUS_STOP)
        self.assertEqual(packet["stop_reason"], wf.WF_AMBIGUOUS_STOP)
        self.assertEqual(packet["stopped_at_step"], "s2")
        # s1 delivered, s2 ambiguous, s3 never dispatched.
        self.assertEqual(
            [r["step_request_id"] for r in packet["receipts"]], ["s1", "s2"]
        )
        self.assertTrue(packet["receipts"][0]["delivered"])
        self.assertFalse(packet["receipts"][1]["delivered"])
        self.assertFalse(packet["visible_delivery"])

    def test_ambiguity_exception_fails_fast(self) -> None:
        def dispatch(step: wf.WorkflowStep, incoming_digest: str) -> dict:
            raise wf.WorkflowAmbiguityError("ambiguous upstream")

        packet = wf.run_sequential_workflow(
            [_step("s1")], dispatch=dispatch, lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["stop_reason"], wf.WF_AMBIGUOUS_STOP)
        self.assertFalse(packet["receipts"][0]["delivered"])

    def test_actor_swap_is_hard_failure(self) -> None:
        def dispatch(step: wf.WorkflowStep, incoming_digest: str) -> dict:
            return {
                "status": "ok",
                "provider": "kimi",  # different from the step's provider
                "output_text": "wrong actor",
                "machine_error_code": "OK",
            }

        packet = wf.run_sequential_workflow(
            [_step("s1", provider="deepseek")],
            dispatch=dispatch,
            lease_root=self.lease_root,
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_ACTOR_SWAP_VIOLATION)
        self.assertEqual(packet["stop_reason"], wf.WF_ACTOR_SWAP_VIOLATION)

    def test_dispatch_error_stops_run(self) -> None:
        def dispatch(step: wf.WorkflowStep, incoming_digest: str) -> dict:
            return {
                "status": "error",
                "provider": step.provider,
                "human_message": "provider unavailable",
                "machine_error_code": "PROVIDER_UNAVAILABLE",
            }

        packet = wf.run_sequential_workflow(
            [_step("s1")], dispatch=dispatch, lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_DISPATCH_FAILED)
        self.assertEqual(packet["receipts"][0]["machine_error_code"], "PROVIDER_UNAVAILABLE")
        self.assertFalse(packet["receipts"][0]["delivered"])

    def test_invalid_dispatch_result_releases_owned_lease(self) -> None:
        def dispatch(step: wf.WorkflowStep, incoming_digest: str):
            return None

        packet = wf.run_sequential_workflow(
            [_step("s1", repo_touching=True)],
            dispatch=dispatch,
            lease_root=self.lease_root,
        )
        self.assertEqual(packet["machine_error_code"], wf.WF_DISPATCH_FAILED)
        self.assertEqual(
            RepoLease(self.lease_root).status()["machine_error_code"],
            "REPO_LEASE_FREE",
        )

    def test_output_is_redacted_before_receipt_and_context_reuse(self) -> None:
        marker = "api_" + "key=" + "abcdefgh12345678"
        seen_context: list[wf.WorkflowDispatchContext] = []

        def dispatch(step: wf.WorkflowStep, context: wf.WorkflowDispatchContext):
            seen_context.append(context)
            return {
                "status": "ok",
                "provider": step.provider,
                "output_text": marker if step.step_request_id == "s1" else "done",
                "machine_error_code": "OK",
                "context_material_delivered": True,
                "visible_context_sha256": context.visible_context_sha256,
            }

        packet = wf.run_sequential_workflow(
            [
                _step("s1"),
                _step("s2", policy=wf.CONTEXT_POLICY_CONTINUE),
            ],
            dispatch_with_context=dispatch,
            lease_root=self.lease_root,
        )
        self.assertEqual(packet["status"], "ok")
        self.assertNotIn(marker, packet["receipts"][0]["output_text"])
        self.assertNotIn(marker, seen_context[1].visible_context)

    def test_repo_lease_blocked_by_external_holder(self) -> None:
        external = RepoLease(self.lease_root)
        acquired = external.acquire(
            holder="other-process", operation="external", worktree="other"
        )
        self.assertEqual(acquired["status"], "ok")
        steps = [_step("s1", repo_touching=True)]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_REPO_LEASE_BLOCKED)
        self.assertEqual(packet["stop_reason"], wf.WF_REPO_LEASE_BLOCKED)

    def test_repo_lease_acquired_and_released(self) -> None:
        steps = [
            _step("s1", repo_touching=True),
            _step("s2"),
        ]
        packet = wf.run_sequential_workflow(
            steps, dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "ok")
        status = RepoLease(self.lease_root).status()
        self.assertEqual(status["machine_error_code"], "REPO_LEASE_FREE")

    def test_duplicate_step_ids_rejected(self) -> None:
        packet = wf.run_sequential_workflow(
            [_step("s1"), _step("s1")],
            dispatch=self._ok_dispatch([]),
            lease_root=self.lease_root,
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_SCHEMA_INVALID)

    def test_invalid_policy_rejected(self) -> None:
        packet = wf.run_sequential_workflow(
            [_step("s1", policy="sideways")],
            dispatch=self._ok_dispatch([]),
            lease_root=self.lease_root,
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_SCHEMA_INVALID)

    def test_empty_workflow_rejected(self) -> None:
        packet = wf.run_sequential_workflow(
            [], dispatch=self._ok_dispatch([]), lease_root=self.lease_root
        )
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], wf.WF_SCHEMA_INVALID)


if __name__ == "__main__":
    unittest.main()
