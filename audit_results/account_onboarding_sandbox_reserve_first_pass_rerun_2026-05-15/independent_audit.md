# Independent Audit

Verdict: `STOP_AND_DIAGNOSE`.

Grounded facts:
- The rerun packet in [onboard_command_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/onboard_command_packet.json) returned `machine_error_code = ONBOARD_FAILED`.
- Nested `onboarding_result.selection_status = no_new_backend_detected`, `reserve_first_enforced = false`, and `final_outcome = import_failed`.
- Post-refresh [post_onboard_accounts_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/post_onboard_accounts_packet.json) remained empty, so reserve-first success was not proven.
- The reserve-first gate in [wild_boar_proxy/runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:11998) requires a uniquely selected backend in `reserve`; the same owner surface returns `ONBOARD_FAILED` / `import_failed` when `selection_status == no_new_backend_detected` after a nonzero external run at [wild_boar_proxy/runtime.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py:12062).
- The repaired owner helper lane exists, but its auth validator only accepts payloads with `type in {"codex", "apikey"}` at [wild_boar_proxy/sandbox_owner_helpers.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/sandbox_owner_helpers.py:161). The sandbox auth file used in this rerun has keys `auth_mode` and `OPENAI_API_KEY`, not `type`, as recorded in [pre_onboard_snapshot.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/pre_onboard_snapshot.json). This matches stderr `invalid auth type: None`.
- Forbidden live-path drift was not observed in [forbidden_drift_check.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun_2026-05-15/forbidden_drift_check.json).

Conclusion:
The contour cannot close `GO` because reserve-first semantics were never reached. The narrow blocker is sandbox auth payload compatibility with the repaired owner-helper contract, not helper-path isolation or live-path fallback.
