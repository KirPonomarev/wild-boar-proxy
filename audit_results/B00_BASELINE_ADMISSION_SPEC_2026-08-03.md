<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B00 Baseline Admission Repair

## Objective

Close the reproduced B00 baseline false-green findings at the exact current
head (`b4a9de07`) so the multi-actor plan can be admitted on a verified
baseline. Reproduce-first: each candidate finding is either
`REPRODUCED_AND_REPAIRED` with a regression test or
`NOT_REPRODUCED_ALREADY_CONTAINED` with evidence.

## In Scope

- F1: empty required-step set must not be accepted by the release E2E receipt
  and the desktop pilot receipt (`all([])` false-green) — guard + regression
  tests.
- F2: one SHA must not stand for multiple independent release milestones in
  the final assurance audit — distinctness guard + regression test.
- F3: tests must not touch protected ports `10808` / `12334` (payload strings
  and active probe candidates) and must not hardcode fixed ports in
  test-authored harness source — replace with non-protected dynamic values.
- F6: negative coverage for a fully missing required packet set in the
  GPT+API+DIP acceptance gate (`*_packet_missing` path).
- B00 closeout evidence with the `NOT_REPRODUCED_ALREADY_CONTAINED`
  classifications for the remaining candidate findings (evidence-level
  taxonomy naming → B03 input; provider catalog staging → B08 input).

## Out of Scope

- Evidence-level taxonomy renaming (plan `LIVE_PROVEN` /
  `PHYSICAL_VISIBLE_PROVEN` vs code `PHYSICAL_PROVEN`) — owned by B03
  (normalized transport and evidence state machine).
- Qwen provider integration — owned by B08.
- OpenRouter README documentation — carried to the B07 contract contour.
- Any production change to legacy local-proxy candidate discovery in
  `wild_boar_proxy/runtime.py` (product surface, unchanged).

## Constraints

- No change to canon files in this contour (`CANON.md`,
  `RUNTIME_CONTRACT.md`, `STATE_SCHEMA.md`, `COMMAND_API.md`,
  `DELIVERY_RULES.md`).
- New error codes must be stable tokens, documented in code, and carried by
  strict command packets that pass `inspect_command_packet_semantics`.
- Tests never bind, probe, or reference protected ports `10808` / `12334`.
- One writer, one branch, one PR; WIP = 1.

## Assumptions

- Milestone tags `v0.1.0`, `v0.2.0`, `v0.3.0` resolve to distinct existing
  commits, so the final-assurance synthetic proof keeps its completeness path
  under the new distinctness guard.
- Protected-port strings in test payload fixtures are data, but the plan
  forbids any test usage, so they are replaced too.

## Acceptance Criteria

- [ ] `build_release_e2e_receipt(steps=[])` returns a non-green packet
      (`RELEASE_E2E_EMPTY_STEP_SET`), never `WEB_RELEASE_V0_1_0_ACCEPTED`.
- [ ] `build_desktop_pilot_receipt(steps=[])` returns a non-green packet
      (`DESKTOP_PILOT_EMPTY_STEP_SET`), never `WBP_DESKTOP_PILOT_V0_3_0_RELEASED`.
- [ ] `run_final_assurance_audit` rejects identical SHAs for the three
      milestones (`FINAL_ASSURANCE_SHA_COLLISION`), never `WBP_MASTER_PLAN_V3_6_DONE`.
- [ ] No test file references `10808` / `12334`; no fixed port in
      test-authored harness source.
- [ ] Acceptance gate has a negative test for a fully missing required packet
      set.
- [ ] Focused, affected, and required wider checks pass; closeout evidence
      recorded; contour merged to `main`.

## Verification

- tests: repro tests fail before the fix, pass after; focused files; `make
  check`; `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  local full baseline `make test-full`.
- build: n/a (no packaging change).
- manual: n/a.
- live evidence: n/a (synthetic contract level only).

## Open Questions

- None blocking.
