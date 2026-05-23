# CODEX_CUSTOM_SESSION_MANAGER_PASS

## Contour Capsule

- Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`
- Contour: `CODEX_CUSTOM_SESSION_MANAGER_PASS`
- Date: 2026-05-23
- Mode: non-live Codex Custom session lifecycle
- Goal: create, prompt-dry-run, transcript, cancel, and cleanup through WBP web without live prompt, provider calls, token burn, or current Codex mutation.

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

- `POST /api/codex/custom/sessions`
- `GET /api/codex/custom/sessions`
- `GET /api/codex/custom/sessions/:id`
- `POST /api/codex/custom/sessions/:id/prompt-dry-run`
- `GET /api/codex/custom/sessions/:id/transcript`
- `POST /api/codex/custom/sessions/:id/cancel`
- `POST /api/codex/custom/sessions/:id/cleanup`
- WBP web UI session lifecycle panel.

## Out Of Scope

- live GPT account inference
- live WBP `/v1/responses`
- provider/API calls
- account mutation
- runtime mode mutation
- desktop app launch/package
- design polish

## Non-Live Contract

Expected packet truth:

```text
live_prompt_admitted=false
prompt_runner_called=false
live_selection_proven=false
inference_proven=false
runtime_meter_attached=false
network_calls_made=false
provider_called=false
token_burn=0
```

The web UI must not render or bind a live `Run prompt` button in this contour.
