# Spec: Codex Custom Session Manager

## Objective

Implement a server-owned Codex Custom session lifecycle for the WBP web interface without claiming inference. The contour creates, lists, inspects, cancels, cleans up, and records dry-run prompt admission for isolated Codex Custom sessions.

## In Scope

- Add a server-side `CodexCustomSessionManager`.
- Create sessions only from server-issued model ids.
- Bind each session to server-issued account selection proof.
- Expose session list, detail, transcript, prompt dry-run, cancel, and cleanup endpoints.
- Add a web panel for session lifecycle controls.
- Store service-ledger transcript entries without raw prompt text.
- Reject browser-supplied backend, route, account, auth, token, secret, and path fields.
- Prove no inference, no model response, no runtime meter, and zero token burn.

## Out of Scope

- Launching a real Codex process.
- Running GPT/API inference.
- Sending prompts to provider routes.
- Persisting custom app sessions beyond the server-owned temp root.
- Changing account lifecycle, rollout, package, installer, or release behavior.
- Mutating the current Codex profile.

## Constraints

- JSON command packets are primary truth.
- Browser may submit only admitted action fields.
- Session cleanup is by server-owned `session_id`, not arbitrary path.
- Prompt text is admitted only as dry-run metadata and must not be echoed raw in transcript artifacts.
- `model_response_present=false`, `inference_proven=false`, `runtime_meter_attached=false`, and `token_burn=0` must be explicit on dry-run proof.

## Assumptions

- `CLIProxyAPI` remains the engine for later inference contours.
- This contour prepares the session shell for `CODEX_CUSTOM_GPT_API_E2E_PASS`.
- Account selection truth is read from the existing Codex Custom account-selection surface.

## Acceptance Criteria

- [x] Session create/list/detail endpoints exist.
- [x] Prompt dry-run endpoint admits a prompt without inference.
- [x] Transcript endpoint returns service-ledger-only data.
- [x] Cancel endpoint does not claim process kill.
- [x] Cleanup endpoint removes only server-owned session state.
- [x] Browser-forged backend/route/path fields are rejected.
- [x] UI can create, dry-run, cancel, and cleanup a session.
- [x] Redaction audit is clean for text artifacts.

## Verification

- tests: targeted and full web/session unit suites.
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`.
- manual: in-app browser click proof on `http://127.0.0.1:8796/`.
- live evidence: `proof.json`, packet artifacts, screenshots, and `browser_proof.json`.

## Open Questions

- The next contour must decide the exact process runner and provider route binding for real Codex Custom inference.
