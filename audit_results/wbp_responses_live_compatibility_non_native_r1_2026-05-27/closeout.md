# WBP Responses Live Compatibility Non Native R1 Closeout

## Goal

Classify bounded live Responses compatibility through a direct WBP non-stream
request, without native Codex launch, CLI acceptance, streaming, tool-loop,
model-availability, direct-egress, provider-family, or final E2E claims.

## Result

- status: ok
- final verdict: WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_CLASSIFIED
- closure state: CLOSED

## Contour Capsule

- goal: classify bounded direct WBP live non-stream Responses compatibility
- branch: codex/external-agent-lab-isolated
- head: c12de2a2e8812679ae92681ea13a86ac8c39c4a1
- touched files: tools/responses_live_non_native_probe.py, tests/test_responses_live_non_native_probe.py, audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27
- tests run: python3 -m py_compile tools/responses_live_non_native_probe.py; python3 -m unittest -q tests.test_responses_live_non_native_probe; probe JSON emission; JSON parse; secret marker scan; closeout resilience
- blocked risks: native Codex acceptance, CLI acceptance, model availability, streaming compatibility, tool-loop compatibility, provider-family compatibility, direct egress absence, and final E2E remain unclaimed
- closure state: CLOSED

## Verification

- tests: python3 -m unittest -q tests.test_responses_live_non_native_probe
- build: python3 -m py_compile tools/responses_live_non_native_probe.py
- manual: all emitted JSON packets parsed; secret marker scan was clean; independent audit packet status was ok
- live verification: direct WBP POST /v1/responses, non-stream, model gpt-5.4-mini, upstream_status_code 200, response_status completed, response shape accepted by direct WBP client

## Artifacts

- spec: thread-only contour definition
- packet: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_non_native_summary_packet.json
- report: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_non_native_false_green_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the contour commit containing this closeout
- pushed: recorded by repository remote after contour verification

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes, raw prompt text, bearer token material, auth headers, upstream body text, and provider secrets are excluded from emitted evidence

## Notes

- blockers encountered: authorized configured-model gpt-5.5 attempt timed out before HTTP status; final classified evidence uses the bounded successful gpt-5.4-mini direct WBP non-stream attempt
- resume from here: CLOSED
