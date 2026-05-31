<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Single Exact Text Safe Apply

## Objective

Enable one bounded `apply_exact_text_change` path for one admitted exact-text
 review item by consuming server-owned preflight truth, writing at most one
 file, returning a narrow success receipt, and keeping all blocked paths
 zero-write.

## In Scope

- command-bus enablement for `apply_exact_text_change`
- single-file exact-text mutation through one bounded helper
- exact-only duplicate/no-match blocking, including overlapping duplicates
- single-file rollback snapshot proof
- post-apply in-memory review-surface refresh
- command-bus/session-store atomicity for the apply success path

## Out of Scope

- structural apply
- approximate or fallback matching
- multi-item or multi-scene apply
- import-contract redesign
- query-schema redesign
- UI changes
- general recovery framework expansion

## Constraints

- `apply_exact_text_change` may consume only server-owned preflight truth
- blocked paths must perform zero writes
- success path may mutate at most one file
- default live-server POST apply must still require explicit server-owned apply
  context
- review session updates must not race file writes into disk/state divergence

## Assumptions

- `CONTOUR_04A` preflight truth remains authoritative for target resolution
- one-file exact-text mutation is sufficient for the first useful release scope
- in-memory review-session refresh is enough after successful apply

## Acceptance Criteria

- [x] one admitted exact-text item applies through the command bus
- [x] blocked matrix stays honest for preflight-required, closed-session,
  stale-baseline, no-match, and duplicate-match paths
- [x] overlapping duplicates such as `ababa` / `aba` block as ambiguous
- [x] default live-server POST apply is not auto-enabled by repo-local default
  apply context discovery
- [x] apply success path holds store/update atomicity against concurrent clear or
  re-import
- [x] targeted tests and adjacent regressions pass

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_review_bridge_command_bus tests.test_review_bridge_live_server tests.test_review_bridge_apply_admission tests.test_review_bridge_packet_import`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_web_design_command_adapter tests.test_web_design_live_server`
- build:
  - `python3 -m py_compile wild_boar_proxy/review_bridge_exact_text_apply.py wild_boar_proxy/review_bridge_command_bus.py wild_boar_proxy/review_bridge_session_store.py wild_boar_proxy/web_design_live_server.py tests/test_review_bridge_command_bus.py tests/test_review_bridge_live_server.py`
  - `git diff --check`
- manual:
  - not run
- live evidence:
  - `audit_results/single_exact_text_safe_apply_pass_2026-05-24/evidence/apply_packets.json`
  - `audit_results/single_exact_text_safe_apply_pass_2026-05-24/evidence/verification_summary.json`
  - `audit_results/single_exact_text_safe_apply_pass_2026-05-24/evidence/independent_audit_report.json`
