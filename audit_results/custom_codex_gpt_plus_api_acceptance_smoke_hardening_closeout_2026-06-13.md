<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex GPT Plus API Acceptance Smoke Hardening Closeout

## Goal

Stabilize the Custom Codex GPT-plus-API path with a strict, fresh, exact-response acceptance smoke for the server-owned runtime context and file bridge route to DeepSeek.

## Result

- status: ok
- final verdict: CUSTOM_CODEX_GPT_PLUS_API_FILE_BRIDGE_ACCEPTANCE_SMOKE_PROVEN_WITH_LIMITS
- closure state: CLOSED

## Contour Capsule

- goal: Custom Codex runtime context and file bridge acceptance smoke for wbp-deepseek-chat exact response evidence
- branch: codex/stabilize-runtime-core
- head: 756ef191 base plus this completed contour commit on the pushed branch tip
- touched files: AGENTS.md; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/native_filesystem_probe.py; wild_boar_proxy/native_window_probe.py; wild_boar_proxy/runtime.py; wild_boar_proxy/cli.py; tests/test_web_design_live_server.py; tests/test_native_filesystem_probe.py; tests/test_runtime_native_auth_recovery.py; tests/test_cli.py; audit_results/custom_codex_gpt_plus_api_acceptance_smoke_hardening_closeout_2026-06-13.md
- tests run: python3 -m pytest targeted web/native/cli/runtime set 40 passed; python3 -m pytest explicit acceptance smoke node ids 4 passed; python3 -m py_compile wild_boar_proxy/web_design_live_server.py; git diff --check; route registration probe
- blocked risks: native coder slot dispatch remains outside this contour and is explicitly reported false by the acceptance smoke packet
- closure state: CLOSED

## Verification

- tests: targeted pytest set passed with 40 passed and 1063 deselected; explicit acceptance smoke tests passed with 4 passed
- build: python3 -m py_compile wild_boar_proxy/web_design_live_server.py passed
- manual: route table lookup returned post_api_codex_custom_chatgpt_plus_api_acceptance_smoke
- live verification: local handler from current worktree returned status ok, machine_error_code OK, provider deepseek, requested_model wbp-deepseek-chat, acceptance_smoke_proven true, final_status CUSTOM_CODEX_GPT_PLUS_API_FILE_BRIDGE_ACCEPTANCE_SMOKE_PROVEN_WITH_LIMITS

## Artifacts

- spec: current thread implementation contour
- packet: live acceptance smoke JSON response with request_id wbp-acceptance-91970fb8d0e74f1ab0b430ed1a348c62 and expected_text WBP_ACCEPTANCE_LIVE_b836eb7e8302
- report: this closeout

## Git

- branch: codex/stabilize-runtime-core
- commit: completed contour commit containing this closeout
- pushed: yes after successful commit and push

## Scope Check

- unrelated work mixed in: no UI polish, release work, or design expansion; inherited Custom Codex runtime-context dirty tail was completed as one execution-core contour
- private-data risk reviewed: yes; smoke packets redact context paths and expose no secret values or raw backend details

## Notes

- blockers encountered: launcher test expectation still referenced the pre-existing inline open-project command shape and was updated to the launch_codex_app helper shape already present in runtime
- resume from here: CLOSED
