<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Desktop HTML Static Overview With Fixtures

## Objective

Create the first repo-owned desktop HTML UI implementation slice by transferring
`01_overview_dashboard` into `wild_boar_proxy/desktop_ui/` with synthetic JSON
fixtures and no live command wiring.

## In Scope

- Static overview screen.
- Local design tokens and overview CSS.
- Local `boar_mark.png` asset.
- Synthetic fixture packets for required overview states.
- Browser-openable static preview.
- Static safety tests.
- Visual screenshot evidence at `1600x1000`.

## Out Of Scope

- Live command execution.
- Command adapter implementation.
- Runtime or CLI changes.
- `web_ui.py` changes.
- `ui_shell.py` changes.
- Accounts, diagnostics, settings, or modal implementation.
- Packaging or installer work.

## Constraints

- Fixtures must be synthetic and shaped like command packets.
- Fixtures must not be generated from live state files, logs, registry files, or
  runtime files.
- The UI must not execute commands in this contour.
- The UI must not read state files or logs as truth.
- Deferred rollout and stage actions must remain absent.

## Acceptance Criteria

- [x] Overview screen exists in repo-owned desktop UI files.
- [x] `boar_mark.png` renders from a local asset.
- [x] Required fixture states exist and parse as JSON.
- [x] Fixture switching works through query parameter / JS helper without live
      commands.
- [x] No live command execution is present.
- [x] No runtime, CLI, `web_ui.py`, or `ui_shell.py` changes were made.
- [x] Screenshot evidence exists at `1600x1000`.
- [x] `pywebview` unavailability is recorded without stalling the contour.

## Verification

- tests:
  - `python3 -m unittest -q tests.test_desktop_ui_static`
  - `python3 -m json.tool` for every fixture JSON file
- build:
  - no launcher was added, so `py_compile` is not applicable.
- visual:
  - headless Chrome screenshot at `1600x1000`
- manual:
  - review screenshot against the admitted reference screen
  - confirm no live command wiring
  - confirm no direct state/log truth
- live evidence:
  - none

## Open Questions

- The next contour still needs to prove the desktop app wrapper. `pywebview` was
  unavailable in the current environment and was not installed here.
