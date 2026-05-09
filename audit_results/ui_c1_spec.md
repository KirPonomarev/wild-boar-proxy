<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# UI_C1_BASIC_COMPANION_UI_REENTRY Spec

## Goal

Reopen the baseline companion UI lane after the earned design gate and align
the existing `ui_shell.py` implementation with the current canon-backed command
surfaces without touching `web_ui.py`, inventing new commands, or reopening an
execution-core repair lane.

## Scope

- update `wild_boar_proxy/ui_shell.py`
- update `tests/test_ui_shell.py`
- add read-only healthcheck detail support
- add read-only rotation-inspect detail support
- add stable-repair dry-run support

## Explicitly Out Of Scope

- `wild_boar_proxy/web_ui.py`
- visual redesign or rich UI polish
- installer or packaging work
- new runtime command surfaces
- stage-proof, stage-advance, policy-stage, or live-evidence UI actions
- broad docs refresh

## Acceptance Target

- baseline UI shell consumes existing strict JSON command packets only
- healthcheck and rotation inspect are available as read-only detail surfaces
- stable repair dry-run exists alongside stable repair apply
- no forbidden rollout or live-evidence actions are exposed
- verification passes with focused UI and contract tests
