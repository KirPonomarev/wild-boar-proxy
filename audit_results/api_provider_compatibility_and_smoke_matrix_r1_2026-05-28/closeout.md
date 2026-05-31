# API Provider Compatibility And Smoke Matrix R1 Closeout

## Goal

Classify the exact current API-lane provider/model smoke rows from the current
server-issued registry truth without promoting row results into provider-family
compatibility, tools/streaming parity, live upstream acceptance, or policy
completion claims.

## Result

- status: `ok`
- final verdict: `API_PROVIDER_COMPATIBILITY_AND_SMOKE_MATRIX_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: classify exact current `wbp_api` rows as bounded plain-response session-runtime harness passes or blocked rows, while preserving inherited semantic limits and blocking family-wide overclaim
- branch: `codex/external-agent-lab-isolated`
- head: `48f084dc0ed1dbb229c7d3bd6b0f013bc262ed5b`
- touched files: `tools/api_provider_compatibility_and_smoke_matrix_r1_probe.py`, `tests/test_api_provider_compatibility_and_smoke_matrix_r1_probe.py`, `audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28/*.json`, `audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile tools/api_provider_compatibility_and_smoke_matrix_r1_probe.py tests/test_api_provider_compatibility_and_smoke_matrix_r1_probe.py`; `python3 -m pytest -q tests/test_api_provider_compatibility_and_smoke_matrix_r1_probe.py`; `python3 -m pytest -q tests/test_api_provider_compatibility_and_smoke_matrix_r1_probe.py tests/test_responses_streaming_tools_failure_semantics_r1_probe.py`; `python3 tools/api_provider_compatibility_and_smoke_matrix_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28`; `python3 tools/check_closeout_resilience.py audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28/closeout.md`; `git diff --check`
- blocked risks: live upstream provider acceptance remains unproven here; the matrix is narrower than the 8-12 row target because only four current `wbp_api` rows exist in the current server-issued snapshot; `direct-mistral-devstral-2512` remains blocked by catalog/runtime route-visibility mismatch; `wbp-disabled-route` remains blocked and non-selectable; streaming and tool semantics remain inherited/open limits rather than row-proven capabilities; provider identity remains unresolved where the current snapshot omits `provider`
- closure state: CLOSED

## Verification

- tests: `2 passed` in `tests/test_api_provider_compatibility_and_smoke_matrix_r1_probe.py`; `4 passed` in the combined focused pytest run with the prior semantics probe test
- build: `py_compile` passed for the contour-local probe and focused probe test
- manual: the contour-local probe wrote `8/8` required packet artifacts with parseable JSON; `provider_smoke_matrix_packet.json` records a 4-row current matrix with `live_provider_calls_attempted=false`, `upstream_provider_acceptance_proven=false`, and row-pass scope constrained to bounded plain-response session-runtime harness only; `provider_smoke_row_results.json` shows `native-looking-external` and `wbp:deepseek-max` as `pass_with_limits`, `direct-mistral-devstral-2512` as `blocked_by_runtime_path` with `EXTERNAL_API_ROUTE_NOT_VISIBLE`, and `wbp-disabled-route` as `blocked_by_runtime_path` with `MODEL_NOT_SELECTABLE` and `ROUTE_DISABLED`; `provider_semantic_limits_inheritance_packet.json` preserves the prior contour’s `current_adapter_sse_only_with_limits` and unsupported model-driven tool protocol semantics for passing rows
- live verification: none in this contour; the smoke scope stayed explicitly at bounded current session-runtime harness level with no live upstream provider calls attempted

## Artifacts

- spec: thread-only contour plan for `API_PROVIDER_COMPATIBILITY_AND_SMOKE_MATRIX_R1`
- packet: `audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28/provider_smoke_matrix_packet.json`
- report: `audit_results/api_provider_compatibility_and_smoke_matrix_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; packets contain no raw secrets, the probe uses synthetic prompt text and bounded session-runtime harness responses only, and no session-root artifacts are included in the contour evidence surface

## Notes

- blockers encountered: the first blocker was scope integrity. Existing `model_availability_*` and `provider_adapter_*` contours in the repo provided useful harness patterns, but they closed adjacent truths such as direct availability, fixture semantics, or provider-family classification rather than this contour’s exact current row truth. The contour-local probe therefore rebuilt row classification directly from the current generic model registry, current session manager admission rules, and the prior semantics probe’s reproved limits. The second blocker was matrix breadth: the current server-issued `wbp_api` snapshot only exposes four rows, not the target 8-12, so the contour records the narrower matrix instead of synthesizing rows from historical seed material. The third blocker was a real independent-audit finding: the first probe revision wrote synthetic session artifacts into `audit_results`, and those artifacts inherited `provider_called=true` from generic session-manager persistence semantics even though the contour’s top-level packets explicitly said no live provider calls were attempted. That contradiction was fixed by moving probe session roots into temporary space outside the evidence directory and by adding a focused test that asserts no `probe_session_root` is written into contour evidence. A final independent read-only audit then reported no material issues in the updated scope and confirmed that the remaining limits are honestly classified rather than hidden behind row-pass vanity.
- resume from here: CLOSED
