<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Min Review UI Actions

## Objective

Make the existing overview/right-panel surface practically usable for the
already-admitted review bridge actions without adding backend capability,
file-picker choreography, or renderer-owned mutation logic.

## In Scope

- add one bounded review bridge card to the overview UI
- wire `import_review_packet`, `apply_exact_text_change`, and
  `clear_review_session` through the existing review command surface
- render existing `/api/review-surface`, `/api/review-commands`, and command
  packet truth
- enforce live-only UI guards for command-triggering controls
- render blocked reasons and success receipts from packet truth
- add focused UI tests for the new surface

## Out of Scope

- file-picker or drag-and-drop review import
- renderer-side file IO
- backend command/schema expansion
- review import semantics changes
- exact-text apply semantics changes
- UI redesign or layout rewrite
- markdown confirmation work
- release wording or claim matrix work

## Constraints

- renderer mirrors packet/query truth only
- UI does not independently derive target identity or apply admission
- UI actions stay limited to `import/apply/clear`
- no direct renderer write path
- no backend drift into `CONTOUR_06+`

## Assumptions

- existing review endpoints remain authoritative:
  - `GET /api/review-surface`
  - `GET /api/review-commands`
  - `POST /api/review-command`
- bounded JSON review packet intake from `CONTOUR_02` stays the only admitted
  import path
- apply enablement from `CONTOUR_04` remains command-bus owned

## Acceptance Criteria

- [x] existing overview UI can trigger `import_review_packet`
- [x] existing overview UI can trigger `apply_exact_text_change`
- [x] existing overview UI can trigger `clear_review_session`
- [x] apply button state mirrors existing packet truth only
- [x] blocked reasons render from packet/query truth
- [x] success receipt renders from command packet truth
- [x] renderer has no direct-write path and no file-picker drift

## Verification

- tests:
  - bundled runtime `tests.test_web_design_ui`
  - bundled runtime `tests.test_review_bridge_live_server`
  - bundled runtime `tests.test_review_bridge_command_bus`
  - bundled runtime `tests.test_review_bridge_packet_import`
  - bundled runtime `tests.test_review_bridge_apply_admission`
  - bundled runtime `tests.test_web_design_live_server`
  - bundled runtime `tests.test_web_design_command_adapter`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - bundled runtime `python -m py_compile ...`
  - `git diff --check`
- manual:
  - local HTTP smoke against `wild_boar_proxy.web_design_live_server`
- live evidence:
  - bounded import, query refresh, and clear flow through review endpoints

## Open Questions

- behavioral browser/UI automation for live-only command guards is still absent
- behavioral UI automation for apply enablement across admitted vs blocked
  `apply_preflight` packets remains a follow-up hardening gap
