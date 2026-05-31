<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Web Setup Import Surface Admission Foundation Pass

## Objective

Expose a minimal admitted web packet surface for the setup/import branch so the
web layer can represent one bounded preview/discovery lane and one bounded
import-capable lane without enabling runtime execution, confirm semantics, or
UI workflow expansion.

## In Scope

- add admitted `ui_action` metadata entries for `setup_discovery` and
  `legacy_import`
- keep both surfaces unavailable in live, sandbox, and full phases
- return machine-readable unavailable packets for both actions
- prove no runtime command execution happens for these new actions
- update live-server tests from `absent` to `present but blocked`

## Out of Scope

- command adapter entries for `installer_init` or `legacy_import`
- runtime bridge execution
- setup/select-client/import-existing UI changes
- confirm semantics
- collision handling
- final import success semantics
- markdown/parser/domain expansion

## Constraints

- admitted web packet path only
- zero runtime mutation
- no UI widening
- no command-envelope redesign
- no static-preview teardown beyond server metadata truth

## Assumptions

- `/api/actions` and `/api/action` are sufficient to prove the admitted web
  surface for this contour
- the next contour still owns confirm/cancel/collision honesty
- keeping these surfaces unavailable across all phases is acceptable for a
  foundation-only contour

## Acceptance Criteria

- [x] `setup_discovery` is present in web action metadata as a blocked
  foundation preview/discovery surface
- [x] `legacy_import` is present in web action metadata as a blocked
  foundation import-capable surface
- [x] `run_ui_action()` returns unavailable packets with `changed_files=[]` for
  both actions
- [x] no command adapter or runtime bridge execution path is enabled
- [x] setup/import UI remains static-only

## Verification

- tests:
  - `tests.test_web_design_live_server` via inline `unittest` launcher with an
    ephemeral `tkinter` stub because the local Python lacks `_tkinter`
  - `tests.test_web_design_ui` via inline `unittest` launcher with an
    ephemeral `PIL.Image` stub backed by PNG parsing because the local Python
    lacks Pillow
- build:
  - `python3 -m py_compile wild_boar_proxy/web_design_live_server.py tests/test_web_design_live_server.py`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- manual:
  - not run
- live evidence:
  - unavailable packets for `setup_discovery` and `legacy_import`

## Open Questions

- whether the future `CONTOUR_06` should attach explicit confirm to
  `legacy_import` directly or introduce a narrower setup/import follow-up action
