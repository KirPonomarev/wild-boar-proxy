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
