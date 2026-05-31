# SANDBOX_ONBOARDING_AUTH_JSON_ADMISSION_PASS Closeout

## Goal

Keep the onboarding destination fixed to the sandbox-local `auth.json` path and
choose the narrowest admissible upstream auth source class without reading
secret contents, writing auth material, or rerunning onboarding.

## Result

- status: `completed`
- final verdict: `GO_TO_SANDBOX_AUTH_SOURCE_SPECIFIC_ADMISSION_PASS`
- next action: open a narrower source-specific admission contour before any
  `auth.json` materialization

## Contour Capsule

- goal: decide whether the fixed sandbox `auth.json` destination is ready for
  direct materialization or still needs a narrower upstream source admission
- branch: `codex/external-agent-lab-isolated`
- head: `bd77566 Choose sandbox auth input lane for onboarding`
- touched files:
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/*`
- tests run:
  - read-only source-surface inventory under sandbox and forbidden live roots
  - `python3 -m unittest -q tests.test_cli.CliTests.test_stable_repair_dry_run_reports_missing_allowed_auth_plan tests.test_cli.CliTests.test_stable_repair_dry_run_reports_observed_source_missing_dir_without_blocking tests.test_external_models.ExternalModelContractTests.test_paths_from_env_uses_isolated_overrides`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - the currently observed upstream auth-like candidates live under forbidden
    live/working roots and are not directly admitted for secret-bearing use
- next exact command: `git status --short --untracked-files=no`

## Verification

- tests:
  - stable-repair dry-run still separates observed source inventory from source
    copy inputs and target mutation authority
  - missing allowed auth sources remain machine-readable rather than silently
    guessed
  - env override paths remain isolated and explicit
- build:
  - `git diff --check`
- manual:
  - `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json` is still
    absent
  - `/Users/kirillponomarev/.codex-custom-sandbox-20260515/stable/` contains no
    `codex-*.json`
  - forbidden roots `/Users/kirillponomarev/.codex-custom-cli` and
    `/Users/kirillponomarev/.cli-proxy-api` do contain auth-like filenames by
    inventory
  - no secret payload contents were read
- live verification:
  - not applicable; this contour is admission-only and performs no auth write
    or onboarding rerun

## Artifacts

- spec:
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/destination_lock_basis.json`
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/upstream_source_candidates.json`
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/rollback_surface_matrix.json`
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/canon_admissibility_matrix.json`
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/decision_packet.json`
- report:
  - `audit_results/sandbox_onboarding_auth_json_admission_pass_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only filename/path inventories were used, and no auth payload contents were read or copied`

## Notes

- blockers encountered:
  - the current wave still lacks any sandbox-owned upstream auth material
  - the only observed auth-like candidates currently sit under forbidden live roots
- follow-up contour:
  - `SANDBOX_AUTH_SOURCE_SPECIFIC_ADMISSION_PASS`
- resume from here: `narrow one exact upstream auth source surface under a source-specific admission contour before opening any auth.json materialization`
