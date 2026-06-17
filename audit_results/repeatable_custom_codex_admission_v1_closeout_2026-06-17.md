<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Repeatable Custom Codex Admission v1 Closeout

## Goal

Add a repeatable admission runner that proves a Custom Codex `UserPromptSubmit`
flow can be bound to the WBP hook ledger, runtime context, server-issued API
lane command, live provider response, Codex working-flow delivery, and strict
sealed origin proof without claiming product readiness, Custom Codex UI
visibility, or native free-chat router readiness.

## Result

- status: closed
- final verdict: positive admission proof accepted
- closure state: CLOSED

## Contour Capsule

- goal: repeatable Custom Codex admission through hook ledger, context/allowlist binding, live API lane, working-flow delivery, strict sealed proof, and no product/UI/native-router overclaim
- branch: `codex/stabilize-runtime-core`
- head: `756ace9d08033352c8479cfb9cd46e284d68d93b` before the contour commit
- touched files: `wild_boar_proxy/custom_codex_admission.py`, `wild_boar_proxy/cli.py`, `tests/test_custom_codex_admission.py`, this closeout
- tests run: `python3 -m pytest tests/test_custom_codex_admission.py -q`; `python3 -m pytest tests/test_custom_codex_admission.py tests/test_real_custom_codex_hook_proof.py tests/test_codex_working_flow_delivery_proof.py tests/test_custom_codex_hook_origin_proof.py tests/test_proof_seal.py tests/test_user_prompt_submit_hook_producer.py tests/test_cli_runner.py -q`; `python3 -m py_compile wild_boar_proxy/custom_codex_admission.py wild_boar_proxy/cli.py tests/test_custom_codex_admission.py`; `make test-core`; live packet semantic inspection
- blocked risks: first live admission run failed to observe the live provider packet because the runner selected the empty profile-managed external-models registry; the runner now selects the server-owned registry that contains a context route, and negative coverage guards live-provider lookalikes, hook digest mismatch, working-flow binding failure, seal failure, origin failure, runtime truth mutation, and machine-error precedence
- closure state: CLOSED

## Verification

- tests: `10 passed, 9 subtests passed` for admission runner tests
- tests: `96 passed, 42 subtests passed` for the expanded admission/proof stack
- build: `python3 -m py_compile` completed without output for changed Python files
- build: `make test-core` passed with `418 passed, 120 subtests passed`
- manual: scoped status check confirmed pre-existing dirty UI files were not part of this contour
- live verification: `/Volumes/Work/wbp-proof-homes/custom-codex-admission-20260617T-live-env-fixed/custom-codex-admission.packet.json` has `status=ok`, `machine_error_code=OK`, `admission_proven=true`, `repeatable_custom_codex_admission_proven=true`, `custom_codex_flow_proven=true`, `user_prompt_submit_hook_ran=true`, `hook_ledger_bound=true`, `runtime_context_bound=true`, `server_issued_cli_command_bound=true`, `api_lane_called=true`, `external_live_provider_response_proven=true`, `codex_working_flow_delivery_proven=true`, `strict_sealed_evidence=true`, `proof_seal_verified=true`, `runtime_effective_truth_unchanged=true`, `product_ready=false`, `custom_codex_ui_visibility_proven=false`, `native_free_chat_router_proven=false`, `fallback_used=false`, `local_imitation_used=false`, and `native_codex_subagent_used_as_dip=false`

## Artifacts

- packet: `/Volumes/Work/wbp-proof-homes/custom-codex-admission-20260617T-live-env-fixed/custom-codex-admission.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/custom-codex-admission-20260617T-live-env-fixed/user-prompt-submit-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/custom-codex-admission-20260617T-live-env-fixed/working-flow-delivery-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/custom-codex-admission-20260617T-live-env-fixed/custom-origin-proof.strict-sealed.packet.json`
- report: this closeout

## Negative Coverage

- fake provider echo command does not count as API lane dispatch
- runtime-effective truth mutation blocks admission
- hook prompt digest mismatch blocks admission
- unbound assistant continuation blocks working-flow delivery
- proof seal verification failure blocks admission
- custom-origin proof failure blocks admission
- machine-error-code precedence remains fail-closed for unsafe packet, runtime mutation, Codex launch failure, provider missing, hook proof failure, working-flow failure, seal failure, and origin failure

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

- independent audit verdict: no confirmed runtime bug on the admission path; the auditor found a negative-coverage gap, which was closed before commit
- implementation note: this contour proves repeatable admission through Custom Codex exec/hook flow and live API lane, not product readiness, rendered Custom Codex UI visibility, or a native free-chat router
- blockers encountered: first live run lacked a matching route registry in the runner environment; server-owned route registry selection fixed the failure and the live proof passed afterward
- resume from here: CLOSED
