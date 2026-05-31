<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_DEVICE_USERCODE_GATE_AND_CHALLENGE_LOCALIZATION_R1 Closeout

## Goal

Repair or precisely localize the fresh device-usercode gate so that live Codex
device-login starts can be evaluated honestly again, then continue only if that
re-earned handoff can progress through owner completion, repo-owned auth
materialization, and stable native runtime truth.

## Result

- status: completed
- final verdict: repeated pre-handoff HTTP 403 challenge responses were real but not durable enough to justify a permanent gate-block claim; a later fresh handoff was re-earned, a bounded reserve-first onboarding false positive was repaired, and stable native runtime truth was reproved with direct `/v1/responses = 200`
- closure state: CLOSED

## Contour Capsule

- goal: prove whether fresh Codex device-login starts were still blocked before handoff or whether the native chain could be re-earned and advanced honestly without fake recovery claims
- branch: codex/external-agent-lab-isolated
- head: `9c42320e`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_cli.py`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_device_usercode_gate_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_handoff_retry_failure_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_browser_success_handoff_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_pre_expiry_owner_completion_observation_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_post_login_materialization_gap_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_onboarding_reserve_first_gate_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_runtime_load_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_stable_reproof_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/independent_audit_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest tests/test_cli.py::CliTests::test_accounts_onboard_ignores_selected_backend_state_drift_for_reserve_first_gate tests/test_cli.py::CliTests::test_accounts_onboard_detected_new_auth_no_sync_does_not_overclaim_sync tests/test_cli.py::CliTests::test_accounts_onboard_blocks_selected_backend_active_routing_change tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py -q`
  - `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_completion_and_stable_reproof_r1_probe.py tests/test_cli.py`
- blocked risks:
  - repeated fresh-start `deviceauth/usercode` HTTP 403 challenge responses were observed twice but not yet durably explained
  - durable pre-handoff gate repair remains a non-claim even though one later fresh handoff succeeded
  - direct runtime truth is healthy again, but future contours must still avoid overclaiming reproducibility from a single recovered fresh handoff
- closure state: CLOSED

## Verification

- tests:
  - `18 passed` in focused runtime, probe, and CLI coverage
- build:
  - `py_compile` passed for touched Python files
- manual:
  - owner completed live browser-side Codex device login for `kir.test.gpt26@gmail.com`
- live verification:
  - earlier fresh retries (`codex-88e5678798144625b875de8fea6b0eef`, `codex-b785da6549d1456fb003fe7ae8eeae56`) failed before handoff with `LOGIN_DEVICE_HANDOFF_MISSING`; stdout contained `device code request failed with status 403` and Cloudflare challenge HTML
  - later fresh start `codex-f43e4142d69e4e728fd666f18e8d8868` re-earned handoff with `device_code = S6W2-S4OS9`
  - after owner completion, `accounts login status --session codex-f43e4142d69e4e728fd666f18e8d8868 --json` reported `login_result.status = completed`, `auth_materialized = true`, `auth_ref_present = true`, and `used = true`
  - pre-fix `accounts login complete --session codex-f43e4142d69e4e728fd666f18e8d8868 --json` had surfaced `ONBOARD_ACTIVE_ROUTING_CHANGED` even though onboarding chose reserve backend `kir-test-gpt26`
  - bounded repair removed `selected_backend_ids` drift from reserve-first active-routing change truth
  - post-fix onboarding for the same live session completed with `machine_error_code = OK`, `active_routing_changed = false`, and `final_outcome = explicit_existing_auth_adopted_to_reserve`
  - `healthcheck --json` returned `machine_error_code = OK`, `responses_ok = true`, and `launch_readiness.status = ready`
  - `status --json` returned `machine_error_code = OK` and `liveness = healthy`
  - direct native probe returned `http_status = 200`

## Artifacts

- spec: thread-only contour plan
- packet:
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_device_usercode_gate_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_handoff_retry_failure_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_browser_success_handoff_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_pre_expiry_owner_completion_observation_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_post_login_materialization_gap_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_onboarding_reserve_first_gate_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_runtime_load_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/native_stable_reproof_packet.json`
  - `audit_results/live_native_device_usercode_gate_and_challenge_localization_r1_2026-05-29/independent_audit_packet.json`
- report:
  - repeated pre-handoff HTTP 403 challenge responses were preserved as factual evidence, not promoted into a full upstream-cause claim
  - a later fresh start re-earned handoff and progressed through owner completion to repo-owned auth materialization
  - the remaining live failure was a local reserve-first onboarding false positive, not a renewed pre-handoff gate failure
  - reserve-first onboarding was repaired narrowly and stable native runtime truth was reproved

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded in the contour closeout commit on `codex/external-agent-lab-isolated`
- pushed: yes

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered:
  - `native_handoff_retry_failure_packet.json` recorded two genuine fresh-start `LOGIN_DEVICE_HANDOFF_MISSING` failures with HTTP 403 challenge evidence
  - `native_device_usercode_gate_packet.json` intentionally kept `durable_gate_repair_proven = false` because one recovered handoff is not durable proof
  - the decisive local blocker on the recovered session was `ONBOARD_ACTIVE_ROUTING_CHANGED`, caused by reserve-first onboarding over-trusting `selected_backend_ids` drift rather than actual active-routing truth
  - replaying `accounts login complete` after successful completion correctly returned `LOGIN_SESSION_REPLAY_BLOCKED`; replay guard was not treated as regression
- resume from here: CLOSED
