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
- desired stable runtime consumer source must be reported separately from
  effective stable runtime consumer source
- observed stable inventory source remains observation truth, not approved
  runtime-target truth
- approved repair-target reference remains control-layer target truth, not
  effective runtime-consumer truth
- a generated stable runtime config is a control artifact, not a truth surface
- stable-runtime generated-config handoff uses a narrow launcher-scoped
  `WBP_STABLE_CONFIG` override, not a generic config-routing surface
- runtime-state activation evidence may be cached as snapshot evidence, but
  snapshot evidence alone must not flip effective stable runtime consumer truth
- deterministic stable recovery entry is owned by the live attestation and
  fallback-reconciliation path exposed through `healthcheck --json`
- `status --json` may delegate to that owner path and must report its outcome
  honestly; it is not a separate recovery owner
- the current stable-runtime activation implementation is limited to the
  `launch smoke` seam
- generated stable runtime config materialization must not rewrite baseline
  stable config in place
- the recovery contract fixes that later deterministic stable recovery must
  reuse the same generated config path, `WBP_STABLE_CONFIG` handoff, and
  snapshot topic unless a later blocker proves otherwise
- the recovery contract fixes that later deterministic stable recovery must
  regenerate generated config per attempt and must not treat a stale generated
  config artifact as authoritative truth
- approved-target activation success must remain separately observable from a
  healthy observed-source fallback
- fallback from approved target to observed stable source must be explicit and
  machine-readable
- desired stable runtime consumer source must never be reported as effective
  before successful live activation evidence

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
