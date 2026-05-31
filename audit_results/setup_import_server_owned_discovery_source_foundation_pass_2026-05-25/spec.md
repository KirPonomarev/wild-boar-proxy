<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Setup Import Server-Owned Discovery Source Foundation Pass

## Objective

Expose one bounded server-owned discovery source for `setup_discovery` so the
web setup/import branch can emit minimal packet truth (`none`, `discovered`, or
`blocked`) without browser path intake, selection semantics, session
materialization, or import execution.

## In Scope

- reuse existing `/api/action` + `setup_discovery`
- compute discovery truth from current server-owned runtime layout only
- keep `legacy_import` unavailable
- return zero-write packets for `none` and `discovered`
- block relative or otherwise non-absolute runtime target paths
- prove no runner execution happens for `setup_discovery`

## Out of Scope

- target/session token materialization
- selection persistence
- explicit confirm
- cancel semantics
- final import execution
- command-adapter entries for `installer_init` or `legacy_import`
- UI wiring changes

## Constraints

- source-only contour
- packet semantics stay minimal
- browser path/source payload remains forbidden
- no runtime mutation
- no command-envelope redesign

## Assumptions

- current server-owned runtime layout from `RuntimePaths.from_env()` is an
  admitted narrow owned source for this contour
- known owned file markers are sufficient to distinguish `none` vs
  `discovered`
- keeping `legacy_import` parked is required for scope integrity

## Acceptance Criteria

- [x] `setup_discovery` is available as a zero-write local packet lane
- [x] `setup_discovery` returns `none` when the owned runtime layout has no
  known markers
- [x] `setup_discovery` returns `discovered` when the owned runtime layout is
  initialized
- [x] `setup_discovery` returns `blocked` for non-absolute runtime target paths
- [x] `legacy_import` remains unavailable and metadata-only
- [x] no command runner execution occurs for `setup_discovery`

## Verification

- tests:
  - `tests.test_web_design_live_server` via inline `unittest` launcher with an
    ephemeral `tkinter` stub because the local Python lacks `_tkinter`
  - `tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_screens_are_inert_skeletons`
    and `tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_routes_are_static_only`
    via inline `unittest` launcher with an ephemeral `PIL.Image` stub because
    the local Python lacks Pillow
- build:
  - `python3 -m py_compile wild_boar_proxy/web_design_live_server.py tests/test_web_design_live_server.py`
  - `git diff --check`
- manual:
  - not run
- live evidence:
  - factual `setup_discovery` packets for `none`, `discovered`, and `blocked`

## Open Questions

- whether the next contour should materialize a target/session token directly in
  `web_design_live_server.py` or via a dedicated setup/import helper module
