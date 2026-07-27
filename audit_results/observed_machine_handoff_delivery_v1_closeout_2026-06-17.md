<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Observed Machine Handoff Delivery v1 Closeout

## Goal

Add a minimal WBP-owned observed machine handoff delivery proof that accepts a
valid approved handoff packet, requires the approved handoff surface to be
`mcp_tool_response`, validates the sanitized payload digest against the approved
handoff digest, and proves a no-write MCP tool response envelope was observed.

This contour does not claim live provider access, observed Custom Codex origin,
native free-chat interception, UI readiness, or product readiness.

## Result

- status: CLOSED
- final verdict: OBSERVED_MACHINE_HANDOFF_DELIVERY_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: approved handoff proof to observed no-write MCP tool response envelope without live-provider, native-free-chat, observed-origin, UI, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: 5f589a3a
- touched files: wild_boar_proxy/observed_machine_handoff_delivery.py; wild_boar_proxy/cli.py; tests/test_observed_machine_handoff_delivery.py; tests/test_cli.py; audit_results/observed_machine_handoff_delivery_v1_closeout_2026-06-17.md
- tests run: python3 -m pytest tests/test_observed_machine_handoff_delivery.py -q; python3 -m compileall -q wild_boar_proxy tests/test_observed_machine_handoff_delivery.py; python3 -m pytest tests/test_observed_machine_handoff_delivery.py tests/test_approved_handoff.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_observed_machine_handoff_delivery.py tests/test_approved_handoff.py tests/test_controlled_api_dispatch.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; git diff --check -- wild_boar_proxy/observed_machine_handoff_delivery.py wild_boar_proxy/cli.py tests/test_observed_machine_handoff_delivery.py tests/test_cli.py; make test-core
- blocked risks: initial implementation could compute an envelope candidate even when the approved handoff source was invalid or payload digest mismatched; fixed so delivery is attempted only after approved source, safe source claims, surface allowlist, payload availability, and digest match all pass
- closure state: CLOSED

## Verification

- tests: observed machine handoff delivery focused suite passed with 10 tests and 11 subtests
- tests: handoff, dispatch, hook entry, natural intent, and CLI effect classifier suite passed with 66 tests and 121 subtests
- tests: observed delivery, approved handoff, controlled dispatch, router hook, natural intent, MCP delegate, official MCP admission, command packet, owner/effect inventory, and CLI classifier suite passed with 223 tests and 228 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for this contour's files
- audit: read-only codebase inspection confirmed MCP tool responses use `content`, `structuredContent`, and `isError`, and that this contour should build on `approved_handoff` and command packets
- audit: contract/security inspection confirmed the existing chain is fail-closed and recommended keeping delivery blocked unless observed
- live verification: not performed; this contour proves a no-write machine response envelope only and keeps live provider/native/product claims false

## Artifacts

- spec: active task thread contour text and repository canon
- packet: wild_boar_proxy/observed_machine_handoff_delivery.py
- command: wild-boar-proxy router-hook deliver --prompt <natural prompt> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_observed_machine_handoff_delivery
- command surface: router-hook deliver --json
- effect: probe
- changed_files: []
- source packet kind required: wbp_approved_handoff_proof
- source approved handoff packet valid: true on positive proof
- required handoff surface: mcp_tool_response
- delivery surface: mcp_tool_response
- delivery surface allowlist enforced: true
- handoff_ready: true on positive proof
- handoff_payload_sanitized: true on positive proof
- handoff_payload_sha256: required in source approved handoff packet
- delivery_payload_sha256: required and matched to approved handoff payload digest
- delivery_payload_digest_matches_approved_handoff: true on positive proof
- delivery_payload_text_recorded: false
- delivery_payload_raw_recorded: false
- machine_response_envelope_observed: true on positive proof
- machine_response_envelope_sha256: present on positive proof
- machine_response_structured_content_present: true on positive proof
- machine_response_structured_content_sha256: present on positive proof
- machine_response_content_text_present: true on positive proof
- machine_response_content_text_recorded: false
- machine_response_raw_recorded: false
- mcp_tool_response_is_error: false on positive proof
- handoff_delivered: true only after approved source, digest match, allowed surface, and observed envelope
- delivery_observed: true only after approved source, digest match, allowed surface, and observed envelope
- delivery_truth_source: server_owned_mcp_tool_response_envelope
- delivery_counts_as_machine_handoff: true on positive proof
- delivery_counts_as_custom_codex_ui: false
- delivery_counts_as_native_free_chat_router: false
- delivery_counts_as_live_provider_proof: false
- delivery_counts_as_product_ready: false
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
- selected_api_route_id_recorded: false
- raw_provider_response_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- state_written: false
- evidence_written: false
- file_mutation_attempted: false

## Negative Coverage

- missing approved handoff packet: blocked
- failed approved handoff packet: blocked
- approved handoff built for non-MCP handoff surface: blocked
- unapproved delivery surface: blocked
- missing handoff payload: blocked
- delivery surface not observed: blocked
- handoff payload digest mismatch: blocked
- raw prompt claim in source packet: blocked
- raw route id claim in source packet: blocked
- raw provider response claim in source packet: blocked
- product-ready overclaim in source packet: blocked
- native free-chat overclaim in source packet: blocked
- observed Custom Codex origin overclaim in source packet: blocked
- live provider overclaim in source packet: blocked
- invalid source, unapproved surface, unsafe source, and payload mismatch do not attempt delivery and do not observe a machine response envelope
- CLI command emits a single strict JSON object
- CLI command preserves `changed_files=[]` and leaves an external sentinel file unchanged

## Git

- branch: codex/stabilize-runtime-core
- commit: observed machine handoff delivery v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- private-data risk reviewed: yes; prompt text, route id, provider response text, backend details, context file path, machine response text, and secret values are not recorded in the delivery proof packet

## Notes

- blockers encountered: the first local review found that envelope observation could be computed before all fail-closed preconditions passed; this was corrected and covered by negative assertions.
- resume from here: CLOSED
