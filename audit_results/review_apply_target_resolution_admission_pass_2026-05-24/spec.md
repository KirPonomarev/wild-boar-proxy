<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Review Apply Target Resolution Admission Pass

## Objective

Add a zero-write admission layer for future single exact-text apply by proving
server-owned target resolution truth for one imported exact-text item through the
existing review query surface.

## In Scope

- server-owned scene manifest truth for `scene_id -> scene_path`
- exact-text admission checks for `scene_id`, `before`, and `after`
- query-only `apply_preflight` packet on the review surface when an explicit
  apply context is present or a repo-local scene manifest exists
- blocked/admitted packet matrix
- zero-write proof

## Out of Scope

- actual apply enablement
- manuscript writes
- success receipts
- rollback of live writes
- UI changes
- import-contract redesign

## Constraints

- `GET /api/review-surface` stays query-only
- `apply_exact_text_change` remains blocked as `REVIEW_APPLY_NOT_ENABLED`
- browser-owned path and target fields are rejected
- no filesystem mutation occurs in the review-apply path

## Assumptions

- a server-owned scene manifest is a narrow enough truth source for this contour
- current import/session truth from Contours `01A` and `02` remains authoritative
- if no explicit apply context exists and no repo-local scene manifest is present,
  the live server must not expose `apply_preflight` by default

## Acceptance Criteria

- [x] server-owned target-resolution truth is machine-checkable
- [x] exact-text target admission is machine-checkable
- [x] blocked matrix is honest for unknown, ambiguous, stale, closed, and
  missing-field paths
- [x] query surface remains zero-write
- [x] no import-contract redesign occurs
- [x] no UI drift occurs

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_review_bridge_apply_admission tests.test_review_bridge_live_server tests.test_review_bridge_packet_import tests.test_review_bridge_command_bus`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_web_design_command_adapter tests.test_web_design_live_server`
- build:
  - `python3 -m py_compile wild_boar_proxy/review_bridge_apply_admission.py wild_boar_proxy/review_bridge_session_store.py wild_boar_proxy/web_design_live_server.py tests/test_review_bridge_apply_admission.py tests.test_review_bridge_live_server`
  - `git diff --check`
- live evidence:
  - `audit_results/review_apply_target_resolution_admission_pass_2026-05-24/evidence/preflight_packets.json`
  - `audit_results/review_apply_target_resolution_admission_pass_2026-05-24/evidence/verification_summary.json`
