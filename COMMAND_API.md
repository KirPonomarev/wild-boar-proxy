# Command API Contract

All operator commands must support `--json`.

## JSON output rules

- `stdout` must contain exactly one JSON object
- `stdout` must not contain leading or trailing non-JSON text
- `stderr` may contain human-readable logs
- invalid JSON is a hard integration failure even when exit code is `0`
- UI and automation must not fall back to plain-text parsing or log parsing

## Required commands

- `status --json`
- `sync --json`
- `healthcheck --json`
- `mode get --json`
- `mode set stable --json`
- `mode set managed --json`
- `accounts list --json`
- `accounts validate <id> --json`
- `accounts promote <id> --json`
- `accounts demote <id> --json`
- `accounts hold <id> --json`
- `accounts release <id> --json`
- `accounts retire <id> --json`
- `accounts onboard --json`
- `diagnostics export --json`

## Required response fields

Every command response must include all required fields on both success and failure.

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`

## Response rules

- `status` must not collapse liveness, severity, and operator action into one ambiguous token
- `exit_code` must reflect command success or failure
- `human_message` is for operator-readable summary, not machine parsing
- `machine_error_code` must be stable enough for UI and automation branching
- `changed_files` must be an array and may be empty
- `next_action` must be present even when the correct action is `none`
- `next_action` must use documented machine-readable tokens such as `none`,
  `retry`, `user_action`, or `stop`
- commands that report runtime health must expose `liveness`, `severity`, and
  `operator_action` as separate top-level fields instead of overloading
  `status`
- commands that carry runtime attestation must expose an `attestation` object
  containing the required attestation fields from `RUNTIME_CONTRACT.md`

## Error classes

- `recoverable`
- `needs_user_action`
- `fatal`

## Additional target-switch contract surface

The current target-switch contour exposes:

- `stable target switch --dry-run --json`
- `stable target switch --apply --json`

`--dry-run` remains a contract and reporting surface.
`--apply` is now a narrow control-layer write surface.

They must remain strict JSON and expose explicit machine-readable separation
between:

- current observed stable inventory source
- approved repair-target reference
- target-switch transaction metadata surface

Current required target-switch contract fields:

- `target_surface.status`
- `target_surface.observed_stable_inventory_source`
- `target_surface.approved_repair_target_reference`
- `target_surface.target_switch_transaction_metadata_surface`
- `declared_write_surfaces`
- `forbidden_surfaces`
- `transaction_phases`
- `verify_scope`

`stable target switch --apply --json` may materialize only:

- `<managed_dir>/stable-repair-target`
- `<managed_dir>/approved-repair-target.json`
- `<managed_dir>/target-switch-transaction.json`

Successful apply means control-layer target activation only.
It does not imply:

- runtime switch success
- engine inventory redirection
- repair success
- stable runtime health improvement

The materialized target directory may remain empty of `codex-*.json` auth
files. That is a success condition for this contour, not a defect.

## Additional stable-repair contract surface

`stable repair --dry-run --json` remains non-mutating.

`stable repair --apply --json` may mutate only:

- `<managed_dir>/stable-repair-target/codex-*.json`

It may also use process-local transaction scratch under companion-managed data:

- `<managed_dir>/.stable-repair-stage-*`
- `<managed_dir>/.stable-repair-backup-*`

These scratch directories are ephemeral transaction mechanics, not persisted
contract surfaces. They must be removed before the command returns on success
or rollback.

Successful apply means approved target inventory reconciliation only.
It does not imply:

- runtime switch success
- engine inventory redirection
- stable runtime health improvement

Apply-time field rules:

- eligible registry `auth_ref` files are policy-authorized copy inputs only
- source files remain non-mutating inputs
- observed-source drift fields remain observation only
- prune authority is limited to unauthorized `codex-*.json` entries already
  inside the approved control-owned target inventory
- basename preservation is exact; no rename or dedup logic is implied

It must expose explicit machine-readable separation between:

- observed stable inventory reporting
- registry source-copy inputs
- approved repair-target contract surface
- future target reconciliation plan
- repair apply authority

Required stable-repair contract groups:

- `transaction_plan.repair_observation`
- `transaction_plan.registry_source_inputs`
- `transaction_plan.repair_target_contract_surface`
- `transaction_plan.target_reconciliation_plan`
- `transaction_plan.repair_apply_authority`
- `transaction_plan.blocked_reasons`

Field meaning rules:

- observed-source fields must not silently imply delete authority over the
  observed stable inventory source
- registry `auth_ref` source files may be policy inputs for future repair apply,
  but this dry-run contract does not grant mutation authority over those source
  files
- target reconciliation fields must describe only the approved control-owned
  target inventory
- `would_change` must reflect future target reconciliation work, not merely
  observed-source drift
- apply blocker paths for missing source files or basename collisions must be
  machine-readable and must not fall back to implicit rename logic

## Additional stable-runtime consumer contract surface

The current stable-runtime consumer line now exposes a narrow activation path
only through `launch smoke --json`.

It must expose explicit machine-readable separation between:

- observed stable inventory source
- approved repair-target reference
- desired stable runtime consumer source
- effective stable runtime consumer source
- derived stable runtime config surface
- explicit fallback contract

Current reporting surfaces for this contract are:

- `status --json`
- `launch smoke --json`

Required contract fields:

- `stable_runtime_consumer.status`
- `stable_runtime_consumer.observed_stable_inventory_source`
- `stable_runtime_consumer.approved_repair_target_reference`
- `stable_runtime_consumer.desired_stable_runtime_consumer_source`
- `stable_runtime_consumer.effective_stable_runtime_consumer_source`
- `stable_runtime_consumer.derived_stable_runtime_config_surface`
- `stable_runtime_consumer.launcher_handoff_contract`
- `stable_runtime_consumer.activation_evidence_surface`
- `stable_runtime_consumer.effective_truth_contract`
- `stable_runtime_consumer.baseline_stable_config_surface`
- `stable_runtime_consumer.fallback_contract`
- `stable_runtime_consumer.deterministic_stable_recovery_contract`
- `stable_runtime_consumer.consumer_activation_readiness`

Field meaning rules:

- desired stable runtime consumer source is control-layer selection truth
- effective stable runtime consumer source is runtime-observed truth only
- desired source must not be reported as effective before successful live
  activation evidence
- launcher handoff for stable-runtime activation is a narrow process-local
  override contract:
  `WBP_STABLE_CONFIG=<managed_dir>/stable-runtime-config.generated.yaml`
- that handoff must remain launcher-scoped and must not silently become a
  generic config-routing platform
- runtime-state activation evidence is a snapshot surface only; snapshot evidence
  alone must not flip effective stable runtime consumer truth
- baseline stable config remains an engine-adjacent observation surface
- `stable-runtime-config.generated.yaml` is a generated control artifact, not a
  truth surface
- deterministic stable recovery entry is owned by the live attestation and
  fallback-reconciliation path exposed through `healthcheck --json`
- `status --json` may delegate to that owner path and must report its outcome
  honestly; it must not pretend to be a separate recovery owner
- silent fallback from approved target to observed source is forbidden
- when desired source is the approved repair target, `launch smoke --json` may:
  - materialize `stable-runtime-config.generated.yaml`
  - pass it through the launcher-scoped `WBP_STABLE_CONFIG` override
  - write `stable_runtime_consumer_snapshot` with outcome
    `approved_target_activated` or `observed_source_fallback`
- when desired source remains the observed stable inventory source, `launch
  smoke --json` may write `stable_runtime_consumer_snapshot` with outcome
  `observed_source_selected`
- approved-target activation success and observed-source fallback must remain
  separately distinguishable in machine-readable output
- deterministic stable recovery in the owner path now reuses the same generated
  config path, `WBP_STABLE_CONFIG` handoff, and snapshot topic through
  `healthcheck --json`
- deterministic stable recovery in the owner path must regenerate generated
  config per approved-target attempt and must not treat a stale generated
  config artifact as authoritative truth
- `healthcheck --json` may expose top-level
  `deterministic_stable_recovery_contract`
- `healthcheck --json` may expose top-level
  `deterministic_stable_recovery_result`
- `status --json` may expose nested
  `stable_runtime_consumer.deterministic_stable_recovery_result`
- owner-path packets now emit `deterministic_stable_recovery_result.entry_lane`
- top-level `STABLE_SERVICE_DISABLED` may be emitted only when:
  - the same packet proves `entry_lane = stable_service_disabled`
  - final live runtime truth remains unhealthy
- absent positive evidence for the narrower disabled-service lane, the system
  must stay on generic `LISTENER_DOWN`
- `stable_service_disabled` classification must remain separate from
  `PROXY_PATH_BROKEN` and `PROXY_REPROBE_FAILED`
- `launch smoke --json` must not surface deterministic stable recovery result as
  if it owned the healthcheck recovery lane
- `sync --json` must not expose deterministic stable recovery as an owner lane
- no new persisted recovery metadata file or snapshot-schema widening is
  required for `stable_service_disabled` packet truth by default
- owner-path writes across fallback reconciliation, generated-config
  materialization, and snapshot refresh must remain visible in `changed_files`
- owner-path packets may expose top-level `last_known_good_proxy_contract`
- owner-path packets may expose top-level `last_known_good_proxy`
  with an honest materialization status such as `declared_not_materialized`
- owner-path packets may expose top-level `current_proxy_adoption_contract`
- that contract may declare a dedicated current-proxy activation handoff such as
  `WBP_CURRENT_PROXY_URL`
- owner-path healthcheck writes may materialize or refresh
  `last_known_good_proxy_url` and `last_known_good_proxy_observed_at`
  in `supervisor-state.json`
- `status --json` may expose the same `current_proxy_adoption_contract` only as
  delegated reporting
- `proxy_reprobe.working_candidate` remains nested bounded evidence only and
  must not become `current_proxy_url` by mere presence
- `status --json` may expose the same `last_known_good_proxy` readout only as
  delegated reporting
- delegated `status --json` must propagate those owner-path writes honestly in
  `changed_files`
- `current_proxy_url` is current live outbound proxy truth and remains separate
  from nested `proxy_reprobe.working_candidate`
- `current_proxy_url` remains separate from persisted
  `last_known_good_proxy.proxy_url`
- ambient shell proxy env must not become the authoritative control-layer truth
  surface for current proxy selection
- control-plane runtime attestation remains proxyless even if a later managed
  runtime activation lane receives a dedicated current-proxy handoff
- candidate existence alone must never produce top-level `OK`
- persisted last-known-good proxy truth must never by itself change top-level
  `status`, `liveness`, `machine_error_code`, `endpoint`, or `current_proxy_url`
