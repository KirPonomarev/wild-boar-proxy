<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R65 Security / Reliability Production-Path Matrix Closeout

## Goal

Re-prove B17 against the production workflow and web-control paths admitted by
R59-R64, and repair any concrete false-green evidence gap found by the matrix.

## Result

- status: implemented and locally verified
- final verdict: the matrix now runs 15 deterministic checks: 14 passed,
  1 honestly guarded (`codex_upgrade_invalidation_guard`), and 0 failed
- production repair: successful workflow receipts now preserve
  `dispatch_attempted`, `response_observed`, `fallback_used=false`, and
  `actor_substitution_used=false`; exception and invalid-result receipts also
  record absence of fallback/substitution
- production matrix coverage now includes:
  - canonical binding-revision drift rejection before adapter dispatch;
  - disabled-route fail-stop before provider dispatch and without fallback;
  - registry-bound two-step controlled workflow, independent dispatch receipts,
    visible context delivery, and repository-lease cleanup;
  - unauthorized live-mode rejection before credential probe/network dispatch;
  - loopback, token, origin, CSRF, rate-limit, browser-authority, writer-fencing,
    public-status redaction, secret-input, and restart boundaries
- no live provider call, credential read, Codex surface read, public release, or
  protected-network mutation was authorized or performed
- closure state: CLOSED

## Contour Capsule

- goal: R65 production-path security/reliability matrix and workflow receipt
  evidence repair
- branch: `codex/r65-security-reliability-production-matrix`
- head: exact base `aae8f1e77f2f170e06ae1597b6cb07c395d57fc4` plus the single logically complete R65 contour commit
- base: `aae8f1e77f2f170e06ae1597b6cb07c395d57fc4`
- tests run: focused matrix/workflow 20 passed; affected production workflow/web/transport 85 passed plus 7 subtests; `make check` collected 5111 tests; core 638 passed plus 141 subtests; custom stability 27 passed plus 5 subtests; web E2E 617 passed, 1 skipped, plus 95 subtests; full suite 5111 passed plus 997 subtests
- touched files:
  - `wild_boar_proxy/security_reliability_matrix.py`
  - `wild_boar_proxy/sequential_workflow_runner.py`
  - `tests/test_security_reliability_matrix.py`
  - `tests/test_workflow_api_dispatch.py`
  - `audit_results/R65_SECURITY_RELIABILITY_PRODUCTION_MATRIX_SPEC_2026-08-13.md`
  - `audit_results/R65_SECURITY_RELIABILITY_PRODUCTION_MATRIX_closeout_2026-08-13.md`
- risk size: M, runtime evidence/security boundary
- blocked risks: false-green no-fallback claims, identity drift, browser authority
  escalation, secret exposure, unauthorized live dispatch, lease leakage
- closure state: CLOSED

## Verification

- focused matrix + workflow dispatch: `20 passed in 16.72s`
- affected production workflow/web/transport set:
  `85 passed, 7 subtests passed in 18.69s`
- manual matrix packet: `15 checks`, `14 passed`, `1 guarded`, `0 failed`,
  `machine_error_code=OK`
- `make check`: compileall green; `5111 tests collected`
- `make test-core`: `638 passed, 141 subtests passed in 68.90s`
- `make test-custom-stability`: `27 passed, 5 subtests passed in 2.60s`
- `make test-web-e2e`: `617 passed, 1 skipped, 95 subtests passed in 127.77s`
- one material-contour full suite:
  `5111 passed, 1 warning, 997 subtests passed in 1168.19s`
- warning: pre-existing Pillow `Image.Image.getdata` deprecation in
  `tests/test_web_design_ui.py`; non-blocking and unrelated to R65

## Scope Check

- unrelated work mixed in: no
- runtime/live provider mutation: no
- credential values read or persisted: no
- primary Codex paths read or changed: no
- public release or protected-network action: no
- UI/design changes: no
- external execution state changed only by the separately fenced R64/B14
  checkpoint before this contour; no R65 close claim has been written externally
  before remote delivery

## Delivery

- local commit: this contour commit contains the implementation, tests, spec,
  and closeout as one logically complete change
- remote branch/PR/CI/merge: not claimed in this repository artifact; external
  delivery receipts remain authoritative

## Notes

- first focused failure localized a fixture that omitted the mandatory primary
  ChatGPT slot; adding the canonical primary slot restored registry validity
- second focused failure exposed the real public-receipt evidence gap repaired by
  this contour; the web unauthorized-case failure was a fixture truthiness bug
  and was corrected without changing production ingress
- resume from here: CLOSED
