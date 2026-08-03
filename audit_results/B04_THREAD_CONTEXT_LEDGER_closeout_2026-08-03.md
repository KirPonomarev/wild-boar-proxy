<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B04 Thread Context Ledger V2 Closeout

## Goal

Implement the transactional shared visible-context ledger for external
actors with redaction, monotonic revisions, idempotency, TTL and size limits,
atomic compaction, crash recovery, per-thread isolation, mode 0600, and exact
context-digest binding.

## Result

- status: implemented and verified
- final verdict: `ThreadContextLedger` is live with all required properties;
  secret-shaped content is structurally redacted before persistence; the
  content digest is reproducible across replicas (metadata-free), enabling
  exact `fork` context transitions
- closure state: CLOSED

## Contour Capsule

- goal: B04 Thread Context Ledger V2
- branch: `codex/b04-thread-context-ledger`
- head: `f53c39bc3ac12b2b9e4ea12a3c04f027e7e675bd` (base before contour commit)
- touched files: `wild_boar_proxy/thread_context_ledger.py` (new),
  `tests/test_thread_context_ledger.py` (new),
  `audit_results/B04_THREAD_CONTEXT_LEDGER_SPEC_2026-08-03.md`,
  `audit_results/B04_THREAD_CONTEXT_LEDGER_closeout_2026-08-03.md`
- tests run: `tests/test_thread_context_ledger.py` (15 tests); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: secret leakage into the ledger, duplicate entries, revision
  gaps, size/TTL growth, per-thread bleed, non-reproducible digests
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_thread_context_ledger.py` -> `15 passed`
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> full local baseline green
- build:
  - `make check` (compileall + collect) green
- manual:
  - `git diff --check` clean
- live verification:
  - no live mutation; pure runtime-artifact module under the temp root

## Artifacts

- spec: `audit_results/B04_THREAD_CONTEXT_LEDGER_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: no canon change in this contour (ledger is a runtime artifact
  under the approved temp root, matching the codex sessions convention)

## Git

- branch: `codex/b04-thread-context-ledger`
- commit: contour commit contains module, tests, spec, and closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (redaction patterns cover sk- keys, bearer
  tokens, authorization headers, api keys, passwords, secrets, keychain,
  cookies; verified by tests against persisted bytes)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: digest stability required excluding wall-clock
  metadata (observed_at, revision, generation) from the content digest so a
  `fork` context transition binds to one exact reproducible digest; crash
  recovery skips malformed entries and marks the ledger degraded until atomic
  compaction rewrites the file
- resume from here: CLOSED
