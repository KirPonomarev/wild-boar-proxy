# SANDBOX_ACTIVE_LANE_EXTERNAL_AUTH_IMPORT_REPAIR_PASS Closeout

## Goal

Import the canon-admitted external auth source into the sandbox auth target, then re-run owner truth without widening scope.

## Result

- status: complete
- final verdict: `STOP_AND_DIAGNOSE`
- next action: open `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS`

## Contour Capsule

- goal: determine whether a real external auth import can clear the primary sandbox `HTTP 401` blocker inside the declared import-only scope
- branch: `codex/external-agent-lab-isolated`
- head: `2f1eaac Audit external auth source scope admission`
- touched files: `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/contour.md`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/source_target_confirmation.json`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/auth_import_before_after.json`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/rollback_snapshot.json`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/attestation_verification.json`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/forbidden_drift_check.json`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/decision_packet.json`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/independent_audit.md`, `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/closeout.md`
- tests run: `python3 -m unittest tests.test_web_ui tests.test_ui_shell`; `python3 -m unittest -q tests.test_cli.CliTests.test_healthcheck_classifies_auth_unavailable tests.test_cli.CliTests.test_healthcheck_surfaces_empty_usable_auth_pool tests.test_cli.CliTests.test_healthcheck_classifies_model_unavailable tests.test_cli.CliTests.test_status_reports_stable_runtime_consumer_contract_when_approved_target_not_ready`
- blocked risks: hidden registry mutation, mixing import with launcher/materialization writes, treating a new post-import blocker as broad success
- next exact command: `python3 -m wild_boar_proxy external-models status --json` after opening `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS`

## Verification

- tests: targeted UI-shell/status delegation suite passed; targeted healthcheck/status quartet passed
- build: `git diff --check`
- manual: real import, post-import owner reproof, byte-faithful rollback, post-rollback owner reproof
- live verification: real import cleared the primary `HTTP 401` and revealed a new truthful blocker `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`; rollback restored sandbox auth target back to the pre-import digest and the original `HTTP 401` owner truth

## Artifacts

- spec: `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/contour.md`
- packet: `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/decision_packet.json`
- report: `audit_results/sandbox_active_lane_external_auth_import_repair_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts contain only paths, digests, sizes, and packet truth, never secret contents

## Notes

- blockers encountered: owner truth remained blocked after import because the sandbox `external-models` foundation is empty and the configured model has no known provider/route in the live proof path
- follow-up contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS`
- resume from here: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_FOUNDATION_SCOPE_ADMISSION_PASS`
