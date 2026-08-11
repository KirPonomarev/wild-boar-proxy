# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""R54: GateEvidenceBundleV2 forged-gate regression suite.

Builds a SYNTHETIC git repository and control root in a temp dir (never
the operator's real state) and proves that every R4-era forgery vector is
rejected with the correct typed code:

- only stage labels;
- missing merge SHA;
- missing closeout;
- missing/wrong digest;
- unreachable commit;
- wrong candidate;
- duplicate receipt;
- invalidated stage;
- stale receipt;
- wrong plan hash;
- current worktree file instead of git-show blob;
- empty evidence index.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from wild_boar_proxy import gate_evidence_bundle_v2 as gebv

PLAN_ID = "WBP-TEST-PLAN"
PLAN_HASH = "a" * 64
VERIFIER = "test-verifier"
OBSERVED = "2026-08-05T00:00:00Z"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class SyntheticFixture:
    """A synthetic repo + control root with a fully valid V2 bundle."""

    def __init__(self, root: Path) -> None:
        self.repo = root / "repo"
        self.control = root / "control"
        self.repo.mkdir()
        self.control.mkdir()
        _git(self.repo, "init", "-q")
        self.receipts: list[dict] = []
        for stage in gebv.REQUIRED_STAGES:
            rel = f"audit_results/{stage.lower()}_closeout.md"
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"# closeout {stage}\n", encoding="utf-8")
            _git(self.repo, "add", rel)
            _git(
                self.repo,
                "-c", "user.name=t", "-c", "user.email=t@t",
                "commit", "-q", "-m", f"closeout {stage}",
            )
            merge = _git(self.repo, "rev-parse", "HEAD")
            blob = subprocess.run(
                ["git", "-C", str(self.repo), "show", f"{merge}:{rel}"],
                capture_output=True,
                timeout=15,
            ).stdout
            self.receipts.append(
                gebv.build_closeout_reference_receipt(
                    receipt_id=f"receipt-{stage}",
                    plan_id=PLAN_ID,
                    plan_contract_sha256=PLAN_HASH,
                    stage_id=stage,
                    candidate_sha=merge,
                    merge_commit_sha=merge,
                    remote_main_sha=merge,
                    closeout_path=rel,
                    closeout_blob_sha256=hashlib.sha256(blob).hexdigest(),
                    observed_at=OBSERVED,
                    verifier_identity=VERIFIER,
                )
            )
        _git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.candidate = _git(self.repo, "rev-parse", "origin/main")
        self.state = {
            "plan_id": PLAN_ID,
            "plan_contract_sha256": PLAN_HASH,
            "completed_stages": list(gebv.REQUIRED_STAGES),
            "invalidated_stages": [],
        }
        self.state["current_state_sha256"] = gebv.execution_state_hash(self.state)
        self.index = {
            "schema_version": 2,
            "plan_id": PLAN_ID,
            "references": self.receipts,
        }

    def write(self, *, state: dict | None = None, index: dict | None = None) -> None:
        (self.control / "execution-state.json").write_text(
            json.dumps(state if state is not None else self.state),
            encoding="utf-8",
        )
        (self.control / "evidence-index.json").write_text(
            json.dumps(index if index is not None else self.index),
            encoding="utf-8",
        )

    def verifier(self) -> gebv.GateEvidenceVerifier:
        return gebv.GateEvidenceVerifier(
            project_root=self.repo, control_root=self.control
        )


def _rehash(receipt: dict) -> dict:
    receipt["receipt_sha256"] = gebv.receipt_hash(receipt)
    return receipt


class GateEvidenceBundleV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fixture = SyntheticFixture(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _run(self, *, mutate_index=None, mutate_state=None, candidate=None):
        index = copy.deepcopy(self.fixture.index)
        state = copy.deepcopy(self.fixture.state)
        if mutate_index is not None:
            mutate_index(index)
        if mutate_state is not None:
            mutate_state(state)
        self.fixture.write(state=state, index=index)
        return self.fixture.verifier().verify_bundle(candidate=candidate)

    def _codes(self, result) -> set[str]:
        return {f["code"] for f in result["failures"]}

    # --- happy path ---

    def test_valid_bundle_is_earned(self) -> None:
        result = self._run()
        self.assertTrue(result["earned"], result["failures"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["findings"]["receipt_count"], len(gebv.REQUIRED_STAGES))

    def test_r59_transport_repair_supplement_is_required(self) -> None:
        stage = "R59_API_TRANSPORT_TRUTH_HARDENING"
        self.assertIn(stage, gebv.REQUIRED_STAGES)

        def mutate(index):
            index["references"] = [
                receipt
                for receipt in index["references"]
                if receipt.get("stage_id") != stage
            ]

        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(stage, result["findings"]["missing_required_stages"])
        reasons = {failure["reason"] for failure in result["failures"]}
        self.assertIn("required_stage_missing", reasons)

    # --- forged vectors ---

    def test_stage_labels_only_rejected(self) -> None:
        def mutate(index):
            index["references"] = [
                {"stage_id": s, "receipt_type": "closeout_reference"}
                for s in gebv.REQUIRED_STAGES
            ]
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_SCHEMA_INVALID, self._codes(result))

    def test_missing_merge_sha_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            del receipt["merge_commit_sha"]
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_SCHEMA_INVALID, self._codes(result))

    def test_missing_closeout_in_commit_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["closeout_path"] = "audit_results/never_committed.md"
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_DIGEST_MISMATCH, self._codes(result))

    def test_wrong_closeout_digest_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["closeout_blob_sha256"] = "b" * 64
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_DIGEST_MISMATCH, self._codes(result))

    def test_missing_receipt_hash_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["receipt_sha256"] = "c" * 64
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_DIGEST_MISMATCH, self._codes(result))

    def test_unreachable_commit_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            fake = "0" * 40
            receipt["merge_commit_sha"] = fake
            receipt["remote_main_sha"] = fake
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_COMMIT_UNREACHABLE, self._codes(result))

    def test_wrong_gate_candidate_rejected(self) -> None:
        result = self._run(candidate="d" * 40)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_CANDIDATE_MISMATCH, self._codes(result))

    def test_receipt_candidate_unreachable_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["candidate_sha"] = "e" * 40
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_CANDIDATE_MISMATCH, self._codes(result))

    def test_duplicate_receipt_rejected(self) -> None:
        def mutate(index):
            index["references"].append(copy.deepcopy(index["references"][0]))
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_SCHEMA_INVALID, self._codes(result))
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("duplicate_stage_id", reasons)
        self.assertIn("duplicate_receipt_id", reasons)

    def test_invalidated_receipt_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["invalidated"] = True
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_STAGE_INVALIDATED, self._codes(result))

    def test_required_stage_invalidated_in_state_rejected(self) -> None:
        def mutate_state(state):
            state["invalidated_stages"] = [gebv.REQUIRED_STAGES[0]]
            state["current_state_sha256"] = gebv.execution_state_hash(state)
        result = self._run(mutate_state=mutate_state)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_STAGE_INVALIDATED, self._codes(result))

    def test_stage_completed_and_invalidated_rejected(self) -> None:
        def mutate_state(state):
            # A stage present in BOTH lists is contradictory state.
            state["invalidated_stages"] = ["B07_CODE_MULTI_API_CORE"]
            state["current_state_sha256"] = gebv.execution_state_hash(state)
        result = self._run(mutate_state=mutate_state)
        self.assertFalse(result["earned"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("stage_completed_and_invalidated", reasons)

    def test_stale_receipt_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["observed_at"] = "yesterday"
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        self.assertIn(gebv.EVIDENCE_SCHEMA_INVALID, self._codes(result))

    def test_wrong_plan_hash_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            receipt["plan_contract_sha256"] = "f" * 64
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("plan_hash_mismatch", reasons)

    def test_worktree_file_is_not_used_instead_of_git_blob(self) -> None:
        """Modify the closeout in the worktree AFTER the commit. The
        verifier must still pass with the committed digest (proving it
        reads `git show`, not the worktree), and a receipt rebound to the
        worktree-modified digest must be rejected."""
        rel = self.fixture.receipts[0]["closeout_path"]
        worktree_file = self.fixture.repo / rel
        original = worktree_file.read_bytes()
        try:
            worktree_file.write_bytes(original + b"forged worktree edit\n")
            # 1. Original committed digest still verifies (git show used).
            result = self._run()
            self.assertTrue(result["earned"], result["failures"])
            # 2. A receipt rebound to the worktree-modified file fails.
            forged_digest = hashlib.sha256(worktree_file.read_bytes()).hexdigest()

            def mutate(index):
                receipt = index["references"][0]
                receipt["closeout_blob_sha256"] = forged_digest
                _rehash(receipt)

            result = self._run(mutate_index=mutate)
            self.assertFalse(result["earned"])
            self.assertIn(gebv.EVIDENCE_DIGEST_MISMATCH, self._codes(result))
        finally:
            worktree_file.write_bytes(original)

    def test_empty_evidence_index_rejected(self) -> None:
        result = self._run(mutate_index=lambda index: index.update(references=[]))
        self.assertFalse(result["earned"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("evidence_index_empty", reasons)

    def test_state_hash_invalid_rejected(self) -> None:
        def mutate_state(state):
            state["completed_stages"] = []  # mutation without rehash
        result = self._run(mutate_state=mutate_state)
        self.assertFalse(result["earned"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("execution_state_hash_invalid", reasons)

    def test_remote_main_transition_mismatch_rejected(self) -> None:
        def mutate(index):
            receipt = index["references"][0]
            other = index["references"][1]["merge_commit_sha"]
            receipt["remote_main_sha"] = other
            _rehash(receipt)
        result = self._run(mutate_index=mutate)
        self.assertFalse(result["earned"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("remote_main_transition_mismatch", reasons)


if __name__ == "__main__":
    unittest.main()
