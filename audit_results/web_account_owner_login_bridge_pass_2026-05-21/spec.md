# Spec: WEB_ACCOUNT_OWNER_LOGIN_BRIDGE_PASS

## Objective

Add a truthful web bridge from Quick Start account connection to an owner-owned
browser login flow, then complete reserve-first onboarding through
`accounts onboard --json`.

## Canon Basis

- `CANON.md`: Wild Boar Proxy is the managing layer; `CLIProxyAPI` is the
  engine; auth flows belong to the engine/owner surface.
- `COMMAND_API.md`: `accounts onboard --json` is the reserve-first onboarding
  owner truth surface.
- `MASTER_PLAN.md`: `WEB_SAFE_ACCOUNT_CONNECT_LIVE_PASS` is the product step
  that should make account connection usable from web.

## Required Behavior

Web may:

- start an owner-owned login flow;
- open an owner-provided login URL or report an owner-started login process;
- show progress and completion state;
- run/observe `accounts onboard --json`;
- refresh `accounts-readonly`;
- show a reserve-only result after packet plus refresh truth.

Web must not:

- accept token, password, secret, auth file, local path, or `backend_id`;
- parse provider auth payloads;
- materialize auth itself;
- choose backend identity;
- show green without owner packet and refresh proof.

## Discovery Result

`STOP_AND_DIAGNOSE`: no owner-owned browser login/callback surface exists in
the current command/API surface.

Observed owner onboarding support:

- `accounts onboard --json`;
- owner helper modes `--once`, `--loop`, `--auth-ref`, `--skip-login`,
  `--non-interactive`;
- detected-new-auth mode based on sandbox-local auth file inventory.

Missing surface:

- no strict JSON owner command to start browser login;
- no owner-owned callback/session handle;
- no owner packet that returns `login_url` or login completion state;
- no browser-login admission path that can be bridged by web without becoming
  the auth owner.

## Verdict Rule

This contour can only close as success after an owner-owned browser login
surface exists and web bridges to it. In the current repo state, success would
require inventing auth/callback ownership in the web layer, which violates
canon.

## Next Required Contour

`ACCOUNT_OWNER_BROWSER_LOGIN_ADMISSION_PASS`

Goal: add the minimal owner-owned browser login admission surface with strict
JSON, sandbox-only materialization, and no browser secret/path/token intake.

