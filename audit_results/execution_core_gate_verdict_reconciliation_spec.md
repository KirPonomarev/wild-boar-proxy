<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: Execution Core Gate Verdict Reconciliation

## Objective

Resolve the active design-gate truth after conflicting evidence:
`stage20_c6` claims `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`,
while the later pushed execution-core closure and fresh owner packets show a
red runtime posture around rotation evidence.

## In Scope

- inspect current tracked `stage20_c6` gate artifacts
- inspect pushed `origin/codex/execution-core-gate-closure` RED artifacts
- capture fresh read-only owner packets
- classify the active verdict as exactly one of:
  - `GREEN_FOR_BASIC_COMPANION_UI`
  - `RED_EXECUTION_CORE_FOLLOWUP_REQUIRED`
- write the machine-carried verdict and closeout

## Out of Scope

- UI implementation
- runtime repair
- policy mutation
- stage advance
- account mutation
- direct state/log truth as primary evidence
- branch merge or PR conflict resolution

## Constraints

- fresh owner command packets outrank older narrative artifacts
- older artifacts must be explained rather than ignored
- no repair work may be performed inside this contour
- no UI work may be performed inside this contour

## Acceptance Criteria

- [x] branch status recorded
- [x] relevant GREEN and RED artifacts inspected
- [x] fresh owner packets captured and JSON-valid
- [x] gate verdict explicit
- [x] contradiction explained
- [x] next legal contour named exactly once

## Verification

- tests:
  - `python3 -m json.tool` over all fresh owner packets and verdict JSON
- build:
  - not applicable
- manual:
  - read-only owner packet capture
- live evidence:
  - `audit_results/gate_reconciliation_raw/status.json`
  - `audit_results/gate_reconciliation_raw/healthcheck.json`
  - `audit_results/gate_reconciliation_raw/mode.json`
  - `audit_results/gate_reconciliation_raw/accounts.json`
  - `audit_results/gate_reconciliation_raw/rotation.json`
  - `audit_results/gate_reconciliation_raw/posture20.json`

## Open Questions

- whether the next repair contour should address stable policy drift directly
  or first localize why `stage20_c6` green-for-UI no longer matches fresh packet
  truth
