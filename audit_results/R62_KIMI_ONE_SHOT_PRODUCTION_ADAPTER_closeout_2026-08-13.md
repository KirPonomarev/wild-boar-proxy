<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R62 Kimi One-Shot Production Adapter Closeout

## Goal

Admit a server-owned, fail-closed Kimi Code production one-shot adapter with
current prompt-mode argv, isolated data and auth-presence boundaries, bounded
stream-JSON output, read-only project access, and an operational-child-only
network boundary without claiming live provider proof.

## Result

- status: implementation and deterministic verification complete
- final verdict: PASS for R62 code admission; B11_LIVE remains explicitly unproven
- closure state: CLOSED

## Contour Capsule

- goal: replace the fake-only Kimi code claim with a sealed production adapter contract
- branch: `codex/r62-kimi-one-shot-production-adapter`
- head: verified pre-closeout candidate `62f900d5e3e48417911bd00a9e61aa98b3697d91`
- touched files: `RUNTIME_CONTRACT.md`; R62 spec and ADR; six focused test modules; `wild_boar_proxy/final_candidate_assurance.py`; `wild_boar_proxy/gate_evidence_bundle_v2.py`; `wild_boar_proxy/kimi_one_shot_cli.py`; `wild_boar_proxy/one_shot_cli_runtime.py`; merged R62F web-fetch-budget repair and its completed evidence
- tests run: focused implementation 169 passed plus 9 subtests; original implementation full suite 5087 passed plus 994 subtests; merged-candidate focused 126 passed plus 9 subtests; merged-candidate collection 5088 tests; merged-candidate core 638 passed plus 141 subtests; merged-candidate custom-stability 27 passed plus 5 subtests; R62F full suite 5081 passed plus 989 subtests locally and two independent green CI full suites
- blocked risks: exact Kimi binary admission, operator-managed auth, and real provider positive/negative proof were not authorized or performed and remain B11_LIVE gates
- closure state: CLOSED

## Verification

- tests: implementation `169 passed, 9 subtests passed`; implementation full suite `5087 passed, 1 warning, 994 subtests passed in 1086.14s`; merged candidate `126 passed, 9 subtests passed in 35.86s`; merged-candidate core `638 passed, 141 subtests passed in 68.59s`; merged-candidate custom stability `27 passed, 5 subtests passed in 2.61s`; R62F CI full suites passed in `24m02s` and `26m12s`
- build: merged-candidate `make check` compiled the tree and collected 5088 tests
- manual: exact Kimi argv, fixed privacy and execution environment, isolated data root, empty skills root, credential-metadata-only boundary, bounded JSONL success parsing, unique R62 evidence stage, and distinct live-proof boundary were reviewed; `git diff --check` and repository hygiene passed on the implementation candidate
- live verification: not performed; no Kimi install, binary admission, login, credential read, auth mutation, or provider request was used

## Artifacts

- spec: `audit_results/R62_KIMI_ONE_SHOT_PRODUCTION_ADAPTER_SPEC_2026-08-13.md`
- packet: deterministic test packets generated in isolated temporary test homes only
- report: `audit_results/ADR_R62_KIMI_PRINT_MODE_SANDBOX_2026-08-13.md`

## Git

- branch: `codex/r62-kimi-one-shot-production-adapter`
- commit: implementation `15897c5d578313f61480e9bd08991eeec3587f42`; required CI test-budget repair merged from PR #154 as `1bd7d32f43943a03a325be4a652c655c2d433f81`; combined pre-closeout candidate `62f900d5e3e48417911bd00a9e61aa98b3697d91`
- pushed: implementation commit was verified at the matching remote branch ref; combined candidate is subject to final exact-SHA push and CI readback

## Scope Check

- unrelated work mixed in: no; the Kimi runtime, contract, evidence guard, direct regressions, and merged prerequisite CI-harness repair are separate complete contours in branch history
- private-data risk reviewed: yes; config and credential contents are never read or emitted, secret-shaped prompts fail before spawn, ambient extension surfaces are denied, and test fixtures contain no real credentials

## Notes

- blockers encountered: the first R62 branch CI run exposed two loaded-runner web requests whose helper abandoned each attempt after three seconds despite a fifteen-second aggregate budget; R62F localized and repaired that independent test-harness defect, proved it locally and in two independent full CI suites, and was merged before the combined R62 candidate was verified
- resume from here: CLOSED
