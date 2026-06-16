<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Approved Handoff Proof v1 Closeout

## Goal

Add a minimal WBP-owned approved handoff proof that accepts a proven controlled
API dispatch packet, validates canonical route/request/provider digests and
truth-source fields, enforces an approved handoff surface allowlist, and emits a
sanitized strict JSON packet showing handoff readiness.

This contour does not claim handoff delivery, live provider access, observed
Custom Codex origin, native free-chat interception, UI readiness, or product
readiness.

## Result

- status: CLOSED
- final verdict: APPROVED_HANDOFF_PROOF_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: controlled dispatch proof to sanitized approved handoff readiness packet without live-provider, native-free-chat, observed-origin, delivery, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: 0a480b4e
- touched files: wild_boar_proxy/approved_handoff.py; wild_boar_proxy/cli.py; tests/test_approved_handoff.py; audit_results/approved_handoff_proof_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_approved_handoff.py -q; python3 -m compileall -q wild_boar_proxy tests/test_approved_handoff.py; python3 -m pytest tests/test_approved_handoff.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py -q; python3 -m pytest tests/test_owner_surface_effect_inventory.py tests/test_approved_handoff.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py -q; python3 -m pytest tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; git diff --check; make test-core
- blocked risks: independent audit found missing canonical digest and truth-source validation; fixed with route/request/provider digest checks, provider digest binding, controlled provider response recomputation, selected route presence, request sent, and truth-source guards
- closure state: CLOSED

## Verification

- tests: approved handoff focused tests passed with 11 tests and 24 subtests
- tests: targeted handoff, controlled dispatch, hook entry, natural intent, MCP delegate, official MCP admission, and command packet suite passed with 187 tests and 117 subtests
- tests: owner surface effect inventory plus handoff/dispatch/hook tests passed with 58 tests and 72 subtests
- tests: CLI effect classifier targeted case passed with 1 test and 59 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output
- audit: Parfit read-only code review found a high digest/truth-source validation gap and a medium missing-test gap; both were fixed and rechecked as findings none
- audit: Kuhn contract/security read-only review passed before and after digest/truth-source hardening
- live verification: not performed; this contour is approved handoff readiness proof only and keeps delivery/live provider/native/product claims false

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/approved_handoff.py
- command: wild-boar-proxy router-hook handoff --prompt <natural prompt> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_approved_handoff_proof
- command surface: router-hook handoff --json
- effect: probe
- changed_files: []
- source packet kind required: wbp_controlled_api_dispatch_proof
- source dispatch packet valid: true on positive proof
- hook_entry_proven: true on positive proof
- route_bound_dispatch_proven: true on positive proof
- provider_response_proven: true on positive proof
- controlled_provider_response_proven: true on positive proof
- allowed_api_route_ids_enforced: true on positive proof
- selected_api_route_id_present: required in source dispatch packet
- selected_api_route_id_recorded: false
- selected_api_route_id_sha256: required in source dispatch packet
- route_bound_request_sent: required in source dispatch packet
- route_bound_request_sha256: required in source dispatch packet
- provider_response_digest: required in source dispatch packet
- controlled_provider_response_sha256: required and recomputed from request digest and route digest
- dispatch_truth_source: server_owned_controlled_provider_no_live_network
- api_lane_truth_source: server_owned_controlled_route_bound_dispatch
- handoff_surface_allowed: true on approved surfaces
- handoff_surface_allowlist_enforced: true
- handoff_payload_prepared: true on positive proof
- handoff_ready: true on positive proof
- handoff_payload_sanitized: true on positive proof
- handoff_payload_sha256: present on positive proof
- handoff_payload_text_recorded: false
- handoff_payload_raw_recorded: false
- handoff_truth_source: server_owned_controlled_dispatch
- handoff_delivered: false by default
- handoff_delivery_observed: false by default
- handoff_counts_as_native_free_chat_router: false
- handoff_counts_as_live_provider_proof: false
- handoff_counts_as_product_ready: false
- command_origin_proven: false
- custom_codex_origin_proven: false
- native_custom_codex_flow_proven: false
- native_router_hook_observed: false
- native_free_chat_router_proven: false
- live_provider_response_proven: false
- external_live_provider_response_proven: false
- product_ready: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- natural_phrase_recorded: false
- route_candidate_recorded: false
- raw_provider_response_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- state_written: false
- evidence_written: false
- file_mutation_attempted: false

## Negative Coverage

- missing dispatch packet: blocked
- failed dispatch packet: blocked
- unapproved handoff surface: blocked
- missing selected route digest: blocked
- missing selected route presence flag: blocked
- missing route-bound request sent flag: blocked
- missing route-bound request digest: blocked
- missing provider response digest: blocked
- missing controlled provider response digest: blocked
- provider response digest mismatch: blocked
- forged self-consistent provider digest not matching route/request digest: blocked
- invalid dispatch truth source: blocked
- invalid API-lane truth source: blocked
- raw prompt claim: blocked
- raw route id claim: blocked
- raw provider response claim: blocked
- live provider overclaim: blocked
- product-ready overclaim: blocked
- native free-chat overclaim: blocked
- observed Custom Codex origin overclaim: blocked
- handoff delivered claim without observed delivery: blocked
- CLI command emits a single strict JSON object

## Git

- branch: codex/stabilize-runtime-core
- commit: approved handoff proof v1 commit created after closeout verification
- pushed: branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; prompt text, route id, provider response text, backend details, context file path, and secret values are not recorded in the handoff proof packet

## Notes

- blockers encountered: the initial handoff guard trusted boolean source proof fields too much; independent audit forced canonical digest/truth-source binding and the final packet now fails closed when those fields are missing, inconsistent, or forged.
- resume from here: CLOSED
