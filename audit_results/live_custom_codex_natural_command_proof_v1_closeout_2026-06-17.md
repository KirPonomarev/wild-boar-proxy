<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Live Custom Codex Natural Command Proof v1 Closeout

## Goal

Prove that a natural command submitted through the Custom Codex flow can be
bound to a WBP `UserPromptSubmit` hook ledger, dispatch through the WBP API
lane, call the live provider route, and return a digest-bound result into the
Codex working flow without claiming product readiness or Custom Codex UI
visibility.

## Result

- status: closed
- final verdict: positive proof accepted after verifier hardening
- closure state: CLOSED

## Contour Capsule

- goal: live Custom Codex natural command proof with hook ledger, API lane, CLI-bound provider call, working-flow delivery, and strict sealed origin join
- branch: `codex/stabilize-runtime-core`
- head: `8ef35b2c1a8ff50efce30471796cc5abc202121a`
- touched files: `wild_boar_proxy/real_custom_codex_hook_proof.py`, `wild_boar_proxy/codex_working_flow_delivery_proof.py`, `wild_boar_proxy/custom_codex_hook_origin_proof.py`, `wild_boar_proxy/codex_exec_assistant_continuation_proof.py`, `tests/test_codex_working_flow_delivery_proof.py`, `tests/test_custom_codex_hook_origin_proof.py`, this closeout
- tests run: `python3 -m pytest tests/test_codex_working_flow_delivery_proof.py tests/test_custom_codex_hook_origin_proof.py tests/test_real_custom_codex_hook_proof.py tests/test_codex_exec_assistant_continuation_proof.py -q`; `python3 -m pytest tests/test_codex_working_flow_delivery_proof.py tests/test_custom_codex_hook_origin_proof.py tests/test_real_custom_codex_hook_proof.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_custom_codex_approved_visible_source_observation.py tests/test_user_prompt_submit_hook_producer.py tests/test_proof_seal.py tests/test_approved_handoff.py tests/test_observed_machine_handoff_delivery.py -q`; `python3 -m pytest tests/test_cli.py -q`; `make test-core`; packet semantic/leak checks on real proof artifacts
- blocked risks: initial command-execution verifier accepted lookalike commands; strict origin join did not reject non-empty command failure lists; broad subagent text detection treated negative instructions as subagent usage; all were reproduced or localized, guarded, and retested
- closure state: CLOSED

## Verification

- tests: `100 passed, 93 subtests passed`; `496 passed, 113 subtests passed`; `418 passed, 120 subtests passed`
- build: `python3 -m py_compile` passed for changed proof modules
- manual: live Custom Codex `codex exec` prompt produced `DIP_API_OK` after loopback bridge failure and file bridge timeout, using the server-issued CLI route from runtime context
- live verification: `/Volumes/Work/wbp-proof-homes/live-custom-natural-command-20260617T180616Z-cli-bound/custom-origin-proof.strict-sealed.packet.json` has `status=ok`, `machine_error_code=OK`, `strict_sealed_evidence=true`, `command_origin_proven=true`, `custom_codex_flow_proven=true`, `api_lane_called=true`, `external_live_provider_response_proven=true`, `codex_working_flow_delivery_proven=true`, `product_ready=false`, `custom_codex_ui_visibility_proven=false`, `native_free_chat_router_proven=false`, and empty `blocking_reasons`

## Artifacts

- spec: current thread contour text
- packet: `/Volumes/Work/wbp-proof-homes/live-custom-natural-command-20260617T180616Z-cli-bound/user-prompt-submit-proof.packet.json`; `/Volumes/Work/wbp-proof-homes/live-custom-natural-command-20260617T180616Z-cli-bound/working-flow-delivery-proof.packet.json`; `/Volumes/Work/wbp-proof-homes/live-custom-natural-command-20260617T180616Z-cli-bound/custom-origin-proof.strict-sealed.packet.json`
- report: this closeout

## Git

- branch: `codex/stabilize-runtime-core`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were not staged or edited by this contour
- private-data risk reviewed: yes; joined proof packets were checked for raw prompt, raw route id, raw provider response, and raw expected prompt values

## Notes

- blockers encountered: read-only Custom Codex run could not complete API lane; one live run lacked `WBP_PROFILE_DIR` in the Codex process and correctly returned `FAIL_ALIAS_CONTEXT_MISSING`; one live run stopped after file bridge `TIMEOUT`; the accepted live run used explicit `WBP_PROFILE_DIR`, observed bridge failures, then used the server-issued CLI command
- resume from here: CLOSED
