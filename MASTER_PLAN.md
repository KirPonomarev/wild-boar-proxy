# Managed Companion Control App Master Plan

## Product

Wild Boar Proxy is an experimental managed companion control app built on top
of `CLIProxyAPI`.

## Strategy

- do not fork the host client
- do not build a second proxy engine
- keep `CLIProxyAPI` as engine
- keep Wild Boar Proxy as the managing layer
- design the architecture for 20 accounts from day one
- prove rollout gradually through staged updates

## Positioning

Wild Boar Proxy is not a universal GUI for `CLIProxyAPI`.

It is a managed operations layer focused on:

- profile orchestration
- runtime modes
- pool lifecycle
- onboarding
- diagnostics
- recovery
- staged scaling

## Workstreams

1. Freeze terminology and boundaries.
2. Freeze runtime contract.
3. Freeze state schema.
4. Freeze command API with `--json`.
5. Harden `stable` and `managed` runtime behavior.
6. Productize reserve-first onboarding.
7. Build a minimal operator UI.
8. Add diagnostics export and recovery flows.
9. Prepare experimental public packaging.
10. Prove staged scaling from 10 to 20 accounts.

## Delivery order

1. Runtime hardening
2. Onboarding
3. State and diagnostics
4. UI
5. Packaging
6. Staged pool expansion
