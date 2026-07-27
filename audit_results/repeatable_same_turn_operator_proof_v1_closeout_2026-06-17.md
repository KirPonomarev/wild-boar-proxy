<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Repeatable Same-Turn Operator Proof v1 Closeout

## Goal

Prove a repeatable operator-owned same-turn Custom Codex proof path by running
two independent same-turn admission proofs for the same natural prompt, joining
their file-backed evidence, and emitting a final strict packet that proves
repeatability without claiming product readiness, rendered Custom Codex UI
visibility, or native free-chat router readiness.

## Result

- status: closed
- final verdict: positive repeatable same-turn operator proof accepted with run-id, transcript, invariant, and no-leak guards
- closure state: CLOSED

## Contour Capsule

- goal: run two WBP-owned same-turn Custom Codex admission proofs, require distinct admission run-id digests and stable invariant digest, and produce one final operator packet with API lane proof and false product/UI/native-router claims
- branch: `codex/stabilize-runtime-core`
- head: `d003476df919f5e82833288230f865b42524685a` before the contour commit
- touched files: `wild_boar_proxy/custom_codex_operator_proof.py`, `wild_boar_proxy/cli.py`, `tests/test_custom_codex_operator_proof.py`, `tests/test_cli.py`, this closeout
- tests run: `python3 -m py_compile wild_boar_proxy/custom_codex_operator_proof.py tests/test_custom_codex_operator_proof.py`; `python3 -m pytest tests/test_custom_codex_operator_proof.py -q`; `python3 -m pytest tests/test_custom_codex_operator_proof.py tests/test_custom_codex_admission.py tests/test_user_prompt_submit_hook_producer.py tests/test_real_custom_codex_hook_proof.py tests/test_codex_working_flow_delivery_proof.py tests/test_interactive_codex_working_flow_delivery.py tests/test_proof_seal.py -q`; `python3 -m pytest tests/test_cli.py -q -k 'codex_runner or operator-proof or operator or admission or interactive or working_flow_delivery'`; live repeatable operator proof; live packet semantic/no-leak check; `git diff --check`; `make test-core`
- blocked risks: replayed admission run-id false green, missing admission run-id digest, prompt digest drift across runs, unstable operator invariant digest, raw prompt/route/expected-text leakage, admission packet tool/route/detail recording, local imitation, fallback use, product/UI/native-router overclaim
- closure state: CLOSED

## Verification

- tests: `tests/test_custom_codex_operator_proof.py` passed with `6 passed, 10 subtests passed`
- tests: expanded admission/proof stack passed with `74 passed, 50 subtests passed`
- tests: targeted CLI selection passed with `9 passed, 487 deselected`
- build: `python3 -m py_compile` completed without output for changed operator proof code and tests
- build: `git diff --check` completed without output
- build: `make test-core` passed with `418 passed, 120 subtests passed`
- manual: live packet semantic/no-leak inspection returned `semantic_violations=[]`, `leaks=[]`, `status=ok`, and `machine_error_code=OK`
- manual: scoped status checks confirmed pre-existing dirty UI files stayed outside this contour
- audit: independent read-only auditor Newton returned `PASS` after checking diff, CLI effect, false-green guards, live packet boundaries, and layer separation
- live verification: `/Volumes/Work/wbp-proof-homes/repeatable-operator-proof-live-20260617T205457Z/repeatable-same-turn-operator-proof.packet.json` returned `status=ok`, `machine_error_code=OK`, `repeatable_same_turn_operator_proof_proven=true`, `same_turn_custom_codex_flow_proven=true`, `operator_run_count=2`, `required_operator_run_count=2`, `two_live_runs_proven=true`, `admission_run_ids_distinct=true`, `admission_run_id_reused=false`, `prompt_digest_consistent=true`, `operator_invariant_digest_consistent=true`, `hook_ledger_fresh=true`, `runtime_context_digest_bound=true`, `api_lane_called=true`, `external_live_provider_response_proven=true`, `codex_exec_transcript_bound=true`, `assistant_continuation_proven=true`, `fallback_used=false`, `local_imitation_used=false`, `native_codex_subagent_used_as_dip=false`, `product_ready=false`, `custom_codex_ui_visibility_proven=false`, and `native_free_chat_router_proven=false`

## Artifacts

- packet: `/Volumes/Work/wbp-proof-homes/repeatable-operator-proof-live-20260617T205457Z/repeatable-same-turn-operator-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/repeatable-operator-proof-live-20260617T205457Z/run_1/custom-codex-admission.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/repeatable-operator-proof-live-20260617T205457Z/run_2/custom-codex-admission.packet.json`
- command: `wild-boar-proxy codex-runner operator-proof --prompt <natural prompt> --codex-bin <custom codex bin> --proof-dir <proof root> --codex-cwd /Volumes/Work/wild-boar-proxy --expected-text <expected text> --sandbox danger-full-access --json`
- report: this closeout

## Negative Coverage

- reused admission run-id digest blocks operator proof
- missing admission run-id digest blocks operator proof
- stable invariant digest mismatch blocks operator proof
- missing fresh hook ledger blocks operator proof
- missing runtime context digest binding blocks operator proof
- missing API lane call blocks operator proof
- local imitation blocks operator proof
- recorded tool-call arguments block operator proof
- recorded selected API route id blocks operator proof
- recorded expected text blocks operator proof
- product-ready overclaim blocks operator proof
- Custom Codex UI visibility overclaim blocks operator proof
- native free-chat router overclaim blocks operator proof
- final operator packet semantic inspection rejects raw prompt, route id, expected text, backend details, and secret leakage

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat router work mixed in: no
- Codex patch work mixed in: no
- private-data risk reviewed: yes; final operator packet stores digests and file-backed evidence paths, keeps raw prompt, raw route id, selected route id, expected text, raw provider response, tool arguments, backend details, and secret values out of packet authority

## Notes

- blockers encountered: independent audit found a non-blocking coverage gap where operator proof did not re-assert several admission no-leak booleans; the contour strengthened `required_false_fields` and negative tests before closeout
- implementation note: this contour proves repeatable same-turn Custom Codex exec/hook/API-lane working-flow admission under the operator command, not product readiness, rendered Custom Codex UI visibility, or a native free-chat router
- resume from here: CLOSED
