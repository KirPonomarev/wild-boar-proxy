<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Master Plan Active-Path Reconciliation Or Live-Path Selection

```text
CONTOUR:
master_plan_active_path_reconciliation_or_live_path_selection

Goal:
Reconcile the active top-line MASTER_PLAN path with later historical closeout
notes and choose one canonically valid governing path without claim escalation.

Size: M
Risk level: high
Decision owner: project owner / canon-first
Mode: audit + decision

In scope:
- governing-path matrix
- exact blocker capture
- historical-vs-active artifact classification
- independent audit

Out of scope:
- runtime, installer, package, or UI implementation
- release or pilot claims
- broad MASTER_PLAN rewrite

Assumptions:
- AGENTS canon order is authoritative
- historical artifacts remain truthful but do not automatically define the
  current active contour
- strict JSON owner surfaces remain the primary truth source when available

Inputs:
- docs:
  - AGENTS.md
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
- code:
  - wild_boar_proxy/cli.py
  - wild_boar_proxy/runtime.py
- runtime evidence:
  - audit_results/stage20_c6_closeout_report.md
  - audit_results/stage20_c6_verification_packet.json
  - audit_results/release_gate_alignment_packet_2026-05-12.json
  - audit_results/pilot_entry_preconditions_2026-05-12.json
  - audit_results/release_gate_independent_audit_2026-05-12.json
  - audit_results/step42_decision_packet.json
  - audit_results/step42_normalization_decision_packet.json
  - audit_results/latest_status_raw.json
  - audit_results/latest_rotation_inspect_raw.json
  - audit_results/latest_accounts_list_raw.json

Commands / files:
- tests:
  - python3 -m unittest -q tests.test_cli -k stage_advance_20
  - python3 -m unittest -q tests.test_ui_shell tests.test_web_ui
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check

Acceptance criteria:
- Path A/B/C matrix exists
- one governing verdict is selected
- blocked claims remain blocked
- independent audit finds no claim escalation

Verification:
- tests:
  - python3 -m unittest -q tests.test_cli -k stage_advance_20
  - python3 -m unittest -q tests.test_ui_shell tests.test_web_ui
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check
- manual:
  - artifact replay and path-selection matrix review
- live packet:
  - none; this contour reuses existing read-only gate artifacts

Artifacts:
- spec:
  - audit_results/master_plan_active_path_reconciliation_contour_2026-05-12.md
- packet:
  - audit_results/master_plan_active_path_selection_packet_2026-05-12.json
- closeout note:
  - audit_results/master_plan_active_path_reconciliation_closeout_2026-05-12.md

Stop conditions:
- Path A or B would require claim escalation
- active and historical sources cannot be bounded cleanly
- any attempt to treat health green alone as governing truth

Closeout:
- verification complete: yes
- commit: required
- push: required
- next contour:
  - hold_with_exact_blockers_packet
```
