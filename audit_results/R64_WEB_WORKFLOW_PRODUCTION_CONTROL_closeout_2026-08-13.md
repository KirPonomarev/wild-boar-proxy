<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R64 Web Workflow Production Control Closeout

## Goal

Expose the R63 registry-bound workflow execution boundary through the existing
production local web server and provide an operator screen that composes, runs,
and inspects bounded multi-actor API workflows without transferring identity,
route, provider, credential, or authorization authority to the browser.

## Result

- status: implementation and deterministic product verification complete
- final verdict: PASS for controlled production web workflow execution; no live provider call was performed or claimed
- closure state: CLOSED

## Contour Capsule

- goal: ship a server-owned registry-bound workflow API and responsive operator surface over the existing admitted live-server ingress
- branch: `codex/r64-web-workflow-production-control`
- head: exact base `43fa86c5b1cf15a2d9a172389f99056bea931274` plus the single logically complete R64 contour commit
- touched files: R64 spec, ADR, and closeout; workflow control and live-server modules; workflow screen markup, behavior, and styles; workflow control, live-server, UI behavior, and existing UI compatibility tests
- tests run: focused workflow/backend/UI 19 passed; complete repository suite exercised 5108 tests with 5106 passed plus 997 subtests before two localized UI compatibility fixes; final affected surface 7 passed after those fixes; browser-controlled two-actor workflow passed end to end
- blocked risks: live provider execution, persistent workflow resume, and native-primary orchestration were outside authorization and scope; workflow history remains process-local
- closure state: CLOSED

## Verification

- tests: focused workflow control, live-server, and UI suites `19 passed in 1.66s`; complete repository run `5106 passed, 1 warning, 997 subtests passed in 1191.92s` with only two localized UI compatibility failures; both failures were fixed and their final affected set passed `7 passed in 3.61s`
- build: Python and JavaScript syntax checks passed; `make check` compiled the tree and collected 5108 tests; exact-SHA protected CI is the final delivery gate
- manual: the in-app browser loaded the server-owned DIP and Kimi slots, ran a controlled DIP to Kimi workflow, rendered two `DISPATCH_COMPLETE` receipts and history, reported zero console warnings/errors, and fit both 1280 px desktop and 390 px mobile viewports without horizontal overflow
- live verification: not performed; absent server authorization keeps live mode disabled and rejects live work before credentials or provider network

## Artifacts

- spec: `audit_results/R64_WEB_WORKFLOW_PRODUCTION_CONTROL_SPEC_2026-08-13.md`
- packet: controlled workflow receipts and browser QA facts were generated only against temporary deterministic runtime roots
- report: `audit_results/ADR_R64_SERVER_OWNED_WORKFLOW_UI_BOUNDARY_2026-08-13.md`; Lazyweb evidence `https://www.lazyweb.com/agentic-search/705500ec-b6e6-449e-aaa5-826e79e17e64`

## Git

- branch: `codex/r64-web-workflow-production-control`
- commit: single logically complete R64 implementation, UI, regression, decision, and closeout commit
- pushed: subject to exact remote branch readback and required CI before merge

## Scope Check

- unrelated work mixed in: no; changes are limited to the admitted web workflow control boundary, operator surface, direct regressions, and contour evidence
- private-data risk reviewed: yes; the browser cannot submit credentials or canonical transport identity, public status hides fencing values, responses redact and bound output, and no live provider or credential path was exercised

## Notes

- blockers encountered: a browser pass exposed mobile navigation overflow after adding the seventh screen; the complete suite then exposed that same viewport constraint and one compatibility marker coupled to the settings heading; both were localized, fixed, and verified on their affected surface
- resume from here: CLOSED
