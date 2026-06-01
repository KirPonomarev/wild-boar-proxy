# API-Only Route Truth R7 Closeout

## Goal

Prove API-only route truth with strict command and evidence packets: the
declared mode is `api_only`, DeepSeek/API is the executed provider/model,
ChatGPT is absent, fallback is false, and no UI, dual-role, profile/history, or
final E2E claim is made.

## Result

- status: pass
- final verdict: API_ONLY_ROUTE_TRUTH_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: capture fresh API-only DeepSeek route truth and add explicit route-truth
  fields to the provider-only external-models packet surface
- branch: codex/api-only-route-truth-r7
- head: 0ca70834ad07d94debda77e93b436a19ee561e6e before this contour commit
- touched files: COMMAND_API.md, wild_boar_proxy/external_models/validate.py,
  tests/test_cli_external_models.py, audit_results/api_only_route_truth_r7_2026-06-01
- tests run: python3 -m py_compile wild_boar_proxy/external_models/validate.py
  wild_boar_proxy/codex_model_registry.py tests/test_cli_external_models.py
  tests/test_codex_model_registry.py; python3 -m pytest -q
  tests/test_cli_external_models.py -k 'check_success or live_format_check';
  python3 -m pytest -q tests/test_cli_external_models.py
  tests/test_codex_model_registry.py; live external-models live-format-check
  DeepSeek proof; secret marker scan; independent audit agent; git diff
  --check; closeout resilience check
- blocked risks: ChatGPT-only route truth, ChatGPT plus API role split,
  coding_agent_model_slot, live coding proof-file mutation, profile/history,
  Quick Start UI, voice input, speed comparison, and final E2E remain unclaimed
- closure state: CLOSED

## Verification

- tests: targeted external-models route checks passed, then
  tests/test_cli_external_models.py and tests/test_codex_model_registry.py passed
  with 69 tests
- build: py_compile passed for the touched route-truth code and related tests
- manual: route truth packets were inspected for declared_mode,
  executed_provider, executed_model, chatgpt_invoked, fallback_used,
  request_count, retry_count, and no-write fields
- live verification: external-models live-format-check called the DeepSeek
  route once with zero retries, observed expected text, recorded
  executed_provider=deepseek and executed_model=deepseek-v4-flash, and reported
  chatgpt_invoked=false, fallback_used=false, state_written=false,
  evidence_written=false, and file_mutation_attempted=false

## Artifacts

- spec: thread-only contour definition
- packet: audit_results/api_only_route_truth_r7_2026-06-01/summary_packet.json
- route truth: audit_results/api_only_route_truth_r7_2026-06-01/api_only_route_truth_packet.json
- live command: audit_results/api_only_route_truth_r7_2026-06-01/live_format_command_packet.json
- independent audit: audit_results/api_only_route_truth_r7_2026-06-01/independent_audit_packet.json

## Git

- branch: codex/api-only-route-truth-r7
- commit: contour commit created after this closeout content
- pushed: yes after commit

## Scope Check

- unrelated work mixed in: no; this contour only touched API-only route truth
  fields, their command contract, tests, and R7 evidence
- private-data risk reviewed: yes; raw API keys, auth tokens, local auth
  filenames, emails, raw config contents, and raw route secret refs were not
  recorded

## Notes

- blockers encountered: the first live aggregation run classified a selector
  gate blocker because the temporary API snapshot omitted a redacted
  secret-ref-presence marker; rerun kept the secret redacted while preserving
  server-issued route truth and closed the contour
- resume from here: CLOSED
