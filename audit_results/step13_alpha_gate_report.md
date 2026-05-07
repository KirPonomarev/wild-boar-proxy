# STEP-13 Alpha Gate Report (Isolated Runtime)

## Command Replay Table

| command | exit code | evidence |
|---|---:|---|
| `python3 -m unittest -q tests.test_cli.CliTests.test_healthcheck_returns_attestation` | `0` | `Ran 1 test`, `OK` (attestation surface verified by existing unit assertion set). |
| `python3 -m unittest -q tests.test_cli.CliTests.test_status_uses_live_attestation_for_green_state` | `0` | `Ran 1 test`, `OK` (status delegated attestation summary path verified). |
| `python3 -m unittest -q tests.test_cli.CliTests.test_sync_returns_single_json_object` | `0` | `Ran 1 test`, `OK` (single JSON object expectation for owner command). |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_stage_advance_15_blocks_cross_thread_mode_mutation_during_policy_step` | `0` | `Ran 1 test`, `OK`; interleaving path enforces serialized lock semantics. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_healthcheck_owner_path_reports_observed_source_fallback_recovery` | `0` | `Ran 1 test`, `OK`; forced managed preflight failure fallback path validated. |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_reports_complete_packet` | `0` | `Ran 1 test`, `OK`; expected `scale_gate_summary` with all alpha gates `passed`. |
| `python3 -m unittest -q tests/test_cli.py -k "healthcheck or status or advance or fallback"` | `0` | Ran `0 tests`; recorded as non-gating replay only and explicitly excluded from coverage evidence. |
| `python3 -m unittest -q tests/test_ui_shell.py` | `0` | `Ran 82 tests`, `OK`; strict JSON parser/consumer behavior covered. |
| `python3 -m unittest -q tests.test_cli -k healthcheck` | `0` | `Ran 27 tests`, `OK`. |
| `python3 -m unittest -q tests.test_cli -k status` | `0` | `Ran 37 tests`, `OK`. |
| `python3 -m unittest -q tests.test_cli -k advance` | `0` | `Ran 31 tests`, `OK`. |
| `python3 -m unittest -q tests.test_cli -k fallback` | `0` | `Ran 4 tests`, `OK`. |
| `python3 -m wild_boar_proxy healthcheck --json` (isolated temp runtime + `WBP_*`) | `0` | strict JSON: `true`; `status=ok`; `machine_error_code=OK`; attestation required fields present; `attestation_source=healthcheck --json`. |
| `python3 -m wild_boar_proxy status --json` (isolated temp runtime + `WBP_*`) | `0` | strict JSON: `true`; `status=ok`; `machine_error_code=OK`; `attestation_summary` required fields present (`status`, `machine_error_code`, `attestation_source`). |
| `python3 -m wild_boar_proxy sync --json` (isolated temp runtime + `WBP_*`) | `0` | strict JSON: `true`; `status=ok`; `machine_error_code=OK`; stderr only expected script marker (`sync-ran`). |
| `python3 -m wild_boar_proxy rollout evidence capture 16 --json` (executed via existing `CliTests` fixture helpers) | `0` | `status=ok`; `machine_error_code=OK`; `packet_status=complete`; `final_outcome=field_evidence_packet_complete`; `blocked_reasons=[]`; `blocked_gate_names=[]`; gate statuses: runtime/strict-json/state-serialization/fallback all `passed`. |
| `python3 -m wild_boar_proxy healthcheck --json` with forced launcher nonzero (`exit=9`) in fixture | `0` | `status=ok`; `machine_error_code=OK`; deterministic recovery outcome `observed_source_fallback_recovered`; `entry_lane=managed_preflight_failure`; `fallback_reason=launcher_exit_nonzero`; `live_runtime_observation_confirmed=true`. |
| stage-advance interleaving regression path via existing runtime test harness (`run_rollout_stage_advance`) | `0` | payload `status=ok`; `machine_error_code=OK`; concurrent mode mutation returns `LOCK_HELD` + `operator_action=retry`; `runtime_mode_after=managed`. |

## Gate Verdicts

- `RUNTIME_ATTESTATION_GATE`: **PASS** (`healthcheck/status` JSON surfaces include attestation fields; evidence packet gate status `passed`).
- `STRICT_JSON_COMMAND_API_GATE`: **PASS** (direct strict single-object checks for `healthcheck/status/sync`; evidence packet gate status `passed`).
- `STATE_SERIALIZATION_GATE`: **PASS** (interleaving regression confirms lock behavior; evidence packet gate status `passed`).
- `FALLBACK_DRILL_GATE`: **PASS** (forced managed failure fallback produces truthful observed-source recovery; evidence packet gate status `passed`).

## Stop-Condition Scan Result

- Source used: `rollout evidence capture 16 --json` complete-packet run in isolated fixture runtime.
- Observed:
  - `packet_status=complete`
  - `blocked_reasons=[]`
  - `scale_gate_summary.blocked_gate_names=[]`
  - all alpha gates are `passed`
- Stop-condition classification:
  - no `incomplete`
  - no `contradicted`
  - no `unsafe_to_claim`
- Result: **no stop-condition trigger detected in this alpha verification contour**.

## Coverage Note

- The command `python3 -m unittest -q tests/test_cli.py -k "healthcheck or status or advance or fallback"` is preserved in replay history but is not part of gate coverage because it selected zero tests in this environment.
- Gate coverage is established by targeted `CliTests` single-test replays plus grouped runs:
  - `python3 -m unittest -q tests.test_cli -k healthcheck`
  - `python3 -m unittest -q tests.test_cli -k status`
  - `python3 -m unittest -q tests.test_cli -k advance`
  - `python3 -m unittest -q tests.test_cli -k fallback`
