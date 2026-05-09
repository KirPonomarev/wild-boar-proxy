# UI_DESKTOP_HTML_OVERVIEW_ACTION_RUNNER Closeout

## Result

The backend-only overview action runner is implemented at
`wild_boar_proxy/desktop_ui/overview_actions.py`.

It accepts admitted action IDs, requires confirmation for admitted actions,
executes through `command_adapter.py`, and regenerates the live overview snapshot
after action execution.

## What Changed

- Added admitted overview action specs for stable/managed switch, sync, launch
  client, and smoke test.
- Added deferred action handling for stable repair, accounts, diagnostics,
  rollout/stage/policy/evidence, and stable target switch families.
- Added strict JSON packets for confirmation-required, deferred, forbidden,
  command-error, integration-failure, and refresh-failure cases.
- Added tests for action admission, confirmation, deferred action blocking,
  command error handling, invalid JSON handling, and post-action refresh failure.
- Documented that browser buttons remain deferred until a separate bridge
  contour.

## Scope Check

- `runtime_core_changed`: no
- `cli_changed`: no
- `web_ui_changed`: no
- `ui_shell_changed`: no
- `browser_click_wiring_added`: no
- `renderer_bridge_added`: no
- `live_mutating_smoke_run`: no
- `direct_state_or_log_truth_added`: no

## Verification

- `python3 -m unittest -q tests.test_desktop_ui_overview_actions tests.test_desktop_ui_overview_live_binding tests.test_desktop_ui_command_adapter tests.test_desktop_ui_static` passed, 38 tests.
- `python3 -m py_compile wild_boar_proxy/desktop_ui/overview_actions.py wild_boar_proxy/desktop_ui/live_overview.py wild_boar_proxy/desktop_ui/command_adapter.py tests/test_desktop_ui_overview_actions.py tests/test_desktop_ui_overview_live_binding.py tests/test_desktop_ui_static.py` passed.
- `switch_stable` without confirmation emitted strict JSON with
  `CONFIRMATION_REQUIRED` and did not execute adapter.
- `stable_repair_apply` emitted strict JSON with `ACTION_DEFERRED` and did not
  execute adapter.
- Safety scan over `wild_boar_proxy/desktop_ui` source found no forbidden
  `shell=True`, direct state/log fallback markers, deferred rollout/stage
  command strings, or `auth_ref` exposure.

## Residual Risk

This contour does not connect browser buttons to the runner. That remains a
separate bridge contour.

## Next

Open `UI_DESKTOP_HTML_OVERVIEW_ACTION_BRIDGE` only after review and merge.
