# SELECTOR_REFRESH_OWNER_PATH_PASS Contour

## Goal

Refresh selected-backend participation evidence through the canonical owner path
after fresh runtime re-entry closed green, then name the next contour from
fresh selector packet truth only.

## Classification

- Size: `S`
- Risk level: `high`
- Mode: `live-proof / selector refresh`

## Canon Basis

- `CANON.md` is the highest source of truth.
- Fresh packet truth outranks historical stale narrative.
- Selector refresh must be its own contour.
- Fresh `runtime_reproof_pass_reentry_2026-05-16` closeout and decision packet
  govern this contour start while `MASTER_PLAN.md` top pointer still lags.

## In Scope

- `git status --short --untracked-files=no`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy status --json`
- capture machine-readable packets
- independent audit after packet capture
- close with a decision packet naming the next contour

## Out Of Scope

- no `launch smoke --json` unless a new contradiction forces a separate runtime contour
- no exact auth-source admission
- no sandbox `auth.json` materialization
- no onboarding rerun
- no route mutation
- no UI/release work

## Declared Live Write Surfaces

- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json` only
  if packet truth reports it
- `/Users/kirillponomarev/.codex-custom-cli/managed/wild-boar-proxy.lock` as
  transient lock surface only

## Acceptance Criteria

- fresh selector evidence is captured or truthfully blocked
- no stale selector snapshot is treated as current
- `sync --json` outcome is preserved exactly, including `changed_files`
- post-refresh `rollout rotation inspect --json` truthfully classifies selector state
- next contour is named from fresh packet truth only

## Artifacts

- `audit_results/selector_refresh_owner_path_pass_reentry_2026-05-16/contour.md`
- `selector_basis.json`
- `rotation_before_sync.json`
- `sync_refresh_packet.json`
- `rotation_after_sync.json`
- `status_after_sync.json`
- `decision_packet.json`
- `independent_audit.md`
- `closeout.md`
