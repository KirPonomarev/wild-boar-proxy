# LEGACY_ACCOUNT_POOL_ADOPTION_PASS Closeout

## Contour Capsule
- contour: `LEGACY_ACCOUNT_POOL_ADOPTION_PASS`
- goal: import the legacy account pool into the current proof target, exclude the operator-held identity if present, prove account/ranking/runtime/web truth, and leave API route adoption out of scope.
- outcome: `closed_imported_with_runtime_blocker`
- date: 2026-05-23
- branch: `codex/external-agent-lab-isolated`
- head: `05fb181`
- touched files: `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/external_models/http_client.py`, `tests/test_web_design_live_server.py`, `audit_results/legacy_account_pool_adoption_pass_2026-05-23/*`
- tests run: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; targeted unittest regressions for sandbox readonly routing and loopback provider check; full unittest gate `tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q` with 568 tests OK; `git diff --check`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: live runtime remains non-green because provider attestation fails with `ATTESTATION_FAILED` / `HTTP 401 Invalid API key`; duplicate account_id groups remain explicit imported backend entries, not independent identity claims.
- next exact command: `WBP_PROFILE_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/profile WBP_MANAGED_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed WBP_EXTERNAL_MODELS_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed/external-models /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m wild_boar_proxy status --json`
- resume from here: account pool import is complete; next contour should address API/provider runtime blocker and duplicate-aware health/routing proof, not redo the import.

## Summary
Imported the legacy account pool from `~/.codex-custom-cli` into the current proof target via canonical `legacy import --source-dir ... --json`. The old source directories were used as read-only sources. API routes/secrets were deliberately out of scope.

## Results
- source backend entries: 25
- staged/imported backend entries: 25
- post-import visible accounts: 25
- validation: 25/25 OK
- duplicate warnings: 5
- ranking proof: pass
- launch-capable backend count: 15
- runtime blocker: `ATTESTATION_FAILED` / `external_runtime_attestation_failed_invalid_api_key`

## Operator Exclusion
The exact `ponomarevkirill89@gmail.com` candidate was found only in `removed-auth`, not in the active source registry or active auth file set. Therefore no active backend needed removal from staging.

## Verification
- canonical import packet: `evidence/import/legacy-import.json`
- post-import accounts: `post_import_accounts.json`
- validation proof: `validation_proof.json`
- ranking proof: `ranking_proof.json`
- runtime truth: `runtime_truth_proof.json`
- web readout after handler fix: `evidence/web/web-readout-summary-after-handler-fix.json`

## Notes
A web live-readonly split-brain was found and fixed: sandbox action mode now routes all readonly surfaces through the sandbox runner. This prevents imported accounts from being shown beside default-runtime healthy status.

A loopback provider-check issue was also fixed in `external_models/http_client.py`: local `127.0.0.1` / `localhost` / `::1` provider validations bypass system proxy handlers, so sandbox route proof reaches the intended local mock instead of producing false provider failures.

## Tests
- `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`: pass
- targeted regressions for sandbox readonly routing and packaged loopback provider check: pass
- `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q`: 568 tests OK

## Next
Open `LEGACY_API_ROUTES_AND_PROVIDER_PROOF_PASS` to restore OpenRouter/DeepSeek route and resolve the current `HTTP 401 Invalid API key` live attestation blocker.
