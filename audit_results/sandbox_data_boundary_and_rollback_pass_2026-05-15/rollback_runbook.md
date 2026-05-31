# Rollback Runbook

## Scope

This contour performed no sandbox mutation. Rollback is therefore declarative
for the next sandbox contour.

## Rollback Unit

The rollback unit for the next sandbox wave is the declared fresh root:

`/Users/kirillponomarev/.codex-custom-sandbox-20260515`

## Rollback Rule

If the next contour creates or mutates only paths inside the declared sandbox
root, rollback is:

1. stop any sandbox-scoped processes started by that contour
2. verify no working/live roots were touched
3. remove the fresh sandbox root tree in full
4. re-check that working/live roots remain unchanged

## Why This Rollback Is Credible

- the active sandbox root is dedicated and absent before the next contour
- working/live roots are outside it
- the old sandbox candidate root is quarantined and excluded from active writes

## Rollback Verification

After a future rollback:

- `/Users/kirillponomarev/.codex-custom-sandbox-20260515` must be absent again
- `/Users/kirillponomarev/.codex-custom-cli` must remain untouched
- `/Users/kirillponomarev/.cli-proxy-api` must remain untouched
- `/Users/kirillponomarev/.wild-boar-proxy/external-models` must remain
  untouched
