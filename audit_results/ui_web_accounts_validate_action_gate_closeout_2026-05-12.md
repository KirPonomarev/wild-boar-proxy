# UI_WEB_ACCOUNTS_VALIDATE_ACTION_GATE Closeout

## Result

PASS with unrelated dirty worktree note.

The contour added one bounded account verification action to the web Accounts
screen. It did not add lifecycle management, desktop transfer, direct state/log
reads, or runtime-core changes.

## Implemented

- Added `accounts_validate` to the web design command adapter.
- Added `validate_account` as a UI action, not a raw command surface.
- Allowed browser payload is still bounded: `ui_action` plus `account_id` only
  for `validate_account`.
- Server validates account id syntax and verifies the target exists through
  `accounts list --json` before running `accounts validate <id> --json`.
- UI renders one `Проверить` button per account row.
- Confirmation modal shows the selected account id.
- After action completion, the Accounts screen refreshes from
  `/api/accounts-readonly`.

## Verification

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed.
- `python3 -m unittest -q tests.test_web_design_command_adapter` ran 15 tests,
  passed.
- `python3 -m unittest -q tests.test_web_design_live_server` ran 18 tests,
  passed.
- `python3 -m unittest -q tests.test_web_design_ui` ran 12 tests, passed.
- `python3 -m unittest -q tests.test_web_design_command_adapter tests.test_web_design_live_server tests.test_web_design_ui` ran 45 tests, passed.
- `python3 -m unittest discover -s tests -p 'test_*.py' -q` ran 539 tests,
  passed.
- `git diff --check` passed.
- `python3 -m unittest -q` selected 0 tests and was rejected as not-success.

## Browser Smoke

Fake-runner browser smoke opened Accounts in live mode, clicked
`validate_account` for `acct-active`, confirmed the modal, and observed:

- action status: `ok`
- machine code: `OK`
- action account: `acct-active`
- refresh: `live refresh ok`

Recorded command sequence:

```text
accounts list --json
accounts list --json
accounts validate acct-active --json
accounts list --json
```

This means: initial render, target preflight, bounded validation, post-action
refresh.

## Audit

Independent scoped audit passed for the changed UI/adapter/server/test files.

The auditor flagged worktree boundary FAIL because `wild_boar_proxy/runtime.py`
is dirty in the current worktree. That file is unrelated to this contour and is
not staged. Per repo rules, it is preserved and excluded from this commit.

## Scope Check

- `runtime.py`: not staged.
- desktop transfer: not done.
- lifecycle account actions: not added.
- browser `command_id` or raw argv: not exposed.
- direct runtime files/logs: not read.
