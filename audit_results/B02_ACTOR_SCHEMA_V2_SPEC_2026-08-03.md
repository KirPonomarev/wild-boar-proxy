<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B02 Actor Schema V2 And Migration

## Objective

Implement the canonical multi-actor entity model (schema v2) for
`custom-agent-bindings.json` with actor definitions, slot bindings, role
assignments, registry revisions, legacy `agent_id` projection, transactional
v1 -> v2 migration with backup/rollback, stale-route guards, and session
reconciliation. Update `STATE_SCHEMA.md` and `COMMAND_API.md` in the same
contract contour with a canon-diff report.

## In Scope

- `wild_boar_proxy/actor_registry.py`: canonical v2 document model,
  validation (no secrets, stale-route guard, slot cardinality, revision
  monotonicity, legacy projection round-trip), v1 -> v2 migration via the
  state-migration transaction model, read/list surface, bounded
  binding-reference resolution for sessions
- `custom-agent-bindings.json` schema v2 write/read compatibility in
  `custom_agent_bindings.py` (legacy `agent_bindings` projection preserved
  for wire compatibility)
- `codex_custom_sessions.py` reconciliation: optional flat
  `actor_registry_*` create fields stored as a bounded
  `actor_registry_reference` on the session (fail closed on malformed input)
- new owner surfaces `actors list --json` (read) and
  `actors migrate --dry-run|--apply --json` (mutate)
- `STATE_SCHEMA.md` actor-registry section + write-surface ownership
- `COMMAND_API.md` actor registry owner surfaces
- tests: `tests/test_actor_registry.py` + affected suites
- B02 spec + closeout in `audit_results/`; `CANON_DIFF_REPORT` in the PR

## Out of Scope

- dispatcher, permission intersection, and diagnostics (B05)
- transport normalization and evidence state machine (B03)
- thread context ledger (B04)
- web UI controls for slots (B14)
- any credential migration; any change to engine runtime truth

## Constraints

- Credentials are never stored; secret-shaped fields are structurally
  rejected
- Migration is snapshot/stage/verify/switch/rollback with a real backup file
  and no partial writes
- Legacy `agent_id` wire behavior (router-hook aliases, DIP/Agent 2) must not
  regress
- Forbidden stale route `wbp-deepseek-v3` rejected in every surface
- Strict JSON command packets pass `inspect_command_packet_semantics`
- Canon files change only in this admitted contract contour with a
  canon-diff report

## Assumptions

- Existing `custom-agent-bindings.json` state files are schema v1 with
  `agent_bindings` lists; no in-the-wild v2 files exist yet
- Session create callers that omit `actor_registry_*` fields keep legacy
  behavior

## Acceptance Criteria

- [ ] v1 -> v2 migration produces a valid canonical document, writes a backup,
      and reports rollback availability
- [ ] legacy projection round-trip holds; mismatch blocks validation
- [ ] secret-shaped fields and stale routes rejected
- [ ] `actors list --json` and `actors migrate --json` emit strict packets
- [ ] session create persists `actor_registry_reference` when provided and
      fails closed on malformed input
- [ ] existing bindings/sessions/alias tests pass unchanged
- [ ] full verification green; closeout merged to `main` with canon-diff
      report

## Verification

- tests: `tests/test_actor_registry.py` (new), `test_custom_agent_bindings.py`,
  `test_agent_bindings_kimi_glm.py`, `test_codex_custom_sessions.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: CLI smoke for `actors list` / `actors migrate` (no state and
  migrated states)
- live evidence: none (synthetic contract level)

## Open Questions

- None blocking.
