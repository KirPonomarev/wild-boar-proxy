# ACCOUNT_ROTATION_AND_MODERATE_LOAD_PASS

## Objective

Prove bounded repeated Codex Custom prompts through the existing WBP web session
path without broadening product scope or making scale/stage claims.

## Canon Basis

Decision order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`
8. `WORKFLOW_OS_V1_2.md`
9. `AGENTS.md`

If runtime packets, docs, and assumptions conflict, packet truth and the canon
order decide.

## Scope

In scope:

- Runtime/account preflight.
- One bounded selector refresh only if needed to clear stale rotation evidence.
- Existing web Codex Custom session endpoints.
- Canary run: 3-5 serial prompts.
- Moderate run: 20 prompts at concurrency 2, optional expansion only if clean.
- Post-load reclear with status, healthcheck, accounts, rotation packets.
- Redaction audit, independent audit, closeout, commit, push.

Out of scope:

- UI polish or new load dashboard.
- Desktop GUI, packaging, installer.
- Account login, reauth, provider credential mutation.
- Destructive lifecycle actions.
- Policy stage changes.
- Production, stable-15/stable-20, design gate, or general rotation readiness
  claims.

## Live Bounds

- Prompt path: existing `/api/codex/custom/sessions/:id/prompt`.
- Trace path: existing `OperatorSurfaceSession.run_prompt(..., trace_wbp=True)`.
- Canary: 3 serial requests.
- Moderate run: 20 requests, concurrency 2.
- Retry storm: forbidden.
- Prompt: tiny deterministic low-output request.
- Response storage: bounded preview only.

## Required Proof Fields

- `trace_path=/v1/responses`
- `forwarded_to_wbp=true`
- `upstream_status` classified
- `source_provenance_proven=true`
- `selected_source_class`
- `current_codex_touched=false`
- `isolated_engine_home_proven=true`
- `secret_value_recorded=false`
- no raw auth/backend/account/path/token in artifacts
- cleanup only on owned temp session roots

## Stop Conditions

Stop and diagnose on:

- Same failure repeats twice.
- Upstream `401`, `403`, or `429` reports green.
- Missing WBP trace after claimed success.
- Current Codex touch.
- Secret/auth/backend/account/path leak.
- Pool corruption or unexpected account mutation.
- Repeated `LOCK_HELD`.
- Non-JSON command output.
- Test failure caused by contour changes.

## Success Token

Allowed if all criteria pass:

`ACCOUNT_ROTATION_AND_MODERATE_LOAD_BOUNDED_PROOF_READY`

Forbidden claims:

- `CODEX_CUSTOM_ROTATION_READY`
- `CODEX_CUSTOM_LOAD_READY`
- `CODEX_CUSTOM_DESKTOP_READY`
- `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`
- stable-15/stable-20 readiness
- production readiness
