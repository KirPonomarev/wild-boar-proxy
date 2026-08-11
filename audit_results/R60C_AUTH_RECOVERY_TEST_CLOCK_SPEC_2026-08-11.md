<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R60C Auth Recovery Test Clock Repair

## Objective

Make the two login-session signal-selection tests independent of macOS runner
scheduling latency by controlling the grace clock and sleep they exercise.

## In Scope

- preserve both independent R60B full-suite failure receipts without rerun;
- make the process-group and PID-fallback tests use an explicit deterministic
  clock sequence;
- re-prove the focused auth-recovery surface and all repository test gates.

## Out of Scope

- changing runtime termination behavior, signal order, grace duration,
  process ownership, login behavior, UI, provider behavior, credentials,
  network settings, release, or public publishing;
- modifying the paused R60A checkpoint or the preserved R60B branch.

## Constraints

- the contour starts from exact merged `origin/main` commit
  `8ab0dcaae45ce1e57bd2b1e3e9d4604abab9d793`;
- runtime code changes are forbidden for this test-contract repair;
- the tests must continue proving process-group preference and PID fallback;
- one branch, one worktree, and no protected host mutations.

## Failure Evidence

- PR-event R5 full-suite run `31475448974` failed
  `test_terminate_login_session_pid_prefers_process_group_with_pid_fallback`
  after `5064` passes and `985` passing subtests;
- push-event R5 full-suite run `31475430104` failed the sibling
  `test_terminate_login_session_pid_falls_back_when_process_group_missing`
  after `5064` passes and `985` passing subtests;
- both tests unexpectedly reached the `SIGKILL` branch because their real
  0.2-second wall-clock grace expired before the mocked liveness sequence was
  consumed on loaded macOS runners;
- neither failing workflow was rerun.

## Acceptance Criteria

- [ ] both tests control `time.time` and `time.sleep` explicitly;
- [ ] their assertions still prove exact signal selection and fallback order;
- [ ] no production file changes;
- [ ] focused, core, custom-stability, full-suite, hygiene, diff, and closeout
  resilience verification pass on the final candidate.

## Verification

- tests: the two exact failed tests, the complete auth-recovery file, then
  repository core, custom-stability, and full suites;
- build: `make check`;
- manual: inspect the final diff to prove test/spec/closeout-only scope;
- live evidence: not applicable; no process signal or provider call is needed.

## Open Questions

- none; two independent exact-candidate runs produced sibling failures with
  the same uncontrolled-clock signature.
