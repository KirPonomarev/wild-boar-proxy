<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Interactive Custom Codex Proof v1 Closeout

## Goal

Add a bounded proof harness that prepares an operator-driven Custom Codex prompt
submission, requires a fresh `UserPromptSubmit` hook ledger, joins that ledger
to runtime context and a live API lane response, and emits a strict proof packet
without claiming product readiness, rendered Custom Codex UI visibility, Codex
working-flow delivery, or native free-chat router readiness.

## Result

- status: closed
- final verdict: positive interactive proof accepted with approved handoff only
- closure state: CLOSED

## Contour Capsule

- goal: interactive Custom Codex proof preflight and collector with fresh hook ledger, context/allowlist binding, live API lane, approved handoff, source proof seal, and no product/UI/native-router overclaim
- branch: `codex/stabilize-runtime-core`
- head: `1845e4bab7926462eca9008bee7c257b4217e3c8` before the contour commit
- touched files: `wild_boar_proxy/interactive_custom_codex_proof.py`, `wild_boar_proxy/cli.py`, `tests/test_interactive_custom_codex_proof.py`, this closeout
- tests run: `python3 -m pytest tests/test_interactive_custom_codex_proof.py -q`; `python3 -m py_compile wild_boar_proxy/interactive_custom_codex_proof.py wild_boar_proxy/cli.py tests/test_interactive_custom_codex_proof.py`; `python3 -m pytest tests/test_interactive_custom_codex_proof.py tests/test_custom_codex_admission.py tests/test_real_custom_codex_hook_proof.py tests/test_user_prompt_submit_hook_producer.py tests/test_proof_seal.py tests/test_cli_runner.py -q`; `make test-core`; `python3 -m pytest tests/test_cli.py tests/test_interactive_custom_codex_proof.py -q`; live packet semantic inspection
- blocked risks: independent audit found three truth gaps before commit: registry guard accepted any truthy path, absent ledger was reported in `changed_files`, and suppressed live-provider metadata claimed a file had been read; all three were fixed and covered by regression tests
- closure state: CLOSED

## Verification

- tests: `7 passed` for interactive proof tests
- tests: `72 passed, 35 subtests passed` for the expanded interactive/admission/proof stack
- tests: `503 passed, 113 subtests passed` for CLI plus interactive proof tests
- build: `python3 -m py_compile` completed without output for changed Python files
- build: `make test-core` passed with `418 passed, 120 subtests passed`
- manual: scoped `git diff --check` completed without output for contour files
- live verification: `/Volumes/Work/wbp-proof-homes/interactive-custom-codex-proof-20260617T192827Z/interactive-custom-codex-proof.packet.json` has `status=ok`, `machine_error_code=OK`, `interactive_custom_codex_flow_proven=true`, `hook_ledger_fresh=true`, `user_prompt_submit_hook_ran=true`, `hook_prompt_digest_bound=true`, `hook_runtime_context_digest_bound=true`, `api_lane_called=true`, `external_live_provider_response_proven=true`, `approved_handoff_proven=true`, `strict_sealed_evidence=true`, `proof_seal_verified=true`, `product_ready=false`, `custom_codex_ui_visibility_proven=false`, `native_free_chat_router_proven=false`, `codex_working_flow_delivery_proven=false`, and empty `blocking_reasons`

## Artifacts

- packet: `/Volumes/Work/wbp-proof-homes/interactive-custom-codex-proof-20260617T192827Z/interactive-preflight.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/interactive-custom-codex-proof-20260617T192827Z/interactive-live-provider.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/interactive-custom-codex-proof-20260617T192827Z/interactive-user-prompt-submit-proof.packet.json`
- packet: `/Volumes/Work/wbp-proof-homes/interactive-custom-codex-proof-20260617T192827Z/interactive-user-prompt-submit-proof.seal.json`
- packet: `/Volumes/Work/wbp-proof-homes/interactive-custom-codex-proof-20260617T192827Z/interactive-custom-codex-proof.packet.json`
- report: this closeout

## Negative Coverage

- missing or stale hook ledger blocks before live-provider call
- preflight prompt digest mismatch blocks before live-provider call
- selected external-models registry must contain the context route
- absent initial ledger is not reported as a changed file
- suppressed live-provider path does not claim a provider proof file was read
- raw prompt, raw route id, raw provider response, expected text, backend details, and secret values remain absent from the final command packet

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files stayed outside this contour
- UI/product work mixed in: no
- native free-chat router work mixed in: no
- private-data risk reviewed: yes; final packet semantic inspection passed with prompt, route, and expected-text values supplied as secret values

## Notes

- implementation note: this contour proves real Custom Codex prompt submission through the trusted hook ledger and an approved handoff; it deliberately does not prove rendered UI visibility or native free-chat router behavior.
- implementation note: live proof used a real Custom Codex profile prompt submission to create the fresh hook ledger, then the WBP collector performed the live API lane check and joined the result to the proof packet.
- blockers encountered: independent audit found three packet-truth gaps before commit; all were fixed and retested before closeout.
- resume from here: CLOSED
