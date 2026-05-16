# SELECTOR_REFRESH_OWNER_PATH_PASS_RETRY_ONCE

## Goal

Retry canonical selector refresh exactly once after lock diagnosis closed, then
decide from fresh packet truth whether selector evidence is re-earned or the
chain must stop again.

## Why This Contour Is Next

- prior selector refresh stopped on `LOCK_HELD`
- lock diagnosis localized the blocker as a true concurrent lock with
  post-packet release, not stale-lock ambiguity
- sync-specific held-lock and stale-lock behavior is now directly tested
- canon allows a bounded retry only after new contradiction diagnosis

## Canon Basis

- `CANON.md` outranks all lower docs
- fresh lock-diagnosis closeout outranks stale top-pointer text in `MASTER_PLAN.md`
- anti-loop rule forbids open-ended sync retries
- runtime-green truth does not count as selector success; selector evidence must
  be re-earned directly

## In Scope

- `git status --short --untracked-files=no`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy rollout rotation inspect --json`
- `python3 -m wild_boar_proxy status --json`
- machine-readable packets, independent audit, decision packet, closeout

## Out Of Scope

- no second `sync --json` retry inside this contour
- no `launch smoke --json`
- no exact auth-source admission
- no sandbox `auth.json` materialization
- no onboarding rerun
- no route mutation
- no UI/release work

## Declared Live Write Surfaces

- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json` only if packet truth reports it
- `/Users/kirillponomarev/.codex-custom-cli/managed/wild-boar-proxy.lock` as transient lock surface only
