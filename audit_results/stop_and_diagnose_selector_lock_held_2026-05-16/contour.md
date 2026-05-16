# STOP_AND_DIAGNOSE_SELECTOR_LOCK_HELD

## Goal

Localize and explain the transient `LOCK_HELD` blocker from the failed
`SELECTOR_REFRESH_OWNER_PATH_PASS` re-entry, then decide whether a fresh
selector retry contour is admissible without violating the anti-loop rule.

## Why This Contour Is Next

- fresh selector refresh attempt stopped with `LOCK_HELD`
- `sync --json` produced no progress and no changed files
- selector evidence remained stale before and after the attempt
- runtime truth stayed green, so the blocker is a narrow selector owner-path
  lock diagnosis problem, not a broad runtime-repair problem

## Canon Basis

- `CANON.md` outranks all lower docs
- fresh contour closeout evidence outranks stale master-plan pointer text
- `MASTER_PLAN.md` anti-loop rule forbids re-running `sync --json` without new
  contradiction diagnosis
- no selector retry is honest until the lock blocker is localized

## In Scope

- inspect selector owner-path lock handling in repo code
- inspect lock-file lifecycle and stale-pid handling logic
- classify whether `LOCK_HELD` came from true concurrent work, stale lock, or
  packet ambiguity
- add only minimal guard coverage if diagnosis reveals an evidence gap
- produce machine-readable diagnosis artifacts and next-step decision

## Out Of Scope

- no `sync --json` retry inside this contour
- no selector refresh execution
- no `rollout rotation inspect --json` retry by inertia
- no `launch smoke --json`
- no auth/source, sandbox, onboarding, route, or UI work

## Verification Plan

- targeted lock-handling tests
- `git diff --check`
- `python3 tools/check_closeout_resilience.py` for closeout
- `python3 tools/check_closeout_resilience.py --staged-only` before commit
