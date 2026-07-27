<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Custom App Identity Atomic Write Hardening

## Objective

Harden `Info.plist` writes in `custom_app_identity_repair` so the custom-app
identity repair path no longer relies on a fixed temporary filename, while
preserving packet semantics, rollback truth, and the existing plist output
format.

## In Scope

- `_write_plist_atomic` in
  `wild_boar_proxy/custom_app_identity_repair.py`.
- A narrow local atomic-bytes helper for the plist write path only.
- Targeted tests in `tests/test_custom_app_identity_repair.py` for:
  legacy fixed-temp avoidance, temp cleanup on failure, publish-failure
  preservation, and pre-publish fsync-failure preservation.

## Out of Scope

- Shared write-helper refactors in `state_store.py`.
- Review bridge, MCP evidence, release-gate, UI, or docs expansion.
- Live-path mutation or real host-app `codesign` work.

## Constraints

- Follow canon in this order: `CANON.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- Keep the contour bounded to runtime hardening for the custom-app identity
  repair path.
- Preserve plist output format; no silent switch from XML plist to binary plist.
- Do not weaken packet truth, `changed_files` truth, rollback truth, or
  admission/codesign guards.

## Assumptions

- `Info.plist` parent directories already exist in the admitted repair path.
- The local atomic helper may mirror the existing state-store atomic pattern
  without becoming a shared cross-module API in this contour.
- Existing rollback and codesign failure tests remain authoritative for
  post-write failure behavior.

## Acceptance Criteria

- [ ] The fixed sibling temp path `.Info.plist.wbp-tmp` is no longer used for
      writes.
- [ ] The plist write path uses a unique sibling temp file, `fsync`, atomic
      replace, and temp cleanup on failure.
- [ ] Existing packet semantics stay truthful.
- [ ] The plist output remains XML-format compatible with the prior behavior.
- [ ] Targeted tests prove fixed-temp avoidance, temp cleanup, publish-failure
      preservation, and pre-publish fsync-failure preservation.

## Verification

- tests:
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py`
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py -k 'legacy_fixed_temp_name or plist_write_failure_cleans_temp_files_and_preserves_original or plist_fsync_failure_cleans_temp_files_and_preserves_original or codesign_failure_restores_original_plist or codesign_failure_side_effects_do_not_claim_full_rollback'`
- build:
  - `python3 -m compileall -q wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
- manual:
  - `git diff --check -- wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
  - helper probe plus `file` check to confirm the current output remains XML
- live evidence:
  - none in this contour

## Open Questions

- None admitted for this contour.
