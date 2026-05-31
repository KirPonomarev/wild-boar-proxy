# WBP_CODEX_PROVIDER_LIVE_PROOF_MATRIX_PASS_R2 Closeout

## Goal

Prove whether the local Codex CLI can send a real `model_providers.wbp` request to the live WBP endpoint under a bounded non-native contour, classify `env_key` and `auth.command` variants, and preserve current Codex targeted surfaces.

## Result

- status: PASS
- final verdict: `WBP_CODEX_PROVIDER_LIVE_COMPATIBILITY_CLASSIFIED`
- closure state: CLOSED

## Contour Capsule

- goal: classify live Codex CLI provider compatibility against the local WBP endpoint using temp `HOME` and temp `CODEX_HOME`, with machine-backed proof for Variant A `env_key` and Variant B `auth.command`
- branch: `codex/external-agent-lab-isolated`
- head: `f0a8eea30d82521c133aa7129b06f33e91fd8ef7`
- touched files: `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/sync_gate_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/version_pinning_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/ambient_env_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/codex_provider_live_variant_matrix.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/codex_provider_live_trace_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/codex_provider_wire_compatibility_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/codex_auth_command_runtime_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/codex_auth_dependency_negative_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/codex_direct_egress_negative_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/current_codex_observation_packet.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/provider_live_summary.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/independent_provider_live_audit.json`, `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/closeout.md`
- tests run: `python3 -m json.tool` on all contour evidence packets; `python3 tools/check_closeout_resilience.py audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/closeout.md`; `git diff --check`; `python3 -m unittest tests.test_repo_hygiene tests.test_closeout_resilience`
- blocked risks: positive arrival proof is strong but general non-arrival proof is not available from the current trace surfaces; full GET `/models` compatibility through the observer surface is not classified; global remote silence is not proven because stderr showed ancillary `chatgpt.com` plugin-sync traffic even though model-path-to-WBP was proven
- closure state: CLOSED

## Verification

- tests: both live variants returned the exact expected message `WBP_PROVIDER_LIVE_OK`; JSON packet validation passed; resilience and hygiene tests passed
- build: not applicable; no source-code changes were made in this contour
- manual: verified live WBP status endpoint `http://127.0.0.1:8318/v1` was healthy before the bounded runs; verified Variant B `auth.command` invocation through a temp stamp file
- live verification: Variant A `env_key` and Variant B `auth.command` both issued real Codex CLI provider requests, both were observed by `WbpTraceObserver` forwarding to `http://127.0.0.1:8318/v1`, and both completed without targeted current Codex surface changes

## Artifacts

- spec: none; thread-only contour plan under canon
- packet: `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/provider_live_summary.json`
- report: `audit_results/wbp_codex_provider_live_proof_matrix_pass_2026-05-25/evidence/independent_provider_live_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: not yet created at time of writing this closeout
- pushed: no at time of writing this closeout

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets store hashes, redacted config shape, trace metadata, and classification outcomes only; no raw tokens or prompt bodies were recorded

## Notes

- blockers encountered: none that prevented live compatibility classification; the contour intentionally stopped before CLI productization, native app work, and FILE_AUTH implementation
- resume from here: CLOSED
