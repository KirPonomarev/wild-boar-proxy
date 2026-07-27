<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Agent Binding Runtime Contract Closeout

## Goal

Make Wild Boar Proxy the server-owned source of truth for Custom Codex agent aliases, roles, lanes, and API-route bindings, then export that truth into the Custom Codex runtime context and acceptance smoke path.

## Result

- status: completed
- final verdict: alias-to-route runtime contract is implemented with server validation, runtime context export, web JSON read/probe/write surfaces, unit coverage, live DeepSeek alias smoke, and independent audit follow-up fixed
- closure state: CLOSED

## Contour Capsule

- goal: Custom Codex aliases such as Codex, DIP, Agent 1, and Agent 2 resolve from server-owned binding state into runtime context and API-route acceptance checks
- branch: codex/stabilize-runtime-core
- head: 63b61300bb99cf0a43875b90ca9d3fdf0ae42128 pre-closeout base, with this closeout included in the completed contour commit
- touched files: wild_boar_proxy/custom_agent_bindings.py; wild_boar_proxy/web_design_live_server.py; tests/test_custom_agent_bindings.py; tests/test_web_design_live_server.py; audit_results/custom_codex_agent_binding_runtime_contract_spec_2026-06-14.md; audit_results/custom_codex_agent_binding_runtime_contract_closeout_2026-06-14.md
- tests run: pytest binding/web/runtime targeted suites; native runtime context probe; py_compile changed modules; git diff whitespace check; live alias DeepSeek smoke through local WBP bridge
- blocked risks: empty route registry false-green; invalid persisted state fallback; duplicate or unknown alias; disabled alias; primary-lane alias used as API agent; stale wbp-deepseek-v3 route; browser backend, URL, or secret intake; provider fallback or wrong provider output
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest tests/test_custom_agent_bindings.py tests/test_web_design_live_server.py -k 'agent_bindings or custom_native_runtime_context_exports_persisted_agent_bindings or custom_native_acceptance_smoke or acceptance_response_validation or custom_native_file_bridge_worker or registry_routes_have_get_and_post_dispatch_bindings'` -> 19 passed
- build: `python3 -m py_compile wild_boar_proxy/custom_agent_bindings.py wild_boar_proxy/web_design_live_server.py` -> passed
- manual: `python3 -m pytest tests/test_native_filesystem_probe.py -k 'agent_runtime_context'` -> 1 passed; route table dispatch registration test included in targeted web suite
- live verification: `DIP` alias smoke resolved to `wbp-deepseek-chat`, provider `deepseek`, machine_error_code `OK`, final_status `CUSTOM_CODEX_AGENT_ALIAS_ROUTE_ACCEPTANCE_SMOKE_PROVEN_WITH_LIMITS`

## Artifacts

- spec: audit_results/custom_codex_agent_binding_runtime_contract_spec_2026-06-14.md
- packet: live alias smoke compact JSON recorded in the working log with `agent_alias_route_acceptance_proven: true`
- report: independent mini-audit found one medium route-registry false-green risk, fixed by requiring non-empty server route registry for API-route bindings and adding regression coverage

## Git

- branch: codex/stabilize-runtime-core
- commit: completed contour commit containing this closeout and scoped implementation changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no UI polish, design expansion, release work, or unrelated runtime repair included
- private-data risk reviewed: browser payloads cannot supply backend, base URL, endpoint, raw backend, secret, secret_ref, or token fields; live smoke output recorded only route id, provider name, alias, and machine status

## Notes

- blockers encountered: route-registry false-green risk and invalid state fallback risk were localized, guarded, and covered by tests before closure
- resume from here: CLOSED
