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
