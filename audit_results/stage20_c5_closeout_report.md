<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# STAGE20_C5_RESERVE_SEMANTICS_ADR Closeout

## Goal

Close reserve-semantics policy ambiguity without changing runtime behavior, so
current canon matches real repo behavior and the proposed minimum-depth model
remains a future alternative rather than a silent behavior change.

## Result

- status: completed
- final verdict: `GO_STAGE20_C6_FINAL_VERIFICATION_AND_UI_GATE`
- next action: open `STAGE20_C6_FINAL_VERIFICATION_AND_UI_GATE`

## Verification

- docs:
  - ADR reviewed against current runtime and tests
  - `STATE_SCHEMA.md` updated to reflect mixed current reserve semantics
  - `COMMAND_API.md` updated to reflect mixed current reserve semantics
- commands:
  - `git diff --check`
  - observed result: passed
  - `git diff --name-only --diff-filter=ACM`
  - observed result: `COMMAND_API.md`, `STATE_SCHEMA.md`
- manual:
  - code behavior remained unchanged
  - no tests changed
  - no runtime files changed
  - minimum-depth semantics stayed documented as future alternative only
- live verification:
  - none; repo-only contour

## Artifacts

- ADR:
  - `ADR-0001-reserve-semantics-stage-proof.md`
- spec:
  - `audit_results/stage20_c5_spec.md`
- packet:
  - `audit_results/stage20_c5_decision_packet.json`
- report:
  - `audit_results/stage20_c5_closeout_report.md`

## Independent Audit

- auditor: `Mendel`
  - identified the initial contradiction:
    - stage proof and stage-advance postflight enforce exact reserve alignment
    - promotion already uses reserve-floor semantics
  - confirmed current canon docs were ambiguous before alignment
- auditor: `Halley`
  - initial verdict: `STOP_AND_DIAGNOSE` on the false uniform exact-count claim
  - final verdict: `SAFE` after ADR and canon docs were revised to document the
    mixed current model truthfully

## Git

- branch: `codex/stage20-c5-reserve-semantics-adr`
- commit: `a52a7da` (primary artifact commit)
- pushed: yes
- pull request: `#39` draft, targeting `codex/stage20-c3-rollout-posture-inspect`

## Scope Check

- unrelated work mixed in: no
- runtime behavior changed: no
- runtime data committed: no
- tests changed: no

## Notes

- This contour did not adopt minimum-depth semantics.
- This contour did not change execution-core behavior.
- This contour resolved ambiguity by aligning canon docs with the mixed current
  repo behavior:
  - promotion uses reserve-floor semantics
  - stage proof and stage-advance postflight use exact reserve alignment
