# Spec: WEB_CODEX_ACCOUNT_LOGIN_BRIDGE_PASS

## Objective

Replace the web account-connect live path's sandbox synthetic login bridge with the existing engine-owned Codex onboarding lane:

```text
web onboard_account -> accounts onboard --json -> cli-proxy-api -codex-login when needed -> sandbox auth artifact -> reserve-first import -> accounts refresh
```

## In Scope

- Use `accounts onboard --json` as the owner truth surface for the live web account connect action.
- Keep browser payload bounded to `ui_action=onboard_account`.
- Preserve reserve-first onboarding and `active_routing_changed=false`.
- Materialize the selected sandbox auth into sandbox `profile/auth.json` only when `WBP_REQUIRE_SANDBOX_AUTH_DIR=1`, so post-onboard status proof can use the newly admitted auth.
- Let status attestation use either `OPENAI_API_KEY` or Codex `access_token`.
- Update UI handoff text for engine-owned Codex login/onboard.
- Add targeted regression tests.

## Out of Scope

- Web token/password/auth/path input.
- Generic OAuth provider framework.
- API route work.
- Promotion to active.
- Desktop, packaging, or redesign.

## Constraints

- Wild Boar Proxy remains the control layer.
- CLIProxyAPI/owner lane owns auth flow.
- Current working Codex must not be used as the sandbox target.
- Runtime secrets must not appear in packets, logs, audit artifacts, or screenshots.

## Acceptance Criteria

- [x] `onboard_account` no longer calls `accounts login start/complete --provider sandbox` in the live path.
- [x] `onboard_account` calls `accounts onboard --json`.
- [x] Browser payload contains no token, secret, auth ref, path, or backend id.
- [x] New backend lands in `reserve`.
- [x] `active_routing_changed=false`.
- [x] Accounts refresh shows the new reserve account.
- [x] Full unittest gate passes.
- [x] Browser-context proof passes with redaction check.

## Verification

- tests: full required unittest gate, targeted live/web/UI tests.
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`, `git diff --check`.
- manual: code and evidence inspection.
- live evidence: `evidence/browser-run-summary.json`, `evidence/action-packet.json`, `evidence/accounts-readonly-after.json`.

## Open Questions

- Real operator login with the physical provider browser remains dependent on `cli-proxy-api -codex-login` behavior in the operator environment; this contour proves the WBP bridge and sandbox write boundary.
