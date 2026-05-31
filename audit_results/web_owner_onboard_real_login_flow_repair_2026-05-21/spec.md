# WEB_OWNER_ONBOARD_REAL_LOGIN_FLOW_REPAIR Spec

## Goal

Repair the web account connect lane so `Подключить аккаунт` no longer stays in
the sandbox synthetic-login bridge. The live web action must call the owner
onboarding surface and let the owner helper start the CLIProxyAPI Codex login
flow when no sandbox-local auth candidate exists.

## Canon Boundary

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy web remains the control layer.
- Browser payload may contain only `ui_action` for account connect.
- Browser must not provide token, password, auth file, local path, auth ref, or
  backend id.
- In the web sandbox runner, Codex login must write only to a sandbox-scoped
  auth directory.
- Success is still accepted only from `accounts onboard --json` packet truth
  plus accounts refresh proof.

## Implementation Scope

- Restore the owner helper detected-new-auth login path:
  `codex-account-onboard --once` starts `cli-proxy-api -codex-login` when no
  auth candidate exists.
- Discover the newly materialized `codex-*.json` auth artifact from the
  configured auth-dir and import it to `reserve`.
- Set `WBP_REQUIRE_SANDBOX_AUTH_DIR=1` for web sandbox actions.
- Route web `onboard_account` directly to `accounts onboard --json`.
- Update UI modal copy to describe the real owner onboarding/login flow.

## Out Of Scope

- Real provider OAuth implementation inside Wild Boar Proxy web.
- Browser callback listener owned by web.
- Browser secret/file/path intake.
- API route create/adopt.
- Desktop packaging.
- Promotion to active.
