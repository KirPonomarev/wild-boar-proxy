# WBP_CODEX_CLI_RUNNER_VIA_WBP_PROOF_PASS_R2 Closeout

## Goal

Prove a practical non-native Codex CLI runner can use WBP safely without being misrepresented as native `Codex.app`.

## Result

- status: BLOCKED
- final verdict: `CODEX_CLI_RUNNER_VIA_WBP_NOT_PROVEN`
- closure state: CLOSED

## Contour Capsule

- goal: prove a bounded reusable `CODEX_CLI_RUNNER_VIA_WBP` lane with isolated `CODEX_HOME`, WBP provider routing, transcript artifact, cleanup artifact, and explicit non-native classification
- branch: `codex/external-agent-lab-isolated`
- head: `c2ef487c772fc750c9ca71f7d14fbaae74d8eaad`
- touched files: `wild_boar_proxy/cli.py`, `wild_boar_proxy/cli_runner.py`, `tests/test_cli_runner.py`, `COMMAND_API.md`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/sync_gate_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/version_pinning_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/ambient_env_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_live_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_launch_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_prompt_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_transcript_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_cleanup_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/current_codex_observation_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_direct_egress_negative_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_false_green_audit.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_summary.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/independent_cli_runner_audit.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/subagent_factcheck_packet.json`, `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/closeout.md`
- tests run: `python3 -m unittest tests.test_cli_runner tests.test_cli_token_command tests.test_repo_hygiene tests.test_closeout_resilience`; JSON parse validation on all contour evidence packets; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/closeout.md`
- blocked risks: direct-egress negative proof remained unproven with safe tooling; this contour does not prove native `Codex.app`, Original via WBP, FILE_AUTH, native strategy selection, or final E2E readiness
- closure state: CLOSED

## Verification

- tests: CLI runner unit coverage, token-command coverage, repo hygiene, and closeout resilience passed after aligning unit packet shape with live `run_wbp()` wrappers and asserting route-backed runner semantics
- build: not applicable; no packaging/build contour in scope
- manual: live `python3 -m wild_boar_proxy codex-runner smoke --json --prompt 'Reply with exactly CLI_RUNNER_VIA_WBP_OK.'` returned `status=ok`, `consumer_kind=codex_cli_runner`, `native_app_claimed=false`, `selected_model_id=wbp-web-primary-openrouter`, exact bounded response `CLI_RUNNER_VIA_WBP_OK`, `transcript_kind=service_ledger_only`, cleanup `owned_session_root_only=true`, and targeted current `~/.codex/config.toml` / `~/.codex/auth.json` unchanged
- live verification: WBP trace proved `POST /v1/responses` forwarding through the route-backed provider path and cleanup removed only the owned temp session root; a separate safe-tooling egress packet could not prove the absence of all direct non-WBP egress, so the contour remained blocked instead of claiming full pass

## Artifacts

- spec: none; thread-only contour plan under canon
- packet: `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/cli_runner_summary.json`
- report: `audit_results/wbp_codex_cli_runner_via_wbp_proof_pass_2026-05-25/evidence/independent_cli_runner_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `c2ef487c772fc750c9ca71f7d14fbaae74d8eaad`
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets store hashes, booleans, route ids, status codes, and trace metadata only; no raw bearer, prompt body, or response body was recorded

## Notes

- blockers encountered: the first runner attempt failed because `OperatorSurfaceSession.run_wbp()` returns raw wrappers while the session manager expects normalized command packets; after normalizing command packets and fixing cleanup-not-applicable semantics, the runner worked live as a route-backed lane
- resume from here: CLOSED
