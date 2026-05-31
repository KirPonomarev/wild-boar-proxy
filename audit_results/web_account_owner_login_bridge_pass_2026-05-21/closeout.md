# WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS Closeout

## Goal

Bridge web account connection to an owner-owned browser login flow, then prove
reserve-first onboarding through `accounts onboard --json` and
`accounts-readonly` refresh.

## Result

- status: STOP_AND_DIAGNOSE
- verdict: the bridge cannot be implemented truthfully in the current repo
  state because there is no owner-owned browser login start/callback surface.
- next action: open `ACCOUNT_OWNER_BROWSER_LOGIN_ADMISSION_PASS`.

## Contour Capsule

- goal: verify whether web can bridge to an existing owner-owned browser login
  flow without web becoming auth owner.
- branch: `codex/external-agent-lab-isolated`
- head: `96240a8`
- touched files:
  - `audit_results/web_account_owner_login_bridge_pass_2026-05-21/*`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: owner browser login admission surface is structurally absent;
  implementing login/callback in web would mix auth-engine ownership into the
  managing layer.
- next exact command: `git commit -m "web: record owner login bridge blocker"`

## Evidence

- `CANON.md` lines 24-32: Wild Boar Proxy is the managing layer; CLIProxyAPI is
  the engine; auth flows belong to the engine.
- `COMMAND_API.md` lines 123-182: `accounts onboard --json` is the owner truth
  surface for reserve-first onboarding.
- `wild_boar_proxy/runtime.py` lines 12571-12880: `run_onboard` wraps helper
  execution and post-proofs onboarding, but does not start a browser login
  session.
- `wild_boar_proxy/sandbox_owner_helpers.py` lines 393-426: helper consumes an
  explicit auth ref or sandbox-local auth file; no browser callback/session
  flow exists.
- `tests/test_web_design_live_server.py` lines 1237-1262: web onboarding rejects
  auth/path/password/backend_id browser payloads.

## Scope Check

- no runtime behavior changed.
- no UI behavior changed.
- no browser token/password/auth/path intake added.
- no API route work mixed in.
- no desktop, packaging, or redesign work mixed in.

## Required Follow-Up

`ACCOUNT_OWNER_BROWSER_LOGIN_ADMISSION_PASS`

That contour must add the owner-owned login start/callback/materialization
surface first. After that, this bridge contour can be resumed and completed as a
real web product flow.

resume from here: `ACCOUNT_OWNER_BROWSER_LOGIN_ADMISSION_PASS`

