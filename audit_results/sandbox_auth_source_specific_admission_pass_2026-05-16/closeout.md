# SANDBOX_AUTH_SOURCE_SPECIFIC_ADMISSION_PASS Closeout

## Goal

Try to narrow the upstream auth source from a source class to one exact surface
for later sandbox `auth.json` materialization, without reading secret contents,
writing auth material, or rerunning onboarding.

## Result

- status: `completed`
- final verdict: `GO_TO_NARROWER_SOURCE_TRANSFER_ADMISSION_PASS`
- next action: open a narrower transfer-admission contour for the currently
  localized live-registry auth-ref family

## Contour Capsule

- goal: decide whether one exact upstream auth source can be admitted now or
  whether the current live-root candidate family still needs a narrower
  transfer-safe admission contour
- branch: `codex/external-agent-lab-isolated`
- head: `3f22cb4 Admit sandbox auth.json source class boundary`
- touched files:
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/*`
- tests run:
  - read-only registry/state path inspection only
  - `python3 -m unittest -q tests.test_cli.CliTests.test_stable_repair_dry_run_reports_missing_allowed_auth_plan tests.test_cli.CliTests.test_stable_repair_dry_run_reports_observed_source_missing_dir_without_blocking tests.test_cli.CliTests.test_stable_repair_dry_run_blocks_ambiguous_registry`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - all currently observed exact candidates live under forbidden live roots
  - more than one exact source remains policy-plausible
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - stable-repair dry-run still separates source-copy inputs from target
    mutation authority
  - missing or ambiguous source states remain machine-readable instead of being
    guessed away
- build:
  - `git diff --check`
- manual:
  - current live registry references 25 exact `auth_ref` surfaces
  - current live policy-allowed subset contains 12 exact `auth_ref` surfaces
  - current supervisor snapshot has `selected_backend_ids = []`
  - no secret payload contents were read
- live verification:
  - not applicable; this contour is admission-only and performs no auth write
    or onboarding rerun

## Artifacts

- spec:
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/destination_and_blocker_basis.json`
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/exact_source_candidates.json`
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/rollback_surface_matrix.json`
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/canon_admissibility_matrix.json`
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/sandbox_auth_source_specific_admission_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only path references, counts, and registry/state metadata were inspected`

## Notes

- blockers encountered:
  - one exact upstream source cannot be selected honestly from the current
    forbidden-root candidate family
- follow-up contour:
  - `NARROWER_SOURCE_TRANSFER_ADMISSION_PASS`
- resume from here: `narrow the current forbidden-root auth-ref family to one transfer-safe exact source surface before opening any auth.json materialization`
