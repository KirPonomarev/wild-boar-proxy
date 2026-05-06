<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Wild Boar Proxy Canon

## Source of truth order

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Product definition

Wild Boar Proxy is an experimental companion control app.

It does not replace the proxy engine and does not fork the host client.

## Boundary rule

`Wild Boar Proxy App` is the managing layer.

`CLIProxyAPI` is the engine.

The managing layer makes decisions about modes, pool policy, recovery,
diagnostics, and rollout.

The engine handles API traffic, auth flows, provider translation, and
low-level routing.

## Non-negotiable rules

- one active truth surface per topic
- no split-brain between docs and runtime
- no false-green or stale-green status
- runtime data is never committed
- repo work is not considered synchronized while it exists only in a local worktree
- each closed write contour must reach GitHub, not just a local commit
- architecture is designed for 20 accounts from day one
- scaling proof is staged: 10, then 15, then 20

## Owner authorization rule

The project owner may grant project-scoped standing approval in the current
thread for any legal project-development action, including live runtime
contours.

Current standing approval phrase:

`разрешаю тебе любые законные действия в рамках разработки проекта`

If that standing approval exists in the current thread and has not been
revoked, it satisfies owner authorization for later project-scoped live
commands that are otherwise allowed by canon and runbooks.

Exact one-off owner markers remain valid and may still be used.

Generic phrases such as `start`, `go`, or `начинай работу` do not themselves
authorize live commands unless the thread already contains the standing owner
approval or a more specific owner marker.

Standing approval does not widen command scope beyond what canon and runbooks
already allow.
