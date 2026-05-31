# WEB_FUNCTIONAL_MENU_WIRING_PASS Closeout

## Goal

Expose already proven runtime/accounts/API/diagnostics actions through the web
control surface without design creep, keep sandbox-phase runtime mutations
truthfully parked, and eliminate the stale provider split where API credential
actions still claimed `openrouter` while readonly route truth was already
`deepseek`.

## Result

- status: `closed_success`
- final verdict: provider-aware credential execution now follows the current
  primary route snapshot, live `/api/actions` keeps parked runtime mutations
  truthfully disabled, and live `api_route_credential_check` now returns
  `credential_provider=deepseek` with `credential_ref=DEEPSEEK_API_KEY`
- next action: proceed to `ISOLATED_CODEX_APP_E2E_PASS`

## Contour Capsule

- goal: truthful web functional wiring for admitted actions, with provider-aware
  API credential handoff and no sandbox-phase false-green
- branch: `codex/external-agent-lab-isolated`
- head: `bc4fe9a`
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_command_adapter.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/spec.md`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/baseline.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/proof.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/metrics.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/redaction_audit.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/independent_audit.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/evidence/browser_api_actions.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/evidence/browser_quick_start_api.json`
  - `audit_results/web_functional_menu_wiring_pass_2026-05-23/closeout.md`
- tests run:
  - `python3 -B -m unittest tests.test_web_design_live_server.WebDesignLiveServerTests.test_ui_action_metadata_hides_adapter_commands_and_marks_confirmed_actions tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_connect_adopts_existing_primary_route_without_add tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_connect_prefers_primary_route_snapshot_provider tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_connect_rejects_forbidden_browser_fields tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_credential_check_surfaces_missing_owner_env_without_route_mutation tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_credential_check_reports_present_owner_env tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_credential_check_uses_server_owned_route_provider tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_route_credential_check_prefers_primary_route_snapshot_provider tests.test_web_design_ui.WebDesignUiTests.test_api_connections_screen_is_readonly_and_product_safe tests.test_web_design_ui.WebDesignUiTests.test_static_confirmation_policy_covers_risky_actions tests.test_web_design_ui.WebDesignUiTests.test_static_preview_applies_action_availability_from_metadata tests.test_web_design_ui.WebDesignUiTests.test_snapshot_command_ledger_renders_bounded_readonly_commands tests.test_web_design_ui.WebDesignUiTests.test_action_ledger_recent_entries_are_session_only_and_count_paths -q`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- blocked risks:
  - sandbox phase still truthfully parks runtime-mutating actions such as
    `launch_client_dispatch`, `sync_runtime`, and `refresh_health_detail`; this
    is expected scope, not a regression
  - external agent spawn for independent audit hit a thread-limit boundary, so
    the independent audit packet was produced by local replay instead of a
    separate live subagent
- next exact command:
  - `git push origin codex/external-agent-lab-isolated`

## Verification

- tests:
  - targeted live-server + web UI suite passed (`13` tests)
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - compared `/api/actions` metadata, `/api/api-connections-readonly`, and live
    `POST /api/action` output for `api_route_credential_check`
  - verified browser quick-start/API surface continues to show `deepseek`,
    `DEEPSEEK_API_KEY`, and sandbox-phase parked runtime controls
- live verification:
  - `curl -s http://127.0.0.1:8788/api/actions`
  - `curl -s http://127.0.0.1:8788/api/api-connections-readonly`
  - `curl -s -X POST http://127.0.0.1:8788/api/action -H 'Content-Type: application/json' -d '{"ui_action":"api_route_credential_check"}'`

## Artifacts

- spec:
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/spec.md`
- packet:
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/baseline.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/proof.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/metrics.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/redaction_audit.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/independent_audit.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/evidence/browser_api_actions.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/evidence/browser_quick_start_api.json`
- report:
  - `/Volumes/Work/wild-boar-proxy/audit_results/web_functional_menu_wiring_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `bc4fe9a` (packet + code/tests)
- pushed: `no`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes`; artifacts contain only bounded secret refs,
  not secret values

## Notes

- blockers encountered:
  - initial live `/api/actions` metadata was fixed first, but live
    `api_route_credential_check` still executed through stale OpenRouter
    fallback logic until provider/secret-ref selection switched to the current
    primary route snapshot
  - browser proof for the changed provider lane was easier to capture through
    quick-start/API readonly state plus live `ui_action` packets than through a
    dedicated visible credential button on the API routes screen
- follow-up contour:
  - `ISOLATED_CODEX_APP_E2E_PASS`
- resume from here: `ISOLATED_CODEX_APP_E2E_PASS`
