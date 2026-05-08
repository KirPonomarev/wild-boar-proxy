# STEP-14 STABLE-10 Proof Canon Report (Isolated Runtime)

## Command Replay Table

| command | exit code | evidence |
|---|---:|---|
| `python3 - <<'PY' ...` (isolated `CliTests` fixture replay for `healthcheck --json`, `status --json`, `rollout rotation inspect --json`, `rollout stage prove 10 --json`) | `0` | `healthcheck`: `machine_error_code=OK`; `status`: `attestation_summary.status=ok`; `rotation inspect`: `machine_error_code=OK`, `rotation_evidence_status=participation_evidence_present`, `blocker_type=none`; `stage prove 10`: `machine_error_code=OK`, `proof_gate_status=stable_10_gate_closed`, `final_outcome=stable_10_proved`, `runtime_attestation_status=passed`, `rotation_evidence_status=available`, `rollback_readiness_status=ready`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_prove_10_reports_runtime_attestation_failure` | `0` | `Ran 1 test`, `OK`; negative attestation path covered (`STAGE_PROOF_ATTESTATION_FAILED`, `final_outcome=runtime_attestation_failed` in assertions). |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_prove_10_reports_success_with_bounded_delegated_evidence` | `0` | `Ran 1 test`, `OK`; positive stable-10 proof path asserts `final_outcome=stable_10_proved`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_prove_10_reports_rotation_insufficiency` | `0` | `Ran 1 test`, `OK`; negative rotation insufficiency path asserts `machine_error_code=STAGE_PROOF_ROTATION_INSUFFICIENT`, `final_outcome=rotation_evidence_insufficient`. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_holds_outer_serialization_lock_across_composite_steps` | `0` | `Ran 1 test`, `OK`; serialization lock is held across prove/policy/promote/materialize/postflight sequence. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_blocks_held_lock_without_mutation` | `0` | `Ran 1 test`, `OK`; lock contention path returns `LOCK_HELD` without mutation. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_fails_on_postflight_contradiction_after_promotion` | `0` | `Ran 1 test`, `OK`; contradicted rotation/postflight evidence path covered (`STAGE_ADVANCE_POSTFLIGHT_ROTATION_FAILED`, rollback outcome asserted). |
| `python3 -m unittest -q tests.test_cli -k "prove_10 or stage_prove or rollback_readiness"` | `0` | `Ran 0 tests`; recorded for parity with requested grouped command, explicitly **non-gating**. |
| `python3 -m unittest -q tests.test_cli -k stage_prove` | `0` | `Ran 16 tests`, `OK`; grouped stage-prove contour coverage. |
| `python3 -m unittest -q tests.test_cli -k rollback_readiness` | `0` | `Ran 3 tests`, `OK`; grouped rollback-readiness contour coverage. |
| `python3 -m unittest -q tests.test_cli -k prove_10` | `0` | `Ran 7 tests`, `OK`; grouped stable-10 prove contour coverage. |
| `python3 -m unittest -q tests/test_ui_shell.py` | `0` | `Ran 82 tests`, `OK`; UI shell snapshot/contract suite passes. |

## Precheck Result

- Environment contour: isolated temp runtime through test fixtures and `WBP_*` only (no real `~/.codex-custom-cli`, no real `~/.cli-proxy-api`).
- Supporting owner surfaces in the same controlled replay:
  - `healthcheck --json`: `status=ok`, `machine_error_code=OK`.
  - `status --json`: `status=ok`, `machine_error_code=OK`, delegated attestation summary present.
  - `rollout rotation inspect --json`: `status=ok`, `machine_error_code=OK`, evidence present (`blocker_type=none`).
- Proof owner surface:
  - `rollout stage prove 10 --json`: `status=ok`, `machine_error_code=OK`, `proof_gate_status=stable_10_gate_closed`, `final_outcome=stable_10_proved`.

## Gate Verdicts (Stable-10 Contour)

- `STAGE_POLICY_MATCH_GATE`: **PASS** (proof reports stage matched for stage 10).
- `ACTIVE_POOL_GATE`: **PASS** in positive replay; negative mismatch path covered by suite.
- `ROTATION_EVIDENCE_GATE`: **PASS** in positive replay; insufficiency and contradiction negatives covered by targeted tests.
- `RUNTIME_ATTESTATION_GATE`: **PASS** in positive replay; explicit attestation-failed negative path covered.
- `ROLLBACK_READINESS_GATE`: **PASS** in positive replay and grouped rollback-readiness suite.
- `SERIALIZATION_LOCK_GATE` (prove/advance lane safety): **PASS** via lock-held and outer-lock coverage.

## Findings

- None (no P0/P1/P2/P3 defects identified in this step-14 contour during replay).

## Non-Gating Replay Note

- `python3 -m unittest -q tests.test_cli -k "prove_10 or stage_prove or rollback_readiness"` executed with `Ran 0 tests`; this command is retained in replay history but is non-gating.
- Gating grouped coverage is provided by working chunks:
  - `python3 -m unittest -q tests.test_cli -k stage_prove`
  - `python3 -m unittest -q tests.test_cli -k rollback_readiness`
  - `python3 -m unittest -q tests.test_cli -k prove_10`

## Outcome

- Achieved: `stable_10_proved`.
- Machine reason: `OK` (`rollout stage prove 10 --json` in isolated fixture replay).
- Claim scope: bounded to stable-10 contour only (no claims above `stable_10`).
