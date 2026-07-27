<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom App Identity Atomic Write Hardening Closeout

## Goal

Retire the fixed-temp `Info.plist` write pattern in the custom-app identity
repair path and replace it with a stronger atomic write flow, without changing
packet truth, rollback truth, or plist output format.

## Result

- status: implemented and verified
- final verdict: fixed-temp plist writes were removed from the custom-app
  identity repair path, targeted failure-mode coverage was added, and the plist
  output remains XML-format compatible
- closure state: CLOSED

## Contour Capsule

- goal: custom app identity atomic write hardening
- branch: `codex/stabilize-runtime-core`
- head: `f126b4ef83fc0156d60dc683371dbe0bbee87c34` before contour commit
- touched files: `wild_boar_proxy/custom_app_identity_repair.py`, `tests/test_custom_app_identity_repair.py`, `audit_results/custom_app_identity_atomic_write_hardening_spec_2026-06-26.md`, `audit_results/custom_app_identity_atomic_write_hardening_closeout_2026-06-26.md`
- tests run: `python3 -m pytest -q tests/test_custom_app_identity_repair.py`; `python3 -m pytest -q tests/test_custom_app_identity_repair.py -k 'legacy_fixed_temp_name or plist_write_failure_cleans_temp_files_and_preserves_original or plist_fsync_failure_cleans_temp_files_and_preserves_original or codesign_failure_restores_original_plist or codesign_failure_side_effects_do_not_claim_full_rollback'`; `python3 -m compileall -q wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`; `git diff --check -- wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
- blocked risks: fixed temp-name collision, temp residue after failed write, false partial-success claim after write failure, rollback overclaim, accidental plist format drift from XML to binary
- closure state: CLOSED

## Verification

- tests:
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py` -> `12 passed in 0.32s`
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py -k 'legacy_fixed_temp_name or plist_write_failure_cleans_temp_files_and_preserves_original or plist_fsync_failure_cleans_temp_files_and_preserves_original or codesign_failure_restores_original_plist or codesign_failure_side_effects_do_not_claim_full_rollback'` -> `5 passed, 7 deselected in 0.12s`
- build:
  - `python3 -m compileall -q wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
- manual:
  - `git diff --check -- wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py` -> clean
  - helper probe through `_write_plist_atomic` rewrote the bundle id and `file` reported `XML 1.0 document text, ASCII text`
- live verification:
  - none; this contour stayed in fixture-backed verification only

## Artifacts

- spec:
  - `audit_results/custom_app_identity_atomic_write_hardening_spec_2026-06-26.md`
- packet:
  - none; this contour introduced no live packet artifact
- report:
  - independent subagent inspection confirmed the publish-failure gap and
    exposed a stale count mismatch in an early test report; the final accepted
    evidence is the local verification above

## Git

- branch: `codex/stabilize-runtime-core`
- commit: contour commit contains this closeout and the runtime/test changes
- pushed: contour branch push required after commit

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes
- live-path mutation performed: no
- shared-helper refactor introduced: no
- plist output format drift accepted: no

## Notes

- blockers encountered: the first worker patch silently switched plist writes
  to binary format and left one legacy-temp test failing; the final accepted
  diff preserved XML-format output, added an explicit legacy-temp test, and
  added publish-failure plus fsync-failure cleanup coverage
- resume from here: CLOSED
