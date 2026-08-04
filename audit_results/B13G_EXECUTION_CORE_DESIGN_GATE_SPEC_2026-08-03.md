<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: B13G Execution-Core Design Gate

## Objective

Run the repository-native design gate and earn the exact token
`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` as real evidence.
B14 cannot start from a narrative claim: the token must be earned by a
deterministic, verifiable gate packet. Execution-core repair is considered
closed only with the recorded facts (all execution-core contours merged,
evidence-index references, green full suite); the gate never fabricates
those facts.

## In Scope

- `wild_boar_proxy/execution_core_design_gate.py` (new):
  - `execution_core_repair_closed_evidence(...)`: records the input facts
    (completed contour stages, evidence-index reference count, full-suite
    status, main head) without inventing any
  - `run_execution_core_design_gate(...)`: integrates the repository-native
    `design_gate_accessibility` gate with the execution-core evidence; the
    exact token `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`
    appears in the packet only when the gate is earned
  - fail-closed behavior: core open or any a11y check failing yields
    `DESIGN_GATE_NOT_EARNED` with no token
- `audit_results/B13G_EXECUTION_CORE_DESIGN_GATE_evidence_2026-08-03.json`:
  the generated evidence packet (real evidence stage)
- tests: `tests/test_execution_core_design_gate.py`
- B13G spec + closeout in `audit_results/`

## Out of Scope

- UI expansion (B14, starts only after this gate)
- design polish contours
- any canon change (no command/state schema touch)

## Constraints

- the token is earned, never claimed: packet carries it only when
  `design_gate_earned` is true
- input facts are recorded as evidence, not asserted by the module
- gate checks mirror the repository-native accessibility contract
  (a11y / keyboard / contrast / focus / responsive)

## Assumptions

- execution-core repair closure is evidenced by the plan ledger
  (completed stages), the evidence index, and the green full suite;
  the module records these facts verbatim

## Acceptance Criteria

- [ ] gate packet earns the exact token when core evidence is closed and
      all checks pass
- [ ] token is absent when the core is open or any check fails
- [ ] evidence packet artifact is generated and recorded in the closeout
- [ ] full verification green; closeout merged to `main`

## Verification

- tests: `tests/test_execution_core_design_gate.py`;
  `make check`; `make test-core`; `make test-custom-stability`;
  `make test-web-e2e`; `make test-full`
- build: `make check` compileall
- manual: `run_execution_core_design_gate(...)` with the recorded facts ->
  token earned packet (recorded in the evidence artifact)
- live evidence: none (deterministic local gate)

## Open Questions

- None blocking.
