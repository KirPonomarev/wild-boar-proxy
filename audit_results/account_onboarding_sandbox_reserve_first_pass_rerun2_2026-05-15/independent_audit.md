# Independent Audit

Verdict: `STOP_AND_DIAGNOSE`.

Grounded facts:
- The onboarding mutation itself succeeded: the packet in [onboard_command_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/onboard_command_packet.json) reports `status = ok`, `machine_error_code = OK`, `selected_backend_id = "auth"`, `selection_status = "selected_unique_backend"`, `reserve_first_enforced = true`, `validate_outcome = ok`, `sync_outcome = ok`, and `final_outcome = explicit_auth_imported_to_reserve`.
- Post-refresh [post_onboard_accounts_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/post_onboard_accounts_packet.json) shows backend `auth` present in pool `reserve`.
- Forbidden live-path drift was not observed in [forbidden_drift_check.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/forbidden_drift_check.json).
- But the packet’s own `status_observed` summary records `command_status = error`, `machine_error_code = ATTESTATION_FAILED`, and `liveness = degraded`, and the separate [post_onboard_status_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/account_onboarding_sandbox_reserve_first_pass_rerun2_2026-05-15/post_onboard_status_packet.json) confirms the same degraded attestation outcome.
- Existing UI evidence still supports no-overclaim: the targeted tests in [tests/test_web_design_live_server.py](/Volumes/Work/wild-boar-proxy/tests/test_web_design_live_server.py:715) and [tests/test_web_design_ui.py](/Volumes/Work/wild-boar-proxy/tests/test_web_design_ui.py:2320) keep reserve-first success separate from active/promoted claims and keep non-success states non-green.

Conclusion:
The contour earned reserve-first onboarding admission proof, but it did not earn safe handoff to lifecycle actions because the post-onboard status proof remains degraded. The next honest step is a status-attestation repair contour, not `ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`.
