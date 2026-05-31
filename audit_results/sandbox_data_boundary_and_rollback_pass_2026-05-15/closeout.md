# SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS Closeout

## Goal

Define a safe sandbox boundary, declared write surfaces, rollback, and teardown
before the sandbox mutation wave begins.

## Result

- status: `GO`
- final verdict: `GO_TO_SANDBOX_LIVE_SERVER_BINDING_PASS`
- next action: open the sandbox binding contour against the declared fresh root

## Contour Capsule

- goal: separate observed paths from declared sandbox policy, classify the old
  sandbox candidate root, and decide whether a fresh sandbox root can carry the
  next binding contour safely
- branch: `codex/external-agent-lab-isolated`
- head: `a92a421 Rerun readonly truth baseline with owner discipline`
- touched files:
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/contour.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/path_inventory.json`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/write_surface_declaration.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/forbidden_surface_declaration.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/sandbox_boundary_packet.json`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/rollback_runbook.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/teardown_runbook.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/separation_proof.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/decision_packet.json`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/independent_audit.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/closeout.md`
- tests run:
  - `python3 -m unittest -q tests.test_external_models.ExternalModelContractTests.test_paths_from_env_uses_isolated_overrides tests.test_cli.CliTests.test_installer_init_creates_baseline_companion_layout`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - no active blocker remains after declaring a fresh dedicated sandbox root and quarantining the old candidate root
- next exact command: `python3 -m wild_boar_proxy installer init --json`

## Verification

- tests:
  - isolated path override test passed
  - isolated installer bootstrap test passed
- build:
  - `git diff --check`
- manual:
  - working/live roots were observed directly
  - old sandbox candidate root contents were enumerated without mutation
  - path overlap was checked directly
  - fresh root absence was verified directly
- live verification:
  - not applicable; this contour is boundary planning only

## Artifacts

- spec:
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/contour.md`
- packet:
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/path_inventory.json`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/sandbox_boundary_packet.json`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/decision_packet.json`
- report:
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/write_surface_declaration.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/forbidden_surface_declaration.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/rollback_runbook.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/teardown_runbook.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/separation_proof.md`
  - `audit_results/sandbox_data_boundary_and_rollback_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only path and size facts were recorded, no
  secret payloads were copied into artifacts`

## Notes

- blockers encountered:
  - old sandbox candidate root was found inadmissible for active-wave reuse
- follow-up contour:
  - `SANDBOX_LIVE_SERVER_BINDING_PASS`
- resume from here: `bind the live server and command runner only against /Users/kirillponomarev/.codex-custom-sandbox-20260515`
