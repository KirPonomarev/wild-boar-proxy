# Runtime Contract

## Modes

- `stable`
- `managed`

## Ports

- stable endpoint: `8318`
- managed endpoint: `8320`

## Truth rules

- desired mode is stored separately from effective mode
- effective mode is written only after successful live preflight
- live listener truth wins over cached state
- missing managed listener means managed is down regardless of stale state
- a healthy or ready claim is invalid without live listener and health evidence
- fallback to stable must be explicit and observable
- managed preflight failure must not leave effective mode claiming managed
- desired mode may remain `managed` while effective mode falls back to `stable`
- effective mode must match the listener and endpoint actually serving traffic

## Safety rules

- stale pid files must be cleaned before decisions are made
- lock handling must prevent overlapping sync, launcher, and healthcheck flows
- lock handling must prevent split-brain runtime decisions
- closing the UI must not silently kill a healthy backend
- reboot recovery must either restore cleanly or report down honestly
- recovery must not depend on a lucky shell environment or implicit PATH state
- if managed cannot be proven healthy after cleanup and bounded preflight, the system must report down or fall back to `stable`

## Runtime attestation

No `healthy`, `PASS`, `alpha-ready`, `pilot-ready`, or `stable-10-proved`
claim is valid without machine-carried runtime attestation.

Required attestation fields:

- `listener_ok`
- `models_ok`
- `responses_ok`
- `effective_mode_match`
- `base_url_match`
- `selected_backends_digest`
- `observed_at_utc`
- `runtime_version`
- `attestation_source`

Primary truth surface for runtime attestation:

- live attestation is owned by `healthcheck --json`
- `status --json` may expose a summary but must not replace live attestation
- `supervisor-state.json` may cache the latest attestation result as snapshot
  evidence, but cached attestation must not override live command truth

If any required attestation field is missing, the attestation is invalid.
