<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Runtime Attestation Detail Admission Spec

## Contour

`RUNTIME_ATTESTATION_DETAIL_ADMISSION`

## Goal

Decide whether a richer runtime attestation detail surface may be admitted into
the web design UI, and define the narrowest truthful product contract.

## Final verdict

`RUNTIME_ATTESTATION_DETAIL_READONLY_ADMITTED_WITH_EXISTING_PACKETS`

## Why this verdict

The repo already has packet-owned readonly runtime attestation detail surfaces.
This is not a hypothetical future contract.

Existing canon and code already establish:

- `status --json` as the primary operator runtime truth surface
- `healthcheck --json` as the owner path for live runtime attestation
- optional operator-triggered attestation detail from `healthcheck --json`
- nested delegated recovery detail under `status --json`

So a bounded readonly attestation detail screen is admitted from existing
packets. But this admission is not unlimited. The contour does not admit:

- browser-owned synthesis of a stronger runtime verdict
- path-bearing internal detail
- selected source paths
- config/snapshot file locations
- recovery detail as a replacement for top-level runtime truth

## Canon anchors

- Wild Boar Proxy remains the managing/control layer.
- CLIProxyAPI / strict JSON command packets remain truth owners.
- UI is not a runtime verifier.
- UI is not a recovery owner.
- UI is not a log parser.
- `status --json` remains the primary operator runtime truth surface.
- `healthcheck --json` may supply deeper attestation detail, but must not
  replace or silently redefine top-level runtime truth.
- attestation detail must remain packet-owned readonly truth only.
- `deterministic_stable_recovery_result`, when shown, remains a delegated
  secondary surface and must not collapse into a single runtime-health claim.
- desired mode and effective mode remain separate facts.
- observation-only and effectful-confirmed states remain separate facts.
- UI must not synthesize a stronger verdict than any one packet actually proves.

## Repo facts

1. `UI_READINESS_SPEC.md` already says:
   - the Runtime Status screen must read from `status --json`
   - optional operator-triggered detail may come from `healthcheck --json`
   - required runtime fields include `attestation_summary`
   - `attestation` detail fields are explicitly listed
   - desired mode and effective mode must be shown separately

2. `RUNTIME_CONTRACT.md` explicitly states:
   - live attestation is owned by `healthcheck --json`
   - `status --json` may expose a summary but must not replace live attestation

3. `COMMAND_API.md` explicitly distinguishes:
   - runtime-health ownership in `healthcheck --json`
   - delegated runtime readout in `status --json`
   - top-level healthcheck `deterministic_stable_recovery_contract`
   - top-level healthcheck `deterministic_stable_recovery_result`
   - nested `status --json` delegated
     `stable_runtime_consumer.deterministic_stable_recovery_result`

4. `wild_boar_proxy/runtime.py` already materializes:
   - `attestation_summary` into `status --json`
   - `stable_runtime_consumer` into `status --json`
   - top-level `deterministic_stable_recovery_contract` in `healthcheck --json`
   - top-level `deterministic_stable_recovery_result` in `healthcheck --json`

5. `tests/test_cli.py` confirms:
   - `status --json` exposes the stable runtime consumer contract
   - `status --json` delegates nested deterministic recovery result
   - `healthcheck --json` exposes owner-path deterministic recovery result
   - `guardrail_status` and `effectful_claim_allowed` separate observation-only
     from confirmed/effectful recovery claims

6. `tests/test_ui_shell.py` confirms:
   - `attestation_summary` is required and validated as a structured object
   - `stable_runtime_consumer` is expected as structured contract data

7. `audit_results/ui_final_screen_passports_2026-05-14.json` still marks
   `26_runtime_attestation_detail` as admission-required, but its note is
   consistent with this contour outcome: the screen needs bounded JSON
   attestation packet truth, which already exists in the current command
   surfaces.

## Admitted readonly field groups

### Group 1. Primary runtime truth from `status --json`

Admitted:

- `status`
- `human_message`
- `machine_error_code`
- `next_action`
- `liveness`
- `severity`
- `operator_action`
- `desired_mode`
- `effective_mode`
- `endpoint`
- `current_proxy_url`
- `attestation_summary`
- `last_error`

Rule:

- these remain the primary operator runtime truth layer

### Group 2. Attestation detail from `healthcheck --json`

Admitted when packet-owned:

- `listener_ok`
- `models_ok`
- `responses_ok`
- `effective_mode_match`
- `base_url_match`
- `selected_backends_digest`
- `observed_at_utc`
- `attestation_source`
- `runtime_version`

Rule:

- this is a deeper readonly detail layer
- it must not silently replace the top-level runtime truth layer

### Group 3. Stable runtime consumer summary from `status --json`

Admitted summary-level contract fields:

- `stable_runtime_consumer.status`
- `desired_stable_runtime_consumer_source.status`
- `desired_stable_runtime_consumer_source.source_kind`
- `effective_stable_runtime_consumer_source.status`
- `effective_stable_runtime_consumer_source.source_kind`
- `effective_stable_runtime_consumer_source.matches_desired`
- `consumer_activation_readiness.status`
- `consumer_activation_readiness.machine_error_code`
- `consumer_activation_readiness.reason`
- `deterministic_stable_recovery_contract.status`
- `deterministic_stable_recovery_contract.entry_owner`
- `deterministic_stable_recovery_contract.owner_command_surface`
- `deterministic_stable_recovery_contract.top_level_truth_boundaries`
  summary fields only

Rule:

- this is admitted as readonly contract/status detail
- it must not become a browser-owned runtime selection model

### Group 4. Delegated recovery detail

Admitted summary-level fields only:

- `deterministic_stable_recovery_result.status`
- `attempted`
- `entry_lane`
- `outcome`
- `re_enable_method`
- `selected_source_kind`
- `live_runtime_observation_confirmed`
- `confirmation_basis`
- `effectful_claim_allowed`
- `guardrail_status`

Rule:

- this section is explicitly secondary
- it must not replace top-level runtime truth
- it must not be collapsed into a single “runtime recovered” claim

## Not admitted in this contour

- `selected_source_path`
- raw file paths in `resolved_path`
- `config_file`
- `snapshot_file`
- `generated_config_file`
- other path-bearing implementation detail
- internal inventory/location detail
- raw `current_snapshot` payloads
- browser-owned synthesis of “ready for rollout”
- browser-owned synthesis of “proven healthy”
- browser-owned synthesis of “recovered now”

## Browser payload boundary

Allowed in the current admitted shape:

- `ui_action`

Optional in a future implementation only if already bounded and admitted:

- readonly presentation mode

Forbidden:

- `command_id`
- `argv`
- `shell`
- path
- token
- secret
- recovery selector
- strategy selector
- raw packet fragments

## Copy rules

UI may say:

- runtime attestation detail
- observed runtime check
- delegated recovery detail
- observation only
- confirmed recovery claim allowed
- stale
- historical
- unavailable
- unknown

UI must not say:

- proven healthy
- fully verified
- ready for rollout
- recovered now
- safe now
- guaranteed fallback
- guaranteed recovery
- failover confirmed
- active route proved

## Identity preservation check

External references may inform interaction patterns only.
Visual language, layout hierarchy, copy tone, and product identity must stay
aligned with the approved Wild Boar design baseline.
