<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

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
- deterministic stable recovery entry is owned by the explicit repair path
  exposed through `healthcheck --repair --json`
- `status --json` must not delegate to that owner path; it is a read-only
  snapshot surface and must mark live attestation as not run by status
- the current stable-runtime activation implementation is limited to the
  `launch smoke` seam
- `launch client --json` may exist as a separate bounded external host-client
  dispatch owner surface
- `launch client --json` must not become a new owner of runtime health,
  fallback, or recovery truth
- `launch client --json` may verify runtime preconditions before dispatch and
  may report that delegated runtime readout honestly
- `launch client --json` success must remain bounded to explicit OS-level
  dispatch truth and must not imply internal host-client session success,
  profile-selection success, or runtime connectivity success by itself
- generated stable runtime config materialization must not rewrite baseline
  stable config in place
- deterministic stable recovery now reuses the same generated config path,
  `WBP_STABLE_CONFIG` handoff, and snapshot topic through the bounded
  `healthcheck --repair --json` owner path
- deterministic stable recovery must regenerate generated config per
  approved-target attempt and must not treat a stale generated config artifact
  as authoritative truth
- `healthcheck --repair --json` may expose a top-level
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
- owner-path `healthcheck --repair --json` writes may materialize or refresh
  `last_known_good_proxy_url` and `last_known_good_proxy_observed_at`
  in `supervisor-state.json`
- `status --json` may report static current-proxy adoption contracts only as
  read-only snapshot data
- `status --json` must not report a fresh nested
  `proxy_reprobe_adoption_result`; any such field must come only from already
  persisted/cached snapshot evidence
- `proxy_reprobe.working_candidate` remains nested bounded evidence only and
  must not become `current_proxy_url` by mere presence
- current bounded candidate discovery remains
  `shallow_socket_listener_only` and is limited to local listener reachability
  rather than a separate deep-probing truth surface
- top-level current-proxy adoption success still requires same-owner live
  runtime reproof through `healthcheck.attestation`
- no separate control-layer deep-probing surface is active by default; deeper
  runtime validation remains delegated to the live reproof surface above
- `status --json` may report the same last-known-good proxy surface only as a
  persisted-state snapshot
- `status --json` must not report owner-path writes and must emit
  `changed_files=[]`
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

## One-shot CLI production admission

- production one-shot authority requires both an immutable server-owned tool
  declaration and a matching external binary-admission record
- the declaration binds provider identity, version probe, allowed argv and
  environment schema, cwd policy, output parser and bounds, process-group
  policy, sandbox policy, auth strategy, session policy, and network policy
- the admission record binds that declaration digest to one exact executable
  realpath, full content digest, owner, mode, and observed version
- a probe never grants operational authority; it runs with the sterile fixed
  PATH, isolated temporary home, bounded output/time, a new process group, and
  the same deny-default offline seatbelt used by an operational child
- executable lookup uses only code-owned fixed candidate roots; ambient PATH,
  caller paths, environment-selected manifests, and global runtime grants are
  never authority surfaces
- admission storage is canonical JSON under a fixed WBP-owned mode-`0700`
  root; the admission file and real writer lock are mode `0600`, owner-checked,
  and the file is atomically replaced while the lock is held
- missing, malformed, noncanonical, mode/owner-unsafe, symlink-drifted,
  declaration-drifted, binary-drifted, or version-drifted admission fails
  closed before persistent provider-home creation or operational dispatch
- exact admission is revalidated immediately before every production run;
  one-shot sessions never resume
- secret-shaped argv or stdin is rejected before spawn; captured stdout and
  stderr are bounded and redacted before packet serialization; raw process
  exception text is not a packet surface
- the Qwen production adapter is code-admitted with one sealed headless argv:
  `--prompt <bounded-nonsecret-text> --output-format json --safe-mode
  --approval-mode plan --max-session-turns 30 --max-wall-time 300s
  --max-tool-calls 25 --exclude-tools shell,write,edit,agent`; callers cannot
  supply argv, environment, provider home, parser, or sandbox policy
- Qwen operational output must be one complete, non-truncated buffered JSON
  array containing a non-error `result/success` envelope with non-empty result
  text; process success with malformed, partial, error, or empty output is still
  a typed failure
- Qwen authentication is presence-checked only in its isolated WBP-owned home;
  WBP neither reads secret values nor performs interactive login in this contour
- the operational child receives fixed server-owned
  `QWEN_USAGE_STATISTICS_ENABLED=false` and `QWEN_TELEMETRY_ENABLED=false`;
  ambient or caller values cannot override this privacy boundary
- provider network is denied for probes and every default child; it is enabled
  only for the exact admitted Qwen operational child after binary and auth
  revalidation, while repository writes remain denied and an explicitly selected
  project root is read-only
- Qwen binary admission, auth presence, and a live provider call remain external
  gates; code admission alone is not live proof
- the Kimi declaration is present, but its provider adapter, interactive login,
  and network policy remain not admitted until its separate B11 contour

## Runtime attestation

No `healthy`, `PASS`, `alpha-ready`, `pilot-ready`, `stable-10-proved`, or `stable-15-proved`
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
- `healthcheck --json` is a probe surface and must not mutate runtime truth,
  clean stale pid files, run recovery, or report repair writes
- bounded runtime health repair is owned by `healthcheck --repair --json`
- `status --json` may expose a read-only snapshot summary but must not run or
  replace live attestation
- `supervisor-state.json` may cache the latest attestation result as snapshot
  evidence, but cached attestation must not override live command truth

If any required attestation field is missing, the attestation is invalid.

## Evidence levels

Evidence claims use the canonical normalized taxonomy (B03):

```text
DECLARED < SYNTHETIC_PROVEN < INTEGRATION_PROVEN < LIVE_PROVEN
< PHYSICAL_VISIBLE_PROVEN
```

- lower levels never substitute for higher levels
- an empty required-step collection is never accepted as evidence
  (`all([])` is not proof)
- one SHA cannot stand for multiple independent milestones
- credential presence is never a live response
- bridge success is never direct-provider auth proof
- stale evidence (after code, config, binding, binary, hook, or Codex-version
  changes) is invalid
- every evidence record binds plan, stage, project identity, candidate SHA,
  artifact digest, actor/binding/assignment revisions, adapter, context
  digest, environment/policy identity, evidence level, timestamp, TTL, and
  invalidation keys

## Normalized transport

External adapters normalize one shared surface (B03):

- request envelope
- stream events
- final response
- tool-call events
- typed errors
- ambiguity and cancellation
- capability negotiation
- dispatch receipts

`native_primary` is a special host boundary, not an ordinary callable
`transport.send()` adapter. Ambiguous-delivery results are never retried and
never replaced by another actor's response under the original identity.
Cross-provider fallback is off by default.

API adapter truth rules:

- deterministic controlled dispatch validates the registered route but neither
  requires nor probes a live credential; it is always marked
  `SYNTHETIC_PROVEN` and never proves a provider call
- live dispatch requires presence-only credential admission before constructing
  provider headers
- every request must match the resolved dispatch plan's dispatch, transport,
  provider, model, permission, and bound context identities; any supplied slot,
  binding, binding revision, assignment, or assignment revision must also match,
  and successful receipts always use the exact plan-owned identity values
- the registered route record is authoritative; a caller-supplied route that is
  not canonically equivalent is rejected and cannot override the endpoint; its
  canonical digest is rechecked between admission, dispatch, and live rebind
- secret-shaped credential values in prompt text are rejected before provider
  invocation
- a failure before invoking the bounded HTTP request reports
  `dispatch_attempted=false`; an exception after invocation begins reports
  `ambiguous_delivery`, `dispatch_attempted=true`, and
  `retry_permitted=false`
- a returned non-2xx HTTP response is an observed typed error, never successful
  actor output; 401/403 map to `invalid_credential`, 404 to
  `model_not_available`, 408 to `timeout`, 429 to `quota_exhausted`, and 5xx to
  `network_failed`
- result classification gives an error code precedence over
  `response_observed`; observation alone can never turn an error into `ok`
- `LIVE_PROVEN` requires a 2xx response and a non-empty normalized provider
  output; credential presence, an error payload, or a transport attempt is
  insufficient
- provider output is redacted before entering a receipt and is bound by a
  SHA-256 digest; when an assembled stream requires redaction, none of its
  original non-empty deltas are emitted; raw provider bodies and raw exception
  text are structurally absent from the receipt
- failure never enables cross-provider fallback, actor substitution, or an
  automatic retry
