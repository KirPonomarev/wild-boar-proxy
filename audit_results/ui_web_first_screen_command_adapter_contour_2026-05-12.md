# UI Web First Screen Command Adapter Boundary

Date: 2026-05-12

Contour ID: `UI_WEB_FIRST_SCREEN_COMMAND_ADAPTER_BOUNDARY`

## Goal

Create a bounded Python-side command adapter for the web-design first screen
without connecting the static HTML preview to live runtime execution.

## Canon Boundary

- Runtime truth remains owned by existing strict JSON command surfaces.
- The web-design first screen remains fixture-backed until a later live-binding
  contour.
- The adapter accepts structured `command_id` values only.
- Arbitrary shell strings are forbidden.
- Direct state-file, registry-file, diagnostics-bundle, or log reads are
  forbidden.
- `launch_client` remains disabled for the first screen until a separate
  confirmation/path-input contour.

## In Scope

- Add a standalone web-design command adapter module.
- Define an explicit allowlist for first-screen truth/action/support commands.
- Normalize command packets without treating exit code alone as success.
- Convert parse, packet, timeout, and forbidden-command failures into visible
  integration failures.
- Add tests for allowlist, forbidden commands, invalid packet shape, timeout,
  top-level error packet semantics, and disabled launch-client posture.

## Out Of Scope

- Live browser command execution.
- Runtime-core changes.
- `web_ui.py`, `ui_shell.py`, or `runtime.py` rewrites.
- New command surfaces.
- UI design expansion beyond the first-screen boundary.
