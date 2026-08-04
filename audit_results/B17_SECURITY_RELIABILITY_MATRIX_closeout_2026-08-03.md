<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B17 Security / Reliability / Advanced-Capability / Upgrade Matrix Closeout

## Goal

Build the repository-native security and reliability matrix: run
deterministic local probes for fuzzing, malformed/large streams,
cancellation, corruption/recovery, binary and revision drift, auth expiry,
provider failures, injection/redaction, lease contention, app restart,
Codex upgrade invalidation guard, admitted advanced capabilities, and
protected-surface guards.

## Result

- status: implemented and verified
- final verdict: `security_reliability_matrix.py` runs 13 deterministic
  checks: 12 passed, 1 guarded (`codex_upgrade_invalidation_guard` —
  Codex state is never read under the owner safety override; the guard
  itself is the evidence). All checks are real probes against existing
  machinery (parsers, stream accumulator, one-shot runtime, ledger,
  repo-lease TTL, provider error taxonomy, redaction, qwen/kimi/glm
  slices, workflow receipts); guarded surfaces are reported as guarded,
  never simulated; the aggregate packet is strict and secret-free
- closure state: CLOSED

## Contour Capsule

- goal: B17 security/reliability matrix
- branch: `codex/b17-security-reliability-matrix`
- head: `f932b40d1bd26b8e7229995535ea1ffba363ad21` (base before contour commit)
- touched files: `wild_boar_proxy/security_reliability_matrix.py` (new),
  `tests/test_security_reliability_matrix.py` (new),
  `audit_results/B17_SECURITY_RELIABILITY_MATRIX_SPEC_2026-08-03.md`,
  `audit_results/B17_SECURITY_RELIABILITY_MATRIX_closeout_2026-08-03.md`
- tests run: `tests/test_security_reliability_matrix.py` (6); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: greenwashing matrix entries, Codex surface reads,
  secret leakage in matrix packets
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_security_reliability_matrix.py` -> `6 passed` (matrix
    passes all checks with 12 passed / 1 guarded; strict packet; Codex
    guard reported guarded without Codex reads; matrix fails closed when
    guard facts are violated; advanced-capability checks are real
    probes; no secrets in the packet)
  - manual run recorded: `status: ok`, 12 passed, 1 guarded, 0 failed
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - `run_security_reliability_matrix(main_codex_facts=...)` ->
    `MATRIX_OK`; guarded entry: `codex_upgrade_invalidation_guard`
    (owner safety override)
- live verification:
  - none; all checks are deterministic local probes

## Artifacts

- spec: `audit_results/B17_SECURITY_RELIABILITY_MATRIX_SPEC_2026-08-03.md`
- packet: matrix run recorded in this closeout (12 passed / 1 guarded)
- report: live-credential-dependent aspects (auth expiry of provider
  credentials, live provider failures) remain covered by the pending live
  gates; matrix covers the deterministic machinery

## Git

- branch: `codex/b17-security-reliability-matrix`
- commit: contour commit contains the matrix module, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (no Codex reads, no secrets in packets,
  guarded checks reported as guarded)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none beyond routine probe calibration (ledger
  entry kinds, stream_complete property, provider taxonomy values)
- resume from here: CLOSED
