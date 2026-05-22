# LEGACY_API_ROUTES_AND_PROVIDER_PROOF_PASS Closeout

## Contour Capsule
- contour: `LEGACY_API_ROUTES_AND_PROVIDER_PROOF_PASS`
- goal: prove the OpenRouter/DeepSeek owner credential and provider route path after account pool adoption, without browser secret intake or false-green route claims.
- outcome: `closed_blocked_waiting_for_valid_provider_key`
- date: 2026-05-23
- branch: `codex/external-agent-lab-isolated`
- head: `2384af9`
- touched files: `audit_results/legacy_api_routes_and_provider_proof_pass_2026-05-23/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli_external_models tests.test_external_models tests.test_web_design_live_server tests.test_web_design_command_adapter -q` with 132 tests OK; full gate `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_cli_external_models tests.test_external_models tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q` with 606 tests OK; `git diff --check`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: owner env has no `OPENROUTER_API_KEY`, `WBP_OPENROUTER_API_KEY`, or `WBP_PROVIDER_OPENROUTER_API_KEY`; provider route add/check is blocked to avoid false connected state.
- next exact command: `WBP_PROFILE_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/profile WBP_MANAGED_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed WBP_EXTERNAL_MODELS_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed/external-models /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m wild_boar_proxy external-models credentials admit --provider openrouter --source owner-env --json`
- resume from here: set a valid owner-side OpenRouter credential in the owner process environment, then rerun credential admit, route add/adopt, route validate, provider check, API readonly refresh, and runtime post-check.

## Summary
The contour reached the correct blocker without mutating routes or leaking secrets. Current external-models state has no OpenRouter credential and no routes. Web `api_route_connect` returns a non-green missing-credential result and API Connections remains at zero routes.

## Evidence
- baseline external-models: `baseline_external_models.json`
- credential diagnosis: `credential_diagnosis.json`
- credential admission proof: `credential_admission_proof.json`
- web readout proof: `web_readout_proof.json`
- account regression: `account_pool_regression.json`
- redaction audit: `redaction_audit.json`
- metrics: `metrics.json`
- independent audit: `independent_audit.json`

## Result
- credential status: `missing`
- credential admit: `EXTERNAL_MODELS_CREDENTIAL_SOURCE_MISSING`
- routes count: `0`
- route restore: not attempted
- provider check: not run
- web API action: `command_error`
- account pool regression: `25` visible accounts
- secret exposure: false

## Next
Do not paste the API key into chat or browser. Make the credential available owner-side, then resume from the exact command in the Contour Capsule.
