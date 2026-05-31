# Spec: Codex Custom WBP Trace GPT Account Live Prompt Pass

## Objective

Add an independent local WBP trace observer to the Codex Custom prompt path so
`wbp_path_proven=true` can only be emitted when an observed request is forwarded
through the WBP endpoint and receives a clean upstream response. Live token burn
is gated by `CANON.md` owner authorization.

## In Scope

- temporary localhost trace observer
- server-side `trace_wbp=True` for Codex Custom session prompt execution
- redacted trace packet with request/response digests only
- `wbp_path_proven` gated by independent trace evidence
- tests for observer redaction, forwarding, path proof, and browser trace-field rejection
- blocked live authorization artifact when owner phrase is absent

## Out of Scope

- running live GPT account prompt without owner authorization
- account rotation/load
- external API route proof
- UI redesign
- package/installer
- current Codex mutation

## Constraints

- Browser may not supply trace controls, model/backend/route ids, auth, token, or paths.
- Trace observer must not store raw prompt, auth header, token, account id, backend id, or response body.
- Trace observer is proof surface only; runtime health remains owned by status/healthcheck/account packets.
- No success may be inferred from config, exit code, or final response text alone.

## Acceptance Criteria

- [x] observer forwards allowed OpenAI-compatible paths to WBP downstream endpoint
- [x] observer records only digests and booleans
- [x] `independent_wbp_trace_observed` requires observed request, observed response, WBP forwarding, matching downstream endpoint, 2xx/3xx upstream status, and clean redaction flags
- [x] Codex Custom web prompt uses server-side trace mode
- [x] browser `trace_wbp` and `trace_observer` fields are forbidden
- [x] targeted tests pass
- [ ] live GPT-account prompt executed after owner authorization

## Verification

- tests:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_operator_surface tests.test_codex_custom_sessions tests.test_web_design_live_server -q`
  - full gate recorded in closeout
- build:
  - `git diff --check`
- manual:
  - independent audit
- live evidence:
  - blocked until owner authorization phrase is present in active thread

## Open Questions

- After owner authorization, whether the first live run should use the web endpoint or the lower-level session manager harness for tighter evidence capture.
