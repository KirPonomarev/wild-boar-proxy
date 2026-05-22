<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# RUNTIME_INVARIANT_CHECK_AND_RECOVERY_HINTS_PASS Closeout

## Goal

Add a read-only runtime invariant check command that returns strict JSON,
machine-checks core runtime truth, rejects false-green evidence, and provides
sorted advisory recovery hints.

## Result

- status: `closed_success`
- final verdict: `RUNTIME_INVARIANT_CHECK_JSON_SURFACE_ADMITTED`
- command: `wild-boar-proxy invariant-check --json`
- next action: return to product track with
  `WEB_API_ROUTE_CREATE_OR_ADOPT_SERVER_OWNED_PASS` or real provider login
  callback work

## Contour Capsule

- goal:
  add read-only machine-checkable runtime invariants and recovery hints
- branch: `codex/external-agent-lab-isolated`
- base head: `d3d99d8`
- head: pending commit
- touched files:
  - `COMMAND_API.md`
  - `wild_boar_proxy/cli.py`
  - `wild_boar_proxy/runtime.py`
  - `tests/test_cli.py`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/spec.md`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/metrics.json`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/independent_audit.json`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/closeout.md`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/invariant-check-healthy.json`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/targeted-tests.txt`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/full-gate.txt`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/node-check-overview.txt`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/git-diff-check.txt`
- tests run:
  - targeted invariant-check unittest set: `Ran 13 tests ... OK`
  - full required gate: `Ran 658 tests ... OK`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - no remaining blocker in this contour
- next exact command:
  - choose and plan the next product contour from master-plan priority
- resume from here:
  - verify commit hash in this closeout after commit, then continue with
    `WEB_API_ROUTE_CREATE_OR_ADOPT_SERVER_OWNED_PASS` unless real provider login
    callback has priority

## Verification

- healthy owner proof:
  - `status=ok`
  - `machine_error_code=OK`
  - `invariant_result.status=passed`
  - `passed=8`
  - `failed=0`
  - `changed_files=[]`
- targeted failure proofs:
  - listener down
  - mode mismatch
  - bad account pool
  - missing managed path
  - malformed packet
  - false-green rejection
  - onboarding not reserve-first
  - ambiguous active routing
  - sorted recovery hints
  - unknown failure fallback hint
  - read-only runtime state proof

## Scope Check

- UI changed: `no`
- `STATE_SCHEMA.md` changed: `no`
- auto-recovery added: `no`
- runtime state writes added: `no`
- broad runtime refactor: `no`
- command API updated: `yes`

## Artifacts

- spec:
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/spec.md`
- metrics:
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/metrics.json`
- independent audit:
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/independent_audit.json`
- evidence:
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/invariant-check-healthy.json`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/targeted-tests.txt`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/full-gate.txt`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/node-check-overview.txt`
  - `audit_results/runtime_invariant_check_and_recovery_hints_pass_2026-05-22/evidence/git-diff-check.txt`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending
