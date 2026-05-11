CONTOUR:
ID:
COMPOSITE_RUNTIME_RECONCILIATION_PROOF_CONTOUR

Goal:
Reprove simultaneous green execution-core truth through the explicitly admitted
bounded sequence `sync --json -> launch smoke --json`, without expanding this
contour into reserve-readiness mutation, posture normalization, stage-20
re-entry, same-day validation, or UI.

Immediate reason:
- `step68` closed:
  - `NO_GO_UPSTREAM_BLOCKER_RECHECK`
- primary verdict:
  - `EXECUTION_CORE_REGRESSED_BEFORE_BRANCH_C_COULD_REOPEN`
- fresh preflight truth in `step68` showed:
  - `claim_gate.status=blocked`
  - `policy_drift.status=detected`
  - `consumer_activation_readiness=STABLE_RUNTIME_CONSUMER_ACTIVATION_PENDING`
  - `rollout rotation inspect --json -> ROTATION_EVIDENCE_STALE`
- therefore Branch C reserve-readiness reopening is no longer admissible
- the next legal contour is execution-core reconciliation first

Mode:
live-proof

Admitted owner surfaces:
1. `sync --json`
2. `launch smoke --json`

Execution shape:
1. Capture fresh preflight packets:
   - `status --json`
   - `healthcheck --json`
   - `accounts list --json`
   - `rollout rotation inspect --json`
2. Declare bounded sequence, write surfaces, rollback expectation, and stop
   conditions.
3. Execute `sync --json`.
4. Reread `rollout rotation inspect --json`.
5. If rotation is green enough, execute `launch smoke --json`.
6. Capture final postflight packets:
   - `status --json`
   - `healthcheck --json`
   - `accounts list --json`
   - `rollout rotation inspect --json`
7. Close with factual convergence verdict.

Primary success criteria:
- `claim_gate.status=clear`
- `policy_drift.status=clear`
- `consumer_activation_readiness=OK`
- desired stable-runtime source equals effective source
- `rotation_machine_error_code=OK`
- `rotation_evidence_freshness=fresh`
- partial green is not success
