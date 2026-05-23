# CODEX_PROXY_ISOLATION_FAILURE_MODE_SIMULATION_PASS Closeout

## Goal

Model isolated Codex engine proxy failure modes and prove the current Codex is not mutated or made dependent on WBP.

## Result

- status: closed_blocked_by_mock_protocol_incompatibility
- final verdict: isolation and rollback sentinels passed; mock success is blocked by Codex CLI mock protocol incompatibility; optional real WBP smoke returned OK
- next action: implement/verify Codex-compatible `GET /v1/responses` mock handshake or use WBP as canonical harness before `ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS`

## Contour Capsule

- goal: simulate isolated proxy failure modes with mandatory temp HOME/CODEX_HOME while preserving current Codex
- branch: codex/external-agent-lab-isolated
- head: c941093
- touched files: audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/spec.md; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/baseline_main_codex_snapshot.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/mock_proxy_results.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/real_wbp_results.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/failure_mode_matrix.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/rollback_proof.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/redaction_audit.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/independent_audit.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/proof.json; audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/closeout.md
- tests run: bounded codex exec mock matrix; optional real WBP smoke; JSON validation; redaction scan; git diff --check; python3 tools/check_closeout_resilience.py --staged-only
- blocked risks: main ~/.codex auth/config mutation; current Codex process stop; false success from failure; real WBP shutdown; provider-native model alias misuse
- next exact command: inspect mock_proxy_results.json and implement Codex-compatible GET /v1/responses streamable mock before rerunning mock success

## Verification

- tests: JSON validation passed; isolation assertions passed; redaction scan passed; git diff --check passed; python3 tools/check_closeout_resilience.py --staged-only passed
- build: not applicable because no production code changed
- manual: failure matrix, rollback proof, independent audit, and redaction audit generated
- live verification: mock endpoint was contacted by isolated Codex; real WBP smoke attempted=True and returned OK=True

## Artifacts

- spec: audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/spec.md
- packet: audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/proof.json
- report: audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/failure_mode_matrix.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending-current-contour-commit
- pushed: pending-current-contour-push

## Scope Check

- unrelated work mixed in: false
- private-data risk reviewed: true; raw auth values were not stored; mock key is fake and Authorization headers are redacted

## Notes

- blockers encountered: subagent spawn failed with `agent thread limit reached`; simple OpenAI-compatible mock is not enough for Codex CLI 0.133 because it repeatedly probes `GET /v1/responses`; isolated real WBP smoke succeeded; isolated remote plugin sync attempted chatgpt.com and received 401
- follow-up contour: CODEX_PROXY_MOCK_HANDSHAKE_REPAIR_PASS or rerun this contour after mock handshake support
- resume from here: inspect audit_results/codex_proxy_isolation_failure_mode_simulation_pass_2026-05-23/mock_proxy_results.json and implement Codex-compatible GET /v1/responses streamable handshake
