# Spec: LEGACY_IMPORT_DISCOVERY_OR_DRY_RUN_COMMAND_CONTOUR

## Objective

Open one bounded non-mutating command-owned truth path for an importable legacy source candidate without opening `legacy_import` execution, browser path intake, or token/session semantics.

## In Scope

- one read-only import-source discovery lane
- strict JSON packet truth for `none / discovered / blocked`
- explicit rejection of browser-owned path/source payload fields
- proof that current runtime layout is not reused as import-source truth
- targeted live-server tests and inert UI regressions

## Out of Scope

- `legacy_import` execution
- explicit confirm or cancel
- token/session binding
- snapshot or rollback commands
- UI activation or redesign

## Constraints

- browser must not provide `source_dir`, `source_path`, `path`, or `source`
- discovery must stay zero-write
- current runtime layout fallback must not masquerade as import-source truth
- existing `legacy_import` lane stays parked

## Assumptions

- a narrow exact known-owned source is cheaper and truer than a broad filesystem scan
- `~/.codex-custom-cli` may be used only as a read-only server-owned candidate source
- UI may remain inert while command/packet truth is admitted

## Acceptance Criteria

- [x] one bounded non-mutating import-source truth path exists
- [x] packet truth returns `none / discovered / blocked`
- [x] browser path/source payload is explicitly rejected
- [x] current runtime layout reuse is blocked
- [x] `legacy_import` execution remains unavailable
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
  - `audit_results/legacy_import_discovery_or_dry_run_command_contour_pass_2026-05-25/evidence/action_packets.json`

## Open Questions

- whether the later token/session contour should reuse this exact known-owned source or replace it with a stricter server-owned mediation contract
