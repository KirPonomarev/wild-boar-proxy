<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI Final Onboarding Result Flow Transfer Spec

## Goal

Transfer the final onboarding result-flow surface into the web design UI without
changing the `onboard_account` command contract, browser payload shape, or
runtime truth source.

## Canon Boundary

- UI layer only.
- Existing `onboard_account` action only.
- Browser request remains `ui_action` only.
- No `auth_ref`, source path, password, backend selector, command argv, or raw
  adapter command can enter the browser request.
- Success is green only when the server-shaped onboarding summary is
  reserve-first and admitted.
- The result screen must not claim active routing, promotion, lifecycle success,
  or runtime truth.
- Validate/promote remain separate operator actions after onboarding.

## Scope

- Add a result-flow block to the existing action result surface.
- Render success, user-action-needed, command-error, and unknown result states.
- Show only safe metadata: `new_backend_ids`, `selected_backend_id`,
  `selection_status`, reserve proof, validate outcome, and sync outcome from the
  already-shaped action result.
- Update render package registry/passports for `09_onboarding_result_flow`.
- Add VM-backed DOM tests for the result renderer.

## Out Of Scope

- No standalone runtime screen.
- No desktop renderer work.
- No direct runtime/state/log file reads.
- No command adapter widening.
- No onboarding source/import/auth collection UI.
- No automatic account promotion.
- No private external reference research.

## Acceptance

- `onboardingResultFlow` is hidden until the latest action is
  `onboard_account`.
- Green state requires `ui_state=success`, `final_outcome=admitted`,
  `reserve_first_proven=true`, and `selected_backend_id`.
- Non-success states never display a selected backend as success.
- Copy says reserve-only and keeps promotion/validation separate.
- Existing web UI tests, live server tests, and command adapter tests pass.
- Browser smoke confirms the static page still loads at 1600x1000 and the
  result-flow is hidden before command truth.
- Independent audit reports no blocking finding.
