<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B18 Final Candidate Assurance Closeout

## Goal

Run the final candidate assurance checks: exact-remote-head repository
state, full-test evidence, package, privacy, migration, provider, CLI,
workflow, web, account-isolation, and protected-network. B18 may emit only
`FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`, never `DONE`.

## Result

- status: implemented and verified
- final verdict: `final_candidate_assurance.py` runs 11 deterministic
  checks; on this machine all 11 pass and the packet emits exactly
  `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT` (never `DONE`): local
  main equals origin/main; full-suite evidence recorded (4896 passed,
  clean run); packaging imports resolve; packet redaction verified;
  state migration v1->v2 probe with backup; 4-provider release set;
  one-shot CLI runtime receipt; sequential workflow delivery; web
  workflow control gate endpoint; qwen/kimi provider-home isolation
  (0700, distinct); protected ports product truth with recorded network
  air-gap facts
- closure state: CLOSED

## Contour Capsule

- goal: B18 final candidate assurance
- branch: `codex/b18-final-candidate-assurance`
- head: `c36561bd2f26dfd762ee35b357a3343d6fe7a6b7` (base before contour commit)
- touched files: `wild_boar_proxy/final_candidate_assurance.py` (new),
  `tests/test_final_candidate_assurance.py` (new),
  `audit_results/B18_FINAL_CANDIDATE_ASSURANCE_SPEC_2026-08-03.md`,
  `audit_results/B18_FINAL_CANDIDATE_ASSURANCE_closeout_2026-08-03.md`
- tests run: `tests/test_final_candidate_assurance.py` (6); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`; `make package-web-smoke`
- blocked risks: emitting DONE, greenwashing check evidence, Codex
  surface reads, secret leakage
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_final_candidate_assurance.py` -> `6 passed` (ready status
    emitted with 11/11 passed; DONE never emitted; all check ids covered;
    strict packet; fails closed on bad evidence; no secrets in packets)
  - manual run recorded: `status: ok`,
    `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`, 11/11 passed
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - `make package-web-smoke` -> green (wheel/sdist build evidence)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
  - `make package-web-smoke` green
- manual:
  - `run_final_candidate_assurance(full_suite_passed=4896, clean_run=True,
    network_air_gap_evidence=...)` -> `FINAL_CANDIDATE_READY_FOR_INDEPENDENT_AUDIT`
- live verification:
  - none; pending live gates remain recorded as pending

## Artifacts

- spec: `audit_results/B18_FINAL_CANDIDATE_ASSURANCE_SPEC_2026-08-03.md`
- packet: assurance run recorded in this closeout (11/11 passed)
- report: final candidate is ready for the independent audit (Script 5);
  the DONE transition is reserved for Script 6 after the audit verdict

## Git

- branch: `codex/b18-final-candidate-assurance`
- commit: contour commit contains the assurance module, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (redaction probe, no Codex reads, no
  secrets in packets)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none beyond routine probe calibration (package
  metadata resolution in a non-installed checkout; MigrationResult
  accessors)
- resume from here: CLOSED
