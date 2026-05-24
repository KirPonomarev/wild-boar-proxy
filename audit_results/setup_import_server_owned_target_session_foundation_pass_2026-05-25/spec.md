# Spec: SETUP_IMPORT_SERVER_OWNED_TARGET_SESSION_FOUNDATION_PASS

## Objective

Admit one minimal server-owned opaque token lane on top of existing `legacy_import_discovery` truth so `legacy_import` can expose token-bound import-capable reference truth without opening browser path intake, import execution, confirm semantics, or workflow lifecycle.

## In Scope

- one in-memory server-owned token store for the import-existing branch
- token materialization from `legacy_import_discovery`
- token-only reference binding for `legacy_import`
- explicit rejection of browser-owned source/path fields on `legacy_import`
- shared handler wiring across `/api/action` and `/api/actions`
- targeted live-server tests and inert UI regressions

## Out of Scope

- final `legacy_import` execution
- explicit confirm or cancel
- selection semantics or workflow lifecycle
- durable token persistence
- UI activation or redesign

## Constraints

- browser must not provide `source_dir`, `source_path`, `path`, or `source`
- token must stay opaque and server-owned
- token flow must stay zero-write
- `legacy_import` must remain reference-only and non-mutating
- current runtime layout fallback must not masquerade as import-source truth

## Assumptions

- a single active in-memory token is sufficient for this foundation contour
- later contours may change token shape only through deliberate contract work
- handler-local storage is cheaper and truer than a durable session subsystem at this stage

## Acceptance Criteria

- [x] `legacy_import_discovery` materializes one server-owned opaque token on discovered truth
- [x] `legacy_import` accepts only token-bound reference payloads
- [x] browser path/source payload is explicitly rejected
- [x] metadata and action execution share the same handler-level token store
- [x] zero-write proof holds and `runner.calls` remains empty
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
  - packet capture only; no UI activation and no import execution in this contour
- live evidence:
  - `audit_results/setup_import_server_owned_target_session_foundation_pass_2026-05-25/evidence/action_packets.json`

## Open Questions

- whether later contours need more than one simultaneous import-existing token per handler instance
