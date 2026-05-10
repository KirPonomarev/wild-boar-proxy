<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Stable Policy Drift Operation Declaration

## Authorization

- required authorization: explicit standing phrase or exact one-off approval
- standing phrase required by `CANON.md`:
  `разрешаю тебе любые законные действия в рамках разработки проекта`
- active-thread authorization status: `absent`
- result: `PRECONDITION_NOT_MET_NO_LIVE_MUTATION`

## Commands Actually Executed

Read-only / dry-run only:

- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy accounts list --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy rollout posture inspect 20 --json`
- `python3 -m wild_boar_proxy stable repair --dry-run --json`

## Commands Not Executed

- `python3 -m wild_boar_proxy stable target switch --apply --json`
- `python3 -m wild_boar_proxy stable repair --apply --json`
- `python3 -m wild_boar_proxy launch smoke --json`

## Expected Write Surfaces If Later Authorized

- approved stable repair target inventory
- stable target reference surfaces only if target switch is admitted
- runtime activation evidence written by `launch smoke --json`
- audit artifacts

## Rollback Expectation

No rollback was needed because no live mutation was performed.
