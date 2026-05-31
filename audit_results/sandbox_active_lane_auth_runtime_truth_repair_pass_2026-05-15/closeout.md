# SANDBOX_ACTIVE_LANE_AUTH_RUNTIME_TRUTH_REPAIR_PASS Closeout

## Goal

Determine whether the sandbox active-lane auth/runtime blocker after failed promotion could be repaired inside the current contour without smuggling in auth-secret rotation/import or launch/materialization scope.

## Result

- status: completed
- final verdict: `STOP_AND_DIAGNOSE`
- next action: move to `SANDBOX_ACTIVE_LANE_AUTH_SOURCE_AND_MATERIALIZATION_SCOPE_ADMISSION_PASS`

## Contour Capsule

- goal: re-check the active-lane blocker on fresh sandbox owner packets and only continue if a narrow in-scope repair path existed
- branch: `codex/external-agent-lab-isolated`
- head: `819a80c Audit sandbox post-promotion attestation blocker`
- touched files: `audit_results/sandbox_active_lane_auth_runtime_truth_repair_pass_2026-05-15/{contour.md,blocker_confirmation.json,truth_source_split.json,repair_plan.md,targeted_test_report.txt,active_lane_verification.json,decision_packet.json,independent_audit.md,closeout.md}`
- tests run: `python3 -m unittest -q tests.test_cli.CliTests.test_accounts_promote_status_verification_failure_rolls_back tests.test_cli.CliTests.test_status_reports_stable_runtime_consumer_contract_when_approved_target_not_ready tests.test_cli.CliTests.test_stable_target_switch_dry_run_returns_contract_without_mutation tests.test_cli.CliTests.test_stable_repair_dry_run_reports_not_needed_when_target_matches_eligible_registry_auths`
- blocked risks: live sandbox attestation still returns `HTTP 401: {"error":"Invalid API key"}`; `sync --json` keeps `effective_mode=stable`; managed listener remains absent; control-layer repair dry-runs do not open an in-scope repair path
- next exact command: `python3 -m wild_boar_proxy healthcheck --json` only after a separate auth-source/materialization scope-admission contour closes with GO

## Verification

- tests: 4 targeted unittest cases passed
- build: not applicable, no repo code changes
- manual: confirmed fresh sandbox `healthcheck --json` and `status --json` both return `ATTESTATION_FAILED` with `blocking_reason=models_surface_unavailable_or_invalid`; confirmed fresh sandbox `sync --json` returns `effective_mode=stable`; confirmed `stable target switch --dry-run --json` is contract-only; confirmed `stable repair --dry-run --json` reports `STABLE_REPAIR_NOT_NEEDED`; confirmed `127.0.0.1:8318` listens and `127.0.0.1:8320` refuses connections
- live verification: packets preserved in `blocker_confirmation.json`, `truth_source_split.json`, and `active_lane_verification.json`

## Artifacts

- spec: [contour.md](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_active_lane_auth_runtime_truth_repair_pass_2026-05-15/contour.md)
- packet: [decision_packet.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_active_lane_auth_runtime_truth_repair_pass_2026-05-15/decision_packet.json)
- report: [independent_audit.md](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_active_lane_auth_runtime_truth_repair_pass_2026-05-15/independent_audit.md)

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; only packet fields, key presence/state, and non-secret path/config facts were recorded

## Notes

- blockers encountered: raw sandbox attestation still fails with `HTTP 401 Invalid API key`; the current sandbox sync/helper path keeps the runtime on `stable`; no managed listener is present; stable target switch / stable repair remain separate control-layer surfaces and do not repair active-lane truth by themselves
- follow-up contour: `SANDBOX_ACTIVE_LANE_AUTH_SOURCE_AND_MATERIALIZATION_SCOPE_ADMISSION_PASS`
- resume from here: `SANDBOX_ACTIVE_LANE_AUTH_SOURCE_AND_MATERIALIZATION_SCOPE_ADMISSION_PASS`
