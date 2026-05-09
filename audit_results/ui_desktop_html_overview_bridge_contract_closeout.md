# UI_DESKTOP_HTML_OVERVIEW_BRIDGE_CONTRACT Closeout

## Result

The backend bridge contract is implemented at
`wild_boar_proxy/desktop_ui/overview_bridge.py`.

It accepts only fixed operation IDs, rejects forbidden request fields, delegates
refresh to `live_overview.py`, delegates actions to `overview_actions.py`, and
returns strict JSON packets for success and failure.

## What Changed

- Added bridge operation allowlist for `refresh_overview` and
  `run_overview_action`.
- Added forbidden request field guard for command, argv, shell, path, state/log
  paths, registry path, snapshot path, env, and cwd.
- Added strict JSON CLI wrapper for bridge requests.
- Added tests for refresh, action delegation, unknown operation, forbidden
  fields, fixed snapshot path, missing action ID, action error propagation, and
  CLI JSON error output.
- Documented that browser buttons remain deferred until the full implantation
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

- `python3 -m unittest -q tests.test_desktop_ui_overview_bridge tests.test_desktop_ui_overview_actions tests.test_desktop_ui_overview_live_binding tests.test_desktop_ui_command_adapter tests.test_desktop_ui_static` passed, 47 tests.
- `python3 -m py_compile wild_boar_proxy/desktop_ui/overview_bridge.py wild_boar_proxy/desktop_ui/overview_actions.py wild_boar_proxy/desktop_ui/live_overview.py wild_boar_proxy/desktop_ui/command_adapter.py tests/test_desktop_ui_overview_bridge.py tests/test_desktop_ui_overview_actions.py tests/test_desktop_ui_overview_live_binding.py tests/test_desktop_ui_static.py` passed.
- Forbidden-field CLI smoke emitted strict JSON with
  `BRIDGE_REQUEST_FORBIDDEN_FIELD`.
- Unknown-operation CLI smoke emitted strict JSON with
  `BRIDGE_OPERATION_FORBIDDEN`.
- Safety scan over `wild_boar_proxy/desktop_ui` source found no forbidden
  `shell=True`, direct state/log fallback markers, deferred rollout/stage
  command strings, or `auth_ref` exposure.

## Residual Risk

This contour does not connect browser buttons to the bridge. The next contour
must implement the renderer/browser side of the already-defined bridge contract.

## Next

Open `UI_DESKTOP_HTML_OVERVIEW_FULL_IMPLANTATION` only after review and merge.
