# WBP_CODEX_PROVIDER_AUTH_COMMAND_CONTRACT_PASS_R2 Closeout

## Goal

Replace the bounded temp `auth.command` stub with a real server-owned WBP token command contract and prove Codex can use it safely.

## Result

- status: PASS
- final verdict: `WBP_CODEX_AUTH_COMMAND_CONTRACT_PROVEN`
- closure state: CLOSED

## Contour Capsule

- goal: prove a minimal real WBP-owned `auth.command` using existing local token machinery, without expanding into broader auth architecture
- branch: `codex/external-agent-lab-isolated`
- head: `1b1d8fbd34a9984a937142839dd4860be870a344`
- touched files: `wild_boar_proxy/cli.py`, `wild_boar_proxy/token_command.py`, `wbp_codex_auth_command.py`, `tests/test_cli_token_command.py`, `COMMAND_API.md`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/sync_gate_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/version_pinning_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/ambient_env_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/wbp_token_command_contract.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/auth_command_output_format_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/codex_auth_command_invocation_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/bearer_mapping_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/codex_provider_live_trace_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/current_codex_observation_packet.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/secret_redaction_audit.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/auth_command_contract_summary.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/independent_auth_command_audit.json`, `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/closeout.md`
- tests run: `python3 -m unittest tests.test_cli_token_command tests.test_repo_hygiene tests.test_closeout_resilience`; JSON parse validation on all contour evidence packets; `git diff --check`; `python3 tools/check_closeout_resilience.py audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/closeout.md`
- blocked risks: proof remains pinned to local `codex-cli 0.128.0`; this contour does not prove native Codex.app behavior, CLI runner productization, FILE_AUTH, Original via WBP, or generalized multi-provider auth architecture
- closure state: CLOSED

## Verification

- tests: token-command unit coverage, repo hygiene, and closeout resilience all passed; helper failure path now exits without traceback; helper direct invocation, wrong-token control, and spaced-string failure were all classified in evidence packets
- build: not applicable; no packaging/build contour in scope
- manual: verified local listener `http://127.0.0.1:8318/v1/responses` rejects no-auth requests with `401`, accepts the local listener bearer with `200`, and the repo-owned helper is executable
- live verification: a spaced shell-like `auth.command` string failed to start and yielded downstream `401`; a wrong-token executable helper was invoked and rejected with downstream `401`; the repo-owned helper path was invoked, wrote the audit stamp, reached WBP through `WbpTraceObserver`, and returned exact `WBP_PROVIDER_LIVE_OK` without changing targeted current Codex files

## Artifacts

- spec: none; thread-only contour plan under canon
- packet: `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/auth_command_contract_summary.json`
- report: `audit_results/wbp_codex_provider_auth_command_contract_pass_2026-05-25/evidence/independent_auth_command_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: not yet created at time of writing this closeout
- pushed: no at time of writing this closeout

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets store hashes, booleans, status codes, and trace metadata only; no raw bearer token was recorded

## Notes

- blockers encountered: the first real-command attempt used a spaced command string that local Codex treated as a literal executable path; the first audit also caught a helper failure-path bug and an evidence digest bug, both fixed before final audit pass
- resume from here: CLOSED
