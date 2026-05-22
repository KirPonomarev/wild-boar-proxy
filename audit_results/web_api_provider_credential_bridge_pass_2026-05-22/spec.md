# WEB_API_PROVIDER_CREDENTIAL_BRIDGE_PASS Spec

## Goal

Make the web `Подключить API` action run the provider credential bridge honestly:

`web click -> owner credential status/admit -> server-owned route add/adopt -> validate -> api-connections-readonly refresh`

The browser must not provide an API key, token, secret, auth path, local path, backend id, or route id.

## Canon

- `CANON.md`
- `MASTER_PLAN.md`
- `RUNTIME_CONTRACT.md`
- `STATE_SCHEMA.md`
- `COMMAND_API.md`
- `DELIVERY_RULES.md`
- `README.md`

## Scope

- Extend internal web command allowlist with owner credential commands:
  - `external-models credentials status --provider openrouter --json`
  - `external-models credentials admit --provider openrouter --source owner-env --json`
- Extend `api_route_connect` server action so credential status/admit runs before route add/adopt and validate.
- Keep UI as control layer only: the browser sends only `ui_action=api_route_connect`.
- Expose credential phase in action result and ledger support details.
- Preserve server-owned route source and readonly refresh proof.

## Out Of Scope

- Web API key input.
- Browser file/path/token/secret intake.
- Provider dashboard automation or OAuth.
- Desktop, packaging, broad route builder, or runtime readiness claims.

## Success Criteria

- [x] `api_route_connect` checks `credentials status`.
- [x] Missing credential triggers `credentials admit --source owner-env`.
- [x] Admit failure is non-green and blocks route add/validate.
- [x] Browser payload rejects forbidden fields, including `api_key`.
- [x] Successful action packet proves `credential_phase=credential_admitted`.
- [x] Route is added and validated after credential admission.
- [x] `api-connections-readonly` refresh shows route connected.
- [x] Ledger exposes credential phase without secret value.
- [x] Redaction check confirms sentinel secret is absent from text evidence.
- [x] Tests and browser proof passed.

## Evidence

- `evidence/browser-action-packet.json`
- `evidence/browser-run-summary.json`
- `evidence/browser-api-connections-after.json`
- `evidence/browser-run-network.json`
- `evidence/browser-dom-summary.json`
- `evidence/browser-api-credential-bridge-after.png`
- `evidence/credential-status-after-browser.json`
- `evidence/routes-list-after-browser.json`
- `evidence/redaction-check.json`

## Verdict

`closed_success` after final closeout resilience check, commit, and push.
