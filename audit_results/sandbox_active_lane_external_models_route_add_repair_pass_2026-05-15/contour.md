# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_ADD_REPAIR_PASS

## Goal

Use the narrowest canon-admitted mutation surface to eliminate the empty local external-models route registry as the current sandbox blocker candidate, then re-run owner truth without widening into token, validation, provider-check, or materialization work.

## Declared Surfaces

- read surfaces:
  - `/Users/kirillponomarev/.codex-custom-cli/auth.json`
  - `/Users/kirillponomarev/.codex-custom-test/config.toml`
  - `/Users/kirillponomarev/.codex-custom-test/external-models/routes.json`
  - `/Users/kirillponomarev/.codex-custom-test/external-models/state.json`
  - `/Users/kirillponomarev/.codex-custom-test/external-models/secrets.env`
- write surface:
  - `/Users/kirillponomarev/.codex-custom-test/external-models/routes.json`

## Baseline Truth

- sandbox `healthcheck --json` with the external auth override stayed blocked on `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`
- `external-models routes list --json` returned `count = 0`
- `external-models models --json` returned `count = 0`
- `state.json` and `secrets.env` existed and were not part of the declared mutation surface

## Minimal Route Attempt

- route payload used only schema-required keys
- `upstream_model = claude-sonnet-4-6-thinking`
- `auth.type = none`
- no secret ref was introduced
- mutation command surface: `external-models routes add --json --stdin`

## Observed Outcome

- route add succeeded and changed only `routes.json`
- post-add `routes list` moved from `0` to `1`
- post-add `models list` moved from `0` to `1`
- owner truth did **not** move: `healthcheck --json` stayed blocked on the same `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`
- this proves the empty local route registry was a real local gap, but not the owner-level blocker currently deciding runtime attestation

## Rollback

- pre-mutation `routes.json` snapshot captured
- byte-faithful rollback executed after blocked post-add proof
- post-rollback packets confirmed `routes_count = 0` and `models_count = 0`

## Result Shape

- contour outcome: `STOP_AND_DIAGNOSE`
- next scope is no longer route creation
- next scope must localize provider-evidence / model-resolution ownership before any more route mutations are attempted
