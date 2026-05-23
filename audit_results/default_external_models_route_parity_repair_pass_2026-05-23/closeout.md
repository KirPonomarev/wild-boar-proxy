# DEFAULT_EXTERNAL_MODELS_ROUTE_PARITY_REPAIR_PASS Closeout

## Goal

Resolve the `route_not_found` blocker for `wbp-deepseek-v3` by selecting and proving the canonical external-models target for the next isolated Codex engine harness.

## Result

- status: `closed_success_sandbox_canonical_target_selected`
- final verdict: sandbox/web external-models lane selected as canonical for the next engine harness; selected lane `external-models check --route wbp-deepseek-v3 --json` returned `OK`; default lane remains honestly reported as `route_not_found` and must not be used silently by the next harness.
- next action: run `ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS_WITH_REAL_WBP_HARNESS_RETRY` with explicit sandbox env.

## Contour Capsule

- goal: repair external-models target split without Codex smoke, UI work, GUI work, or secret copy
- branch: `codex/external-agent-lab-isolated`
- head: `05ad17a`
- touched files: `audit_results/default_external_models_route_parity_repair_pass_2026-05-23/*`
- tests run: default/sandbox external-models route/status/credential/check packets; web api-connections readonly; JSON validation; redaction scan; git diff --check; closeout resilience gate
- blocked risks: false-green default route claim; secret copying; mixing route repair with Codex engine smoke
- next exact command: `WBP_PROFILE_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/profile WBP_MANAGED_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed WBP_EXTERNAL_MODELS_DIR=/private/var/folders/qq/p9w353w13lqb3n8vdv_lf2f80000gn/T/wbp_codex_login_live_tz983sfx/managed/external-models python3 -m wild_boar_proxy external-models check --route wbp-deepseek-v3 --json`

## Verification

- tests: JSON validation passed; redaction scan passed; git diff --check passed; closeout resilience gate passed after staging
- build: no production code changed
- manual: machine packets captured live
- live verification: sandbox_check_ok=True; default_route_not_found=True; web_packet_status=ok; web route `wbp-deepseek-v3` shown with validation `ok`

## Artifacts

- spec: `audit_results/default_external_models_route_parity_repair_pass_2026-05-23/spec.md`
- packet: `audit_results/default_external_models_route_parity_repair_pass_2026-05-23/proof.json`
- web proof: `audit_results/default_external_models_route_parity_repair_pass_2026-05-23/web_readonly_proof.json`
- report: `audit_results/default_external_models_route_parity_repair_pass_2026-05-23/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending-current-contour-commit
- pushed: pending-current-contour-push

## Scope Check

- unrelated work mixed in: false
- private-data risk reviewed: true; no raw secret material intentionally serialized; redaction audit status `pass`

## Notes

- blockers encountered: subagent spawn failed with `agent thread limit reached`; default lane returned `route_not_found`
- follow-up contour: `ISOLATED_CODEX_ENGINE_WORK_SESSION_PASS_WITH_REAL_WBP_HARNESS_RETRY`
- resume from here: use explicit sandbox env for external-models preflight; do not use default external-models lane for this harness
