# READONLY_TRUTH_PACKET_BASELINE_PASS Independent Audit

## Auditor

- agent: `019e2bc0-5481-7d52-ba00-b0b530731235`
- nickname: `Pasteur`
- model: `gpt-5.4-mini`
- role: readonly truth-chain cross-check

## Auditor Findings

- `live_readonly` packet is fed by:
  - `status --json`
  - `mode get --json`
  - `accounts list --json`
  - `healthcheck --json`
  - `rollout rotation inspect --json`
- `accounts_readonly` packet is fed only by `accounts list --json`
- `api_connections_readonly` packet is fed by:
  - `external-models status --json`
  - `external-models models --json`
  - `external-models routes list --json`
- The auditor flagged several mismatch hotspots:
  - overview/account `problem` semantics can drift
  - API latest-check is structurally weak
  - quick-start primary-route detection is heuristic
  - account redaction is split across server/UI helpers
  - overview hard-fails on status/mode disagreement

## Auditor Verdict

- verdict: `STOP_AND_DIAGNOSE`

## Adjudication

Main contour adjudication agrees with the auditor verdict.

The blocking reason is narrower and factual:

- canonical command truth and live GET truth were sufficiently aligned for this contour
- but the `overview` screen in `source=live` did not reflect that truth
- therefore sandbox boundary work must wait until the live overview truth chain is repaired and re-baselined
