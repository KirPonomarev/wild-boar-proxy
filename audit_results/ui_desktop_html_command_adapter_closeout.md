# UI_DESKTOP_HTML_COMMAND_ADAPTER_BOUNDARY Closeout

## Result

The desktop HTML command adapter boundary is implemented as a backend-side
utility at `wild_boar_proxy/desktop_ui/command_adapter.py`.

The static browser shell remains fixture-only. No live browser binding was
introduced in this contour.

## What Changed

- Added an explicit command allowlist with fixed argv construction.
- Added strict single-object JSON parsing for owner command packets.
- Added required top-level packet field validation.
- Added integration-failure handling for forbidden commands, missing args,
  invalid JSON, extra stdout, invalid packets, timeouts, and runner failures.
- Preserved top-level command error packets as visible `command_error` results.
- Updated desktop UI README with boundary rules.
- Added unit tests for adapter behavior and updated static guards so the adapter
  is the only legal subprocess boundary inside `desktop_ui`.

## Scope Check

- `runtime_core_changed`: no
- `cli_changed`: no
- `web_ui_changed`: no
- `ui_shell_changed`: no
- `browser_live_binding_added`: no
- `direct_state_or_log_truth_added`: no
- `deferred_rollout_or_stage_actions_exposed`: no

## Verification

- `python3 -m unittest -q tests.test_desktop_ui_command_adapter` passed, 12 tests.
- `python3 -m unittest -q tests.test_desktop_ui_static` passed, 7 tests.
- `python3 -m unittest -q tests.test_desktop_ui_command_adapter tests.test_desktop_ui_static` passed, 19 tests.
- `python3 -m py_compile wild_boar_proxy/desktop_ui/command_adapter.py tests/test_desktop_ui_command_adapter.py tests/test_desktop_ui_static.py` passed.
- Safety scan over `wild_boar_proxy/desktop_ui` source files found no forbidden
  `shell=True`, direct state/log fallback markers, or deferred rollout/stage
  command strings.
- CLI help checks confirmed the selected root and subcommand surfaces exist.
- `python3 -m wild_boar_proxy status --json` returned a valid owner packet with
  the required top-level fields.

## Residual Risk

This contour does not prove live command packets against the current operator
environment. It intentionally stops before live binding. The next contour must
bind overview data through this adapter and prove visible failure states without
stale-green success.

## Next

Open `UI_DESKTOP_HTML_OVERVIEW_LIVE_BINDING` after review and merge.
