# WEB_API_ROUTE_ALLOW_EXISTING_SERVER_OWNED_PASS Closeout

## Goal

Prove a real sandbox-safe web flow for enabling an existing disabled API route through `api_route_allow`, with packet truth and readonly refresh truth.

## Result

- status: closed
- verdict: `api_route_allow` works as admitted server-owned sandbox action and flips the target route from disabled to enabled in refreshed readonly state.
- next action: proceed to the next API-route contour from the master-plan queue.

## Contour Capsule

- goal: close `api_route_allow` live lane on sandbox copy.
- branch: `codex/external-agent-lab-isolated`
- head: `cf2da10`
- touched files:
  - `tests/test_web_design_live_server.py`
  - `audit_results/web_api_route_allow_existing_server_owned_pass_2026-05-21/*`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_command_adapter.WebDesignCommandAdapterTests.test_accounts_onboard_runs_exact_argv_without_browser_args tests.test_web_design_command_adapter.WebDesignCommandAdapterTests.test_accounts_onboard_rejects_all_browser_args -q`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: no structural blocker found; contour remains bounded to allow-existing lane and does not claim runtime readiness.
- next exact command: `git commit -m "web: prove sandbox api route allow existing lane"`
- primary proof:
  - packet: `evidence/api-route-allow-packet.json`
  - refresh before/after: `evidence/api-connections-readonly-before.json`, `evidence/api-connections-readonly-after.json`
  - browser-state screenshot: `screenshots/browser-api-connections-after-allow.png`

## Verification

- targeted tests:
  - `tests.test_web_design_live_server.WebDesignLiveServerTests.test_real_json_runner_supports_sandbox_api_route_allow_from_profile_cwd`
  - `tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_actions_preflight_route_and_execute_exact_commands`
  - `tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_actions_reject_bad_targets_without_execution`
  - `tests.test_web_design_ui.WebDesignUiTests.test_api_route_action_buttons_require_live_source_and_enabled_route`
- contour gate checks:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - full unittest suite from prior contour gate (same baseline command set)
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`

## Scope Check

- no create/import/adopt flow added.
- no browser secret/path/token intake added.
- no desktop/packaging/design work mixed in.

## Notes

- The browser artifact is a headless render after successful action execution; packet and refresh truth remain canonical for success.
- This contour does not claim runtime readiness; adapter remains synthetic and runtime claim stays blocked by design.

resume from here: `NEXT_API_ROUTE_CONTOUR_FROM_MASTER_PLAN`
