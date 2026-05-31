# SANDBOX_ACTIVE_LANE_EXTERNAL_AUTH_IMPORT_REPAIR_PASS

## Goal

Perform the canon-admitted external auth import into the sandbox auth target, then re-run owner truth without widening into rebinding, materialization, or lifecycle continuation.

## Declared Surfaces

- read: `/Users/kirillponomarev/.codex-custom-cli/auth.json`
- write: `/Users/kirillponomarev/.codex-custom-test/auth.json`

## Owner Truth

- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy status --json`

## Execution Summary

- baseline sandbox owner truth remained `HTTP 401 Invalid API key`
- bounded import copied external source bytes into sandbox target and preserved target mode `0o600`
- post-import owner truth cleared `401` but remained blocked on `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`
- rollback expectation therefore triggered and sandbox auth target was restored byte-for-byte
- no registry rebinding was attempted
- no launcher/materialization writes were attempted

## Live Follow-up Evidence

- `external-models status --json` => `profile_ready=false`, `routes_count=0`, `local_auth.token_present=false`
- `external-models models --json` => `count=0`
- `external-models routes list --json` => `count=0`

## Result

- final verdict: `STOP_AND_DIAGNOSE`
- next contour candidate: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS`
