<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B14 Web Workflow Control Surface Closeout

## Goal

After B13G, implement the web management control surface for the execution
core: workflow run controls (B13 integration), workflow history, writer
status, capability/evidence badges, provider/transport/model selection
facts, aliases, credential presence, assignments, and context policies —
protected by token, rate limit, origin/CSRF checks, strict packets,
loopback policy, and secret redaction. The dispatch seam is
controlled-only in B14; live dispatch is rejected with a typed error.

## Result

- status: implemented and verified
- final verdict: `web_workflow_control.py` provides the JSON control
  surface: GET `/api/workflow/gate` (design-gate badge with the earned
  token), GET `/api/workflow/history` (bounded run history), GET
  `/api/workflow/status` (writer status, capability badges, alias
  bindings, credential presence, assignments, context policies, selection
  facts), POST `/api/workflow/run` (B13 runner with the controlled
  dispatch seam; live dispatch rejected with
  `WORKFLOW_LIVE_DISPATCH_NOT_IMPLEMENTED`); every response is a strict
  command packet; POSTs require token + CSRF + allowed origin + rate-limit
  admission; clients are loopback-only; the writer lock is single-writer
  with a fencing token; secret values are redacted by the packet contract
- closure state: CLOSED

## Contour Capsule

- goal: B14 web workflow control surface
- branch: `codex/b14-web-workflow-control`
- head: `f60ae261b4e82f9263a9b3fb5a6ac95ebf8b9aee` (base before contour commit)
- touched files: `wild_boar_proxy/web_workflow_control.py` (new),
  `tests/test_web_workflow_control.py` (new),
  `audit_results/B14_WEB_WORKFLOW_CONTROL_SPEC_2026-08-03.md`,
  `audit_results/B14_WEB_WORKFLOW_CONTROL_closeout_2026-08-03.md`
- tests run: `tests/test_web_workflow_control.py` (13); `make check`;
  `make test-core`; `make test-custom-stability`; `make test-web-e2e`;
  `make test-full`
- blocked risks: unprotected POST actions, CSRF/origin bypass, rate-limit
  bypass, secret echo, live dispatch simulation, unbounded history,
  concurrent writers
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_web_workflow_control.py` -> `13 passed` (gate badge with
    earned token; bounded history; token required; CSRF required; loopback
    client enforcement; origin rejection; live dispatch rejected with the
    typed error; steps execute with independent receipts and history
    recording; single-writer lock with fencing token; rate limiting;
    unknown path fails closed; secret values never echoed; history
    bounded to max entries)
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> green (counts recorded in the PR)
  - GitHub CI results recorded in the PR
- build:
  - `make check` (compileall + collect) green
- manual:
  - n/a
- live verification:
  - controlled dispatch seam only; live dispatch is rejected, never
    simulated

## Artifacts

- spec: `audit_results/B14_WEB_WORKFLOW_CONTROL_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: the surface reuses the existing web token / rate-limit / origin
  / CSRF machinery and the B13 runner; no UI page rendering was added

## Git

- branch: `codex/b14-web-workflow-control`
- commit: contour commit contains the control surface, tests, spec, and
  closeout
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (token/CSRF verified, origin checked,
  rate limited, loopback-only, secret values redacted by packet contract)
- live-path mutation performed: no (controlled dispatch only)
- shared-helper refactor introduced: no (existing web token/rate-limit/
  origin/CSRF machinery reused)
- materialization output drift accepted: no

## Notes

- blockers encountered: none beyond routine test iterations (CSRF header
  name `X-WBP-CSRF` and host/origin port matching)
- resume from here: CLOSED
