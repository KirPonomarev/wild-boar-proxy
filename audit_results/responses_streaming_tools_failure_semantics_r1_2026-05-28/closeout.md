# Responses Streaming Tools Failure Semantics R1 Closeout

## Goal

Classify the currently observed protocol-semantics boundary for the admitted
dual-lane Custom Codex runtime across plain responses, streaming behavior,
tool-call shape, and failure behavior without widening claims into provider
family compatibility, production-ready streaming, consumer-accepted tool
execution, or completed fallback policy.

## Result

- status: `ok`
- final verdict: `RESPONSES_STREAMING_TOOLS_FAILURE_SEMANTICS_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: packetize plain-response acceptance, current-adapter-only streaming, model-driven tool-protocol limits, and bounded failure semantics while blocking false-green protocol claims
- branch: `codex/external-agent-lab-isolated`
- head: `d692a388c80615c89e296de1d5392eb3e37b5518`
- touched files: `tools/responses_streaming_tools_failure_semantics_r1_probe.py`, `tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`, `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-28/*.json`, `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile tools/responses_streaming_tools_failure_semantics_r1_probe.py tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`; `python3 -m pytest -q tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`; `python3 -m pytest -q tests/test_wbp_responses_fixture_compatibility.py`; `python3 -m pytest -q tests/test_responses_streaming_tools_failure_semantics_r1_probe.py tests/test_wbp_responses_fixture_compatibility.py`; `python3 tools/responses_streaming_tools_failure_semantics_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-28`; `python3 tools/check_closeout_resilience.py audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-28/closeout.md`; `git diff --check`
- blocked risks: consumer-visible streaming remains unproven; upstream-native streaming is currently blocked by the reviewed adapter path because upstream requests are forced to `stream: false`; model-driven function-tool protocol remains unsupported by the reviewed adapter path because top-level tool declarations are not forwarded upstream and text-only success remains required; structured response semantics beyond plain text remain unproven; the observed failure matrix is bounded and non-silent but not exhaustive
- closure state: CLOSED

## Verification

- tests: `2 passed` in `tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`; `20 passed, 2 subtests passed` in `tests/test_wbp_responses_fixture_compatibility.py`; `22 passed, 2 subtests passed` in the combined focused pytest run
- build: `py_compile` passed for the contour-local probe and focused probe test
- manual: the contour-local probe wrote `9/9` required packet artifacts plus an owned `probe_session_root/` scratch session tree under the contour evidence directory; `responses_semantics_packet.json` proves plain-text consumer acceptance for both the ChatGPT lane and one API/WBP route lane, `streaming_semantics_packet.json` classifies streaming as `current_adapter_sse_only_with_limits` with `upstream_request_stream_flag_true=false`, `tool_call_semantics_packet.json` keeps model-driven function-tool protocol unsupported while still proving adapter-side history shaping and text-only output handling, and `failure_semantics_packet.json` records bounded 400/502/runner-exception paths without silent lane substitution
- live verification: none in this contour; verification stayed at fixture/dry-run and bounded session-manager probe level by design

## Artifacts

- spec: thread-only contour plan for `RESPONSES_STREAMING_TOOLS_FAILURE_SEMANTICS_R1`
- packet: `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-28/responses_semantics_packet.json`
- report: `audit_results/responses_streaming_tools_failure_semantics_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; the contour-local probe uses synthetic route/account identifiers, packets contain no raw secrets, and the owned `probe_session_root/` transcript tree stays inside the contour evidence directory

## Notes

- blockers encountered: the first blocker was evidence hygiene rather than product logic: the contour worktree already contained an untracked probe and test file, so the first step was to verify whether they were real or just narrative scaffolding. They proved real under `py_compile` and focused pytest. A second blocker was verification drift: a parallel `rm -rf` plus artifact-read attempt raced the evidence directory creation and briefly produced an empty summary, so evidence generation was rerun sequentially before any claim was recorded. A third blocker was claim scope: earlier runtime surfaces in `operator_surface.py` and `codex_custom_sessions.py` can easily read as stronger than they are, because adapter-generated SSE and adapter-shaped tool-call messages look rich at the wire boundary while the consumer path still only proves plain-text acceptance through `final_message`. A final independent read-only audit found one material overclaim and one wording bug in the contour-local packets: the prior tool packet treated function-tool request admission as if that implied model-driven tool semantics support, and the prior streaming gap phrased a hard-coded adapter limitation as mere lack of evidence. The contour-local probe and tests were tightened so the current packets now record the narrower truth: plain text is consumer-accepted for both lanes, streaming is current-adapter SSE only, model-driven function-tool protocol is unsupported by the reviewed adapter path, history-shaped tool traces remain text-only and non-consumer-accepted, and failure packets stay bounded instead of silently substituting lanes or turning adapter normalization into upstream-native compatibility. Independent read-only audit findings are recorded in `independent_audit_packet.json`; any residual limits that survive are explicit open gaps rather than deferred narrative promises.
- resume from here: CLOSED
