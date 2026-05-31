# Spec: Web Codex Launch Mode Split And Dry Run Guard

## Objective

Split Codex launch modes in the WBP web UI and backend packets:

```text
Original Codex = protected baseline
Codex Custom = proxy-enabled workbench
```

This contour proves mode separation and a dry-run guard only. It does not launch Original Codex or Codex Custom.

## In Scope

- Add backend packet builders for launch modes.
- Add web endpoints:
  - `GET /api/codex/launch-modes`
  - `GET /api/codex/original/status`
  - `POST /api/codex/original/launch-dry-run`
  - `GET /api/codex/custom/status`
- Add a minimal Overview panel for Original and Custom modes.
- Prove Original dry-run rejects browser-controlled fields.
- Show previous Custom isolation proof only as last-known, not fresh truth.
- Keep `claim_gate blocked` visible.

## Out of Scope

- Original Codex live launch.
- Custom Codex live launch.
- Custom session manager.
- GPT accounts route proof.
- API route E2E.
- Moderate load.
- Desktop packaging.
- Design polish.
- Claim gate repair.

## Constraints

- `CLIProxyAPI` remains the engine.
- WBP remains the control layer.
- Browser must not provide proxy, endpoint, `HOME`, `CODEX_HOME`, path, model, route, backend, auth, token, or secret fields to Original dry-run.
- Dry-run success is not runtime success.
- Previous isolation proof is not fresh truth.

## Acceptance Criteria

- [x] Original and Custom launch modes are separate in backend packets.
- [x] Original and Custom launch modes are visible in WBP web UI.
- [x] Original dry-run accepts `{}` only.
- [x] Original dry-run rejects forbidden browser fields.
- [x] Original dry-run reports no proxy/custom env/model/route/backend injection.
- [x] Custom status is readonly readiness only.
- [x] Custom session is not admitted.
- [x] Browser proof shows `dry-run safe / gate blocked`.
- [x] Redaction audit is clean.

## Verification

- tests: see `closeout.md`.
- build: `node --check`; `git diff --check`.
- manual: browser proof screenshot and packet.
- live evidence: `browser_proof.json`.

## Open Questions

- Live Original dispatch remains out of scope and requires a separate contour if needed.
- Custom session manager remains the next implementation block.
