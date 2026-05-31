# UI_WEB_ACCOUNTS_RETIRE_ACTION_GATE closeout

Date: 2026-05-12

## Summary

Implemented bounded `retire_account` for the web design Accounts screen. The browser sends only `ui_action` plus `account_id`; the live server performs an `accounts list --json` preflight, blocks invalid or already-retired targets before lifecycle execution, and maps eligible requests to the exact `accounts retire <id> --json` adapter template.

## Scope Check

Included:
- Adapter spec for `accounts_retire`.
- Live server metadata and server-side gate for `retire_account`.
- Accounts screen row action for terminal lifecycle retirement.
- Tests covering adapter metadata, command sequence, payload rejection, eligibility rejection, and static UI guards.

Excluded:
- Reactivation.
- Delete or auth file deletion.
- Onboarding.
- Desktop renderer work.
- Runtime changes.
- Direct state or log reads.
- Policy or rollout mutation.
- Global confirmation system redesign.

## Canon Check

- Runtime/account truth still comes from strict JSON command surfaces.
- Browser payload remains structured and bounded.
- No raw argv, shell command, browser `command_id`, arbitrary path, or config mutation is accepted from the browser.
- Account lifecycle actions preflight through `accounts list --json`.
- Retirement is treated as terminal lifecycle retirement, not demotion, deletion, or reactivation.
- Post-action UI truth is refreshed from the accounts readonly endpoint, not optimistic local state.
- `runtime.py` was not touched by this contour.

## Verification

Targeted suite:

```text
python3 -m unittest tests.test_web_design_command_adapter tests.test_web_design_live_server tests.test_web_design_ui
Ran 55 tests
OK
```

Full discovery:

```text
python3 -m unittest discover -s tests -p 'test*.py'
Ran 549 tests
OK
```

Checks:
- JSON artifact validation passed.
- `git diff --check` passed.
- Service-marker scan passed with no matches.
- Sensitive scan over contour files passed with no matches.
- Independent audit passed for the retire gate itself.
- Dirty-tail scope findings were adjudicated as out-of-contour and must remain unstaged.

## Notes

The worktree still contains a pre-existing dirty tail outside this UI contour, including `wild_boar_proxy/runtime.py` and external lab files. Those files are excluded from this contour commit and remain for `WORKTREE_TAIL_ADJUDICATION`.
