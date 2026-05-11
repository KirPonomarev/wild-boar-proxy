<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Reserve-First Stage-20 Live Path Selection And Precondition Contour Closeout

## Goal

Decide, via read-only owner-surface replay only, whether the reserve-first live
stage-20 path is admissible again without performing any live mutation.

## Result

- status: completed
- final verdict: `NO_GO_STAY_ON_HOLD`
- next action:
  - keep canonical hold active
  - do not open the live stage-20 path
  - do not start same-day validation
- blocker refresh note:
  - still active:
    - `OWNER_SURFACE_CONTRADICTION`
    - `NO_EXPLICIT_RESERVE_POSTURE`
  - worsened relative to frozen hold packet:
    - `ROTATION_EVIDENCE_INSUFFICIENT` -> `ROTATION_EVIDENCE_CONTRADICTED`
  - still non-green at target stage:
    - `LIVE_POSTURE_DRIFT_ONLY`
  - reactivated in fresh current status truth:
    - `CLAIM_GATE_BLOCKED`
    - `STABLE_POLICY_DRIFT`

## Verification

- tests:
  - `python3 -m unittest -q tests.test_cli -k claim_gate`
  - observed result: `Ran 2 tests ... OK`
  - `python3 -m unittest -q tests.test_cli -k stage_advance_20`
  - observed result: `Ran 15 tests ... OK`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
  - observed result: passed
  - `git diff --check`
  - observed result: passed
- manual:
  - replayed fresh read-only owner surfaces:
    - `status --json`
    - `healthcheck --json`
    - `rollout rotation inspect --json`
    - `accounts list --json`
    - `rollout posture inspect 20 --json`
  - captured raw packets under `audit_results/reserve_first_stage20_*_raw_2026-05-12.json`
  - compared field-level blocker truth against the frozen hold packet
- live verification:
  - none
  - this contour intentionally remained read-only

## Artifacts

- spec:
  - `audit_results/reserve_first_stage20_live_path_selection_contour_2026-05-12.md`
- packet:
  - `audit_results/reserve_first_stage20_live_path_selection_packet_2026-05-12.json`
- report:
  - `audit_results/reserve_first_stage20_live_path_selection_independent_audit_2026-05-12.json`
- raw packets:
  - `audit_results/reserve_first_stage20_status_raw_2026-05-12.json`
  - `audit_results/reserve_first_stage20_healthcheck_raw_2026-05-12.json`
  - `audit_results/reserve_first_stage20_rotation_inspect_raw_2026-05-12.json`
  - `audit_results/reserve_first_stage20_accounts_list_raw_2026-05-12.json`
  - `audit_results/reserve_first_stage20_posture20_raw_2026-05-12.json`

## Git

- branch:
  - `codex/external-agent-lab-isolated`
- commit:
  - pending
- pushed:
  - pending

## Scope Check

- unrelated work mixed in:
  - no product behavior changed
  - no runtime/package/UI surfaces changed
- private-data risk reviewed:
  - yes; raw packets were captured from existing owner surfaces only

## Notes

- blockers encountered:
  - current hold remains active
  - fresh owner-surface replay reactivated `CLAIM_GATE_BLOCKED` and `STABLE_POLICY_DRIFT`
- follow-up contour:
  - none unless blocking truth changes
