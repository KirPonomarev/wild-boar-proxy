<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R66 Final Assurance Strict Live Matrix Closeout

## Goal

Remove B18 false-green evidence acceptance and require subject-specific,
candidate-bound physical proof for every assurance category, including a
strict provider/API/CLI workflow matrix.

## Result

- status: implemented and locally verified
- final verdict: bare `ok=true` / `passed=true` evidence no longer closes any
  required assurance check
- provider live proof now requires DeepSeek, Kimi, GLM, and Qwen API rows plus
  API/API, API/CLI, and CLI/CLI combination rows
- every live row is bound to exact candidate, provider/model/route, actor,
  binding, assignment, session, revision, dispatch, credential-presence,
  output digest, live-response, no-fallback, and no-substitution facts
- migration, privacy, workflow, web lifecycle/security, account isolation,
  package, macOS sandbox, design gate, and protected-network evidence now use
  dedicated schemas instead of generic booleans
- only `provider_cli_live` may be typed pending, and only with
  `WAIT_EXTERNAL_PREREQUISITE`; internal pending receipts fail closed
- malformed evidence fails as typed evidence invalidity without exceptions
- the stale production bundle now fails honestly and is not ready for
  independent audit; no live provider action was authorized or performed
- closure state: CLOSED

## Contour Capsule

- goal: strict B18 evidence schemas and provider/API/CLI live matrix
- branch: `codex/r66-final-assurance-strict-live-matrix`
- head: exact base `667027416dba5466201aece1541569b22319e4de` plus the single logically complete R66 contour commit
- touched files:
  - `wild_boar_proxy/assurance_evidence_bundle_v2.py`
  - `wild_boar_proxy/final_candidate_assurance.py`
  - `tests/test_final_candidate_assurance.py`
  - `audit_results/R66_FINAL_ASSURANCE_STRICT_LIVE_MATRIX_SPEC_2026-08-13.md`
  - `audit_results/R66_FINAL_ASSURANCE_STRICT_LIVE_MATRIX_closeout_2026-08-13.md`
- tests run: focused/affected 64 passed plus 25 subtests; `make check`
  collected 5115 tests; replacement full suite 5114 passed, 1 skipped, plus
  1022 subtests
- blocked risks: false-green generic evidence, provider/combination coverage
  gaps, identity/revision drift, controlled/synthetic promotion, fallback or
  actor substitution, missing output, credential-absent live claims, malformed
  evidence crash, internal checks disguised as external waits
- closure state: CLOSED

## Verification

- focused assurance and gate tests: `64 passed, 25 subtests passed in 26.17s`
- `make check`: compileall green; `5115 tests collected`
- first full-suite attempt: invalid environment run, `93 failed, 5021 passed,
  1 skipped, 1022 subtests`; all failures shared absent ambient `node`
  (`FileNotFoundError`) and were unrelated to the changed assurance surfaces
- root-cause probe: bundled Node `v24.19.0`; the three classification tests and
  one representative UI test passed `4 passed in 0.67s` with the corrected PATH
- one materially different replacement full suite with the bundled Node PATH:
  `5114 passed, 1 skipped, 1022 subtests passed in 1166.56s`
- production assurance readback: stale external bundle is not ready and reports
  typed candidate/schema failures instead of a false green

## Artifacts

- spec: `audit_results/R66_FINAL_ASSURANCE_STRICT_LIVE_MATRIX_SPEC_2026-08-13.md`
- packet: production `run_final_candidate_assurance()` readback, zero writes
- report: this closeout

## Git

- branch: `codex/r66-final-assurance-strict-live-matrix`
- commit: this logically complete contour commit
- pushed: delivery evidence is recorded externally after exact remote readback

## Scope Check

- unrelated work mixed in: no
- runtime/live provider mutation: no
- credential values read or persisted: no
- primary Codex paths read or changed: no
- public release or protected-network action: no
- UI/product changes: no
- private-data risk reviewed: yes; evidence schemas accept only identifiers,
  revisions, booleans, and digests, never credential or raw-provider values

## Notes

- blockers encountered: the initial full suite inherited no ambient Node binary;
  the exact shared signature was localized before one corrected-environment
  replacement, and no production policy was weakened
- resume from here: CLOSED
