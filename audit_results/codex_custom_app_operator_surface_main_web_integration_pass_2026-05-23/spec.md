# Spec: Codex Custom App Operator Surface Main Web Integration

## Objective

Integrate the hardened Codex Operator path into the main Wild Boar Proxy web UI as one bounded operator scenario:

```text
main WBP web overview -> Codex Operator panel -> server-issued models -> one prompt run -> isolated Codex engine -> response packet
```

This contour proves the main web control surface wiring. It does not close runtime claim gate, provider route proof, account rotation/load proof, GUI Desktop launch, package, or design gate.

## In Scope

- Add server-owned `/api/operator/status`, `/api/operator/models`, `/api/operator/transcript`, and `/api/operator/run`.
- Add a minimal Overview `Codex Operator` panel.
- Accept only browser payload keys `prompt` and `model_id`.
- Validate `model_id` against server-issued `/v1/models` from WBP endpoint `http://127.0.0.1:8318/v1`.
- Send prompt to Codex engine through stdin, not argv.
- Use temporary `HOME` and `CODEX_HOME`.
- Capture browser UI proof and process-only isolation proof.
- Add targeted tests for adapter and web endpoints.

## Out of Scope

- GUI Desktop app launch.
- Production app/package/installer.
- Rich UI/design polish.
- Account lifecycle mutation.
- Runtime claim gate repair.
- Provider route proof.
- Rotation/load proof.
- Current `~/.codex` mutation.

## Constraints

- `CLIProxyAPI` remains the engine.
- Wild Boar Proxy remains the control layer.
- Browser must not send `api_key`, `secret`, `token`, `auth`, `path`, `backend_id`, `route_id`, or runtime config fields.
- JSON packets are primary truth.
- Browser proof is not isolation proof.
- `claim_gate blocked` must remain visible and must not be converted into a green global success.

## Acceptance Criteria

- [x] Main web Overview exposes `Codex Operator`.
- [x] `/api/operator/models` exposes server-issued models.
- [x] Browser run payload is bounded to `prompt` and `model_id`.
- [x] Free-form `route_id`/`backend_id`/secret/path fields are rejected server-side.
- [x] Browser click proof returns `MAIN_WEB_OK`.
- [x] Process-only proof returns `MAIN_WEB_PROCESS_OK`.
- [x] Protected current Codex surfaces remain unchanged in process-only proof.
- [x] UI displays `prompt ok / gate blocked` when refresh packet reports blocked claim gate.
- [x] Redaction audit is clean.
- [x] Independent audit is recorded.

## Verification

- tests: see `closeout.md`.
- build: `node --check` and `git diff --check`.
- manual: browser proof artifact.
- live evidence: `browser_proof.json`, `process_isolation_proof.json`.

## Open Questions

- Runtime claim gate remains blocked by existing policy drift claims and belongs to a later runtime contour.
