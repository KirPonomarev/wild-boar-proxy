<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: STAGE20_C5_RESERVE_SEMANTICS_ADR

## Objective

Close reserve-semantics policy ambiguity without changing runtime behavior, so
the current mixed model is fixed explicitly and the proposed minimum-depth
model remains a documented future alternative rather than an implicit change.

## In Scope

- `ADR-0001-reserve-semantics-stage-proof.md`
- `audit_results/stage20_c5_spec.md`
- `audit_results/stage20_c5_decision_packet.json`
- `audit_results/stage20_c5_closeout_report.md`
- canon/doc review against current runtime/test behavior

## Out of Scope

- `wild_boar_proxy/runtime.py`
- `tests/test_cli.py`
- command-surface changes
- UI work
- live runtime work
- reserve-semantics implementation change

## Constraints

- repo-only docs/policy contour
- no live mutation
- no live read-only packet
- no runtime behavior change
- no silent test expectation rewrite

## Assumptions

- `STAGE20_C3_ROLLOUT_POSTURE_INSPECT` is closed
- current runtime truth uses a mixed reserve-semantics model
- external minimum-depth proposal remains unaccepted behavior

## Acceptance Criteria

- [ ] ADR exists and is internally consistent.
- [ ] Current mixed reserve semantics are explicitly fixed as current canon.
- [ ] Minimum-depth semantics are documented only as a future alternative.
- [ ] No code behavior change occurs.
- [ ] No tests are changed.
- [ ] The contour closes with an explicit next-contour decision.

## Verification

- docs:
  - ADR reviewed against canon order
  - closeout reviewed
- commands:
  - `git diff --check`
- manual:
  - confirm only docs/artifacts changed
  - confirm current runtime/test behavior matches the retained mixed canon
- live evidence:
  - none

## Open Questions

- If minimum-depth semantics are pursued later, is a pure behavior-change
  contour sufficient, or does the repo first need a wider lifecycle/schema
  design contour?
