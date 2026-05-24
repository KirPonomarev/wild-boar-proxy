# WEB_CODEX_CUSTOM_SINGLE_SESSION_CONTROL_PASS

## Goal

Prove the first web-controlled Codex Custom session path:

```text
WBP web UI -> create isolated session -> server-issued model -> one bounded live prompt
-> WBP /v1/responses trace proof -> transcript/cleanup -> current Codex untouched
```

## Scope

In scope:

- Codex Custom session create/list/detail through web-owned endpoints.
- One bounded live prompt from the web UI.
- Machine proof fields for WBP trace path, upstream status, source provenance, and current Codex isolation.
- Cleanup of the owned temp session root.
- Browser proof, targeted tests, redaction audit, and independent audit.

Out of scope:

- Account rotation/load.
- Account mutation/login/reauth.
- Provider credential mutation.
- Desktop GUI launch.
- Package/installer/release work.
- UI design polish.

## Guardrails

- Browser cannot provide backend/source/path/auth/secret fields for prompt execution.
- Success requires WBP trace proof and isolated engine home proof.
- `current_codex_home_used=true` blocks success with `CURRENT_CODEX_TOUCHED`.
- Trace observer packets exposed to browser are whitelisted.
- No raw prompt, auth ref, backend id, or secret value may be written to artifacts.
