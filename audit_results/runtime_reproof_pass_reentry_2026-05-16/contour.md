# RUNTIME_REPROOF_PASS_REENTRY Contour

## Goal

One fresh live runtime re-entry after launch-smoke write-surface alignment.
Reconfirm runtime-green truth on current state, then name the next contour from
fresh packet truth only.

## Classification

- Size: `S`
- Risk level: `high`
- Mode: `live-proof / re-entry`

## Canon Basis

- `CANON.md` is the highest source of truth.
- `MASTER_PLAN.md` keeps selector/auth/sandbox lanes parked until runtime truth
  is honest.
- `CONTRACT_ALIGNMENT_FOR_LAUNCH_SMOKE_WRITE_SURFACES` closed and named this
  contour as the next live re-entry contour from aligned evidence.
- Selector refresh must reopen only after fresh runtime reproof, not by
  inertia.

## In Scope

- `git status --short --untracked-files=no`
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy launch smoke --json` only if needed
- `python3 -m wild_boar_proxy status --json`
- capture machine-readable packets
- independent audit after packet capture
- close with a decision packet naming the next contour

## Out Of Scope

- no `rollout rotation inspect --json`
- no `sync --json`
- no selector refresh execution
- no exact auth-source admission
- no sandbox `auth.json` materialization
- no onboarding rerun
- no route mutation
- no UI/release work

## Declared Live Write Surfaces

- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh` only if
  packet truth reports it

## Acceptance Criteria

- fresh runtime packet truth is captured on aligned contract surfaces
- `claim_gate` is either clear or truthfully blocked with preserved reason
- `policy_drift` is either clear or truthfully blocked with preserved reason
- no undeclared writes occur
- next contour is named from fresh packet truth, not historical packets

## Artifacts

- `audit_results/runtime_reproof_pass_reentry_2026-05-16/contour.md`
- `runtime_reentry_basis.json`
- `healthcheck_packet.json`
- `status_after_healthcheck.json`
- `launch_smoke_packet.json` if invoked
- `status_after_launch_smoke.json` if invoked
- `decision_packet.json`
- `independent_audit.md`
- `closeout.md`
