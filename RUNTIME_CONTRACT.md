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
- deterministic stable recovery now reuses the same generated config path,
  `WBP_STABLE_CONFIG` handoff, and snapshot topic through the bounded
  `healthcheck --json` owner path
- deterministic stable recovery must regenerate generated config per
  approved-target attempt and must not treat a stale generated config artifact
  as authoritative truth
- `healthcheck --json` may expose a top-level
  `deterministic_stable_recovery_contract` surface for owner-lane semantics
- `launch smoke --json` must not pretend to own the deterministic stable
  recovery lane or echo its result surface
- approved-target activation success must remain separately observable from a
  healthy observed-source fallback
- fallback from approved target to observed stable source must be explicit and
  machine-readable
- desired stable runtime consumer source must never be reported as effective
  before successful live activation evidence
- top-level healthcheck and status truth must continue to describe final live
  runtime state, while deterministic stable recovery outcome remains a separate
  recovery-attempt surface
- owner-path packets emit `deterministic_stable_recovery_result.entry_lane`
- top-level `STABLE_SERVICE_DISABLED` is valid only when:
  - the same packet proves `entry_lane = stable_service_disabled`
  - final live runtime truth remains unhealthy
- absent positive evidence, final listener failure stays on conservative
  `LISTENER_DOWN`
- `stable_service_disabled` remains a control-layer classification and must stay
  separate from `PROXY_PATH_BROKEN` and `PROXY_REPROBE_FAILED`
- no new persisted recovery metadata file or snapshot-schema widening is
  required for stable-service-disabled packet truth by default
- owner-path proxy packets may expose top-level
  `last_known_good_proxy_contract`
- owner-path proxy packets may expose top-level `last_known_good_proxy`
  with an honest materialization status such as `declared_not_materialized`
- owner-path proxy packets may expose top-level
  `current_proxy_adoption_contract`
- that contract may declare a dedicated current-proxy activation handoff such as
  `WBP_CURRENT_PROXY_URL`
- that handoff remains a launcher-scoped process-local carrier rather than a
  truth surface for `current_proxy_url`
- owner-path proxy packets may now expose nested
  `proxy_reprobe_adoption_result`
  when proxy-path failure found a bounded working candidate and the owner path
  evaluated or attempted current-proxy adoption
- `proxy_reprobe_adoption_result` remains nested owner-path truth rather than a
  top-level current-proxy truth surface
- that contract may expose an external launcher-path surface for
  `WBP_LAUNCHER_SCRIPT`, but launcher-path presence alone must not be treated as
  proof of current-proxy consumer capability
- the default launcher path may be a bounded repo-owned provisioning target,
  but a preexisting unmarked file at that path must not be silently overwritten
- a repo-owned default launcher artifact may carry a narrow repo-managed marker
  used only for safe refresh of that default-path artifact
- that contract may expose a bounded launcher-consumer readiness surface and
  must report:
  - repo-owned default consumer provisioning availability
  - default-path missing or provisioned state
  - default-path ownership-unverified state
  - explicit external override unverified state
  honestly without implying current-proxy adoption readiness
- absent default-path materialization remains a bounded owner-path prerequisite,
  not lane eligibility by itself
- owner-path current-proxy adoption may proceed only through a recognized
  repo-owned default launcher artifact after any prerequisite materialization
  has been re-evaluated
- explicit external override paths, invalid default-path markers, and
  unrecognized marked default-path files remain ineligible owner-path adoption
  lanes
- that contract may allow a later launcher consumer to derive engine-local proxy
  env keys for the managed runtime child process only
- any such derived proxy env keys remain engine-local routing inputs, not
  control-plane truth surfaces
- owner-path healthcheck writes may materialize or refresh
  `last_known_good_proxy_url` and `last_known_good_proxy_observed_at`
  in `supervisor-state.json`
- `status --json` may report the same current-proxy adoption contract only as
  delegated readout
- `status --json` may report the same nested `proxy_reprobe_adoption_result`
  only as delegated readout
- `proxy_reprobe.working_candidate` remains nested bounded evidence only and
  must not become `current_proxy_url` by mere presence
- `status --json` may report the same last-known-good proxy surface only as
  delegated readout
- delegated `status --json` must propagate those owner-path writes honestly in
  `changed_files`
- `current_proxy_url` is current live outbound proxy truth and remains separate
  from nested `proxy_reprobe.working_candidate`
- ambient shell proxy env must not become the authoritative control-layer truth
  surface for current proxy selection
- derived proxy env keys such as `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and
  lowercase variants may later be generated only inside the bounded launcher
  consumer from `WBP_CURRENT_PROXY_URL`; that allowance does not itself claim
  that the current engine already consumes those keys
- control-plane runtime attestation remains proxyless even if a later managed
  runtime activation lane receives a dedicated current-proxy handoff
- `current_proxy_url` may change only after the same serialized owner path:
  - detected proxy-path failure
  - found a bounded working candidate
  - established an eligible recognized repo-owned launcher lane
  - carried that candidate through `WBP_CURRENT_PROXY_URL`
  - reran live managed runtime attestation successfully
- persisted last-known-good proxy truth must remain separate from
  `current_proxy_url`
- candidate existence alone must never produce top-level `OK`
- persisted last-known-good proxy truth must never by itself change top-level
  live runtime truth

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
