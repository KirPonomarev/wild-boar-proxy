# WBP_RESPONSES_WIRE_API_COMPAT_REPAIR_PASS Closeout

## Contour Capsule

- Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`
- Contour: `WBP_RESPONSES_WIRE_API_COMPAT_REPAIR_PASS`
- Status: `passed_guard_repair`
- Close token: `WBP_RESPONSES_WIRE_API_COMPAT_REPAIRED`
- Branch: `codex/external-agent-lab-isolated`
- Start head: `ae72f7ad`
- head: `ae72f7ad` before this contour; final commit hash is recorded in the operator final note.
- Goal: repair repo-owned `/v1/responses` trace/wire compatibility defects without rerunning Codex Custom live prompt.
- Changed files: `wild_boar_proxy/operator_surface.py`; `tests/test_operator_surface.py`; `audit_results/wbp_responses_wire_api_compat_repair_pass_2026-05-24/*`
- touched files: `wild_boar_proxy/operator_surface.py`; `tests/test_operator_surface.py`; `audit_results/wbp_responses_wire_api_compat_repair_pass_2026-05-24/*`
- tests run: `tests.test_operator_surface`; `tests.test_codex_custom_sessions`; `tests.test_codex_account_selection`; `tests.test_web_design_live_server`; `node --check`; `git diff --check`; closeout resilience.
- blocked risks: live Codex Custom success is still not proven; if the next single traced rerun still returns upstream `401`, the remaining owner class is GPT account/upstream auth.
- next exact command: start `CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_RERUN_PASS` and run exactly one traced Codex Custom prompt; if it returns upstream `401`, stop and open `GPT_ACCOUNT_AUTH_REPAIR_OR_OPERATOR_REAUTH_PASS`.
- Forbidden actions not performed: no Codex Custom live prompt rerun; no direct live `/v1/responses` probe; no account reauth; no account/provider credential mutation; no current Codex mutation.

## Result

Two repo-owned defects were fixed.

First, `WbpTraceObserver` previously forwarded only content type and local authorization to downstream WBP. It now preserves safe Codex/OpenAI compatibility headers while excluding hop-by-hop and secret-bearing ambient headers.

Second, traced upstream 4xx was present in the trace packet but the top-level prompt result could remain generic. `OperatorSurfaceSession.run_prompt` now bubbles traced upstream 4xx as `TRACE_UPSTREAM_HTTP_<status>`.

This contour does not prove live Codex Custom success. It only repairs the repo-owned trace/wire compatibility layer and prepares the next single live rerun.

## Verification

- `python3 -B -m unittest tests.test_operator_surface -q` -> OK, 10 tests.
- `python3 -B -m unittest tests.test_codex_custom_sessions tests.test_codex_account_selection -q` -> OK, 20 tests.
- `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_operator_surface tests.test_codex_custom_sessions tests.test_codex_account_selection tests.test_web_design_live_server -q` -> OK, 115 tests.
- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> OK.
- `git diff --check` -> OK.

## Resume From Here

resume from here: run `CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_RERUN_PASS` with exactly one traced Codex Custom prompt. If it still returns upstream `401`, stop and open `GPT_ACCOUNT_AUTH_REPAIR_OR_OPERATOR_REAUTH_PASS`; do not loop prompt retries.

## Git

- Commit hash: recorded in final operator note after commit.
- Push status: recorded in final operator note after remote push completes.
