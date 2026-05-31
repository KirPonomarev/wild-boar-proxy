# WEB_LIVE_SERVER_READONLY_ADMISSION_PASS

## Goal

Prove that the design live server can be used as the current readonly truth
surface without reopening parked mutations, sandbox writes, or fixture-backed
false-green behavior.

## Scope

- start `python3 -m wild_boar_proxy.web_design_live_server --port 8788`
- inspect readonly HTTP surfaces:
  - `/api/actions`
  - `/api/live-readonly`
  - `/api/accounts-readonly`
  - `/api/api-connections-readonly`
- inspect `?screen=quick-start&source=live` and readonly summary screens
- verify negative cases:
  - parked POST action stays blocked
  - malformed POST JSON stays blocked
  - live failure copy does not reuse fixture truth
- capture screenshots and audit packets

Out of scope:

- account onboarding or lifecycle execution
- route mutation or provider checks
- mode set, sync, launch, diagnostics export execution
- sandbox binding or config/auth/state writes

## Findings

- server starts through `main(...)` on `127.0.0.1:8788` in
  `action_phase=live_readonly`
- `/api/actions` reports exactly two available actions:
  - `refresh_health_detail`
  - `stable_repair_plan`
- `/api/live-readonly` returned `status=ok`, `source=live_readonly`,
  `primary_truth_ok=true`, `ui_state=healthy`, with one warning:
  `ROTATION_EVIDENCE_CONTRADICTED`
- `/api/accounts-readonly` returned `status=ok`, `source=accounts_readonly`,
  `account_count=25`
- `/api/api-connections-readonly` returned `status=ok`,
  `source=api_connections_readonly`, `routes_count=0`,
  `runtime_claim_blocked=true`
- UI screens stayed in `source=live`; enabled visible actions remained readonly
  support only
- malformed POST JSON returned `UI_ACTION_NOT_ALLOWED`
- parked POST action `export_diagnostics` returned
  `UI_ACTION_PHASE_PARKED`
- invalid live-readonly JSON produced red failure copy with “previous healthy
  data not used” messaging instead of silent fixture fallback

## Decision

- status: `GO_TO_READONLY_TRUTH_PACKET_BASELINE_PASS`
- reason:
  - live server is startable and coherent as a readonly truth surface
  - parked actions remain parked in metadata, UI, and POST behavior
  - live failure states stay honest and do not masquerade as fixture success

## Next Guardrails

- keep the next contour packet-first:
  - `status --json`
  - `mode get --json`
  - `accounts list --json`
  - `healthcheck --json`
  - `rollout rotation inspect --json`
- do not interpret readonly support actions as runtime success claims
- do not reopen parked actions before sandbox admission contours
