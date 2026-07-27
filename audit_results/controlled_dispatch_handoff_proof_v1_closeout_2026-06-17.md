<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Controlled Dispatch Handoff Proof v1 Closeout

## Goal

Add a strict proof layer that accepts a positive
`wbp_controlled_ingress_api_dispatch_proof`, validates the dispatch truth and
unsafe-claim boundaries, prepares an approved handoff payload, observes an MCP
tool-response delivery envelope, and emits a sanitized handoff proof packet.

This contour proves controlled dispatch handoff through an approved observed
machine surface. It does not prove Custom Codex UI visibility, native free-chat
interception, live provider access, semantic expected-text matching, rich UI
readiness, voice, or product readiness.

## Result

- status: CLOSED
- final verdict: CONTROLLED_DISPATCH_HANDOFF_PROOF_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: positive controlled ingress API dispatch proof to approved observed MCP tool-response handoff proof without UI, native-free-chat, live-provider, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: dba9b269
- touched files: wild_boar_proxy/controlled_dispatch_handoff_proof.py; wild_boar_proxy/approved_handoff.py; wild_boar_proxy/cli.py; tests/test_controlled_dispatch_handoff_proof.py; tests/test_approved_handoff.py; tests/test_cli.py; audit_results/controlled_dispatch_handoff_proof_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_controlled_dispatch_handoff_proof.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_controlled_dispatch_handoff_proof.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_custom_codex_ingress_proof.py tests/test_controlled_api_dispatch.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m compileall -q wild_boar_proxy tests/test_controlled_dispatch_handoff_proof.py tests/test_approved_handoff.py; git diff --check for contour files; make test-core
- blocked risks: read-only contract audit found a broken CLI import, missing dedicated top-level tests, missing top-level ingress prerequisites, and weaker direct approved-handoff validation; all were fixed and reverified
- closure state: CLOSED

## Verification

- tests: focused handoff/dispatch/CLI suite passed with 37 tests and 141 subtests
- tests: expanded proof and command-packet suite passed with 249 tests and 283 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for contour files
- audit: James read-only scanner confirmed the existing `approved_handoff` and `observed_machine_handoff_delivery` primitives were the right reuse path
- audit: Dewey read-only contract review found CLI and validator gaps; fixes were added for `HANDOFF_SURFACE_MCP_TOOL_RESPONSE` import, top-level `ingress_proven` and `controlled_ingress_proven` validation, dedicated wrapper tests, and stricter standalone approved-handoff checks
- live verification: not performed; this contour proves controlled provider-like dispatch handoff and keeps live provider claims false

## Artifacts

- packet: wild_boar_proxy/controlled_dispatch_handoff_proof.py
- command: wild-boar-proxy router-hook handoff-proof --dispatch-proof-file <dispatch-proof.json> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_controlled_dispatch_handoff_proof
- command surface: router-hook handoff-proof --json
- effect: probe
- changed_files: []
- dispatch_proof_kind: wbp_controlled_ingress_api_dispatch_proof
- dispatch_proof_valid: true on positive proof
- ingress_proven: true on positive proof
- controlled_ingress_proven: true on positive proof
- dispatch_proven: true on positive proof
- api_lane_called: true on positive proof
- api_response_received: true on positive proof
- response_bound_to_proof: true on positive proof
- provider_like_response_only: true
- allowed_api_route_ids_enforced: true on positive proof
- forbidden_stale_route_ids_enforced: true on positive proof
- route_bound_dispatch_proven: true on positive proof
- controlled_provider_response_proven: true on positive proof
- handoff_surface_kind: mcp_tool_response on positive proof
- handoff_surface_allowed: true on positive proof
- handoff_surface_supports_observed_delivery: true on positive proof
- approved_handoff_surface_used: true on positive proof
- approved_handoff_ready: true on positive proof
- approved_handoff_payload_sanitized: true on positive proof
- handoff_payload_digest: present on positive proof
- handoff_payload_prepared: true on positive proof
- handoff_envelope_built: true on positive proof
- handoff_observed: true on positive proof
- handoff_completed: true on positive proof
- machine_response_envelope_observed: true on positive proof
- machine_response_structured_content_present: true on positive proof
- codex_working_flow_delivery_proven: false
- delivery_counts_as_custom_codex_ui: false
- live_provider_proven: false
- live_provider_response_proven: false
- external_live_provider_response_proven: false
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

- wrong dispatch proof kind: blocked
- negative dispatch proof: blocked
- dispatch proof missing `ingress_proven` or `controlled_ingress_proven`: blocked as invalid dispatch proof
- dispatch proof missing dispatch/API/response/stale-route/digest evidence: blocked as invalid dispatch proof
- dispatch proof overclaims fallback, local imitation, Codex sub-agent, live provider, product-ready, native-free-chat, raw prompt, raw provider response, or secret exposure: blocked as unsafe source
- approved but unobserved handoff surfaces such as file bridge: blocked as unsupported for observed handoff proof v1
- unapproved handoff surface: blocked
- direct approved-handoff source with spoofed `machine_error_code`, missing `dispatch_proven`, wrong `dispatch_status`, or live-provider overclaim: blocked
- CLI command emits a single strict JSON object
- CLI command preserves `changed_files=[]` and leaves an external sentinel file unchanged

## Git

- branch: codex/stabilize-runtime-core
- commit: controlled dispatch handoff proof v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat work mixed in: no
- live provider work mixed in: no
- private-data risk reviewed: yes; prompt text, raw JSONL, route id, provider response text, backend details, dispatch proof file path, and secret values are not recorded in the proof packet

## Notes

- implementation note: only `mcp_tool_response` is supported as an observed handoff proof surface in this contour because it has an existing machine envelope proof primitive; other approved handoff surfaces remain blocked until separately observed.
- implementation note: the proof intentionally keeps `codex_working_flow_delivery_proven=false`; this contour proves approved machine handoff, not visible Custom Codex chat UI delivery.
- blockers encountered: first focused run exposed a missing CLI import; audit then exposed missing top-level ingress prerequisites and weaker direct approved-handoff validation; all were fixed and reverified.
- resume from here: CLOSED
