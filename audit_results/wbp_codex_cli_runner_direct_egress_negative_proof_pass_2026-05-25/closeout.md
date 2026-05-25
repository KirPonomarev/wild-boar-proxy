# WBP_CODEX_CLI_RUNNER_DIRECT_EGRESS_NEGATIVE_PROOF_PASS_R2 Closeout

## Goal

Resolve the blocked gate from the CLI runner contour by proving, or honestly classifying, direct non-WBP model egress behavior for the bounded `CODEX_CLI_RUNNER_VIA_WBP` lane.

## Result

- status: PASS
- final verdict: `CODEX_CLI_RUNNER_DIRECT_EGRESS_NEGATIVE_PROOF_PROVEN`
- closure state: CLOSED

## Contour Capsule

- goal: prove the CLI runner egress gate with bounded owner-side process/network observation, without widening into native work or general observability architecture
- branch: `codex/external-agent-lab-isolated`
- head: `f9ad7ce0ab6783f4bd20bd51ae4f3f62d07a55bd`
- touched files: `wild_boar_proxy/operator_surface.py`, `wild_boar_proxy/codex_custom_sessions.py`, `wild_boar_proxy/cli_runner.py`, `tests/test_operator_surface.py`, `tests/test_cli_runner.py`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/sync_gate_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/version_pinning_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_live_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_process_tree_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_network_observation_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_direct_egress_negative_packet_v2.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_wbp_trace_reconciliation_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_direct_egress_summary.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/current_codex_observation_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/independent_cli_runner_egress_audit.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/subagent_factcheck_packet.json`, `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/closeout.md`
- tests run: `python3 -m unittest tests.test_operator_surface tests.test_cli_runner tests.test_cli_token_command tests.test_repo_hygiene tests.test_closeout_resilience`; JSON parse validation on all contour evidence packets; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/closeout.md`
- blocked risks: this contour does not prove native `Codex.app`, Original via WBP, final E2E, or upstream business success for the bounded runner prompt; it closes only the direct non-WBP model egress gate
- closure state: CLOSED

## Verification

- tests: owner-side process/network observation classification, CLI runner packet surfacing, token-command coverage, repo hygiene, and closeout resilience all passed
- build: not applicable; no packaging/build contour in scope
- manual: bounded `python3 -m wild_boar_proxy codex-runner smoke --json --prompt 'Reply with exactly CLI_RUNNER_VIA_WBP_OK.'` was re-run under the new owner-side observer and produced route-backed `selected_model_id=wbp-web-primary-openrouter`, root-local allowed endpoint observation, descendant ancillary `git-remote-https` remote traffic, and unchanged targeted current `~/.codex/config.toml` / `~/.codex/auth.json`
- live verification: WBP trace still proved `POST /v1/responses` forwarding through the route-backed path; owner-side observation tied the root `codex` process to allowed local endpoints and attributed the only non-local peer to a descendant `git-remote-https` command, so direct non-WBP model egress was proven absent even though the bounded prompt itself returned upstream `HTTP 402`

## Artifacts

- spec: none; thread-only contour plan under canon
- packet: `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/cli_runner_direct_egress_summary.json`
- report: `audit_results/wbp_codex_cli_runner_direct_egress_negative_proof_pass_2026-05-25/evidence/independent_cli_runner_egress_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: not yet created at time of writing this closeout
- pushed: no at time of writing this closeout

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; owner-side observation stores pid digests, command basenames, endpoint strings, booleans, and status codes only; no raw pid, bearer, prompt body, or response body was recorded

## Notes

- blockers encountered: the first observation seam treated any non-local peer as direct model egress and could not distinguish descendant ancillary traffic; adding redacted process-tree attribution resolved that ambiguity without widening into a general observability subsystem
- resume from here: CLOSED
