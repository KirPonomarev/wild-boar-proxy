# CONTRACT_ALIGNMENT_FOR_LAUNCH_SMOKE_WRITE_SURFACES Contour

## Goal

Align contour admission truth, declared live write surfaces, and active
governing docs with the diagnosed repo/runtime truth that `launch smoke --json`
legitimately writes `config.toml` as part of its owner-path behavior.

## Classification

- Size: `S`
- Risk level: `medium`
- Mode: `contract alignment / docs-runtime truth reconciliation`
- Decision owner: `CANON.md` for disputed decisions

## Canon Basis

- `CANON.md` outranks all lower documents.
- Fresh closeout evidence outranks stale contour expectations.
- No live continuation may proceed across a known contract mismatch.
- Selector refresh remains parked until launch-smoke write-surface truth is
  aligned.

## In Scope

- update active governing truth where launch-smoke write surfaces were
  underdeclared
- update active master-plan pointer to reflect the post-diagnosis contour chain
- produce machine-readable alignment verdict and next-contour recommendation

## Out Of Scope

- no `healthcheck --json`
- no `status --json`
- no `launch smoke --json`
- no `rollout rotation inspect --json`
- no `sync --json`
- no selector refresh execution
- no exact auth-source admission
- no sandbox `auth.json` materialization
- no onboarding rerun
- no route mutation
- no UI/release work

## Inputs

- `CANON.md`
- `MASTER_PLAN.md`
- `audit_results/runtime_reproof_pass_2026-05-16_v5/*`
- `audit_results/stop_and_diagnose_config_toml_write_2026-05-16/*`
- `wild_boar_proxy/runtime.py`
- `tests/test_cli.py`

## Acceptance Criteria

- active governing truth matches repo/runtime launch-smoke write behavior
- `MASTER_PLAN.md` no longer points at `RUNTIME_REPROOF_PASS` as the next
  primary contour
- next contour is named from aligned truth, not pre-diagnosis memory

## Artifacts

- `audit_results/contract_alignment_launch_smoke_write_surfaces_2026-05-16/contour.md`
- `audit_results/contract_alignment_launch_smoke_write_surfaces_2026-05-16/alignment_basis.json`
- `audit_results/contract_alignment_launch_smoke_write_surfaces_2026-05-16/write_surface_alignment_verdict.json`
- `audit_results/contract_alignment_launch_smoke_write_surfaces_2026-05-16/next_contour_decision.json`
- `audit_results/contract_alignment_launch_smoke_write_surfaces_2026-05-16/independent_audit.md`
- `audit_results/contract_alignment_launch_smoke_write_surfaces_2026-05-16/closeout.md`
