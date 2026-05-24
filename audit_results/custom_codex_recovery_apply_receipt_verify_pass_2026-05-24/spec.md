<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Custom Codex Recovery Apply Receipt Verify

## Objective

Add a bounded, read-only receipt verifier for Custom Codex rollback apply receipts. The verifier proves only that the latest server-owned bounded apply receipt is internally valid, provenance-bound to a ready source preflight packet, and linked to a server-owned rollback point.

This contour must not claim system recovery readiness.

## In Scope

- Contract packet builder for rollback apply receipt verification.
- GET endpoint: `/api/codex/custom/recovery/rollback-apply/receipt/verify`.
- Web UI projection of receipt verification state.
- Tests for success, missing receipt, digest mismatch, forged provenance, touched/operator/kill flags, ambiguous latest receipt, and forbidden browser fields.
- Machine-readable audit artifacts.

## Out Of Scope

- Actual rollback recovery workflow.
- Process kill, stuck process cleanup, stop custom session, or rollback state mutation.
- Credential mutation or account recovery.
- Desktop app, installer, or rich design work.

## Constraints

- WBP remains the control layer; CLIProxyAPI remains the engine.
- Original Codex and current Codex home must not be touched.
- Browser cannot supply receipt id, receipt path, artifact id, artifact path, digest, backend, route, session, pid, auth, token, API key, secret, CODEX_HOME, or HOME.
- JSON packets are the primary truth.
- No false-green: forged or ambiguous receipts must block.
- Verifier must be read-only and must not create artifact roots.

## Assumptions

- The previous bounded apply receipt writer is allowed to create `rap-*.json` receipts.
- New receipts embed the source preflight packet so `source_preflight_sha256` is verifiable.
- Existing older receipts without embedded preflight are treated as not provenance-verifiable.

## Acceptance Criteria

- [x] Success reports `verified_scope=bounded_apply_receipt_only`.
- [x] Success reports `human_summary="receipt verified · not system recovery"`.
- [x] Digest and provenance checks are explicit booleans.
- [x] Browser forbidden fields reject before read, including blank query values.
- [x] Forged receipt provenance rejects.
- [x] Ambiguous latest valid receipts reject.
- [x] Verify never writes, applies rollback, kills processes, or claims operator readiness.
- [x] Current Codex, Original Codex, and auth material touch flags remain false.

## Verification

- tests: targeted verifier tests; full recovery/session/live/UI suite; operator/adapter suite
- build: Python compile and JavaScript syntax check
- manual: independent auditor pass after fixes
- live evidence: receipt_verify_packet.json and browser_rejection_packet.json

## Open Questions

- Next contour should define stop/cleanup preflight without claiming full operator readiness.
