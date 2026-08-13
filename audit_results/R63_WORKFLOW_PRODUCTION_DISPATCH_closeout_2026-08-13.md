<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R63 Workflow Production Dispatch Closeout

## Goal

Replace B13's fake-only dispatch claim with a registry-bound API workflow
execution path that transfers bounded visible context, preserves exact actor
identity, ambiguity, and repo-lease semantics, and denies live provider work
without explicit authorization.

## Result

- status: implementation and deterministic verification complete
- final verdict: PASS for R63 production workflow code; no live provider call was performed or claimed
- closure state: CLOSED

## Contour Capsule

- goal: connect the sequential workflow runner to the canonical registry and API transport boundary with proven visible context delivery
- branch: `codex/r63-workflow-production-dispatch`
- head: exact base `60e0b5cf85886c2c427403ac32cb9230389f4471` plus the single logically complete R63 contour commit
- touched files: `RUNTIME_CONTRACT.md`; R63 spec, ADR, and closeout; `tests/test_gate_evidence_bundle_v2.py`; `tests/test_sequential_workflow_runner.py`; `tests/test_workflow_api_dispatch.py`; `wild_boar_proxy/gate_evidence_bundle_v2.py`; `wild_boar_proxy/sequential_workflow_runner.py`; `wild_boar_proxy/workflow_api_dispatch.py`
- tests run: focused workflow/evidence 51 passed; broader registry/dispatcher/transport/workflow integration 140 passed plus 7 subtests; `make check` collected 5102 tests; core 638 passed plus 141 subtests; custom-stability 27 passed plus 5 subtests; full suite 5102 passed plus 994 subtests
- blocked risks: web control wiring, real credential presence, and live provider dispatch were not authorized or performed; existing live gates remain pending
- closure state: CLOSED

## Verification

- tests: focused `51 passed in 15.89s`; broader integration `140 passed, 7 subtests passed in 17.90s`; core `638 passed, 141 subtests passed in 85.44s`; custom stability `27 passed, 5 subtests passed in 3.00s`; full suite `5102 passed, 1 warning, 994 subtests passed in 1364.13s`
- build: `make check` compiled the tree and collected 5102 tests
- manual: exact registry/step identity matching, normalized request construction, controlled/live evidence separation, visible-context digest proof, redaction and bounds, ambiguity, no fallback, and all terminal lease-release paths were reviewed; `git diff --check` passed
- live verification: not performed; live mode was exercised only with a deterministic transport double after an explicit test authorization fact, and missing authorization/credentials were proven to stop before provider network

## Artifacts

- spec: `audit_results/R63_WORKFLOW_PRODUCTION_DISPATCH_SPEC_2026-08-13.md`
- packet: deterministic workflow receipts generated only beneath temporary test roots
- report: `audit_results/ADR_R63_WORKFLOW_VISIBLE_CONTEXT_2026-08-13.md`

## Git

- branch: `codex/r63-workflow-production-dispatch`
- commit: single logically complete R63 implementation, contract, regression, and closeout commit
- pushed: subject to exact remote branch readback and required CI before merge

## Scope Check

- unrelated work mixed in: no; the contour changes execution-core workflow dispatch, its contract/evidence guard, and direct regressions only
- private-data risk reviewed: yes; credentials are not read, live dispatch is authorization-gated, output/context is redacted and bounded, receipts persist only context proof facts, and raw exceptions are not exposed

## Notes

- blockers encountered: the first new fixture omitted the mandatory primary slot and correctly failed registry validation; a later negative test exposed a missing explicit `live_provider_called=false` field in terminal workflow receipts, which was added without weakening the pre-network credential stop
- resume from here: CLOSED
