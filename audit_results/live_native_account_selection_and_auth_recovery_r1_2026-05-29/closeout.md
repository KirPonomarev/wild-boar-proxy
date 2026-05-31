<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# LIVE_NATIVE_ACCOUNT_SELECTION_AND_AUTH_RECOVERY_R1 Closeout

## Goal

Restore one honest native ChatGPT-account path on the admitted live surface, or localize the remaining hard blocker without masking native failure behind selector/UI surfaces.

## Result

- status: completed
- final verdict: `LIVE_NATIVE_AUTH_PATH_RESTORED_OR_BLOCKER_LOCALIZED`
- closure state: CLOSED

## Contour Capsule

- goal: separate selected-backend observation truth from runtime-loaded auth truth and emit an exact owner recovery action when native `/v1/responses` remains `AUTH_UNAVAILABLE`
- branch: `codex/external-agent-lab-isolated`
- head: `d6f4ac36`
- touched files: `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`, `/Volumes/Work/wild-boar-proxy/tools/live_native_account_selection_and_auth_recovery_r1_probe.py`, `/Volumes/Work/wild-boar-proxy/tests/test_runtime_native_auth_recovery.py`, `/Volumes/Work/wild-boar-proxy/tests/test_live_native_account_selection_and_auth_recovery_r1_probe.py`, `/Volumes/Work/wild-boar-proxy/audit_results/live_native_account_selection_and_auth_recovery_r1_2026-05-29/*.json`
- tests run: `python3 -m pytest tests/test_runtime_native_auth_recovery.py tests/test_live_native_account_selection_and_auth_recovery_r1_probe.py -q`; `python3 -m pytest tests/test_live_native_gpt_lane_repair_r1_probe.py -q`; `python3 -m pytest tests/test_cli.py -k "sync_repopulates_selected_backend_ids_from_live_capable_registry or reconcile_stable_recovery_success_preserves_selected_backend_snapshot_surfaces or reconcile_stable_fallback_preserves_selected_backend_snapshot_surfaces" -q`; `python3 -m py_compile wild_boar_proxy/runtime.py tools/live_native_account_selection_and_auth_recovery_r1_probe.py tests/test_runtime_native_auth_recovery.py tests/test_live_native_account_selection_and_auth_recovery_r1_probe.py`
- blocked risks: native `/v1/responses` still returns `503 auth_unavailable` on the admitted stable endpoint even after `sync --json`; restoring native lane now requires owner login recovery, not selector cosmetics
- closure state: CLOSED

## Verification

- tests: `4 passed` in contour-focused tests; `1 passed` in prior native-lane probe regression; `3 passed, 409 deselected` in focused CLI regression
- build: `python3 -m py_compile ...` passed; `git diff --check` passed on touched files
- manual: live `healthcheck --json` now reports `native_auth_recovery_hint.status=owner_action_required`, `selected_backend_observation_source=runtime_state.selected_backend_snapshot`, and `operator_action=user_action`
- live verification: direct native `POST http://127.0.0.1:8318/v1/responses` for `gpt-5.5` remained `503` while `sync --json` produced `selected_backend_ids_count=15`; `healthcheck` then observed `selected_backend_ids_observed_count=15` and `selected_backend_runtime_loaded_count=0`

## Artifacts

- spec: thread-only contour plan for `LIVE_NATIVE_ACCOUNT_SELECTION_AND_AUTH_RECOVERY_R1`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/live_native_account_selection_and_auth_recovery_r1_2026-05-29/native_auth_recovery_attempt_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/live_native_account_selection_and_auth_recovery_r1_2026-05-29/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `d6f4ac36`
- pushed: no

## Scope Check

- unrelated work mixed in: no; only runtime truth surfaces, contour-local probe/tests, and contour evidence were staged
- private-data risk reviewed: yes; packets avoid raw auth material and only store counts, status codes, and bounded command surfaces

## Notes

- blockers encountered: the managed state can preserve a valid `selected_backend_snapshot` while stable fallback clears flat `selected_backend_ids`; native auth remains blocked even after canonical `sync --json`, so selected-backend observation truth and runnable auth truth must stay separate
- resume from here: CLOSED
