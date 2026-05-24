<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Codex Custom Recovery Rollback Point Verify

## Objective

Add a read-only verification contour for Codex Custom rollback point artifacts. The endpoint proves that an owned generated rollback point exists and is internally consistent before any future rollback-apply contour is admitted.

## In Scope

- `GET /api/codex/custom/recovery/rollback-point/verify`.
- Server-side selection of `crp-*.json` artifacts from the owned generated recovery artifact root.
- Server-side manifest `_rollback_point_manifest.json` as external provenance for the selected artifact.
- Validation of schema, artifact kind, claim scope, parseable `created_at_utc`, payload digest, file digest, source admission digest, write surface, and negative touch/secret/apply claims.
- UI rendering of allowlisted verify packet fields.
- Regression tests for stale/false-green risks.

## Out of Scope

- Applying rollback.
- Process kill readiness or process kill execution.
- Operator-ready recovery claim.
- Browser-supplied artifact id, path, digest, session id, backend, route, auth, home, or token.
- Rich UI expansion or design polish.

## Constraints

- `Wild Boar Proxy` remains the control layer; `CLIProxyAPI` remains the engine.
- JSON packet fields are the primary truth.
- Browser payload for verify is not admitted.
- Verify must not write to the filesystem.
- Current Codex home and Original Codex profile are forbidden surfaces.
- Secret-bearing values must not appear in artifacts or UI packets.

## Assumptions

- The live create contour wrote rollback point artifacts only under the owned generated recovery artifact surface.
- A verify claim is weaker than rollback readiness and does not imply rollback apply is safe.
- Manifest provenance is sufficient for this contour because the manifest is server-created and separate from the artifact payload.

## Acceptance Criteria

- [x] Verify succeeds after bounded live create.
- [x] Verify blocks without rollback point artifacts.
- [x] Verify blocks browser-supplied artifact/path/digest input before any filesystem read.
- [x] Verify blocks malformed artifacts.
- [x] Verify blocks wrong schema and wrong kind.
- [x] Verify blocks missing or invalid `created_at_utc`.
- [x] Verify blocks missing provenance, tampered provenance, wrong surface, digest mismatch, touch claims, and secret claims.
- [x] Verify blocks ambiguous latest candidate selection.
- [x] Verify packet keeps rollback apply/operator-ready/current Codex/Original Codex/auth/secret claims false.

## Verification

- tests: targeted recovery/server/UI tests, full recovery/session/live/UI tests, operator/adapter tests
- build: `python3 -m py_compile`, `node --check`
- manual: bounded local packet proof with tamper check
- live evidence: `rollback_point_verify_packet.json`

## Open Questions

- Future contour must define a separate rollback-apply admission contract before any state-changing rollback can be considered.
