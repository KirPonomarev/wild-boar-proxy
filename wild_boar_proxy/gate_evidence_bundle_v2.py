# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""GateEvidenceBundleV2 (R54).

Strict evidence verification for the execution-core design gate. Every
required receipt is a `closeout_reference` bound to real git objects: the
merge commit, the closeout blob read via `git show <merge>:<path>` (never
the current worktree file), the remote-main transition, the sealed plan
hash, and the execution-state canonical hash. Stage labels alone earn
nothing.

Typed failure codes:

- EVIDENCE_SCHEMA_INVALID
- EVIDENCE_DIGEST_MISMATCH
- EVIDENCE_COMMIT_UNREACHABLE
- EVIDENCE_STAGE_INVALIDATED
- EVIDENCE_CANDIDATE_MISMATCH

The production gate uses `production_verifier()` (server-owned roots, no
environment overrides). Tests construct `GateEvidenceVerifier` instances
against synthetic repositories and control roots.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

EVIDENCE_SCHEMA_INVALID = "EVIDENCE_SCHEMA_INVALID"
EVIDENCE_DIGEST_MISMATCH = "EVIDENCE_DIGEST_MISMATCH"
EVIDENCE_COMMIT_UNREACHABLE = "EVIDENCE_COMMIT_UNREACHABLE"
EVIDENCE_STAGE_INVALIDATED = "EVIDENCE_STAGE_INVALIDATED"
EVIDENCE_CANDIDATE_MISMATCH = "EVIDENCE_CANDIDATE_MISMATCH"

RECEIPT_SCHEMA_VERSION = 2
RECEIPT_TYPE_CLOSEOUT_REFERENCE = "closeout_reference"

# Required execution-core stages (B00–B13), full stage ids.
REQUIRED_STAGES: tuple[str, ...] = (
    "B00_BASELINE_ADMISSION_REPAIR",
    "B01_ACTOR_ADR_AND_SPIKES",
    "B02_ACTOR_SCHEMA_V2_AND_MIGRATION",
    "B03_TRANSPORT_AND_EVIDENCE_STATE_MACHINE",
    "B04_THREAD_CONTEXT_LEDGER_V2",
    "B05_DISPATCHER_ASSIGNMENTS_PERMISSIONS_DIAGNOSTICS",
    "B06_LEGACY_SURFACE_AND_EVIDENCE_MATRIX_REGRESSION",
    "B07_CODE_MULTI_API_CORE",
    "B08_CODE_QWEN_API",
    "B09_ONE_SHOT_CLI_RUNTIME",
    "B10_CODE_QWEN_ONE_SHOT_CLI",
    "B11_CODE_KIMI_ONE_SHOT_CLI",
    "B12_ADMISSION_GLM_CLI_API_ONLY",
    "B13_SEQUENTIAL_WORKFLOW_RUNNER",
)

REQUIRED_RECEIPT_FIELDS: dict[str, type] = {
    "receipt_id": str,
    "schema_version": int,
    "plan_id": str,
    "plan_contract_sha256": str,
    "stage_id": str,
    "receipt_type": str,
    "candidate_sha": str,
    "merge_commit_sha": str,
    "remote_main_sha": str,
    "closeout_path": str,
    "closeout_blob_sha256": str,
    "receipt_sha256": str,
    "observed_at": str,
    "verifier_identity": str,
    "invalidated": bool,
}

_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA64_RE = re.compile(r"^[0-9a-f]{64}$")
_OBSERVED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

EVIDENCE_INDEX_FILENAME = "evidence-index.json"
EXECUTION_STATE_FILENAME = "execution-state.json"


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON: UTF-8, sorted keys, compact separators, one
    trailing newline. Matches the execution-state CAS convention."""
    return (
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
        + b"\n"
    )


def execution_state_hash(state: dict[str, Any]) -> str:
    """Hash projection: the whole state object minus current_state_sha256."""
    proj = {k: v for k, v in state.items() if k != "current_state_sha256"}
    return hashlib.sha256(canonical_json_bytes(proj)).hexdigest()


def receipt_hash(receipt: dict[str, Any]) -> str:
    """Canonical receipt hash: all fields minus receipt_sha256."""
    proj = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    return hashlib.sha256(canonical_json_bytes(proj)).hexdigest()


def build_closeout_reference_receipt(
    *,
    receipt_id: str,
    plan_id: str,
    plan_contract_sha256: str,
    stage_id: str,
    candidate_sha: str,
    merge_commit_sha: str,
    remote_main_sha: str,
    closeout_path: str,
    closeout_blob_sha256: str,
    observed_at: str,
    verifier_identity: str,
) -> dict[str, Any]:
    """Server-owned receipt construction with the bound canonical hash."""
    receipt: dict[str, Any] = {
        "receipt_id": str(receipt_id),
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "plan_id": str(plan_id),
        "plan_contract_sha256": str(plan_contract_sha256),
        "stage_id": str(stage_id),
        "receipt_type": RECEIPT_TYPE_CLOSEOUT_REFERENCE,
        "candidate_sha": str(candidate_sha),
        "merge_commit_sha": str(merge_commit_sha),
        "remote_main_sha": str(remote_main_sha),
        "closeout_path": str(closeout_path),
        "closeout_blob_sha256": str(closeout_blob_sha256),
        "observed_at": str(observed_at),
        "verifier_identity": str(verifier_identity),
        "invalidated": False,
    }
    receipt["receipt_sha256"] = receipt_hash(receipt)
    return receipt


def _failure(code: str, reason: str, **context: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "reason": reason}
    for key, value in context.items():
        if value is not None:
            item[key] = value
    return item


class GateEvidenceVerifier:
    """Instance-sealed verifier: explicit project/control roots, no env."""

    def __init__(self, *, project_root: Path | str, control_root: Path | str) -> None:
        self._project_root = Path(project_root)
        self._control_root = Path(control_root)

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def control_root(self) -> Path:
        return self._control_root

    # --- git primitives (read-only) ---

    def _git(self, args: list[str]) -> tuple[int, str]:
        try:
            result = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(self._project_root),
            )
        except (OSError, subprocess.SubprocessError):
            return 1, ""
        return result.returncode, result.stdout.strip()

    def _commit_exists(self, sha: str) -> bool:
        if not _SHA40_RE.match(sha or ""):
            return False
        rc, out = self._git(["cat-file", "-t", sha])
        return rc == 0 and out == "commit"

    def _is_ancestor(self, sha: str, of: str) -> bool:
        if not (_SHA40_RE.match(sha or "") and _SHA40_RE.match(of or "")):
            return False
        rc, _ = self._git(["merge-base", "--is-ancestor", sha, of])
        return rc == 0

    def _git_show_blob(self, sha: str, path: str) -> bytes | None:
        try:
            result = subprocess.run(
                ["git", "show", f"{sha}:{path}"],
                capture_output=True,
                timeout=15,
                cwd=str(self._project_root),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout

    def origin_main_sha(self) -> str | None:
        rc, out = self._git(["rev-parse", "origin/main"])
        if rc != 0 or not _SHA40_RE.match(out):
            return None
        return out

    # --- state / index loading ---

    def _load_execution_state(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        path = self._control_root / EXECUTION_STATE_FILENAME
        if not path.is_file():
            return None, _failure(
                EVIDENCE_SCHEMA_INVALID, "execution_state_missing"
            )
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, _failure(
                EVIDENCE_SCHEMA_INVALID, "execution_state_unreadable"
            )
        stored = state.get("current_state_sha256")
        if not isinstance(stored, str) or not _SHA64_RE.match(stored):
            return None, _failure(
                EVIDENCE_SCHEMA_INVALID, "execution_state_hash_missing"
            )
        if execution_state_hash(state) != stored:
            return None, _failure(
                EVIDENCE_SCHEMA_INVALID, "execution_state_hash_invalid"
            )
        return state, None

    def _load_evidence_index(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        path = self._control_root / EVIDENCE_INDEX_FILENAME
        if not path.is_file():
            return None, _failure(EVIDENCE_SCHEMA_INVALID, "evidence_index_missing")
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None, _failure(EVIDENCE_SCHEMA_INVALID, "evidence_index_unreadable")
        refs = index.get("references")
        if not isinstance(refs, list) or not refs:
            return None, _failure(EVIDENCE_SCHEMA_INVALID, "evidence_index_empty")
        return index, None

    # --- receipt verification ---

    def verify_receipt(
        self,
        receipt: Any,
        *,
        candidate: str,
        sealed_plan_id: str | None,
        sealed_plan_hash: str | None,
    ) -> list[dict[str, Any]]:
        """Verify one receipt against git truth and the sealed plan."""
        failures: list[dict[str, Any]] = []
        if not isinstance(receipt, dict):
            return [_failure(EVIDENCE_SCHEMA_INVALID, "receipt_not_an_object")]
        stage_id = receipt.get("stage_id") if isinstance(receipt.get("stage_id"), str) else None
        receipt_id = (
            receipt.get("receipt_id") if isinstance(receipt.get("receipt_id"), str) else None
        )

        # Rule 1: all fields present with correct types.
        for field, ftype in REQUIRED_RECEIPT_FIELDS.items():
            if field not in receipt or not isinstance(receipt[field], ftype):
                failures.append(
                    _failure(
                        EVIDENCE_SCHEMA_INVALID,
                        "field_missing_or_wrong_type",
                        field=field,
                        stage_id=stage_id,
                        receipt_id=receipt_id,
                    )
                )
        if failures:
            return failures

        # Rule: schema/version/type exactness.
        if receipt["schema_version"] != RECEIPT_SCHEMA_VERSION:
            failures.append(
                _failure(
                    EVIDENCE_SCHEMA_INVALID,
                    "schema_version_mismatch",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
        if receipt["receipt_type"] != RECEIPT_TYPE_CLOSEOUT_REFERENCE:
            failures.append(
                _failure(
                    EVIDENCE_SCHEMA_INVALID,
                    "receipt_type_mismatch",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
        if not _OBSERVED_AT_RE.match(receipt["observed_at"]):
            failures.append(
                _failure(
                    EVIDENCE_SCHEMA_INVALID,
                    "observed_at_invalid",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )

        # Rule 2: SHA formats.
        for field in ("candidate_sha", "merge_commit_sha", "remote_main_sha"):
            if not _SHA40_RE.match(receipt[field]):
                failures.append(
                    _failure(
                        EVIDENCE_SCHEMA_INVALID,
                        "sha_format_invalid",
                        field=field,
                        stage_id=stage_id,
                        receipt_id=receipt_id,
                    )
                )
        for field in ("closeout_blob_sha256", "receipt_sha256", "plan_contract_sha256"):
            if not _SHA64_RE.match(receipt[field]):
                failures.append(
                    _failure(
                        EVIDENCE_SCHEMA_INVALID,
                        "digest_format_invalid",
                        field=field,
                        stage_id=stage_id,
                        receipt_id=receipt_id,
                    )
                )
        if failures:
            return failures

        # Rule 10a: invalidated flag must be false.
        if receipt["invalidated"] is not False:
            failures.append(
                _failure(
                    EVIDENCE_STAGE_INVALIDATED,
                    "receipt_invalidated",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )

        # Rule 3: merge commit exists.
        merge_sha = receipt["merge_commit_sha"]
        if not self._commit_exists(merge_sha):
            failures.append(
                _failure(
                    EVIDENCE_COMMIT_UNREACHABLE,
                    "merge_commit_missing",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
            return failures

        # Rule 4: merge commit is an ancestor of the gate candidate.
        if not self._is_ancestor(merge_sha, candidate):
            failures.append(
                _failure(
                    EVIDENCE_COMMIT_UNREACHABLE,
                    "merge_commit_not_ancestor_of_candidate",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )

        # Rule 5: remote_main_sha matches the receipt transition.
        if receipt["remote_main_sha"] != merge_sha:
            failures.append(
                _failure(
                    EVIDENCE_SCHEMA_INVALID,
                    "remote_main_transition_mismatch",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )

        # Rule: receipt candidate must be reachable from the gate candidate
        # (a receipt bound to a fork/unknown candidate is a candidate
        # mismatch, not merely an old observation).
        if not self._is_ancestor(receipt["candidate_sha"], candidate):
            failures.append(
                _failure(
                    EVIDENCE_CANDIDATE_MISMATCH,
                    "receipt_candidate_unreachable",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
        # The receipt candidate must itself contain the merge commit.
        if not self._is_ancestor(merge_sha, receipt["candidate_sha"]):
            failures.append(
                _failure(
                    EVIDENCE_CANDIDATE_MISMATCH,
                    "merge_not_in_receipt_candidate",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )

        # Rules 6+7: closeout blob from git show at the merge commit;
        # never the current worktree file.
        blob = self._git_show_blob(merge_sha, receipt["closeout_path"])
        if blob is None:
            failures.append(
                _failure(
                    EVIDENCE_DIGEST_MISMATCH,
                    "closeout_missing_in_commit",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
        else:
            actual = hashlib.sha256(blob).hexdigest()
            if actual != receipt["closeout_blob_sha256"]:
                failures.append(
                    _failure(
                        EVIDENCE_DIGEST_MISMATCH,
                        "closeout_digest_mismatch",
                        stage_id=stage_id,
                        receipt_id=receipt_id,
                    )
                )

        # Rule 8: canonical receipt hash.
        if receipt_hash(receipt) != receipt["receipt_sha256"]:
            failures.append(
                _failure(
                    EVIDENCE_DIGEST_MISMATCH,
                    "receipt_hash_mismatch",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )

        # Rule 9: plan binding against the sealed plan.
        if sealed_plan_id is not None and receipt["plan_id"] != sealed_plan_id:
            failures.append(
                _failure(
                    EVIDENCE_SCHEMA_INVALID,
                    "plan_id_mismatch",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
        if (
            sealed_plan_hash is not None
            and receipt["plan_contract_sha256"] != sealed_plan_hash
        ):
            failures.append(
                _failure(
                    EVIDENCE_SCHEMA_INVALID,
                    "plan_hash_mismatch",
                    stage_id=stage_id,
                    receipt_id=receipt_id,
                )
            )
        return failures

    # --- bundle verification ---

    def verify_bundle(
        self,
        *,
        candidate: str | None = None,
        required_stages: Iterable[str] = REQUIRED_STAGES,
    ) -> dict[str, Any]:
        """Verify the whole GateEvidenceBundleV2.

        `candidate` defaults to origin/main (production behavior). The
        gate's candidate must equal origin/main (rule 12).
        """
        failures: list[dict[str, Any]] = []
        findings: dict[str, Any] = {}

        origin_main = self.origin_main_sha()
        findings["origin_main_sha"] = origin_main
        if origin_main is None:
            failures.append(
                _failure(EVIDENCE_CANDIDATE_MISMATCH, "origin_main_unavailable")
            )
            return {"earned": False, "failures": failures, "findings": findings}
        if candidate is None:
            candidate = origin_main
        findings["candidate_sha"] = candidate
        if candidate != origin_main:
            failures.append(
                _failure(EVIDENCE_CANDIDATE_MISMATCH, "candidate_not_origin_main")
            )
        if not self._commit_exists(candidate):
            failures.append(
                _failure(EVIDENCE_COMMIT_UNREACHABLE, "candidate_missing")
            )

        # Rule 13: execution-state canonical hash.
        state, state_failure = self._load_execution_state()
        if state_failure is not None:
            failures.append(state_failure)
        sealed_plan_id = state.get("plan_id") if state else None
        sealed_plan_hash = state.get("plan_contract_sha256") if state else None
        findings["sealed_plan_id"] = sealed_plan_id

        index, index_failure = self._load_evidence_index()
        if index_failure is not None:
            failures.append(index_failure)
            return {"earned": False, "failures": failures, "findings": findings}

        refs = index["references"] if index else []
        findings["receipt_count"] = len(refs)

        # Per-receipt verification.
        per_receipt_failures: list[dict[str, Any]] = []
        for ref in refs:
            per_receipt_failures.extend(
                self.verify_receipt(
                    ref,
                    candidate=candidate,
                    sealed_plan_id=sealed_plan_id if isinstance(sealed_plan_id, str) else None,
                    sealed_plan_hash=(
                        sealed_plan_hash if isinstance(sealed_plan_hash, str) else None
                    ),
                )
            )
        failures.extend(per_receipt_failures)

        # Rule 11: no duplicate stage IDs / receipt IDs.
        stage_ids = [r.get("stage_id") for r in refs if isinstance(r, dict)]
        receipt_ids = [r.get("receipt_id") for r in refs if isinstance(r, dict)]
        for label, values in (("stage_id", stage_ids), ("receipt_id", receipt_ids)):
            seen: set[Any] = set()
            for value in values:
                if value is None:
                    continue
                if value in seen:
                    failures.append(
                        _failure(
                            EVIDENCE_SCHEMA_INVALID,
                            f"duplicate_{label}",
                            **{label: value},
                        )
                    )
                seen.add(value)

        # Required-stage coverage (stage labels alone are not enough: the
        # receipts above must also have passed per-receipt verification).
        required = set(required_stages)
        present = {s for s in stage_ids if isinstance(s, str)}
        missing = sorted(required - present)
        findings["missing_required_stages"] = missing
        for stage in missing:
            failures.append(
                _failure(EVIDENCE_SCHEMA_INVALID, "required_stage_missing", stage_id=stage)
            )

        # Rules 14+15: execution-state invalidation truth.
        if state is not None:
            invalidated = set(state.get("invalidated_stages") or [])
            completed = set(state.get("completed_stages") or [])
            for stage in sorted(required & invalidated):
                failures.append(
                    _failure(
                        EVIDENCE_STAGE_INVALIDATED,
                        "required_stage_invalidated_in_state",
                        stage_id=stage,
                    )
                )
            for stage in sorted(completed & invalidated):
                failures.append(
                    _failure(
                        EVIDENCE_STAGE_INVALIDATED,
                        "stage_completed_and_invalidated",
                        stage_id=stage,
                    )
                )

        findings["failure_count"] = len(failures)
        return {"earned": not failures, "failures": failures, "findings": findings}


# Server-owned production roots. No WBP_PROJECT_ROOT / WBP_CONTROL_ROOT
# environment overrides: the project root is derived from the code
# location itself; the control root is a fixed operator path.
def production_project_root() -> Path:
    package_dir = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "-C", str(package_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return package_dir.parent


def production_control_root() -> Path:
    return (
        Path.home()
        / "Library"
        / "Application Support"
        / "WildBoarProxy"
        / "agent-control"
        / "WBP_MULTI_ACTOR_API_CLI_V1_1"
    )


def production_verifier() -> GateEvidenceVerifier:
    return GateEvidenceVerifier(
        project_root=production_project_root(),
        control_root=production_control_root(),
    )


__all__ = [
    "EVIDENCE_SCHEMA_INVALID",
    "EVIDENCE_DIGEST_MISMATCH",
    "EVIDENCE_COMMIT_UNREACHABLE",
    "EVIDENCE_STAGE_INVALIDATED",
    "EVIDENCE_CANDIDATE_MISMATCH",
    "RECEIPT_SCHEMA_VERSION",
    "REQUIRED_STAGES",
    "REQUIRED_RECEIPT_FIELDS",
    "GateEvidenceVerifier",
    "build_closeout_reference_receipt",
    "canonical_json_bytes",
    "execution_state_hash",
    "receipt_hash",
    "production_verifier",
]
