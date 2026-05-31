<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WBP Codex CLI Runner Via WBP Smoke R1 Closeout

## Goal

Prove one bounded isolated Codex CLI runner non-stream prompt can route to WBP via `auth.command` using `gpt-5.4-mini`, without claiming native Codex.app, Original lane, direct egress, streaming, tool loop, full wire, or final E2E proof.

## Result

- status: passed
- final verdict: CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP
- closure state: CLOSED

## Contour Capsule

- goal: bounded isolated Codex CLI runner WBP smoke through server-owned auth.command
- branch: codex/external-agent-lab-isolated
- head: c2ed1460 before contour commit
- touched files: wild_boar_proxy/cli_runner_via_wbp.py, wild_boar_proxy/operator_surface.py, tools/cli_runner_via_wbp_smoke_probe.py, tests/test_cli_runner.py, tests/test_operator_surface.py, audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-26/*
- tests run: py_compile for changed Python files; focused unittest suite tests.test_cli_runner/tests.test_operator_surface/tests.test_provider_auth_strategy/tests.test_model_availability/tests.test_cli_token_command; core guard suite tests.test_native_launch_contract/tests.test_native_launch_dispatch/tests.test_codex_launch_modes/tests.test_operator_surface/tests.test_repo_hygiene/tests.test_closeout_resilience/tests.test_cli_runner; live probe; packet status audit; secret scan; closeout resilience; git diff check
- blocked risks: native app usability, Original lane reversibility, direct egress absence, streaming, tool loop, full wire compatibility, and final E2E intentionally unclaimed
- closure state: CLOSED

## Verification

- tests: focused and core guard unittest suites passed
- build: changed Python files compiled with py_compile
- manual: no owner manual prompt was required for this CLI runner contour
- live verification: `cli_runner_closeout_packet.json` status is `passed`; WBP trace packet records `/v1/responses`, upstream status `200`, request and response hashes present, raw prompt/token/auth not recorded

## Artifacts

- packet: `cli_runner_closeout_packet.json`
- packet: `cli_runner_trace_packet.json`
- packet: `cli_runner_env_no_ambient_authority_packet.json`
- packet: `cli_runner_false_green_audit.json`
- packet: `cli_runner_original_surface_integrity_packet.json`
- packet: `cli_runner_route_account_guard_packet.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit contains this closeout and its evidence
- pushed: contour commit is intended to be pushed after verification

## Scope Check

- unrelated work mixed in: no; pre-existing dirty historical evidence remained unstaged and unused as active truth
- private-data risk reviewed: yes; evidence records hashes, lengths, classifications, and redaction booleans, not raw prompt, raw token, raw auth header, or upstream secret

## Notes

- blockers encountered: first diagnostic run showed `auth.command` needs explicit server-owned WBP runtime env when Codex `HOME` is isolated; the probe now supplies those paths without using current `~/.codex/auth.json`
- resume from here: CLOSED
