<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R60 Gate Evidence Requirement Repair

## Objective

Require the immutable R60 one-shot production-admission repair supplement in
`GateEvidenceBundleV2`, so the historical B09 closeout cannot independently
re-earn the reopened stage after R60.

## In Scope

- add `R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION` to the server-owned required
  evidence stages;
- prove that deleting the R60 supplement makes the bundle fail with
  `required_stage_missing`;
- preserve the historical B09 receipt without rewriting or duplicating its
  stage identifier.

## Out of Scope

- one-shot runtime, provider adapters, binaries, credentials, provider calls,
  network policy, UI, release, and public publishing;
- rewriting historical external receipts or clearing the B09 invalidation
  before this guard is merged and reverified.

## Constraints

- the contour starts from exact merged `origin/main` commit
  `8ab0dcaae45ce1e57bd2b1e3e9d4604abab9d793`;
- after the unrelated R60B baseline repair and its prerequisite test-harness
  repairs merged, the preserved three-file checkpoint resumes on exact merged
  `origin/main` commit `dd3633050120d8f228f9e06b5a5b4c584bb403c7`
  without widening this contour;
- the external R60 receipt uses the unique stage
  `R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION` and remains bound to the R60 merge
  commit and closeout blob;
- required-stage and receipt identifiers remain unique;
- no protected authentication, VPN, proxy, firewall, port, tag, release, or
  canonical-checkout surface may change.

## Assumptions

- `GateEvidenceBundleV2` remains the authoritative execution-core evidence
  verifier;
- a repair supplement must be independently required, following the existing
  R59 pattern, because an old stage receipt proves only its historical merge.

## Acceptance Criteria

- [ ] `R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION` is present exactly once in
  `REQUIRED_STAGES`;
- [ ] a complete synthetic bundle earns the gate with both B09 and R60
  receipts;
- [ ] removing only the R60 receipt makes the bundle fail with the exact
  missing-stage finding;
- [ ] focused, core, custom-stability, full-suite, hygiene, diff, and closeout
  resilience verification pass on the final candidate.

## Verification

- tests: focused `tests/test_gate_evidence_bundle_v2.py`, then repository core,
  custom-stability, and full suites;
- build: `make check`;
- manual: inspect exact required-stage uniqueness and external receipt binding;
- live evidence: not applicable; this is an offline verifier-only repair.

## Open Questions

- none; the reproduced duplicate-stage rejection and existing R59 supplement
  pattern determine the repair.
