<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Custom App Identity Backup Rollback Write Truth

## Objective

Harden backup and rollback plist writes in `custom_app_identity_repair` so the
admitted repair path no longer relies on direct non-atomic backup/restore
writes, while preserving packet truth, rollback truth, and XML plist output.

## In Scope

- Backup write in
  `wild_boar_proxy/custom_app_identity_repair.py`.
- Rollback restore writes in the same module after:
  - codesign failure
  - generic plist write/publish failure handling
- Targeted tests in `tests/test_custom_app_identity_repair.py` for:
  - backup write failure without raw exception escape
  - rollback restore failure after codesign failure
  - rollback restore failure in the generic plist-write-failure path
  - preservation of existing XML plist output

## Out of Scope

- `review_bridge_exact_text_apply.py`
- `mcp_delegate.py`
- `official_e2e_fresh_working_flow_proof_runner.py`
- Shared helper refactors outside `custom_app_identity_repair.py`
- UI, release, docs, and proof/evidence-only surfaces
- Live host-app mutation or real host-app codesign

## Constraints

- Follow canon in this order: `CANON.md`, `RUNTIME_CONTRACT.md`,
  `STATE_SCHEMA.md`, `COMMAND_API.md`, `DELIVERY_RULES.md`, `README.md`.
- Keep the contour bounded to the current runtime repair surface.
- Preserve packet contract truth and existing `machine_error_code` semantics.
- Preserve XML plist output; do not silently switch to binary plist output.

## Assumptions

- The prior contour already hardened the forward `Info.plist` write path.
- Local fixture-backed verification is sufficient for this contour.
- Backup and rollback writes can be fixed locally without shared abstractions.

## Acceptance Criteria

- [ ] Backup writes in the admitted repair path use atomic discipline.
- [ ] Rollback restore writes in the admitted repair path use atomic discipline.
- [ ] Backup and rollback failure paths return truthful packets instead of raw
      exception escape.
- [ ] Existing packet truth remains materially unchanged.
- [ ] XML plist output remains unchanged.
- [ ] Targeted tests prove backup failure truth and both rollback-restore
      failure branches.

## Verification

- tests:
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py`
  - `python3 -m pytest -q tests/test_custom_app_identity_repair.py -k 'backup_write_failure or plist_write_failure_with_restore_failure or codesign_failure_with_restore_failure or plist_fsync_failure or plist_write_failure_cleans_temp_files'`
- build:
  - `python3 -m compileall -q wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
- manual:
  - `git diff --check -- wild_boar_proxy/custom_app_identity_repair.py tests/test_custom_app_identity_repair.py`
  - direct helper probe plus `file` check to confirm XML output
  - direct fault-injection probes for backup failure and rollback-restore failure
- live evidence:
  - none in this contour

## Open Questions

- None admitted for this contour.
