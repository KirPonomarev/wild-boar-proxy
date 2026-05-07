<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Next Contour Canon Plan

PLAN_NAME: Next Contour Canon Plan
PLAN_VERSION: 1.6
PLAN_DATE: 2026-05-07
PLAN_OWNER: Product and Platform Team
PLAN_STATUS: Active; canonicalized; live lane blocked until owner authorization and preflight capture
PLAN_SCOPE: Day-of 20-account validation prerequisites and go or no-go decision

## Canon Priority

When sources conflict, decisions must follow this order:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Purpose

Close remaining execution-core prerequisites, run same-day live 20-account
validation, and produce a machine-carried decision packet without mixing layers
or expanding scope.

This contour does not use a fixed 14-day metrics gate.
Validation is executed in one approved same-day high-load contour on
2026-05-07.

## Layer Boundary

Control-layer only in this contour:

- mode orchestration
- lifecycle policy
- onboarding flow
- truth layer
- fallback and recovery
- diagnostics and evidence packet assembly

Engine-layer changes are out of scope unless a concrete blocker is proven and
documented.

Layer-mixing is forbidden in this contour:

- do not patch `CLIProxyAPI` as part of day-of validation work
- do not convert engine instability into unplanned engine refactor inside this
  contour
- if engine blocker is proven, stop and open a separate blocker contour with
  blocker code and evidence

## In Scope

1. Canonicalization closeout for governing docs before claims.
2. Final runtime-hardening tail closure only for active gates.
3. Live-runtime preflight on approved real contour.
4. Same-day 20-account stress validation with machine-carried evidence.
5. Independent audit and final go or no-go packet.

## Out of Scope

1. Rich UI expansion.
2. Installer or packaging.
3. Public release claims.
4. Engine-layer refactor without blocker approval.

## Active Gates For This Contour

- `RUNTIME_ATTESTATION_GATE`
- `STRICT_JSON_COMMAND_API_GATE`
- `STATE_SERIALIZATION_GATE`
- `FALLBACK_DRILL_GATE`
- `SCALE_EVIDENCE_PACKET_GATE` (same-day 20-account validation packet lane)

Note:

- this contour does not introduce a new canonical command surface
  `rollout evidence capture 20`
- evidence is assembled as a redacted machine-carried packet from existing
  canonical command outputs and runtime attestations

## Live Start Gate

Live lane may start only when all conditions are true:

1. `PLAN_NOT_CANONICALIZED` is closed by commit and push.
2. Owner authorization for live-runtime actions is explicit in the current
   thread according to `CANON.md`.
3. Live operation declaration is recorded before command execution.
4. Mandatory preflight packet is captured in strict JSON form.

## Execution Steps

1. Canonicalization pre-check
   - confirm governing docs are clean in worktree
   - if plan text changed, commit and push before live claims
   - record branch and commit hash

2. Runtime-hardening tail revision
   - this is a repo-write lane only
   - close only blockers tied to active gates
   - forbid unrelated refactors
   - run targeted and full test suites
   - close and re-verify repo-write lane before live lane execution

3. Live operation declaration
   - declare exact commands
   - declare exact real paths that may be read
   - declare exact real paths that may be written
   - declare rollback or backup expectation

4. Live preflight
   - run `status --json`
   - run `healthcheck --json`
   - run `accounts list --json`
   - run `rollout rotation inspect --json`
   - run `diagnostics export --json`
   - run fallback drill and verify deterministic stable recovery
   - verify attestation mandatory fields
   - reject any command output that violates strict JSON contract

5. 20-account day-of validation run
   - keep reserve-first lifecycle discipline
   - validate then controlled promotion path
   - run high-load traffic for same-day contour window
   - collect rotation participation and pool health evidence
   - do not patch engine-layer code during this step
   - if an engine blocker is proven, stop this contour and open a separate
     blocker contour

6. Evidence packet build
   - include redacted outputs required by master plan
   - include pool counts and selected backend participation proof
   - include attestation, fallback readiness, commit hash, observation date,
     environment note
   - exclude secrets, auth artifacts, unredacted logs

7. Independent audit lane
   - verify JSON contract integrity (`stdout` single JSON object)
   - verify no log-parsing fallback was used instead of canonical JSON surfaces
   - verify no stale-green or false-green claim
   - verify no layer-mixing actions
   - issue `GO_NEXT_CONTOUR` or `NO_GO` with explicit blocker codes

8. Transition decision
   - if `GO_NEXT_CONTOUR`: move to remaining development closeout, basic UI,
     and pre-release testing
   - if `NO_GO`: reopen only the blocking execution-core contour

## Immediate One-Pass Run Order

This ordered checklist is the default execution path for the next contour:

1. Confirm live gate readiness (`PLAN_NOT_CANONICALIZED` must stay closed).
2. Obtain explicit owner authorization in the current thread.
3. Record live operation declaration (commands, read paths, write paths,
   rollback expectation).
4. Execute mandatory preflight JSON packet and reject invalid JSON output.
5. Execute day-of 20-account high-load validation in control-layer scope only.
6. Build evidence packet, run independent audit, and publish `GO_NEXT_CONTOUR`
   or `NO_GO` with blocker codes.

## Mandatory Artifacts

1. Decision packet in `audit_results/` with explicit blocker codes or GO token.
2. Redacted evidence packet in `audit_results/` for same-day 20-account run.
3. Verification pack with executed commands, exit codes, and timestamps.
4. Short closeout report with branch and commit hash.

Artifacts must not include auth files, secrets, raw unredacted logs, or private
runtime dumps.

Decision packet blocker-code mapping:

- `PLAN_NOT_CANONICALIZED`:
  governing docs dirty or required plan revision not committed and pushed
- `LIVE_RUNTIME_OWNER_AUTH_NOT_EXPLICIT`:
  owner authorization for live-runtime operations is missing in current thread
- `LIVE_PRECHECK_NOT_EXECUTED`:
  mandatory preflight commands are not executed and captured
- `ATTESTATION_FIELDS_MISSING`:
  one or more mandatory runtime-attestation fields are absent
- `STRICT_JSON_CONTRACT_BROKEN`:
  command `stdout` is not exactly one JSON object
- `LOG_PARSING_FALLBACK_USED`:
  operator decision or audit relied on log parsing instead of canonical JSON
  command surfaces
- `STATE_SERIALIZATION_BREACH`:
  evidence shows interleaving or split ownership in serialized mutation path
- `FALLBACK_DRILL_FAILED`:
  deterministic stable fallback or stable recovery readiness is not proven
- `ENGINE_BLOCKER_ESCALATION_REQUIRED`:
  proven engine-layer blocker exists and requires a separate contour outside the
  current control-layer scope

## Dispute Resolution Rule

For any disputed decision:

- choose truth over speed
- choose serialization over convenience
- choose control-layer boundary over engine duplication
- choose fallback determinism over optimistic progress

## Success Criteria

1. Same-day 20-account contour has machine-carried packet with attestation and
   rotation evidence.
2. No invalid JSON command response in critical path.
3. No stale-green or false-green runtime status.
4. Stable fallback remains operational and deterministic.
5. Final decision packet is explicit and auditable.

## Final Claim Discipline

This contour can support:

- `scale-to-20 validated` (same-day contour claim)

This contour cannot by itself imply:

- `pilot_ready`
- `production_ready`

Pilot and release claims require their own gates from `MASTER_PLAN.md` and are
out of scope for this contour closeout.

## Plan Validity Check

- Practicality: the contour is executable in one day because it is limited to
  live-gate closure, preflight, day-of load run, evidence packet, and audit.
- Canon alignment: no deviation from source-of-truth order, live authorization
  rule, strict JSON rule, or staged-claim discipline.
- Layer discipline: no engine-layer fixes are allowed inside this contour; any
  proven engine blocker triggers separate blocker contour opening.

## No-Deviation Statement

This contour does not deviate from `MASTER_PLAN.md` or `CANON.md`.
Any conflict must be resolved in favor of `CANON.md`, then `MASTER_PLAN.md`.

## Day-Of Layer Guardrail

During same-day 20-account validation, the team must not:

- patch engine-layer code
- replace canonical JSON command surfaces with log parsing
- convert runtime-validation lane into refactor lane

If any of these conditions occurs, the run must stop with explicit blocker
codes and reopen as a separate blocker contour.

## Next Contour Operational Plan

1. Obtain explicit owner authorization in the current thread.
2. Record live-operation declaration before any live command:
   exact commands, read paths, write paths, rollback or backup expectation.
3. Execute mandatory preflight JSON packet:
   `status --json`, `healthcheck --json`, `accounts list --json`,
   `rollout rotation inspect --json`, `diagnostics export --json`.
4. Apply preflight decision gate:
   if preflight fails, issue `NO_GO` with blocker codes;
   if preflight passes, proceed to same-day load run.
5. Execute same-day 20-account validation in control-layer scope only:
   reserve-first lifecycle, validate, controlled promotion, high-load run.
6. Build redacted evidence packet:
   attestation, rotation participation, truthful pool counts,
   fallback readiness, commit hash, observation date, environment note.
7. Run independent audit and publish final contour verdict:
   `GO_NEXT_CONTOUR` or `NO_GO` with explicit blocker codes.

## Layer-Mixing Stop Triggers

The contour must stop immediately and reopen as a separate blocker contour if:

- engine-layer patching is attempted
- canonical JSON surfaces are replaced by log parsing
- runtime-validation lane is converted into refactor work
