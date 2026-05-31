# UI Web First Screen Visual Polish Closeout

Contour: `UI_WEB_FIRST_SCREEN_VISUAL_POLISH_AND_PARITY`

## Completed

- Removed fixed `width=1600,height=1000` viewport metadata.
- Removed whole-window JS `fitPreviewToViewport` scaling.
- Replaced poster-like scaling with desktop browser containment.
- Added CSS breakpoints for narrower desktop browser windows.
- Kept `web_design_ui` isolated from runtime, command adapter, desktop shell,
  `web_ui.py`, and `ui_shell.py`.
- Preserved the sharp owner-provided boar logo.

## Verification

- `python3 -m unittest -q tests.test_web_design_ui`
  - `Ran 7 tests`
  - `OK`
- `python3 -m unittest -q tests.test_web_ui`
  - `Ran 10 tests`
  - `OK`
- `python3 -m unittest -q tests.test_ui_shell`
  - `Ran 97 tests`
  - `OK`
- `git diff --check`
  - OK
- `rg` forbidden command/runtime/state/log scan in `wild_boar_proxy/web_design_ui`
  - no matches

## Browser Check

Checked in the in-app browser at:

`http://127.0.0.1:8787/?state=healthy&polish=containment`

Observed:

- overview heading visible
- SVG icons present
- fixture warning visible
- no live command binding

Fixture state text check covered:

- `healthy`
- `degraded`
- `down`
- `stale`
- `unknown`
- `integration_failure`

Only `healthy` rendered the healthy label. `degraded`, `down`, `stale`,
`unknown`, and `integration_failure` did not render `Работает`.

## Residual Risk

Automated pixel/layout regression is still not part of the repo test suite.
Manual browser review remains required before accepting visual parity.

Very narrow browser panes can look compressed because a mobile layout system is
explicitly out of scope for this contour.

## Scope Check

- No live command execution introduced.
- No direct state/log/runtime file reads introduced.
- No `runtime.py` changes introduced by this contour.
- No old fallback UI replacement.

## Independent Audit Follow-Up

Independent audit found one orphaned CSS declaration block after the visual
patch. The orphaned declarations were removed, and the verification suite was
rerun successfully.

## Next Contour

`UI_WEB_FIRST_SCREEN_COMMAND_ADAPTER_BOUNDARY`
