# Spec: WEB_DESIGN_FINISH_PASS

## Objective

Finish the web UI as a coherent operator surface without expanding runtime or
command scope.

This contour stayed inside the UI layer:

- responsive containment for narrow/mobile-ish viewports;
- stable navigation/main-column stacking;
- bounded table scrolling instead of page-level layout breakage;
- header action fit for Accounts and API Connections;
- Quick Start, Accounts, and API Connections readability across desktop and
  narrow viewports.

## In Scope

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `tests/test_web_design_ui.py`
- browser proof on fixture-backed local design server

## Out of Scope

- runtime fixes
- new owner commands
- new JSON packet fields
- new auth/provider flows
- desktop/native port work
- packaging

## Constraints

- no derived runtime truth
- no new command surfaces
- no false-green
- UI stays a managing-layer consumer of existing packets

## Assumptions

- `ACCOUNT_LIFECYCLE_ROUTING_TRUTH_HARDENING_PASS` already truthfully earned the
  design gate
- table overflow on narrow viewports is acceptable only inside explicit local
  scroll containers, never as page-level horizontal breakage

## Acceptance Criteria

- [x] narrow/mobile-ish viewports no longer collapse sidebar and main content
      into overlapping columns
- [x] Quick Start remains readable on narrow viewport
- [x] Accounts and API Connections remain navigable on narrow viewport
- [x] Accounts and API tables use bounded horizontal scroll instead of page
      overflow
- [x] header action rows fit on narrow viewports without clipping
- [x] no runtime or command-surface expansion is introduced

## Verification

- tests:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_web_design_command_adapter -q`
- build:
  - local design server via `python -m wild_boar_proxy.web_design_live_server`
- manual:
  - desktop and narrow screenshots for Quick Start, Accounts, and API
    Connections
- live evidence:
  - `audit_results/web_design_finish_pass_2026-05-22/evidence/browser-run-summary.json`
  - `audit_results/web_design_finish_pass_2026-05-22/evidence/after-pass-2/*.png`

## Open Questions

- none inside this contour scope; next product step belongs to the desktop port
  lane, not new web runtime semantics
