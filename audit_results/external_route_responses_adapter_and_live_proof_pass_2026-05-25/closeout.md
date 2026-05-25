# External Route Responses Adapter And Live Proof Closeout

## Goal

Repair the route-backed external API path for `Codex Custom` by inserting a
bounded local `responses` adapter between Codex and the server-owned external
route, then prove one real external live prompt through the WBP web path.

## Result

- status: completed
- final verdict: external route adapter slice closed; full `8B` not upgraded in this closeout
- closure state: CLOSED

## Contour Capsule

- goal: close the route-backed external prompt gap after credential admission by translating Codex `responses` traffic into provider `chat/completions` traffic and proving one live external prompt through the WBP web path
- branch: `codex/external-agent-lab-isolated`
- head: `ef2d23acdf3ee4034a6f147061686f40cc748c1c`
- touched files:
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/codex_model_registry.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/codex_custom_sessions.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/operator_surface.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/web_design_live_server.py`
  - `/Volumes/Work/wild-boar-proxy/tests/test_codex_custom_sessions.py`
  - `/Volumes/Work/wild-boar-proxy/tests/test_operator_surface.py`
  - `/Volumes/Work/wild-boar-proxy/tests/test_web_design_live_server.py`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/spec.md`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/models_packet.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/launch_packet.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/prompt_packet.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/live_proof_summary.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/verification_summary.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/independent_audit_report.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/closeout.md`
- tests run:
  - `PYTHONPATH=/Volumes/Work/wild-boar-proxy /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile /Volumes/Work/wild-boar-proxy/wild_boar_proxy/operator_surface.py /Volumes/Work/wild-boar-proxy/tests/test_operator_surface.py /Volumes/Work/wild-boar-proxy/tests/test_codex_custom_sessions.py`
  - `PYTHONPATH=/Volumes/Work/wild-boar-proxy /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_operator_surface.OperatorSurfaceTests.test_external_route_responses_adapter_translates_responses_to_chat_completions tests.test_operator_surface.OperatorSurfaceTests.test_external_route_responses_adapter_streams_response_completed_for_streaming_clients tests.test_operator_surface.OperatorSurfaceTests.test_run_prompt_route_backed_external_model_uses_route_upstream_model_and_secret tests.test_codex_custom_sessions.CodexCustomSessionManagerTests.test_route_backed_session_with_route_provenance_can_satisfy_full_success`
  - `PYTHONPATH=/Volumes/Work/wild-boar-proxy /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -q tests.test_operator_surface tests.test_codex_custom_sessions tests.test_web_design_live_server`
  - `git -C /Volumes/Work/wild-boar-proxy diff --check`
- blocked risks:
  - full `8B` remains broader than this slice because screenshot and recovery acceptance boundaries are not re-closed here
- closure state: CLOSED

## Verification

- tests:
  - `Ran 149 tests in 33.239s OK`
- build:
  - `py_compile: OK`
  - `git diff --check: OK`
- manual:
  - direct `codex exec` debug against the local adapter proved stream-mode parsing and localized the missing `usage` fields before final live success
- live verification:
  - `/api/codex/custom/models` includes `wbp-web-primary-openrouter`
  - `/api/codex/custom/launch` returns `running_status=true` with `selected_source_class=route_backed`
  - `/api/codex/custom/sessions/<id>/prompt` returns `status=ok`, `machine_error_code=OK`, `live_prompt_full_success=true`, `wbp_path_proven=true`, `current_codex_touched=false`

## Artifacts

- spec:
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/spec.md`
- packet:
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/live_proof_summary.json`
- report:
  - `/Volumes/Work/wild-boar-proxy/audit_results/external_route_responses_adapter_and_live_proof_pass_2026-05-25/evidence/independent_audit_report.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `not created at artifact authoring time`
- pushed: `no`

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; owner secret admitted into sandbox-managed secrets store only, no secret value written to artifacts

## Notes

- blockers encountered:
  - initial route-backed path still configured `wire_api = "chat_completions"` and failed client-side
  - first adapter revision returned non-streaming JSON, which Codex rejected because it expected `response.completed`
  - second adapter revision streamed `response.completed` but omitted normalized `usage.input_tokens` and `usage.output_tokens`
- resume from here: CLOSED
