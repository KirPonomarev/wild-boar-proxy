# External Lab C24 Operation Declaration

Contour: `c24_pre_integration_runtime_remediation`
Date: `2026-05-11`

Canon precedence:
`CANON.md > MASTER_PLAN.md > RUNTIME_CONTRACT.md > STATE_SCHEMA.md > COMMAND_API.md > DELIVERY_RULES.md`

Declared write surfaces:
- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`
- `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/cli.py`
- `/Volumes/Work/wild-boar-proxy/tests/test_cli.py`
- `/Volumes/Work/wild-boar-proxy/audit_results/external_lab_c24_*`

Execution boundaries:
- no integration execution
- no Gate B work
- no UI/release work
- no live account-state repair
- no quota refresh

Quota / limit rule:
- `quota_exhausted`, `rate_limited`, and stale-limit signals are non-blocking only when they do not affect B1-B4 acceptance surfaces and do not mask a runtime-contract regression.

Live runtime boundary:
- `LOCK_HELD` and `ROTATION_EVIDENCE_CONTRADICTED` observed in precondition are preserved as machine truth.
- C24 does not attempt live state repair or contradiction resolution.

Rollback expectations:
- if targeted remediation regresses unrelated runtime contracts, revert only contour-owned edits
- preserve failing evidence before any rollback
- emit `HOLD_WITH_EXACT_BLOCKERS` if full `tests.test_cli` cannot be closed inside declared surfaces
