<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Ingress Proof v1 Closeout

## Goal

Add a minimal WBP-owned ingress proof that composes an observed Codex-side MCP
tool-call transcript with WBP router-hook entry preflight. The proof shows a
prompt digest was bound to a `delegate_to_dip` tool call and to router entry
truth, while keeping dispatch, live provider, native free-chat router, Custom
Codex UI origin, and product readiness claims false.

This contour does not claim API dispatch, live provider access, observed Custom
Codex UI origin, native free-chat interception, UI readiness, or product
readiness.

## Result

- status: CLOSED
- final verdict: CUSTOM_CODEX_INGRESS_PROOF_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: Codex-side MCP tool-call transcript plus WBP router entry preflight to controlled ingress proof without API dispatch, live-provider, native-free-chat, observed-UI-origin, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: 04603581
- touched files: wild_boar_proxy/custom_codex_ingress_proof.py; wild_boar_proxy/cli.py; tests/test_custom_codex_ingress_proof.py; tests/test_cli.py; audit_results/custom_codex_ingress_proof_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_custom_codex_ingress_proof.py -q; python3 -m pytest tests/test_custom_codex_ingress_proof.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_custom_codex_ingress_proof.py tests/test_observed_machine_handoff_delivery.py tests/test_approved_handoff.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m compileall -q wild_boar_proxy tests/test_custom_codex_ingress_proof.py; git diff --check -- wild_boar_proxy/custom_codex_ingress_proof.py wild_boar_proxy/cli.py tests/test_custom_codex_ingress_proof.py tests/test_cli.py; make test-core
- blocked risks: initial implementation incorrectly treated `browser_authority_fields_rejected=false` as a failure even when no forbidden authority fields existed; fixed to require forbidden authority field count zero
- closure state: CLOSED

## Verification

- tests: custom Codex ingress proof focused suite passed with 8 tests and 11 subtests
- tests: ingress, MCP delegate, official MCP admission, router hook, natural intent, and CLI classifier suite passed with 136 tests and 134 subtests
- tests: ingress plus previous proof-contour and command-packet suites passed with 231 tests and 240 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for this contour's files
- audit: Volta read-only research identified the reusable transcript/tool-call/router-entry primitives used in this implementation
- audit: Kant read-only contract review identified the no-UI, no-live-provider, no-product-ready, no-raw-data invariants and negative tests used here
- live verification: not performed; this contour consumes bounded transcript evidence and keeps live provider/native/product claims false

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/custom_codex_ingress_proof.py
- command: wild-boar-proxy router-hook ingress --prompt <natural prompt> --codex-exec-jsonl-file <codex-jsonl> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_custom_codex_ingress_proof
- command surface: router-hook ingress --json
- effect: probe
- changed_files: []
- prompt packet kind required: wbp_codex_prompt_observation
- Codex tool-call packet kind required: wbp_codex_exec_tool_call_observation
- router hook entry packet kind required: wbp_router_hook_entry
- ingress_proven: true on positive proof
- controlled_ingress_proven: true on positive proof
- custom_codex_origin_proven: false
- codex_tool_call_transcript_observed: true on positive proof
- mcp_tool_call_observed: true on positive proof
- mcp_tool_call_completed: true on positive proof
- prompt_digest: present on positive proof
- prompt_digest_bound_to_codex_tool_call: true on positive proof
- prompt_digest_bound_to_router_entry: true on positive proof
- prompt_digest_bound_to_ingress: true on positive proof
- tool_call_sha256: present on positive proof
- alias_context_read: true on positive proof
- alias_bound: true on positive proof
- route_id_allowed: true on positive proof
- allowed_api_route_ids_enforced: true on positive proof
- wbp_controlled_entry_called: true on positive proof
- router_hook_entry_preflight_passed: true on positive proof
- codex_native_subagent_used_as_dip: false on positive proof
- fallback_used: false on positive proof
- local_imitation_used: false on positive proof
- dispatch_proven: false
- dispatch_status: not_attempted
- api_lane_called: false
- native_free_chat_router_proven: false
- product_ready: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- natural_phrase_recorded: false
- raw_jsonl_recorded: false
- tool_call_arguments_recorded: false
- route_candidate_recorded: false
- selected_api_route_id_recorded: false
- raw_provider_response_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- state_written: false
- evidence_written: false
- file_mutation_attempted: false

## Negative Coverage

- missing transcript: blocked
- no MCP tool call in transcript: blocked
- failed MCP tool call: blocked
- prompt/tool digest mismatch: blocked
- missing runtime context: blocked
- route outside allowlist: blocked
- no alias in router entry prompt: blocked
- local Codex sub-agent used as DIP: blocked and reported as local imitation
- fallback claim in source packet: blocked
- product-ready overclaim in source packet: blocked
- native free-chat router overclaim in source packet: blocked
- API-lane claim in source packet: blocked
- raw prompt claim in source packet: blocked
- CLI command emits a single strict JSON object
- CLI command preserves `changed_files=[]` and leaves an external sentinel file unchanged

## Git

- branch: codex/stabilize-runtime-core
- commit: custom Codex ingress proof v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; prompt text, raw JSONL, route id, provider response text, backend details, context file path, and secret values are not recorded in the ingress proof packet

## Notes

- blockers encountered: the first focused test run exposed one overly strict authority-field assertion and one test fixture that accidentally contained the `Codex` alias while intending a no-alias case; both were corrected and reverified.
- resume from here: CLOSED
