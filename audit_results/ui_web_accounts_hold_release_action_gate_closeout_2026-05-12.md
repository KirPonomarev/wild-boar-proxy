# UI_WEB_ACCOUNTS_HOLD_RELEASE_ACTION_GATE Closeout

## Result

PASS with unrelated dirty worktree note.

The contour adds bounded `hold_account` and `release_account` action gates to
the web Accounts screen. It does not add promote, demote, retire, onboard,
desktop transfer, direct state/log reads, post-action sync, or runtime-core
changes.

## Implemented

- Added `accounts_hold` and `accounts_release` to the web design command
  adapter.
- Added `hold_account` and `release_account` as UI actions, not raw command
  surfaces.
- Browser payload remains bounded to `ui_action` plus `account_id` for account
  actions only.
- Server validates account id syntax and verifies the target exists through
  `accounts list --json` before hold/release.
- Server blocks hold for already-held accounts.
- Server blocks release for accounts not on manual hold.
- Server blocks hold/release for retired accounts.
- UI renders `Удержать` for non-held non-retired accounts and `Снять hold` for
  held non-retired accounts.
- Confirmation modal shows the selected account id.
- After each action, Accounts refreshes from `/api/accounts-readonly`.

## Verification

- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed.
- `python3 -m unittest -q tests.test_web_design_command_adapter` ran 17 tests,
  passed.
- `python3 -m unittest -q tests.test_web_design_live_server` ran 20 tests,
  passed.
- `python3 -m unittest -q tests.test_web_design_ui` ran 12 tests, passed.
- `python3 -m unittest -q tests.test_web_design_command_adapter tests.test_web_design_live_server tests.test_web_design_ui` ran 49 tests, passed.
- `git diff --check` passed.
- `python3 -m unittest -q` selected 0 tests and was rejected as not-success.
- Initial `python3 -m unittest discover -s tests -p 'test_*.py' -q` failed
  because `urllib` local HTTP tests were routed through the system HTTP proxy
  `127.0.0.1:10809` and received `503 Service Unavailable`.
- Test localhost helpers were updated to bypass proxy with
  `urllib.request.ProxyHandler({})`.
- Re-run `python3 -m unittest discover -s tests -p 'test_*.py' -q` ran 543
  tests in 252.863s, passed.

## Browser Smoke

Fake-runner browser smoke opened Accounts in live mode and observed:

- hold button for `acct-active`: visible and enabled
- release button for `acct-hold`: visible and enabled
- hold confirmation account: `acct-active`
- hold action status: `ok`
- hold machine code: `OK`
- hold refresh: `live refresh ok`
- release confirmation account: `acct-hold`
- release action status: `ok`
- release machine code: `OK`
- release refresh: `live refresh ok`

Recorded command sequence:

```text
accounts list --json
accounts list --json
accounts hold acct-active --json
accounts list --json
accounts list --json
accounts release acct-hold --json
accounts list --json
```

This means: initial render, hold preflight, bounded hold, post-hold refresh,
release preflight, bounded release, post-release refresh.

## Scope Check

- `runtime.py`: not staged by this contour.
- desktop transfer: not done.
- promote/demote/retire/onboard controls: not added.
- browser `command_id` or raw argv: not exposed.
- direct runtime files/logs: not read.
- action result: not promoted to runtime truth.

## Audit

Independent scoped audit passed for the product diff. The auditor noted a
nonblocking banner copy drift; the banner was updated to say hold/release are
bounded action requests instead of saying all lifecycle actions are deferred.

The worktree still contains unrelated dirty files, including `runtime.py`; they
are preserved and excluded from this contour commit.
