# CUSTOM_CODEX_KEYCHAIN_PREFLIGHT_LIVE_VALIDATION_R2 Closeout

## Goal

Verify on the real Custom Codex product launch path that the integrated isolated-home keychain preflight avoids the specific macOS keychain-not-found prompt on this host without widening the claim into auth proof or universal compatibility.

## Result

- status: ok
- final verdict: `CUSTOM_CODEX_KEYCHAIN_NOT_FOUND_PROMPT_AVOIDED_ON_THIS_HOST_VIA_PRODUCT_PATH`
- closure state: CLOSED

## Contour Capsule

- goal: validate the real Custom native launch product path on current code, align packet truth with machine prompt observation, and keep the final claim host-local and non-auth
- branch: `codex/external-agent-lab-isolated`
- head: `4d22360a`
- touched files: `audit_results/custom_codex_keychain_preflight_live_validation_r2_2026-05-28/*`
- tests run: `curl -sS http://127.0.0.1:8791/api/actions`; `curl -sS -H 'Content-Type: application/json' -d '{\"ui_action\":\"launch_custom_client_native\"}' http://127.0.0.1:8791/api/action`; `osascript` SecurityAgent polling over 40 samples during the fresh product-path run; `security default-keychain -d user` before and after the product-path run; temp-process cleanup for `/tmp/wbp-native-window-live-*`; `python3 tools/check_closeout_resilience.py audit_results/custom_codex_keychain_preflight_live_validation_r2_2026-05-28/closeout.md`; JSON parse sweep; `git diff --check`
- blocked risks: owner observation was not captured in this contour; older long-running live servers on `127.0.0.1:8788` and `127.0.0.1:8790` were stale in memory and could not be used as current-code validation surfaces
- closure state: CLOSED

## Verification

- tests: fresh product-path action on `127.0.0.1:8791` returned `status=ok`, `result.status=ok`, `keychain_preflight_status=ok`, `isolated_default_keychain_verified=true`, `isolated_search_list_verified=true`, `real_codex_app_launched=true`
- build: no product code changes in this contour; `git diff --check` passed
- manual: none required for closure; owner observation was invited but not needed because machine polling stayed empty
- live verification: machine `SecurityAgent` polling over 40 samples observed zero windows; `security default-keychain -d user` was unchanged before/after; temp `/tmp/wbp-native-window-live-*` processes were cleaned up after validation

## Artifacts

- spec: thread-only contour `CUSTOM_CODEX_KEYCHAIN_PREFLIGHT_LIVE_VALIDATION_R2`
- packet: `audit_results/custom_codex_keychain_preflight_live_validation_r2_2026-05-28/*.json`
- report: `audit_results/custom_codex_keychain_preflight_live_validation_r2_2026-05-28/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit set: this closeout is intended to travel only inside the logically complete contour commit set
- push state: contour is closed only together with the pushed branch state that carries this closeout

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; real keychain path was not widened beyond the standard local default-keychain check, no secrets were read, and no hidden owner action was performed

## Notes

- blockers encountered: initial live validation on older long-running servers showed a contradiction between packet truth and prompt observation; localization proved those servers were stale in memory and lacked the integrated `keychain_preflight_*` fields, so the final validation was rerun on a fresh current-code server at `127.0.0.1:8791`
- resume from here: CLOSED
