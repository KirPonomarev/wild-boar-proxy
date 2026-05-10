<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Stable Policy Drift Authorized Operation Declaration

## Authorization

- active-thread authorization: present
- authorization text: `разрешаю ... делай все что необходимо сделать ради реализации проекта`
- authorization interpretation: explicit project-scoped live authorization for
  legal project-development work under canon and runbooks

## Phase 0 Result

- `status --json`: `OK`, policy drift detected
- `healthcheck --json`: `OK`
- `accounts list --json`: `OK`
- `rollout rotation inspect --json`: `ROTATION_EVIDENCE_CONTRADICTED`
- `rollout posture inspect 20 --json`: `INSUFFICIENT_ELIGIBLE_POOL`
- `stable repair --dry-run --json`: `OK`, `would_change=true`
- dry-run target reference status: `materialized_aligned`
- dry-run target plan: add `9`, prune `1`, keep `0`

## Apply Admission

- authorization recorded: yes
- dry-run valid JSON: yes
- dry-run expected write scope: approved target inventory only
- target switch needed: no
- target switch decision: `TARGET_SWITCH_SKIPPED_ALREADY_ALIGNED`

## Commands To Execute

- `python3 -m wild_boar_proxy stable repair --apply --json`
- `python3 -m wild_boar_proxy launch smoke --json`

## Commands Explicitly Not Executed

- `python3 -m wild_boar_proxy stable target switch --apply --json`
- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy policy stage set ... --json`
- `python3 -m wild_boar_proxy rollout stage advance ... --json`
- `python3 -m wild_boar_proxy accounts ... --json`

## Expected Write Surfaces

- approved stable repair target inventory:
  - `<managed_dir>/stable-repair-target/codex-*.json`
- launch-smoke activation evidence and runtime activation surfaces:
  - managed supervisor state
  - generated stable runtime config
  - runtime effective mode
  - managed proxy pid/config surfaces if the owner packet reports them

## Rollback Expectation

No manual rollback inside this contour. If post-operation owner packets remain
RED, preserve evidence and close with the exact packet-derived blocker.
