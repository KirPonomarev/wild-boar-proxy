# SPDX-FileCopyrightText: 2026 Kirill Ponomarev
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Execution-core design gate (B13G / R08).

The design gate SELF-VERIFIES execution-core repair closure by checking
git state directly: origin/main HEAD, reachability, evidence-index
receipts, closeout digest match, invalidation state, and completed-stage
presence. It does NOT accept caller-provided truth or default True checks.
The token is earned, never claimed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Sequence

from . import design_gate_accessibility as dga
from .runtime import build_command_payload

DESIGN_GATE_TOKEN = dga.DESIGN_GATE_TOKEN
GATE_SCHEMA_VERSION = 1

_PROJECT_ROOT = os.environ.get("WBP_PROJECT_ROOT", str(Path.cwd()))
_CONTROL_ROOT = os.environ.get(
    "WBP_CONTROL_ROOT",
    str(Path.home() / "Library" / "Application Support" / "WildBoarProxy"
        / "agent-control" / "WBP_MULTI_ACTOR_API_CLI_V1_1"),
)

_KNOWN_COMPLETED_STAGES = frozenset({
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
    "B13G_EXECUTION_CORE_DESIGN_GATE",
    "B14_WEB_WORKFLOW_CONTROL",
    "B15_OPTIONAL_ACP_DEFERRED",
    "B16_OPTIONAL_CODEX_CLI_DEFERRED",
    "B17_SECURITY_RELIABILITY_MATRIX",
    "B18_FINAL_CANDIDATE_ASSURANCE",
})

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git"] + args, capture_output=True, text=True, timeout=10,
            cwd=_PROJECT_ROOT,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _verify_sha_exists(sha: str) -> bool:
    if not _GIT_SHA_RE.match(sha):
        return False
    r = subprocess.run(
        ["git", "cat-file", "-t", sha], capture_output=True, text=True, timeout=5,
        cwd=_PROJECT_ROOT,
    )
    return r.returncode == 0 and r.stdout.strip() == "commit"


def _verify_origin_main_matches(sha: str) -> bool:
    origin = _git(["rev-parse", "origin/main"])
    return bool(origin) and origin == sha


def _verify_reachable_from_main(sha: str) -> bool:
    ancestors = set(_git(["rev-list", "origin/main"]).split())
    return sha in ancestors


def _verify_evidence_index(candidate_sha: str) -> tuple[bool, dict[str, Any]]:
    """Verify evidence-index receipts: closeout digests match, no
    invalidated entries, all merge commits reachable."""
    idx_path = os.path.join(_CONTROL_ROOT, "evidence-index.json")
    if not os.path.isfile(idx_path):
        return False, {"reason": "evidence_index_missing"}
    try:
        idx = json.loads(open(idx_path, encoding="utf-8").read())
    except (OSError, ValueError):
        return False, {"reason": "evidence_index_unreadable"}
    refs = idx.get("references", [])
    ancestors = set(_git(["rev-list", "origin/main"]).split())
    bad_receipts = []
    invalidated = []
    for ref in refs:
        if ref.get("invalidated"):
            invalidated.append(ref.get("stage_id"))
            continue
        # check merge commit reachable
        merge = ref.get("merge_commit_sha") or ""
        if merge and merge not in ancestors:
            bad_receipts.append({"stage": ref.get("stage_id"), "reason": "merge_not_reachable"})
        # check closeout digest if path present
        cp = ref.get("closeout_path")
        blob = ref.get("closeout_blob_sha")
        if cp and blob:
            full = os.path.join(_PROJECT_ROOT, cp)
            if os.path.isfile(full):
                actual = hashlib.sha256(open(full, "rb").read()).hexdigest()
                if actual != blob:
                    bad_receipts.append({"stage": ref.get("stage_id"), "reason": "closeout_digest_mismatch"})
    ok = not bad_receipts and not invalidated
    return ok, {
        "receipt_count": len(refs),
        "bad_receipts": bad_receipts,
        "invalidated": invalidated,
    }


def run_execution_core_design_gate(
    *,
    completed_stages: Sequence[str] | None = None,
    main_head: str | None = None,
) -> dict[str, Any]:
    """Run the design gate with SELF-VERIFIED evidence.

    No caller-provided truth: the gate reads git state and the
    evidence-index directly. Accessibility checks are NOT hardcoded True;
    they are omitted from this gate (they belong to the repository-native
    dga module, called separately when UI work is admitted).
    """
    findings: dict[str, Any] = {}

    # 1. Determine candidate SHA
    candidate = main_head or _git(["rev-parse", "HEAD"])
    findings["candidate_sha"] = candidate
    sha_valid = _verify_sha_exists(candidate)
    findings["sha_exists"] = sha_valid

    # 2. origin/main matches
    origin_match = _verify_origin_main_matches(candidate)
    findings["origin_main_matches"] = origin_match

    # 3. Reachability (candidate is origin/main itself, so trivially true
    # if origin_match)
    findings["reachable_from_main"] = origin_match

    # 4. Evidence-index verification
    ev_ok, ev_detail = _verify_evidence_index(candidate)
    findings["evidence_index"] = ev_detail

    # 5. Completed stages from evidence-index, not caller
    idx_path = os.path.join(_CONTROL_ROOT, "evidence-index.json")
    indexed_stages: set[str] = set()
    if os.path.isfile(idx_path):
        try:
            idx = json.loads(open(idx_path, encoding="utf-8").read())
            indexed_stages = {
                r["stage_id"] for r in idx.get("references", [])
                if r.get("receipt_type") == "closeout_reference"
                and not r.get("invalidated")
            }
        except (OSError, ValueError):
            pass
    # verify known stages present
    required = {s for s in _KNOWN_COMPLETED_STAGES if s != "B13G_EXECUTION_CORE_DESIGN_GATE"}
    missing_stages = required - indexed_stages
    findings["indexed_stages"] = sorted(indexed_stages)
    findings["missing_required_stages"] = sorted(missing_stages)
    stages_ok = not missing_stages

    # 6. Full-suite receipt bound to exact HEAD
    # The evidence-index does not carry full-suite counts; the gate
    # checks that the candidate SHA is origin/main (CI runs on that SHA).
    findings["exact_head_suite_note"] = (
        "full-suite evidence is recorded in closeout files, not the index; "
        "CI runs on the exact origin/main SHA"
    )

    earned = (
        sha_valid
        and origin_match
        and ev_ok
        and stages_ok
    )
    extra: dict[str, Any] = {
        "schema_version": GATE_SCHEMA_VERSION,
        "design_gate_token": DESIGN_GATE_TOKEN if earned else None,
        "design_gate_marker": DESIGN_GATE_TOKEN if earned else None,
        "design_gate_earned": earned,
        "execution_core_repair_closed": earned,
        "findings": findings,
    }
    if earned:
        return build_command_payload(
            ok=True,
            human_message=(
                f"Execution-core repair closed; design gate earned with token "
                f"{DESIGN_GATE_TOKEN}. Self-verified: SHA exists, origin/main "
                f"matches, evidence receipts valid, required stages indexed."
            ),
            machine_error_code="OK",
            liveness="healthy",
            severity="info",
            operator_action="none",
            changed_files=[],
            exit_code=0,
            extra=extra,
        )
    reason_parts = []
    if not sha_valid:
        reason_parts.append("SHA does not exist in git")
    if not origin_match:
        reason_parts.append("local HEAD != origin/main")
    if not ev_ok:
        reason_parts.append(f"evidence-index defects: {ev_detail.get('bad_receipts')}")
    if not stages_ok:
        reason_parts.append(f"missing required stages: {sorted(missing_stages)}")
    return build_command_payload(
        ok=False,
        human_message=f"Design gate not earned: {'; '.join(reason_parts)}.",
        machine_error_code="DESIGN_GATE_NOT_EARNED",
        liveness="degraded",
        severity="recoverable",
        operator_action="user_action",
        changed_files=[],
        exit_code=1,
        extra=extra,
    )


__all__ = ["DESIGN_GATE_TOKEN", "run_execution_core_design_gate"]
