<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R60A Gate Evidence Requirement Repair Closeout

## Goal

Require the immutable R60 one-shot production-admission supplement in
`GateEvidenceBundleV2`, so the historical B09 closeout cannot independently
re-earn the reopened stage.

## Result

- status: verifier guard and deterministic regression complete with renewed full local verification
- final verdict: R60A_GATE_EVIDENCE_REQUIREMENT_REPAIR_CODE_COMPLETE
- closure state: CLOSED

## Contour Capsule

- goal: require the unique `R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION` receipt in addition to the historical B09 receipt and fail closed when the supplement is absent
- branch: codex/r60a-one-shot-evidence-guard
- head: c12e8094f00040e78147b40eb44208d4d5e4a6d0
- touched files: wild_boar_proxy/gate_evidence_bundle_v2.py, tests/test_gate_evidence_bundle_v2.py, audit_results/R60A_GATE_EVIDENCE_REQUIREMENT_REPAIR_SPEC_2026-08-11.md, audit_results/R60A_GATE_EVIDENCE_REQUIREMENT_REPAIR_closeout_2026-08-11.md
- tests run: 21 focused verifier tests; 630 core tests and 132 subtests; 27 Custom stability tests and 5 subtests; 5069 full-suite tests and 985 subtests
- blocked risks: none within the admitted offline verifier scope; B09 completion remains fail-closed until the merged guard and evidence bundle are independently reverified
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest -q tests/test_gate_evidence_bundle_v2.py` passed 21 tests in 11.59 seconds; `make test-core` passed 630 tests and 132 subtests in 65.96 seconds; `make test-custom-stability` passed 27 tests and 5 subtests in 2.60 seconds; `make test-full` passed 5069 tests and 985 subtests in 1338.07 seconds
- build: `make check` compiled repository Python surfaces and collected 5069 tests; the only full-suite warning was the pre-existing Pillow `Image.getdata` deprecation
- manual: `R60_ONE_SHOT_CLI_PRODUCTION_ADMISSION` occurs exactly once in `REQUIRED_STAGES`; the external evidence index contains exactly one matching reference bound to R60 merge `8ab0dcaae45ce1e57bd2b1e3e9d4604abab9d793`, receipt digest `c0e06835b73319dc8d2cf3e41a67c2ea9d64c3f3615afc42d60dea7e663ff1bc`, and the approved plan digest
- live verification: not applicable; the contour is an offline verifier-only repair and made no provider request, credential read, login action, external network call, or live-runtime mutation

## Artifacts

- spec: `audit_results/R60A_GATE_EVIDENCE_REQUIREMENT_REPAIR_SPEC_2026-08-11.md`
- packet: the focused regression removes only the R60 supplement from an otherwise complete synthetic evidence index and proves `earned=false`, the exact missing stage, and `required_stage_missing`
- report: external execution-state revisions 94 through 108 preserve the checkpoint, dependency diagnosis, exact stash identity, R60B recovery, restored write set, and renewed verification receipts

## Git

- branch: codex/r60a-one-shot-evidence-guard
- commit: c12e8094f00040e78147b40eb44208d4d5e4a6d0 contains the verifier requirement, regression, and resumed spec
- pushed: yes; the logically complete implementation plus this closeout commit is published and read back from the same branch before merge admission

## Scope Check

- unrelated work mixed in: false; the final diff contains only the required-stage tuple addition, its direct fail-closed regression, spec, and closeout
- private-data risk reviewed: no secrets, credentials, provider routes, main Codex material, runtime state, protected host settings, UI, release, tag, or user-owned canonical-checkout changes were introduced

## Notes

- blockers encountered: the first full-suite exposed the unrelated web readiness timeout; R60B and its three baseline test-harness prerequisites were isolated, merged, and fully reverified before this exact three-file checkpoint resumed; one combined core/custom output handle was lost after a tool yield, so a single recorded replacement core run supplied a terminal exit receipt without masking a test failure
- resume from here: CLOSED
