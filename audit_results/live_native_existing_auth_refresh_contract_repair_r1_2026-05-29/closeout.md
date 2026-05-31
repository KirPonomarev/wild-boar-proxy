<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_EXISTING_AUTH_REFRESH_CONTRACT_REPAIR_R1 Closeout

## Goal

Repair or precisely localize the existing-auth refresh and repo-owned adoption
contract after bounded detector repair, using the live `kir.test` browser login
path as the admitted truth surface.

## Result

- status: completed
- final verdict: blocker localized; existing-auth refresh was neither emitted nor adopted on the repo-owned path after live browser success
- closure state: CLOSED

## Contour Capsule

- goal: determine whether a fresh `kir.test` device-login session emits or adopts a session-bound existing-auth refresh that can materialize repo-owned auth and advance stable native truth
- branch: codex/external-agent-lab-isolated
- head: `0bf78ab0`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_runtime_native_auth_recovery.py`
  - `tests/test_cli.py`
  - `tools/live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py::CliTests::test_accounts_onboard_explicit_auth_adopts_existing_matching_backend_without_new_backend -q`
  - `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py`
- blocked risks:
  - browser-visible success did not advance repo-owned login session beyond `waiting_for_user`
  - existing `kir.test` auth artifact remained unchanged after the live session
  - stable native runtime remained `AUTH_UNAVAILABLE` with direct `/v1/responses = 503`
- closure state: CLOSED

## Verification

- tests:
  - `12 passed` in focused runtime, probe, and CLI coverage
- build:
  - `py_compile` passed for touched Python files
- manual:
  - owner completed browser-side device login for `kir.test.gpt26@gmail.com`
- live verification:
  - `accounts login status --session codex-409b804206e7455d82de668e000be920 --json` remained `waiting_for_user`
  - `accounts login complete --session codex-409b804206e7455d82de668e000be920 --json` returned `LOGIN_AUTH_NOT_MATERIALIZED`
  - `healthcheck --json` remained `AUTH_UNAVAILABLE`
  - `status --json` remained `AUTH_UNAVAILABLE`
  - direct native `/v1/responses` remained `503`

## Artifacts

- spec: thread-only contour plan
- packet:
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_existing_auth_refresh_contract_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_session_bound_refresh_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_post_login_materialization_gap_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_materialization_repair_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_materialization_failure_taxonomy_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_runtime_load_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/native_stable_reproof_packet.json`
  - `audit_results/live_native_existing_auth_refresh_contract_repair_r1_2026-05-29/independent_audit_packet.json`
- report:
  - bounded repair covered explicit adoption of an already-existing matching backend
  - live reprobe still produced `existing_auth_refresh_not_emitted_or_not_adopted`
  - `session_bound_refresh_unproven` remained the honest packet-backed classification

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded in the contour closeout commit on `codex/external-agent-lab-isolated`
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered:
  - `native_existing_auth_refresh_contract_packet.json` recorded `existing_auth_refresh_emitted = false` and `existing_auth_refresh_adopted = false`
  - `native_session_bound_refresh_packet.json` recorded `session_bound_refresh_proven = false`
  - `native_post_login_materialization_gap_packet.json` recorded `classification = existing_auth_ref_present_but_unmaterialized`
  - `matching_auth_entries_changed_since_session_created_count = 0`
  - `auth_inventory_added_count = 0`
  - `refresh_token_reused_observed_in_recent_logs = true`
- resume from here: CLOSED
