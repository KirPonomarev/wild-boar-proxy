# UI_WEB_GLOBAL_CANONICAL_SURFACE_AUDIT_PASS Spec

## Goal

Audit the current web UI as one product surface after the screen-by-screen
transfer and stabilization contours. This contour checks visual fit, semantic
truth boundaries, forbidden browser inputs, release/readiness claims, and
private-reference traces. It is not a redesign contour and does not introduce
new command or runtime surfaces.

## Scope

- `Overview`
- `Accounts`
- `API-подключения`
- `Diagnostics`
- `Settings`
- `Setup`
- `Select Client`
- `Account Onboarding`
- `Account Detail drawer`
- `Action Ledger`
- `Diagnostics Export Result`
- `About / License / Version`
- Static discovery of the present but non-navigation `import-existing` route

## Out Of Scope

- runtime changes
- command adapter changes
- allowlist expansion
- live server contract changes
- desktop/native work
- new screens or large redesigns
- private external-reference research artifacts
- production, release, package, or desktop-ready claims

## Acceptance

- Implemented planned surfaces fit `1600x1000`, or defects are explicitly
  documented for follow-up.
- No visible inline SVG icons on audited screens.
- No active browser file/path/token/secret/config editor surface.
- No raw logs, raw state files, or diagnostics bundle parsing in the web UI.
- No fake release, production, desktop, package, or support claims.
- No private external-reference forbidden terms in the contour artifacts.
- Command result and runtime truth remain separate.

## Stop Conditions

- A required fix would touch runtime, command adapter, allowlist, live server, or
  desktop/native code.
- A screen cannot fit without a redesign pass.
- UI success semantics contradict command/runtime truth.
- Private external-reference traces appear in repo artifacts.
- Tests fail.
