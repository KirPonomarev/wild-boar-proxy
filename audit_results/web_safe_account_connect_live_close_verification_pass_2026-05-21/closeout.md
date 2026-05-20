<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_LIVE_CLOSE_VERIFICATION_PASS Closeout

## Goal

Execute the already-implemented live Quick Start onboarding lane in sandbox and
close it with owner packet, canonical refresh proof, browser evidence, and
independent audit.

## Result

- status: `closed_success`
- final verdict:
  `LIVE_QUICK_START_ONBOARDING_PROVEN_WITH_SANDBOX_PACKET_AND_CANONICAL_REFRESH`
- next action:
  move to `WEB_API_ROUTE_VERIFY_OR_ADOPT_SANDBOX_PASS`

## Contour Capsule

- goal:
  close the live Quick Start onboarding lane with one real sandbox run and
  machine-backed proof rather than local confidence
- branch: `codex/external-agent-lab-isolated`
- head: `current_contour_commit`
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/spec.md`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/independent_audit.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/closeout.md`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/*`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/*`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server.WebDesignLiveServerTests.test_http_sandbox_readonly_endpoints_follow_sandbox_target tests.test_web_design_live_server.WebDesignLiveServerTests.test_real_json_runner_supports_sandbox_onboard_from_profile_cwd tests.test_web_design_live_server.WebDesignLiveServerTests.test_account_connect_preflight_admits_clear_registry_identity -q`
  - `git diff --check`
- blocked risks:
  - none at medium-or-higher severity inside this contour
- next exact command:
  - `curl -s http://127.0.0.1:<sandbox-port>/api/api-connections-readonly`

## Verification

- tests:
  - targeted sandbox HTTP refresh test added and passed
  - existing live server/UI/adapter suites passed after the narrow repair
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed
  - `git diff --check` passed
- browser:
  - one real Quick Start dry-run preview executed in sandbox
  - one real Quick Start live onboarding executed in sandbox
  - screenshots captured for initial state, dry-run modal, dry-run result,
    live modal, live confirmation, live result, and action ledger
- live verification:
  - browser-run network trace persisted in
    `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/ui-run-network.json`
  - browser-run action panel summary persisted in
    `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/ui-run-summary.json`
  - canonical sandbox refresh persisted in
    `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/accounts-list-canonical-after.json`

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/spec.md`
- packet and refresh evidence:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/ui-run-network.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/ui-run-summary.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/accounts-readonly-after.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/accounts-list-canonical-after.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/evidence/status-canonical-after.json`
- screenshots:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/01-quick-start-initial.png`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/02-dry-run-modal.png`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/03-dry-run-result.png`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/04-live-modal.png`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/05-live-confirm.png`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/06-live-result.png`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/screenshots/07-action-ledger.png`
- audit:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `current_contour_commit`
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; browser still provided no token/path/auth/backend payloads and all writes stayed inside sandbox-only profile/data directories`

## Notes

- blockers encountered:
  - the first real UI run exposed a factual mismatch: live `POST /api/action`
    used the sandbox runner, but `/api/accounts-readonly` and
    `/api/api-connections-readonly` still refreshed through the generic readonly
    runner, producing `canonical refresh mismatch`
- blocker repair:
  - `build_handler(...)` now routes sandbox-phase accounts/API readonly GETs
    through the same sandbox-owned runner when the sandbox preflight is
    admitted
  - `test_http_sandbox_readonly_endpoints_follow_sandbox_target` proves the
    endpoint starts empty, live onboard succeeds, and refresh returns
    `auth` in `reserve`
- residual risk:
  - `status-canonical-after.json` still shows blocked `claim_gate` and
    `launch_capable_empty`; this does not invalidate reserve-first onboarding
    proof but it keeps broader runtime readiness outside this contour
- follow-up contour:
  - `WEB_API_ROUTE_VERIFY_OR_ADOPT_SANDBOX_PASS`
- resume from here:
  `start WEB_API_ROUTE_VERIFY_OR_ADOPT_SANDBOX_PASS using the same sandbox-only truth discipline; account onboarding is now proven and closed`
