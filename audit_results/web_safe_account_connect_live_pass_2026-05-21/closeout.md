<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS Closeout

## Goal

Enable the real reserve-first onboarding lane from Quick Start in sandbox web
mode, keeping preview and live semantics separate and proving live success only
through the owner packet plus canonical accounts refresh.

## Result

- status: `blocked_pending_owner_authorization`
- final verdict:
  `IMPLEMENTATION_VERIFIED_WITH_STUBBED_LIVE_LANE_REAL_SANDBOX_MUTATION_NOT_EXECUTED`
- next action:
  provide canonical owner authorization, then run one real sandbox onboarding
  through Quick Start and refresh proof

## Contour Capsule

- goal:
  admit `onboard_account` in `sandbox_actions`, wire Quick Start from preview to
  live reserve-first connect, and make onboarding refresh truth depend on the
  accounts snapshot rather than generic action success
- branch: `codex/external-agent-lab-isolated`
- head: `7704627` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/spec.md`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/closeout.md`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/independent_audit.json`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/screenshots/README.md`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`
  - `git diff --check`
  - local HTTP verification against `build_handler(..., action_phase=sandbox_actions)` with `MappingRunner(live_payloads())`
- blocked risks:
  - real sandbox write was not executed because the thread did not contain the
    explicit owner authorization phrase required by `CANON.md`
  - screenshot evidence is absent because browser automation was unavailable in
    the current tool set/runtime
- next exact command:
  - `curl -s -X POST http://127.0.0.1:<sandbox-port>/api/action -H 'Content-Type: application/json' -d '{"ui_action":"onboard_account"}'`

## Verification

- tests:
  - live-server tests prove `onboard_account` is admitted in `sandbox_actions`
    and still blocked by server-owned accounts preflight when the readonly proof
    is unsafe
  - UI tests prove Quick Start modal switches from preview to live reserve-first
    connect only after an admitted preview in the current session
  - UI tests prove onboarding refresh truth is taken from the accounts snapshot
    and treats reserve mismatch as non-success
- build:
  - `git diff --check` passed
- manual:
  - local `/api/actions` returned
    `onboard_account.available=true` in `sandbox_actions`
  - local `/api/action` dry-run packet returned
    `preview_only=true`, `ui_state=dry_run_ready`
  - local `/api/action` live packet returned
    `final_outcome=reserve_only_success`,
    `reserve_first_proven=true`,
    `selected_backend_id=acct-new`
- live verification:
  - blocked by missing explicit owner authorization phrase required by `CANON.md`

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_live_pass_2026-05-21/independent_audit.json`
- report:
  - this closeout plus stub-server HTTP evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; browser surfaces still exclude token/path/auth/backend_id, and no rollback truth was synthesized`

## Notes

- blockers encountered:
  - Quick Start still hard-wired the modal to `onboard_account_dry_run`
  - generic refresh handling treated the Quick Start composite refresh payload as
    failed, which would have falsely degraded live onboarding after success
  - canonical owner authorization was insufficient for a real sandbox write
- follow-up contour:
  - exact next move depends on explicit authorization; if granted, rerun the
    same contour's live verification instead of widening scope
- resume from here:
  `wait for canonical owner authorization phrase, then run one real sandbox Quick Start onboarding and confirm packet plus accounts refresh proof`
