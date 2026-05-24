# Spec: CONTOUR_06 MARKDOWN_IMPORT_CONFIRMATION_FIX

## Objective

On current repo truth, execute the master-plan `CONTOUR_06` through the admitted `legacy_import_discovery` + `legacy_import` server-owned token surface so token-only import calls remain zero-write reference truth and real import mutation becomes possible only after explicit confirm.

## In Scope

- explicit confirm gate on `legacy_import`
- server-owned token resolution to owner import execution
- token-only reference lane stays zero-write
- receipt only after confirmed write attempt
- source-dir sanitization in failure and receipt truth
- token consumption after confirmed execution attempt
- targeted live-server tests and inert UI regressions

## Out of Scope

- UI redesign or import wizard activation
- browser-owned path submission
- generic workflow/session subsystem
- dry-run/verify plan expansion
- release claim wording

## Constraints

- browser must not provide `source_dir`, `source_path`, `path`, or `source`
- token-only path must remain non-mutating
- confirmed path must execute only through main-process-owned token binding
- receipt must appear only after a real confirmed write attempt
- source path must not leak in web-facing failure or receipt truth

## Assumptions

- `legacy_import_discovery` remains the only admitted discovery lane
- `legacy_import` remains the only admitted create lane
- one in-memory active token per handler is sufficient for this contour

## Acceptance Criteria

- [x] preview/discovery stays zero-write
- [x] token-only `legacy_import` remains reference-only and non-mutating
- [x] confirmed `legacy_import` executes only with explicit `confirmed: true`
- [x] receipt appears only after real confirmed write attempt
- [x] failure/rollback truth is honest and does not leak source path
- [x] targeted tests and inert UI regressions pass

## Verification

- tests:
  - `tests.test_web_design_live_server`
  - `tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_screens_are_inert_skeletons`
  - `tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_routes_are_static_only`
- build:
  - `python3 -m py_compile wild_boar_proxy/web_design_live_server.py tests/test_web_design_live_server.py`
  - `git diff --check`
- manual:
  - packet capture only; no UI activation in this contour
- live evidence:
  - `audit_results/markdown_import_confirmation_fix_pass_2026-05-25/evidence/action_packets.json`

## Open Questions

- whether later contours need a separate dry-run/verify import-plan packet before broader import UX can be claimed
