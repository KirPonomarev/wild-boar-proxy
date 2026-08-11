<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R60E Desktop Shell Smoke Budget Repair Closeout

## Goal

Remove full-suite load sensitivity from the bounded desktop web-shell smoke
without changing production server, endpoint, packet, or authorization
semantics.

## Result

- status: bounded smoke-harness repair complete with renewed full local verification
- final verdict: R60E_DESKTOP_SHELL_SMOKE_BUDGET_REPAIR_CODE_COMPLETE
- closure state: CLOSED

## Contour Capsule

- goal: make six sequential loopback smoke operations share one decreasing 30-second total deadline instead of independent three-second request limits
- branch: codex/r60d-web-dispatch-test-timeout
- head: 4df03733c13a5aa5ecbf05b4da55c2dc146af0d4
- touched files: wild_boar_proxy/desktop_web_shell.py, tests/test_desktop_web_shell.py, audit_results/R60E_DESKTOP_SHELL_SMOKE_BUDGET_REPAIR_SPEC_2026-08-11.md, audit_results/R60E_DESKTOP_SHELL_SMOKE_BUDGET_REPAIR_closeout_2026-08-11.md
- tests run: 16 focused desktop/package tests and 3 subtests; 630 core tests and 132 subtests; 27 Custom stability tests and 5 subtests; 5067 full-suite tests and 985 subtests
- blocked risks: none in the contour; smoke deadline exhaustion remains fail-closed and cleanup remains in the existing finally block
- closure state: CLOSED

## Verification

- tests: focused desktop-shell plus relocated-package set passed 16 tests and 3 subtests in 10.41 seconds; replacement `make test-full` passed 5067 tests and 985 subtests in 1529.15 seconds
- build: `make check` collected 5067 tests; `make test-core` passed 630 tests and 132 subtests in 70.65 seconds; `make test-custom-stability` passed 27 tests and 5 subtests in 3.23 seconds
- manual: final diff proves only the smoke client consumes the new aggregate deadline; server startup, request handling, action phase, authorization, packet construction, and cleanup structure are unchanged
- live verification: test-owned local loopback servers only; no provider, credential, external network, protected host mutation, release, or publishing

## Artifacts

- spec: `audit_results/R60E_DESKTOP_SHELL_SMOKE_BUDGET_REPAIR_SPEC_2026-08-11.md`
- packet: push workflow 31482653837 and pull-request workflow 31482673959 preserve independent `TimeoutError` smoke failures; the final local full-suite output proves both repaired paths on the combined candidate
- report: external execution-state revisions 98 and 99 bind the failure diagnosis, exact implementation head, app-pause interruption, and authorized replacement local gate

## Git

- branch: codex/r60d-web-dispatch-test-timeout
- commit: 4df03733c13a5aa5ecbf05b4da55c2dc146af0d4 contains the aggregate smoke budget, deterministic regression test, and spec
- pushed: yes; the logically complete implementation plus closeout commit is pushed and read back from the same branch before merge admission

## Scope Check

- unrelated work mixed in: false; R60E changes only the desktop smoke request budget, its deterministic test, and contour evidence
- private-data risk reviewed: no secrets, credentials, runtime state, provider calls, public bind, UI expansion, release, or publishing were introduced

## Notes

- blockers encountered: both independent PR #149 full suites failed different desktop smoke tests under the same three-second request limit; the first replacement local full gate was interrupted by an app pause at 13 percent without a terminal result, then the explicitly recorded replacement gate passed
- resume from here: CLOSED
