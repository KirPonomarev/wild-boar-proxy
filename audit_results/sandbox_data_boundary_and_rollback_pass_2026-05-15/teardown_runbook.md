# Teardown Runbook

## Purpose

Teardown for the next sandbox contours must leave no active sandbox process and
no ambiguity about residual sandbox state.

## Teardown Steps

1. stop any process started with sandbox path env overrides
2. collect changed-files proof if the contour emitted it
3. preserve contour artifacts in `audit_results/`
4. if the contour was a disposable sandbox attempt, remove the declared fresh
   sandbox root:
   - `/Users/kirillponomarev/.codex-custom-sandbox-20260515`
5. re-check that forbidden roots remain untouched:
   - `/Users/kirillponomarev/.codex-custom-cli`
   - `/Users/kirillponomarev/.cli-proxy-api`
   - `/Users/kirillponomarev/.wild-boar-proxy/external-models`

## Non-Teardown Rule

Do not “teardown” by mutating or cleaning the quarantined old sandbox root
`.codex-custom-test` inside unrelated contours.
