# WBP Responses Runtime Compatibility R1 Closeout

## Goal

Classify WBP Responses runtime behavior for non-stream shape, SSE sequence, tool loop, reasoning handling, error shape, and failure semantics through a controlled local harness without native launch, external provider live calls, model availability claims, egress claims, UX claims, Original Codex mutation, or final E2E claims.

## Result

- status: `WBP_RESPONSES_RUNTIME_COMPATIBILITY_CLASSIFIED_WITH_LIMITS`
- final verdict: local runtime harness packets classify Responses behavior and failure semantics; client cancel remains `blocked_by_host_environment` and does not count as a pass.
- closure state: CLOSED

## Contour Capsule

- goal: classify WBP Responses runtime and failure semantics through controlled local harness packets
- branch: codex/external-agent-lab-isolated
- head: a065d064a64554e6af62d90e401e99e3b3a70545 before this contour commit
- touched files: wild_boar_proxy/operator_surface.py; tests/test_wbp_responses_fixture_compatibility.py; tools/responses_runtime_compatibility_probe.py; audit_results/wbp_responses_runtime_compatibility_r1_2026-05-26
- tests run: py_compile; responses_runtime_compatibility_probe; tests.test_wbp_responses_fixture_compatibility; tests.test_operator_surface; tests.test_codex_model_registry; JSON parse; secret scan
- blocked risks: client cancel remains blocked_by_host_environment and not counted as pass; socket-level external provider live behavior remains out of scope
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest -q tests.test_wbp_responses_fixture_compatibility` passed 17 tests; combined runtime subset passed 40 tests.
- build: `python3 -m py_compile tools/responses_runtime_compatibility_probe.py wild_boar_proxy/operator_surface.py tests/test_wbp_responses_fixture_compatibility.py` passed.
- manual: independent scanner/auditor packet records no blocking findings and cites current code, tests, and evidence packets.
- live verification: not attempted by design; this contour does not prove native UX, external provider live compatibility, model availability, direct egress absence, Original reversibility, or final E2E.

## Artifacts

- spec: thread-owned contour instructions; no repo-resident planning artifact added.
- packet: `audit_results/wbp_responses_runtime_compatibility_r1_2026-05-26/responses_runtime_compatibility_matrix.json`
- report: `audit_results/wbp_responses_runtime_compatibility_r1_2026-05-26/independent_wire_audit.json`; `audit_results/wbp_responses_runtime_compatibility_r1_2026-05-26/scanner_agent_fact_report_packet.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit created after this closeout
- pushed: contour branch pushed after commit

## Scope Check

- unrelated work mixed in: no; pre-existing historical dirty evidence remained unstaged and untouched.
- private-data risk reviewed: yes; generated packets do not store raw prompt secrets or auth headers, and evidence secret scan produced no matches.

## Notes

- blockers encountered: probe initially attempted to parse SSE as single JSON; corrected to classify SSE event lines separately before evidence closeout.
- resume from here: CLOSED
