<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Codex Transcript Delivery Observation v1 Closeout

## Goal

Add a strict read-only proof layer that accepts a positive
`wbp_controlled_dispatch_handoff_proof`, reads a Codex exec JSONL transcript,
observes an MCP tool-result `structuredContent`, and proves that the nested
handoff payload digest matches the handoff proof.

This contour proves Codex transcript delivery observation for an MCP result.
It does not prove Custom Codex UI visibility, native free-chat interception,
live provider access, voice, rich UI readiness, or product readiness.

## Result

- status: CLOSED
- final verdict: CODEX_TRANSCRIPT_DELIVERY_OBSERVATION_V1_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: positive controlled dispatch handoff proof to Codex exec JSON MCP tool-result observation with digest binding and no UI, native-free-chat, live-provider, or product-ready claims
- branch: codex/stabilize-runtime-core
- head: b5284074 before the contour commit
- touched files: wild_boar_proxy/codex_transcript_delivery_observation.py; wild_boar_proxy/cli.py; tests/test_codex_transcript_delivery_observation.py; tests/test_cli.py; audit_results/codex_transcript_delivery_observation_v1_closeout_2026-06-17.md
- tests run: python3 -m compileall -q wild_boar_proxy tests/test_codex_transcript_delivery_observation.py; python3 -m pytest tests/test_codex_transcript_delivery_observation.py -q; python3 -m pytest tests/test_codex_transcript_delivery_observation.py tests/test_controlled_dispatch_handoff_proof.py tests/test_observed_machine_handoff_delivery.py tests/test_mcp_delegate.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; python3 -m pytest tests/test_codex_transcript_delivery_observation.py tests/test_controlled_dispatch_handoff_proof.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_custom_codex_ingress_proof.py tests/test_controlled_api_dispatch.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py tests/test_router_hook_entry.py tests/test_natural_intent_contract.py tests/test_mcp_delegate.py tests/test_official_mcp_admission_proof.py tests/test_command_packets_core.py tests/test_owner_surface_effect_inventory.py tests/test_cli.py::CliTests::test_cli_effect_classifier_covers_canonical_error_contexts -q; git diff --check for contour files; make test-core
- blocked risks: read-only audit found that previous handoff proof synthesized an envelope and did not read transcript tool results; this contour adds transcript input, structuredContent digest binding, content-text divergence guard, wrong server/tool blocking, raw/overclaim blocking, and CLI JSONL fail-closed coverage
- closure state: CLOSED

## Verification

- tests: focused transcript suite passed with 7 tests and 7 subtests
- tests: focused transcript/handoff/delivery/mcp/CLI suite passed with 106 tests and 150 subtests
- tests: expanded proof and command-packet suite passed with 256 tests and 291 subtests
- build: make test-core passed with 418 tests and 120 subtests
- build: compileall completed without output
- manual: git diff --check completed without output for contour files
- audit: Descartes read-only scanner mapped existing Codex JSONL, MCP response envelope, handoff, and command-packet redaction primitives
- audit: Aquinas read-only contract review identified the missing transcript tool-result binding; the implementation adds the missing binding and negative coverage
- live verification: not performed; this contour uses Codex exec JSONL transcript input and keeps live provider claims false

## Artifacts

- packet: wild_boar_proxy/codex_transcript_delivery_observation.py
- command: wild-boar-proxy router-hook transcript-observe --handoff-proof-file <handoff-proof.json> --codex-exec-jsonl-file <codex-exec.jsonl> --json
- report: this closeout

## Evidence Summary

- packet_kind: wbp_codex_transcript_delivery_observation
- command surface: router-hook transcript-observe --json
- effect: probe
- changed_files: []
- observation_path: codex_exec_json_mcp_tool_result
- handoff_proof_kind: wbp_controlled_dispatch_handoff_proof
- handoff_proof_valid: true on positive proof
- handoff_completed: true on positive proof
- handoff_envelope_built: true on positive proof
- machine_response_envelope_observed: true on positive proof
- machine_response_structured_content_present: true on positive proof
- codex_exec_json_events_observed: true on positive proof
- mcp_tool_result_observed: true on positive proof
- mcp_tool_result_structured_content_present: true on positive proof
- mcp_tool_result_server_allowed: true on positive proof
- mcp_tool_result_name_allowed: true on positive proof
- mcp_tool_result_is_error: false on positive proof
- mcp_tool_result_content_text_json_matches_structured_content: true when transcript content text is present
- structured_content_digest: present on positive proof
- declared_handoff_payload_digest: matches handoff_payload_digest on positive proof
- observed_handoff_payload_digest: matches handoff_payload_digest on positive proof
- structured_content_matches_handoff: true on positive proof
- codex_transcript_delivery_observed: true on positive proof
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

- invalid handoff proof: blocked
- transcript without MCP tool result: blocked
- invalid JSONL transcript: blocked with machine-readable error packet
- MCP result with mismatched handoff payload digest: blocked
- MCP result with `content[0].text` JSON diverging from `structuredContent`: blocked
- MCP result with `isError=true`: blocked
- MCP result from wrong server name: blocked
- MCP result with wrong tool name: blocked
- transcript event with raw provider-response claim: blocked as unsafe
- stale mismatching result before a later matching result: matching result is selected and proven
- CLI command emits a single JSON object and preserves `changed_files=[]`
- CLI command records file presence/read status but does not record file paths

## Git

- branch: codex/stabilize-runtime-core
- commit: Codex transcript delivery observation v1 implementation and evidence are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat work mixed in: no
- live provider work mixed in: no
- private-data risk reviewed: yes; prompt text, raw JSONL, route id, provider response text, backend details, file paths, and secret values are not recorded in the proof packet

## Notes

- implementation note: `structured_content_digest` is the digest of the full delivery payload, while handoff matching is proven by the nested `handoff_payload` digest and declared `handoff_payload_sha256`.
- implementation note: `content[0].text` is not required to be present in every transcript shape, but when it is present it must parse to JSON and match `structuredContent`.
- implementation note: the proof intentionally keeps `custom_codex_ui_visibility_proven=false` and `product_ready=false`; this contour proves transcript delivery observation, not visible Custom Codex chat UI delivery.
- blockers encountered: first focused run exposed overly-inner candidate selection that dropped server/tool context; selection now binds the observed payload to the outer MCP result event/item.
- resume from here: CLOSED
