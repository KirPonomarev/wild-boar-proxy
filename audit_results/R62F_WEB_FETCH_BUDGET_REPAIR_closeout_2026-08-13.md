<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R62F Web Fetch Budget Repair Closeout

## Goal

Remove the loaded-runner request amplification exposed by R62 push CI without
changing production web or Kimi behavior.

## Result

- status: implementation and deterministic verification complete
- final verdict: PASS for R62F test-harness repair
- closure state: CLOSED

## Contour Capsule

- goal: give each test HTTP attempt the remaining hard deadline instead of
  spawning a new abandoned request every three seconds
- branch: `codex/r62f-web-fetch-budget`
- head: implementation commit recorded in Git history
- touched files: this spec and closeout plus
  `tests/test_web_design_live_server.py`
- tests run: exact repair `3 passed`; `make check` collected 5081 tests; core
  `634 passed, 136 subtests`; custom stability `27 passed, 5 subtests`; full
  `5081 passed, 1 warning, 989 subtests passed in 1088.03s`
- blocked risks: none for the test-only repair
- closure state: CLOSED

## Verification

- tests: exact failed tests plus regression passed; all repository local gates
  passed on the repair tree
- build: `make check` passed
- manual: `git diff --check` passed and production files are absent from diff
- live verification: local in-process HTTP only; no external service used

## Artifacts

- spec: `audit_results/R62F_WEB_FETCH_BUDGET_REPAIR_SPEC_2026-08-13.md`
- packet: GitHub Actions push job `94297012226` preserved the two timeout and
  BrokenPipe failures that triggered this repair
- report: this closeout

## Git

- branch: `codex/r62f-web-fetch-budget`
- commit: recorded in Git history
- pushed: pending commit/push at closeout authoring time

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; no provider, credential, or external network
  surface was accessed

## Notes

- blockers encountered: a real R62 remote check failure required
  `STOP_AND_DIAGNOSE`; the independent synthetic-merge job passed, while the
  failed push job showed two client timeouts followed by handler BrokenPipes
- resume from here: CLOSED
