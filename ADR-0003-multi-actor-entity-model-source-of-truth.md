<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ADR: Multi-Actor Entity Model Is One Canonical Source Of Truth With A Legacy Projection

## Status

Proposed

## Date

2026-08-03

## Context

The WBP Multi-Actor Master Plan requires one Codex conversation to use the
native Codex/GPT lane plus up to two external actor slots (`agent_1`,
`agent_2`), where each external slot independently binds an admitted API or
CLI actor. The repository currently carries several overlapping truth
surfaces for agent identity, roles, and sessions (`custom_agent_bindings`
schema v1, `codex_custom_sessions` schema v3, router-hook runtime context,
DIP/Agent 2 aliases). A blind global rename is forbidden by the plan; the
model is expensive to reverse because every dispatch, evidence record, and
migration depends on the identity separation.

An explicit owner safety override forbids starting any Codex/Custom Codex
process and touching the main Codex profile, so physical capability spikes
for the host delivery mode are impossible in this environment. The
visible-delivery mode must therefore default to the plan's conservative
proven mode until physical proof exists.

## Decision

1. Canonical entity model. Adopt exactly five separated surfaces, never
   conflated: actor definition (capability + credential reference),
   slot binding (slot -> actor, aliases), role assignment (free-form user
   instruction, never an authority grant), transport session (adapter-bound
   provider session), and dispatch (turn/workflow-bound receipt). V1 exposes
   `primary`, `agent_1`, `agent_2`; at most two external slots in the UI.
2. Legacy projection, not rename. Preserve `agent_id` as a legacy
   wire-compatible projection. `custom_agent_bindings` schema v1 migrates to
   canonical actor/binding identities; `codex_custom_sessions` schema v3 is
   reconciled to transport-session references. `DIP`, `Agent 2`, primary
   aliases, custom aliases, exact-text and exact-JSON paths are preserved.
   Forbidden stale routes (including `wbp-deepseek-v3`) are rejected.
   Credentials are never migrated. Removal of the legacy projection is a
   separate future major migration.
3. Registry ownership. The actor/slot/binding/assignment registry is owned by
   the WBP control layer under the existing single-writer serialized mutation
   model. `CLIProxyAPI` remains the engine; the actor registry never becomes a
   second runtime truth surface.
4. Failover ownership. Provider-local account-pool failover stays owned by the
   existing pool policy. Actor routing creates no second failover truth.
   Cross-provider fallback is off by default; an unavailable actor never
   returns another actor's response under the original identity.
5. OpenRouter compatibility. OpenRouter remains a compatibility/admission
   surface, not a mandatory new-release provider. Existing OpenRouter routes
   must not regress; missing live OpenRouter proof does not block the
   DeepSeek/Kimi/GLM/Qwen core.
6. DIP behavior. The canonical router-hook surfaces (`auto-route`,
   `direct-reply`) and `tools/wbp_dip` stay the only admitted DIP lanes.
   `DIP` is an API-lane alias resolved from server-issued runtime context;
   unknown/ambiguous aliases fail closed. No wrapper shopping, no local
   imitation, no fallback chains.
7. Visible-delivery mode. Without physical proof (blocked by the owner
   safety override), V1 uses the conservative proven mode: one labelled
   answer block (`Agent 1: <exact provider output>`, `Agent 2: <exact
   provider output>`, `Codex: <native synthesis>`). The ledger stores
   separate actor messages; the product never claims multiple native UI
   participants. Automated native-primary workflow steps stay disabled until
   physically proven.
8. Ledger storage. Thread Context Ledger V2 uses a transactional store (real
   lock or SQLite transaction), monotonic revision, event idempotency,
   per-thread isolation, TTL/size limits, mode 0600, redaction before
   persistence, exact context-digest binding per dispatch, and explicit
   degraded/failure status when hook fields are unavailable.
9. CLI isolation. Every CLI adapter is server-owned with a recorded manifest
   (realpath, version, digest, argv/env allowlists, provider homes,
   process-group termination, auth strategy). Qwen uses isolated `QWEN_HOME`
   and `QWEN_RUNTIME_DIR`; Kimi uses isolated `KIMI_CODE_HOME` with OS-level
   read-only enforcement. Isolated Codex CLI (B16) is DEFERRED: the owner
   override forbids any Codex process and no separate exact owner marker
   exists.

## Alternatives Considered

1. Global `agent_id` -> `actor_id` rename with a single schema.
   Rejected: breaks legacy wire compatibility and the plan forbids it.
2. Merge actor state into the engine runtime state.
   Rejected: creates a second runtime truth surface and violates canon
   (engine vs control layer).
3. Keep the existing role/slot surfaces as parallel truth.
   Rejected: split-brain between docs and runtime is a canon violation.
4. Physical visible-delivery spike now (start Custom Codex to observe
   message rendering).
   Rejected: the owner safety override forbids starting any Codex/Custom
   Codex process; conservative mode is the honest default until physical
   proof is possible.

## Consequences

- Positive:
  - One canonical identity model with a documented migration path.
  - Legacy DIP/Agent 2/exact-answer behavior preserved without a rename.
  - No second failover or runtime truth surface.
  - Conservative visible-delivery mode keeps claims honest.
- Negative:
  - B02 migration must be transactional, idempotent, backed up, and
    rollback-proven; legacy projection adds long-term wire surface.
  - Physical visible-delivery proof remains pending for the workflow stage
    (B13) and the final audit.
- Follow-up work:
  - B02: actor schema V2 + migration (contract contour with canon-diff
    report).
  - B03: normalized transport and evidence state machine.
  - B04: Thread Context Ledger V2.
  - B05: dispatcher, assignments, permissions, diagnostics.

## Evidence

- spec: plan contract section 4 (entity model), section 5 (legacy
  compatibility), section 10 (visible-delivery truth), section 14 (CLI
  isolation); owner safety override message 2026-08-03 (main Codex air gap)
- tests: existing router-hook/DIP/alias regression suite (B06 verifies)
- runtime packet: none (decision contour; no live dispatch)
- supporting docs: `COMMAND_API.md` router-hook sections, `CANON.md`
  boundary rule, `STATE_SCHEMA.md` single-writer mutation model
