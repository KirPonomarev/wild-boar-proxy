# DEEPSEEK_DIRECT_API_MINIMAL_TOKEN_PROOF_PASS Closeout

## Goal

Prove that the sandbox-scoped DeepSeek direct route is configured correctly,
passes canonical route smoke truth, and stays aligned with web readonly truth
without leaking secrets or overstating runtime readiness.

## Result

- status: `closed_success`
- final verdict: `external-models check --route wbp-deepseek-v3 --json` passed,
  one direct provider probe passed, and `routes validate` returned
  `model_not_available` as a bounded alias/model-visibility limitation rather
  than a route-break contradiction
- next action: proceed to `WEB_FUNCTIONAL_MENU_WIRING_PASS`

## Contour Capsule

- goal: direct DeepSeek route proof with minimal token burn and truthful web
  alignment
- branch: `codex/external-agent-lab-isolated`
- head: `14327d5`
- touched files:
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/spec.md`
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/baseline.json`
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/proof.json`
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/metrics.json`
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/redaction_audit.json`
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/independent_audit.json`
  - `audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/closeout.md`
- tests run:
  - `python3 -B -m unittest tests.test_cli_external_models.ExternalModelsCliTests.test_deepseek_credentials_admit_and_status_use_direct_provider_refs tests.test_cli_external_models.ExternalModelsCliTests.test_route_validate_model_unavailable_updates_route_state tests.test_cli_external_models.ExternalModelsCliTests.test_check_success_writes_verified_state_and_evidence tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_connections_readonly_projects_observed_route_check_state tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_connections_readonly_downgrades_route_when_provider_validation_failed tests.test_web_design_live_server.WebDesignLiveServerTests.test_api_connections_readonly_requires_matching_secret_ref -q`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- blocked risks:
  - default `external-models` lane is empty while the live web uses a sandbox
    launch-copy lane; this is scoped separation, not split-brain
  - `routes validate` returns `model_not_available`; classified as
    `DEEPSEEK_MODELS_ALIAS_LIMITATION` because route smoke and one direct
    provider probe both succeeded
- next exact command:
  - `curl -sS http://127.0.0.1:8788/api/actions`

## Verification

- tests:
  - targeted external-models and web readonly tests passed (`6` tests)
- build:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- manual:
  - compared default lane, sandbox lane, and web readonly lane
  - verified post-check and post-validate web snapshots
- live verification:
  - sandbox `external-models check --route wbp-deepseek-v3 --json`: passed
  - sandbox `external-models routes validate --route wbp-deepseek-v3 --json`:
    `model_not_available`
  - one direct provider probe: `HTTP 200`

## Artifacts

- spec:
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/spec.md`
- packet:
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/baseline.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/proof.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/metrics.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/redaction_audit.json`
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/independent_audit.json`
- report:
  - `/Volumes/Work/wild-boar-proxy/audit_results/deepseek_direct_api_minimal_token_proof_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `d391d91` (packet), `14327d5` (closeout)
- pushed: `no`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes`; scans found no raw provider key material

## Notes

- blockers encountered:
  - initial default-lane packets were empty; localized to sandbox-scoped
    `WBP_EXTERNAL_MODELS_DIR` injected by the web launch-copy environment
  - `routes validate` returned `model_not_available` while route smoke passed;
    bounded by direct provider probe and classified as alias limitation
- follow-up contour:
  - `WEB_FUNCTIONAL_MENU_WIRING_PASS`
- resume from here: `WEB_FUNCTIONAL_MENU_WIRING_PASS`
