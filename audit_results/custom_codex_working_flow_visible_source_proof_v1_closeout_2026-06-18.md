<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Working-Flow Visible Source Proof v1 Closeout

## Goal

Prove a repeatable Custom Codex working-flow visible-source evidence layer by
joining the existing repeatable operator proof, both admission packets, and both
Codex working-flow delivery packets into one strict file-backed packet without
claiming rendered Custom Codex UI visibility, native free-chat router readiness,
or product readiness.

## Result

- status: closed
- final verdict: positive working-flow visible-source proof accepted with operator/admission/working-flow digest bindings and no product/UI/native-router claims
- closure state: CLOSED

## Contour Capsule

- goal: bind repeatable operator proof to two admission packets and two Codex working-flow delivery packets, prove approved working-flow visible-source evidence, and keep UI/product/native-router claims false
- branch: `codex/stabilize-runtime-core`
- head: `4435ae7507e323da88a0ee06ea51d0a7e924e453` before the contour commit
- touched files: `wild_boar_proxy/custom_codex_working_flow_visible_source_proof.py`, `wild_boar_proxy/cli.py`, `tests/test_custom_codex_working_flow_visible_source_proof.py`, `tests/test_cli.py`, this closeout
- tests run: `python3 -m py_compile wild_boar_proxy/custom_codex_working_flow_visible_source_proof.py wild_boar_proxy/cli.py tests/test_custom_codex_working_flow_visible_source_proof.py`; `python3 -m pytest tests/test_custom_codex_working_flow_visible_source_proof.py -q`; `python3 -m pytest tests/test_custom_codex_working_flow_visible_source_proof.py tests/test_custom_codex_operator_proof.py tests/test_custom_codex_admission.py tests/test_codex_working_flow_delivery_proof.py tests/test_custom_codex_approved_visible_source_observation.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_proof_seal.py -q`; `python3 -m pytest tests/test_cli.py -q -k 'codex_runner or visible_source or operator or admission or working_flow_delivery'`; live working-flow visible-source proof; live packet semantic/no-leak check; `git diff --check`; `make test-core`
- blocked risks: invalid operator proof, admission hash/run-id drift, working-flow transcript digest mismatch, missing assistant response binding, source packet secret leakage including Unicode prompt text, fallback/local imitation, product-ready overclaim, Custom Codex UI visibility overclaim, native free-chat router overclaim
- closure state: CLOSED

## Verification

- tests: `tests/test_custom_codex_working_flow_visible_source_proof.py` passed with `5 passed, 3 subtests passed`
- tests: expanded working-flow/operator/admission/proof stack passed with `61 passed, 48 subtests passed`
- tests: targeted CLI selection passed with `8 passed, 488 deselected`
- build: `python3 -m py_compile` completed without output for changed proof code, CLI, and tests
- build: `git diff --check` completed without output
- build: `make test-core` passed with `418 passed, 120 subtests passed`
- manual: live packet semantic/no-leak inspection returned `semantic_violations=[]`, `leaks=[]`, `status=ok`, and `machine_error_code=OK`
- manual: scoped status checks confirmed pre-existing dirty UI files stayed outside this contour
- audit: read-only inspector Descartes confirmed existing proof builders and CLI surfaces should be reused; independent read-only auditor Halley returned `PASS` after checking the final diff, live packet, false-green guards, and layer separation
- live verification: `/Volumes/Work/wbp-proof-homes/working-flow-visible-source-live-20260617T212115Z/working-flow-visible-source-proof.packet.json` returned `status=ok`, `machine_error_code=OK`, `working_flow_visible_source_proven=true`, `custom_codex_working_flow_visible_source_proven=true`, `same_turn_custom_codex_flow_proven=true`, `repeatable_operator_proof_bound=true`, `operator_proof_valid=true`, `operator_run_count=2`, `visible_source_run_count=2`, `required_visible_source_run_count=2`, `approved_visible_source_kind=codex_working_flow_delivery_packet`, `approved_visible_source_observed=true`, `approved_visible_source_digest_bound=true`, `runtime_context_digest_bound=true`, `route_id_allowed=true`, `allowed_api_route_ids_enforced=true`, `api_lane_called=true`, `external_live_provider_response_proven=true`, `assistant_continuation_proven=true`, `codex_exec_assistant_continuation_proven=true`, `codex_working_flow_delivery_proven=true`, `codex_exec_transcript_bound=true`, `fallback_used=false`, `local_imitation_used=false`, `native_codex_subagent_used_as_dip=false`, `product_ready=false`, `custom_codex_ui_visibility_proven=false`, `delivery_counts_as_custom_codex_ui=false`, `native_free_chat_router_proven=false`, and `blocking_reasons=[]`

## Artifacts

- packet: `/Volumes/Work/wbp-proof-homes/working-flow-visible-source-live-20260617T212115Z/working-flow-visible-source-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/working-flow-visible-source-live-20260617T212115Z/repeatable-same-turn-operator-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/working-flow-visible-source-live-20260617T212115Z/run_1/working-flow-delivery-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/working-flow-visible-source-live-20260617T212115Z/run_2/working-flow-delivery-proof.packet.json`
- command: `wild-boar-proxy codex-runner working-flow-visible-source-proof --prompt <natural prompt> --codex-bin <custom codex bin> --proof-dir <proof root> --codex-cwd /Volumes/Work/wild-boar-proxy --expected-text <expected text> --sandbox danger-full-access --json`
- report: this closeout

## Negative Coverage

- invalid operator proof blocks visible-source proof
- working-flow transcript digest mismatch blocks visible-source proof
- missing assistant response digest binding blocks visible-source proof
- product-ready overclaim blocks visible-source proof
- source packet secret leak blocks visible-source proof
- final packet semantic inspection rejects raw prompt, route id, expected text, backend details, and secret leakage

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat router work mixed in: no
- Codex patch work mixed in: no
- private-data risk reviewed: yes; final packet stores digests and file-backed evidence paths, keeps raw prompt, raw route id, selected route id, expected text, raw provider response, tool arguments, backend details, and secret values out of packet authority

## Notes

- blockers encountered: initial source-packet secret scan missed Unicode raw prompt text because the lower-level scanner serializes with ASCII escapes; this contour added a Unicode-aware source-packet secret check before closeout
- implementation note: this contour proves repeatable Custom Codex working-flow visible-source evidence, not rendered Custom Codex UI visibility, native free-chat router readiness, or product readiness
- resume from here: CLOSED
