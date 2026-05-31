# UI Web First Screen Live Overview Completion

Date: 2026-05-12

Contour ID: `UI_WEB_FIRST_SCREEN_LIVE_OVERVIEW_COMPLETION`

## Goal

Make the first web overview useful in live read-only mode by separating primary
overview truth from detail and rollout evidence.

## Layer Rules

- Primary overview truth: `status`, `mode_get`, `accounts_list`.
- Runtime detail evidence: `healthcheck`.
- Rollout evidence: `rollout_rotation_inspect`.
- Primary command failure is fatal for the overview.
- Detail evidence failure is visible as warning/degraded detail.
- Rollout evidence failure is visible as warning, not runtime availability.
- Browser still cannot submit command IDs.
- Action buttons remain disabled.
- No desktop transfer.

## Out Of Scope

- Runtime-core edits.
- Button/action wiring.
- Accounts screen implementation.
- Full visual polish.
- Desktop shell work.
