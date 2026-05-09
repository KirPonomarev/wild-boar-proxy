<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_C1_BASIC_COMPANION_UI_REENTRY Closeout

## Goal

Reopen the baseline companion UI shell after the earned design gate and align
it with the current canon-backed JSON command surfaces without drifting into
`web_ui.py`, rich design work, or execution-core repair.

## Result

- status: completed
- final verdict: `GO_NEXT_BOUNDED_UI_OR_INSTALLER_CONTOUR`
- next action:
  - continue with the next bounded UI or installer contour by master-plan order
- implemented in this contour:
  - read-only `healthcheck --json` detail surface in the baseline UI shell
  - read-only `rollout rotation inspect --json` detail surface in the baseline UI shell
  - `stable repair --dry-run --json` path in the baseline UI shell
- explicitly not implemented in this contour:
  - `web_ui.py` work
  - stage-proof or stage-advance UI
  - live evidence capture UI
  - rich visual polish

## Verification

- build:
  - `python3 -m py_compile wild_boar_proxy/ui_shell.py tests/test_ui_shell.py`
  - observed result: passed
- tests:
  - `python3 -m unittest -q tests.test_ui_shell`
  - observed result: `Ran 96 tests in 0.050s OK`
  - `python3 -m unittest -q tests.test_cli -k healthcheck`
  - observed result: `Ran 40 tests in 27.785s OK`
  - `python3 -m unittest -q tests.test_cli -k rollout_rotation_inspect`
  - observed result: `Ran 30 tests in 3.624s OK`
- manual:
  - `git diff --check`
  - observed result: passed
  - diff review confirmed only:
    - `wild_boar_proxy/ui_shell.py`
    - `tests/test_ui_shell.py`

## Independent Audit

- scanner: `Huygens`
  - identified the real baseline gaps:
    - no healthcheck invocation path
    - no rotation inspect invocation path
    - no stable repair dry-run path
- auditor: `Halley`
  - verdict: `SAFE`
  - decisive findings:
    - no `web_ui` touch
    - no invented command surface
    - no forbidden rollout or live-capture UI action exposure

## Scope Check

- unrelated runtime repair mixed in: no
- `web_ui.py` touched: no
- broad docs touched: no
- new truth surface invented: no
- deferred rollout controls exposed: no

## Git

- branch: `codex/ui-c1-basic-companion-ui-reentry`
- commit: `c657072` (primary artifact commit)
- pushed: yes
- pull request: `#41` draft, targeting `codex/stage20-c6-final-verification-ui-gate`

## Notes

- support/open-file actions remain a later bounded UI contour, not a blocker for
  this baseline re-entry slice
- this contour hardens the existing `ui_shell.py` path only
- visual redesign remains out of scope
