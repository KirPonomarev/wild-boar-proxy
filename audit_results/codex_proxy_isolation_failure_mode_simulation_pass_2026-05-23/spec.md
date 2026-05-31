# Spec: CODEX_PROXY_ISOLATION_FAILURE_MODE_SIMULATION_PASS

## Objective

Simulate isolated Codex engine proxy success/failure modes with mandatory temp `HOME` and `CODEX_HOME`, proving safe failure boundaries for the current Codex.

## In Scope

- Main Codex metadata/hash sentinel.
- Temp isolated `HOME` and `CODEX_HOME`.
- Mock proxy success/failure drills.
- Optional real WBP minimal smoke with sandbox-scoped auth if available.
- Rollback, redaction, and independent audit.

## Out of Scope

- Main/current Codex proxying.
- Writes to `~/.codex`.
- GUI Desktop automation.
- Real WBP shutdown.
- Web UI wiring.
- Long work session or load testing.

## Constraints

- Canon order: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, STATE_SCHEMA.md, COMMAND_API.md, DELIVERY_RULES.md, README.md, WORKFLOW_OS_V1_2.md, AGENTS.md.
- Config model must be Codex-facing `gpt-5.3-codex`.
- Provider-native `deepseek-chat` is forbidden as Codex config model.
- No success from timeout, exit code alone, or narrative.

## Acceptance Criteria

- [x] isolated `HOME` and `CODEX_HOME` created under `/tmp`.
- [x] current auth was not copied for mock tests.
- [x] sandbox auth copy, if used for real WBP, was temporary and removed.
- [x] failures were not reported as success.
- [x] `~/.codex/auth.json` and `~/.codex/config.toml` hashes unchanged.
- [x] temp root removed.
- [x] redaction audit clean.
- [ ] mock success returned machine-backed OK.

## Verification

- tests: live bounded `codex exec --json` against temp mock and optional WBP.
- build: not applicable, no production code changed.
- manual: artifacts inspect failure matrix and rollback proof.
- live evidence: `failure_mode_matrix.json`, `mock_proxy_results.json`, `real_wbp_results.json`.

## Open Questions

- What exact Codex 0.133 `GET /v1/responses` streamable handshake must mock implement for local success without WBP?
