<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_BROWSER_SUCCESS_TO_LOCAL_SESSION_HANDOFF_REPAIR_R1 Closeout

## Goal

Repair or precisely localize the browser-success to local-session handoff contract
so repo-owned session truth no longer masks a dead post-handoff process as
`waiting_for_user`.

## Result

- status: completed
- final verdict: local session truth repaired; dead-after-handoff sessions now classify as failed with explicit handoff-process-exited evidence, while native auth remains unrecovered
- closure state: CLOSED

## Contour Capsule

- goal: prove whether a Codex device-login session receives a usable local handoff after URL/code emission or instead dies before any repo-owned auth materialization
- branch: codex/external-agent-lab-isolated
- head: `b2b206d8`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_runtime_native_auth_recovery.py`
  - `tests/test_cli.py`
  - `tools/live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py::CliTests::test_accounts_login_status_codex_fails_after_device_handoff_process_exit tests/test_cli.py::CliTests::test_accounts_onboard_explicit_auth_adopts_existing_matching_backend_without_new_backend -q`
  - `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py`
- blocked risks:
  - device-login process exits a few seconds after handoff with no repo-owned auth materialization
  - stable native runtime remains `AUTH_UNAVAILABLE`
  - direct native `/v1/responses` remains blocked
- closure state: CLOSED

## Verification

- tests:
  - `15 passed` in focused runtime, probe, and CLI coverage
- build:
  - `py_compile` passed for touched Python files
- manual:
  - no owner action required for the closing live proof; the repaired contour is proven by no-owner session liveness truth
- live verification:
  - `accounts login start --provider codex --mode device --json` for `codex-17972f09dad048d09e2e0d9d52ce5e8d` returned `handoff_observed = true` and `session_process_alive = true`
  - after ~3 seconds, `accounts login status --session codex-17972f09dad048d09e2e0d9d52ce5e8d --json` returned `LOGIN_HANDOFF_PROCESS_EXITED`
  - `accounts login complete --session codex-17972f09dad048d09e2e0d9d52ce5e8d --json` returned `LOGIN_HANDOFF_PROCESS_EXITED`
  - `healthcheck --json` remained `AUTH_UNAVAILABLE`
  - `status --json` remained `AUTH_UNAVAILABLE`
  - direct native `/v1/responses` remained `503`

## Artifacts

- spec: thread-only contour plan
- packet:
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_browser_success_handoff_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_local_session_transition_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_existing_auth_refresh_contract_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_session_bound_refresh_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_materialization_failure_taxonomy_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_runtime_load_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/native_stable_reproof_packet.json`
  - `audit_results/live_native_browser_success_to_local_session_handoff_repair_r1_2026-05-29/independent_audit_packet.json`
- report:
  - local session truth is no longer falsely green or falsely pending after dead post-handoff process exit
  - the repaired classification narrows the blocker to `device_handoff_process_exited_before_auth_materialized`
  - stable native recovery remains unproven and blocked

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded in the contour closeout commit on `codex/external-agent-lab-isolated`
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered:
  - `native_browser_success_handoff_packet.json` recorded `handoff_emitted_but_local_session_not_promoted`
  - `native_local_session_transition_packet.json` recorded `handoff_received_but_session_not_promoted`
  - `native_owner_dependency_packet.json` recorded `browser_success_without_local_session_handoff`
  - `independent_audit_packet.json` recommended closure `device_handoff_process_exited_before_auth_materialized`
  - one concurrent `status` + `complete` probe against the same session exposed a local file-replace race, so final contour truth used sequential owner surfaces only
- resume from here: CLOSED
