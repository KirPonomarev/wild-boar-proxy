<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_OWNER_LOGIN_RECOVERY_AND_REPROOF_R1 Closeout

## Goal

Execute the canonical owner login recovery lane and reprove native live auth truth, or localize the remaining blocker without blurring owner action and runtime failure.

## Result

- status: completed
- final verdict: `LIVE_NATIVE_OWNER_LOGIN_RECOVERED_OR_BLOCKER_LOCALIZED`
- closure state: CLOSED

## Contour Capsule

- goal: remove the false pre-owner system blocker, prove that canonical Codex device login now emits a real handoff on the admitted stable inventory path, and classify whether native recovery is blocked by missing owner completion or by deeper runtime failure
- branch: `codex/external-agent-lab-isolated`
- head: `4daa70d3`
- touched files: `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`, `/Volumes/Work/wild-boar-proxy/tools/live_native_owner_login_recovery_and_reproof_r1_probe.py`, `/Volumes/Work/wild-boar-proxy/tests/test_runtime_native_auth_recovery.py`, `/Volumes/Work/wild-boar-proxy/tests/test_live_native_owner_login_recovery_and_reproof_r1_probe.py`, `/Volumes/Work/wild-boar-proxy/tests/test_cli.py`, `/Volumes/Work/wild-boar-proxy/audit_results/live_native_owner_login_recovery_and_reproof_r1_2026-05-29/*.json`
- tests run: `python3 -m pytest tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_login_recovery_and_reproof_r1_probe.py -q`; `python3 -m pytest tests/test_cli.py -k "accounts_login_start_codex_device_allows_stable_config_parent_inventory or accounts_login_start_codex_device_blocks_auth_dir_outside_admitted_roots or accounts_login_status_codex_keeps_waiting_after_device_handoff_process_exit" -q`; `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_owner_login_recovery_and_reproof_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_owner_login_recovery_and_reproof_r1_probe.py`
- blocked risks: owner login is still required and native `/v1/responses` remains `503 auth_unavailable` until owner completion materializes auth; launched Custom Codex native recovery remains non-claim
- closure state: CLOSED

## Verification

- tests: `5 passed` in runtime/probe-focused tests; `3 passed, 412 deselected` in focused CLI regression
- build: `python3 -m py_compile ...` passed; `git diff --check` passed on touched files
- manual: live `accounts login start --provider codex --mode device --json` now succeeds on the real stable inventory path, emits `device_url=https://auth.openai.com/codex/device`, `device_code_present=true`, and `login_result.scope=admitted_owner_login`; subsequent `accounts login status --session ... --json` stays at `waiting_for_user` instead of collapsing to a false failed state when the handoff process exits
- live verification: direct native `POST http://127.0.0.1:8318/v1/responses` for `gpt-5.5` still returned `503 auth_unavailable`; contour probe classified `owner_action_pending` with `session_id_present=true`, `device_code_present=true`, `auth_materialized=false`, and `stable_runtime_native_responses_reproved=false`

## Artifacts

- spec: thread-only contour plan for `LIVE_NATIVE_OWNER_LOGIN_RECOVERY_AND_REPROOF_R1`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/live_native_owner_login_recovery_and_reproof_r1_2026-05-29/native_owner_dependency_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/live_native_owner_login_recovery_and_reproof_r1_2026-05-29/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `4daa70d3`
- pushed: no

## Scope Check

- unrelated work mixed in: no; only runtime login/reproof truth surfaces, contour-local probe/tests, and contour evidence were staged
- private-data risk reviewed: yes; packets store only bounded session metadata, status codes, and command surfaces, not raw auth contents

## Notes

- blockers encountered: canonical owner login initially failed before any handoff because stable auth inventory lived in `~/.cli-proxy-api`, outside the overly narrow profile/managed-only guard; after widening the admitted owner-login scope to include the stable config parent, the next blocker surfaced: the device-login process can exit immediately after printing the handoff, so refresh logic had to preserve `waiting_for_user` until auth materializes or the session expires
- resume from here: CLOSED
