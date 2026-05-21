<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Reserve Semantics In Stage Proof And Stage Advance

## Status

Accepted

## Date

2026-05-09

## Context

Stage20 research surfaced a real policy ambiguity: should `reserve_target`
express an exact reserve count, or only a minimum reserve depth?

Current repo behavior is mixed:

- `rollout stage prove` blocks when
  `reserve_pool_count_observed != reserve_target`.
- stage-advance postflight currently expects
  `reserve_pool_count_after == reserve_target`.
- `accounts promote` blocks when promotion would drop reserve below the staged
  target.
- tests already encode those exact behaviors as canonical current behavior.

External research proposed a minimum-depth alternative:

- `active_count == active_target`
- `reserve_count >= reserve_target`

That may be a valid future direction, but adopting it would be a behavioral and
contract change across proof packets, postflight verification, policy checks,
tests, docs, and later UI interpretation. It is too expensive to reverse to
merge as an incidental side effect of Stage20 execution-core repair.

## Decision

The current mixed reserve semantics remain the accepted canon.

For the current system:

- active-window alignment remains exact against stage policy
- promotion reserve safety remains floor-based
- stage proof and stage-advance postflight reserve posture remain exact against
  stage policy
- no minimum-depth reserve semantics are adopted in runtime behavior
- no tests are rewritten to imply minimum-depth semantics

The minimum-depth model is retained only as a documented alternative for a
future dedicated behavior-change contour.

Any future move to minimum-depth semantics requires:

1. a separate accepted contour after this ADR
2. explicit command-surface updates
3. targeted runtime/test/doc changes
4. no mixing with UI or unrelated execution-core work

## Alternatives Considered

1. Keep the current mixed model as current canon.
   Chosen. It matches current runtime behavior, current tests, and current
   docs once canon wording is clarified explicitly.
2. Adopt minimum-depth semantics immediately.
   Not chosen. It would be a real behavior change across stage proof,
   stage-advance postflight, promote policy checks, tests, docs, and UI-facing
   interpretation.
3. Split active-window and reserve-depth into separate explicit fields first.
   Not chosen in this contour. It may be cleaner long-term, but it is larger
   than the current Stage20 adoption scope and belongs to a separate design and
   implementation contour.

## Consequences

- Positive:
  - current code, tests, and canon become aligned explicitly
  - UI gate is not blocked by reserve-semantics ambiguity
  - future minimum-depth work stays possible without being silently merged now
- Negative:
  - current mixed model remains conceptually awkward
  - exact stage-proof/postflight reserve posture remains strict and may
    continue to flag surplus reserve as posture drift
  - some operational pain identified by external research remains deferred
- Follow-up work:
  - if the team wants minimum-depth semantics later, open a separate repo-owned
    behavior-change contour
  - if a broader lifecycle model is wanted, consider explicit separation of
    active window, reserve depth, and managed inventory in a later design contour

## Evidence

- spec:
  - `audit_results/stage20_c5_spec.md`
- tests:
  - `tests/test_cli.py` reserve-posture mismatch and promote-policy checks
- supporting code:
  - `wild_boar_proxy/runtime.py` stage-proof reserve equality check
  - `wild_boar_proxy/runtime.py` stage-advance postflight reserve equality check
  - `wild_boar_proxy/runtime.py` promote reserve-floor check
- supporting docs:
  - `audit_results/external_stage20_research_assessment.md`
  - `audit_results/external_stage20_research_adoption_tz.md`
  - `STATE_SCHEMA.md`
  - `COMMAND_API.md`
  - downloaded external `ADR-0001-reserve-semantics-stage-proof.md` used as
    source material only
