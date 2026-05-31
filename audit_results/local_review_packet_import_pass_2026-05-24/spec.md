<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Local Review Packet Import Pass

## Objective

Admit one bounded JSON review-packet import path through the existing review
command bus, validate and adapt that packet on the main side, and expose the
imported review surface through the existing query bridge with zero manuscript
writes.

## In Scope

- bounded `review_packet` payload intake through `POST /api/review-command`
- review packet validation and adaptation on the main side
- wrong-project and stale-baseline rejection
- import through the existing `import_review_packet` command surface
- query-surface exposure of imported review data
- zero-write proof

## Out of Scope

- file-picker choreography
- renderer-owned file IO
- apply behavior
- manuscript writes
- DOCX/Word/Google claims
- UI redesign

## Constraints

- `GET /api/review-surface` stays query-only
- bounded intake path is `review_packet` payload only
- import validation/adaptation lives in main-side Python layers
- `changed_files` remains empty
- `APPLY_EXACT_TEXT_CHANGE` remains reserved and blocked

## Assumptions

- current-project truth is provided by a main-side `ReviewImportContext`
- imported review packets are bounded JSON objects with schema version 1
- packet consumers can provide the current project/baseline identifiers required
  for admission

## Acceptance Criteria

- [x] valid bounded JSON review packet is admitted
- [x] malformed packet is rejected honestly
- [x] wrong-project packet is rejected honestly
- [x] stale-baseline packet is rejected honestly
- [x] imported review surface is exposed through the query bridge
- [x] zero manuscript writes are proven
- [x] clear session still works after import
- [x] targeted tests pass
- [x] adjacent regressions pass

## Verification

- tests:
  - `python3 -m unittest -q tests.test_review_bridge_command_bus tests.test_review_bridge_live_server tests.test_review_bridge_packet_import`
  - `python3 -m unittest -q tests.test_web_design_command_adapter tests.test_web_design_live_server`
- build:
  - `python3 -m py_compile wild_boar_proxy/review_bridge_packet_import.py wild_boar_proxy/review_bridge_command_bus.py wild_boar_proxy/web_design_live_server.py tests/test_review_bridge_packet_import.py`
  - `git diff --check`
- manual:
  - not run
- live evidence:
  - `POST /api/review-command` with `{"command_id":"import_review_packet","payload":{"review_packet":...}}`
  - `GET /api/review-surface`

## Open Questions

- whether a later contour should expose a dedicated read-only import-context
  surface for project/baseline introspection
