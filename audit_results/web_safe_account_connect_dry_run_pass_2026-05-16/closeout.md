<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_DRY_RUN_PASS Closeout

## Goal

Add one safe web dry-run flow for account connection that shows preview-only
truth without doing real onboarding, auth import, registry mutation, or runtime
mutation.

## Result

- status: `verified_pending_git_close`
- final verdict:
  `SERVER_OWNED_DRY_RUN_PREVIEW_FLOW_ADDED_WITHOUT_LIVE_ACCOUNT_MUTATION`
- next action:
  move to `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS`

## Contour Capsule

- goal:
  replace the visible web account-add affordance with a dry-run-only preview
  flow that never accepts browser secrets or writes account state
- branch: `codex/external-agent-lab-isolated`
- head: `955f000` before contour changes
- touched files:
  - `wild_boar_proxy/web_design_live_server.py`
  - `wild_boar_proxy/web_design_ui/index.html`
  - `wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `tests/test_web_design_live_server.py`
  - `tests/test_web_design_ui.py`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/contour.md`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/decision_packet.json`
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui`
  - browser check against a local preview server at `?screen=accounts&source=live`
- blocked risks:
  - no real account connection or auth import was performed in this contour
  - dry-run preview still depends on a later live contour for actual onboarding
- next exact command:
  - `python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui`

## Verification

- tests:
  - live-server tests passed with preview-only dry-run action and browser-arg rejection
  - UI tests passed with preview-only onboarding rendering and non-green result states
- build:
  - decision packet JSON parses
  - `git diff --check` must pass before commit
- manual:
  - accounts button now says `Проверить подключение`
  - dry-run modal explains preview-only boundary
  - action result shows preview-only banner, no selected backend, and next live contour
- live verification:
  - browser click executed against a local preview server
  - current working Codex session was not launched, mutated, or interrupted

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/web_safe_account_connect_dry_run_pass_2026-05-16/decision_packet.json`
- report:
  - this closeout plus unit-test and browser-check evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: atomic contour commit is created after staged verification passes
- pushed: contour branch must be pushed before closeout is final

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; browser payload stays bounded and no auth paths, secrets, or raw packets are exposed`

## Notes

- blockers encountered:
  - the existing visible onboarding affordance still pointed at live `onboard_account` and had to be narrowed to preview-only copy and action id
  - preview result rendering initially reused green success assumptions and was tightened to neutral/amber preview-only states
- follow-up contour:
  - `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS`
- resume from here:
  `dry-run preview flow is browser-click verified and mutation-free; next move is live account-connect with explicit write surfaces`
