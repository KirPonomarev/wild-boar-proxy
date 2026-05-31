# UI Web Accounts Read-Only Screen Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_ACCOUNTS_READONLY_SCREEN`

## Result

Implemented the second web-preview screen, `Аккаунты`, as a read-only account
visibility surface.

The screen can render fixture account rows and live read-only account rows from
the bounded `/api/accounts-readonly` endpoint. The endpoint calls only the
allowlisted `accounts_list` adapter command and returns a minimized redacted
shape instead of raw command packets.

## Layer Check

- Browser reads accounts through `api/accounts-readonly`.
- Browser does not send `command_id`.
- Browser does not send `client_path`.
- Account lifecycle commands are not enabled in this contour.
- `accounts validate/promote/demote/hold/release/retire/onboard` remain future
  contours.
- Raw `auth_ref`, raw local paths, tokens, raw logs, and raw private dumps are
  not exposed in the accounts snapshot.
- Desktop transfer was not started.
- `runtime.py`, `web_ui.py`, and `ui_shell.py` were not changed by this contour.

## Browser Smoke

Browser smoke used a fake command runner to avoid real runtime mutation.

Observed:

```text
fixture accounts screen -> visible
overview screen -> hidden
accounts table -> present
live accounts screen -> 4 rows from fake accounts_list
registry identity -> ok · OK
private leak markers -> false
lifecycle command markers -> false
```

## Verification

Completed:

```text
node --check wild_boar_proxy/web_design_ui/scripts/overview.js
python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter
python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui
git diff --check
```

Results:

```text
targeted tests: Ran 41 tests OK
combined regression: Ran 148 tests OK
git diff --check: OK
independent audit: PASS
```

Residual risks:

```text
runtime.py remains dirty outside this contour and is not staged.
visual parity is baseline only.
account lifecycle actions are intentionally deferred.
```
