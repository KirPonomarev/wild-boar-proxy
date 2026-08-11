<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R60B Web Readiness Budget Repair Closeout

## Goal

Remove the reproducible cold-start failure in the real loopback web lifecycle
without weakening full live-readonly readiness or extending the caller's
bounded startup deadline.

## Result

- status: code complete with focused, manual, core, custom-stability, and full-suite verification
- final verdict: R60B_WEB_READINESS_BUDGET_REPAIR_CODE_COMPLETE
- closure state: CLOSED

## Contour Capsule

- goal: bind the heavyweight live-readonly readiness request to the remaining outer startup budget so one cold request can finish without two-second timeout retry amplification
- branch: codex/r60b-web-readiness-budget-v2
- head: 0d555de78cfc0b654271d6e44e0a624a64e18f06 (recovery integration head; implementation commit remains 4795e295cf835890746cf20178d3c8ce478f0388)
- touched files: wild_boar_proxy/web_lifecycle.py, tests/test_web_lifecycle.py, audit_results/R60B_WEB_READINESS_BUDGET_REPAIR_SPEC_2026-08-11.md, audit_results/R60B_WEB_READINESS_BUDGET_REPAIR_closeout_2026-08-11.md
- tests run: 65 combined focused tests and 3 subtests; 4 real lifecycle integration tests; one real manual start/status/open/stop lifecycle; 630 core tests and 132 subtests; 27 Custom stability tests and 5 subtests; 5068 recovery full-suite tests and 985 subtests
- blocked risks: none within the admitted lifecycle scope; full live-readonly snapshot cost remains intentionally bounded by the existing startup deadline
- closure state: CLOSED

## Verification

- tests: the focused unit plus real integration surface passed 27 tests in 18.24 seconds; `make test-core` passed 630 tests and 132 subtests in 125.13 seconds; `make test-full` passed 5067 tests and 985 subtests in 1587.83 seconds
- build: `make check` compiled repository Python surfaces and collected 5067 tests; `make test-custom-stability` passed 27 tests and 5 subtests in 3.80 seconds; the only full-suite warning was the pre-existing Pillow `getdata` deprecation
- manual: one isolated temporary managed root completed real `web_start`, `web_status`, `web_open`, and `web_stop`; start proved listener and full live-readonly readiness, status classified `running`, stop closed the listener, final status classified `no_ledger`, and no owner artifacts remained
- live verification: local loopback only; no provider request, credential, login, external network call, public bind, host proxy change, or fixed production managed-root mutation occurred

## Recovery Verification

- the original PR #148 push and pull-request full suites were preserved without rerun after they exposed two sibling auth-recovery test-clock failures outside the R60B write set;
- R60C, R60D, and R60E repaired those independent baseline timing contracts and merged through PR #149 as `9189214a8538931b7675ffa6c700ad6a4962cf01`;
- a new recovery branch preserved the original R60B commits, merged that green baseline without conflict as `0d555de78cfc0b654271d6e44e0a624a64e18f06`, and retained the exact four-file R60B diff against `main`;
- renewed verification passed 65 combined focused tests and 3 subtests in 13.75 seconds, 4 lifecycle integration tests in 15.66 seconds, `make check` with 5068 collected tests, 630 core tests and 132 subtests, 27 Custom stability tests and 5 subtests, and 5068 full-suite tests with 985 subtests in 1356.70 seconds;
- the only recovery full-suite warning remained the pre-existing Pillow `getdata` deprecation.

## Failure Diagnosis and Repair

- exact failure: the pre-repair full suite ended with 2 failures, 5065 passes, 1 warning, and 985 subtests; both failures were in `tests/test_web_lifecycle_integration.py` and returned `WEB_LISTENER_NOT_READY` with `listener_ok=true`, `readiness_ok=false`, and `TimeoutError`
- reproduction: the focused integration file repeated the same signature with 2 failures and 2 passes in 92.28 seconds; no same-signature full-suite rerun was used as substitute evidence
- root cause: `web_start` gave each heavyweight `/api/live-readonly` request a fixed two-second HTTP timeout even though the outer startup window was longer; a cold snapshot could exceed two seconds, leaving the server handler running while the client immediately launched another request and amplified load until the outer deadline
- repair: each readiness request now receives the positive remaining outer startup budget; the request stays bounded by the original deadline and the complete live-readonly snapshot remains the success condition
- guard: a focused regression asserts that the readiness request timeout is positive and never exceeds the caller's startup budget; the real integration and one manual child-process lifecycle prove listener, readiness, ownership, and cleanup behavior

## Artifacts

- spec: `audit_results/R60B_WEB_READINESS_BUDGET_REPAIR_SPEC_2026-08-11.md`
- packet: real lifecycle command packets proved `status=ok`, listener/readiness truth, `running`, exact stop cleanup, and terminal `no_ledger`
- report: the failed pre-repair and PR #148 outputs remain preserved in external execution-state history; revisions 102 through 104 bind the non-rewriting recovery branch, green baseline merge, and renewed local gates

## Git

- branch: codex/r60b-web-readiness-budget-v2
- commit: 4795e295cf835890746cf20178d3c8ce478f0388 contains the verified runtime repair, regression, and spec; 0d555de78cfc0b654271d6e44e0a624a64e18f06 integrates it with the green PR #149 baseline
- pushed: yes; the logically complete recovery integration plus refreshed closeout commit is pushed and read back from the new branch before merge admission

## Scope Check

- unrelated work mixed in: false; the contour changes only web lifecycle readiness budgeting, its direct regression, spec, and closeout
- private-data risk reviewed: no secrets, provider credentials, main Codex material, protected ports, host network settings, UI, releases, tags, or user-owned canonical-checkout changes were accessed or introduced

## Notes

- blockers encountered: the R60A full-suite verification exposed this unrelated but production-relevant cold-start lifecycle defect; PR #148 then exposed independent baseline test-clock failures, which were isolated and merged separately before the R60B recovery branch renewed all gates; R60A stayed isolated in an exact stash throughout
- resume from here: CLOSED
