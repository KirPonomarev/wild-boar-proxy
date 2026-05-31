<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_SETTINGS_ACCOUNTS_POLICY_SUBFLOW_PASS Closeout

## Goal

Implement a bounded Settings subflow for `Accounts Policy`: policy invariants, pool meanings, validation and hold semantics, observed pool snapshot counts, deferred policy controls, and compact last-command state without making Settings a config editor, lifecycle action table, or hidden bulk-action surface.

## Result

- status: implemented and verified
- final verdict: PASS
- next action: owner review, then proceed to the next approved contour

## Contour Capsule

- goal: add `?screen=settings&section=accounts-policy` as a Settings-only subflow entered from the existing Accounts Policy hub card, with observed pool snapshot separated from future policy truth.
- branch: `codex/external-agent-lab-isolated`
- head: pending final contour commit; implementation started after `883ac38`.
- touched files: `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_ui.py`, `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`; `git diff --check`; browser metric matrix captured at `1600x1000`.
- blocked risks: no command adapter change, no allowlist change, no live-server contract change, no desktop/native bridge, no config/state/auth/log writes, no policy write action, no lifecycle mutation action, no auto-promote copy/action, no `accounts list` treated as policy config truth.
- next exact command: stage the declared scope, run staged closeout resilience, commit, push.

## Verification

- preflight: `git status --short --untracked-files=no` was clean for tracked files; `git log --oneline -n 6` showed previous closed contour commit `883ac38`.
- structure inspection: Settings now supports sections `hub`, `runtime`, `client`, `accounts-policy`, and `data-layout`; `accounts-policy` is not a sidebar screen and is not added to `SCREENS`.
- route gate: `?screen=settings&section=accounts-policy` opens the Accounts Policy subflow; `Назад к настройкам` returns to the Settings hub.
- boundary inspection: the subflow exposes no `data-ui-action`; it only links to Accounts and opens the existing local action ledger.
- policy truth inspection: `accounts list readonly snapshot` is labelled as observed pool snapshot only; policy source remains `future policy packet / unavailable`.
- forbidden surface check: no file/input/select/textarea, no editable policy form, no policy write payload, no capacity/reserve target payload, no lifecycle action dispatch, no auto-promote action/copy, no config/path/raw command/argv/shell payload.
- visual gate: all six `1600x1000` captures pass `documentElement.scrollHeight <= 1000`, `main.scrollHeight <= main.clientHeight + 1`, `accountsPolicyPanel.bottom <= 934`, no horizontal overflow, no clipped buttons/chips, all five pool meanings visible, `visibleSvgIcons === 0`, `visibleImgIcons > 0`, no input/select/textarea, and no false policy truth strings.
- unit suite: 96 tests passed across `tests.test_web_design_ui`, `tests.test_web_design_live_server`, and `tests.test_web_design_command_adapter`.

## Artifacts

- design source: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/screens/17_settings_accounts_policy.png`
- design tokens: `/Users/kirillponomarev/Downloads/кабан дизайн/final_design_package/specs/design_tokens.json`
- report: `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/closeout.md`
- screenshots:
  - `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/screenshots/policy_healthy_preview_1600x1000.png`
  - `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/screenshots/accounts_stale_1600x1000.png`
  - `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/screenshots/no_accounts_first_run_1600x1000.png`
  - `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/screenshots/pool_problem_1600x1000.png`
  - `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/screenshots/deferred_controls_1600x1000.png`
  - `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/screenshots/live_integration_failure_1600x1000.png`
- metrics: `audit_results/ui_web_settings_accounts_policy_subflow_pass_2026-05-15/metrics/*.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: final implementation commit recorded in git history and final operator note
- pushed: pending before final push

## Scope Check

- unrelated work mixed in: no; existing unrelated untracked `audit_results/external_lab_*` and `external_agent_lab/legacy/eval_results/` remain untouched.
- runtime touched: no.
- command adapter or allowlist touched: no.
- live server contract touched: no.
- desktop/native bridge touched: no.
- config/state/auth/log files touched: no.
- accounts runtime policy implementation touched: no.
- private-data risk reviewed: yes; no auth values, account secrets, browser paths, raw logs, raw command strings, or policy mutation payloads are rendered or dispatched.

## Notes

- `accounts list readonly snapshot` is used only for observed counts. It is not presented as full policy truth.
- Numeric targets remain `unknown` or `design target preview`; there is no saved-policy claim.
- Lifecycle actions remain in Accounts / Account Detail and are intentionally absent from this Settings subflow.
- resume from here: CLOSED
