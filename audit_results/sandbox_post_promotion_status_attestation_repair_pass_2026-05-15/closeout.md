# SANDBOX_POST_PROMOTION_STATUS_ATTESTATION_REPAIR_PASS Closeout

## Goal

Determine whether the post-promotion sandbox attestation blocker could be repaired inside the current contour without smuggling in auth-secret rotation/import or launch-lane scope.

## Result

- status: completed
- final verdict: `STOP_AND_DIAGNOSE`
- next action: move to `SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS`

## Contour Capsule

- goal: localize the failed post-promotion status proof on sandbox-local surfaces and only continue if a narrow in-scope repair existed
- branch: `codex/external-agent-lab-isolated`
- head: `0ffb015 Audit sandbox lifecycle rerun attestation blocker`
- touched files: `audit_results/sandbox_post_promotion_status_attestation_repair_pass_2026-05-15/{contour.md,repair_plan.md,blocker_confirmation.json,attestation_matrix.json,status_attestation_verification.json,targeted_test_report.txt,decision_packet.json,independent_audit.md,closeout.md}`
- tests run: `python3 -m unittest -q tests.test_cli.CliTests.test_accounts_promote_status_verification_failure_rolls_back tests.test_cli.CliTests.test_accounts_promote_promotes_reserve_backend_with_verified_active_routing tests.test_cli.CliTests.test_sync_reports_config_toml_change_when_external_sync_promotes_base_url tests.test_cli.CliTests.test_status_reports_default_launcher_provisioning_available_before_materialization`
- blocked risks: live sandbox attestation still returns `HTTP 401: {"error":"Invalid API key"}` and managed active lane is not materialized inside current contour scope
- next exact command: `python3 -m wild_boar_proxy accounts promote auth --json` only after a separate active-lane auth/runtime truth contour closes with GO

## Verification

- tests: 4 targeted unittest cases passed
- build: not applicable, no repo code changes
- manual: confirmed sandbox `status --json` and `healthcheck --json` both return `ATTESTATION_FAILED` with `blocking_reason=models_surface_unavailable_or_invalid`; confirmed sandbox `sync --json` returns `effective_mode=stable`; confirmed `127.0.0.1:8318` listens and `127.0.0.1:8320` refuses connections; confirmed sandbox launcher remains unprovisioned and sandbox `external-models` adapter remains stopped
- live verification: packets preserved in `blocker_confirmation.json`, `attestation_matrix.json`, and `status_attestation_verification.json`

## Artifacts

- spec: [contour.md](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_promotion_status_attestation_repair_pass_2026-05-15/contour.md)
- packet: [decision_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_promotion_status_attestation_repair_pass_2026-05-15/decision_packet.json)
- report: [independent_audit.md](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_post_promotion_status_attestation_repair_pass_2026-05-15/independent_audit.md)

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; only key presence/state was recorded, not secret values

## Notes

- blockers encountered: sandbox-local live attestation remains hard-failed on `HTTP 401 Invalid API key`; `sync --json` truthfully keeps the sandbox in `stable`; sandbox managed listener is absent; launcher consumer is not repo-managed/provisioned
- follow-up contour: `SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS`
- resume from here: `SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS`
