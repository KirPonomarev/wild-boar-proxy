# Spec: WEB_API_ROUTE_ALLOW_EXISTING_SERVER_OWNED_PASS

## Objective

Close a real sandbox-safe web lane for enabling an already-known disabled API route from `api-connections`, without browser secret/path intake and with packet+refresh proof.

## In Scope

- `ui_action=api_route_allow` through sandbox admitted server path.
- Exact adapter command proof: `external-models routes enable --route <route_id> --json`.
- Refresh proof via `api/api-connections-readonly` before/after.
- Targeted tests and contour artifacts.

## Out of Scope

- API route create/import/update/draft.
- Browser secret/token/path entry.
- Desktop, packaging, redesign, or runtime promotion.

## Constraints

- Browser payload is bounded to `ui_action` + `route_id`.
- Green requires command packet truth plus readonly refresh truth.
- Writes must stay in sandbox copy surfaces.

## Acceptance Criteria

- [x] `api_route_allow` returns `status=ok` and `machine_error_code=OK`.
- [x] Action role is `api_route_lifecycle_allow`.
- [x] Packet changed file points to sandbox `external-models/routes.json`.
- [x] Refresh proves route state changed from disabled to enabled.
- [x] Guard test rejects extra browser fields for `api_route_allow`.

## Verification

- tests:
  - `python3 -B -m unittest tests.test_web_design_live_server.WebDesignLiveServerTests.test_real_json_runner_supports_sandbox_api_route_allow_from_profile_cwd -q`
  - `python3 -B -m unittest tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_actions_preflight_route_and_execute_exact_commands tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_actions_reject_bad_targets_without_execution -q`
  - `python3 -B -m unittest tests.test_web_design_ui.WebDesignUiTests.test_api_route_action_buttons_require_live_source_and_enabled_route -q`
- live evidence:
  - `evidence/api-route-allow-packet.json`
  - `evidence/api-connections-readonly-before.json`
  - `evidence/api-connections-readonly-after.json`
  - `evidence/browser-run-summary.json`
  - `screenshots/browser-api-connections-after-allow.png`

