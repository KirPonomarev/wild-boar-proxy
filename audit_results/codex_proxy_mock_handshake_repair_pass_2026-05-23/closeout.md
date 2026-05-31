# CODEX_PROXY_MOCK_HANDSHAKE_REPAIR_PASS Closeout

## Goal

Repair or honestly block the local mock handshake for Codex CLI while preserving current Codex isolation.

## Result

- status: closed_blocked_by_codex_private_handshake
- final verdict: three bounded variants failed; classify as Codex private handshake for mock purposes
- next action: use real WBP as canonical harness; production-grade upgrade mock requires separate approval

## Contour Capsule

- goal: test up to three local mock variants for Codex CLI `GET /v1/responses` handshake without touching real WBP or main Codex
- branch: codex/external-agent-lab-isolated
- head: 028e07b
- touched files: audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/spec.md; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/baseline_main_codex_snapshot.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/request_trace.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/mock_handshake_matrix.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/failure_mode_results.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/rollback_proof.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/redaction_audit.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/independent_audit.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/proof.json; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/closeout.md; audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/evidence/mock_harness_summary.md
- tests run: bounded Codex mock variant run; JSON validation; isolation assertions; redaction scan; git diff --check; python3 tools/check_closeout_resilience.py --staged-only
- blocked risks: real WBP execution; current auth copy; sandbox auth copy; main ~/.codex auth/config mutation; timeout false-green; more than 3 variants
- next exact command: start ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS_WITH_REAL_WBP_HARNESS

## Verification

- tests: JSON validation passed; mock handshake assertions passed; git diff --check passed; python3 tools/check_closeout_resilience.py --staged-only passed
- build: not applicable because no production code changed
- manual: request trace and mock matrix generated from live bounded Codex runs
- live verification: real WBP executed=false; variants attempted=3; success_variant=none

## Artifacts

- spec: audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/spec.md
- packet: audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/proof.json
- report: audit_results/codex_proxy_mock_handshake_repair_pass_2026-05-23/mock_handshake_matrix.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending-current-contour-commit
- pushed: pending-current-contour-push

## Scope Check

- unrelated work mixed in: false
- private-data risk reviewed: true; Authorization redacted and only fake mock auth used

## Notes

- blockers encountered: subagent spawn failed with `agent thread limit reached`; Codex mock remained incompatible after 3 variants; trace shows `Connection: Upgrade` on `GET /v1/responses`
- follow-up contour: ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS_WITH_REAL_WBP_HARNESS
- resume from here: ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS_WITH_REAL_WBP_HARNESS
