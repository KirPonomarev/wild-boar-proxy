# RERUN_READONLY_TRUTH_PACKET_BASELINE_PASS

## Goal

Rerun the readonly semantic baseline after the `overview` live pending-source repair and determine whether the canonical command truth, live GET truth, and core UI live claims now align well enough to move to sandbox boundary work.

## Scope

- readonly canonical commands only
- readonly live GET packets only
- core UI screens only: `quick-start`, `overview`, `accounts`, `api-connections`
- no `POST /api/action`
- no live-action clicks
- no runtime mutations

## Evidence Plan

1. recapture canonical packets
2. recapture live GET packets
3. compare command truth to live truth
4. compare live truth to UI truth claims
5. classify mismatches, if any
6. issue `GO` or `STOP_AND_DIAGNOSE`
