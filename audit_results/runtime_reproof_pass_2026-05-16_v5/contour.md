# RUNTIME_REPROOF_PASS Contour

## Goal

Re-earn runtime-green state after `SELECTOR_REFRESH_OWNER_PATH_PASS` v3 stopped
on `LOCK_HELD` and runtime preconditions regressed before retry. Decide, from
packet truth only, whether selector refresh may be reopened next.

## Classification

- Size: `S`
- Risk level: `high`
- Decision owner: operator for live runtime commands; `CANON.md` for disputed
  decisions
- Mode: `live-proof / diagnosis`

## Canon Basis

- `CANON.md` is the highest source of truth.
- `MASTER_PLAN.md v1.49` is the active execution pointer.
- Strict JSON command packets are the primary truth source.
- No stale-green or false-green status is acceptable.
- One active truth surface per topic.
- Parked lanes remain parked unless packet truth earns reentry.

## Pre-Start Gate

- Tracked worktree must be clean:
  `git status --short --untracked-files=no`
- Ambient unrelated untracked tail may exist in the repo, but for this contour
  the higher-order active rule in `MASTER_PLAN.md` governs pre-start cleanliness
  as tracked-file cleanliness. Ambient untracked files are noted but not touched
  unless a separate hygiene contour is opened.
- Previous contour work this contour depends on must be closed with
  verification, commit, and push.
- Current `MASTER_PLAN.md` correction must be closed before this contour starts.
- Owner authorization must be present before live runtime commands. Canonically
  valid authorization may be either the standing approval phrase present in the
  active thread or an exact one-off owner marker accepted by `CANON.md`.
- No new write/live contour starts from unresolved local-only truth.

## Declared Live Read Surfaces

The following exact real files or directories may be read by the admitted live
runtime commands in this contour:

- `/Users/kirillponomarev/.codex-custom-cli/`
- `/Users/kirillponomarev/.codex-custom-cli/auth.json`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh`
- `/Users/kirillponomarev/.codex-custom-cli/managed/`
- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-sync.sh`
- `/Users/kirillponomarev/.codex-custom-cli/managed/wild-boar-proxy.lock`
- `/Users/kirillponomarev/.codex-custom-cli/managed/approved-repair-target.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/target-switch-transaction.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-repair-target/`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.cli-proxy-api/config.yaml`

## Declared Live Write Surfaces

This contour may allow writes only through the invoked runtime owner commands.
Allowed changed files are limited to the following exact real files:

- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/stable-runtime-config.generated.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh` only if a
  command packet explicitly reports repo-owned launcher refresh

The contour must stop if command packets report writes to any other path,
including:

- repo source files
- sandbox `auth.json`
- onboarding auth materialization targets
- route registry or provider config surfaces
- lifecycle registry mutations outside the runtime owner path
- any private data surface not declared by the command packet

## Rollback Expectations

- No manual rollback is attempted from narrative memory.
- If a command packet reports a failed owner-path mutation with rollback
  information, preserve that packet and follow the command-provided
  `operator_action`.
- If changed files fall outside the declared write surfaces, stop and preserve
  evidence before any further command.
- If runtime truth remains blocked after attempted reproof, close with
  `STOP_AND_DIAGNOSE` and do not continue into selector refresh.

## In Scope

- Preserve selector-refresh v3 and handoff evidence.
- Reprove runtime truth through owner command surfaces only.
- Run `healthcheck --json` first.
- Run `status --json` after each runtime owner-path attempt.
- Run `launch smoke --json` only if `healthcheck --json` does not restore or
  prove runtime-green state.
- Run `rollout rotation inspect --json` only after runtime reproof, and only to
  classify next-contour readiness.
- Produce machine-carried packets and a decision packet.

## Out Of Scope

- No `sync --json`.
- No selector refresh execution.
- No sandbox `auth.json` materialization.
- No onboarding rerun.
- No exact auth-source admission.
- No route mutation.
- No UI/design work.
- No stage/pilot claim.
- No `stable repair --apply` inside this contour.

## Inputs

- `CANON.md`
- `MASTER_PLAN.md`
- `RUNTIME_CONTRACT.md`
- `STATE_SCHEMA.md`
- `COMMAND_API.md`
- `DELIVERY_RULES.md`
- `audit_results/thread_handoff_snapshot_2026-05-16.json`
- `audit_results/selector_refresh_owner_path_pass_2026-05-16_v3/*`
- `audit_results/runtime_reproof_pass_2026-05-16_v4/*`

## Commands

- `git status --short --untracked-files=no`
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy launch smoke --json` only if needed
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json` only for
  next-contour classification

## Acceptance Criteria

- `claim_gate = clear`, or a packet-preserved blocker explains why it remains
  blocked.
- `policy_drift = clear`, or a packet-preserved blocker explains the remaining
  drift.
- Effective stable runtime consumer truth is current and not inferred from
  stale activation evidence.
- Activation evidence is fresh enough to support the runtime conclusion.
- `rollout rotation inspect --json` is used only to classify selector readiness,
  not to claim selector refresh.
- No command result is treated as success without packet-level runtime truth.
- Parked lanes remain parked.

## Next-Contour Decision Rules

- If runtime-green is re-earned and selector evidence remains stale:
  next contour is `SELECTOR_REFRESH_OWNER_PATH_PASS`.
- If runtime truth remains blocked or contradictory:
  next contour is `STOP_AND_DIAGNOSE`.
- If packets localize a stable-policy/runtime contradiction:
  next contour is a narrower stable/runtime repair or reconciliation contour.
- If selector evidence becomes contradicted rather than stale:
  next contour is diagnosis, not auth-source admission.

## Stop Conditions

- Dirty tracked worktree at start.
- Contour-owned untracked or tracked tail outside the declared artifacts is
  present before live execution.
- Previous dependent contour is not closed with verification, commit, and push.
- Missing owner authorization for live runtime commands.
- Invalid JSON from any command packet.
- Contradictory authoritative command packets.
- Active or ambiguous lock state.
- Changed files outside declared runtime owner surfaces.
- `status --json` remains blocked without localized root cause.
- Any need to run `sync --json`, auth-source admission, onboarding, route
  mutation, or sandbox materialization inside this contour.

## Artifacts

- `audit_results/runtime_reproof_pass_2026-05-16_v5/contour.md`
- `preflight_packet.json`
- `authorization_gate_packet.json`
- `runtime_basis.json`
- `owner_path_reproof_packets.json`
- `runtime_truth_classification.json`
- `selector_followup_evaluation.json`
- `decision_packet.json`
- `independent_audit.md`
- `closeout.md`

## Verification

- Targeted CLI tests for healthcheck, launch-smoke, status, and rotation
  classification.
- `git diff --check`
- `python3 tools/check_closeout_resilience.py` for any new or changed closeout.
- `python3 tools/check_closeout_resilience.py --staged-only` before commit.

## Closeout

- Verification complete.
- Scope and private-data check complete.
- Closeout resilience check complete.
- Focused commit.
- Push.
- Final closeout note names the verification command, commit hash, and branch.
- Final next contour named from packet truth, not narrative memory.
