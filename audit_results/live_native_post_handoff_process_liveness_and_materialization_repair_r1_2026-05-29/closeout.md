<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_POST_HANDOFF_PROCESS_LIVENESS_AND_MATERIALIZATION_REPAIR_R1 Closeout

## Goal

Repair or precisely localize the post-handoff process-liveness and
materialization path so a Codex device-login session no longer dies immediately
after handoff and can be evaluated honestly for downstream auth materialization.

## Result

- status: completed
- final verdict: post-handoff process liveness repaired; auth materialization still unproven; later fresh reprobes were blocked by repeated upstream device-usercode HTTP 403 challenge responses
- closure state: CLOSED

## Contour Capsule

- goal: prove whether the local codex device-login subprocess can stay alive through the handoff window and either materialize repo-owned auth or localize the next blocker without fake native recovery
- branch: codex/external-agent-lab-isolated
- head: `4139fd04`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tools/live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `tests/test_runtime_native_auth_recovery.py`
  - `tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_pre_expiry_owner_completion_observation_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_handoff_retry_failure_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py::CliTests::test_accounts_login_status_codex_fails_after_device_handoff_process_exit tests/test_cli.py::CliTests::test_accounts_onboard_explicit_auth_adopts_existing_matching_backend_without_new_backend -q`
  - `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py`
- blocked risks:
  - native auth still does not materialize into repo-owned inventory
  - stable native runtime remains `AUTH_UNAVAILABLE`
  - repeated fresh device-usercode requests hit upstream HTTP 403 challenge responses
- closure state: CLOSED

## Verification

- tests:
  - `17 passed` in focused runtime, probe, and CLI coverage
- build:
  - `py_compile` passed for touched Python files
- manual:
  - owner completed one live browser-side Codex device login for `kir.test.gpt26@gmail.com`
- live verification:
  - `accounts login start --provider codex --mode device --json` for `codex-a6774fadc45044b989d88b9fda341035` emitted handoff with `device_code = S641-ULBVN`
  - after ~3 seconds with no owner action, `accounts login status --session codex-a6774fadc45044b989d88b9fda341035 --json` still reported `waiting_for_user` with `handoff_observed = true` and `session_process_alive = true`
  - after owner completion, sequential live packets still reported `waiting_for_user` and `LOGIN_AUTH_NOT_MATERIALIZED`, proving that liveness repair did not yet produce repo-owned auth materialization
  - later probe capture against the same session recorded expiry with unchanged matching `kir.test` auth entry and no auth inventory additions
  - two fresh retries (`codex-88e5678798144625b875de8fea6b0eef`, `codex-b785da6549d1456fb003fe7ae8eeae56`) failed before handoff with `LOGIN_DEVICE_HANDOFF_MISSING`; their stdout logs contained `device code request failed with status 403` and Cloudflare challenge HTML
  - `healthcheck --json` remained `AUTH_UNAVAILABLE`
  - `status --json` remained `AUTH_UNAVAILABLE`
  - direct native `/v1/responses` remained `503`

## Artifacts

- spec: thread-only contour plan
- packet:
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_owner_dependency_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_post_login_materialization_gap_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_existing_auth_refresh_contract_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_session_bound_refresh_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_materialization_failure_taxonomy_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_runtime_load_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_stable_reproof_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_pre_expiry_owner_completion_observation_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/native_handoff_retry_failure_packet.json`
  - `audit_results/live_native_post_handoff_process_liveness_and_materialization_repair_r1_2026-05-29/independent_audit_packet.json`
- report:
  - `start_new_session=True` preserved post-handoff subprocess liveness past the previous immediate-death window
  - repo-owned auth still did not materialize after a live owner-completed session
  - later fresh reprobes exposed an upstream device-usercode request blocker rather than a renewed local post-handoff death

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded in the contour closeout commit on `codex/external-agent-lab-isolated`
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered:
  - `native_owner_dependency_packet.json` recorded `owner_action_expired` for the later probe capture, while direct sequential packets taken earlier in the live window had already shown `LOGIN_AUTH_NOT_MATERIALIZED`
  - `native_post_login_materialization_gap_packet.json` recorded `existing_auth_ref_stale_and_unchanged_after_session_expiry`
  - `native_handoff_retry_failure_packet.json` recorded repeated upstream usercode-request HTTP 403 challenge responses
  - the probe reporter originally hid `LOGIN_AUTH_NOT_MATERIALIZED` behind `LOGIN_COMPLETE_NOT_ATTEMPTED`; this contour corrected that factual gap
- resume from here: CLOSED
