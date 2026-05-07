# STEP-18A Release Gate Alignment Report

- Step: `STEP-18A_OWNER_EVIDENCE_CLOSURE`
- Generated at (UTC): `2026-05-07T05:00:16Z`
- Claim scope: `machine-evidence-only`

## Command Evidence Table

| command | exit code | short fact |
|---|---:|---|
| `python3 -m unittest -q tests.test_cli -k onboard` | 0 | Ran 18 tests; unittest status OK |
| `python3 -m unittest -q tests/test_ui_shell.py` | 0 | Ran 82 tests; unittest status OK |
| `python3 -m unittest -q tests.test_cli -k installer` | 0 | Ran 2 tests; unittest status OK |
| `python3 -m unittest -q tests.test_cli -k legacy_import` | 0 | Ran 3 tests; unittest status OK |
| `python3 -m unittest -q tests.test_cli -k package_experimental` | 0 | Ran 7 tests; unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_diagnostics_export_redacts_runtime_state_and_registry_secrets` | 0 | Ran 1 test; unittest status OK |
| `python3 -m unittest -q tests.test_cli.CliTests.test_rollout_evidence_capture_16_redacts_bundle_secrets` | 0 | Ran 1 test; unittest status OK |

## Blocker Mapping

| blocker_id | status | fact |
|---|---|---|
| PILOT_ENTRY_ONBOARDING_EVIDENCE_MISSING | closed_by_machine_evidence | onboard-focused unittest selection completed with exit_code=0 |
| PILOT_ENTRY_UI_COMPLETION_EVIDENCE_MISSING | closed_by_machine_evidence | ui shell test suite completed with exit_code=0 |
| PILOT_ENTRY_SECURITY_EVIDENCE_MISSING | closed_by_machine_evidence | two redaction-focused security tests completed with exit_code=0 |
| PILOT_ENTRY_LEGACY_IMPORT_EVIDENCE_MISSING | closed_by_machine_evidence | legacy_import-focused unittest selection completed with exit_code=0 |
| PILOT_GATE_INSTALLER_AND_2W_METRICS_MISSING | still_blocked | installer-focused unittest selection completed with exit_code=0; two-week metrics evidence not provided in step18A scope |
| EXTERNAL_PACKAGE_GATE_EVIDENCE_MISSING | closed_by_machine_evidence | package_experimental-focused unittest selection completed with exit_code=0 |

## Residual Blocked Reasons

| item | status | reason |
|---|---|---|
| two-week metrics evidence | still_blocked | Required for pilot gate completion; no new machine evidence in step18A test scope. |
| scale20 completion evidence | still_blocked | step18A did not add a new controlled staged rollout-to-20 proof artifact. |
