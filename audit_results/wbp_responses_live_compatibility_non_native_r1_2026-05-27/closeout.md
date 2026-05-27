# WBP Responses Live Compatibility Non Native R1 Closeout

## Goal

Classify bounded live Responses compatibility through direct non-native WBP
exercise across non-stream, streaming, tool-loop follow-up, and failure
semantics surfaces, without native Codex launch, CLI acceptance, model
availability, direct-egress, provider-family, or final E2E claims.

## Result

- status: ok
- final verdict: WBP_RESPONSES_LIVE_COMPATIBILITY_NON_NATIVE_R1_CLASSIFIED
- closure state: CLOSED

## Contour Capsule

- goal: classify bounded direct WBP live Responses compatibility across the
  admitted non-native surfaces
- branch: codex/external-agent-lab-isolated
- head: 076f44ca3dde1975baa5ab23aeaaa706afbffe66
- touched files: tools/responses_live_non_native_probe.py, tests/test_responses_live_non_native_probe.py, audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27
- tests run: python3 -m pytest -q tests/test_responses_live_non_native_probe.py; live probe JSON emission; JSON parse; secret marker scan; closeout resilience
- blocked risks: native Codex acceptance, CLI acceptance, model availability,
  provider-family compatibility, direct egress absence, and final E2E remain unclaimed
- closure state: CLOSED

## Verification

- tests: python3 -m pytest -q tests/test_responses_live_non_native_probe.py
- build: probe packet generation and JSON parse succeeded
- manual: all emitted JSON packets parsed; secret marker scan was clean; independent audit packet status was ok
- live verification: direct WBP POST /v1/responses with model gpt-5.4-mini
  classified non-stream, streaming, failure semantics, and repaired tool-loop
  follow-up. Canonical tool-loop follow-up replay passed with
  followup_upstream_status_code 200 and assistant continuation observed.
  Negative-control previous_response_id-only follow-up returned 400 and was kept
  separate from model/provider claims.

## Artifacts

- spec: thread-only contour definition
- packet: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_non_native_summary_packet.json
- report: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_non_native_false_green_audit.json
- matrix: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_live_compatibility_matrix.json
- tool-loop follow-up request: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_tool_loop_followup_request_packet.json
- tool-loop follow-up response: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_tool_loop_followup_response_packet.json
- tool-loop follow-up failure classification: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_tool_loop_followup_failure_packet.json
- tool-loop cause classification: audit_results/wbp_responses_live_compatibility_non_native_r1_2026-05-27/responses_tool_loop_followup_root_cause_classification_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the contour commit containing this closeout
- pushed: recorded by repository remote after contour verification

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes, raw prompt text, bearer token material, auth headers, upstream body text, and provider secrets are excluded from emitted evidence

## Notes

- blockers encountered: initial tool-loop follow-up remained limited when the
  probe used previous_response_id plus function_call_output only. Reopen repair
  proved a narrower accepted follow-up shape: prior output replay plus
  function_call_output.
- resume from here: CLOSED
