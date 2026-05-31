# EXECUTION_CORE_ACCOUNT_RANKING_AND_API_PULL_PASS Closeout

## Goal

Harden the execution-core internals before returning to design work: account selection must use explicit ranking truth, and API route check/validate must pull provider evidence only through eligible enabled routes.

## Result

- status: `closed_success`
- final verdict: runtime account ranking now has an explicit deterministic policy, API disabled routes are blocked before provider network calls, and existing runtime/API/web gates remain green
- next action: continue execution-core product hardening only if new functional gaps appear; otherwise return to web UX/design on top of this stable core

## Contour Capsule

- goal: make account ranking and API provider pull semantics explicit, tested, and command-contract backed
- branch: `codex/external-agent-lab-isolated`
- head: `71f42ba`
- touched files:
  - `COMMAND_API.md`
  - `tests/test_cli.py`
  - `tests/test_cli_external_models.py`
  - `wild_boar_proxy/external_models/errors.py`
  - `wild_boar_proxy/external_models/validate.py`
  - `wild_boar_proxy/runtime.py`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/spec.md`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/metrics.json`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/independent_audit.json`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/closeout.md`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/evidence/targeted-test-results.txt`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/evidence/composite-gate-result.txt`
- tests run:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli.CliTests.test_launch_capable_backend_ids_apply_runtime_ranking_policy tests.test_cli_external_models.ExternalModelsCliTests.test_check_disabled_route_is_blocked_without_provider_call tests.test_cli_external_models.ExternalModelsCliTests.test_validate_disabled_route_is_blocked_without_provider_call -q` -> `Ran 3 tests in 1.023s OK`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_cli_external_models tests.test_external_models -q` -> `Ran 447 tests in 180.706s OK`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> pass
  - `git diff --check` -> pass
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_cli tests.test_cli_external_models tests.test_external_models -q` -> `Ran 595 tests in 200.157s OK`
- blocked risks: no blocking risks remain inside contour scope; true provider OAuth, active-pool promotion policy, and design polish remain separate contours
- next exact command: `python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests:
  - account ranking regression: pass
  - disabled API check network guard: pass
  - disabled API validate network guard: pass
  - runtime/API suite: `Ran 447 tests in 180.706s OK`
  - full required composite suite: `Ran 595 tests in 200.157s OK`
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`: pass
  - `git diff --check`: pass
- manual:
  - reviewed ranking path against lifecycle eligibility gates
  - reviewed API check/validate path to confirm disabled routes block before `_provider_headers` and provider requests
- live verification:
  - not required for this execution-core contour; full web live proof remains covered by `WEB_ACCOUNT_AND_API_CONNECT_E2E_HARDENING_PASS`

## Artifacts

- spec:
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/spec.md`
- packet:
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/evidence/targeted-test-results.txt`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/evidence/composite-gate-result.txt`
- report:
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/metrics.json`
  - `audit_results/execution_core_account_ranking_and_api_pull_pass_2026-05-22/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: not-yet

## Scope Check

- unrelated work mixed in: no; edits stayed inside execution-core ranking, external-models route verification, tests, command contract, and audit artifacts
- private-data risk reviewed: yes; no auth token, API key, or local runtime path evidence was added

## Notes

- blockers encountered:
  - first disabled-route guard placement returned a packet without `route_state`; it was moved into the common error-shaping path and covered by tests
- follow-up contour:
  - return to web UX/design only after this commit is pushed; no new cleanup contour is needed for this task
- resume from here: CLOSED
