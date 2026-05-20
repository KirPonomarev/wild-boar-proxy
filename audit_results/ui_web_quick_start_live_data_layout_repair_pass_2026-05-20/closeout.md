<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_QUICK_START_LIVE_DATA_LAYOUT_REPAIR_PASS Closeout

## Goal

Repair Quick Start after density polish so live account data does not break the
operator layout: accounts stay left, API stays right, raw ISO timestamps are
hidden from the primary view, and `Проверить` no longer behaves like a broken
status/action hybrid.

## Result

- status: closed
- final verdict: pass after independent audit re-check
- next action: continue with the next master-plan contour after operator review

## Contour Capsule

- goal: repair Quick Start live-data layout, account-row copy, and inert check marker without touching runtime or command contracts
- branch: codex/external-agent-lab-isolated
- head: 697049b
- touched files: wild_boar_proxy/web_design_ui/scripts/overview.js; wild_boar_proxy/web_design_ui/styles/overview.css; tests/test_web_design_ui.py; audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; /usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q; git diff --check; browser metrics at 1600x1000
- blocked risks: raw ISO timestamp leakage, disappearing API column, mixed status/action chip, accidental command surface, runtime/adapter scope creep
- next exact command: git status --short

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- tests: `git diff --check`
- browser: `http://127.0.0.1:8765/?screen=quick-start&source=live` at `1600x1000`
- browser: `http://127.0.0.1:8765/?screen=quick-start&source=fixture&state=healthy` at `1600x1000`
- live verification: `metrics.json` shows `cardsTwoColumn=true`, `noRawIso=true`, `noLastCheckCopy=true`, `apiTitleNoBrokenWrap=true`, `noHorizontalOverflow=true`, `mainFits=true`, `visibleSvgIconsZero=true`, and `brokenImagesEmpty=true`
- fixture verification: `fixtureRows.rowCount=4`, `fixtureRows.noRawIso=true`, `fixtureRows.noLastCheckCopy=true`, and row copy uses operator labels such as `Пауза`, `Резерв`, and `Активен`
- independent audit: first pass found disabled button risk; fix replaced it with inert `span`; repeat audit verdict is pass

## Artifacts

- spec: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/spec.md`
- metrics: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/metrics.json`
- screenshot: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/screenshots/quick-start-live-layout-repaired.png`
- screenshot: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/screenshots/quick-start-fixture-rows-repaired.png`
- independent audit: `audit_results/ui_web_quick_start_live_data_layout_repair_pass_2026-05-20/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: created after final staged checks in the same contour closeout sequence
- pushed: pushed after commit in the same contour closeout sequence

## Scope Check

- unrelated work mixed in: no
- runtime files touched: no
- command adapter touched: no
- live server touched: no
- command contracts touched: no
- allowlist touched: no
- desktop/native bridge touched: no
- private-data risk reviewed: screenshots and metrics contain UI state only; no secrets, tokens, auth files, or local runtime credentials are added

## Notes

- blockers encountered: independent auditor rejected the initial disabled-button implementation as a possible command surface
- resolution: accepted the audit finding and changed the row check affordance to an inert marker with `aria-disabled="true"` and no command payload
- follow-up contour: per-account live checking remains deferred until a dedicated admitted action mapping is specified
- resume from here: CLOSED
