# Spec: ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS_WITH_REAL_WBP_HARNESS

## Objective

Prove a short deterministic headless Codex engine work session through real WBP while preserving current Codex isolation.

## In Scope

- WBP readonly/check preflight and reclear.
- Temp `HOME` and `CODEX_HOME`.
- Sandbox-scoped auth copy into temp only.
- Exactly 3 required prompts and exactly 1 restart prompt.
- Cleanup, redaction, independent audit.

## Out of Scope

- Main Codex proxying.
- GUI Desktop.
- Mock repair.
- Web UI wiring.
- Load/stress.
- Runtime repair.
- Plugin sync fix.
- Production code changes.

## Constraints

- Canon order: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, STATE_SCHEMA.md, COMMAND_API.md, DELIVERY_RULES.md, README.md, WORKFLOW_OS_V1_2.md, AGENTS.md.
- Config model is `gpt-5.3-codex`; provider-native `deepseek-chat` is not used as Codex model.
- No success from exit code alone; exact JSONL agent message required.
- No concurrency and no retries.

## Acceptance Criteria

- [x] WBP preflight acceptable.
- [x] isolated `HOME` used.
- [x] isolated `CODEX_HOME` used.
- [x] sandbox auth copied only to temp.
- [ ] prompt 1 returns exactly `OK`.
- [ ] prompt 2 returns exactly `WBP`.
- [ ] prompt 3 returns exactly `{"status":"ok"}`.
- [ ] restart prompt returns exactly `12345`.
- [x] main `~/.codex/auth.json` unchanged.
- [x] main `~/.codex/config.toml` unchanged.
- [x] temp dirs removed.
- [x] redaction audit clean.

## Verification

- tests: bounded live Codex exec prompts through WBP.
- build: not applicable, no production code changed.
- live evidence: `work_session_results.json`, `restart_proof.json`, `wbp_reclear.json`.

## Open Questions

- Plugin sync warning guard belongs to a separate contour if warnings remain noisy.
