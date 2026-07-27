<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Admitted Model Guard Closeout

## Goal

Prevent bounded Codex exec proof surfaces from misclassifying a ChatGPT-account
model-admission failure as generic auth failure, and provide a fail-closed guard
for the known unsafe `gpt-5.3-codex` default.

## Result

- status: completed
- final verdict: model-admission guard added for the Codex exec proof layer; absent or unsafe default model resolves to `gpt-5.4`, explicit `gpt-5.3-codex` fails closed with `CODEX_MODEL_NOT_ADMITTED`, and unsupported-model exec errors no longer map to generic auth
- closure state: CLOSED

## Contour Capsule

- goal: add a scoped admitted-model guard for ChatGPT-account Codex exec proof packets without changing UI, API-lane, or product-router behavior
- branch: codex/stabilize-runtime-core
- head: acbb7f8a pre-closeout base; closure commit includes this evidence and scoped guard/test changes
- touched files: wild_boar_proxy/mcp_delegate.py; tests/test_mcp_delegate.py; audit_results/admitted_model_guard_closeout_2026-06-16.md
- tests run: targeted MCP/custom/command-packet/CLI-runner tests passed; Python compile passed; line-length and diff whitespace checks passed; `make test-core` passed; closeout resilience check passed before commit
- blocked risks: unsafe default model causing false auth diagnosis; explicit unsupported model being silently substituted; successful ChatGPT-account output being over-classified as auth failure
- closure state: CLOSED

## Verification

- tests: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/test_mcp_delegate.py tests/test_custom_agent_bindings.py tests/test_command_packets_core.py tests/test_cli_runner.py` -> 106 passed, 49 subtests passed
- tests: `PYTHONDONTWRITEBYTECODE=1 make test-core` -> 418 passed, 120 subtests passed
- build: `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- build: line-length guard for `wild_boar_proxy/mcp_delegate.py` and `tests/test_mcp_delegate.py` -> passed
- build: `git diff --check -- wild_boar_proxy/mcp_delegate.py tests/test_mcp_delegate.py` -> passed
- manual: read-only inspector Cicero mapped relevant proof/model-selection surfaces and confirmed existing UI dirty files are outside this contour
- manual: `codex-runner smoke` was inspected as an active command surface and left unchanged because it runs through WBP provider/auth-command, not ChatGPT-account Codex exec

## Artifacts

- spec: current task thread contour plan
- packet: model-admission guard packet fields are covered by unit tests
- report: unsupported-model observation packet now emits `CODEX_MODEL_NOT_ADMITTED` with `codex_exec_unsupported_model_observed=true` and `codex_exec_auth_blocker_observed=false`

## Git

- branch: codex/stabilize-runtime-core
- commit: closure commit containing this closeout and scoped guard/test changes
- pushed: branch push after closure commit

## Scope Check

- unrelated work mixed in: no; pre-existing dirty UI files were left unstaged and untouched
- private-data risk reviewed: auth files, proof-home tree, raw Codex JSONL, stderr, prompt text, tokens, route secrets, and backend details were not recorded

## Notes

- blockers encountered: none after limiting the contour to Codex exec proof packet truth
- resume from here: CLOSED
