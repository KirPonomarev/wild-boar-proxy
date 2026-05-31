# API_PROVIDER_OWNER_SETUP_HANDOFF_PASS Spec

## Goal

Make missing API provider credentials understandable in web without turning web into a secret intake surface.

Flow:

`web click -> credential missing -> owner setup handoff -> operator sets owner env -> retry -> API connected`

## Canon

- `CANON.md`
- `MASTER_PLAN.md`
- `RUNTIME_CONTRACT.md`
- `STATE_SCHEMA.md`
- `COMMAND_API.md`
- `DELIVERY_RULES.md`
- `README.md`

## Scope

- Reuse existing credential command packets.
- Add setup metadata to credential status/admit missing result:
  - `supported_sources`
  - `expected_refs`
  - `provider_dashboard_url`
  - no secret value
- Map missing owner env in web to `credential_missing`.
- Show setup handoff metadata in action support details and ledger.
- Keep retry on the existing `api_route_connect` bridge path.

## Out Of Scope

- New setup command surface.
- API key input in web.
- Browser token/secret/auth/path/file intake.
- OAuth or provider dashboard automation.
- Desktop, packaging, redesign, or runtime readiness claims.

## Success Criteria

- [x] Missing credential is non-green.
- [x] Missing packet includes owner setup metadata.
- [x] Web shows `credential_missing`, expected refs, and provider dashboard URL.
- [x] Web has no API key input.
- [x] Retry after owner env succeeds through existing bridge.
- [x] Route appears after `api-connections-readonly` refresh.
- [x] Ledger records missing and admitted phases.
- [x] Secret value absent from text evidence.
- [x] Tests and browser proof passed.

## Evidence

- `evidence/browser-missing-action-packet.json`
- `evidence/browser-missing-summary.json`
- `evidence/browser-missing-dom-summary.json`
- `evidence/browser-missing-state.png`
- `evidence/browser-retry-action-packet.json`
- `evidence/browser-retry-summary.json`
- `evidence/browser-retry-dom-summary.json`
- `evidence/browser-retry-api-connections-after.json`
- `evidence/browser-retry-state.png`
- `evidence/redaction-check.json`

## Verdict

`closed_success` after final gate, independent audit, commit, and push.
