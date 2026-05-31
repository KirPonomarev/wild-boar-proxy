# SELECTOR_REFRESH_OWNER_PATH_PASS_RETRY_ONCE Closeout

## Goal

Retry canonical selector refresh exactly once after lock diagnosis closed, then
decide from fresh packet truth whether selector evidence is re-earned or the
chain must stop again.

## Result

- status: `stopped`
- final verdict: `STOP_AND_DIAGNOSE`
- next action: localize repeated selector lock contention and post-retry
  runtime regression before any further live retry

## Contour Capsule

- goal: perform one bounded selector refresh retry and stop on any repeated
  lock/no-progress outcome
- branch: `codex/external-agent-lab-isolated`
- head: `d02a468`
- touched files:
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/*`
- tests run:
  - `git status --short --untracked-files=no`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m wild_boar_proxy sync --json`
  - `python3 -m wild_boar_proxy rollout rotation inspect --json`
  - `python3 -m wild_boar_proxy status --json`
  - independent packet audits
  - `python3 tools/check_closeout_resilience.py audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - repeated live lock contention remained unresolved
  - runtime truth regressed after the failed retry
- next exact command:
  - `rg -n "LOCK_HELD|wild-boar-proxy\\.lock|serialized_lock|claim_gate|policy_drift" wild_boar_proxy tests`

## Verification

- tests:
  - bounded live packet chain captured successfully
- build:
  - packet JSON files written successfully
- manual:
  - pre-sync selector evidence was stale
  - `sync --json` returned `LOCK_HELD` with holder pid `53546`
  - post-sync selector read remained blocked and returned `LOCK_HELD`
  - lock file was already absent on follow-up observation
  - `status --json` after retry regressed to `claim_gate = blocked` and
    `policy_drift = detected`
- live verification:
  - no selector progress was earned
  - no undeclared writes occurred
  - bounded retry budget was exhausted

## Artifacts

- spec:
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/contour.md`
- packet:
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/selector_retry_basis.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/rotation_before_sync.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/sync_refresh_packet.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/rotation_after_sync.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/status_after_sync.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/decision_packet.json`
- report:
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; only bounded packet outputs and lock-state
  observations were recorded`

## Notes

- blockers encountered:
  - bounded retry hit a new live lock holder pid `53546`
  - runtime truth regressed after the failed selector retry
- follow-up contour:
  - `STOP_AND_DIAGNOSE`
- resume from here: `CLOSED / STOP_AND_DIAGNOSE`
