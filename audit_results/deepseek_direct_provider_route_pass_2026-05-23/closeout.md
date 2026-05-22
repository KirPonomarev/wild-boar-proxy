# DEEPSEEK_DIRECT_PROVIDER_ROUTE_PASS Closeout

## Contour Capsule
- contour: `DEEPSEEK_DIRECT_PROVIDER_ROUTE_PASS`
- goal: add direct DeepSeek provider support, migrate the mistakenly admitted OpenRouter ref to `DEEPSEEK_API_KEY`, replace the wrong OpenRouter route, and prove route/provider truth without secret exposure.
- outcome: `closed_direct_lane_added_provider_auth_failed`
- date: 2026-05-23
- branch: `codex/external-agent-lab-isolated`
- head: `5bd4ae6`
- touched files: `wild_boar_proxy/external_models/credentials.py`, `tests/test_cli_external_models.py`, `audit_results/deepseek_direct_provider_route_pass_2026-05-23/*`
- tests run: targeted DeepSeek/OpenRouter credential tests with 2 tests OK; `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`; `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli_external_models tests.test_external_models tests.test_web_design_command_adapter -q` with 62 tests OK; `git diff --check`; `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks: DeepSeek direct upstream returns `provider_auth_failed`; route must remain non-green until a valid DeepSeek credential/access is provided.
- next exact command: `WBP_PROFILE_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/profile WBP_MANAGED_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed WBP_EXTERNAL_MODELS_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed/external-models /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m wild_boar_proxy external-models check --route wbp-deepseek-v3 --json`
- resume from here: provide a valid DeepSeek direct key owner-side, then rerun route validate/check and web API readonly proof.

## Summary
Direct DeepSeek provider support is implemented. The sandbox secret ref was migrated to `DEEPSEEK_API_KEY` without copying the secret into artifacts. The old OpenRouter route was disabled/removed and replaced by `provider=deepseek`, `base_url=https://api.deepseek.com`, `upstream_model=deepseek-chat`.

## Result
DeepSeek provider validate/check currently return `provider_auth_failed`. Web reflects this honestly with a red `validate failed` state. No route connected claim was made.
