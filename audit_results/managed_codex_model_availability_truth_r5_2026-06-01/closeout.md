# Managed Codex Model Availability Truth R5 Closeout

## Goal

Classify managed CLIProxyAPI Codex/ChatGPT model availability using strict
JSON evidence from live `/v1/models` and `/v1/responses` probes, without
changing user defaults, UI state, DeepSeek routes, or current-proxy truth.

## Result

- status: pass
- final verdict: MANAGED_CODEX_MODEL_AVAILABILITY_TRUTH_CAPTURED
- closure state: CLOSED

## Contour Capsule

- goal: prove which bounded managed Codex/ChatGPT catalog models are actually
  executable through `/v1/responses` and which are blocked, catalog-only, or
  endpoint-mismatched
- branch: codex/managed-codex-model-availability-r5
- head: 6768397acf57860a043fda66d7ec7cd4c8296df2 before this contour commit
- touched files: audit_results/managed_codex_model_availability_truth_r5_2026-06-01
- tests run: live managed CLIProxyAPI `/v1/models` catalog probe; live managed
  CLIProxyAPI `/v1/responses` per-model matrix probe; independent audit agent;
  secret marker scan; python3 -m py_compile wild_boar_proxy/cli.py
  wild_boar_proxy/runtime.py tests/test_cli.py; python3 -m pytest -q
  tests/test_cli.py -k managed_listener_start; git diff --check; closeout
  resilience check
- blocked risks: route truth for DeepSeek/API-only, ChatGPT plus API role-slot
  orchestration, UI selectors, profile/history, voice input, speed comparison,
  and final E2E remain unclaimed by this contour
- closure state: CLOSED

## Verification

- tests: targeted CLI managed-listener startup tests passed
- build: py_compile passed for the CLI/runtime/test files relevant to managed
  listener startup
- manual: JSON packets were inspected for status buckets, startup probe
  recommendation, route-truth boundaries, and redaction boundaries
- live verification: live managed CLIProxyAPI catalog returned eight bounded
  models; `/v1/responses` classified `gpt-5.4-mini`, `gpt-5.5`, and
  `codex-auto-review` as available, `gpt-5.2`, `gpt-5.3-codex`, and `gpt-5.4`
  as quota-blocked, `gpt-5.3-codex-spark` as catalog-only-not-executable, and
  `gpt-image-2` as wrong-endpoint-for-model

## Artifacts

- spec: thread-only contour definition
- packet: audit_results/managed_codex_model_availability_truth_r5_2026-06-01/summary_packet.json
- report: audit_results/managed_codex_model_availability_truth_r5_2026-06-01/model_availability_classification_packet.json
- independent audit: audit_results/managed_codex_model_availability_truth_r5_2026-06-01/independent_audit_packet.json
- matrix: audit_results/managed_codex_model_availability_truth_r5_2026-06-01/responses_matrix_packet.json
- recommendation: audit_results/managed_codex_model_availability_truth_r5_2026-06-01/startup_probe_recommendation_packet.json

## Git

- branch: codex/managed-codex-model-availability-r5
- commit: contour commit created after this closeout content
- pushed: yes after commit

## Scope Check

- unrelated work mixed in: no; this contour only adds managed Codex/ChatGPT
  model availability evidence and closeout
- private-data risk reviewed: yes; raw API keys, auth tokens, local auth
  filenames, emails, and raw config contents were not recorded

## Notes

- blockers encountered: no live transport blocker remained; quota-blocked,
  catalog-only, and endpoint-mismatched models are classified evidence, not
  contour failures
- resume from here: CLOSED
