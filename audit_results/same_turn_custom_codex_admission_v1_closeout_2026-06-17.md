<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Same-Turn Custom Codex Admission v1 Closeout

## Goal

Prove one linked same-turn Custom Codex admission path from natural prompt
submission to `UserPromptSubmit` hook ledger, source proof, API lane,
Codex exec working-flow delivery, assistant continuation, strict proof seals,
and final admission packet without claiming product readiness, rendered UI
visibility, or native free-chat router readiness.

## Result

- status: closed
- final verdict: positive same-turn admission proof accepted with strengthened digest bindings
- closure state: CLOSED

## Contour Capsule

- goal: bind a Custom Codex prompt run to hook ledger, runtime context, runner-issued admission run id, live API lane, recomputed Codex exec transcript digest, source/working proof seals, and final no-product/no-UI/no-native-router packet
- branch: `codex/stabilize-runtime-core`
- head: `3574467ef5a65c310b2e7deccbea9759dac865bd` before the contour commit
- touched files: `wild_boar_proxy/custom_codex_admission.py`, `wild_boar_proxy/user_prompt_submit_hook_producer.py`, `wild_boar_proxy/real_custom_codex_hook_proof.py`, `tests/test_custom_codex_admission.py`, this closeout
- tests run: `python3 -m pytest tests/test_custom_codex_admission.py -q`; `python3 -m pytest tests/test_custom_codex_admission.py tests/test_user_prompt_submit_hook_producer.py tests/test_real_custom_codex_hook_proof.py tests/test_codex_working_flow_delivery_proof.py tests/test_interactive_codex_working_flow_delivery.py tests/test_proof_seal.py -q`; `python3 -m pytest tests/test_cli.py -q -k 'admission or interactive or working_flow_delivery or codex_runner or user_prompt'`; `python3 -m py_compile wild_boar_proxy/custom_codex_admission.py wild_boar_proxy/user_prompt_submit_hook_producer.py wild_boar_proxy/real_custom_codex_hook_proof.py tests/test_custom_codex_admission.py`; `git diff --check`; `make test-core`; live same-turn admission proof and semantic leak check
- blocked risks: weak transcript presence checks, missing runner-issued run-id binding, source seal relying only on empty input hashes, source seal hook-ledger/profile-hook-config digest mismatch gaps, raw prompt/route/expected-text leakage, product/UI/native-router overclaim
- closure state: CLOSED

## Verification

- tests: `tests/test_custom_codex_admission.py` passed with `16 passed, 10 subtests passed`
- tests: expanded admission/proof stack passed with `68 passed, 40 subtests passed`
- tests: targeted CLI selection passed with `4 passed, 492 deselected`
- build: `python3 -m py_compile` completed without output for changed Python files and tests
- build: `git diff --check` completed without output
- build: `make test-core` passed with `418 passed, 120 subtests passed`
- manual: scoped status check confirmed pre-existing dirty UI files stayed outside this contour
- live verification: `/Volumes/Work/wbp-proof-homes/same-turn-admission-live-strong-20260617T203608Z/custom-codex-admission.packet.json` returned `status=ok`, `machine_error_code=OK`, `same_turn_custom_codex_flow_proven=true`, `admission_run_id_digest_bound=true`, `run_id_bound=true`, `prompt_digest_bound=true`, `runtime_context_digest_bound=true`, `codex_exec_transcript_bound=true`, `same_codex_exec_jsonl_bound=true`, `source_seal_runtime_context_digest_bound=true`, `source_seal_hook_ledger_digest_bound=true`, `source_seal_profile_hook_config_digest_bound=true`, `working_flow_seal_input_hashes_bound=true`, `api_lane_called=true`, `external_live_provider_response_proven=true`, `strict_sealed_evidence=true`, `product_ready=false`, `custom_codex_ui_visibility_proven=false`, `native_free_chat_router_proven=false`, `fallback_used=false`, `local_imitation_used=false`, and `native_codex_subagent_used_as_dip=false`

## Artifacts

- packet: `/Volumes/Work/wbp-proof-homes/same-turn-admission-live-strong-20260617T203608Z/custom-codex-admission.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/same-turn-admission-live-strong-20260617T203608Z/user-prompt-submit-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/same-turn-admission-live-strong-20260617T203608Z/working-flow-delivery-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/same-turn-admission-live-strong-20260617T203608Z/custom-origin-proof.strict-sealed.packet.json`
- report: this closeout

## Negative Coverage

- missing runner-issued admission run id digest blocks same-turn admission
- forged Codex exec transcript digest blocks same-turn admission
- echo/provider-like local command does not count as API lane dispatch
- runtime-effective truth mutation blocks admission
- hook prompt digest mismatch blocks admission
- unbound assistant continuation blocks working-flow delivery
- proof seal verification failure blocks admission
- working-flow seal input hash mismatch blocks same-turn admission
- source seal runtime-context digest mismatch blocks same-turn admission
- source seal hook-ledger digest mismatch blocks same-turn admission
- source seal profile-hook-config digest mismatch blocks same-turn admission
- custom-origin proof failure blocks admission
- machine-error-code precedence remains fail-closed for unsafe packet, runtime mutation, Codex launch failure, provider missing, hook proof failure, working-flow failure, seal failure, origin failure, and same-turn binding failure

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat router work mixed in: no
- private-data risk reviewed: yes; final admission packet and semantic inspection keep raw prompt, raw route id, raw provider response, expected text, backend details, and secret values out of browser/packet authority

## Notes

- independent audit verdict: initial BLOCK found weak same-turn binds; rework added transcript digest comparison, runner-issued run-id binding, source seal digest binds, and admission-layer negative coverage
- implementation note: this contour proves same-turn Custom Codex exec/hook/working-flow admission, not product readiness, rendered Custom Codex UI visibility, or a native free-chat router
- blockers encountered: weak same-turn proof fields were strengthened before closeout
- resume from here: CLOSED
