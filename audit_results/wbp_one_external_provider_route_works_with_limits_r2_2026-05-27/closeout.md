<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WBP One External Provider Route Works With Limits R2 Closeout

## Goal

Repair the selected single-provider OpenRouter smoke lane so
`external-models check --route wbp-web-primary-openrouter --json` succeeds
truthfully with the real upstream and record completed evidence for Pass 2 only.

## Result

- status: ok
- final verdict: WBP_ONE_EXTERNAL_PROVIDER_ROUTE_WORKS_WITH_LIMITS_R2 achieved for the selected OpenRouter lane only
- closure state: CLOSED

## Contour Capsule

- goal: raise the bounded smoke-request completion budget in `wild_boar_proxy/external_models/transforms.py` just enough for the selected OpenRouter lane to return truthful text instead of invalid upstream responses, then prove it with focused tests and live packets
- branch: codex/external-agent-lab-isolated
- head: d65b5a42536ef6da4127e544e5dfd1ea753db4f8
- touched files: wild_boar_proxy/external_models/transforms.py; tests/test_cli_external_models.py; tests/test_external_models.py; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/provider_lane_selection_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/credential_status_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/route_validation_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/route_smoke_check_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/response_shape_classification_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/failure_semantics_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/auth_authority_boundary_packet.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/false_green_audit.json; audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/closeout.md
- tests run: python3 -m unittest tests.test_external_models tests.test_cli_external_models; WBP_EXTERNAL_MODELS_DIR="$HOME/.wild-boar-proxy/external-models" WBP_MANAGED_DIR="$HOME/.wild-boar-proxy" python3 -m wild_boar_proxy external-models credentials status --provider openrouter --json; WBP_EXTERNAL_MODELS_DIR="$HOME/.wild-boar-proxy/external-models" WBP_MANAGED_DIR="$HOME/.wild-boar-proxy" python3 -m wild_boar_proxy external-models credentials status --provider deepseek --json; python3 -m wild_boar_proxy external-models routes list --json; WBP_EXTERNAL_MODELS_DIR="$HOME/.wild-boar-proxy/external-models" WBP_MANAGED_DIR="$HOME/.wild-boar-proxy" python3 -m wild_boar_proxy external-models routes validate --json --route wbp-web-primary-openrouter; WBP_EXTERNAL_MODELS_DIR="$HOME/.wild-boar-proxy/external-models" WBP_MANAGED_DIR="$HOME/.wild-boar-proxy" python3 -m wild_boar_proxy external-models check --json --route wbp-web-primary-openrouter; WBP_EXTERNAL_MODELS_DIR="$HOME/.wild-boar-proxy/external-models" WBP_MANAGED_DIR="$HOME/.wild-boar-proxy" python3 -m wild_boar_proxy external-models profile codex-desktop --json --route wbp-web-primary-openrouter; python3 tools/check_closeout_resilience.py audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/closeout.md; JSON parse sweep over audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27; git diff --check
- blocked risks: the runtime fix used a shared smoke completion budget helper across request shapes, so the code change was broader than a route-id-specific branch; only the selected OpenRouter lane is live-proven here, auth stayed on `OPENROUTER_API_KEY`, and non-selected providers remain unproven and blocked
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_external_models tests.test_cli_external_models` ran `41 tests in 9.470s` and returned `OK`
- build: no separate build step was required for this bounded runtime repair
- manual: code inspection confirmed the runtime behavior change was a shared smoke-request completion budget helper in `wild_boar_proxy/external_models/transforms.py`, not a route-id-specific branch
- live verification: selected OpenRouter credentials were `present`, DeepSeek credentials were `missing`, route validation remained `ok/model_visible`, route smoke check became `ok/verified`, and `profile codex-desktop` remained non-mutating with `api_key_source=managed_local_token`; this live proof covers only the selected OpenRouter lane, while non-selected providers remain unproven and blocked

## Artifacts

- spec: thread-only operator instruction, not stored in repo
- packet: provider_lane_selection_packet.json; credential_status_packet.json; route_validation_packet.json; route_smoke_check_packet.json; response_shape_classification_packet.json; failure_semantics_packet.json; auth_authority_boundary_packet.json; false_green_audit.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: d65b5a42536ef6da4127e544e5dfd1ea753db4f8
- pushed: already pushed to origin

## Scope Check

- unrelated work mixed in: no; writes stayed inside `wild_boar_proxy/external_models/transforms.py`, the owned external-model test files, and `audit_results/wbp_one_external_provider_route_works_with_limits_r2_2026-05-27/*`
- private-data risk reviewed: yes; packets record credential presence and route evidence only, with no secret values

## Notes

- blockers encountered: none after the narrow budget fix; the pre-fix failure semantics were limited to too-small completion budgets on the selected OpenRouter lane
- resume from here: CLOSED
