# UI_WEB_ACCOUNTS_PROMOTE_DEMOTE_ACTION_GATE closeout

Date: 2026-05-12

## Summary

Implemented bounded `promote_account` and `demote_account` actions for the web design Accounts screen. The browser sends only `ui_action` plus `account_id`; the live server performs an `accounts list --json` preflight, checks eligibility, maps the action to an adapter allowlist entry, and executes an exact JSON command template only when eligible.

## Scope Check

Included:
- Adapter specs for `accounts_promote` and `accounts_demote`.
- Live server metadata and server-side gates for `promote_account` and `demote_account`.
- Accounts screen row buttons for reserve-to-active and active-to-reserve placement.
- Tests covering adapter metadata, command sequence, eligibility rejection, and static UI guards.

Excluded:
- Retire account.
- Onboard account.
- Desktop renderer work.
- Runtime changes.
- Direct state or log reads.
- Policy or rollout mutation.

## Canon Check

- Runtime truth still comes from strict JSON command surfaces.
- Browser payload remains structured and bounded.
- No raw argv, shell command, `command_id`, arbitrary path, or config mutation is accepted from the browser.
- Account lifecycle actions preflight through `accounts list --json`.
- Post-action UI truth is refreshed from the accounts readonly endpoint, not optimistic local state.
- `runtime.py` was not touched by this contour.

## Verification

Targeted suite:

```text
python3 -m unittest tests.test_web_design_command_adapter tests.test_web_design_live_server tests.test_web_design_ui
Ran 52 tests
OK
```

Full discovery:

```text
python3 -m unittest discover -s tests -p 'test*.py'
Ran 546 tests
OK
```

Checks:
- JSON artifact validation passed.
- `git diff --check` passed.
- Service-marker scan passed with no matches.
- Independent audit passed for the UI/account gate itself.

## Notes

The action layout can become dense when table rows have several lifecycle buttons. That is a visual stabilization follow-up, not a blocker for this bounded action gate.

The worktree still contains a pre-existing dirty tail outside this UI contour, including `wild_boar_proxy/runtime.py` and external lab files. Those files are excluded from this contour commit and remain for `WORKTREE_TAIL_ADJUDICATION`.
