# ISOLATED_CODEX_ENGINE_WBP_ENDPOINT_E2E_PASS Closeout

## Goal

Prove a temporary isolated headless Codex engine can call WBP at `http://127.0.0.1:8318/v1` with a GPT-facing model and return exactly `WBP_OK`, without touching the current Codex profile.

## Result

- status: closed_success
- final verdict: isolated Codex engine WBP endpoint smoke passed
- next action: CODEX_CUSTOM_APP_WBP_ENDPOINT_E2E_PASS

## Contour Capsule

- goal: isolated temp HOME/CODEX_HOME + WBP endpoint + one GPT-facing Codex engine request + no current Codex mutation
- branch: codex/external-agent-lab-isolated
- head: 353ca75
- touched files: audit_results/isolated_codex_engine_wbp_endpoint_e2e_pass_2026-05-23/*
- tests run: live codex exec smoke; WBP status/healthcheck pre and post; authenticated /v1/models probe with local proxy handling disabled; redaction scan
- blocked risks: GPT provider-route proof intentionally not claimed; rotation participation not claimed because rotation inspect evidence may be stale; ambient proxy poisoning diagnosed and guarded; unsupported minimal reasoning config corrected to low
- next exact command: git diff --check && python3 tools/check_closeout_resilience.py --staged-only

## Verification

- tests: redaction audit pass; independent audit pass
- build: git diff --check pending after staging
- manual: current Codex profile hash/mtime compared before and after
- live verification: `codex exec --json` returned `WBP_OK` with exit code `0`

## Artifacts

- spec: audit_results/isolated_codex_engine_wbp_endpoint_e2e_pass_2026-05-23/spec.md
- packet: audit_results/isolated_codex_engine_wbp_endpoint_e2e_pass_2026-05-23/engine_request_proof.json
- report: audit_results/isolated_codex_engine_wbp_endpoint_e2e_pass_2026-05-23/independent_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no repo code mixed; owner runtime activation was observed/diagnosed as managed runtime state, not current Codex profile
- private-data risk reviewed: yes; runtime API key used only as process env, not written to artifacts; artifact redaction scan executed

## Notes

- blockers encountered: ambient-proxy-poisoned localhost probe; unsupported `minimal` reasoning value in temp config
- follow-up contour: CODEX_CUSTOM_APP_WBP_ENDPOINT_E2E_PASS
- resume from here: CLOSED

Close token: ISOLATED_CODEX_ENGINE_WBP_ENDPOINT_E2E_READY

Forbidden claims not made:
- GPT provider-route proof
- GUI Desktop proof
- heavy load proof
- DeepSeek-only success proof
