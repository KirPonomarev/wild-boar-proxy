<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom-Origin-Bound Working Flow Delivery Closeout

## Goal

Allow the Codex working-flow delivery verifier to consume the file-backed
`wbp_custom_origin_bound_live_provider_join` packet and prove:

`Custom-origin-bound dispatch -> live provider response digest -> sanitized approved handoff payload -> Codex working-flow delivery`

without claiming Custom Codex UI visibility, native free-chat product readiness,
or product readiness.

## Result

- status: CLOSED
- final verdict: CUSTOM_ORIGIN_BOUND_WORKING_FLOW_DELIVERY_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: bind the existing Custom-origin-bound live-provider join packet to approved Codex working-flow delivery while preserving fail-closed digest checks and no UI/product overclaim
- branch: codex/stabilize-runtime-core
- head: f1d063ef pre-closeout base; closure commit contains the scoped verifier adapter, tests, and this evidence
- touched files: wild_boar_proxy/codex_working_flow_delivery_proof.py; tests/test_custom_origin_bound_working_flow_delivery_proof.py; audit_results/custom_origin_bound_working_flow_delivery_closeout_2026-06-18.md
- tests run: python3 -m py_compile wild_boar_proxy/codex_working_flow_delivery_proof.py tests/test_custom_origin_bound_working_flow_delivery_proof.py; python3 -m unittest tests.test_custom_origin_bound_working_flow_delivery_proof tests.test_codex_working_flow_delivery_proof tests.test_custom_origin_bound_live_provider_join; python3 -m unittest tests.test_controlled_api_dispatch tests.test_real_ledger_bound_api_dispatch_proof tests.test_custom_origin_bound_api_dispatch_proof tests.test_custom_origin_bound_live_provider_join tests.test_custom_origin_bound_working_flow_delivery_proof tests.test_codex_working_flow_delivery_proof tests.test_real_custom_codex_hook_proof tests.test_codex_exec_assistant_continuation_proof tests.test_codex_transcript_delivery_observation; make test-core; python3 -m unittest tests.test_cli tests.test_cli_external_models; git diff --check
- blocked risks: source packet kind spoofing; source gate false-green; missing route, response, prompt, or CLI digests; unfile-backed proof input; source product/UI overclaim; assistant handoff digest mismatch; raw prompt, raw route, expected marker, raw provider response, backend detail, or secret exposure; native Codex subagent-as-DIP; fallback or local imitation
- closure state: CLOSED

## Verification

- tests: focused Custom-origin working-flow, existing working-flow, and live-provider join suite passed with 31 tests
- tests: broader proof stack passed with 89 tests
- build: `make test-core` passed with 418 tests and 120 subtests
- build: CLI and external-models unittest suite passed with 528 tests
- build: `git diff --check` completed without output
- live verification: `/tmp/wbp-custom-origin-bound-working-flow-delivery-proof.json` returned `status=ok`, `machine_error_code=OK`, `packet_kind=wbp_codex_working_flow_delivery_proof`, `custom_origin_bound_dispatch_proven=true`, `live_provider_response_proven=true`, `approved_handoff_derived_from_custom_origin_live_provider_join=true`, `live_provider_response_digest_bound_to_handoff=true`, `codex_working_flow_delivery_proven=true`, `custom_codex_ui_visibility_proven=false`, `product_ready=false`, and `blocking_reasons=[]`
- audit: independent read-only audit found no blockers; it confirmed the old `real_custom_codex_hook_proof` path remained separate and green, and noted that additional gate/digest negatives were useful; those tests were added and passed

## Artifacts

- packet: `wbp_codex_working_flow_delivery_proof`
- packet: `/tmp/wbp-custom-origin-bound-working-flow-delivery-proof.json`
- packet: `/tmp/wbp-custom-origin-bound-live-provider-join-proof.json`
- packet: `/tmp/wbp-custom-origin-bound-working-flow-events.jsonl`
- report: this closeout

## Evidence Summary

- command surface: `router-hook working-flow-delivery-proof --json`
- effect: probe
- changed_files: []
- source packet accepted: `wbp_custom_origin_bound_live_provider_join`
- legacy source path retained: `wbp_real_custom_codex_hook_proof`
- source authority: file-backed integrated live-provider proof metadata required
- delivery authority: digest-bound MCP tool result plus assistant continuation marker
- handoff payload authority: sanitized payload built from source digest fields
- live provider response digest bound to handoff: true
- controlled provider response digest bound to handoff: true
- Codex working-flow delivery proven: true
- Custom Codex UI visibility proven: false
- native free-chat router proven: false
- product ready: false
- raw prompt recorded: false
- raw route id recorded: false
- selected route id recorded: false
- expected text recorded in final packet: false
- raw provider response recorded: false
- provider response preview recorded: false
- backend details exposed: false
- secret value exposed: false

## Negative Coverage

- missing file-backed metadata blocks working-flow proof
- source `product_ready=true` overclaim blocks before proof
- missing required Custom-origin source gates block before proof
- missing required prompt, route, controlled-provider, or live-provider digests block before proof
- assistant handoff digest mismatch blocks working-flow delivery
- existing verifier negatives still block invalid JSONL, unbound command execution, unbound assistant response, transcript digest mismatch, unsafe subagent-as-DIP, and transcript secret exposure

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped verifier/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed unstaged and untouched
- UI/product work mixed in: no
- private-data risk reviewed: yes; final packets use hashes and booleans, and tests confirmed the raw Custom prompt, route id, expected marker, and raw provider text were absent from output

## Notes

- blockers encountered: none after the initial test import fix
- residual risk: this contour proves digest-bound working-flow delivery through an approved handoff path; it does not prove rendered Custom Codex UI visibility, native free-chat router product readiness, or product readiness
- resume from here: CLOSED
