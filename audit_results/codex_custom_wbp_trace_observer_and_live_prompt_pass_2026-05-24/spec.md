# CODEX_CUSTOM_WBP_TRACE_OBSERVER_AND_LIVE_PROMPT_PASS Spec

## Goal

Prepare the Codex Custom live prompt path so it can run only after exact owner authorization, with independent WBP trace proof required before any green path claim.

## Canon Basis

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `COMMAND_API.md`
5. `DELIVERY_RULES.md`
6. `AGENTS.md`

## Scope

- Keep the live prompt endpoint default-deny.
- Admit live prompt only when the caller provides the exact canonical owner phrase.
- Require independent WBP trace evidence for `wbp_path_proven=true`.
- Expose a gated live prompt button in the web UI.
- Preserve prompt-only browser payloads.
- Prove the missing-authorization path with fake-server browser proof.

## Out Of Scope

- No live WBP/API/provider prompt in this run.
- No token burn.
- No rotation/load.
- No account/API/provider mutation.
- No current Codex mutation.
- No design polish.

## Authorization Rule

Exact phrase required:

```text
разрешаю тебе любые законные действия в рамках разработки проекта
```

Absent or near-miss phrase must produce:

```text
OWNER_AUTHORIZATION_REQUIRED
live_prompt_executed=false
prompt_runner_called=false
token_burn=0
```
