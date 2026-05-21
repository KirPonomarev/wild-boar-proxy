<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# 16-Account Evidence Capture Runbook

## Purpose

This runbook controls the safe dry-run and optional live execution of:

```sh
rollout evidence capture 16 --json
```

The command is the owner surface for the observed 16-account field evidence
packet gate.
It aggregates existing machine evidence and writes a redacted evidence bundle to
a temp/export directory.
It is not a runtime repair command, a diagnostics support dump command, an
account lifecycle command, or a scale-to-20 proof command.

## Claim Boundary

Allowed claim:

- `field_evidence_observed_only`

Forbidden claims:

- `stable_16_proved`
- `stable_20_proved`
- `scale_complete`
- `pilot_ready`
- `production_ready`
- `healthy_16`
- `stable_pool_proved`

No evidence packet may promote the 16-account field observation into a stronger
claim.
If the packet is `complete`, the only valid interpretation is that a redacted
machine-carried field evidence packet exists for the observed 16-account
contour.

## Layer Boundary

This runbook belongs to the rollout evidence gate.

It may validate:

- strict JSON output
- packet status and blocked reasons
- runtime attestation summary
- rotation evidence summary
- fallback readiness summary
- account and pool count summaries
- redaction status
- evidence bundle artifact paths

It must not become:

- runtime hardening
- stable repair
- proxy adoption or reprobe execution
- onboarding or OAuth
- account promotion or demotion
- diagnostics support case analysis
- scale-to-20 rollout
- pilot or production readiness certification

## Evidence Input Checklist

The packet command is responsible for aggregating the machine-readable evidence.
The runbook verifies that these surfaces are represented in the packet rather
than reimplementing them manually:

- runtime attestation from the non-mutating `healthcheck --json` path
- status summary equivalent to `status --json`
- accounts summary equivalent to `accounts list --json`
- rotation participation evidence from `rollout rotation inspect --json`
- pool counts: active, reserve, retired, healthy, degraded, down
- selected backend ids digest and source validation
- fallback readiness summary
- redacted evidence bundle summary
- commit hash
- observation timestamp
- environment note

Do not replace these machine fields with log excerpts or narrative operator
memory.

## Responsibility Split

Operator responsibilities:

- request or explicitly approve live capture when needed
- provide the intended runtime environment
- preserve existing auth, proxy, profile, and host-client configuration
- report the factual packet status without upgrading the claim

Maintainer responsibilities:

- verify strict JSON structure
- verify required machine fields
- verify redaction and bundle artifact paths
- verify no runtime write-surface mutation occurred
- verify reproducibility notes: commit hash, observation timestamp, and
  environment note
- reject packets with missing, contradicted, or unsafe evidence

Product and Platform Team responsibilities:

- accept or reject the packet as `field_evidence_observed_only`
- decide whether a separate runtime-hardening or scale contour is needed
- decide whether later live capture may be repeated

## Required Safe Environment

Dry-run uses fixture/test environments only.

Live capture, if explicitly approved later, must use the operator's existing
environment paths and must not edit them:

- `WBP_PROFILE_DIR`
- `WBP_MANAGED_DIR`
- `WBP_STABLE_CONFIG`
- `WBP_CONFIG_TOML`
- `WBP_MANAGED_CONFIG_FILE`
- `WBP_REGISTRY_FILE`
- `WBP_STATE_FILE`
- `WBP_RUNTIME_EFFECTIVE_MODE_FILE`

Known sensitive local defaults include:

- `~/.codex-custom-cli`
- `~/.cli-proxy-api/config.yaml`

Do not copy, print, stage, commit, or package auth files, raw state dumps,
private logs, proxy credentials, or private runtime directories.

## Forbidden Commands During This Contour

Do not run these commands as part of evidence capture closeout:

```sh
mode set stable --json
mode set managed --json
stable repair --apply --json
stable target switch --apply --json
sync --json
launch client --json
launch smoke --json
accounts onboard --json
accounts promote <id> --json
accounts demote <id> --json
accounts hold <id> --json
accounts release <id> --json
accounts retire <id> --json
policy stage set <10|15|20> --json
rollout stage advance 15 <id> --json
rollout stage advance 20 <id> --json
rollout stage prove 10 --json
rollout stage prove 15 --json
diagnostics export --json
```

`diagnostics export --json` remains a support snapshot surface.
It is not the owner surface for the 16-account evidence packet gate.

## Preflight Checklist

Before any dry-run or live step:

1. Confirm the current branch and worktree state:

   ```sh
   git status --short --branch
   ```

2. Confirm no evidence bundle or runtime artifact is staged:

   ```sh
   git diff --name-only --cached
   ```

3. Confirm the command contract exists:

   ```sh
   rg -n "rollout evidence capture 16|field_evidence_observed_only" COMMAND_API.md MASTER_PLAN.md
   ```

4. Confirm forbidden claims are not introduced as successful outcomes.
   Matches are allowed only when they are explicitly listed as forbidden:

   ```sh
   rg -n "stable_16_proved|stable_20_proved|scale_complete|pilot_ready|production_ready|healthy_16|stable_pool_proved" .
   ```

5. Confirm the live step has not been approved by accident.
   If no owner authorization exists, stop after fixture dry-run and tests.

## Dry-Run Procedure

Dry-run must use tests/fixtures only.
It must not read or mutate live runtime paths.

Run:

```sh
python3 -m unittest -k "rollout_evidence_capture" tests.test_cli
```

Expected result:

- tests pass
- command emits exactly one JSON object in tested paths
- `scale_evidence_packet_result` is present
- `claim_scope` is `field_evidence_observed_only`
- packet outcomes are one of:
  - `field_evidence_packet_complete`
  - `field_evidence_packet_incomplete`
  - `field_evidence_packet_contradicted`
  - `field_evidence_packet_unsafe_to_claim`
- `changed_files` contains evidence bundle file paths only
- no evidence bundle artifacts are staged in git

Then run the full CLI suite:

```sh
python3 -m unittest tests.test_cli
```

Run formatting and diff checks:

```sh
git diff --check
git status --short --branch
```

## Optional Live Capture Gate

Live capture is optional and requires owner authorization in the current
thread.

Owner authorization may be either:

- the current project-scoped standing approval defined by `CANON.md`
- a later explicit one-off owner GO marker

Without owner authorization:

- do not run `rollout evidence capture 16 --json` against live paths
- do not inspect private runtime dumps
- do not read auth files directly
- do not touch proxy config
- close this runbook contour through `DELIVERY_RULES.md` without a live capture

If owner authorization is given later, run only:

```sh
rollout evidence capture 16 --json
```

Do not run repair, sync, mode, lifecycle, onboarding, diagnostics export, stage
prove, or stage advance commands as part of the live capture.

## Live Capture Validation

If live capture is owner-authorized and run, validate only the returned JSON
and the redacted bundle artifact paths.

Required top-level checks:

- `status`
- `exit_code`
- `human_message`
- `machine_error_code`
- `changed_files`
- `next_action`
- `liveness`
- `severity`
- `operator_action`
- `scale_evidence_packet_result`

Required packet checks:

- `claim_target == "16"`
- `claim_scope == "field_evidence_observed_only"`
- `packet_status` is one of `complete`, `incomplete`, `contradicted`,
  `unsafe_to_claim`
- `final_outcome` is one of the documented field-evidence outcomes
- forbidden claims do not appear as successful outcomes
- `blocked_reasons` is machine-readable
- `runtime_attestation_summary.attestation` is present
- the nested attestation carries all mandatory runtime-attestation fields:
  - `listener_ok`
  - `models_ok`
  - `responses_ok`
  - `effective_mode_match`
  - `base_url_match`
  - `selected_backends_digest`
  - `observed_at_utc`
  - `runtime_version`
  - `attestation_source`
- `diagnostics_bundle_summary.redaction_status` is present
- `changed_files` lists bundle artifact file paths, not live runtime files

## Redaction Validation

Evidence bundle files must not contain:

- auth file contents
- private tokens
- raw bearer headers
- proxy credentials
- raw unredacted logs
- real account secrets
- private runtime dumps

Use bounded text checks on the returned bundle artifact paths:

```sh
rg -n "OPENAI_API_KEY|sk-[A-Za-z0-9_-]+|Authorization: Bearer|://[^/[:space:]@:]+:[^/[:space:]@]+@" <bundle-artifact-paths>
```

No matches are allowed.

If any secret pattern appears, classify the result as `unsafe_to_claim`.
Do not commit the bundle.

## No-Git-Artifact Rule

Evidence bundles are runtime artifacts.
They must not be committed.

Before commit:

```sh
git status --short --branch
git diff --name-only --cached
```

Allowed staged files in this contour are repo-authored docs or tests only.
Do not stage temp bundle files, auth files, runtime state, logs, or private
config files.

## Failure Classification

`complete` means:

- runtime attestation passed
- rotation evidence is available
- fallback readiness is ready
- redaction passed
- no blocked reasons exist
- no runtime mutation was detected

`incomplete` means one or more of:

- runtime attestation failed or is missing
- rotation evidence is stale, unknown, or insufficient
- fallback readiness is missing
- commit hash is missing
- pool count posture is incomplete

`contradicted` means one or more of:

- rotation evidence is contradicted
- registry identity is ambiguous
- selected backend digest mismatches
- runtime pool count contradicts registry pool count

`unsafe_to_claim` means one or more of:

- redaction failed
- auth, token, or proxy secret is detected
- runtime write surface changed
- the command required mutation to proceed
- bundle includes forbidden runtime data

If the result is not `complete`, record the factual packet status and stop.
Do not repair runtime, change pool lifecycle, or retry with mutation commands in
this contour.

## Factual Report Template

Use this template for dry-run and optional live capture notes:

```text
Contour:
Branch:
Commit:
Capture mode: dry-run fixture | live approved
Owner authorization for live capture: standing approval | exact marker | no
Command:
Exit code:
Machine error code:
Packet status:
Final outcome:
Claim scope:
Runtime attestation status:
Rotation evidence status:
Fallback readiness status:
Diagnostics redaction status:
Changed files:
Bundle committed: no
Forbidden claim found: yes | no
Secret pattern found: yes | no
Runtime/proxy/auth config modified: yes | no
Tests:
Audit:
Next action:
```

## Runbook Contour Closeout

Delivery itself is governed by `DELIVERY_RULES.md`.
The checklist below is only the evidence-capture runbook contour closeout gate,
not a reusable runtime operation procedure.

This contour is closed only when:

- this runbook exists
- dry-run tests pass
- full CLI tests pass
- `git diff --check` passes
- independent audit reports no P0/P1/P2 findings
- live capture is either explicitly skipped or owner-authorized
- no live runtime, proxy, or auth config was modified
- no evidence bundle or runtime dump is staged
- changes are committed
- branch is pushed
