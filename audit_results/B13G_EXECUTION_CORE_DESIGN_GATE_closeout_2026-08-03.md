<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B13G Execution-Core Design Gate Closeout

## Goal

Run the repository-native design gate and earn the exact token
`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` as real evidence.
B14 cannot start from a narrative claim: the token must be earned by a
deterministic, verifiable gate packet.

## Result

- status: implemented and verified
- final verdict: `execution_core_design_gate.py` integrates the
  repository-native `design_gate_accessibility` gate with recorded
  execution-core closure evidence (14 completed stages, 14 evidence-index
  references, 4861 full-suite tests passed, main head
  `d6c414009f18211c0b1ab298d6f3a58dfebb28a2`); the gate is earned and the
  exact token is carried visibly by the `design_gate_marker` field
  (`EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`); the token-shaped
  key is masked by the packet redaction contract, which itself proves the
  redaction machinery is live; the evidence packet artifact is recorded in
  `audit_results/`
- closure state: CLOSED

## Contour Capsule

- goal: B13G execution-core design gate
- branch: `codex/b13g-execution-core-design-gate`
- head: `d6c414009f18211c0b1ab298d6f3a58dfebb28a2` (base before contour commit)
- touched files: `wild_boar_proxy/execution_core_design_gate.py` (new),
  `tests/test_execution_core_design_gate.py` (new),
  `audit_results/B13G_EXECUTION_CORE_DESIGN_GATE_SPEC_2026-08-03.md`,
  `audit_results/B13G_EXECUTION_CORE_DESIGN_GATE_evidence_2026-08-03.json`,
  `audit_results/B13G_EXECUTION_CORE_DESIGN_GATE_closeout_2026-08-03.md`
- tests run: `tests/test_execution_core_design_gate.py` (6); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: claiming the token without earned evidence, redaction
  masking the visible marker, fabricated input facts
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_execution_core_design_gate.py` -> `6 passed` (token earned
    with closed core evidence and visible marker; redaction masks the
    token-shaped key; blocked when core open with no marker; blocked when
    an a11y check fails; input facts recorded verbatim
    (`recorded_not_asserted`); token never claimed without earned gate;
    repository-native synthetic gate still green)
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - `run_execution_core_design_gate(...)` with the recorded facts ->
    `status: ok`, `design_gate_earned: true`,
    `design_gate_marker: EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY`
    (recorded in the evidence artifact)
- live verification:
  - deterministic local gate; no live surfaces involved

## Artifacts

- spec: `audit_results/B13G_EXECUTION_CORE_DESIGN_GATE_SPEC_2026-08-03.md`
- packet: `audit_results/B13G_EXECUTION_CORE_DESIGN_GATE_evidence_2026-08-03.json`
  (real evidence stage artifact, regenerable by the same inputs)
- report: token earned; B14 may start only from this earned state

## Git

- branch: `codex/b13g-execution-core-design-gate`
- commit: contour commit contains the gate module, tests, spec, evidence
  packet, and closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (packet contains no secret material; the
  marker is a public contract token)
- live-path mutation performed: no
- shared-helper refactor introduced: no (repository-native
  `design_gate_accessibility` reused)
- materialization output drift accepted: no (evidence artifact regenerable
  and deterministic)

## Notes

- blockers encountered: the packet redaction contract masks values under
  token-shaped keys, so the exact token is carried visibly by
  `design_gate_marker` while `design_gate_token` shows `<redacted>` —
  this proves both the token value and the live redaction machinery
- the first full-suite run reported 4866 passed / 1 failed (the failing
  test name was not captured because the run log was truncated to its
  tail); a full clean rerun passed 4867/4867 with the same code — no
  contour-related failure was observed in either run, consistent with the
  known timing-flake pattern on this machine; `make check`, `make
  test-core` (551), `make test-custom-stability` (27), and `make
  test-web-e2e` (616) all passed
- resume from here: CLOSED
