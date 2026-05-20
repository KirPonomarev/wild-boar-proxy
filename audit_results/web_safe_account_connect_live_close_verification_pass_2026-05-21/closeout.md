<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WEB_SAFE_ACCOUNT_CONNECT_LIVE_CLOSE_VERIFICATION_PASS Closeout

## Goal

Execute the already-implemented live Quick Start onboarding lane in sandbox and
close it with owner packet plus canonical refresh evidence.

## Result

- status: `preflight_ready_but_owner_authorization_blocked`
- final verdict:
  `TECHNICAL_LIVE_LANE_READY_CANONICAL_OWNER_GATE_BLOCKED_REAL_EXECUTION`
- next action:
  wait for the exact canonical owner authorization phrase, then run one real
  sandbox Quick Start onboarding and capture owner packet plus accounts refresh

## Contour Capsule

- goal:
  verify whether the implemented live onboarding lane can be closed now, and
  if not, localize the exact blocker with machine-backed evidence
- branch: `codex/external-agent-lab-isolated`
- head: `ea2b0b5`
- touched files:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/spec.md`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/independent_audit.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/closeout.md`
- tests run:
  - `git diff --check`
  - canonical owner-authorization grep against `CANON.md`
  - local stub sandbox server proof for `/api/actions`
  - local stub dry-run preview packet proof for `/api/action`
- blocked risks:
  - real sandbox write remains blocked by missing explicit owner authorization
  - no live owner packet from a real mutation was captured
- next exact command:
  - `curl -s -X POST http://127.0.0.1:<sandbox-port>/api/action -H 'Content-Type: application/json' -d '{"ui_action":"onboard_account"}'`

## Verification

- tests:
  - no new product code changed in this contour
- build:
  - `git diff --check` passed
- manual:
  - `CANON.md` confirms the exact standing owner phrase and rejects generic
    `начинай работу`
  - local stub server returned `sandbox_preflight.status=admitted`
  - local stub server returned `onboard_account.available=true`
  - local stub dry-run packet returned `preview_only=true`
- live verification:
  - not executed; canonical owner gate blocked the mutation step

## Artifacts

- spec:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/metrics.json`
  - `audit_results/web_safe_account_connect_live_close_verification_pass_2026-05-21/independent_audit.json`
- report:
  - this closeout plus machine-backed preflight evidence

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; no browser secret/path/auth input was introduced and no real write was executed`

## Notes

- blockers encountered:
  - `CANON.md` requires the exact standing approval phrase
    `разрешаю тебе любые законные действия в рамках разработки проекта`
  - the active thread contains generic start-work instructions but not the
    exact canonical owner phrase
- follow-up contour:
  - rerun this same close contour after explicit owner authorization appears in
    the thread
- resume from here:
  `once the exact owner phrase is present in the active thread, execute one real sandbox Quick Start onboarding and capture owner packet plus canonical accounts refresh`
