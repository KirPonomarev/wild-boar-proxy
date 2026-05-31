# Spec: Codex Custom External API Owner Credential Unblock

## Objective

Capture exact owner-credential truth for the server-owned external API route and
either unblock the live external-route proof or stop with an exact blocked
packet.

## In Scope

- canonical owner credential status packet
- canonical owner credential admit packet
- exact blocker classification
- independent read-only audit
- blocked-pass evidence and closeout

## Out of Scope

- browser secret intake
- route-framework changes
- model-registry changes
- retrying route connect or live prompt without owner-side change
- claim widening for active `8B`

## Constraints

- browser must not carry `api_key`, `secret`, `route_id`, `path`, or `backend`
- retry spiral is forbidden without owner-side change
- historical evidence is support only
- final outcome must be exact blocked truth or full closure; no fuzzy middle

## Assumptions

- current provider remains `openrouter`
- canonical owner surfaces are:
  - `external-models credentials status --provider openrouter --json`
  - `external-models credentials admit --provider openrouter --source owner-env --json`

## Acceptance Criteria

- [x] owner credential truth is machine-proven
- [x] exact blocker packet is captured if credential is still missing
- [x] no fake route-connect or live-prompt retry is claimed without owner-side change
- [x] independent audit confirms exact blocked status

## Verification

- tests:
  - none required; no product code changed in this pass
- build:
  - `git diff --check`
- manual:
  - canonical owner credential status/admit packets captured
- live evidence:
  - `credential_status_packet.json`
  - `credential_admit_blocked_packet.json`
  - `independent_audit_report.json`

## Open Questions

- owner-side credential materialization timing remains external to this pass
