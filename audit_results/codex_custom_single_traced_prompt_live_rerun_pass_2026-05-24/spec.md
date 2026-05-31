# CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_RERUN_PASS Spec

Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`

Goal: run exactly one traced Codex Custom prompt after `/v1/responses` wire repair and prove either a machine-backed response or a classified blocker.

Hard rules:
- `prompt_count = 1`
- `retry_count = 0`
- no account reauth
- no provider credential mutation
- no current Codex mutation
- no second prompt inside this contour

Expected success token: `CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_OK`.
