# NARROWER_SOURCE_TRANSFER_ADMISSION_PASS Closeout

## Goal

Attempt to narrow the current forbidden-root auth source family to one
transfer-safe exact source surface for a later sandbox `auth.json`
materialization step, without reading secret contents, writing auth material, or
rerunning onboarding.

## Result

- status: `completed`
- final verdict: `GO_TO_LIVE_REGISTRY_AUTH_REF_SELECTOR_ADMISSION_PASS`
- next action: open a selector-admission contour inside the current live
  registry auth-ref family before exact-source admission or materialization

## Contour Capsule

- goal: determine whether one exact transfer-safe source surface can be admitted
  now or whether the remaining blocker is selector truth inside the localized
  live-registry family
- branch: `codex/external-agent-lab-isolated`
- head: `5243e40 Narrow sandbox auth source admission contour`
- touched files:
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/*`
- tests run:
  - read-only registry/state path inspection only
- `python3 -m unittest -q tests.test_cli.CliTests.test_stable_repair_dry_run_reports_missing_allowed_auth_plan tests.test_cli.CliTests.test_stable_repair_dry_run_reports_observed_source_missing_dir_without_blocking tests.test_cli.CliTests.test_stable_repair_dry_run_blocks_ambiguous_registry tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_unknown_when_selected_snapshot_missing`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/narrower_source_transfer_admission_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - one exact transfer-safe source surface still cannot be admitted honestly
  - stable_default_backend_id alone is not a sufficient selector
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - stable-repair dry-run still separates source-copy inputs from target
    mutation authority
  - ambiguity remains machine-readable and is not guessed away
  - empty selected-backend evidence remains unknown rather than synthesized from
    registry candidates
- build:
  - `git diff --check`
- manual:
  - current live registry references 25 exact `auth_ref` surfaces
  - current live policy-allowed subset contains 12 exact `auth_ref` surfaces
  - current supervisor snapshot still has `selected_backend_ids = []`
  - no secret payload contents were read
- live verification:
  - not applicable; this contour is admission-only and performs no auth write
    or onboarding rerun

## Artifacts

- spec:
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/destination_and_ambiguity_basis.json`
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/transfer_safe_exact_source_candidates.json`
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/rollback_boundary_matrix.json`
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/canon_admissibility_matrix.json`
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/narrower_source_transfer_admission_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only path references, counts, and registry/state metadata were inspected`

## Notes

- blockers encountered:
  - one exact transfer-safe source surface still cannot be chosen honestly from
    the current live-registry family
- follow-up contour:
  - `LIVE_REGISTRY_AUTH_REF_SELECTOR_ADMISSION_PASS`
- resume from here: `narrow the current live-registry auth-ref family with a selector-specific admission contour before any exact-source admission or auth.json materialization`
