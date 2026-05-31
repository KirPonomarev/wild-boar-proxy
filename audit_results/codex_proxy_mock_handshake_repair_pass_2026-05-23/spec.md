# Spec: CODEX_PROXY_MOCK_HANDSHAKE_REPAIR_PASS

## Objective

Repair or honestly block the artifact-local mock proxy handshake for Codex CLI 0.133.0-alpha.1 without using real WBP or touching the current Codex profile.

## In Scope

- Baseline main Codex sentinel.
- Isolated temp `HOME` and `CODEX_HOME`.
- Local mock proxy request trace.
- Up to 3 handshake variants.
- Failure modes only after mock success.
- Rollback, redaction, independent audit.

## Out of Scope

- Real WBP execution.
- Main Codex proxying.
- GUI Desktop.
- Web UI wiring.
- Plugin sync fix.
- Production WBP/runtime changes.

## Constraints

- Canon order: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, STATE_SCHEMA.md, COMMAND_API.md, DELIVERY_RULES.md, README.md, WORKFLOW_OS_V1_2.md, AGENTS.md.
- No raw secret reads or stored auth values.
- Timeout before mock success is protocol blocker, not clean failure.
- No more than 3 protocol variants.

## Acceptance Criteria

- [ ] mock success returns machine-backed `OK`.
- [x] request traces captured with redacted Authorization.
- [x] real WBP not executed.
- [x] current auth not copied.
- [x] sandbox auth not copied.
- [x] main `~/.codex/auth.json` unchanged.
- [x] main `~/.codex/config.toml` unchanged.
- [x] temp dirs removed.
- [x] redaction audit clean.

## Verification

- tests: bounded live `codex exec --json` against three local mock variants.
- build: not applicable, no production code changed.
- live evidence: `request_trace.json`, `mock_handshake_matrix.json`.

## Open Questions

- Is the Codex CLI `GET /v1/responses` stream a private app-server/event channel that should not be emulated outside WBP?
