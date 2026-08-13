<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R62F Web Fetch Budget Repair

## Objective

Stop the test-only web fetch helper from amplifying a loaded-runner timeout into
multiple abandoned server requests while preserving one hard bounded deadline.

## In Scope

- use the remaining 15-second test deadline as each HTTP attempt's timeout;
- retain bounded retry for fast transient connection failures;
- add a deterministic regression for the initial remaining-budget value;
- preserve the failed R62 CI receipt and verify the repair independently.

## Out of Scope

- production web server, timeout, packet, UI, provider, or runtime changes;
- Kimi R62 implementation changes or a blind rerun of the failed candidate;
- credentials, external network calls, release, or publishing.

## Failure Evidence

- R62 push CI job `94297012226` failed two untouched web tests after their
  client-side three-second reads timed out;
- the abandoned handlers later raised `BrokenPipeError`, proving request
  amplification while the helper still had unused aggregate budget;
- the independent synthetic-merge web job passed the same source tree;
- Kimi-focused, core, custom-stability, local full-suite, and sandbox gates all
  passed and neither failed test intersects the R62 diff.

## Acceptance Criteria

- [x] the first request receives the full remaining 15-second budget;
- [x] fast transient failures may retry only inside the same hard deadline;
- [x] production code and production timeout behavior are unchanged;
- [x] focused web tests, core/custom gates, full suite, hygiene, diff, and
      closeout resilience pass before merge.

## Verification

- focused: budget regression and the two exact failed tests;
- repository: `make check`, `make test-core`, `make test-custom-stability`, and
  `make test-full`;
- live: local in-process HTTP only; no external service.

## Open Questions

- none.
