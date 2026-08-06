# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""B18/R55: FinalAssuranceV2 tests (read-only, bundle-bound).

Uses a SYNTHETIC repo + control root: the assurance reads only the
verified AssuranceEvidenceBundleV2. Caller test counts, clean-run
booleans, network dicts, single-test receipts, synthetic receipts, and
arbitrary dicts are forged input and must be rejected with typed codes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wild_boar_proxy import assurance_evidence_bundle_v2 as aebv
from wild_boar_proxy import final_candidate_assurance as fca
from wild_boar_proxy import gate_evidence_bundle_v2 as gebv
from wild_boar_proxy.core import packets as command_packets

PLAN_ID = "WBP-TEST-PLAN"
PLAN_HASH = "a" * 64
OBSERVED = "2026-08-05T00:00:00Z"
VERIFIER = "test-verifier"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class SyntheticAssuranceFixture:
    def __init__(self, root: Path) -> None:
        self.repo = root / "repo"
        self.control = root / "control"
        self.repo.mkdir()
        self.control.mkdir()
        (self.control / "evidence").mkdir()
        _git(self.repo, "init", "-q")
        (self.repo / "README.md").write_text("x\n", encoding="utf-8")
        _git(self.repo, "add", "README.md")
        _git(self.repo, "-c", "user.name=t", "-c", "user.email=t@t",
             "commit", "-q", "-m", "init")
        _git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.candidate = _git(self.repo, "rev-parse", "origin/main")
        self.state = {
            "plan_id": PLAN_ID,
            "plan_contract_sha256": PLAN_HASH,
            "completed_stages": [],
            "invalidated_stages": [],
        }
        self.state["current_state_sha256"] = gebv.execution_state_hash(self.state)
        self.evidence: dict[str, dict] = {
            "exact_remote_head": {
                "local_head": self.candidate, "remote_head": self.candidate,
            },
            "full_suite_ci": {
                "tests_passed": 4963, "clean_run": True, "runner": "ci",
                "candidate_sha": self.candidate,
            },
            "macos_sandbox_ci": {
                "platform": "macos", "sandbox_exec": True, "runner": "ci",
                "tests_passed": 15,
            },
            "package_artifact_checksum": {"artifact_sha256": "b" * 64},
            "migration": {"ok": True},
            "design_gate": {"design_gate_earned": True},
            "privacy_redaction": {"passed": True},
            "workflow_integration": {"ok": True},
            "web_lifecycle_security": {"ok": True},
            "account_isolation": {"ok": True},
            "protected_network": {
                "air_gap": True, "protected_ports": [10808, 12334],
            },
            "provider_cli_live": {"ok": True},
        }

    def build_bundle(self, *, cli_pending: bool = False) -> dict:
        receipts = []
        for check_id in aebv.REQUIRED_ASSURANCE_CHECKS:
            if cli_pending and check_id == "provider_cli_live":
                receipts.append(
                    aebv.build_assurance_receipt(
                        receipt_id=f"receipt-{check_id}",
                        plan_id=PLAN_ID,
                        plan_contract_sha256=PLAN_HASH,
                        check_id=check_id,
                        candidate_sha=self.candidate,
                        evidence_ref="",
                        evidence_sha256="0" * 64,
                        observed_at=OBSERVED,
                        verifier_identity=VERIFIER,
                        status=aebv.STATUS_PENDING,
                        pending_code=aebv.WAIT_EXTERNAL_PREREQUISITE,
                    )
                )
                continue
            payload = json.dumps(self.evidence[check_id], sort_keys=True).encode("utf-8")
            ref = f"evidence/{check_id}.json"
            (self.control / ref).write_bytes(payload)
            receipts.append(
                aebv.build_assurance_receipt(
                    receipt_id=f"receipt-{check_id}",
                    plan_id=PLAN_ID,
                    plan_contract_sha256=PLAN_HASH,
                    check_id=check_id,
                    candidate_sha=self.candidate,
                    evidence_ref=ref,
                    evidence_sha256=hashlib.sha256(payload).hexdigest(),
                    observed_at=OBSERVED,
                    verifier_identity=VERIFIER,
                )
            )
        return {"schema_version": 2, "plan_id": PLAN_ID, "receipts": receipts}

    def write(self, *, bundle: dict | None, state: dict | None = None) -> None:
        (self.control / "execution-state.json").write_text(
            json.dumps(state if state is not None else self.state), encoding="utf-8"
        )
        bundle_path = self.control / aebv.ASSURANCE_BUNDLE_FILENAME
        if bundle is None:
            bundle_path.unlink(missing_ok=True)
        else:
            bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    def verifier(self) -> aebv.AssuranceBundleVerifier:
        return aebv.AssuranceBundleVerifier(
            project_root=self.repo, control_root=self.control
        )


class FinalAssuranceV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.fixture = SyntheticAssuranceFixture(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _run(self, *, mutate=None, cli_pending: bool = False, drop_bundle: bool = False):
        bundle = None if drop_bundle else self.fixture.build_bundle(cli_pending=cli_pending)
        if mutate is not None and bundle is not None:
            mutate(bundle)
        self.fixture.write(bundle=bundle)
        return self.fixture.verifier().verify_bundle()

    def _codes(self, result) -> set[str]:
        return {f["code"] for f in result["failures"]}

    # --- happy paths ---

    def test_fully_proven_bundle_is_ready(self) -> None:
        result = self._run()
        self.assertTrue(result["ready"], result["failures"])
        self.assertFalse(result["waiting"])
        self.assertEqual(result["failures"], [])

    def test_pending_cli_live_is_typed_waiting(self) -> None:
        """CLI disabled -> typed waiting, never a crash, never ready."""
        result = self._run(cli_pending=True)
        self.assertFalse(result["ready"])
        self.assertTrue(result["waiting"])
        self.assertEqual(result["failures"], [])
        self.assertEqual(
            result["pendings"][0]["pending_code"], aebv.WAIT_EXTERNAL_PREREQUISITE
        )

    # --- forged input on the production entrypoint ---

    def test_caller_test_count_rejected(self) -> None:
        with self.assertRaises(TypeError):
            fca.run_final_candidate_assurance(full_suite_passed=1)  # type: ignore[call-arg]

    def test_clean_run_boolean_rejected(self) -> None:
        with self.assertRaises(TypeError):
            fca.run_final_candidate_assurance(clean_run=True)  # type: ignore[call-arg]

    def test_arbitrary_network_dict_rejected(self) -> None:
        with self.assertRaises(TypeError):
            fca.run_final_candidate_assurance(  # type: ignore[call-arg]
                network_air_gap_evidence={"x": True}
            )

    # --- forged evidence vectors ---

    def test_single_test_receipt_rejected(self) -> None:
        def mutate(bundle):
            for receipt in bundle["receipts"]:
                if receipt["check_id"] == "full_suite_ci":
                    ref = receipt["evidence_ref"]
                    payload = json.dumps(
                        {"tests_passed": 1, "clean_run": True, "runner": "ci",
                         "candidate_sha": self.fixture.candidate},
                        sort_keys=True,
                    ).encode("utf-8")
                    (self.fixture.control / ref).write_bytes(payload)
                    receipt["evidence_sha256"] = hashlib.sha256(payload).hexdigest()
                    receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn(aebv.FULL_SUITE_RECEIPT_INVALID, self._codes(result))

    def test_synthetic_receipt_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            receipt["synthetic"] = True
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn("EVIDENCE_SCHEMA_INVALID", self._codes(result))

    def test_synthetic_proof_level_rejected_for_full_suite(self) -> None:
        def mutate(bundle):
            for receipt in bundle["receipts"]:
                if receipt["check_id"] == "full_suite_ci":
                    ref = receipt["evidence_ref"]
                    payload = json.dumps(
                        {"tests_passed": 9000, "clean_run": True, "runner": "ci",
                         "candidate_sha": self.fixture.candidate,
                         "proof_level": "SYNTHETIC_PROVEN"},
                        sort_keys=True,
                    ).encode("utf-8")
                    (self.fixture.control / ref).write_bytes(payload)
                    receipt["evidence_sha256"] = hashlib.sha256(payload).hexdigest()
                    receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn(aebv.FULL_SUITE_RECEIPT_INVALID, self._codes(result))

    def test_arbitrary_dict_evidence_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            ref = receipt["evidence_ref"]
            payload = b"[1, 2, 3]"
            (self.fixture.control / ref).write_bytes(payload)
            receipt["evidence_sha256"] = hashlib.sha256(payload).hexdigest()
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn("EVIDENCE_SCHEMA_INVALID", self._codes(result))

    def test_air_gap_false_rejected(self) -> None:
        def mutate(bundle):
            for receipt in bundle["receipts"]:
                if receipt["check_id"] == "protected_network":
                    ref = receipt["evidence_ref"]
                    payload = json.dumps(
                        {"air_gap": False, "protected_ports": [10808, 12334]},
                        sort_keys=True,
                    ).encode("utf-8")
                    (self.fixture.control / ref).write_bytes(payload)
                    receipt["evidence_sha256"] = hashlib.sha256(payload).hexdigest()
                    receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn(aebv.PROTECTED_NETWORK_UNPROVEN, self._codes(result))

    def test_missing_bundle_rejected_without_keyerror(self) -> None:
        result = self._run(drop_bundle=True)
        self.assertFalse(result["ready"])
        self.assertFalse(result["waiting"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("assurance_bundle_missing", reasons)

    def test_candidate_mismatch_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            receipt["candidate_sha"] = "c" * 40
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn("EVIDENCE_CANDIDATE_MISMATCH", self._codes(result))

    def test_evidence_digest_mismatch_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            ref = receipt["evidence_ref"]
            (self.fixture.control / ref).write_bytes(b"tampered")
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertIn("EVIDENCE_DIGEST_MISMATCH", self._codes(result))

    def test_evidence_ref_traversal_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            receipt["evidence_ref"] = "../../etc/passwd"
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("evidence_ref_escapes_control_root", reasons)

    def test_duplicate_check_rejected(self) -> None:
        def mutate(bundle):
            bundle["receipts"].append(copy.deepcopy(bundle["receipts"][0]))
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("duplicate_check_id", reasons)

    def test_missing_required_check_rejected(self) -> None:
        def mutate(bundle):
            bundle["receipts"] = [
                r for r in bundle["receipts"] if r["check_id"] != "migration"
            ]
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("required_check_missing", reasons)

    def test_pending_without_typed_code_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            receipt["status"] = aebv.STATUS_PENDING
            receipt["pending_code"] = None
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("pending_without_typed_code", reasons)

    def test_wrong_plan_hash_rejected(self) -> None:
        def mutate(bundle):
            receipt = bundle["receipts"][0]
            receipt["plan_contract_sha256"] = "f" * 64
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        reasons = {f["reason"] for f in result["failures"]}
        self.assertIn("plan_hash_mismatch", reasons)

    # --- production entrypoint outcome mapping (factory boundary mock) ---

    def _packet_for(self, *, cli_pending: bool = False, drop_bundle: bool = False):
        bundle = None if drop_bundle else self.fixture.build_bundle(cli_pending=cli_pending)
        self.fixture.write(bundle=bundle)
        verifier = self.fixture.verifier()
        with patch.object(aebv, "production_verifier", return_value=verifier):
            return fca.run_final_candidate_assurance()

    def test_run_ready_when_fully_proven(self) -> None:
        packet = self._packet_for()
        self.assertEqual(packet["status"], "ok")
        self.assertEqual(packet["machine_error_code"], fca.FINAL_CANDIDATE_STATUS)
        self.assertTrue(packet["ready_for_independent_audit"])
        self.assertTrue(packet["never_emits_done"])
        self.assertNotIn("DONE", packet["machine_error_code"])

    def test_run_waiting_when_cli_pending(self) -> None:
        packet = self._packet_for(cli_pending=True)
        self.assertEqual(packet["status"], "error")
        self.assertEqual(packet["machine_error_code"], aebv.WAIT_EXTERNAL_PREREQUISITE)
        self.assertFalse(packet["ready_for_independent_audit"])
        self.assertTrue(packet["waiting_external_prerequisite"])
        self.assertTrue(packet["never_emits_done"])

    def test_run_fails_typed_when_bundle_missing(self) -> None:
        packet = self._packet_for(drop_bundle=True)
        self.assertEqual(packet["status"], "error")
        self.assertFalse(packet["ready_for_independent_audit"])
        self.assertIn(
            packet["machine_error_code"],
            {
                "EVIDENCE_SCHEMA_INVALID",
                "EVIDENCE_DIGEST_MISMATCH",
                "EVIDENCE_CANDIDATE_MISMATCH",
                aebv.FULL_SUITE_RECEIPT_INVALID,
                aebv.PROTECTED_NETWORK_UNPROVEN,
                aebv.WAIT_EXTERNAL_PREREQUISITE,
                fca.FINAL_CANDIDATE_FAILED,
            },
        )

    def test_packet_is_strict(self) -> None:
        packet = self._packet_for()
        violations = command_packets.inspect_command_packet_semantics(packet)
        self.assertEqual(violations, [])

    def test_packet_contains_no_secrets(self) -> None:
        packet = self._packet_for()
        body = json.dumps(packet)
        self.assertNotIn("sk-", body)
        self.assertNotIn(".codex", body)


if __name__ == "__main__":
    unittest.main()
