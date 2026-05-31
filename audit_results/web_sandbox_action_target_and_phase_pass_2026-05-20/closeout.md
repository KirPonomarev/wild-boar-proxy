<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SANDBOX_ACTION_TARGET_AND_PHASE_PASS Closeout

## Goal

Introduce a separate sandbox action phase so web Quick Start can stop treating
all real actions as permanently parked in `live_readonly`, while keeping the
current working Codex untouched.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `SANDBOX_ACTION_PHASE_AND_TARGET_PROOF_ADDED_WITHOUT_REOPENING_LIVE_READONLY`
- next action: move to `WEB_QUICK_START_ONBOARD_ACCOUNT_SANDBOX_PASS`

## Contour Capsule

- goal:
  add a narrow sandbox phase, prove sandbox target isolation, and expose phase
  truth through `/api/actions` and the Quick Start source label
- branch: `codex/external-agent-lab-isolated`
- head: `04d7d85` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/spec.md`
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/metrics.json`
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/closeout.md`
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/independent_audit.json`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_command_adapter -q`
  - `git diff --check`
  - local `curl` verification for `/api/actions` and `/api/live-readonly` on a sandbox-phase server
- blocked risks:
  - sandbox action phase now gates actions correctly, but real reserve-first
    onboarding still needs a proven sandbox data layout in the next contour
  - full web-safe API provisioning is still deferred; this contour only opens
    route verify/adopt surfaces
- next exact command:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server -q`

## Verification

- tests:
  - live-server tests prove `live_readonly` remains parked and `sandbox_actions`
    opens only the admitted subset
  - UI tests prove the source pill switches to `Sandbox` only when sandbox
    phase metadata is admitted
  - command-adapter tests remain green
- build:
  - `git diff --check` passed
- manual:
  - `/api/actions` on a local sandbox-phase server returned
    `action_phase=sandbox_actions`
  - sandbox preflight returned `status=admitted`
  - `onboard_account.available=true`
  - `validate_account.available=false`
- live verification:
  - local sandbox-phase server kept `/api/live-readonly` on the canonical live
    readonly source while opening only the admitted action subset in
    `/api/actions`
  - source pill and footer switch to `Sandbox` only when sandbox phase metadata
    is admitted, while the subtitle still states that data remains
    live-readonly

## Artifacts

- spec:
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/spec.md`
- packet:
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/metrics.json`
  - `audit_results/web_sandbox_action_target_and_phase_pass_2026-05-20/independent_audit.json`
- report:
  - this closeout plus targeted unit-test and HTTP verification evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; browser surfaces still exclude token/path/auth/backend_id and sandbox target proof stays metadata-only`

## Notes

- blockers encountered:
  - system `python3` lacked `_tkinter` and `PIL`; verification was moved to the
    repo-owned runtime Python
  - direct file-name hints in the sandbox runner env builder first violated a
    static boundary test and were reduced to root-level sandbox env overrides
- follow-up contour:
  - `WEB_QUICK_START_ONBOARD_ACCOUNT_SANDBOX_PASS`
- resume from here:
  `sandbox phase and target proof now exist; next move is real reserve-first onboarding against a seeded or otherwise proven sandbox data layout`
