<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_SHARED_SHELL_BRAND_ALIGNMENT_PASS Closeout

## Goal

Align the sidebar shell across the primary web screens to the Quick Start brand
lockup without touching content layouts, runtime behavior, command surfaces, or
data mappings.

## Result

- status: closed
- final verdict: pass
- next action: continue with the next content-page alignment contour after operator review

## Contour Capsule

- goal: make shared sidebar brand/nav shell match Quick Start with 180px logo, 16px/20px brand typography, hidden caption, and accessible nav across six screens
- branch: codex/external-agent-lab-isolated
- head: c436241
- touched files: wild_boar_proxy/web_design_ui/styles/overview.css; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_web_design_ui.py; audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; /usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q; git diff --check; browser metrics across six screens at 1600x1000
- blocked risks: old per-screen brand sizing drift, visible brand runtime caption, Quick Start shell regression, content layout scope creep, runtime/adapter scope creep
- next exact command: git status --short

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- tests: `git diff --check`
- browser: `quick-start`, `overview`, `accounts`, `api-connections`, `diagnostics`, and `settings` with `source=live`
- browser evidence: `metrics.json` shows `allScreensStable=true`, `logoWidthAligned=true`, `brandTypographyAligned=true`, `captionHidden=true`, `navAccessible=true`, `noHorizontalOverflow=true`, `visibleSvgIconsZero=true`, and `brokenImagesEmpty=true`
- independent audit: pass, no findings

## Artifacts

- spec: `audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/spec.md`
- metrics: `audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/metrics.json`
- screenshots: `audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/screenshots/*-shell.png`
- independent audit: `audit_results/ui_web_shared_shell_brand_alignment_pass_2026-05-20/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: created after final staged checks in this closeout sequence
- pushed: pushed after commit in this closeout sequence

## Scope Check

- unrelated work mixed in: no
- runtime files touched: no
- command adapter touched: no
- live server touched: no
- command contracts touched: no
- data mapping touched: no
- content cards, rows, tables, and forms changed: no
- private-data risk reviewed: screenshots and metrics contain UI layout state only; no secrets, tokens, auth files, or runtime credentials are added

## Notes

- blockers encountered: the independent inspector recommended a more conservative Quick Start-only option, but the operator request required all pages to align to Quick Start
- resolution: promoted Quick Start brand/nav values to shared shell CSS and cleared brand caption text in primary render paths
- follow-up contour: align the Overview content surface to the Quick Start density and typography without changing the shared shell
- resume from here: CLOSED
