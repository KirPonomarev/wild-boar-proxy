<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# RESPONSES_STREAMING_TOOLS_FAILURE_SEMANTICS_R1 Closeout

## Goal

Reprove the currently admitted semantics boundary for the Custom Codex dual-lane
runtime across plain responses, streaming behavior, tool-call behavior, and
bounded failure semantics without widening claims into consumer-accepted
streaming, consumer-accepted tool execution, provider-family compatibility,
policy completeness, or final workflow closure.

## Result

- status: completed
- final verdict: current code still truthfully supports plain-text consumer acceptance for both lanes, while streaming remains adapter-SSE-only with limits, tool semantics remain history-shaped and text-only with limits, and observed failure semantics remain bounded and non-silent
- closure state: CLOSED

## Contour Capsule

- goal: reprove current item-7 semantics boundaries after current-code dual-lane session reproof, and confirm that no false-green upgrade has crept into responses, streaming, tools, or failure classification
- branch: codex/external-agent-lab-isolated
- head: `7bee11f7`
- touched files:
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/responses_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/streaming_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/tool_call_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/failure_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/consumer_acceptance_boundary_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/protocol_non_claims_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/protocol_gap_matrix.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/false_green_boundary_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/independent_audit_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest -q tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`
  - `python3 -m pytest -q tests/test_wbp_responses_fixture_compatibility.py`
  - `python3 -m py_compile tools/responses_streaming_tools_failure_semantics_r1_probe.py wild_boar_proxy/operator_surface.py wild_boar_proxy/codex_custom_sessions.py`
  - `python3 tools/responses_streaming_tools_failure_semantics_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29`
- blocked risks:
  - consumer-visible streaming remains unproven
  - upstream-native streaming remains blocked by the reviewed adapter path because upstream requests still do not carry live `stream: true`
  - model-driven function-tool protocol remains unsupported by the reviewed adapter path
  - structured response semantics beyond plain text remain unproven
  - observed failure taxonomy remains bounded rather than exhaustive
- closure state: CLOSED

## Verification

- tests:
  - `2 passed` in `tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`
  - `20 passed, 2 subtests passed` in `tests/test_wbp_responses_fixture_compatibility.py`
- build:
  - `py_compile` passed for the contour-local probe and its current runtime dependencies
- manual:
  - the contour-local probe wrote `9/9` required JSON packet artifacts in a fresh 2026-05-29 evidence directory
- live verification:
  - none in this contour; verification stayed at bounded probe, fixture, and adapter/session-manager truth surfaces by design

## Artifacts

- spec: thread-only contour plan for `RESPONSES_STREAMING_TOOLS_FAILURE_SEMANTICS_R1`
- packet:
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/responses_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/streaming_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/tool_call_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/failure_semantics_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/consumer_acceptance_boundary_packet.json`
  - `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-29/independent_audit_packet.json`
- report:
  - plain-text response semantics remain consumer-accepted for both reproved lanes
  - streaming still classifies as `current_adapter_sse_only_with_limits`
  - tool-call semantics still classify as `history_shaped_text_only_with_limits`
  - bounded failure cases remain packet-backed and non-silent

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded in the contour closeout commit on `codex/external-agent-lab-isolated`
- pushed: yes

## Scope Check

- unrelated work mixed in: no; unrelated dirty worktree files outside this contour remained untouched
- private-data risk reviewed: yes; packets remain synthetic/bounded, carry no raw secrets, and do not widen browser authority

## Notes

- blockers encountered:
  - this contour did not reveal a new runtime regression; current code reproduced the same bounded semantics limits already known on 2026-05-28
  - current truth still blocks any upgrade from adapter-generated SSE into consumer-visible streaming acceptance
  - current truth still blocks any upgrade from adapter-side tool shaping into model-driven function-tool compatibility or consumer-accepted tool execution
  - the observed failure matrix is intentionally bounded and remains a non-claim for completeness
- resume from here: CLOSED
