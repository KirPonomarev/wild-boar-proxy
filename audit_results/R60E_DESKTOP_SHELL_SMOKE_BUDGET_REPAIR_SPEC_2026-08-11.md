<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R60E Desktop Shell Smoke Budget Repair

## Objective

Make the bounded desktop web-shell smoke reliable under full-suite CI pressure
without changing the production server, endpoint, authorization, or packet
contracts.

## In Scope

- preserve both failed PR #149 full-suite receipts without rerun;
- replace independent three-second smoke request limits with one shared,
  decreasing 30-second total smoke deadline;
- add deterministic proof that every sequential smoke request receives only
  the remaining portion of that deadline;
- re-prove all repository gates on the combined R60C/R60D/R60E candidate.

## Out of Scope

- production web-server request semantics, provider calls, credentials, host
  network settings, UI behavior, release, or publishing;
- the preserved R60B runtime candidate and paused R60A checkpoint.

## Constraints

- the contour starts from exact remote branch head
  `9f9584da2cc24a7e874d6e2a4f9cfdf13362fa52`;
- the smoke remains loopback-only and fail-closed;
- the aggregate request sequence remains bounded by one deadline instead of
  multiplying a timeout across six requests;
- no failed workflow rerun; a code change must produce a new candidate SHA.

## Failure Evidence

- push workflow `31482653837` failed the relocated packaged web-shell smoke
  after `5063` passes and `985` passing subtests;
- pull-request workflow `31482673959` independently failed the explicit-full
  desktop web-shell smoke with `TimeoutError: timed out`, also after `5063`
  passes and `985` passing subtests;
- both paths use the same hardcoded three-second smoke HTTP timeout;
- focused local reproduction passed in 5.24 seconds, proving load sensitivity;
- neither failed workflow was rerun.

## Acceptance Criteria

- [ ] all six sequential smoke HTTP operations consume one decreasing total
  budget;
- [ ] deadline exhaustion remains a fail-closed smoke error;
- [ ] server, authorization, action phase, and packet semantics are unchanged;
- [ ] focused desktop-shell and relocated-package smoke tests pass;
- [ ] check, core, custom-stability, full-suite, diff, and closeout resilience
  verification pass on the final candidate.

## Verification

- tests: deterministic remaining-budget test, desktop-shell test file, and the
  failed relocated-package test, followed by repository suites;
- build: `make check`;
- manual: inspect the final diff and confirm cleanup still executes in
  `finally`;
- live evidence: local loopback smoke only; no external provider call.

## Open Questions

- none; 30 seconds matches the existing bounded startup-class workload while
  remaining a single aggregate deadline.
