# SANDBOX_POST_ONBOARD_STATUS_ATTESTATION_REPAIR_PASS Closeout

## Goal

Resolve the post-onboard status-attestation blocker without weakening raw
`status --json` truth, so we can decide lifecycle admission honestly after the
already-proven reserve-first onboarding success.

## Result

- status: completed
- final verdict: GO_TO_ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS
- next action: start `ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`

## Contour Capsule

- goal: separate launch-readiness degradation from reserve-only lifecycle-admission truth after successful sandbox onboarding
- branch: `codex/external-agent-lab-isolated`
- head: `033ca57 Audit sandbox onboarding rerun2 status blocker`
- touched files: `wild_boar_proxy/runtime.py`, `tests/test_cli.py`, `audit_results/sandbox_post_onboard_status_attestation_repair_pass_2026-05-15/*`
- tests run: `python3 -m py_compile wild_boar_proxy/runtime.py tests/test_cli.py`; 6 targeted CLI tests around onboarding lifecycle admission; 2 targeted UI/live-server no-overclaim regressions; `git diff --check`
- blocked risks: raw `status --json` remains degraded and must stay degraded; only the narrow reserve-only launch-gap case is admitted for lifecycle handoff
- next exact command: `python3 -m unittest tests.test_cli.CliTests.test_accounts_promote_reserve_backend_updates_routing_validate_sync_and_status`

## Verification

- tests: targeted runtime/classification tests passed; UI/no-overclaim regressions stayed green
- build: `python3 -m py_compile wild_boar_proxy/runtime.py tests/test_cli.py`
- manual: applied the new classifier to the preserved rerun2 live packets and obtained `status = ready`, `reason = reserve_only_launch_gap` while the raw status packet remained `ATTESTATION_FAILED`
- live verification: no new live runtime mutation was performed in this contour; the decision is grounded in the preserved rerun2 live packets plus the narrowed runtime classifier

## Artifacts

- spec: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_onboard_status_attestation_repair_pass_2026-05-15/contour.md`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_onboard_status_attestation_repair_pass_2026-05-15/decision_packet.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_onboard_status_attestation_repair_pass_2026-05-15/status_attestation_verification.json`
- independent audit: `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_onboard_status_attestation_repair_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; the contour used preserved sandbox packet artifacts and repo-local tests, without mutating live work-contour auth/config paths

## Notes

- blockers encountered: the original repair was too broad until the failed-check gate was narrowed to launch-gap-only failures
- follow-up contour: `ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`
- resume from here: `ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`
