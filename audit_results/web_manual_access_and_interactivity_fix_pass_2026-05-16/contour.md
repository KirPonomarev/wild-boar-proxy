# WEB_MANUAL_ACCESS_AND_INTERACTIVITY_FIX_PASS

## Goal

Localize and fix the repo-owned blocker that could leave the manual web preview
with dead action buttons after a failed initial action-metadata fetch, without
changing admitted action semantics or widening server/runtime scope.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `repo-owned manual interactivity blocker fixed by live-refresh metadata reload`
- next action:
  `DESKTOP_APP_PORT_PASS`

## Scope

- in scope:
  - manual web interactivity on the existing user-facing live link
  - repo-owned UI metadata refresh path
  - UI regression coverage for failed-first metadata fetch recovery
- out of scope:
  - desktop port
  - packaging
  - runtime/onboarding semantics rewrite
  - host bridge or platform-wide localhost refactor

## Evidence

- browser-facing live page loaded with `source = live`
- visible admitted actions were manually observed as clickable on:
  - quick-start
  - accounts
  - api-connections
- shell-side localhost `503` was observed separately, but rejected as the root
  repo-owned cause because the actual user-facing in-app browser path loaded
  data and actions successfully
- the repo-owned bug that remained was narrower:
  `loadActionMetadata()` only ran on initial page load, so a failed first fetch
  could leave action availability stuck in `UI_ACTION_METADATA_UNAVAILABLE`
  until a full page reload

## Implementation

- `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `setLiveReadonly()` now reloads action metadata and reapplies action
    availability during live refresh
- `tests/test_web_design_ui.py`
  - preserved pending-live UI coverage
  - added recovery coverage for:
    `initial metadata fetch failed -> later live refresh reloads metadata -> button recovers`

## Verification

- tests:
  - `python3 -m unittest -q tests.test_web_design_ui.WebDesignUiTests.test_overview_live_readonly_sets_pending_live_state_before_fetch_resolves tests.test_web_design_ui.WebDesignUiTests.test_set_live_readonly_retries_action_metadata_after_initial_failure`
  - `python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui`
- browser:
  - quick-start live link reloaded successfully
  - quick-start `Подключить аккаунт` button was enabled and opened the modal
  - accounts live screen showed visible enabled account actions
  - api-connections live screen showed visible enabled admitted route actions
- hygiene:
  - `git diff --check`

## Next Contour

`DESKTOP_APP_PORT_PASS`
