<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Native Free-Chat Router Dispatch Admission v1 Closeout

## Goal

Prove a narrow dispatch-admission contour:

`UserPromptSubmit hook ledger -> WBP alias router -> runtime context/allowlist -> controlled API lane -> proof-backed handoff file`

The contour explicitly did not claim product readiness, Custom Codex UI visibility,
or completed native free-chat delivery.

## Result

- status: ok
- final verdict: closed with positive dispatch-admission proof
- closure state: CLOSED

## Contour Capsule

- goal: prove WBP-owned dispatch admission from a file-backed UserPromptSubmit hook ledger into the API lane, with a sanitized handoff evidence file and no product/UI overclaim
- branch: codex/stabilize-runtime-core
- head: d3019e55 before commit
- touched files:
  - wild_boar_proxy/native_free_chat_router_dispatch_admission.py
  - wild_boar_proxy/cli.py
  - tests/test_native_free_chat_router_dispatch_admission.py
  - audit_results/native_free_chat_router_dispatch_admission_v1_closeout_2026-06-18.md
- tests run:
  - python3 -m pytest tests/test_native_free_chat_router_dispatch_admission.py -q
  - python3 -m pytest tests/test_user_prompt_submit_hook_producer.py tests/test_real_custom_codex_hook_proof.py -q
  - python3 -m pytest tests/test_router_hook_entry.py tests/test_controlled_api_dispatch.py tests/test_controlled_ingress_api_dispatch_proof.py tests/test_controlled_dispatch_handoff_proof.py tests/test_approved_handoff.py -q
  - python3 -m pytest tests/test_cli.py -q
  - make test-core
  - live packet and handoff no-leak script
  - independent read-only audit
- blocked risks: product-ready, Custom Codex UI visibility, native free-chat delivery, live provider proof, raw prompt, raw route id, fallback, local imitation, and native Codex subagent claims remain explicitly false
- closure state: CLOSED

## Verification

- tests:
  - tests/test_native_free_chat_router_dispatch_admission.py: 3 passed, 3 subtests passed
  - tests/test_user_prompt_submit_hook_producer.py and tests/test_real_custom_codex_hook_proof.py: 26 passed, 26 subtests passed
  - router/dispatch/handoff focused stack: 50 passed, 75 subtests passed
  - tests/test_cli.py: 496 passed, 115 subtests passed
  - make test-core: 418 passed, 120 subtests passed
- build: not applicable
- manual: live proof-home run used real user_prompt_submit_hook_producer run-hook, then router-hook dispatch-admission
- live verification:
  - native_free_chat_router_dispatch_admission_proven=true
  - api_lane_called=true
  - handoff_file_written=true
  - product_ready=false
  - custom_codex_ui_visibility_proven=false
  - native_free_chat_router_proven=false
  - live packet and handoff no-leak scan returned no failures

## Artifacts

- spec: thread-local contour plan only
- packet: /Volumes/Work/wbp-proof-homes/native-free-chat-router-dispatch-admission-live-20260617T214344Z/native-free-chat-router-dispatch-admission.packet.json
- report:
  - /Volumes/Work/wbp-proof-homes/native-free-chat-router-dispatch-admission-live-20260617T214344Z/dispatch-handoff.json
  - independent audit result: PASS

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and are outside this contour
- private-data risk reviewed: yes; live packet and handoff were scanned for raw prompt, raw route id, and command packet secret leaks

## Notes

- blockers encountered: none
- resume from here: CLOSED
