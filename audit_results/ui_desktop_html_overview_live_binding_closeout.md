# UI_DESKTOP_HTML_OVERVIEW_LIVE_READ_BINDING Closeout

## Result

The desktop HTML overview now has an explicit live-read snapshot path. Browser
JavaScript does not execute commands. It only renders either synthetic fixtures
or a generated live snapshot admitted by source marker.

## What Changed

- Added `wild_boar_proxy/desktop_ui/live_overview.py`.
- Added a git-ignored live snapshot directory for local generated JSON.
- Added `mode=live` browser rendering for admitted live snapshots.
- Preserved fixture mode as the default static preview path.
- Disabled/deferred mutating UI controls in live mode.
- Added tests for live read command selection, no stale-green behavior, private
  path sanitization, desired/effective mismatch, and rotation no-claim behavior.

## Scope Check

- `runtime_core_changed`: no
- `cli_changed`: no
- `web_ui_changed`: no
- `ui_shell_changed`: no
- `browser_command_execution_added`: no
- `mutating_ui_actions_enabled`: no
- `direct_state_or_log_truth_added`: no
- `scale_or_pilot_claim_added`: no

## Verification

- `python3 -m unittest -q tests.test_desktop_ui_overview_live_binding tests.test_desktop_ui_static tests.test_desktop_ui_command_adapter` passed, 27 tests.
- `python3 -m py_compile wild_boar_proxy/desktop_ui/live_overview.py wild_boar_proxy/desktop_ui/command_adapter.py tests/test_desktop_ui_overview_live_binding.py tests/test_desktop_ui_static.py tests/test_desktop_ui_command_adapter.py` passed.
- `python3 -m wild_boar_proxy.desktop_ui.live_overview --output /tmp/wbp_overview_live_snapshot.json` passed.
- `python3 -m json.tool /tmp/wbp_overview_live_snapshot.json` passed.
- Private path scan over the generated live snapshot found no `auth_ref`,
  `/Users/`, `~/.codex`, `supervisor-state`, or `backend-registry`.
- Safety scan over `wild_boar_proxy/desktop_ui` source found no forbidden
  `shell=True`, direct state/log fallback markers, deferred rollout/stage
  command strings, or `auth_ref` exposure.
- Headless Chrome rendered `index.html?mode=live` at `1600x1000` and saved
  `audit_results/ui_desktop_html_overview_live_binding_screenshot.png`.

## Observed Live Snapshot

- `fixture_state`: `degraded`
- `desired_mode`: `managed`
- `effective_mode`: `stable`
- `mode_mismatch`: `true`
- `rotation_adapter_status`: `command_error`
- `rotation_proof_claim`: `not_claimed`

This is intentionally not green because the UI must not show full managed
success when desired/effective mode mismatch and rotation contradiction are
visible.

## Residual Risk

This contour does not enable live mutating actions. It also does not create a
packaged desktop renderer bridge. Live browser rendering currently depends on a
pre-generated local snapshot file.

## Next

Open `UI_DESKTOP_HTML_OVERVIEW_ACTION_WIRING` only after review and merge.
