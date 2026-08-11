<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R60B Web Readiness Budget Repair

## Objective

Prevent deterministic cold-start failure of the loopback web control surface
by binding each live-readonly HTTP readiness request to the remaining outer
startup budget instead of a fixed two-second timeout.

## In Scope

- eliminate retry amplification caused by abandoning a still-running
  live-readonly snapshot handler every two seconds;
- preserve the existing bounded startup deadline and full snapshot readiness
  semantics;
- add a regression test proving the per-request timeout cannot exceed the
  caller's startup budget;
- re-prove the real web lifecycle integration and repository test gates.

## Out of Scope

- changing snapshot content, command allowlists, UI, provider behavior,
  credentials, authentication, network or proxy settings, ports, release, or
  public publishing;
- weakening readiness to a listener-only or synthetic health claim;
- modifying the paused R60A evidence-guard checkpoint.

## Constraints

- the contour starts from exact merged `origin/main` commit
  `8ab0dcaae45ce1e57bd2b1e3e9d4604abab9d793`;
- loopback-only binding, PID ownership, orphan cleanup, and strict packet
  semantics remain unchanged;
- total startup time remains bounded by `startup_probe_timeout`;
- one branch, one worktree, one process, and no protected host-network
  mutations.

## Assumptions

- `/api/live-readonly` intentionally proves the complete read-only command
  snapshot rather than listener availability alone;
- a cold snapshot may legitimately exceed two seconds while remaining within
  the admitted 15-30 second startup window.

## Acceptance Criteria

- [ ] a readiness request receives no more than the remaining startup budget;
- [ ] a timed-out request cannot cause an unbounded extension beyond the
  original outer deadline;
- [ ] the real lifecycle integration passes from a clean child start;
- [ ] focused, core, custom-stability, full-suite, hygiene, diff, and closeout
  resilience verification pass on the final candidate.

## Verification

- tests: `tests/test_web_lifecycle.py` and
  `tests/test_web_lifecycle_integration.py`, followed by repository core,
  custom-stability, and full suites;
- build: `make check`;
- manual: one bounded real `web_start`/`web_stop` probe with exact cleanup;
- live evidence: local loopback integration only; no external provider call.

## Open Questions

- none; the deterministic failure packet and focused reproduction identify the
  hardcoded per-request timeout as the amplification boundary.
