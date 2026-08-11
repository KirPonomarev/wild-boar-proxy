<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R60D Web Dispatch Test Timeout Repair

## Objective

Make the representative GET dispatch/output test independent of loaded-runner
latency without changing the production custom-readonly timeout contract.

## In Scope

- preserve the failed R60C full-suite receipt without rerun;
- give the in-process custom-status request a test-only timeout budget suitable
  for a full-suite runner;
- retain the dedicated production-timeout tests unchanged;
- re-prove all repository gates on the combined R60C/R60D candidate tree.

## Out of Scope

- changing production timeout values, packet semantics, runtime, UI behavior,
  providers, credentials, host network settings, release, or publishing;
- modifying the paused R60A checkpoint or preserved R60B branch.

## Constraints

- the contour depends on the separately committed R60C head
  `576ab637d50a0885084f24d9032487e3977f3c68`, whose origin-main base is
  `8ab0dcaae45ce1e57bd2b1e3e9d4604abab9d793`;
- production code changes are forbidden;
- timeout failure behavior remains covered by the existing explicit
  `CUSTOM_CODEX_READONLY_TIMEOUT` tests;
- one branch, one worktree, and no protected host mutations.

## Failure Evidence

- fresh R60C `make test-full` failed
  `WebDesignRouteEffectRegistryTests::test_get_dispatch_table_preserves_representative_outputs`
  after `5065` passes and `985` passing subtests;
- the representative custom-status result was `integration_failure` instead
  of `ok` or `degraded`;
- focused reproduction passed in 2.84 seconds, proving load sensitivity rather
  than a deterministic dispatch-table mismatch;
- the failed full suite was not rerun.

## Acceptance Criteria

- [ ] only the representative custom-status request receives the expanded
  test budget;
- [ ] production timeout constants and behavior remain unchanged;
- [ ] exact focused test and explicit timeout tests pass;
- [ ] core, custom-stability, full-suite, hygiene, diff, and closeout
  resilience verification pass on the final candidate.

## Verification

- tests: the failed representative-output test plus explicit custom-readonly
  timeout tests, followed by repository core, custom-stability, and full suites;
- build: `make check`;
- manual: final diff proves test/spec/closeout-only scope across R60C/R60D;
- live evidence: local in-process HTTP server only; no external call.

## Open Questions

- none; production timeout behavior already has explicit deterministic tests,
  while this test's responsibility is dispatch and representative output.
