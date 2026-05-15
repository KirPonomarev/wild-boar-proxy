# UI_WEB_SETTINGS_ADVANCED_SUBFLOW_PASS Closeout

## Goal

Implement the Settings subflow `Advanced` as a bounded operator-boundary/reference surface: command-surface rules, deferred dangerous actions, owner-approval gates, safe navigation links, compact last-command summary, and system notes without turning Settings into a raw command center.

## Result

- status: closed and included in the atomic commit `Add advanced settings subflow`.
- final verdict: Settings now has a section-routed Advanced subflow at `?screen=settings&section=advanced`; it contains no active `data-ui-action`, no raw command inputs, no file/path inputs, and no adapter/live-server/allowlist/runtime changes.
- next action: continue with the next UI contour only after the pushed commit is confirmed.

## Contour Capsule

- goal: Add a Settings-only Advanced subflow that explains operator boundaries, deferred gates, and safe surfaces without enabling hidden admin-console behavior.
- branch: codex/external-agent-lab-isolated
- head: atomic commit `Add advanced settings subflow` on branch codex/external-agent-lab-isolated; verify exact hash with `git log --oneline -n 1`.
- touched files: wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; wild_boar_proxy/web_design_ui/styles/overview.css; tests/test_web_design_ui.py; audit_results/ui_web_settings_advanced_subflow_pass_2026-05-15/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q; git diff --check; Playwright visual matrix 7 Advanced states at 1600x1000.
- blocked risks: raw command dispatch blocked; dangerous actions remain disabled/deferred; owner-gated desktop/native and human-open actions are informational only; action result does not become runtime truth.
- next exact command: git log --oneline -n 1

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed; `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q` passed with 98 tests; `git diff --check` passed.
- build: JavaScript syntax check passed.
- manual: Playwright captured and validated `advanced_preview`, `dangerous_actions_deferred`, `owner_approval_required`, `safe_links_only`, `stale`, `live_integration_failure`, and `last_command_visible` at 1600x1000.
- layout gates: `documentScrollHeight=1000`, `main.scrollHeight=942`, `main.clientHeight=942`, `advancedBottom=922`, `visibleSvgIcons=0`, `visibleImgIcons=9`, `dataActions=[]`, `inputs=0`.
- live verification: live integration failure was checked through the static preview server and did not reuse fixture truth.

## Artifacts

- spec: user-provided contour `UI_WEB_SETTINGS_ADVANCED_SUBFLOW_PASS`.
- packet: audit_results/ui_web_settings_advanced_subflow_pass_2026-05-15/visual_matrix_report.json
- screenshots: audit_results/ui_web_settings_advanced_subflow_pass_2026-05-15/screenshots/

## Git

- branch: codex/external-agent-lab-isolated
- commit: Add advanced settings subflow
- pushed: codex/external-agent-lab-isolated pushed to origin after the atomic commit

## Scope Check

- unrelated work mixed in: no; tracked scope is limited to the declared web UI files, UI test file, and this contour's audit artifacts.
- private-data risk reviewed: yes; Advanced displays policy/reference text only and does not render logs, raw support artifacts, secret values, local file contents, or browser-provided paths.
- command boundary reviewed: yes; the Advanced panel has no active command dispatch surface, no `data-ui-action`, and no hidden raw-command form.

## Independent Review

- Parfit reported insertion points for the hub link, section router, panel placement, compact action fanout, CSS block, and order-sensitive tests.
- Rawls audited existing adapter/live-server surfaces and flagged `stable_repair_apply`, policy/rollout controls, browser command identifiers, raw arguments, shell execution, paths, tokens, secrets, and desktop/native behavior as forbidden in Advanced.
- Orchestrator result: implemented as readonly/deferred section with safe navigation only, and validated with tests plus screenshot metrics.

## Notes

- blockers encountered: visual matrix initially exposed cramped/clipped Advanced rows; CSS grid and notes/owner-gate presentation were tightened and the matrix reran cleanly.
- follow-up contour: no follow-up required for this subflow; any active dangerous action requires a separate admitted command-owned contour.
- resume from here: CLOSED
