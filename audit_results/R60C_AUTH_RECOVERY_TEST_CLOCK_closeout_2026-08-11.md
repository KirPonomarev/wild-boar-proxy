<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R60C Auth Recovery Test Clock Repair Closeout

## Goal

Remove loaded-runner timing dependence from two login-session signal-selection
tests without changing production termination behavior.

## Result

- status: test-contract repair complete and verified on the combined R60C/R60D candidate tree
- final verdict: R60C_AUTH_RECOVERY_TEST_CLOCK_REPAIR_CODE_COMPLETE
- closure state: CLOSED

## Contour Capsule

- goal: control grace clock and sleep in the process-group preference and PID-fallback tests while preserving their exact signal-order assertions
- branch: codex/r60c-auth-recovery-test-clock
- head: 576ab637d50a0885084f24d9032487e3977f3c68
- touched files: tests/test_runtime_native_auth_recovery.py, audit_results/R60C_AUTH_RECOVERY_TEST_CLOCK_SPEC_2026-08-11.md, audit_results/R60C_AUTH_RECOVERY_TEST_CLOCK_closeout_2026-08-11.md
- tests run: 2 exact failed tests; 23 auth-recovery tests; 630 core tests and 132 subtests; 27 Custom stability tests and 5 subtests; final combined-tree 5066 full-suite tests and 985 subtests
- blocked risks: none; runtime files and production signal/grace semantics were not changed
- closure state: CLOSED

## Verification

- tests: exact sibling regressions passed 2 tests in 0.16 seconds; the auth-recovery file passed 23 tests in 0.17 seconds; final combined-tree `make test-full` passed 5066 tests and 985 subtests in 1595.16 seconds
- build: `make check` collected 5066 tests; final combined-tree core passed 630 tests and 132 subtests in 94.45 seconds; Custom stability passed 27 tests and 5 subtests in 6.61 seconds
- manual: diff inspection proved clock/sleep mocks are limited to the two signal-selection tests
- live verification: not applicable; no real process was signalled and no provider or external network call occurred

## Artifacts

- spec: `audit_results/R60C_AUTH_RECOVERY_TEST_CLOCK_SPEC_2026-08-11.md`
- packet: PR run `31475448974` and push run `31475430104` preserve the two sibling unexpected-SIGKILL failures
- report: external execution-state revisions 96 and 97 bind candidate invalidation, isolated contour creation, focused proof, and the unrelated later R60D dependency

## Git

- branch: codex/r60c-auth-recovery-test-clock
- commit: 576ab637d50a0885084f24d9032487e3977f3c68 contains the test-clock repair and spec
- pushed: delivered as the first atomic commit in the dependent R60D candidate branch after final verification

## Scope Check

- unrelated work mixed in: false; the R60C commit changes only two auth-recovery tests and its spec
- private-data risk reviewed: no secrets, credentials, runtime state, host settings, UI, release, or provider surfaces were accessed or changed

## Notes

- blockers encountered: two independent R60B CI runs failed sibling tests because real 0.2-second wall-clock grace expired before mocked liveness; the first repaired full suite later exposed a separate web test timeout, isolated as R60D
- resume from here: CLOSED
