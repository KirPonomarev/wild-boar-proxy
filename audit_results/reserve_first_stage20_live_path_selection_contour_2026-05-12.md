<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Reserve-First Stage-20 Live Path Selection And Precondition Contour

```text
CONTOUR:
reserve_first_stage20_live_path_selection_and_precondition_contour

Goal:
Проверить, изменился ли blocking truth настолько,
чтобы canonical hold можно было честно снять
и открыть reserve-first live stage-20 lane,
не делая ни одной live mutation.

Size: S / M
Risk level: high
Decision owner: project owner / canon-first
Mode: audit + live-preflight

In scope:
- read-only replay of current owner surfaces
- exact reopen-condition check against frozen hold packet
- binary admissibility verdict
- machine-carried precondition packet
- independent audit

Out of scope:
- any live mutation
- rollout stage advance 20
- same-day live validation
- runtime/package/UI changes
- release/pilot claims
- historical artifact rewrites

Assumptions:
- canonical hold remains active unless all reopen conditions clear
- write-capable commands are forbidden in this contour
- command packets remain primary truth

Inputs:
- docs:
  - AGENTS.md
  - CANON.md
  - MASTER_PLAN.md
  - RUNTIME_CONTRACT.md
  - COMMAND_API.md
- runtime evidence:
  - audit_results/hold_with_exact_blockers_packet_2026-05-12.json
  - audit_results/master_plan_active_path_selection_packet_2026-05-12.json
  - audit_results/stage20_c6_verification_packet.json
  - audit_results/step42_decision_packet.json
  - audit_results/step42_normalization_decision_packet.json
  - audit_results/reserve_first_stage20_status_raw_2026-05-12.json
  - audit_results/reserve_first_stage20_healthcheck_raw_2026-05-12.json
  - audit_results/reserve_first_stage20_rotation_inspect_raw_2026-05-12.json
  - audit_results/reserve_first_stage20_accounts_list_raw_2026-05-12.json
  - audit_results/reserve_first_stage20_posture20_raw_2026-05-12.json

Commands / files:
- python3 -m wild_boar_proxy status --json
- python3 -m wild_boar_proxy healthcheck --json
- python3 -m wild_boar_proxy rollout rotation inspect --json
- python3 -m wild_boar_proxy accounts list --json
- python3 -m wild_boar_proxy rollout posture inspect 20 --json
- audit_results/reserve_first_stage20_live_path_selection_packet_2026-05-12.json
- audit_results/reserve_first_stage20_live_path_selection_independent_audit_2026-05-12.json
- audit_results/reserve_first_stage20_live_path_selection_closeout_2026-05-12.md

Acceptance criteria:
- every frozen blocker is re-evaluated against current packet truth
- inherited-now-clear labels are explicitly rechecked
- verdict is machine-readable and binary
- no live mutation occurs
- no claim escalation occurs
- independent audit agrees with verdict

Verification:
- tests:
  - python3 -m unittest -q tests.test_cli -k claim_gate
  - python3 -m unittest -q tests.test_cli -k stage_advance_20
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check
- manual:
  - field-level extraction from fresh owner-surface packets
  - blocker comparison against frozen hold packet
- live packet:
  - none
  - read-only owner-surface replay only

Artifacts:
- spec:
  - audit_results/reserve_first_stage20_live_path_selection_contour_2026-05-12.md
- packet:
  - audit_results/reserve_first_stage20_live_path_selection_packet_2026-05-12.json
- closeout note:
  - audit_results/reserve_first_stage20_live_path_selection_closeout_2026-05-12.md

Stop conditions:
- packet truth becomes contradictory mid-replay
- any write-capable action becomes necessary
- healthcheck/status green is treated as sufficient reopen proof

Closeout:
- verification complete:
  - read-only owner-surface replay captured
  - blockers re-evaluated
  - independent audit completed
- commit:
  - required
- push:
  - required
- next contour:
  - none while NO_GO_STAY_ON_HOLD remains true
```
