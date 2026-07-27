<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Controlled Ingress API Dispatch Proof v1 Closeout

## Goal

Add a strict proof layer that accepts a positive WBP-controlled Custom Codex
ingress proof, rebinds it to the runtime prompt by digest, rechecks the current
runtime context and route allowlist, calls the approved controlled API lane, and
emits a sanitized dispatch proof packet.

This contour proves controlled route-bound API dispatch from controlled ingress.
It does not prove native free-chat interception, Custom Codex UI origin, live
provider access, semantic expected-text matching, rich UI readiness, voice, or
product readiness.

## Result

- status: CLOSED
- final verdict: CONTROLLED_INGRESS_API_DISPATCH_PROOF_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: controlled ingress proof plus digest-bound prompt and runtime context recheck to approved controlled API-lane dispatch proof without UI, native-free-chat, live-provider, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: e2d5b958
- touched files: wild_boar_proxy/controlled_ingress_api_dispatch_proof.py; wild_boar_proxy/cli.py; wild_boar_proxy/natural_intent_contract.py; wild_boar_proxy/controlled_api_dispatch.py; wild_boar_proxy/custom_codex_ingress_proof.py; tests/test_controlled_ingress_api_dispatch_proof.py; tests/test_controlled_api_dispatch.py; tests/test_custom_codex_ingress_proof.py; tests/test_router_hook_entry.py; tests/test_natural_intent_contract.py; tests/test_cli.py; audit_results/controlled_ingress_api_dispatch_proof_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_controlled_ingress_api_dispatch_proof.py tests/test_controlled_api_dispatch.py tests/test_custom_codex_ingress_proof.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_controlled_ingress_api_dispatch_proof.py tests/test_controlled_api_dispatch.py tests/test_custom_codex_ingress_proof.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m compileall -q wild_boar_proxy tests/test_controlled_ingress_api_dispatch_proof.py; git diff --check for contour files; make test-core
- blocked risks: read-only contract audit found route proof false-green when `forbidden_stale_route_ids=[]`; fixed by requiring stale-route guard in natural intent/router/ingress/dispatch proof chain and by adding negative tests
- closure state: CLOSED

## Verification

- tests: focused ingress-dispatch/router/natural-intent/CLI suite passed with 64 tests and 113 subtests
- tests: expanded proof and command-packet suite passed with 242 tests and 255 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for contour files
- audit: Franklin read-only scanner confirmed the existing `controlled_api_dispatch` and `mcp_delegate` spine was the right reuse path
- audit: Pasteur read-only contract review identified stale-route guard false-green risk and semantic-response overclaim risk; stale guard was fixed, semantic overclaim was kept false by explicit provider-like/no-live/no-product fields
- live verification: not performed; this contour proves controlled provider-like route-bound dispatch and keeps live provider claims false

## Artifacts

- packet: wild_boar_proxy/controlled_ingress_api_dispatch_proof.py
- command: wild-boar-proxy router-hook dispatch-proof --ingress-proof-file <ingress-proof.json> --prompt <runtime prompt> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_controlled_ingress_api_dispatch_proof
- command surface: router-hook dispatch-proof --json
- effect: probe
- changed_files: []
- ingress_proof_kind: wbp_custom_codex_ingress_proof
- ingress_proven: true on positive proof
- controlled_ingress_proven: true on positive proof
- prompt_digest_bound_to_ingress_proof: true on positive proof
- prompt_digest_bound_to_dispatch: true on positive proof
- prompt_digest_bound_to_proof: true on positive proof
- alias_context_read: true on positive proof
- alias_bound: true on positive proof
- route_id_allowed: true on positive proof
- allowed_api_route_ids_enforced: true on positive proof
- forbidden_stale_route_ids_enforced: true on positive proof
- api_lane_called: true on positive proof
- api_lane_adapter_called: true on positive proof
- api_lane_dispatch_admitted: true on positive proof
- api_response_received: true on positive proof
- controlled_provider_called: true on positive proof
- controlled_provider_response_proven: true on positive proof
- response_bound_to_proof: true on positive proof
- dispatch_proven: true on positive proof
- dispatch_status: proven on positive proof
- provider_like_response_only: true
- live_provider_proven: false
- live_provider_response_proven: false
- external_live_provider_response_proven: false
- live_provider_status: not_attempted
- native_free_chat_router_proven: false
- product_ready: false
- fallback_used: false on positive proof
- local_imitation_used: false on positive proof
- native_codex_subagent_used_as_dip: false on positive proof
- raw_prompt_recorded: false
- prompt_text_recorded: false
- raw_jsonl_recorded: false
- tool_call_arguments_recorded: false
- route_candidate_recorded: false
- selected_api_route_id_recorded: false
- raw_provider_response_recorded: false
- provider_response_text_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- state_written: false
- evidence_written: false
- file_mutation_attempted: false

## Negative Coverage

- wrong ingress packet kind: blocked
- negative ingress packet: blocked
- ingress packet overclaims API lane, dispatch, product-ready, native-free-chat, fallback, local imitation, Codex sub-agent use, or raw prompt: blocked
- prompt digest mismatch between runtime prompt and ingress proof: blocked before dispatch
- current runtime route outside allowlist: blocked before adapter call
- current runtime missing stale-route guard: blocked before adapter call
- API lane adapter unavailable: no false-green
- controlled provider unavailable: no false-green
- controlled provider error: no false-green
- missing stale-route guard in natural intent/router/controlled dispatch/ingress chain: blocked
- CLI command emits a single strict JSON object
- CLI command preserves `changed_files=[]` and leaves an external sentinel file unchanged

## Git

- branch: codex/stabilize-runtime-core
- commit: controlled ingress API dispatch proof v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- live provider work mixed in: no
- private-data risk reviewed: yes; prompt text, raw JSONL, route id, provider response text, backend details, context file path, ingress proof file path, and secret values are not recorded in the proof packet

## Notes

- implementation note: `--prompt` is required by the CLI because the ingress proof intentionally does not store raw prompt text; the command verifies the prompt digest against ingress before dispatch and redacts the prompt from output.
- implementation note: this contour intentionally keeps semantic expected-text matching false; the proof is route-bound controlled provider dispatch, not a live provider content proof.
- blockers encountered: focused tests exposed a test sentinel lifetime bug and missing propagation of detailed router blocking reasons through controlled dispatch; both were fixed and reverified.
- resume from here: CLOSED
