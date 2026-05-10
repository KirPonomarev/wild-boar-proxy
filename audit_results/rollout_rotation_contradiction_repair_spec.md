<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Rollout Rotation Contradiction Repair

## Objective

Classify the current `ROTATION_EVIDENCE_CONTRADICTED` blocker and decide
whether this contour may admit a targeted repo repair.

## In Scope

- capture fresh read-only owner packets
- inspect `status --json` policy drift truth
- inspect `rollout rotation inspect --json` policy drift delegation
- inspect selected-backend snapshot and rotation contradiction tests
- classify root cause
- decide repair admission
- close with a machine-carried verdict

## Out of Scope

- UI work
- live normalization
- `sync --json`
- stable repair apply
- policy mutation
- account mutation
- rollout stage advance
- manual runtime file edits
- broad runtime refactor

## Constraints

- `rollout rotation inspect --json` validates rotation evidence but does not
  create or repair it
- fresh owner command packets are the primary truth
- no live mutation is allowed in this contour without a separate operation
  declaration
- no code repair is admitted unless Phase 0 proves a narrow repo-owned defect

## Acceptance Criteria

- [x] Phase 0 read-only packets captured
- [x] packet JSON validated
- [x] root cause classified exactly once
- [x] repair admission decision recorded
- [x] no UI work performed
- [x] no live mutation performed

## Verification

- tests:
  - `python3 -m json.tool` over raw owner packets and verdict artifacts
- build:
  - not applicable
- manual:
  - code/test inspection of rotation policy drift branches
- live evidence:
  - `audit_results/rollout_rotation_contradiction_repair_raw/status.json`
  - `audit_results/rollout_rotation_contradiction_repair_raw/healthcheck.json`
  - `audit_results/rollout_rotation_contradiction_repair_raw/accounts.json`
  - `audit_results/rollout_rotation_contradiction_repair_raw/rotation.json`
  - `audit_results/rollout_rotation_contradiction_repair_raw/posture20.json`

## Open Questions

- the next contour must decide whether to authorize live operational
  normalization or keep the gate closed until operator-provided pool truth
  changes
