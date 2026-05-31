<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Review Mutate Port And Session Store Pass

## Objective

Add the minimal main-side review mutate entrypoint for the first useful review
bridge release path without drifting into packet adaptation, UI work, or apply.

## In Scope

- review command admission contract
- main-process-owned review session store
- reserved apply refusal path
- read/query split proof through a dedicated review query surface
- targeted tests and adjacent regression verification

## Out of Scope

- packet adaptation logic
- preview rendering logic
- renderer/UI work
- manuscript write paths
- exact-text apply enablement
- markdown/docx import logic

## Constraints

- read surface stays query-only
- mutate surface goes through a bounded command bus
- renderer does not gain filesystem access
- apply remains reserved and returns `REVIEW_APPLY_NOT_ENABLED`
- no review-bridge implementation work may drift into Contour 02

## Assumptions

- the Python-side host in this repo is the main-side owner for the review bridge
- storing canonical review session fields in memory is sufficient for Contour 01A
- future contours will adapt/import external packet content before calling the
  `import_review_packet` command

## Acceptance Criteria

- [x] `IMPORT_REVIEW_PACKET` is admitted through a dedicated command bus
- [x] `CLEAR_REVIEW_SESSION` is admitted through a dedicated command bus
- [x] `GET /api/review-surface` remains query-only
- [x] review session state lives in a main-side store
- [x] `APPLY_EXACT_TEXT_CHANGE` returns `REVIEW_APPLY_NOT_ENABLED`
- [x] targeted tests pass
- [x] adjacent regressions pass

## Verification

- tests:
  - `python3 -m unittest -q tests.test_review_bridge_command_bus tests.test_review_bridge_live_server`
  - `python3 -m unittest -q tests.test_web_design_command_adapter tests.test_web_design_live_server`
- build:
  - `python3 -m py_compile wild_boar_proxy/review_bridge_session_store.py wild_boar_proxy/review_bridge_command_bus.py wild_boar_proxy/web_design_live_server.py tests/test_review_bridge_command_bus.py tests/test_review_bridge_live_server.py`
  - `git diff --check`
- manual:
  - not run; contour was verified through module and HTTP tests only
- live evidence:
  - `GET /api/review-surface`
  - `GET /api/review-commands`
  - `POST /api/review-command`

## Open Questions

- whether Contour 02 should reuse the dedicated review command bus directly or
  adapt imported packet content through a separate main-side helper first
