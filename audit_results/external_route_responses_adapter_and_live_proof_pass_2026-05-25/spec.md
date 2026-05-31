# Spec: External Route Responses Adapter And Live Proof

## Objective

Repair the route-backed external API path for `Codex Custom` by translating the
Codex `responses` wire protocol into the server-owned external route
`chat/completions` protocol, then prove one real external live prompt through
the WBP web path without reopening already-proven GPT-account or launch slices.

## In Scope

- bounded `responses` adapter inside
  `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/operator_surface.py`
- route-backed operator path wiring to the local adapter
- targeted route-backed tests
- live reproof through:
  - `/api/codex/custom/models`
  - `/api/codex/custom/launch`
  - `/api/codex/custom/sessions/<id>/prompt`
- machine-readable evidence for the route-backed external proof

## Out of Scope

- new provider branches
- browser-owned route or secret intake
- UI redesign
- screenshot/recovery final closure for full `8B`
- any claim that `8B` is fully complete by adapter success alone

## Constraints

- keep provider ownership server-side
- keep Codex on `wire_api = "responses"`
- do not reintroduce `chat_completions` as a client-facing wire mode
- preserve `current_codex_touched = false`
- keep the slice bounded to external-route repair and proof

## Assumptions

- `OPENROUTER_API_KEY` has already been admitted into
  `/Users/kirillponomarev/.wild-boar-proxy/external-models/secrets.env`
- the live route id remains `wbp-web-primary-openrouter`
- the current owner server path on `127.0.0.1:8790` is an admitted test surface

## Acceptance Criteria

- [x] route-backed prompt path uses a bounded local `responses` adapter
- [x] the adapter translates `responses` requests into provider
  `chat/completions` requests
- [x] streaming clients receive a `response.completed` event
- [x] one real external live prompt succeeds through the WBP web path
- [x] route provenance remains machine-proven
- [x] transcript response is redacted and bounded
- [x] `current_codex_touched` remains false
- [x] targeted tests are green
- [x] full `8B` is not overclaimed beyond this slice

## Verification

- tests:
  - `tests.test_operator_surface`
  - `tests.test_codex_custom_sessions`
  - `tests.test_web_design_live_server`
- build:
  - `py_compile`
  - `git diff --check`
- manual:
  - direct `codex exec` debug against the local adapter
- live evidence:
  - `models_packet.json`
  - `launch_packet.json`
  - `prompt_packet.json`
  - `live_proof_summary.json`

## Open Questions

- whether screenshot/recovery boundaries are sufficient for final `8B` closure
- whether a final `8B` reconciliation pass can close without additional
  screenshot capture work
