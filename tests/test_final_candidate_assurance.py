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

        def live_identity(provider_id: str, ordinal: int) -> dict:
            return {
                "provider_id": provider_id,
                "transport_kind": "api",
                "candidate_sha": self.candidate,
                "actor_id": f"actor-{provider_id}",
                "actor_revision": 1,
                "binding_id": f"binding-{provider_id}",
                "binding_revision": 1,
                "assignment_id": f"assignment-{provider_id}",
                "assignment_revision": 1,
                "session_id": f"session-provider-{ordinal}",
                "session_revision": 1,
                "dispatch_id": f"dispatch-provider-{ordinal}",
                "model_id": f"model-{provider_id}",
                "route_id": f"route-{provider_id}",
                "output_sha256": f"{ordinal}" * 64,
                "credential_present": True,
                "dispatch_attempted": True,
                "response_observed": True,
                "live_provider_called": True,
                "live_provider_proven": True,
                "output_present": True,
                "controlled": False,
                "fallback_used": False,
                "actor_substitution_used": False,
            }

        def combination(
            combination_id: str, transports: list[str], ordinal: int
        ) -> dict:
            return {
                "combination_id": combination_id,
                "transport_kinds": transports,
                "provider_ids": (
                    ["deepseek", "kimi"]
                    if combination_id == "api_api"
                    else ["glm", "qwen"]
                    if combination_id == "api_cli"
                    else ["qwen", "kimi"]
                ),
                "candidate_sha": self.candidate,
                "proof_level": aebv.PROOF_LIVE,
                "actor_ids": [f"actor-combo-{ordinal}-1", f"actor-combo-{ordinal}-2"],
                "binding_ids": [
                    f"binding-combo-{ordinal}-1",
                    f"binding-combo-{ordinal}-2",
                ],
                "binding_revisions": [1, 1],
                "assignment_ids": [
                    f"assignment-combo-{ordinal}-1",
                    f"assignment-combo-{ordinal}-2",
                ],
                "assignment_revisions": [1, 1],
                "session_ids": [
                    f"session-combo-{ordinal}-1",
                    f"session-combo-{ordinal}-2",
                ],
                "session_revisions": [1, 1],
                "dispatch_ids": [
                    f"dispatch-combo-{ordinal}-1",
                    f"dispatch-combo-{ordinal}-2",
                ],
                "model_ids": [f"model-combo-{ordinal}-1", f"model-combo-{ordinal}-2"],
                "route_ids": [f"route-combo-{ordinal}-1", f"route-combo-{ordinal}-2"],
                "output_sha256s": [f"{ordinal + 4}" * 64, f"{ordinal + 5}" * 64],
                "credential_presence": [True, True],
                "dispatches_attempted": True,
                "responses_observed": True,
                "live_provider_proven": True,
                "outputs_present": True,
                "controlled": False,
                "fallback_used": False,
                "actor_substitution_used": False,
            }

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
                "tests_passed": 15, "candidate_sha": self.candidate,
                "run_id": 1001, "job_id": 2001,
            },
            "package_artifact_checksum": {
                "artifact_sha256": "b" * 64,
                "artifact_name": "wild_boar_proxy.whl",
                "artifact_size_bytes": 4096,
                "candidate_sha": self.candidate,
                "runner": "ci",
            },
            "migration": {
                "proof_level": aebv.PROOF_INTEGRATION,
                "candidate_sha": self.candidate,
                "migration_verified": True,
                "source_schema_version": 1,
                "target_schema_version": 2,
                "records_verified": 3,
                "legacy_projection_lossless": True,
            },
            "design_gate": {
                "design_gate_earned": True,
                "token": "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY",
                "candidate_sha": self.candidate,
                "gate_bundle_sha256": "c" * 64,
            },
            "privacy_redaction": {
                "proof_level": aebv.PROOF_INTEGRATION,
                "candidate_sha": self.candidate,
                "secret_scan_passed": True,
                "packet_redaction_verified": True,
                "raw_backend_absent": True,
                "credential_values_absent": True,
                "files_scanned": 42,
                "scan_receipt_sha256": "d" * 64,
            },
            "workflow_integration": {
                "proof_level": aebv.PROOF_INTEGRATION,
                "candidate_sha": self.candidate,
                "workflow_mode": "production_path_controlled",
                "registry_bound": True,
                "independent_receipts": True,
                "visible_context_delivery": True,
                "lease_cleanup_verified": True,
                "fallback_used": False,
                "actor_substitution_used": False,
                "receipt_sha256s": ["e" * 64, "f" * 64],
            },
            "web_lifecycle_security": {
                "proof_level": aebv.PROOF_INTEGRATION,
                "candidate_sha": self.candidate,
                "loopback_only": True,
                "token_enforced": True,
                "origin_enforced": True,
                "csrf_enforced": True,
                "rate_limit_enforced": True,
                "writer_fencing_verified": True,
                "browser_authority_bounded": True,
                "security_matrix_sha256": "1" * 64,
            },
            "account_isolation": {
                "proof_level": aebv.PROOF_INTEGRATION,
                "candidate_sha": self.candidate,
                "dedicated_accounts": True,
                "provider_homes_isolated": True,
                "credential_stores_isolated": True,
                "primary_codex_untouched": True,
                "main_account_reuse_absent": True,
                "isolation_receipt_sha256": "2" * 64,
            },
            "protected_network": {
                "air_gap": True,
                "protected_ports": [10808, 12334],
                "no_detected_mutation": True,
                "evidence_basis": "guard_enforcement",
                "candidate_sha": self.candidate,
                "guard_receipt_sha256": "3" * 64,
            },
            "provider_cli_live": {
                "proof_level": aebv.PROOF_LIVE,
                "candidate_sha": self.candidate,
                "providers": [
                    live_identity("deepseek", 1),
                    live_identity("kimi", 2),
                    live_identity("glm", 3),
                    live_identity("qwen", 4),
                ],
                "combinations": [
                    combination("api_api", ["api", "api"], 1),
                    combination("api_cli", ["api", "cli"], 2),
                    combination("cli_cli", ["cli", "cli"], 3),
                ],
            },
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

    def _replace_evidence(self, bundle: dict, check_id: str, evidence: dict) -> None:
        for receipt in bundle["receipts"]:
            if receipt["check_id"] != check_id:
                continue
            payload = json.dumps(evidence, sort_keys=True).encode("utf-8")
            (self.fixture.control / receipt["evidence_ref"]).write_bytes(payload)
            receipt["evidence_sha256"] = hashlib.sha256(payload).hexdigest()
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)
            return
        self.fail(f"receipt missing for {check_id}")

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

    def test_bare_boolean_never_closes_any_required_check(self) -> None:
        for check_id in aebv.REQUIRED_ASSURANCE_CHECKS:
            with self.subTest(check_id=check_id):
                def mutate(bundle, selected=check_id):
                    self._replace_evidence(
                        bundle, selected, {"ok": True, "passed": True}
                    )

                result = self._run(mutate=mutate)
                self.assertFalse(result["ready"])
                self.assertGreater(len(result["failures"]), 0)

    def test_provider_live_matrix_rejects_false_green_vectors(self) -> None:
        def mutate_case(case: str):
            def mutate(bundle):
                evidence = copy.deepcopy(self.fixture.evidence["provider_cli_live"])
                if case == "missing_provider":
                    evidence["providers"].pop()
                elif case == "credential_absent":
                    evidence["providers"][0]["credential_present"] = False
                elif case == "controlled":
                    evidence["providers"][0]["controlled"] = True
                elif case == "fallback":
                    evidence["providers"][0]["fallback_used"] = True
                elif case == "candidate_drift":
                    evidence["providers"][0]["candidate_sha"] = "0" * 40
                elif case == "revision_missing":
                    evidence["providers"][0].pop("binding_revision")
                elif case == "output_missing":
                    evidence["providers"][0]["output_sha256"] = ""
                elif case == "missing_combination":
                    evidence["combinations"].pop()
                elif case == "combination_transport_drift":
                    evidence["combinations"][1]["transport_kinds"] = ["api", "api"]
                elif case == "duplicate_dispatch":
                    evidence["combinations"][0]["dispatch_ids"][1] = (
                        evidence["combinations"][0]["dispatch_ids"][0]
                    )
                else:
                    self.fail(f"unknown case {case}")
                self._replace_evidence(bundle, "provider_cli_live", evidence)
            return mutate

        for case in (
            "missing_provider",
            "credential_absent",
            "controlled",
            "fallback",
            "candidate_drift",
            "revision_missing",
            "output_missing",
            "missing_combination",
            "combination_transport_drift",
            "duplicate_dispatch",
        ):
            with self.subTest(case=case):
                result = self._run(mutate=mutate_case(case))
                self.assertFalse(result["ready"])
                reasons = {failure["reason"] for failure in result["failures"]}
                self.assertIn("provider_cli_live_matrix_invalid", reasons)

    def test_pending_internal_check_is_invalid_not_waiting(self) -> None:
        def mutate(bundle):
            receipt = next(
                item for item in bundle["receipts"] if item["check_id"] == "migration"
            )
            receipt["status"] = aebv.STATUS_PENDING
            receipt["pending_code"] = aebv.WAIT_EXTERNAL_PREREQUISITE
            receipt["receipt_sha256"] = aebv.assurance_receipt_hash(receipt)

        result = self._run(mutate=mutate)
        self.assertFalse(result["ready"])
        self.assertFalse(result["waiting"])
        reasons = {failure["reason"] for failure in result["failures"]}
        self.assertIn("pending_not_external_live_gate", reasons)

    def test_malformed_strict_evidence_fails_without_exception(self) -> None:
        cases = (
            ("provider_cli_live", {"proof_level": aebv.PROOF_LIVE,
                                   "candidate_sha": self.fixture.candidate,
                                   "providers": [1], "combinations": []}),
            ("provider_cli_live", {"proof_level": aebv.PROOF_LIVE,
                                   "candidate_sha": self.fixture.candidate,
                                   "providers": [], "combinations": [{
                                       "combination_id": "api_api",
                                       "transport_kinds": 1,
                                   }]}),
            ("workflow_integration", {
                "proof_level": aebv.PROOF_INTEGRATION,
                "candidate_sha": self.fixture.candidate,
                "workflow_mode": "production_path_controlled",
                "registry_bound": True,
                "independent_receipts": True,
                "visible_context_delivery": True,
                "lease_cleanup_verified": True,
                "fallback_used": False,
                "actor_substitution_used": False,
                "receipt_sha256s": [{}],
            }),
        )
        for check_id, evidence in cases:
            with self.subTest(check_id=check_id, evidence=evidence):
                def mutate(bundle, selected=check_id, payload=evidence):
                    self._replace_evidence(bundle, selected, payload)

                result = self._run(mutate=mutate)
                self.assertFalse(result["ready"])
                self.assertGreater(len(result["failures"]), 0)

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
