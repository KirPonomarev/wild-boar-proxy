# UI_WEB_ACCOUNT_DETAIL_CANONICAL_DRAWER_PASS Spec

## Goal

Add and harden the canonical account detail surface for the web UI so an operator
can inspect one account without broadening runtime or command surfaces.

## Scope

- Web UI only.
- Right drawer over the Accounts screen.
- Current accounts JSON is the only drawer data source.
- Account actions remain bounded to `ui_action` plus `account_id`.
- Confirmation must show account id, current pool, requested action, and expected refresh.
- Sensitive account detail text must be redacted before rendering.

## Touched Surfaces

- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/styles/overview.css`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_web_design_ui.py`
- `audit_results/ui_web_account_detail_canonical_drawer_pass_2026-05-15/*`

## Non-Scope

- No runtime engine edits.
- No command adapter edits.
- No allowlist changes.
- No live server edits.
- No desktop or native bridge work.
- No onboarding/import expansion.
- No raw log, auth file, token, secret, or direct state reads.

## Acceptance

- Account row click and menu detail open drawer without dispatching a command.
- Drawer shows identity, pool, lifecycle, hold, checks, timeline, eligible actions,
  disabled reasons, danger actions, and last command result.
- Row/menu/drawer actions use one eligibility source.
- Disabled actions render without dispatch listeners.
- Risky account actions use confirmation and account action preflight summary.
- Sensitive text in last error and timeline fields is redacted.
- Missing account after refresh shows neutral missing state.
- Browser screenshots cover account states and confirmation preflight.
- Verification commands pass.
