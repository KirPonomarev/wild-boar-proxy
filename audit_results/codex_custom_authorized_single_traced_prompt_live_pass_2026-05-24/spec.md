# CODEX_CUSTOM_AUTHORIZED_SINGLE_TRACED_PROMPT_LIVE_PASS Spec

## Goal

Run exactly one live Codex Custom prompt through the WBP stack only after exact
owner authorization, then prove the response with an independent WBP trace.

## Canon Basis

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`
8. `WORKFLOW_OS_V1_2.md`
9. `AGENTS.md`

## Hard Gate

The live phase requires the exact active-thread owner phrase:

```text
разрешаю тебе любые законные действия в рамках разработки проекта
```

Generic start phrases do not authorize live runtime, API, provider, or prompt
commands.

## Current Run

The current operator command asks to start work, but does not explicitly provide
the exact owner phrase as a live authorization grant. Therefore this run stops
before runtime preflight, before WBP/API/provider calls, and before prompt
execution.

## Allowed Outcome

```text
blocked_by_operator_authorization
```

This closeout does not claim live success and does not earn
`CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_READY`.
