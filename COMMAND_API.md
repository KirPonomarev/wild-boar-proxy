<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

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
- `launch client --json`
- `healthcheck --json`
- `mode get --json`
- `mode set stable --json`
- `mode set managed --json`
- `policy stage set <10|15|20> --json`
- `rollout rotation inspect --json`
- `rollout stage prove 10 --json`
- `rollout stage prove 15 --json`
- `rollout stage advance 15 <id> --json`
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

## Additional onboarding owner surface

`accounts onboard --json` is the owner surface for reserve-first onboarding
truth.

Onboarding success must not be inferred from external onboarding process exit
code alone.
Successful owner packets must prove, machine-readably:

- a uniquely selected resulting backend identity
- resulting placement in `reserve`
- no silent active-routing change
- post-onboard validate outcome
- post-onboard sync outcome, unless explicitly skipped
- post-onboard status proof summary

`accounts onboard --json` may expose a nested `onboarding_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `input_mode`
- `explicit_auth_ref`
- `new_backend_ids`
- `selected_backend_id`
- `selection_status`
- `reserve_first_enforced`
- `pool_after_onboarding`
- `validate_attempted`
- `validate_outcome`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `external_command_exit_code`
- `external_command_status`
- `active_routing_changed`
- `final_outcome`

Canonical onboarding outcomes include:

- `explicit_auth_imported_to_reserve`
- `reserve_only_success`
- `no_new_auth_detected`
- `ambiguous_new_auth_detection`
- `validate_failed`
- `sync_failed`
- `status_failed`
- `import_failed`

Reserve-first onboarding remains separate from promotion.
`accounts onboard --json` must not place a newly admitted backend directly into
`active`, and any ambiguous or missing identity proof must stop with
`operator_action = user_action`.

## Additional launch-client owner surface

`launch client --json` is the owner surface for bounded external host-client
dispatch truth.

Launch success must not be inferred from OS invocation alone as end-to-end
client-session success.
Successful owner packets must prove, machine-readably:

- explicit bounded client-path input
- runtime precondition checked before dispatch
- effective mode and endpoint observed before dispatch
- env sanitization before launch
- bounded dispatch observation at the OS invocation layer only
- no stronger claim than dispatch truth

`launch client --json` may expose a nested `client_launch_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `client_path`
- `client_path_kind`
- `runtime_precondition_checked`
- `runtime_precondition_status`
- `effective_mode_observed`
- `endpoint_observed`
- `profile_context`
- `env_sanitized`
- `dispatch_method`
- `dispatch_attempted`
- `dispatch_observed`
- `dispatch_exit_code`
- `launch_claim_scope`
- `final_outcome`

Canonical launch-client outcomes include:

- `dispatch_requested`
- `runtime_precondition_failed`
- `client_path_missing`
- `client_path_invalid`
- `dispatch_failed`
- `unsupported_launch_shape`

`launch client --json` remains separate from:

- runtime health ownership in `healthcheck --json`
- delegated runtime readout in `status --json`
- runtime smoke activation truth in `launch smoke --json`

## Additional staged pool-policy owner surface

`policy stage set <10|15|20> --json` is the owner surface for staged
pool-policy mutation truth.

Stage-policy update success must not be inferred from raw schema mutation alone.
Successful owner packets must prove, machine-readably:

- the requested stage is canonically supported
- the current `pool_policy` is valid before mutation
- the stage-to-policy mapping used for the update
- a rollback point captured before write
- post-write policy verification
- no stronger claim than policy truth itself

`policy stage set <10|15|20> --json` may expose a nested
`pool_policy_update_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_stage`
- `mapped_pool_policy`
- `previous_pool_policy`
- `next_pool_policy`
- `policy_validation_status`
- `stage_mapping_status`
- `rollback_point_captured`
- `write_attempted`
- `write_observed`
- `rollback_attempted`
- `rollback_outcome`
- `final_outcome`

Canonical stage-policy outcomes include:

- `stage_policy_updated`
- `already_on_stage`
- `policy_invalid`
- `unsupported_stage`
- `rollback_completed_after_failed_verification`
- `rollback_failed`

`policy stage set <10|15|20> --json` remains separate from:

- active-pool growth execution in `accounts promote <id> --json`
- stage-completion proof in later rollout contours
- runtime-health ownership in `healthcheck --json`
- delegated registry readout in `accounts list --json`

## Additional rollout rotation evidence surface

`rollout rotation inspect --json` is the bounded read surface for rollout
participation evidence truth.

Participation evidence success must not be inferred from raw blocker tokens or
logs alone.
Successful owner packets must prove, machine-readably:

- the bounded local evidence sources that were inspected
- the observed selected backend ids snapshot
- the observed active-pool posture relevant to participation
- whether policy drift or registry identity contradicts participation evidence
- whether evidence is available, insufficient, contradicted, or unknown
- no stronger claim than bounded local participation evidence itself

`participation_evidence_insufficient` must stay precise:

- it may report that the registry active pool is not yet observably expanded
- it may report that the registry active pool is expanded but routing-eligible
  active candidates are not yet observably expanded

`rollout rotation inspect --json` may expose a nested
`rotation_evidence_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_scope`
- `selected_backend_ids_observed`
- `active_pool_count_observed`
- `runtime_active_pool_count_observed`
- `registry_active_pool_count_observed`
- `active_routing_candidate_ids_observed`
- `active_pool_count_agreement_status`
- `stable_inventory_status`
- `policy_drift_status`
- `registry_identity_status`
- `evidence_sources`
- `evidence_strength`
- `participation_status`
- `claim_scope`
- `final_outcome`

Canonical rotation-evidence outcomes include:

- `participation_evidence_available`
- `participation_evidence_insufficient`
- `participation_evidence_contradicted`
- `participation_evidence_unknown`

`rollout rotation inspect --json` remains separate from:

- stable-10 proof ownership in later rollout contours
- lifecycle mutation under `accounts ... --json`
- policy mutation under `policy stage set ... --json`
- runtime-health ownership in `healthcheck --json`

## Additional stage-proof owner surfaces

`rollout stage prove 10 --json` and `rollout stage prove 15 --json` are the
owner surfaces for canonical stage-proof truth at stages `10` and `15`.

Stage-proof success must not be inferred from:

- policy stage alone
- stale status alone
- logs alone
- rotation evidence alone
- runtime smoke alone

Successful owner packets must prove, machine-readably:

- the current staged policy matches the requested canonical stage
- active-pool posture is aligned with the requested stage policy
- reserve-pool posture is aligned with the requested stage policy
- bounded rotation evidence is not contradicted
- live runtime attestation passed
- bounded runtime smoke passed
- delegated runtime smoke did not displace or invalidate the managed runtime
  proof surface being certified
- rollback-readiness remained available
- all delegated evidence lines stayed delegated rather than replacing their
  owner surfaces

`rollout stage prove 10 --json` and `rollout stage prove 15 --json` may expose a nested `stage_proof_result`
surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_stage`
- `policy_stage_status`
- `policy_stage_observed`
- `policy_mapping_status`
- `active_pool_count_observed`
- `reserve_pool_count_observed`
- `rotation_evidence_status`
- `runtime_attestation_status`
- `runtime_smoke_status`
- `rollback_readiness_status`
- `delegated_evidence`
- `proof_gate_status`
- `final_outcome`

Canonical stage-proof outcomes include:

- `stable_10_proved`
- `stable_15_proved`
- `stage_policy_mismatch`
- `insufficient_active_pool`
- `reserve_posture_mismatch`
- `rotation_evidence_insufficient`
- `rotation_evidence_contradicted`
- `runtime_attestation_failed`
- `runtime_smoke_failed`
- `rollback_readiness_failed`
- `proof_blocked`

`rollout stage prove 10 --json` and `rollout stage prove 15 --json` remain separate from:

- policy mutation under `policy stage set ... --json`
- bounded rotation evidence ownership under `rollout rotation inspect --json`
- runtime-health ownership under `healthcheck --json`
- runtime smoke ownership under `launch smoke --json`
- lifecycle mutation under `accounts ... --json`
- stage execution toward `15` or `20`

## Additional stage-15 advance owner surface

`rollout stage advance 15 <id> --json` is the owner surface for one-step
controlled progression from canonical stable stage `10` toward canonical stage
`15`.

Stage-advance success must not be inferred from:

- policy write alone
- promotion subprocess exit alone
- implicit reserve-target selection
- hidden best-reserve logic
- any direct lifecycle mutation outside delegated `accounts promote <id> --json`
- any direct policy rewrite outside delegated `policy stage set 15 --json`

Successful owner packets must prove, machine-readably:

- explicit backend id input (no fallback selection)
- stable-10 proof gate delegated through `rollout stage prove 10 --json`
  when the current policy stage is canonical `10`
- canon-first one-step sequencing:
  delegated policy transition to stage `15`, then one explicit promotion step,
  or one explicit promotion step when already on canonical stage `15`
- postflight attestation, rotation, and readiness checks delegated to their
  owner surfaces
- delegated failures resolve conservatively and may trigger rollback of the
  bounded advancement step
- no stronger claim than one-step control-layer progression; no stage-15 proof
  claim

`rollout stage advance 15 <id> --json` may expose a nested
`stage_advancement_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `requested_stage`
- `requested_backend_id`
- `preflight_stage10_proof_status`
- `preflight_policy_status`
- `policy_transition_status`
- `promotion_status`
- `postflight_attestation_status`
- `postflight_rotation_status`
- `rollback_readiness_status`
- `rollback_attempted`
- `rollback_outcome`
- `delegated_evidence`
- `final_outcome`

Canonical stage-advance outcomes include:

- `advanced_one_step`
- `already_at_stage_15_target`
- `stable_10_proof_failed`
- `backend_not_eligible`
- `preflight_verification_failed`
- `policy_transition_failed`
- `rollback_completed_after_failed_step`
- `rollback_failed`

`rollout stage advance 15 <id> --json` remains separate from:

- stable-10 proof ownership under `rollout stage prove 10 --json`
- policy mutation ownership under `policy stage set ... --json`
- lifecycle mutation ownership under `accounts ... --json`
- rotation evidence ownership under `rollout rotation inspect --json`

## Additional promotion owner surface

`accounts promote <id> --json` is the owner surface for single-account
promotion truth.

Promotion success must not be inferred from external promote subprocess exit
code alone.
Successful owner packets must prove, machine-readably:

- a unique eligible backend identity
- `reserve` precondition truth
- current `pool_policy` gate truth before routing-impacting promotion
- promotion does not exceed the staged active-pool target
- promotion does not drop reserve below the staged reserve target
- a rollback point captured before routing-impacting mutation
- post-promotion sync outcome
- post-promotion status proof summary
- an explicit verified active-routing consequence

`accounts promote <id> --json` may expose a nested `promotion_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `requested_pool`
- `pool_policy_status`
- `pool_policy_observed`
- `active_pool_count_before`
- `active_target_observed`
- `reserve_count_before`
- `reserve_target_observed`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `validate_attempted`
- `validate_outcome`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `final_outcome`

Canonical promotion outcomes include:

- `promoted_to_active`
- `precondition_failed`
- `validate_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `promotion_command_failed`

Rollback proof is limited to control-layer state and companion-managed
artifacts.
It does not imply rollback of engine-internal routing behavior.

## Additional demote owner surface

`accounts demote <id> --json` is the owner surface for explicit
active-to-reserve demotion truth.

Demotion success must not be inferred from external demote subprocess exit
code alone.
Successful owner packets must prove, machine-readably:

- a unique backend identity
- explicit `active -> reserve` demote precondition truth
- held backend rejection (`release` lane only)
- retired backend rejection (no demote lane from `retired`)
- already-reserve classification as either:
  reserve-only verified no-op success, or explicit failure when reserve-only
  proof is missing
- a rollback point captured before any routing-impacting mutation
- post-transition sync outcome when routing consequence changes
- post-transition status proof summary when routing consequence changes
- an explicit routing-consequence classification
- strict single-packet JSON behavior even on command execution failure
- truthful `changed_files` across registry/state/runtime write surfaces

`accounts demote <id> --json` may expose a nested `demote_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `previous_manual_hold`
- `requested_transition`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `reserve_return_confirmed`
- `final_outcome`

Canonical demote outcomes include:

- `backend_demoted_to_reserve`
- `already_reserve`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `demote_command_failed`

## Additional hold and release owner surfaces

`accounts hold <id> --json` is the owner surface for protective isolation
truth.

`accounts release <id> --json` is the owner surface for explicit
hold-to-reserve truth.

Hold and release success must not be inferred from external subprocess exit
code alone.
Successful owner packets must prove, machine-readably:

- a unique backend identity
- explicit precondition truth
- `hold` represented by `manual_hold=true`, not a new pool token
- `release` returns to `reserve`, not directly to `active`
- a rollback point captured before any routing-impacting mutation
- post-transition sync outcome when routing consequence changes
- post-transition status proof summary when routing consequence changes
- an explicit routing-consequence classification

`accounts hold <id> --json` and `accounts release <id> --json` may expose
nested `hold_result` and `release_result` surfaces.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `previous_manual_hold`
- `requested_transition`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `final_outcome`

Canonical hold outcomes include:

- `backend_held`
- `already_held`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `hold_command_failed`

Canonical release outcomes include:

- `backend_released_to_reserve`
- `not_on_hold`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `release_command_failed`

Protective hold remains separate from promotion.
Release remains separate from promotion and must not return a backend directly
to `active`.

## Additional retire owner surface

`accounts retire <id> --json` is the owner surface for terminal retirement
truth.

Retirement success must not be inferred from external subprocess exit code
alone.
Successful owner packets must prove, machine-readably:

- a unique backend identity
- explicit retirement precondition truth
- resulting terminal `retired` lifecycle state
- explicit terminal no-return proof (`retired`, not held, not routing-eligible,
  not selected)
- no automatic return path implied by the owner packet
- a rollback point captured before any routing-impacting mutation
- post-transition sync outcome when routing consequence changes
- post-transition status proof summary when routing consequence changes
- an explicit routing-consequence classification
- truthful `changed_files` across registry/state/runtime write surfaces

`accounts retire <id> --json` may expose a nested `retire_result` surface.
Preferred fields include:

- `status`
- `attempted`
- `backend_id`
- `precondition_status`
- `previous_pool`
- `previous_manual_hold`
- `requested_transition`
- `rollback_point_captured`
- `routing_change_attempted`
- `routing_change_observed`
- `sync_attempted`
- `sync_outcome`
- `status_observed`
- `rollback_attempted`
- `rollback_outcome`
- `external_command_exit_code`
- `external_command_status`
- `terminal_no_return_confirmed`
- `final_outcome`

Canonical retirement outcomes include:

- `backend_retired`
- `already_retired`
- `precondition_failed`
- `rollback_completed_after_failed_verification`
- `rollback_failed`
- `retire_command_failed`

Retirement remains separate from demote semantics.
`accounts retire <id> --json` must not define or imply any later
reserve-return or reactivation lane for `retired` backends.

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
- that handoff remains a launcher-scoped process-local carrier rather than a
  truth surface for `current_proxy_url`
- owner-path packets may now expose nested
  `proxy_reprobe_adoption_result`
  when proxy-path failure found a bounded working candidate and the owner path
  evaluated or attempted current-proxy adoption
- `proxy_reprobe_adoption_result` must remain nested owner-path truth rather
  than a top-level current-proxy truth surface
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
- `status --json` may expose the same `current_proxy_adoption_contract` only as
  delegated reporting
- `status --json` may expose the same nested `proxy_reprobe_adoption_result`
  only as delegated reporting
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
- candidate existence alone must never produce top-level `OK`
- persisted last-known-good proxy truth must never by itself change top-level
  `status`, `liveness`, `machine_error_code`, `endpoint`, or `current_proxy_url`
