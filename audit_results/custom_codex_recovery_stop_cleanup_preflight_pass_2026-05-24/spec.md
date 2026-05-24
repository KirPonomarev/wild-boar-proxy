<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Custom Codex Recovery Stop/Cleanup Preflight

## Objective

Add a read-only stop/cleanup preflight that proves WBP can identify a server-owned Codex Custom session eligible for future cancel and owned-root cleanup without performing those actions.

The contour must not claim live recovery, process kill readiness, rollback readiness, or operator readiness.

## In Scope

- Contract packet builder for stop/cleanup preflight.
- GET endpoint: `/api/codex/custom/recovery/stop-cleanup/preflight`.
- Minimal web projection and packet view.
- Tests for ready, no session, cleaned session, ambiguous session, browser forbidden fields, blank query fields, and no mutation.
- Independent audit.

## Out Of Scope

- Live session cancel.
- Live owned-root cleanup.
- Process kill.
- Arbitrary path cleanup.
- Rollback live readiness.
- Rich UI polish.

## Constraints

- WBP is the control layer.
- `codex_custom_sessions.py` remains authoritative for session lifecycle truth.
- The preflight must derive from `/api/codex/custom/recovery/admitted-session-actions`.
- Browser cannot provide session id, paths, process ids, backend ids, route ids, auth, token, API key, secret, CODEX_HOME, HOME, receipt id, artifact id, or digest.
- JSON packets are primary truth.
- No false-green.

## Assumptions

- Server-side session selection uses the latest non-cleaned owned session and blocks ties as ambiguous.
- Cleaned sessions are not eligible for future stop/cleanup preflight readiness.
- Future live stop/cleanup must be a separate contour with declared write surfaces.

## Acceptance Criteria

- [x] Success reports `CUSTOM_CODEX_RECOVERY_STOP_CLEANUP_PREFLIGHT_READY`.
- [x] Success reports `verified_scope=owned_custom_session_stop_cleanup_preflight_only`.
- [x] Packet source is `/api/codex/custom/recovery/admitted-session-actions`.
- [x] Forbidden browser fields reject before read, including blank query values.
- [x] Raw selected session id is redacted/omitted.
- [x] Preflight never cancels, cleans, kills, rolls back, or writes.
- [x] Operator-ready and rollback-live remain false.
- [x] Ambiguous server-side selection blocks.

## Verification

- tests: targeted and full bundled suites
- build: py_compile and node --check
- manual: independent auditor pass
- live evidence: packet artifacts in this directory

## Open Questions

- Next contour must decide whether to implement live cancel first, live cleanup first, or a two-step live surface with separate receipts.
