<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Desktop HTML Renderer Admission And Passports

## Objective

Admit the provided design package as a visual baseline for the desktop
companion UI, choose the first renderer spike target, and create screen
passports before implementation.

This contour prepares the design lane. It does not build the live UI.

## In Scope

- Inspect the render package inventory.
- Record renderer target evidence.
- Create a render package manifest.
- Create a surface registry for all supplied screens.
- Create screen passports with command boundaries.
- Confirm the first implementation target.

## Out Of Scope

- Runtime or CLI behavior changes.
- Live command wiring.
- Command adapter implementation.
- Full visual implementation.
- `web_ui.py` changes.
- Broad `ui_shell.py` redesign.
- Packaging or installer work.
- Public web product work.

## Constraints

- The render package is visual baseline only, not runtime canon.
- UI truth must remain on strict JSON command surfaces.
- The renderer must not read state files or logs as truth.
- Deferred rollout and stage actions must stay deferred.
- `ui_shell.py` remains the fallback/control baseline.
- No dependency installation is allowed unless explicitly required for a
  renderer spike and recorded.

## Assumptions

- `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` has been earned.
- `UI_C3_RENDER_HANDOFF_CONTRACT` is closed.
- The supplied render package is the current visual reference.
- `01_overview_dashboard` is the correct first implementation target.

## Acceptance Criteria

- [x] Render package inventory is captured.
- [x] Renderer target evidence is documented.
- [x] Dependency installation status is recorded.
- [x] Every supplied screen has an admission status.
- [x] Implementation-target screens have passports.
- [x] `01_overview_dashboard` is confirmed as first implementation target.
- [x] `08_import_existing` remains deferred pending command support.
- [x] No runtime, CLI, `web_ui.py`, or `ui_shell.py` changes occur.

## Verification

- tests:
  - JSON artifacts parse with `python3 -m json.tool`.
- build:
  - not applicable; no product code was changed.
- manual:
  - Review artifacts against `UI_READINESS_SPEC.md` and `COMMAND_API.md`.
  - Confirm visual package is baseline only.
  - Confirm no direct state/log truth is admitted.
- live evidence:
  - none.

## Open Questions

- The next contour must prove whether `pywebview` can host the overview shell
  with acceptable visual parity before it becomes a locked packaging
  dependency.
