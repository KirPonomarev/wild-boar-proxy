<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Audit Activity History Admission Closeout

## Goal

Decide whether a dedicated Audit / Activity History surface may be admitted
without reading raw logs, leaking paths, treating stale/cached action rows as
current truth, or creating a browser-owned durable ledger.

## Result

- status: completed
- final verdict: AUDIT_ACTIVITY_HISTORY_CURRENT_SESSION_SUMMARY_ONLY_ADMITTED for current-session summaries; AUDIT_ACTIVITY_HISTORY_DEFERRED_PENDING_BOUNDED_ACTIVITY_PACKET for the durable screen
- next action: API_ROUTE_BUILDER_AND_SECRET_CONTRACT_ADMISSION

## Contour Capsule

- goal: split current-session command result summaries from durable Audit / Activity History and decide admission for both
- branch: codex/external-agent-lab-isolated
- head: pre-commit working tree after 93d26ef
- touched files: audit_results/audit_activity_history_admission_spec_2026-05-14.md; audit_results/audit_activity_history_admission_matrix_2026-05-14.json; audit_results/audit_activity_history_admission_independent_audit_2026-05-14.json; audit_results/audit_activity_history_admission_closeout_2026-05-14.md
- tests run: python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server; python3 -m json.tool audit_results/audit_activity_history_admission_matrix_2026-05-14.json; python3 -m json.tool audit_results/audit_activity_history_admission_independent_audit_2026-05-14.json; python3 tools/check_closeout_resilience.py; git diff --check
- blocked risks: no durable server-owned activity packet/index exists; raw logs/stdout/stderr parsing remains forbidden; browser storage must not become activity truth; raw changed_files paths remain forbidden
- next exact command: API_ROUTE_BUILDER_AND_SECRET_CONTRACT_ADMISSION

## Verification

- tests: PASS
- build: not applicable; no runtime or UI code changed
- manual: repo canon, current action ledger behavior, UI tests, and final screen matrix reviewed
- live verification: not applicable; spec-only contour with no runtime mutation

## Artifacts

- spec: audit_results/audit_activity_history_admission_spec_2026-05-14.md
- packet: audit_results/audit_activity_history_admission_matrix_2026-05-14.json
- report: audit_results/audit_activity_history_admission_independent_audit_2026-05-14.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending until the scoped contour artifacts are staged and committed
- pushed: pending until the scoped contour commit is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts admit no direct file truth, raw log parsing, raw changed-file paths, or browser-owned durable storage

## Notes

- blockers encountered: the final design screen still needs a bounded server-owned activity JSON packet/index; current-session action summaries are already admitted only as ephemeral operator feedback
- independent audit note: Hume confirmed the split verdict and found no durable activity packet/index today; Rawls found no content drift and blocked only premature closeout head/commit/push wording, corrected before commit
- follow-up contour: API_ROUTE_BUILDER_AND_SECRET_CONTRACT_ADMISSION
- resume from here: API_ROUTE_BUILDER_AND_SECRET_CONTRACT_ADMISSION
