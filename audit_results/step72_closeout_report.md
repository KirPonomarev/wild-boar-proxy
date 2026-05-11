Result:
- `OWNER_SURFACE_CONTRADICTION_REPAIR_CONTOUR` closed as repo repair complete
- next lawful contour: `FRESH_RESERVE_INPUT_OR_POOL_CHANGE_RECHECK_CONTOUR`

What changed:
- `run_onboard()` now performs a post-sync reserve-first verification gate
- the owner surface no longer claims reserve-first success if sync moves the
  selected backend into `active` or selected routing
- test harness can now simulate registry+state sync mutations
- targeted regression covers the reproduced contradiction chain

Verification:
- `python3 -m py_compile wild_boar_proxy/runtime.py tests/test_cli.py`
- `4/4` focused onboarding regression pack passed
- `19/19` `test_accounts_onboard_*` pack passed
- `git diff --check` passed
- independent inspector approved with monitoring

Scope check:
- repo repair only
- no live mutation
- no UI
