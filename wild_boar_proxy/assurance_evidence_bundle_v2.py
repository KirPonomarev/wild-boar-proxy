# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""AssuranceEvidenceBundleV2 (R66 strict live matrix).

Strict evidence verification for final candidate assurance. The assurance
reads a server-owned bundle of per-check receipts; it never accepts a caller
test count, an arbitrary network dict, a bare boolean, or a synthetic receipt
as physical acceptance.

Required receipts (12):

- exact_remote_head
- full_suite_ci
- macos_sandbox_ci
- package_artifact_checksum
- migration
- design_gate
- privacy_redaction
- workflow_integration
- web_lifecycle_security
- account_isolation
- protected_network
- provider_cli_live (strict per-provider/per-combination live matrix OR typed
  external-prerequisite status)

Outcome semantics:

- provider live pending -> WAIT_EXTERNAL_PREREQUISITE,
  ready_for_independent_audit=false, no KeyError;
- air_gap=false -> PROTECTED_NETWORK_UNPROVEN;
- one test / bare boolean / synthetic receipt / arbitrary dict ->
  FULL_SUITE_RECEIPT_INVALID or EVIDENCE_SCHEMA_INVALID;
- SYNTHETIC_PROVEN never closes required physical acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from . import gate_evidence_bundle_v2 as gebv

WAIT_EXTERNAL_PREREQUISITE = "WAIT_EXTERNAL_PREREQUISITE"
PROTECTED_NETWORK_UNPROVEN = "PROTECTED_NETWORK_UNPROVEN"
FULL_SUITE_RECEIPT_INVALID = "FULL_SUITE_RECEIPT_INVALID"

ASSURANCE_BUNDLE_FILENAME = "assurance-evidence-bundle.json"
ASSURANCE_RECEIPT_SCHEMA_VERSION = 2

# A full suite is thousands of tests; a single-test or toy receipt can
# never close this check.
MIN_FULL_SUITE_TESTS = 1000

PROTECTED_PORTS = (10808, 12334)

REQUIRED_ASSURANCE_CHECKS: tuple[str, ...] = (
    "exact_remote_head",
    "full_suite_ci",
    "macos_sandbox_ci",
    "package_artifact_checksum",
    "migration",
    "design_gate",
    "privacy_redaction",
    "workflow_integration",
    "web_lifecycle_security",
    "account_isolation",
    "protected_network",
    "provider_cli_live",
)

REQUIRED_ASSURANCE_RECEIPT_FIELDS: dict[str, tuple[type, ...]] = {
    "receipt_id": (str,),
    "schema_version": (int,),
    "plan_id": (str,),
    "plan_contract_sha256": (str,),
    "check_id": (str,),
    "candidate_sha": (str,),
    "evidence_ref": (str,),
    "evidence_sha256": (str,),
    "receipt_sha256": (str,),
    "observed_at": (str,),
    "verifier_identity": (str,),
    "status": (str,),
    "pending_code": (str, type(None)),
    "synthetic": (bool,),
}

_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA64_RE = re.compile(r"^[0-9a-f]{64}$")
_OBSERVED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

STATUS_PROVEN = "proven"
STATUS_PENDING = "pending"

PROOF_INTEGRATION = "INTEGRATION_PROVEN"
PROOF_LIVE = "LIVE_PROVEN"

MANDATORY_API_PROVIDERS = frozenset({"deepseek", "kimi", "glm", "qwen"})
MANDATORY_LIVE_COMBINATIONS: dict[str, tuple[str, ...]] = {
    "api_api": ("api", "api"),
    "api_cli": ("api", "cli"),
    "cli_cli": ("cli", "cli"),
}
CLI_PROVIDERS = frozenset({"kimi", "qwen"})


def _failure(code: str, reason: str, **context: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "reason": reason}
    for key, value in context.items():
        if value is not None:
            item[key] = value
    return item


def assurance_receipt_hash(receipt: dict[str, Any]) -> str:
    """Canonical receipt hash: all fields minus receipt_sha256."""
    proj = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    return hashlib.sha256(gebv.canonical_json_bytes(proj)).hexdigest()


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _candidate_bound(evidence: dict[str, Any], candidate: str) -> bool:
    return evidence.get("candidate_sha") == candidate


def _all_true(evidence: dict[str, Any], fields: Iterable[str]) -> bool:
    return all(evidence.get(field) is True for field in fields)


def _all_false(evidence: dict[str, Any], fields: Iterable[str]) -> bool:
    return all(evidence.get(field) is False for field in fields)


def _valid_unique_sha256s(value: Any, *, minimum: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= minimum
        and all(isinstance(item, str) and _SHA64_RE.match(item) for item in value)
        and len(set(value)) == len(value)
    )


def _valid_live_identity(item: Any, *, candidate: str) -> bool:
    if not isinstance(item, dict):
        return False
    if not _candidate_bound(item, candidate):
        return False
    if not all(
        _nonempty_string(item.get(field))
        for field in (
            "actor_id",
            "binding_id",
            "assignment_id",
            "session_id",
            "dispatch_id",
            "model_id",
            "route_id",
            "output_sha256",
        )
    ):
        return False
    if not all(
        _positive_int(item.get(field))
        for field in (
            "actor_revision",
            "binding_revision",
            "assignment_revision",
            "session_revision",
        )
    ):
        return False
    if not _SHA64_RE.match(str(item["output_sha256"])):
        return False
    if not _all_true(
        item,
        (
            "credential_present",
            "dispatch_attempted",
            "response_observed",
            "live_provider_called",
            "live_provider_proven",
            "output_present",
        ),
    ):
        return False
    return _all_false(
        item,
        ("controlled", "fallback_used", "actor_substitution_used"),
    )


def _valid_provider_live_matrix(evidence: dict[str, Any], *, candidate: str) -> bool:
    if evidence.get("proof_level") != PROOF_LIVE:
        return False
    if not _candidate_bound(evidence, candidate):
        return False
    provider_rows = evidence.get("providers")
    combination_rows = evidence.get("combinations")
    if not isinstance(provider_rows, list) or not isinstance(combination_rows, list):
        return False

    providers: dict[str, dict[str, Any]] = {}
    all_dispatch_ids: set[str] = set()
    all_session_ids: set[str] = set()
    for row in provider_rows:
        if not isinstance(row, dict) or not _valid_live_identity(row, candidate=candidate):
            return False
        provider_id = row.get("provider_id")
        if (
            not isinstance(provider_id, str)
            or provider_id not in MANDATORY_API_PROVIDERS
            or provider_id in providers
        ):
            return False
        if row.get("transport_kind") != "api":
            return False
        dispatch_id = str(row["dispatch_id"])
        session_id = str(row["session_id"])
        if dispatch_id in all_dispatch_ids or session_id in all_session_ids:
            return False
        all_dispatch_ids.add(dispatch_id)
        all_session_ids.add(session_id)
        providers[str(provider_id)] = row
    if set(providers) != MANDATORY_API_PROVIDERS:
        return False

    combinations: dict[str, dict[str, Any]] = {}
    for row in combination_rows:
        if not isinstance(row, dict):
            return False
        combination_id = row.get("combination_id")
        if not isinstance(combination_id, str):
            return False
        expected_transports = MANDATORY_LIVE_COMBINATIONS.get(combination_id)
        if expected_transports is None or combination_id in combinations:
            return False
        if not _candidate_bound(row, candidate) or row.get("proof_level") != PROOF_LIVE:
            return False
        transports = row.get("transport_kinds")
        provider_ids = row.get("provider_ids")
        actors = row.get("actor_ids")
        binding_ids = row.get("binding_ids")
        binding_revisions = row.get("binding_revisions")
        assignment_ids = row.get("assignment_ids")
        assignment_revisions = row.get("assignment_revisions")
        session_ids = row.get("session_ids")
        session_revisions = row.get("session_revisions")
        dispatch_ids = row.get("dispatch_ids")
        model_ids = row.get("model_ids")
        route_ids = row.get("route_ids")
        outputs = row.get("output_sha256s")
        credential_presence = row.get("credential_presence")
        if not all(
            isinstance(values, list) and len(values) == 2
            for values in (
                transports,
                provider_ids,
                actors,
                binding_ids,
                binding_revisions,
                assignment_ids,
                assignment_revisions,
                session_ids,
                session_revisions,
                dispatch_ids,
                model_ids,
                route_ids,
                outputs,
                credential_presence,
            )
        ):
            return False
        if tuple(transports) != expected_transports:
            return False
        if not all(_nonempty_string(value) for value in provider_ids):
            return False
        if combination_id == "api_api" and not (
            all(value in MANDATORY_API_PROVIDERS for value in provider_ids)
            and len(set(provider_ids)) == 2
        ):
            return False
        if combination_id == "api_cli" and not (
            provider_ids[0] in MANDATORY_API_PROVIDERS
            and provider_ids[1] in CLI_PROVIDERS
        ):
            return False
        if combination_id == "cli_cli" and set(provider_ids) != CLI_PROVIDERS:
            return False
        if not all(_nonempty_string(value) for value in actors):
            return False
        if not all(_nonempty_string(value) for value in binding_ids):
            return False
        if not all(_positive_int(value) for value in binding_revisions):
            return False
        if not all(_nonempty_string(value) for value in assignment_ids):
            return False
        if not all(_positive_int(value) for value in assignment_revisions):
            return False
        if not all(_nonempty_string(value) for value in session_ids):
            return False
        if not all(_positive_int(value) for value in session_revisions):
            return False
        if not all(_nonempty_string(value) for value in dispatch_ids):
            return False
        if not all(_nonempty_string(value) for value in model_ids):
            return False
        if not all(_nonempty_string(value) for value in route_ids):
            return False
        if not all(isinstance(value, str) and _SHA64_RE.match(value) for value in outputs):
            return False
        if credential_presence != [True, True]:
            return False
        if len(set(dispatch_ids)) != 2 or len(set(session_ids)) != 2:
            return False
        if any(value in all_dispatch_ids for value in dispatch_ids):
            return False
        if any(value in all_session_ids for value in session_ids):
            return False
        if not _all_true(
            row,
            (
                "dispatches_attempted",
                "responses_observed",
                "live_provider_proven",
                "outputs_present",
            ),
        ):
            return False
        if not _all_false(row, ("controlled", "fallback_used", "actor_substitution_used")):
            return False
        all_dispatch_ids.update(str(value) for value in dispatch_ids)
        all_session_ids.update(str(value) for value in session_ids)
        combinations[str(combination_id)] = row
    return set(combinations) == set(MANDATORY_LIVE_COMBINATIONS)


def build_assurance_receipt(
    *,
    receipt_id: str,
    plan_id: str,
    plan_contract_sha256: str,
    check_id: str,
    candidate_sha: str,
    evidence_ref: str,
    evidence_sha256: str,
    observed_at: str,
    verifier_identity: str,
    status: str = STATUS_PROVEN,
    pending_code: str | None = None,
    synthetic: bool = False,
) -> dict[str, Any]:
    """Server-owned assurance receipt construction with the bound hash."""
    receipt: dict[str, Any] = {
        "receipt_id": str(receipt_id),
        "schema_version": ASSURANCE_RECEIPT_SCHEMA_VERSION,
        "plan_id": str(plan_id),
        "plan_contract_sha256": str(plan_contract_sha256),
        "check_id": str(check_id),
        "candidate_sha": str(candidate_sha),
        "evidence_ref": str(evidence_ref),
        "evidence_sha256": str(evidence_sha256),
        "observed_at": str(observed_at),
        "verifier_identity": str(verifier_identity),
        "status": str(status),
        "pending_code": pending_code,
        "synthetic": bool(synthetic),
    }
    receipt["receipt_sha256"] = assurance_receipt_hash(receipt)
    return receipt


class AssuranceBundleVerifier:
    """Instance-sealed verifier: explicit project/control roots, no env,
    no caller-provided truth. Git primitives delegate to the gate
    verifier (same read-only subprocess helpers)."""

    def __init__(self, *, project_root: Path | str, control_root: Path | str) -> None:
        self._project_root = Path(project_root)
        self._control_root = Path(control_root)
        self._git = gebv.GateEvidenceVerifier(
            project_root=self._project_root, control_root=self._control_root
        )

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def control_root(self) -> Path:
        return self._control_root

    # --- evidence file access ---

    def _read_evidence(self, evidence_ref: str) -> tuple[bytes | None, dict[str, Any] | None]:
        """Read an evidence blob inside the control root. Path traversal
        outside the control root is rejected."""
        try:
            target = (self._control_root / evidence_ref).resolve()
            target.relative_to(self._control_root.resolve())
        except (OSError, ValueError):
            return None, _failure(
                "EVIDENCE_SCHEMA_INVALID", "evidence_ref_escapes_control_root",
                evidence_ref=evidence_ref,
            )
        if not target.is_file():
            return None, _failure(
                "EVIDENCE_DIGEST_MISMATCH", "evidence_file_missing",
                evidence_ref=evidence_ref,
            )
        try:
            return target.read_bytes(), None
        except OSError:
            return None, _failure(
                "EVIDENCE_DIGEST_MISMATCH", "evidence_file_unreadable",
                evidence_ref=evidence_ref,
            )

    # --- per-check evidence rules ---

    def _verify_check_evidence(
        self, check_id: str, evidence: Any, *, candidate: str, receipt_id: str | None
    ) -> list[dict[str, Any]]:
        f: list[dict[str, Any]] = []
        if not isinstance(evidence, dict):
            return [
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "evidence_not_an_object",
                    check_id=check_id, receipt_id=receipt_id,
                )
            ]
        if evidence.get("proof_level") == "SYNTHETIC_PROVEN":
            f.append(
                _failure(
                    FULL_SUITE_RECEIPT_INVALID if check_id == "full_suite_ci"
                    else "EVIDENCE_SCHEMA_INVALID",
                    "synthetic_proof_not_physical_acceptance",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
            return f

        if check_id == "exact_remote_head":
            local = evidence.get("local_head")
            remote = evidence.get("remote_head")
            if not (
                isinstance(local, str)
                and isinstance(remote, str)
                and _SHA40_RE.match(local)
                and local == remote == candidate
            ):
                f.append(
                    _failure(
                        "EVIDENCE_CANDIDATE_MISMATCH", "exact_remote_head_mismatch",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "full_suite_ci":
            tests_passed = evidence.get("tests_passed")
            if (
                not isinstance(tests_passed, int)
                or tests_passed < MIN_FULL_SUITE_TESTS
                or evidence.get("clean_run") is not True
                or evidence.get("runner") != "ci"
                or evidence.get("candidate_sha") != candidate
            ):
                f.append(
                    _failure(
                        FULL_SUITE_RECEIPT_INVALID, "full_suite_receipt_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                        detail={
                            "tests_passed": tests_passed,
                            "min_required": MIN_FULL_SUITE_TESTS,
                        },
                    )
                )
        elif check_id == "macos_sandbox_ci":
            if not (
                evidence.get("platform") == "macos"
                and evidence.get("sandbox_exec") is True
                and evidence.get("runner") == "ci"
                and isinstance(evidence.get("tests_passed"), int)
                and evidence.get("tests_passed", 0) > 0
                and _candidate_bound(evidence, candidate)
                and _positive_int(evidence.get("run_id"))
                and _positive_int(evidence.get("job_id"))
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "macos_sandbox_receipt_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "package_artifact_checksum":
            digest = evidence.get("artifact_sha256")
            if not (
                isinstance(digest, str)
                and _SHA64_RE.match(digest)
                and _candidate_bound(evidence, candidate)
                and _nonempty_string(evidence.get("artifact_name"))
                and _positive_int(evidence.get("artifact_size_bytes"))
                and evidence.get("runner") == "ci"
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "package_checksum_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "design_gate":
            if not (
                evidence.get("design_gate_earned") is True
                and evidence.get("token")
                == "EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY"
                and _candidate_bound(evidence, candidate)
                and _SHA64_RE.match(str(evidence.get("gate_bundle_sha256") or ""))
            ):
                f.append(
                    _failure(
                        "DESIGN_GATE_NOT_EARNED", "design_gate_not_earned",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "protected_network":
            ports = evidence.get("protected_ports")
            if not (
                evidence.get("air_gap") is True
                and evidence.get("no_detected_mutation") is True
                and evidence.get("evidence_basis")
                in {
                    "guard_enforcement",
                    "pre_post_comparison",
                    "executor_action_ledger",
                    "system_instrumentation",
                }
                and _candidate_bound(evidence, candidate)
                and _SHA64_RE.match(str(evidence.get("guard_receipt_sha256") or ""))
            ):
                f.append(
                    _failure(
                        PROTECTED_NETWORK_UNPROVEN, "air_gap_unproven",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
            if not (
                isinstance(ports, list)
                and all(p in ports for p in PROTECTED_PORTS)
            ):
                f.append(
                    _failure(
                        PROTECTED_NETWORK_UNPROVEN, "protected_ports_unproven",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "provider_cli_live":
            if not _valid_provider_live_matrix(evidence, candidate=candidate):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID",
                        "provider_cli_live_matrix_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "migration":
            if not (
                evidence.get("proof_level") == PROOF_INTEGRATION
                and _candidate_bound(evidence, candidate)
                and evidence.get("migration_verified") is True
                and _positive_int(evidence.get("source_schema_version"))
                and _positive_int(evidence.get("target_schema_version"))
                and evidence["target_schema_version"] > evidence["source_schema_version"]
                and isinstance(evidence.get("records_verified"), int)
                and not isinstance(evidence.get("records_verified"), bool)
                and evidence["records_verified"] >= 0
                and evidence.get("legacy_projection_lossless") is True
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "migration_evidence_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "privacy_redaction":
            if not (
                evidence.get("proof_level") == PROOF_INTEGRATION
                and _candidate_bound(evidence, candidate)
                and _all_true(
                    evidence,
                    (
                        "secret_scan_passed",
                        "packet_redaction_verified",
                        "raw_backend_absent",
                        "credential_values_absent",
                    ),
                )
                and _positive_int(evidence.get("files_scanned"))
                and _SHA64_RE.match(str(evidence.get("scan_receipt_sha256") or ""))
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "privacy_redaction_evidence_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "workflow_integration":
            if not (
                evidence.get("proof_level") == PROOF_INTEGRATION
                and _candidate_bound(evidence, candidate)
                and evidence.get("workflow_mode") == "production_path_controlled"
                and _all_true(
                    evidence,
                    (
                        "registry_bound",
                        "independent_receipts",
                        "visible_context_delivery",
                        "lease_cleanup_verified",
                    ),
                )
                and _all_false(evidence, ("fallback_used", "actor_substitution_used"))
                and _valid_unique_sha256s(
                    evidence.get("receipt_sha256s"), minimum=2
                )
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "workflow_integration_evidence_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "web_lifecycle_security":
            if not (
                evidence.get("proof_level") == PROOF_INTEGRATION
                and _candidate_bound(evidence, candidate)
                and _all_true(
                    evidence,
                    (
                        "loopback_only",
                        "token_enforced",
                        "origin_enforced",
                        "csrf_enforced",
                        "rate_limit_enforced",
                        "writer_fencing_verified",
                        "browser_authority_bounded",
                    ),
                )
                and _SHA64_RE.match(str(evidence.get("security_matrix_sha256") or ""))
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "web_lifecycle_security_evidence_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        elif check_id == "account_isolation":
            if not (
                evidence.get("proof_level") == PROOF_INTEGRATION
                and _candidate_bound(evidence, candidate)
                and _all_true(
                    evidence,
                    (
                        "dedicated_accounts",
                        "provider_homes_isolated",
                        "credential_stores_isolated",
                        "primary_codex_untouched",
                        "main_account_reuse_absent",
                    ),
                )
                and _SHA64_RE.match(str(evidence.get("isolation_receipt_sha256") or ""))
            ):
                f.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "account_isolation_evidence_invalid",
                        check_id=check_id, receipt_id=receipt_id,
                    )
                )
        else:
            f.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "unknown_assurance_check",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        return f

    # --- receipt verification ---

    def verify_receipt(
        self,
        receipt: Any,
        *,
        candidate: str,
        sealed_plan_id: str | None,
        sealed_plan_hash: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Returns (failures, pending_record_or_None)."""
        failures: list[dict[str, Any]] = []
        if not isinstance(receipt, dict):
            return [_failure("EVIDENCE_SCHEMA_INVALID", "receipt_not_an_object")], None
        check_id = receipt.get("check_id") if isinstance(receipt.get("check_id"), str) else None
        receipt_id = (
            receipt.get("receipt_id") if isinstance(receipt.get("receipt_id"), str) else None
        )

        for field, ftypes in REQUIRED_ASSURANCE_RECEIPT_FIELDS.items():
            if field not in receipt or not isinstance(receipt[field], ftypes):
                failures.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "field_missing_or_wrong_type",
                        field=field, check_id=check_id, receipt_id=receipt_id,
                    )
                )
        if failures:
            return failures, None

        if receipt["schema_version"] != ASSURANCE_RECEIPT_SCHEMA_VERSION:
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "schema_version_mismatch",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if not _OBSERVED_AT_RE.match(receipt["observed_at"]):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "observed_at_invalid",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if not _SHA40_RE.match(receipt["candidate_sha"]):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "candidate_sha_format_invalid",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        for field in ("evidence_sha256", "receipt_sha256", "plan_contract_sha256"):
            if not _SHA64_RE.match(receipt[field]):
                failures.append(
                    _failure(
                        "EVIDENCE_SCHEMA_INVALID", "digest_format_invalid",
                        field=field, check_id=check_id, receipt_id=receipt_id,
                    )
                )
        if receipt["synthetic"] is not False:
            failures.append(
                _failure(
                    FULL_SUITE_RECEIPT_INVALID
                    if check_id == "full_suite_ci"
                    else "EVIDENCE_SCHEMA_INVALID",
                    "synthetic_receipt_not_physical_acceptance",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        status = receipt["status"]
        if status not in (STATUS_PROVEN, STATUS_PENDING):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "status_invalid",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if status == STATUS_PENDING and not isinstance(receipt["pending_code"], str):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "pending_without_typed_code",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if status == STATUS_PENDING and (
            check_id != "provider_cli_live"
            or receipt["pending_code"] != WAIT_EXTERNAL_PREREQUISITE
        ):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "pending_not_external_live_gate",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if status == STATUS_PROVEN and receipt["pending_code"] is not None:
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "proven_with_pending_code",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if failures:
            return failures, None

        # Candidate binding: assurance receipts are about THE candidate.
        if receipt["candidate_sha"] != candidate:
            failures.append(
                _failure(
                    "EVIDENCE_CANDIDATE_MISMATCH", "receipt_candidate_mismatch",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        elif not self._git._commit_exists(candidate):
            failures.append(
                _failure(
                    "EVIDENCE_COMMIT_UNREACHABLE", "candidate_missing",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )

        # Canonical receipt hash.
        if assurance_receipt_hash(receipt) != receipt["receipt_sha256"]:
            failures.append(
                _failure(
                    "EVIDENCE_DIGEST_MISMATCH", "receipt_hash_mismatch",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )

        # Plan binding against the sealed plan.
        if sealed_plan_id is not None and receipt["plan_id"] != sealed_plan_id:
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "plan_id_mismatch",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
        if (
            sealed_plan_hash is not None
            and receipt["plan_contract_sha256"] != sealed_plan_hash
        ):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "plan_hash_mismatch",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )

        # Pending receipts carry no evidence requirement; they are honest
        # typed waits, recorded for the bundle outcome.
        if status == STATUS_PENDING:
            return failures, {
                "check_id": check_id,
                "pending_code": receipt["pending_code"],
                "receipt_id": receipt_id,
            }

        # Evidence blob: must exist inside the control root with a
        # matching digest, then per-check content rules.
        blob, blob_failure = self._read_evidence(receipt["evidence_ref"])
        if blob_failure is not None:
            blob_failure.update({"check_id": check_id, "receipt_id": receipt_id})
            failures.append(blob_failure)
            return failures, None
        assert blob is not None
        actual = hashlib.sha256(blob).hexdigest()
        if actual != receipt["evidence_sha256"]:
            failures.append(
                _failure(
                    "EVIDENCE_DIGEST_MISMATCH", "evidence_digest_mismatch",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
            return failures, None
        try:
            evidence = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "evidence_not_json",
                    check_id=check_id, receipt_id=receipt_id,
                )
            )
            return failures, None
        failures.extend(
            self._verify_check_evidence(
                str(check_id), evidence, candidate=candidate, receipt_id=receipt_id
            )
        )
        return failures, None

    # --- bundle verification ---

    def verify_bundle(
        self,
        *,
        candidate: str | None = None,
        required_checks: Iterable[str] = REQUIRED_ASSURANCE_CHECKS,
    ) -> dict[str, Any]:
        failures: list[dict[str, Any]] = []
        pendings: list[dict[str, Any]] = []
        findings: dict[str, Any] = {}

        origin_main = self._git.origin_main_sha()
        findings["origin_main_sha"] = origin_main
        if origin_main is None:
            failures.append(
                _failure("EVIDENCE_CANDIDATE_MISMATCH", "origin_main_unavailable")
            )
            return {
                "ready": False, "waiting": False,
                "failures": failures, "pendings": pendings, "findings": findings,
            }
        if candidate is None:
            candidate = origin_main
        findings["candidate_sha"] = candidate
        if candidate != origin_main:
            failures.append(
                _failure("EVIDENCE_CANDIDATE_MISMATCH", "candidate_not_origin_main")
            )

        # Execution-state canonical hash + sealed plan (shared convention).
        state, state_failure = self._git._load_execution_state()
        if state_failure is not None:
            failures.append(state_failure)
        sealed_plan_id = state.get("plan_id") if state else None
        sealed_plan_hash = state.get("plan_contract_sha256") if state else None

        # Bundle file.
        bundle_path = self._control_root / ASSURANCE_BUNDLE_FILENAME
        if not bundle_path.is_file():
            failures.append(
                _failure("EVIDENCE_SCHEMA_INVALID", "assurance_bundle_missing")
            )
            return {
                "ready": False, "waiting": False,
                "failures": failures, "pendings": pendings, "findings": findings,
            }
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failures.append(
                _failure("EVIDENCE_SCHEMA_INVALID", "assurance_bundle_unreadable")
            )
            return {
                "ready": False, "waiting": False,
                "failures": failures, "pendings": pendings, "findings": findings,
            }
        receipts = bundle.get("receipts")
        if not isinstance(receipts, list) or not receipts:
            failures.append(
                _failure("EVIDENCE_SCHEMA_INVALID", "assurance_bundle_empty")
            )
            return {
                "ready": False, "waiting": False,
                "failures": failures, "pendings": pendings, "findings": findings,
            }
        findings["receipt_count"] = len(receipts)

        for receipt in receipts:
            receipt_failures, pending = self.verify_receipt(
                receipt,
                candidate=candidate,
                sealed_plan_id=(
                    sealed_plan_id if isinstance(sealed_plan_id, str) else None
                ),
                sealed_plan_hash=(
                    sealed_plan_hash if isinstance(sealed_plan_hash, str) else None
                ),
            )
            failures.extend(receipt_failures)
            if pending is not None:
                pendings.append(pending)

        # Duplicates.
        check_ids = [r.get("check_id") for r in receipts if isinstance(r, dict)]
        receipt_ids = [r.get("receipt_id") for r in receipts if isinstance(r, dict)]
        for label, values in (("check_id", check_ids), ("receipt_id", receipt_ids)):
            seen: set[Any] = set()
            for value in values:
                if value is None:
                    continue
                if value in seen:
                    failures.append(
                        _failure(
                            "EVIDENCE_SCHEMA_INVALID", f"duplicate_{label}",
                            **{label: value},
                        )
                    )
                seen.add(value)

        # Required coverage.
        required = set(required_checks)
        present = {c for c in check_ids if isinstance(c, str)}
        missing = sorted(required - present)
        findings["missing_required_checks"] = missing
        for check in missing:
            failures.append(
                _failure(
                    "EVIDENCE_SCHEMA_INVALID", "required_check_missing", check_id=check
                )
            )

        findings["failure_count"] = len(failures)
        findings["pending_count"] = len(pendings)
        waiting = not failures and bool(pendings)
        ready = not failures and not pendings
        return {
            "ready": ready,
            "waiting": waiting,
            "failures": failures,
            "pendings": pendings,
            "findings": findings,
        }


def production_verifier() -> AssuranceBundleVerifier:
    return AssuranceBundleVerifier(
        project_root=gebv.production_project_root(),
        control_root=gebv.production_control_root(),
    )


__all__ = [
    "WAIT_EXTERNAL_PREREQUISITE",
    "PROTECTED_NETWORK_UNPROVEN",
    "FULL_SUITE_RECEIPT_INVALID",
    "ASSURANCE_BUNDLE_FILENAME",
    "ASSURANCE_RECEIPT_SCHEMA_VERSION",
    "MIN_FULL_SUITE_TESTS",
    "PROTECTED_PORTS",
    "REQUIRED_ASSURANCE_CHECKS",
    "REQUIRED_ASSURANCE_RECEIPT_FIELDS",
    "STATUS_PROVEN",
    "STATUS_PENDING",
    "AssuranceBundleVerifier",
    "assurance_receipt_hash",
    "build_assurance_receipt",
    "production_verifier",
]
