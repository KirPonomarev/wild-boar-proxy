<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Controlled API Dispatch Proof v1 Closeout

## Goal

Add a minimal WBP-owned controlled dispatch proof that starts from the natural
router hook entry, reads the server-issued runtime context, enforces the API
route allowlist, and proves route-bound controlled API-lane dispatch through the
existing `mcp_delegate` adapter/proof spine.

This contour does not claim live provider access, native Custom Codex free-chat
interception, UI readiness, or product readiness.

## Result

- status: CLOSED
- final verdict: CONTROLLED_API_DISPATCH_PROOF_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: router-hook entry to parser/preflight to server-owned route-bound controlled API-lane dispatch proof without live-provider or product-ready claims
- branch: codex/stabilize-runtime-core
- head: fccd8b7b
- touched files: wild_boar_proxy/controlled_api_dispatch.py; wild_boar_proxy/cli.py; tests/test_controlled_api_dispatch.py; audit_results/controlled_api_dispatch_proof_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_controlled_api_dispatch.py -q; python3 -m compileall -q wild_boar_proxy tests/test_controlled_api_dispatch.py; python3 -m pytest tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py -q; python3 -m pytest tests/test_owner_surface_effect_inventory.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py -q; python3 -m pytest tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; git diff --check; make test-core
- blocked risks: independent audit found bridge-backed provenance overclaim on local_proof_command and missing api_lane_truth_source; both were repaired and rechecked before closeout
- closure state: CLOSED

## Verification

- tests: controlled dispatch focused tests passed with 9 tests and 6 subtests
- tests: targeted dispatch, hook entry, natural intent, MCP delegate, official MCP admission, and command packet suite passed with 176 tests and 93 subtests
- tests: owner surface effect inventory plus dispatch/hook tests passed with 47 tests and 48 subtests
- tests: CLI effect classifier targeted case passed with 1 test and 59 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output
- audit: Darwin contract/security read-only review passed
- audit: Hegel code review raised two medium findings; both were repaired, then Hegel rechecked and reported findings: none
- live verification: not performed; this contour is controlled route-bound dispatch proof and keeps live provider proof flags false

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/controlled_api_dispatch.py
- command: wild-boar-proxy router-hook dispatch --prompt <natural prompt> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_controlled_api_dispatch_proof
- command surface: router-hook dispatch --json
- effect: probe
- changed_files: []
- hook_entry_packet_kind: wbp_router_hook_entry
- hook_entry_proven: true only after admitted hook surface and parser/preflight pass
- parser_packet_kind: wbp_natural_intent_contract
- alias_context_read: true on valid runtime context
- route_authority_source: runtime_context
- allowed_api_route_ids_enforced: true on positive proof
- route_candidate_recorded: false
- selected_api_route_id_recorded: false
- selected_api_route_id_sha256: present on positive proof
- api_lane_adapter_called: true on positive proof
- controlled_api_lane_adapter_called: true on positive proof
- api_lane_dispatch_admitted: true on positive proof
- route_bound_dispatch_attempted: true on positive proof
- route_bound_dispatch_proven: true on positive proof
- route_bound_request_sent: true on positive proof
- route_bound_request_sha256: present on positive proof
- dispatch_truth_source: server_owned_controlled_provider_no_live_network
- api_lane_truth_source: server_owned_controlled_route_bound_dispatch
- controlled_provider_called: true on positive proof
- controlled_provider_response_proven: true on positive proof
- provider_response_proven: true on positive proof
- local_proof_command_dispatch_proven: true for local proof command surface
- bridge_backed_provider_proof: true only for bridge-backed hook surfaces
- live_provider_response_proven: false
- external_live_provider_response_proven: false
- product_ready: false
- native_free_chat_router_proven: false
- native_custom_codex_flow_proven: false
- native_router_hook_observed: false
- fallback_used: false
- local_imitation_used: false
- native_codex_subagent_used_as_dip: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- raw_provider_response_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- state_written: false
- evidence_written: false
- file_mutation_attempted: false

## Negative Coverage

- missing alias context: blocked before adapter call
- no alias: blocked before adapter call
- primary-only alias: blocked before adapter call
- route outside allowlist: blocked before adapter call
- API lane adapter unavailable: blocked without route-bound dispatch
- controlled provider unavailable: blocked without provider response proof
- controlled provider error: blocked without provider response proof
- local proof command: proves route-bound controlled dispatch but does not claim bridge-backed provenance
- launcher-owned bridge and file bridge: prove bridge-backed provenance without native Custom Codex or live provider claims
- CLI command: reads runtime context file, emits single strict JSON object, and records no prompt text, route id, provider response text, or context file path

## Git

- branch: codex/stabilize-runtime-core
- commit: controlled api dispatch proof v1 commit created after closeout verification
- pushed: branch push required after commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; prompt text, route id, provider response text, raw backend details, context file path, and secret values are not recorded in the dispatch proof packet

## Notes

- blockers encountered: initial implementation used a local expected-token adapter, then was corrected to reuse the existing `mcp_delegate` route-bound controlled dispatch spine. Independent audit later found a bridge-backed provenance overclaim on `local_proof_command` and a missing canonical `api_lane_truth_source`; both issues were fixed and independently rechecked.
- resume from here: CLOSED
