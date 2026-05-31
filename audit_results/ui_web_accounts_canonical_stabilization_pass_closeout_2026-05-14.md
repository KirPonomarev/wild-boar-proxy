<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_ACCOUNTS_CANONICAL_STABILIZATION_PASS Closeout

## Goal

Bring the `Accounts / Аккаунты` web screen to the canonical table-screen
baseline while preserving runtime truth, command boundaries, and existing
operator safety rules.

## Result

- status: closed after implementation, screenshots, tests, and independent audit
- final verdict: Accounts is now the canonical table screen baseline for the web UI
- next action: plan the next web-only render transfer/stabilization contour from the approved queue, likely Diagnostics unless the owner reprioritizes

## Contour Capsule

- goal: stabilize Accounts as a canonical table screen with safe selection, row menus, no false live success, and no runtime or command-surface changes
- branch: codex/external-agent-lab-isolated
- head: 697ce50 before this contour commit
- touched files: wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; wild_boar_proxy/web_design_ui/styles/overview.css; wild_boar_proxy/web_design_ui/assets/icons/phosphor/dots-three.png; wild_boar_proxy/web_design_ui/assets/icons/phosphor/magnifying-glass.png; wild_boar_proxy/web_design_ui/assets/icons/phosphor/pause-circle.png; wild_boar_proxy/web_design_ui/assets/icons/phosphor/plus.png; wild_boar_proxy/web_design_ui/assets/icons/phosphor/user-plus.png; audit_results/ui_web_accounts_canonical_stabilization_pass_spec_2026-05-14.md; audit_results/ui_web_accounts_canonical_stabilization_pass_matrix_2026-05-14.json; audit_results/ui_web_accounts_canonical_stabilization_pass_independent_audit_2026-05-14.json; audit_results/ui_web_accounts_canonical_stabilization_pass_closeout_2026-05-14.md; audit_results/ui_web_accounts_canonical_stabilization_pass_screenshots/*.png
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q; git diff --check; raw account command trace scan; forbidden external reference trace scan; 1600x1000 screenshot matrix; Playwright DOM metric scan through system Chrome
- blocked risks: no runtime.py changes; no web_design_command_adapter.py changes; no web_design_live_server.py changes; no desktop changes; no fixture changes; no new browser payload keys; bulk validate remains disabled; live failure shows no-data state instead of healthy zeroes
- next exact command: git add wild_boar_proxy/web_design_ui/index.html wild_boar_proxy/web_design_ui/scripts/overview.js wild_boar_proxy/web_design_ui/styles/overview.css wild_boar_proxy/web_design_ui/assets/icons/phosphor/dots-three.png wild_boar_proxy/web_design_ui/assets/icons/phosphor/magnifying-glass.png wild_boar_proxy/web_design_ui/assets/icons/phosphor/pause-circle.png wild_boar_proxy/web_design_ui/assets/icons/phosphor/plus.png wild_boar_proxy/web_design_ui/assets/icons/phosphor/user-plus.png audit_results/ui_web_accounts_canonical_stabilization_pass_spec_2026-05-14.md audit_results/ui_web_accounts_canonical_stabilization_pass_matrix_2026-05-14.json audit_results/ui_web_accounts_canonical_stabilization_pass_independent_audit_2026-05-14.json audit_results/ui_web_accounts_canonical_stabilization_pass_closeout_2026-05-14.md audit_results/ui_web_accounts_canonical_stabilization_pass_screenshots

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed; `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q` passed with 87 tests
- build: static web UI syntax and Python unittest gates passed; no separate bundle step exists for this surface
- manual: reviewed after screenshots for fixture healthy and live readonly failure
- live verification: `http://127.0.0.1:8787/?source=live&screen=accounts` rendered live readonly failure as no-data without reusing healthy fixture values

## Artifacts

- spec: audit_results/ui_web_accounts_canonical_stabilization_pass_spec_2026-05-14.md
- packet: audit_results/ui_web_accounts_canonical_stabilization_pass_matrix_2026-05-14.json
- report: audit_results/ui_web_accounts_canonical_stabilization_pass_independent_audit_2026-05-14.json
- screenshots: audit_results/ui_web_accounts_canonical_stabilization_pass_screenshots/

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout-file creation time
- pushed: pending at closeout-file creation time

## Scope Check

- unrelated work mixed in: no staged or intended contour work outside the web UI files, icon assets, and contour artifacts
- private-data risk reviewed: touched files and artifacts contain no external reference service strings, project-private paths beyond repository-local artifact paths, or secret material

## Notes

- blockers encountered: in-app browser screenshot capture timed out on CDP; system Chrome headless was used for evidence screenshots
- follow-up contour: continue web render transfer/stabilization, likely Diagnostics canonical polish after owner review of Accounts
- resume from here: CLOSED
