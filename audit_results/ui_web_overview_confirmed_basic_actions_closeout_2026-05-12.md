# UI Web Overview Confirmed Basic Actions Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_OVERVIEW_CONFIRMED_BASIC_ACTIONS`

## Result

Implemented confirmed basic actions for the first web overview:

- `sync_runtime`
- `set_mode_stable`
- `set_mode_managed`
- `launch_smoke`

The browser still sends only `ui_action`; it never sends adapter command ids.
The server owns the mapping from `ui_action` to command adapter ids.

## Layer Check

- Action metadata is available through `/api/actions`.
- Metadata does not expose `adapter_command_id`.
- Mutating actions require confirmation.
- Smoke is represented as runtime smoke check only, not host-client launch.
- Action result panel remains separate from live overview truth.
- Post-action overview refresh uses `/api/live-readonly`.
- Desktop transfer was not started.

## Browser Smoke

Browser smoke used a fake command runner to avoid live runtime mutation.

Observed:

```text
sync_runtime -> confirmation opens
sync_runtime cancel -> action panel remains idle
sync_runtime confirm -> controlled_runtime_mutation, ok, live refresh ok
launch_smoke -> runtime_smoke_check, ok, live refresh ok
set_mode_stable -> confirmation opens, controlled_mode_mutation, ok, live refresh ok
set_mode_managed -> confirmation opens, controlled_mode_mutation, ok, live refresh ok
```

## Verification

Completed:

```text
python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter
python3 -m unittest -q tests.test_ui_shell tests.test_web_ui
git diff --check
```

Independent audit: PASS.

Residual risks:

```text
runtime.py remains dirty outside this contour and is not staged.
launch_smoke remains launch-adjacent but is explicitly scoped as check-only.
```
