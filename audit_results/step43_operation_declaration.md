<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Step43 Operation Declaration

## Authorization

- active-thread authorization: present
- authorization basis: explicit project-scoped owner authorization in active
  thread
- exact standing CANON phrase present verbatim: no
- authorization sufficiency for one live refresh contour: yes

## Intended Freshness Producer

- admitted owner freshness producer:
  - `python3 -m wild_boar_proxy sync --json`
- rejected as freshness producers:
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m wild_boar_proxy launch smoke --json`
  - `python3 -m wild_boar_proxy healthcheck --json`

## Declared Write Surfaces If Sync Opened

- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-proxy.pid`

## Actual Admission Decision

- sync admitted to execute: no
- reason:
  - fresh phase-0 owner packets did not show `ROTATION_EVIDENCE_STALE`
  - instead they showed a reproduced owner-surface contradiction:
    `status --json` reported `claim_gate=blocked` and `policy_drift=detected`
    while `rollout rotation inspect --json` reported fresh available
    participation evidence and delegated `policy_drift_status=clear`

## Commands Actually Executed

- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy accounts list --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- bounded reread:
  - `python3 -m wild_boar_proxy status --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`

## Commands Explicitly Not Executed

- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy launch smoke --json`
- any posture/stage/account mutation commands

## Rollback Expectation

No rollback required because no live write step was executed in this contour.
