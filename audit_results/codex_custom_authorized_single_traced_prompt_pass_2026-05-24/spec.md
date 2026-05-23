# CODEX_CUSTOM_AUTHORIZED_SINGLE_TRACED_PROMPT_PASS Spec

## Goal

Run exactly one live Codex Custom prompt through WBP web UI only after exact owner authorization, then prove the response with an independent WBP trace observer.

## Canon Basis

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `COMMAND_API.md`
5. `DELIVERY_RULES.md`
6. `AGENTS.md`

## Required Authorization

The live phase requires the exact active-thread owner phrase:

```text
разрешаю тебе любые законные действия в рамках разработки проекта
```

Generic phrases such as `начинай работу` do not authorize live WBP/API/provider/prompt commands.

## Scope

- One bounded live prompt after authorization.
- Independent WBP trace proof.
- Server-issued model/backend only.
- Prompt-only browser payload.
- No false-green if trace is missing.

## Current Run

The exact authorization phrase was not provided as an explicit owner grant in the active thread. Therefore this run stops before live commands and closes as `blocked_by_operator_authorization`.
