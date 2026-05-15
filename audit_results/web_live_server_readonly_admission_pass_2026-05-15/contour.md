# WEB_LIVE_SERVER_READONLY_ADMISSION_PASS

## Goal

Verify that the live web server can be used as a readonly admission surface:

- the server starts cleanly;
- the four GET endpoints respond with valid JSON;
- `/api/actions` behaves as metadata-only surface;
- the UI binds to `source=live` without silently replacing live failure with fixture truth;
- no POST action or runtime mutation is executed during the contour.

## Scope

- local startup of `wild_boar_proxy.web_design_live_server`
- GET-only endpoint audit
- minimal UI binding check for `quick-start`, `overview`, and `accounts`
- controlled live failure check through in-page refresh after server shutdown
- audit artifact generation only

Out of scope:

- semantic baseline truth comparison
- sandbox preparation
- any `POST /api/action`
- any runtime/config/auth/state/log mutation

## Preflight

- `git status --short --untracked-files=no` -> clean
- `git log --oneline -n 10` -> latest contour `97b5153 Add tech gate and environment inventory audit`
- `bash tools/install_git_hooks.sh` -> hooks path configured

## Fact Summary

- Server started with:
  - `python3 -m wild_boar_proxy.web_design_live_server --host 127.0.0.1 --port 64246`
- GET endpoints confirmed:
  - `/api/live-readonly`
  - `/api/accounts-readonly`
  - `/api/api-connections-readonly`
  - `/api/actions`
- `/api/actions` returned:
  - `source = ui_action_metadata`
  - `status = ok`
  - `actions_count = 22`
  - no `adapter_command_id` leakage
  - no `launch_client_path` leakage
- UI live binding confirmed:
  - `quick-start`
  - `overview`
  - `accounts`
- Controlled failure confirmed on `accounts`:
  - after server shutdown and in-page refresh, live failure copy appeared
  - no fixture fallback copy appeared
  - no false healthy state appeared

## Interpretation

Readonly admission is usable and honest enough to proceed. The main caution is
that admitted live-action buttons remain wired in the live UI, so the next
contour must keep a strict no-POST discipline.

## Decision

- status: `GO_TO_READONLY_TRUTH_PACKET_BASELINE_PASS`
- reason:
  - GET surfaces are live and valid
  - metadata remains metadata
  - UI binds to live source honestly
  - controlled live failure did not degrade into fixture-truth
  - no mutation surface was touched
