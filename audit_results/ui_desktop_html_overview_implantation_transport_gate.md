# UI_DESKTOP_HTML_OVERVIEW_IMPLANTATION_TRANSPORT_GATE

## Gate Result

`TRANSPORT_GATE=RED`

## Reason

The current repository does not contain a proven safe browser-to-backend
transport for `desktop_ui`.

Observed evidence:

- Prior renderer admission selected `pywebview` only as a future spike target.
- Static overview closeout recorded that `pywebview` is not installed in the
  current environment.
- Current overview browser code can fetch fixture/live snapshot JSON files, but
  does not have a safe renderer IPC path to call Python backend functions.
- No Electron/Tauri/preload/window.pywebview-style bridge is present in the
  current `desktop_ui` implementation.

## Decision

This contour must close as:

`UI_DESKTOP_HTML_OVERVIEW_IMPLANTATION_SIMULATED`

Full browser-to-backend implantation is not claimed.

## Allowed In This Contour

- Browser request builder for fixed bridge request shapes.
- Simulated bridge response lifecycle.
- Visual marking that transport is simulated.
- Screenshots and tests proving the simulated lifecycle.

## Forbidden In This Contour

- Browser shell execution.
- Browser direct CLI execution.
- Browser direct state/log/registry reads.
- Browser-supplied command, argv, path, env, cwd, or snapshot path.
- Claiming that overview buttons are live against backend bridge.
