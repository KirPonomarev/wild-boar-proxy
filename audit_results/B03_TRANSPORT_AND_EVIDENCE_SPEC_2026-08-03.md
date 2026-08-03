<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B03 Normalized Transport And Evidence State Machine

## Objective

Implement the normalized transport boundary (native/API/one-shot/ACP shared
surface: request envelope, stream events, final response, tool-call events,
typed errors, ambiguity/cancellation, capability negotiation, dispatch
receipts) and the normalized evidence state machine (canonical
DECLARED..PHYSICAL_VISIBLE_PROVEN taxonomy, non-empty acceptance,
distinct-milestone guard, claim guards, invalidation). Update the affected
contract canon with a canon-diff report.

## In Scope

- `wild_boar_proxy/transport_normalization.py`: normalized request/stream/
  final-response/tool-call normalization, typed error taxonomy,
  ambiguous-delivery classification, dispatch receipts; `native_primary` is a
  boundary, never a synthesized send
- `wild_boar_proxy/evidence_state_machine.py`: evidence-level taxonomy and
  ordering, immutable evidence records bound to exact identities,
  required-step validation (empty set rejected, duplicates/missing rejected,
  level minimums, candidate-SHA consistency, honesty flags), milestone
  distinctness guard, live/physical claim guards, TTL and invalidation keys
- `RUNTIME_CONTRACT.md`: Evidence levels + Normalized transport sections
  (contract contour; canon-diff report in PR)
- tests: `tests/test_transport_normalization.py`,
  `tests/test_evidence_state_machine.py`
- B03 spec + closeout in `audit_results/`

## Out of Scope

- dispatcher/assignment execution and diagnostics (B05)
- thread context ledger (B04)
- provider-specific adapters and live dispatch (B07/B08 live)
- one-shot CLI runtime (B09)
- any credential handling or engine runtime truth

## Constraints

- Credentials and raw secrets never appear in normalized envelopes, receipts,
  or evidence records
- `all([])` acceptance is structurally impossible
- ambiguous delivery is never retried and never replaced by another actor's
  response
- evidence records bind plan/stage/project identity/candidate SHA/artifact
  digest/binding and assignment revisions/adapter/context digest/
  environment-policy identity/level/timestamp/TTL/invalidation keys

## Assumptions

- The canonical taxonomy names (LIVE_PROVEN, PHYSICAL_VISIBLE_PROVEN) are
  introduced here; legacy surface adoption of the canonical names is a B06
  regression concern

## Acceptance Criteria

- [ ] normalized request/stream/response normalization with fail-closed typed
      errors
- [ ] ambiguous delivery classified separately from ok/error and never
      retried
- [ ] empty required-step set rejected; duplicates/missing/insufficient level
      rejected
- [ ] live/physical claim guards block synthetic-only claims
- [ ] stale evidence invalidated by keys and TTL
- [ ] RUNTIME_CONTRACT.md updated with canon-diff report
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: new suites; `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a (pure contract modules)
- live evidence: none

## Open Questions

- None blocking.
