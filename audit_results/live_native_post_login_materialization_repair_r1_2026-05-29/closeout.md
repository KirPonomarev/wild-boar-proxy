<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_POST_LOGIN_MATERIALIZATION_REPAIR_R1 Closeout

## Goal

Repair or precisely localize the post-login materialization gap between browser-visible
Codex login success and repo-owned local auth materialization on the stable native path.

## Result

- status: completed
- final verdict: blocker localized after bounded detector repair; repo-owned local auth still did not materialize for `kir.test.gpt26@gmail.com`
- closure state: CLOSED

## Contour Capsule

- goal: re-run the owner login path after bounded detector repair and determine whether repo-owned materialization, runtime load, or stable native responses truth advances
- branch: codex/external-agent-lab-isolated
- head: final contour commit on `codex/external-agent-lab-isolated`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_runtime_native_auth_recovery.py`
  - `tools/live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py -q`
  - `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py`
- blocked risks:
  - browser-visible success was not enough to materialize repo-owned auth
  - matching `kir.test` auth artifact remained unchanged since before the session
  - stable native runtime remained `AUTH_UNAVAILABLE` with direct `/v1/responses = 503`
- closure state: CLOSED

## Verification

- tests:
  - `10 passed` in focused runtime/probe coverage
- build:
  - `py_compile` passed for touched Python files
- manual:
  - owner completed browser-side device login for `kir.test.gpt26@gmail.com`
- live verification:
  - `accounts login status --session codex-ff4bfb37450d4d8dac0326923fbea520 --json` remained `waiting_for_user` before expiry and later became `expired`
  - `accounts login complete --session codex-ff4bfb37450d4d8dac0326923fbea520 --json` returned `LOGIN_AUTH_NOT_MATERIALIZED`
  - `healthcheck --json` remained `AUTH_UNAVAILABLE`
  - `status --json` remained `AUTH_UNAVAILABLE`
  - direct native `/v1/responses` remained `503`

## Artifacts

- spec: thread-only contour plan
- packet:
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/native_post_login_materialization_gap_packet.json`
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/native_materialization_repair_packet.json`
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/native_materialization_failure_taxonomy_packet.json`
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/native_runtime_load_packet.json`
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/native_stable_reproof_packet.json`
  - `audit_results/live_native_post_login_materialization_repair_r1_2026-05-29/independent_audit_packet.json`
- report:
  - detector repair was test-proven but not sufficient to produce repo-owned materialization in the live `kir.test` path
  - post-login gap remained visible until session expiry with `refresh_token_reused` observed in recent logs

## Git

- branch: codex/external-agent-lab-isolated
- commit: final contour commit on `codex/external-agent-lab-isolated`
- pushed: pending push in the same contour turn

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered:
  - `native_post_login_materialization_gap_packet.json` classified the live result as `existing_auth_ref_stale_and_unchanged_after_session_expiry`
  - `matching_auth_entries_changed_since_session_created_count = 0`
  - `auth_inventory_added_count = 0`
  - `session_pid_alive = false`
  - `refresh_token_reused_observed_in_recent_logs = true`
- resume from here: CLOSED
