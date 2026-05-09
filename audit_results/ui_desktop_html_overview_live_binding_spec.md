# UI_DESKTOP_HTML_OVERVIEW_LIVE_READ_BINDING Spec

## Contour

- `CONTOUR_ID`: `UI_DESKTOP_HTML_OVERVIEW_LIVE_READ_BINDING`
- `CONTOUR_CLASS`: `CODE_PLUS_TESTS_PLUS_VISUAL_SMOKE_PLUS_AUDIT_ARTIFACTS`
- `DATE`: `2026-05-09`
- `BASE_BRANCH`: `codex/ui-desktop-html-command-adapter-boundary`
- `WORK_BRANCH`: `codex/ui-desktop-html-overview-live-read-binding`

## Goal

Bind the desktop HTML overview to live strict JSON command packets through the
desktop command adapter without enabling mutating UI actions, direct state/log
reads, browser-side command execution, or runtime/CLI implementation changes.

## Canon Binding

- Strict JSON command packets remain UI truth.
- Invalid JSON is an integration failure.
- No false-green or stale-green status.
- Desired mode and effective mode stay separate.
- UI does not parse state files, registry files, diagnostics bundles, or logs.
- `ui_shell.py` remains fallback/control baseline.
- Wild Boar Proxy remains control layer; CLIProxyAPI remains engine.

## Write Surfaces

- `wild_boar_proxy/desktop_ui/live_overview.py`
- `wild_boar_proxy/desktop_ui/live/.gitignore`
- `wild_boar_proxy/desktop_ui/screens/overview.js`
- `wild_boar_proxy/desktop_ui/index.html`
- `wild_boar_proxy/desktop_ui/styles/overview.css`
- `wild_boar_proxy/desktop_ui/README.md`
- `tests/test_desktop_ui_overview_live_binding.py`
- `tests/test_desktop_ui_static.py`
- `audit_results/ui_desktop_html_overview_live_binding_spec.md`
- `audit_results/ui_desktop_html_overview_live_binding_packet.json`
- `audit_results/ui_desktop_html_overview_live_binding_closeout.md`
- `audit_results/ui_desktop_html_overview_live_binding_screenshot.png`

## Explicit Non-Scope

- No browser-side shell execution.
- No live mutating UI actions.
- No `runtime.py` or CLI command implementation changes.
- No `web_ui.py` changes.
- No `ui_shell.py` changes.
- No rollout/stage/policy/evidence actions exposed.
- No scale, pilot-ready, or production-ready claim.

## Live Read Seam

`live_overview.py` creates a sanitized live overview snapshot by calling only the
read command IDs admitted through `command_adapter.py`:

- `status`
- `healthcheck`
- `mode.get`
- `accounts.list`
- `rollout.rotation.inspect`

Browser JavaScript loads only an explicit snapshot file in live mode. It does
not import the Python adapter and does not execute commands.

## Runtime Data Rule

Generated live snapshots are ignored by git under:

- `wild_boar_proxy/desktop_ui/live/*.json`

Runtime/private command packets are not committed.

## Acceptance

- Fixture mode remains available.
- Live mode requires an admitted snapshot source.
- Live mode never silently falls back to fixture truth.
- Invalid packet collection renders integration failure.
- Command errors are visible and do not become green.
- Desired/effective mode mismatch is visible and degrades the overview state.
- Account list is summarized without exposing `auth_ref` or private paths.
- Rotation readout never becomes scale proof.
- Mutating buttons are disabled/deferred in live mode.
- Browser JS contains no command-surface strings.
