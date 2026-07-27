<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Real Custom App Submit Ledger Gate Closeout

## Goal

Prove a narrow runtime/proof gate:

`real Custom Codex app submit -> UserPromptSubmit hook ledger -> prompt digest/freshness -> bounded Custom app provenance`

This contour explicitly did not prove API dispatch, handoff delivery, Custom
Codex UI visibility, native free-chat router readiness, live provider response,
or product readiness.

## Result

- status: ok
- final verdict: closed with strict code-level gate and blocked live-smoke evidence
- closure state: CLOSED

## Contour Capsule

- goal: add a fail-closed Custom app submit ledger proof gate that distinguishes ledger-only proof from real Custom app submit provenance without claiming dispatch, handoff, UI visibility, or product readiness
- branch: codex/stabilize-runtime-core
- head: 6f7a074b before commit
- touched files:
  - wild_boar_proxy/real_custom_app_submit_ledger_proof.py
  - wild_boar_proxy/user_prompt_submit_hook_producer.py
  - wild_boar_proxy/real_custom_codex_hook_proof.py
  - wild_boar_proxy/real_user_prompt_submit_ledger_proof.py
  - wild_boar_proxy/cli.py
  - tests/test_real_custom_app_submit_ledger_proof.py
  - tests/test_user_prompt_submit_hook_producer.py
  - audit_results/real_custom_app_submit_ledger_gate_closeout_2026-06-18.md
- tests run:
  - python3 -m py_compile wild_boar_proxy/real_custom_app_submit_ledger_proof.py wild_boar_proxy/user_prompt_submit_hook_producer.py wild_boar_proxy/real_custom_codex_hook_proof.py wild_boar_proxy/real_user_prompt_submit_ledger_proof.py wild_boar_proxy/cli.py
  - python3 -m pytest tests/test_real_custom_app_submit_ledger_proof.py tests/test_real_user_prompt_submit_ledger_proof.py tests/test_user_prompt_submit_hook_producer.py tests/test_real_ledger_bound_api_dispatch_proof.py tests/test_native_launch_dispatch.py -q
  - make test-core
  - live Custom app submit ledger verifier smoke
  - independent read-only audit with blockers fixed
- blocked risks: forged process inventory file, command-line substring spoofing, stale ledger, stock Codex app substitution, missing Clean app-server, unsafe source overclaims, API dispatch, handoff, UI visibility, native router, product readiness, raw prompt, raw route id, raw backend/provider details, fallback, local imitation, and native Codex subagent-as-DIP claims remain blocked or explicitly false
- closure state: CLOSED

## Verification

- tests:
  - new focused proof stack: 27 passed
  - expanded ledger/API/native launch stack: 119 passed, 9 subtests passed
  - make test-core: 418 passed, 120 subtests passed
- build: python3 -m py_compile passed for changed Python modules
- manual: Custom WBP Clean app was launched, but AppleScript paste/submit smoke did not create a fresh ledger
- live verification:
  - current live verifier correctly returned error, not green
  - WBP Clean app process observed=true
  - WBP Clean app-server process observed=true
  - stock Codex process also observed=true
  - ledger freshness check blocked stale ledger
  - ledger parent-process chain check blocked old ledger without exact-path provenance
  - hook readiness/live profile state was observed as not trusted after the launch path rewrote profile config
  - api_lane_called=false
  - handoff_file_written=false
  - custom_codex_ui_visibility_proven=false
  - native_free_chat_router_proven=false
  - product_ready=false

## Artifacts

- spec: thread-local contour plan only
- packet: live verifier emitted a blocked command packet in terminal output
- report:
  - independent audit finding: forged process inventory and substring parent-chain risks
  - fix evidence: process-inventory-file cannot green live proof; parent-chain classification now uses executable path and exact-path-bound flags

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and are outside this contour
- private-data risk reviewed: yes; packets keep raw prompt, raw route ids, backend/provider details, raw process lines, and secrets out of browser/packet surfaces

## Notes

- blockers encountered: live GUI submit smoke did not create a fresh ledger; the verifier correctly stayed red instead of claiming product success
- resume from here: CLOSED
