# UI_WEB_ACCOUNTS_ONBOARD_MODAL_GATE closeout

Date: 2026-05-13

## Summary

Implemented bounded `onboard_account` for the web design Accounts screen. The browser submits only `ui_action`; the server maps the request to exact `accounts onboard --json`, rejects browser-supplied auth/path/credential/backend fields, and summarizes the owner packet without making UI truth authoritative.

## Scope Check

Included:
- Adapter spec for `accounts_onboard`.
- Live server metadata for `onboard_account`.
- Safe onboarding outcome summary for reserve-first proof, no-new-auth, ambiguous identity, failed proof steps, command errors, and unknown outcomes.
- Minimal Add Account modal entry point.
- Tests covering adapter, server, payload rejection, outcome classification, and static UI guards.

Excluded:
- Manual auth file picker.
- Browser path/source-dir/credentials/backend-id input.
- Direct auth directory, state, or log reads.
- Desktop auth automation.
- Auto-promotion after onboarding.
- Import existing.
- Runtime changes.
- Global confirmation system redesign.
- Visual parity polish.

## Canon Check

- `accounts onboard --json` remains the owner command surface.
- Reserve-first success is shown only when owner packet proof is present.
- No-new-auth and ambiguous identity are not green success.
- UI does not infer success from external process exit code or partial nested fields.
- Browser payload remains structured and bounded.
- Post-action visible truth is refreshed from accounts readonly JSON.
- `runtime.py` was not touched by this contour.

## Verification

Targeted suite:

```text
python3 -m unittest tests.test_web_design_command_adapter tests.test_web_design_live_server tests.test_web_design_ui
Ran 61 tests
OK
```

Full discovery:

```text
python3 -m unittest discover -s tests -p 'test*.py'
Ran 555 tests
OK
```

Checks:
- JSON artifact validation passed.
- `git diff --check` passed.
- Service-marker scan passed with no matches.
- Sensitive scan over contour files passed with no matches.
- Independent audit found no findings for the scoped contour.
- Dirty-tail files remain out-of-contour and must remain unstaged.

## Notes

The worktree still contains a pre-existing dirty tail outside this UI contour, including `wild_boar_proxy/runtime.py` and external lab files. Those files are excluded from this contour commit and remain for `WORKTREE_TAIL_ADJUDICATION`.
