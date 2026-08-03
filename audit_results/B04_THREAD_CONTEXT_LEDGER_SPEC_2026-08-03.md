<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B04 Thread Context Ledger V2

## Objective

Implement the transactional shared visible-context ledger for external
actors: permitted visible messages only, redaction before persistence,
monotonic revisions and generation, event idempotency, crash recovery and
atomic compaction, per-thread isolation, TTL and size limits, mode 0600, and
exact context-digest binding per dispatch.

## In Scope

- `wild_boar_proxy/thread_context_ledger.py`: `ThreadContextLedger` with
  flock-guarded transactional appends, entry kinds (visible user messages,
  native answers, external actor outputs, binding/assignment revisions,
  redacted summaries, context digests), secret redaction, duplicate
  rejection, revision/generation monotonicity, size and TTL limits, atomic
  compaction, crash recovery of malformed/non-monotonic entries, per-thread
  isolation, deterministic content digest (metadata-free, reproducible),
  degraded/failed status surfaces
- tests: `tests/test_thread_context_ledger.py`
- B04 spec + closeout in `audit_results/`

## Out of Scope

- dispatcher integration (B05)
- workflow runner (B13)
- web UI (B14)
- hook capture wiring (physical delivery spike pending)
- any canon change (the ledger is a runtime artifact under the approved
  temp root, like codex sessions; no state-file schema change)

## Constraints

- hidden reasoning, chain-of-thought, credentials, auth/session payloads, raw
  Keychain values, cookies, and unrestricted runtime-context dumps are never
  stored
- every dispatch binds to an exact context digest; digest excludes
  wall-clock metadata so forks are reproducible
- appends are transactional (flock) and atomic (temp + fsync + replace)
- files are mode 0600; thread roots are per-thread isolated under the
  approved root

## Assumptions

- The ledger root lives under the OS temp root (`wbp-thread-context-ledgers`)
  as a runtime artifact, matching the codex sessions convention

## Acceptance Criteria

- [ ] transactional append with monotonic revision; duplicate entry id
      rejected idempotently
- [ ] secret-shaped content never persisted
- [ ] missing context digest and oversized entries produce degraded status
- [ ] size limit keeps newest entries and advances generation
- [ ] TTL prune with generation advance
- [ ] corrupt tail recovered atomically; unreadable file fails with status
- [ ] per-thread isolation; file mode 0600
- [ ] content digest reproducible across replicas with identical content
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_thread_context_ledger.py`; `make check`; `make test-core`;
  `make test-custom-stability`; `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: n/a
- live evidence: none

## Open Questions

- None blocking.
