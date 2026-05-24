<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Rollback Apply Admission Dry-Run

## Objective

Add a machine-readable dry-run admission surface for future Codex Custom rollback apply. The contour evaluates eligibility for a later contour but does not admit, ready, or perform live rollback.

## In Scope

- `build_custom_recovery_rollback_apply_admission_dry_run_packet(...)`.
- `GET /api/codex/custom/recovery/rollback-apply/admission-dry-run`.
- UI summary row, action button, and allowlisted packet projection.
- Regression tests for missing verify, browser payload rejection, touch/secret blockers, and no live mutation flags.

## Out of Scope

- Live rollback apply.
- Filesystem/runtime/session mutation.
- Process kill.
- Operator-ready recovery.
- CLIProxyAPI engine behavior.
- Rich UI expansion.

## Constraints

- WBP remains the control layer.
- CLIProxyAPI is not involved.
- Browser payload is not admitted.
- Dry-run admission must not write to filesystem or runtime state.
- Rollback point verification is prerequisite evidence, not apply readiness.
- Current Codex, Original Codex, auth material, and secrets remain forbidden surfaces.

## Assumptions

- Prior rollback point verify contour provides manifest-bound artifact proof.
- Future live apply requires a separate contour with explicit owner, declared write surfaces, rollback expectations, and tests.

## Acceptance Criteria

- [x] Success after verified rollback point.
- [x] Block without verified rollback point.
- [x] Block browser artifact/path/digest/session input before verify/read work.
- [x] Block current Codex, Original Codex, auth, and secret touch claims inherited from verify.
- [x] Keep `rollback_apply_admitted`, `rollback_apply_ready`, `rollback_apply_performed`, and `rollback_completed` false.
- [x] Keep `filesystem_write_performed`, `process_kill_performed`, and `recovery_operator_ready` false.
- [x] UI fetches by GET and has no POST path for admission dry-run.

## Verification

- tests: 35 targeted recovery/server/UI tests; 211 recovery/session/live/UI tests; 33 operator/adapter tests
- build: py_compile and node --check
- manual: bounded local packet proof
- live evidence: rollback_apply_admission_dry_run_packet.json

## Open Questions

- The next contour must define whether any live apply admission is allowed at all, and if so which exact write surfaces and rollback expectations are admitted.
