<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Agent Binding Native Hardening Closeout

## Goal

Make Custom Codex GPT-plus-API agent names and aliases behave correctly under real UI entry, native launch, alias variation, and adversarial binding inputs.

## Result

- status: completed
- final verdict: server-owned agent bindings now fail closed, UI writes runtime bindings before session aliases, API-lane alias variants resolve to DeepSeek, primary-lane aliases are blocked before provider calls, and native Custom Codex launch/input plus mixed GPT-plus-API dispatch proof were verified
- closure state: CLOSED

## Contour Capsule

- goal: harden Custom Codex GPT-plus-API names, aliases, runtime projection, UI save semantics, and native evidence surfaces
- branch: codex/stabilize-runtime-core
- head: b5cf1e45b209caab1bbd3fcbf0c42fcf080b2b9a pre-closeout base, with this closeout included in the completed contour commit
- touched files: wild_boar_proxy/custom_agent_bindings.py; wild_boar_proxy/web_design_live_server.py; wild_boar_proxy/web_design_ui/index.html; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_custom_agent_bindings.py; tests/test_web_design_live_server.py; tests/test_web_design_ui.py; audit_results/custom_codex_agent_binding_native_hardening_spec_2026-06-14.md; audit_results/custom_codex_agent_binding_native_hardening_closeout_2026-06-14.md
- tests run: custom binding unit suite; targeted live-server contract suite; targeted UI alias suite; native filesystem runtime-context test; Python compile; whitespace diff check; Browser-driven live UI/native/manual checks
- blocked risks: invalid binding projection; disabled route acceptance; cross-script alias spoofing; hidden codepoint aliases; NFKC duplicate aliases; wrong-lane model/route fields; provider mismatch; rejected runtime binding leaking into session aliases; old window-trace oracle being used for mixed GPT-plus-API proof
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest tests/test_custom_agent_bindings.py -q` -> 14 passed, 11 subtests passed
- tests: `python3 -m pytest tests/test_web_design_live_server.py -k 'window_input_route_trace or chatgpt_plus_api_coder_trace or native_dispatch_proof or agent_bindings or custom_native_runtime_context_exports_persisted_agent_bindings or custom_native_runtime_context_suppresses_rejected_agent_binding_projection or custom_native_runtime_context_blocks_chatgpt_plus_api_provider_mismatch or custom_native_acceptance_smoke or acceptance_response_validation or custom_native_file_bridge_worker or registry_routes_have_get_and_post_dispatch_bindings' -q` -> 37 passed, 300 deselected, 13 subtests passed
- tests: `python3 -m pytest tests/test_web_design_live_server.py -k 'custom_window_prompt_trace' -q` -> 5 passed, 332 deselected
- tests: `python3 -m pytest tests/test_web_design_ui.py -k 'agent_aliases or stale_agent_alias_binding or runtime_binding' -q` -> 4 passed, 117 deselected
- tests: `python3 -m pytest tests/test_native_filesystem_probe.py -k 'agent_runtime_context' -q` -> 1 passed, 264 deselected
- build: `python3 -m py_compile wild_boar_proxy/custom_agent_bindings.py wild_boar_proxy/web_design_live_server.py` -> passed
- build: `git diff --check` -> passed
- manual: Browser UI saved `Planner`/`Builder`/`Lead`/`Worker` as runtime bindings with `proven:true`; zero-width `Bui\u200blder` returned `proven:false` and did not overwrite persisted good state; fullwidth aliases normalized to ASCII server bindings
- live verification: paced alias matrix proved `Builder`, `builder`, ` Builder `, `Worker`, `DIP`, `Agent 2`, `2`, and `Ｂｕｉｌｄｅｒ` as API aliases for provider `deepseek`, route `wbp-deepseek-chat`
- live verification: paced primary matrix blocked `Planner`, `planner`, ` Lead `, `Codex`, `Agent 1`, `1`, and `Ｐｌａｎｎｅｒ` with `CUSTOM_CODEX_AGENT_ALIAS_NOT_API_ROUTE`
- live verification: Custom Codex native launch returned `status: ok`, `native_app_usable: true`, `input_capable_ui_observed: true`, `bridge_alive: true`, and `launch_claim_scope: custom_native_app_window_launch_only`
- live verification: native prompt surface accepted bounded CDP keyboard text, send control became enabled, and the test text was cleared without prompt submission
- live verification: `/api/codex/custom/native-dispatch-proof` returned `status: ok`, `final_status: CHATGPT_PLUS_API_ROUTE_PROVEN_WITH_LIMITS`, `slot_binding_proven: true`, `coder_dispatch_proven: true`, provider `deepseek`, no fallback, and no secret exposure
- live verification: test runtime state was restored to `source: server_default`, `state_file_present: false`, and the Custom Codex test process was closed

## Artifacts

- spec: audit_results/custom_codex_agent_binding_native_hardening_spec_2026-06-14.md
- packet: compact live packets recorded in the working log for UI save/reject/fullwidth normalization, paced alias matrix, native input verification, and native dispatch proof
- report: independent audit findings from Beauvoir and native-path inventory from Hegel were closed or converted into tests

## Git

- branch: codex/stabilize-runtime-core
- commit: completed contour commit containing this closeout and scoped implementation changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no release work, rich UI design expansion, or unrelated runtime repair included
- private-data risk reviewed: raw prompts, auth headers, backend details, and secret values were not recorded; live evidence records route ids, provider id, machine status, and bounded hashes/status fields only

## Notes

- blockers encountered: initial native acceptance matrix was run before a fresh launch context and hit rate limiting; the cause was localized, a fresh native launch was run, and the paced matrix passed
- resume from here: CLOSED
