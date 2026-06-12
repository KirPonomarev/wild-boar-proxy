<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# ChatGPT Plus API Product Path Proof R1 Closeout

## Goal

Prove the product path for ChatGPT primary execution with API/DeepSeek coding
dispatch through the Wild Boar Proxy quick-start surface, without fallback,
browser-supplied authority, raw backend disclosure, or fake readiness.

## Result

- status: PASS
- final verdict: ChatGPT + API product path proven with runtime truth packet and operator checkpoint
- closure state: CLOSED

## Contour Capsule

- goal: Prove ChatGPT primary plus API/DeepSeek coding dispatch from the product quick-start action.
- branch: codex/stabilize-runtime-core
- head: ac0bb2d8 pre-closeout base, with this closeout committed in the closure commit
- touched files: wild_boar_proxy/codex_custom_sessions.py; wild_boar_proxy/operator_surface.py; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_codex_custom_sessions.py; tests/test_operator_surface.py; tests/test_web_design_live_server.py; tests/test_web_design_ui.py; audit_results/chatgpt_plus_api_product_path_proof_r1_2026-06-12/closeout.md
- tests run: python3 -m pytest -q tests/test_operator_surface.py tests/test_codex_custom_sessions.py tests/test_web_design_live_server.py tests/test_web_design_ui.py -k 'dual_lane or mixed_slot_dispatch_probe or chatgpt_plus_api_coder_trace or native_dispatch_proof or quick_start'; python3 -m pytest -q tests/test_web_design_ui.py -k 'quick_start_mixed_blocked_button_runs_native_launch_chain or quick_start'; python3 -m pytest -q tests/test_web_design_live_server.py -k 'native_dispatch_proof or chatgpt_plus_api_coder_trace'; git diff --check
- blocked risks: No open blocker in the closed contour; history chip remains informational and was not used as readiness proof.
- closure state: CLOSED

## Verification

- tests: focused contour suite passed, 76 passed and 471 deselected; quick-start UI focused suite passed, 35 passed and 83 deselected; live-server focused suite passed, 16 passed and 306 deselected
- build: git diff --check passed
- manual: operator checkpoint PASS after refresh and pressing "Проверить GPT+API"
- live verification: trace endpoint returned status=ok, machine_error_code=OK, mixed_mode_product_decision=WORKS, runtime_readiness_claimed=True, launch_proven=True, prompt_seen=True, coder_dispatch_proven=True, deepseek_route_observed=True, coder_work_result_proven_with_limits=True, next_action=none

## Artifacts

- spec: current thread contour
- packet: http://127.0.0.1:8788/api/codex/custom/chatgpt-plus-api-coder-trace during the operator checkpoint
- report: this closeout

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped implementation changes
- pushed: closure push

## Scope Check

- unrelated work mixed in: No unrelated files outside the ChatGPT+API/DeepSeek product proof path.
- private-data risk reviewed: No raw prompt body, secret value, raw backend details, or browser authority accepted as proof.

## Notes

- blockers encountered: product path initially required manual prompt proof; the closed implementation added server-owned native dispatch proof and UI truth propagation.
- resume from here: CLOSED
