<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_WEB_SIDEBAR_BRAND_LOCKUP_RATIO_FIX_PASS Closeout

## Goal

Repair the Quick Start sidebar brand lockup by removing the visible technical
caption, reducing the `WILD BOAR PROXY` wordmark by about 20%, and enlarging the
boar logo by about 2.5x without touching runtime or command layers.

## Result

- status: closed
- final verdict: pass
- next action: continue with the next master-plan contour after operator review

## Contour Capsule

- goal: remove Quick Start sidebar caption, set boar logo to 180px, and reduce wordmark to 16px/20px without changing runtime or command behavior
- branch: codex/external-agent-lab-isolated
- head: 84f4723
- touched files: wild_boar_proxy/web_design_ui/scripts/overview.js; wild_boar_proxy/web_design_ui/styles/overview.css; tests/test_web_design_ui.py; audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/*
- tests run: node --check wild_boar_proxy/web_design_ui/scripts/overview.js; /usr/bin/python3 -B -m unittest tests.test_web_design_ui -q; git diff --check; browser metrics at 1600x1000
- blocked risks: visible technical caption in Quick Start sidebar, oversized wordmark, undersized boar logo, accidental Quick Start grid change, runtime/adapter scope creep
- next exact command: git status --short

## Verification

- tests: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
- tests: `/usr/bin/python3 -B -m unittest tests.test_web_design_ui -q`
- tests: `git diff --check`
- browser: `http://127.0.0.1:8765/?screen=quick-start&source=live` at `1600x1000`
- live verification: `metrics.json` shows `captionRemoved=true`, `logoApproximatelyTwoPointFiveX=true`, `brandTextReducedTwentyPercent=true`, `brandLineHeightReduced=true`, `noHorizontalOverflow=true`, `navAccessible=true`, `visibleSvgIconsZero=true`, `brokenImagesEmpty=true`, and `quickStartGridUnchanged=true`
- independent audit: pass, no findings

## Artifacts

- spec: `audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/spec.md`
- metrics: `audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/metrics.json`
- screenshot: `audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/screenshots/quick-start-sidebar-brand-lockup-ratio.png`
- independent audit: `audit_results/ui_web_sidebar_brand_lockup_ratio_fix_pass_2026-05-20/independent_audit.json`

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
- allowlist touched: no
- desktop/native bridge touched: no
- private-data risk reviewed: screenshots and metrics contain UI layout state only; no secrets, tokens, auth files, or runtime credentials are added

## Notes

- blockers encountered: early browser metric captured a transient pending caption before Quick Start stabilized
- resolution: rechecked the stable Quick Start state and stored metrics with `captionText=""` and `captionVisible=false`
- follow-up contour: add narrower viewport coverage only if the enlarged logo crowds navigation during operator review
- resume from here: CLOSED
