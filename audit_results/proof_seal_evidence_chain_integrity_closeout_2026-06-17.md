<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Proof Seal Evidence Chain Integrity Closeout

## Goal

Add a runtime/proof-only seal layer that binds file-backed proof packets to
their packet hash, declared input packet hashes, Custom Codex profile digests,
and hook ledger digest, then require strict sealed evidence before promoting
`source_file_authenticity_proven`.

This contour does not claim cryptographic signatures, unforgeable source files,
Custom Codex rendered UI visibility, native free-chat router readiness, voice, or
product readiness.

## Result

- status: CLOSED
- final verdict: PROOF_SEAL_EVIDENCE_CHAIN_INTEGRITY_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: strict file-backed proof seal manifests and verifier for Custom Codex hook-origin proof chain with exact input hash binding and no product, UI, route, prompt, provider-response, or cryptographic overclaims
- branch: codex/stabilize-runtime-core
- head: c5096da8 before the contour commit
- touched files: wild_boar_proxy/proof_seal.py; wild_boar_proxy/custom_codex_hook_origin_proof.py; wild_boar_proxy/cli.py; tests/test_proof_seal.py; tests/test_custom_codex_hook_origin_proof.py; audit_results/proof_seal_evidence_chain_integrity_closeout_2026-06-17.md
- tests run: python3 -m py_compile wild_boar_proxy/proof_seal.py wild_boar_proxy/custom_codex_hook_origin_proof.py wild_boar_proxy/cli.py; python3 -m pytest tests/test_proof_seal.py tests/test_custom_codex_hook_origin_proof.py; python3 -m pytest tests/test_real_custom_codex_hook_proof.py tests/test_codex_working_flow_delivery_proof.py tests/test_cli.py tests/test_proof_seal.py tests/test_custom_codex_hook_origin_proof.py; make test-core; git diff --check for contour files; strict sealed practical proof at /Volumes/Work/wbp-proof-homes/proof-seal-chain-20260617T172552Z/custom-origin-proof.strict-sealed.packet.json
- blocked risks: read-only audit found a false-green in input-chain verification where producer_inputs_digest and unexpected input_packet_hashes were not rejected; implementation now recomputes producer_inputs_digest from declared inputs, enforces exact expected input sets in strict verification, and adds negative coverage for tampered digest and unexpected input hashes
- closure state: CLOSED

## Verification

- tests: focused proof seal and Custom Codex hook-origin suite passed with 25 tests
- tests: expanded hook proof, working-flow delivery, CLI, proof seal, and hook-origin suite passed with 546 tests
- build: make test-core passed with 418 tests and 120 subtests
- build: py_compile passed for proof_seal.py, custom_codex_hook_origin_proof.py, and cli.py
- manual: git diff --check completed without output for contour files
- audit: Herschel read-only scanner confirmed no prior seal layer and identified the relevant proof-chain insertion points and negative test risks
- audit: Beauvoir read-only auditor found the input-chain false-green; the issue was fixed and reverified before commit
- live verification: strict sealed practical proof completed with status ok, source_file_authenticity_proven true, source_file_unforgeable false, cryptographic_authenticity_proven false, command_origin_proven true, custom_codex_flow_proven true, api_lane_called true, external_live_provider_response_proven true, codex_working_flow_delivery_proven true, product_ready false

## Artifacts

- packet: wild_boar_proxy/proof_seal.py
- command: wild-boar-proxy router-hook proof-seal-create --packet-file <packet.json> --producer-kind <kind> --producer-command-digest <sha256> --json
- command: wild-boar-proxy router-hook proof-seal-verify --packet-file <packet.json> --seal-file <seal.json> --expected-packet-kind <kind> --json
- packet: /Volumes/Work/wbp-proof-homes/proof-seal-chain-20260617T172552Z/custom-origin-proof.strict-sealed.packet.json
- report: this closeout

## Evidence Summary

- seal_kind: wbp_proof_seal_v1
- create_packet_kind: wbp_proof_seal_create
- verify_packet_kind: wbp_proof_seal_verify
- effect create: mutate
- effect verify: probe
- sealed_packet_sha256: required and verified
- sealed_packet_kind: required and verified
- producer_kind: required
- producer_command_digest: required
- producer_inputs_digest: required and recomputed from input_packet_hashes
- input_packet_hashes: exact-set enforced when expected inputs are declared
- runtime_context_digest: verified when expected digest is declared
- hook_ledger_digest: verified when expected digest is declared
- profile_hook_config_digest: verified when expected digest is declared
- raw_command_recorded: false
- command_path_recorded: false
- packet_file_path_recorded: false
- seal_file_path_recorded: false
- input_packet_paths_recorded: false
- raw_prompt_recorded: false
- prompt_text_recorded: false
- natural_phrase_recorded: false
- raw_route_id_recorded: false
- selected_api_route_id_recorded: false
- raw_provider_response_recorded: false
- provider_response_text_recorded: false
- provider_response_preview_recorded: false
- raw_backend_details_exposed: false
- secret_value_exposed: false
- custom_codex_ui_visibility_proven: false
- delivery_counts_as_custom_codex_ui: false
- native_free_chat_router_proven: false
- product_ready: false
- source_file_unforgeable: false
- cryptographic_authenticity_proven: false

## Negative Coverage

- missing seal file: blocked
- modified packet after seal creation: blocked
- wrong packet kind: blocked
- unsafe seal product_ready claim: blocked
- input packet hash mismatch: blocked
- tampered producer_inputs_digest: blocked
- unexpected input_packet_hashes when an exact expected input set is declared: blocked
- strict Custom Codex source seal with unexpected inputs: blocked
- strict Custom Codex working-flow seal with cross-run source input hash: blocked
- legacy Custom Codex hook-origin proof keeps source_file_authenticity_proven false
- strict sealed Custom Codex proof requires source and working-flow seal verification

## Git

- branch: codex/stabilize-runtime-core
- commit: Proof seal evidence chain implementation and closeout are included in the contour commit
- pushed: yes

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat router work mixed in: no
- live provider implementation work mixed in: no
- private-data risk reviewed: yes; seal manifests and packets do not record raw prompts, route ids, provider response text, command paths, packet paths, seal paths, input paths, backend details, or secret values

## Notes

- implementation note: strict sealed evidence raises source_file_authenticity_proven only for file-backed packet/hash/input/profile/ledger integrity; it deliberately keeps source_file_unforgeable and cryptographic_authenticity_proven false.
- implementation note: the generic verifier validates producer_inputs_digest against the declared input hash set; strict Custom Codex verification additionally supplies exact expected input hash sets.
- blockers encountered: independent audit found the input-chain false-green before commit; the verifier and tests were tightened and all targeted, expanded, core, and practical checks passed afterward.
- resume from here: CLOSED
