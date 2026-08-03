<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B02 Actor Schema V2 And Migration Closeout

## Goal

Implement the canonical multi-actor entity model (schema v2) for
`custom-agent-bindings.json` with actor definitions, slot bindings, role
assignments, registry revisions, legacy `agent_id` projection, transactional
v1 -> v2 migration with backup/rollback, stale-route guards, and session
reconciliation; update `STATE_SCHEMA.md` and `COMMAND_API.md` in the same
contract contour with a canon-diff report.

## Result

- status: implemented and verified
- final verdict: canonical actor registry schema v2 is live
  (`wild_boar_proxy/actor_registry.py`), the legacy v1 wire projection is
  preserved with a round-trip check, migration is transactional with real
  backups and rollback availability, sessions can bind to canonical registry
  revisions, and the contract canon (`STATE_SCHEMA.md`, `COMMAND_API.md`) is
  updated with a recorded digest transition
- closure state: CLOSED

## Contour Capsule

- goal: B02 actor schema v2 + migration (contract contour)
- branch: `codex/b02-actor-schema-v2`
- head: `7d312be947fc9cd709118a65cc0dcd8471124f44` (base before contour commit)
- touched files: `wild_boar_proxy/actor_registry.py` (new),
  `wild_boar_proxy/custom_agent_bindings.py`, `wild_boar_proxy/cli.py`,
  `wild_boar_proxy/codex_custom_sessions.py`, `STATE_SCHEMA.md`,
  `COMMAND_API.md`, `tests/test_actor_registry.py` (new),
  `audit_results/B02_ACTOR_SCHEMA_V2_SPEC_2026-08-03.md`,
  `audit_results/B02_ACTOR_SCHEMA_V2_AND_MIGRATION_closeout_2026-08-03.md`
- tests run: `tests/test_actor_registry.py` (23 new),
  `tests/test_custom_agent_bindings.py`, `tests/test_agent_bindings_kimi_glm.py`,
  `tests/test_codex_custom_sessions.py` (83 passed, 11 subtests); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: legacy wire compatibility (DIP/Agent 2 aliases and
  router-hook projections must not regress), secret-shaped field intake,
  stale-route acceptance, split-brain between canonical and legacy projection
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_actor_registry.py` -> `23 passed` (build/projection
    round-trip, validation negatives, read/migrate surfaces, binding
    reference, session reconciliation)
  - affected suites `test_custom_agent_bindings.py`,
    `test_agent_bindings_kimi_glm.py`, `test_codex_custom_sessions.py` ->
    `83 passed, 11 subtests passed`
  - `make check` -> green (4707 collected)
  - `make test-core` -> `551 passed, 125 subtests passed`
  - `make test-custom-stability` -> `27 passed, 5 subtests passed`
  - `make test-web-e2e` -> `616 passed, 92 subtests passed`
  - `make test-full` -> `4707 passed, 978 subtests passed`
- build:
  - `make check` (compileall + collect) green
- manual:
  - CLI smoke: `actors list --json` -> `ACTOR_REGISTRY_NOT_INITIALIZED` on
    empty state; `actors migrate --dry-run --json` -> `MIGRATION_NO_STATE`
    fail-closed on missing state
  - `git diff --check` clean
- live verification:
  - no live mutation; synthetic contract level only

## Artifacts

- spec: `audit_results/B02_ACTOR_SCHEMA_V2_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: `CANON_DIFF_REPORT` in PR #116: canon digest transition
  `73f81a8e936e130e41adc7de0c25bde1d83c2be96f2add1719960114fd2d5976` ->
  `6975b76f0d11ce1b4d90d23c72fbca6bd08a40571db6ef8e91806389f4eaea6f`;
  changed files: `STATE_SCHEMA.md` (new Actor registry section + write-surface
  ownership), `COMMAND_API.md` (required-command list + Additional actor
  registry owner surfaces)

## Git

- branch: `codex/b02-actor-schema-v2`
- commit: contour commit contains code, tests, spec, closeout, and contract
  canon updates
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (no credentials migrated; secret-shaped
  fields structurally rejected; no auth material touched)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none blocking; packet-shape rigor required adding
  `exit_code`/`liveness`/`severity`/`operator_action` to every actor-registry
  packet to satisfy `inspect_command_packet_semantics`; migration is
  explicitly separate from the agent-bindings write path (write produces v2
  canonical documents; migrate converts legacy v1 state files)
- resume from here: CLOSED
