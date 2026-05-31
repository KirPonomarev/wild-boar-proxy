<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Hold With Exact Blockers Packet

```text
CONTOUR:
hold_with_exact_blockers_packet

Goal:
Freeze the current governing state as a canonical hold, normalize the blocker
set, describe packet-driven reopen conditions, and prevent claim escalation
from partial green owner-surface signals.

Size: S / M
Risk level: high
Decision owner: project owner / canon-first
Mode: audit + decision

In scope:
- exact blocker inventory
- reopen-condition matrix
- forbidden-claim matrix
- independent audit

Out of scope:
- runtime, installer, package, or UI implementation
- blocker remediation
- release/pilot claims
- live stage-20 execution

Assumptions:
- Path C is the current governing verdict
- current owner-surface packets remain primary truth
- no historical artifact is rewritten here

Inputs:
- docs:
  - AGENTS.md
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
- runtime evidence:
  - audit_results/master_plan_active_path_selection_packet_2026-05-12.json
  - audit_results/stage20_c6_verification_packet.json
  - audit_results/step42_decision_packet.json
  - audit_results/step42_normalization_decision_packet.json
  - audit_results/latest_status_raw.json
  - audit_results/latest_rotation_inspect_raw.json
  - audit_results/latest_accounts_list_raw.json

Commands / files:
- tests:
  - python3 -m unittest -q tests.test_cli -k claim_gate
  - python3 -m unittest -q tests.test_cli -k stage_advance_20
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check

Acceptance criteria:
- blocker set is stable and machine-readable
- reopen conditions are packet-driven
- forbidden claims are explicit
- hold remains exact and non-softened

Verification:
- tests:
  - python3 -m unittest -q tests.test_cli -k claim_gate
  - python3 -m unittest -q tests.test_cli -k stage_advance_20
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check
- manual:
  - artifact replay and blocker/reopen-condition review
- live packet:
  - none; existing read-only artifacts only

Artifacts:
- spec:
  - audit_results/hold_with_exact_blockers_contour_2026-05-12.md
- packet:
  - audit_results/hold_with_exact_blockers_packet_2026-05-12.json
- closeout note:
  - audit_results/hold_with_exact_blockers_closeout_2026-05-12.md

Stop conditions:
- blocker aliases drift without packet basis
- reopen conditions cannot be expressed as observable packet/state changes
- hold wording starts implying partial readiness

Closeout:
- verification complete: yes
- commit: required
- push: required
- next contour:
  - reserve_first_stage20_live_path_selection_and_precondition_contour only after blocker truth changes
```
