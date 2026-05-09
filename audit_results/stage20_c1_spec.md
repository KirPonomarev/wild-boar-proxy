<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: STAGE20_C1_RESEARCH_CLEANUP_CANON

## Objective

Bring the external Stage20 research bundle into a truthful repo-local form
before any execution-core code adoption begins.

This contour does not port behavior changes yet.
It closes only the documentation and adoption-truth boundary:

- what the external bundle actually proves
- what can be adopted safely
- what must remain ADR-only
- what must be rejected as-is

## In Scope

- repo-local assessment of the external Stage20 research bundle
- truthful applicability status for both the original and reworked external
  patch bundles
- corrected adoption matrix
- repo-local adoption specification
- corrected machine-readable manifest for our internal handoff layer
- explicit reserve-semantics ADR boundary
- contour artifacts for spec, decision packet, and closeout

## Out of Scope

- `wild_boar_proxy/runtime.py` behavior changes
- `wild_boar_proxy/cli.py` changes
- test changes outside repo-local truth validation
- UI work
- live mutation
- reserve-semantics implementation

## Constraints

- repo-only contour
- no live mutation
- no engine-layer work
- must follow canon order:
  `CANON.md -> MASTER_PLAN.md -> RUNTIME_CONTRACT.md -> STATE_SCHEMA.md -> COMMAND_API.md -> DELIVERY_RULES.md -> README.md`
- local-only truth is not sufficient closeout; contour must end with commit,
  push, and closeout

## Assumptions

- current target branch is `codex/wave-1c-prereq-closeout`
- current target commit for external bundle review is `701774c`
- repo-local adopted truth should prefer verified local replay over downloaded
  bundle narrative
- the external bundle remains useful source material even when parts of its
  claims are not reproducible against the real target

## Acceptance Criteria

- [ ] Repo-local docs clearly state that the original external patch does not
      apply cleanly to the real target.
- [ ] Repo-local docs clearly state that the reworked external adoption patch is
      not verified as clean-apply against the real target.
- [ ] Repo-local docs do not repeat the disproven claim that two baseline
      `tests.test_cli` failures exist on clean `701774c`.
- [ ] Repo-local docs keep reserve minimum-depth semantics in ADR-only status.
- [ ] Repo-local docs explicitly separate:
      `TAKE NOW`, `ADR ONLY`, and `REJECT AS-IS`.
- [ ] Contour artifacts are written and verified.

## Verification

- tests:
  - `python3 -m unittest tests.test_cli.CliTests.test_accounts_onboard_detected_new_auth_status_failure_does_not_claim_success tests.test_cli.CliTests.test_healthcheck_auto_reconciles_to_healthy_stable_when_listener_is_live`
- build:
  - none
- manual:
  - `git apply --check` against clean `701774c` worktrees for the external
    adoption patch
  - document review of downloaded bundle vs repo-local findings
  - independent fact-check by spawned audit agent
- live evidence:
  - none; this contour is repo-only

## Open Questions

- Should the repo-local adopted output contract later move from `audit_results/`
  into a more permanent docs/governance location?
- Should the later `STAGE20_C5_RESERVE_SEMANTICS_ADR` reuse the external ADR
  draft directly or rewrite it from repo-local wording?
