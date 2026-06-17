<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Codex Exec Assistant Continuation Proof v1 Closeout

## Goal

Add a strict read-only proof layer that accepts a positive
`wbp_codex_transcript_delivery_observation`, reads the same Codex exec JSONL
transcript, observes a matching MCP tool-result, and proves that an
assistant/output event after that tool-result carries a safe machine digest
marker bound to the handoff digest.

This contour proves Codex exec assistant continuation after a digest-bound MCP
result. It does not prove Custom Codex UI visibility, native free-chat
interception, live provider access, voice, rich UI readiness, or product
readiness.

## Result

- status: CLOSED
- final verdict: CODEX_EXEC_ASSISTANT_CONTINUATION_PROOF_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: positive transcript delivery observation to digest-bound assistant continuation in the same Codex exec JSONL without UI, native-free-chat, live-provider, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: 3aa7a67b before the contour commit
- touched files: wild_boar_proxy/codex_exec_assistant_continuation_proof.py; wild_boar_proxy/codex_transcript_delivery_observation.py; wild_boar_proxy/cli.py; tests/test_codex_exec_assistant_continuation_proof.py; tests/test_codex_transcript_delivery_observation.py; tests/test_cli.py; audit_results/codex_exec_assistant_continuation_proof_v1_closeout_2026-06-17.md
- tests run: python3 -m compileall -q wild_boar_proxy tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py; python3 -m pytest tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py -q; python3 -m pytest tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py tests/test_controlled_dispatch_handoff_proof.py tests/test_observed_machine_handoff_delivery.py tests/test_mcp_delegate.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_transcript_delivery_observation.py tests/test_controlled_dispatch_handoff_proof.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_custom_codex_ingress_proof.py tests/test_controlled_api_dispatch.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; git diff --check for contour files; make test-core
- blocked risks: read-only audit found that transcript observation could accept `assistant/output` as a false MCP tool-result and that same-JSONL binding lacked a transcript digest; both were fixed with regression coverage and canonical transcript digest binding
- closure state: CLOSED

## Verification

- tests: focused assistant-continuation and transcript-observation suite passed with 15 tests and 16 subtests
- tests: focused adjacent transcript/handoff/delivery/mcp/CLI suite passed with 114 tests and 160 subtests
- tests: expanded proof and command-packet suite passed with 264 tests and 301 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for contour files
- audit: Russell read-only scanner confirmed the existing JSONL, nested event walking, sub-agent, raw guard, and router-hook CLI patterns were the right reuse path
- audit: Hegel read-only contract review found a transcript-observe false-green on assistant/output, missing same-JSONL digest binding, and layer-mixing risk around synthetic machine envelopes; implementation and tests were updated accordingly
- live verification: not performed; this contour uses Codex exec JSONL transcript input and keeps live provider claims false

## Artifacts

- packet: wild_boar_proxy/codex_exec_assistant_continuation_proof.py
- command: wild-boar-proxy router-hook assistant-continuation-proof --transcript-observation-file <observation.json> --codex-exec-jsonl-file <codex-exec.jsonl> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_codex_exec_assistant_continuation_proof
- command surface: router-hook assistant-continuation-proof --json
- effect: probe
- changed_files: []
- transcript_observation_kind: wbp_codex_transcript_delivery_observation
- transcript_observation_valid: true on positive proof
- transcript_delivery_observed: true on positive proof
- mcp_tool_result_observed: true on positive proof
- mcp_tool_result_structured_content_present: true on positive proof
- structured_content_matches_handoff: true on positive proof
- handoff_payload_digest: present on positive proof
- codex_exec_json_events_observed: true on positive proof
- codex_exec_transcript_sha256: present on positive proof
- transcript_observation_codex_exec_transcript_sha256: present on positive proof
- same_codex_exec_jsonl_bound: true on positive proof
- same_codex_exec_jsonl_digest_matches: true on positive proof
- matching_mcp_tool_result_observed: true on positive proof
- assistant_response_observed: true on positive proof
- assistant_response_after_tool_result: true on positive proof
- assistant_machine_marker_observed: true on positive proof
- assistant_response_bound_to_handoff_digest: true on positive proof
- binding_method: safe_digest_metadata on positive proof
- codex_exec_assistant_continuation_proven: true on positive proof
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

- invalid transcript observation proof: blocked
- no assistant response after matching MCP tool-result: blocked
- assistant response before matching MCP tool-result: blocked
- assistant response without safe digest marker: blocked
- assistant digest marker mismatch: blocked
- current JSONL digest mismatch against transcript observation: blocked
- assistant/output without matching MCP tool-result in the same JSONL: blocked
- handoff digest mismatch against current JSONL tool-result: blocked
- transcript event with product-ready overclaim: blocked as unsafe
- transcript event with raw provider-response claim: blocked as unsafe
- transcript containing a configured secret value: blocked as unsafe
- local Codex sub-agent pretending as DIP/Agent 2: blocked as unsafe
- invalid JSONL transcript: blocked with machine-readable error packet
- transcript-observe regression: assistant/output with a matching delivery payload is no longer accepted as an MCP tool-result
- CLI command emits a single JSON object and preserves `changed_files=[]`
- CLI command records file presence/read status but does not record file paths

## Git

- branch: codex/stabilize-runtime-core
- commit: Codex exec assistant continuation proof v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat work mixed in: no
- live provider work mixed in: no
- private-data risk reviewed: yes; prompt text, raw JSONL, route id, provider response text, backend details, file paths, assistant text, and secret values are not recorded in the proof packet

## Notes

- implementation note: `codex_exec_transcript_sha256` is a canonical digest of parsed JSONL events, not raw JSONL text and not only event type names.
- implementation note: assistant continuation is proven only through machine digest metadata or a safe digest marker; semantic text matching is not used.
- implementation note: synthetic `machine_response_envelope_observed` from the handoff layer is not used as assistant/output proof.
- implementation note: the proof intentionally keeps `custom_codex_ui_visibility_proven=false`, `codex_working_flow_delivery_proven=false`, and `product_ready=false`; this contour proves exec transcript continuation, not visible Custom Codex chat UI delivery.
- blockers encountered: read-only audit exposed a false-green in the prerequisite transcript selector and missing same-JSONL binding; both were fixed and reverified.
- resume from here: CLOSED
