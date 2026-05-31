# GPT_ACCOUNTS_POOL_PACKET_AND_SELECTION_DRY_RUN_PASS

## Contour Capsule

- Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`
- Contour: `GPT_ACCOUNTS_POOL_PACKET_AND_SELECTION_DRY_RUN_PASS`
- Date: 2026-05-23
- Mode: non-live dry-run implementation and verification
- Scope: Codex Custom account packet adapter, server-side selection dry-run, web panel rendering, forbidden browser field guard

## Goal

Prove that the WBP web UI can display GPT account pool packet facts and run a server-owned account selection dry-run without claiming live account truth, inference, provider calls, token burn, or current Codex mutation.

## Canonical Basis

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`
8. `WORKFLOW_OS_V1_2.md`
9. `AGENTS.md`

## In Scope

- `GET /api/codex/custom/accounts`
- `GET /api/codex/custom/account-selection`
- `POST /api/codex/custom/account-smoke-dry-run`
- browser payload limited to server-issued `model_id`
- account/backend ids redacted from Codex Custom account packets
- explicit negative claims:
  - `live_account_truth_checked=false`
  - `live_selection_proven=false`
  - `inference_proven=false`
  - `responses_called=false`
  - `chat_completions_called=false`
  - `provider_called=false`
  - `network_calls_made=false`
  - `account_mutation_performed=false`
  - `token_burn=0`

## Out Of Scope

- live WBP status/healthcheck/accounts commands
- real account validation
- real GPT account inference
- provider/API calls
- session manager live prompt work
- account mutation
- legacy `web_ui.py` cleanup

## Declared Write Surfaces

- `wild_boar_proxy/codex_account_selection.py`
- `wild_boar_proxy/codex_custom_sessions.py`
- `wild_boar_proxy/web_design_ui/index.html`
- `wild_boar_proxy/web_design_ui/scripts/overview.js`
- `tests/test_codex_account_selection.py`
- `tests/test_web_design_live_server.py`
- `tests/test_web_design_ui.py`
- `audit_results/gpt_accounts_pool_packet_and_selection_dry_run_pass_2026-05-23/*`

## Forbidden Write Surfaces

- current `~/.codex`
- runtime auth files
- live account registry state
- external provider credentials
- `/Applications/Codex.app`

