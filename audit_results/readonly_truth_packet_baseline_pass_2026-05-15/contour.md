# READONLY_TRUTH_PACKET_BASELINE_PASS

## Goal

Capture the canonical readonly baseline packet set from direct command surfaces
 and compare it against the previously admitted live-readonly summaries without
 entering any mutation lane.

## Scope

- direct command packets:
  - `status --json`
  - `mode get --json`
  - `accounts list --json`
  - `healthcheck --json`
  - `rollout rotation inspect --json`
  - `external-models status --json`
  - `external-models models --json`
  - `external-models routes list --json`
- readonly summary comparison against the prior
  `WEB_LIVE_SERVER_READONLY_ADMISSION_PASS`
- drift localization only

Out of scope:

- sandbox creation/binding
- runtime repair
- UI repair
- any action execution or mutation contour

## Findings

- all required readonly command surfaces emitted valid JSON packets
- `mode get --json`, `accounts list --json`, rollout evidence, and
  external-models support packets remained structurally coherent
- account count and readonly summary count matched at `25`
- external-models support packets still matched the readonly API-connections
  summary on:
  - `routes_count = 0`
  - `runtime_claim_blocked = true`
- the blocking fact is not packet-shape failure and not fixture fallback
- the blocking fact is owner-truth instability:
  - previous readonly admission snapshot showed healthy readonly truth
  - an intermediate direct capture recorded:
    - `status --json -> ATTESTATION_FAILED`
    - `healthcheck --json -> ATTESTATION_FAILED`
    - `responses_ok = false`
    - `launch_readiness_status = blocked`
    - `launch_blocking_reason = responses_probe_failed`
  - the later retry still did not produce a stable canonical pair:
    - `status --json -> OK`
    - `healthcheck --json -> ATTESTATION_FAILED`

## Decision

- status: `STOP_AND_DIAGNOSE`
- reason:
  - the baseline contour cannot honestly authorize sandbox boundary work while
    direct readonly owner truth flips inside the same contour
  - `healthcheck --json` remains the runtime owner surface and it is not stable
    enough here to call the baseline closed

## Next Guardrails

- preserve owner-truth drift evidence
- do not treat the delegated `status --json` packet as stronger than the
  owner `healthcheck --json`
- do not proceed to `SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS` until the
  readonly runtime-truth drift is localized
