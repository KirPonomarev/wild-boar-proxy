<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Approved Visible Source Observation v1 Closeout

## Goal

Add a strict read-only proof layer that accepts a positive
`wbp_codex_exec_assistant_continuation_proof`, reads an approved visible-source
artifact, and proves that the approved source contains an assistant output marker
bound to the same handoff digest and the same Codex exec transcript digest.

This contour proves approved visible-source observation through
`codex_exec_json_assistant_output`. It does not prove Custom Codex UI screen
visibility, native free-chat interception, live provider access, voice, rich UI
readiness, or product readiness.

## Result

- status: CLOSED
- final verdict: CUSTOM_CODEX_APPROVED_VISIBLE_SOURCE_OBSERVATION_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: positive assistant continuation proof to approved visible-source observation with singleton source-kind allowlist, same transcript digest binding, and no UI, native-free-chat, live-provider, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: 84092097 before the contour commit
- touched files: wild_boar_proxy/custom_codex_approved_visible_source_observation.py; wild_boar_proxy/codex_transcript_delivery_observation.py; wild_boar_proxy/cli.py; tests/test_custom_codex_approved_visible_source_observation.py; tests/test_cli.py; audit_results/custom_codex_approved_visible_source_observation_v1_closeout_2026-06-17.md
- tests run: python3 -m compileall -q wild_boar_proxy tests/test_custom_codex_approved_visible_source_observation.py; python3 -m pytest tests/test_custom_codex_approved_visible_source_observation.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py -q; python3 -m pytest tests/test_custom_codex_approved_visible_source_observation.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py tests/test_controlled_dispatch_handoff_proof.py tests/test_observed_machine_handoff_delivery.py tests/test_mcp_delegate.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_custom_codex_approved_visible_source_observation.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py tests/test_controlled_dispatch_handoff_proof.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_custom_codex_ingress_proof.py tests/test_controlled_api_dispatch.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; git diff --check for contour files; make test-core
- blocked risks: read-only audit found that approved visible-source kind needed a singleton allowlist and packet fields, and that text marker binding lacked positive coverage; implementation adds source-kind allowlist, approved source fields, safe text marker coverage, and stricter UI overclaim guards
- closure state: CLOSED

## Verification

- tests: focused visible-source/continuation/transcript suite passed with 22 tests and 28 subtests
- tests: focused adjacent visible-source/transcript/handoff/delivery/mcp/CLI suite passed with 121 tests and 173 subtests
- tests: expanded proof and command-packet suite passed with 271 tests and 314 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for contour files
- audit: Bohr read-only scanner confirmed existing continuation, transcript digest, JSONL source reading, assistant marker, and raw guard helpers were the right reuse path
- audit: Huygens read-only contract review identified the missing approved source-kind gate and missing safe text marker test coverage; both were fixed and reverified
- live verification: not performed; this contour uses Codex exec JSONL visible-source input and keeps live provider claims false

## Artifacts

- packet: wild_boar_proxy/custom_codex_approved_visible_source_observation.py
- command: wild-boar-proxy router-hook visible-source-observe --assistant-continuation-proof-file <continuation.json> --visible-source-kind codex_exec_json_assistant_output --codex-exec-jsonl-file <codex-exec.jsonl> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_custom_codex_approved_visible_source_observation
- command surface: router-hook visible-source-observe --json
- effect: probe
- changed_files: []
- assistant_continuation_proof_kind: wbp_codex_exec_assistant_continuation_proof
- assistant_continuation_proof_valid: true on positive proof
- codex_exec_assistant_continuation_proven: true on positive proof
- assistant_response_bound_to_handoff_digest: true on positive proof
- same_codex_exec_jsonl_bound: true on positive proof
- handoff_payload_digest: present on positive proof
- approved_visible_source_kind: codex_exec_json_assistant_output
- approved_visible_source_allowed: true on positive proof
- approved_visible_source_kinds_count: 1
- visible_source_read: true on CLI positive proof
- visible_source_events_observed: true on positive proof
- visible_source_digest: present on positive proof
- assistant_continuation_source_digest: present on positive proof
- visible_source_digest_bound: true on positive proof
- visible_source_digest_matches_continuation: true on positive proof
- matching_mcp_tool_result_observed: true on positive proof
- visible_source_assistant_output_observed: true on positive proof
- visible_source_marker_observed: true on positive proof
- visible_source_marker_bound_to_handoff_digest: true on positive proof
- visible_source_marker_binding_method: safe_digest_metadata or safe_digest_marker
- custom_codex_approved_visible_source_observed: true on positive proof
- custom_codex_visible_flow_observed: true on positive proof
- custom_codex_ui_visibility_proven: false
- codex_working_flow_delivery_proven: false
- delivery_counts_as_custom_codex_ui: false
- live_provider_proven: false
- live_provider_response_proven: false
- external_live_provider_response_proven: false
- native_free_chat_router_proven: false
- product_ready: false
- fallback_used: false
- local_imitation_used: false
- native_codex_subagent_used_as_dip: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- natural_phrase_recorded: false
- raw_jsonl_recorded: false
- tool_call_arguments_recorded: false
- route_candidate_recorded: false
- selected_api_route_id_recorded: false
- raw_provider_response_recorded: false
- provider_response_text_recorded: false
- provider_response_preview_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- state_written: false
- evidence_written: false
- file_mutation_attempted: false

## Negative Coverage

- invalid assistant continuation proof: blocked
- unapproved visible source kind: blocked
- visible source digest mismatch against continuation proof: blocked
- visible source with MCP tool-result but no assistant output marker: blocked
- assistant output without marker: blocked
- assistant marker digest mismatch: blocked
- semantic-only digest text without machine marker: blocked
- visible source with `custom_codex_ui_visibility_proven=true`: blocked as unsafe
- visible source with `product_ready=true`: blocked as unsafe
- visible source with raw provider-response claim: blocked as unsafe
- visible source containing configured secret value: blocked as unsafe
- local Codex sub-agent pretending as DIP/Agent 2: blocked as unsafe
- invalid JSONL visible source: blocked with machine-readable error packet
- safe metadata marker binding: accepted on positive proof
- safe text marker binding: accepted on positive proof
- CLI command emits a single JSON object and preserves `changed_files=[]`
- CLI command records file presence/read status but does not record file paths

## Git

- branch: codex/stabilize-runtime-core
- commit: Custom Codex approved visible-source observation v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat work mixed in: no
- live provider work mixed in: no
- private-data risk reviewed: yes; prompt text, raw JSONL, route id, provider response text, backend details, file paths, assistant text, and secret values are not recorded in the proof packet

## Notes

- implementation note: v1 allowlists only `codex_exec_json_assistant_output`; export transcript, CDP, screenshot, accessibility, and native observer sources are not admitted here.
- implementation note: this proof observes an approved visible-source artifact, not a rendered UI screen; `custom_codex_ui_visibility_proven` intentionally remains false.
- implementation note: `_unsafe_flag_failures` now treats `custom_codex_ui_visibility_proven`, `codex_working_flow_delivery_proven`, and `delivery_counts_as_custom_codex_ui` as unsafe overclaims when found in nested source packets or events.
- blockers encountered: first focused run exposed that UI-visibility overclaim was not included in the shared unsafe flag map; the guard was added and reverified.
- resume from here: CLOSED
