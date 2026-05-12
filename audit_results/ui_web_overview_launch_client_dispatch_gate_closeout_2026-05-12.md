# UI Web Overview Launch Client Dispatch Gate Closeout

Date: 2026-05-12

Contour ID: `UI_WEB_OVERVIEW_LAUNCH_CLIENT_DISPATCH_GATE`

## Result

Implemented `launch_client_dispatch` as a guarded first-screen action.

The browser still sends only `ui_action`. It never sends `client_path` or
`command_id`.

The server owns launch availability and attaches the bounded `client_path`
internally only when a server-owned path is supplied.

## Layer Check

- `launch_client` remains disabled for ordinary adapter execution.
- Bounded dispatch requires explicit server-side `allow_disabled=True`.
- `/api/actions` exposes availability and unavailable reason.
- `/api/actions` does not expose `adapter_command_id` or the bounded path.
- Launch dispatch requires confirmation.
- Launch result is dispatch-only and remains in the action panel.
- Post-action overview truth refreshes from `/api/live-readonly`.
- Desktop transfer was not started.

## Browser Smoke

Browser smoke used a fake command runner to avoid real host-client dispatch.

Observed:

```text
without bounded path -> launch button disabled, data-available=false
without bounded path -> title says bounded launch client path is unavailable
with bounded path -> launch button enabled, data-available=true
launch click -> confirmation opens for launch_client_dispatch
confirm -> host_client_dispatch, ok, live refresh ok
```

## Verification

Completed:

```text
python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter
python3 -m unittest -q tests.test_ui_shell tests.test_web_ui
python3 -m unittest -q tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui
git diff --check
```

Independent audit: PASS.

Residual risks:

```text
runtime.py remains dirty outside this contour and is not staged.
real host-client dispatch was intentionally not executed in this contour.
```
