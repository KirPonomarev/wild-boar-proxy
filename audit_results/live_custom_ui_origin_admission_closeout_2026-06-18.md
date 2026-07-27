<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Live Custom UI Origin Admission Closeout

## Goal

Prove the narrow live runtime chain:

`real Custom Codex UI submit -> UserPromptSubmit hook -> fresh file-backed ledger -> Custom UI origin admission`

This contour explicitly did not prove API dispatch, provider response, handoff
delivery, Custom Codex UI visibility of an answer, native free-chat router
readiness, ChatGPT UI session readiness, or product readiness.

## Result

- status: ok
- final verdict: closed with live gate-level proof and explicit non-product scope
- closure state: CLOSED

## Contour Capsule

- goal: prove a real Custom Codex submit can reach the trusted UserPromptSubmit hook, write a fresh ledger, and pass Custom UI origin admission without claiming API dispatch or product readiness
- branch: codex/stabilize-runtime-core
- head: 2aa4e328 before closeout commit
- touched files: audit_results/live_custom_ui_origin_admission_closeout_2026-06-18.md
- tests run: python3 -m pytest tests/test_user_prompt_submit_hook_producer.py tests/test_real_user_prompt_submit_ledger_proof.py tests/test_real_custom_app_submit_ledger_proof.py tests/test_custom_ui_origin_admission.py tests/test_custom_codex_auth_session_readiness.py; make test-core; live Custom Codex CDP submit proof; independent read-only packet audit
- blocked risks: API dispatch, provider response, handoff delivery, answer visibility, native free-chat router readiness, ChatGPT UI-session readiness, product readiness, fallback, local imitation, native Codex subagent-as-DIP, raw prompt exposure, raw route id exposure, raw backend/provider detail exposure, and secret exposure remain blocked or explicitly false
- closure state: CLOSED

## Verification

- tests:
  - focused hook/origin suite: 49 passed
  - make test-core: 418 passed, 120 subtests passed
- build: not changed
- manual: Custom Codex WBP Clean launched through LaunchServices with the WBP profile, then a marker prompt was submitted through the live app page over CDP
- live verification:
  - marker prompt digest: 8e92a9c7e7a33395919d014dea04cf10601458cbd4a974ff2fe6c66bc498512d
  - ledger mtime before submit: 1781739274146230279
  - ledger mtime after submit: 1781748680217093486
  - UserPromptSubmit ledger proof: status=ok, machine_error_code=OK
  - Custom app submit ledger proof: status=ok, machine_error_code=OK
  - Custom UI origin admission: status=ok, machine_error_code=OK
  - custom_ui_origin_admitted=true
  - fresh_user_prompt_submit_ledger_proven=true
  - custom_instance_coexistence_proven=true
  - hook_parent_process_chain_custom_wbp_clean_app=true
  - hook_parent_process_chain_app_server=true
  - hook_parent_process_chain_clean_root=true
  - api_lane_called=false
  - dispatch_attempted=false
  - product_ready=false

## Artifacts

- spec: thread-local contour plan only
- packet:
  - /tmp/wbp-user-prompt-ledger-proof.json
  - /tmp/wbp-custom-app-submit-ledger-proof.json
  - /tmp/wbp-custom-ui-origin-admission.json
  - /tmp/wbp-custom-codex-auth-session-readiness-live.json
- report:
  - independent audit confirmed gate-level proof only
  - auth readiness remained red with machine_error_code=WBP_CUSTOM_CODEX_API_KEY_ONLY and blocking_reasons=[api_key_only_not_ui_session]
  - direct canonical launcher path did not keep the app live in this run; LaunchServices launch kept the same Custom app/profile live long enough for proof

## Git

- branch: codex/stabilize-runtime-core
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and outside this contour
- private-data risk reviewed: yes; proof packets report raw_prompt_recorded=false, prompt_text_recorded=false, raw_backend_details_exposed=false, secret_value_exposed=false, and no_secret_exposed=true

## Notes

- blockers encountered: ChatGPT UI-session readiness remains API-key-only; canonical direct launcher did not remain live during this run, while LaunchServices did
- resume from here: CLOSED
