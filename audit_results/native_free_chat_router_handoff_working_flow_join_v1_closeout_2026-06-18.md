<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Native Free-Chat Router Handoff Working-Flow Join v1 Closeout

## Goal

Prove a narrow handoff-to-working-flow join contour:

`dispatch-admission packet -> dispatch-handoff file -> Codex exec JSONL tool result -> assistant continuation digest marker`

The contour explicitly did not claim product readiness, Custom Codex UI
visibility, live provider proof, or completed native free-chat router product
readiness.

## Result

- status: ok
- final verdict: closed with positive handoff-to-working-flow join proof
- closure state: CLOSED

## Contour Capsule

- goal: prove that a dispatch-admission handoff file can be joined into a bounded Codex working-flow transcript and assistant continuation without product/UI/native-router overclaim
- branch: codex/stabilize-runtime-core
- head: 5d687d48 before commit
- touched files:
  - wild_boar_proxy/native_free_chat_router_handoff_working_flow_join.py
  - wild_boar_proxy/cli.py
  - tests/test_native_free_chat_router_handoff_working_flow_join.py
  - audit_results/native_free_chat_router_handoff_working_flow_join_v1_closeout_2026-06-18.md
- tests run:
  - python3 -m pytest -q tests/test_native_free_chat_router_handoff_working_flow_join.py
  - python3 -m pytest -q tests/test_native_free_chat_router_dispatch_admission.py
  - python3 -m pytest -q tests/test_codex_transcript_delivery_observation.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_working_flow_delivery_proof.py
  - python3 -m pytest -q tests/test_cli.py
  - python3 -m pytest -q tests/test_native_free_chat_router_handoff_working_flow_join.py tests/test_native_free_chat_router_dispatch_admission.py tests/test_codex_transcript_delivery_observation.py tests/test_codex_exec_assistant_continuation_proof.py tests/test_codex_working_flow_delivery_proof.py
  - python3 -m py_compile wild_boar_proxy/native_free_chat_router_handoff_working_flow_join.py wild_boar_proxy/cli.py
  - git diff --check
  - make test-core
  - live packet no-leak and command-packet semantics scan
  - independent read-only audit
- blocked risks: product-ready, Custom Codex UI visibility, native free-chat router proof, native free-chat router product readiness, live provider proof, fallback, local imitation, native Codex subagent-as-DIP, raw prompt, raw JSONL, raw route id, and raw provider response claims remain explicitly false
- closure state: CLOSED

## Verification

- tests:
  - tests/test_native_free_chat_router_handoff_working_flow_join.py: 6 passed
  - tests/test_native_free_chat_router_dispatch_admission.py: 3 passed, 3 subtests passed
  - transcript/assistant/working-flow focused stack: 27 passed, 20 subtests passed
  - tests/test_cli.py: 496 passed, 115 subtests passed
  - final focused regression stack: 36 passed, 23 subtests passed
  - make test-core: 418 passed, 120 subtests passed
- build: not applicable
- manual: live proof-home run used user_prompt_submit_hook_producer run-hook, router-hook dispatch-admission, and router-hook handoff-working-flow-join
- live verification:
  - handoff_to_working_flow_join_proven=true
  - dispatch_admission_proven=true
  - dispatch_result_digest_bound=true
  - handoff_evidence_digest_bound=true
  - approved_handoff_source_used=true
  - assistant_continuation_bound_to_handoff=true
  - codex_working_flow_delivery_proven=true
  - custom_codex_ui_visibility_proven=false
  - native_free_chat_router_proven=false
  - product_ready=false
  - fallback_used=false
  - local_imitation_used=false
  - native_codex_subagent_used_as_dip=false
  - no-leak and command-packet semantics scan returned no failures

## Artifacts

- spec: thread-local contour plan only
- packet: /Volumes/Work/wbp-proof-homes/native-free-chat-router-handoff-working-flow-join-live-20260617T221158Z/handoff-working-flow-join.packet.json
- report:
  - /Volumes/Work/wbp-proof-homes/native-free-chat-router-handoff-working-flow-join-live-20260617T221158Z/dispatch-admission.packet.json
  - /Volumes/Work/wbp-proof-homes/native-free-chat-router-handoff-working-flow-join-live-20260617T221158Z/dispatch-handoff.json
  - /Volumes/Work/wbp-proof-homes/native-free-chat-router-handoff-working-flow-join-live-20260617T221158Z/codex-exec.jsonl
  - independent audit result: PASS

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and are outside this contour
- private-data risk reviewed: yes; live artifacts were scanned for raw prompt, raw route id, provider details, command packet semantic errors, and secret leaks

## Notes

- blockers encountered: none
- resume from here: CLOSED
