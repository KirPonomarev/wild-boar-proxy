<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom-Origin-Bound Live Provider Join Closeout

## Goal

Join the already proven real Custom Codex prompt origin and
Custom-origin-bound API dispatch packet to a live provider response packet from
`external-models live-format-check`, while preserving fail-closed route
binding, prompt digest binding, and no raw prompt, route, expected-text, or
provider-response leakage.

## Result

- status: CLOSED
- final verdict: CUSTOM_ORIGIN_BOUND_LIVE_PROVIDER_JOIN_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: real Custom Codex UI prompt ledger to Custom-origin-bound dispatch to live provider response digest, without handoff, UI visibility, native-router, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: d47145df pre-closeout base; closure commit contains the scoped proof, tests, and this evidence
- touched files: wild_boar_proxy/controlled_api_dispatch.py; wild_boar_proxy/custom_origin_bound_api_dispatch_proof.py; wild_boar_proxy/custom_origin_bound_live_provider_join.py; wild_boar_proxy/cli.py; tests/test_controlled_api_dispatch.py; tests/test_custom_origin_bound_live_provider_join.py; audit_results/custom_origin_bound_live_provider_join_closeout_2026-06-18.md
- tests run: python3 -m py_compile wild_boar_proxy/custom_origin_bound_live_provider_join.py wild_boar_proxy/custom_origin_bound_api_dispatch_proof.py wild_boar_proxy/cli.py; python3 -m unittest tests.test_custom_origin_bound_live_provider_join tests.test_custom_origin_bound_api_dispatch_proof; python3 -m py_compile wild_boar_proxy/controlled_api_dispatch.py wild_boar_proxy/custom_origin_bound_live_provider_join.py; python3 -m unittest tests.test_controlled_api_dispatch tests.test_real_ledger_bound_api_dispatch_proof tests.test_custom_origin_bound_api_dispatch_proof tests.test_custom_origin_bound_live_provider_join; python3 -m unittest tests.test_controlled_api_dispatch tests.test_real_ledger_bound_api_dispatch_proof tests.test_custom_origin_bound_api_dispatch_proof tests.test_custom_origin_bound_live_provider_join tests.test_real_custom_codex_hook_proof tests.test_codex_working_flow_delivery_proof; make test-core; python3 -m unittest tests.test_cli tests.test_cli_external_models; git diff --check
- blocked risks: digest false green from redacted route placeholder; live provider route mismatch; route outside runtime allowlist; missing dispatch route digest; provider fallback; provider response preview mismatch; raw prompt, raw route, expected text, raw provider response, backend detail, or secret exposure; product, UI visibility, handoff, or native-router overclaim
- closure state: CLOSED

## Verification

- tests: focused Custom-origin/live-provider tests passed with 19 tests
- tests: controlled dispatch, ledger-bound dispatch, Custom-origin dispatch, and live-provider join tests passed with 38 tests
- tests: broader proof stack passed with 67 tests
- build: `make test-core` passed with 418 tests and 120 subtests
- build: CLI and external-models unittest suite passed with 528 tests
- build: `git diff --check` completed without output
- manual: live `external-models live-format-check` packet at `/tmp/wbp-custom-origin-live-provider-check.json` returned `status=ok`, `machine_error_code=OK`, `expected_text_observed=true`, `network_dependent=true`, and `changed_files=[]`
- manual: live Custom-origin-bound dispatch packet at `/tmp/wbp-custom-origin-bound-dispatch-proof-current.json` returned `status=ok`, `machine_error_code=OK`, `custom_origin_bound=true`, `dispatch_proven=true`, and a present `selected_api_route_id_sha256`
- live verification: `/tmp/wbp-custom-origin-bound-live-provider-join-proof.json` returned `status=ok`, `machine_error_code=OK`, `custom_origin_bound_dispatch_proven=true`, `same_prompt_digest=true`, `same_allowed_route_binding=true`, `allowed_api_route_ids_enforced=true`, `api_lane_called=true`, `live_provider_called=true`, `live_provider_response_proven=true`, `external_live_provider_response_proven=true`, `response_digest_bound=true`, `fallback_used=false`, `local_imitation_used=false`, `native_codex_subagent_used_as_dip=false`, `product_ready=false`, and `custom_codex_ui_visibility_proven=false`
- audit: independent read-only audit found no blocking issues and confirmed the route digest fix does not output raw route ids

## Artifacts

- packet: `wbp_custom_origin_bound_live_provider_join`
- packet: `/tmp/wbp-custom-origin-bound-live-provider-join-proof.json`
- packet: `/tmp/wbp-custom-origin-bound-dispatch-proof-current.json`
- packet: `/tmp/wbp-custom-origin-live-provider-check.json`
- report: this closeout

## Evidence Summary

- command surface: `router-hook custom-origin-bound-live-provider-join --json`
- effect: probe
- changed_files: []
- proof_scope: `custom_origin_bound_dispatch_to_live_provider_response`
- route authority: runtime context allowlist plus matching dispatch route digest and live provider requested route digest
- prompt authority: same digest as the Custom-origin-bound dispatch packet
- provider authority: file-backed `external-models live-format-check` packet with exact expected marker observed
- raw prompt recorded: false
- raw route id recorded: false
- selected route id recorded: false
- expected text recorded: false
- raw provider response recorded: false
- provider response preview recorded: false
- backend details exposed: false
- secret value exposed: false
- handoff proven: false
- Custom Codex UI visibility proven: false
- native free-chat router proven: false
- product ready: false

## Negative Coverage

- prompt digest mismatch blocks the join
- dispatch packet without route digest blocks the join
- live provider requested route mismatch blocks the join
- selected route outside runtime allowlist blocks the join
- expected text not observed blocks the join
- response preview mismatch blocks the join
- provider fallback blocks the join
- raw provider response overclaim blocks the join
- redacted route placeholder no longer becomes the selected route digest

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped proof changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed unstaged and untouched
- UI/product work mixed in: no
- handoff or Custom Codex visibility work mixed in: no
- private-data risk reviewed: yes; final packets use hashes and booleans, and leak checks confirmed the raw Custom prompt, expected marker, raw route id, and live provider preview were absent

## Notes

- blockers encountered: the first live join failed because route digest was computed from the redacted placeholder in the controlled dispatch path; the route source is now recovered internally before redaction while the emitted packets still omit raw route ids
- residual risk: this contour proves Custom-origin-bound dispatch joined to live provider response, not handoff into the Codex working flow, rendered UI visibility, native free-chat product routing, or product readiness
- resume from here: CLOSED
