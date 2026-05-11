Primary repair:
- add a post-sync reserve-first verification gate inside `run_onboard()`
- re-read registry/state after sync+status proof
- fail with fatal owner packet if the selected backend enters active routing or
  no longer remains in `reserve`

Test support:
- add a sync test helper that mutates both registry and state
- add one regression proving sync-driven promotion of the selected onboarded
  backend cannot close as reserve-first success

Scope guard:
- no live mutation
- no rollout-stage work
- no UI
