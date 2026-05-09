# External Agent Lab Acceptance Verification

Date: `2026-05-09`
Contour: `external_agent_lab_c3_truth_relock_and_acceptance_docs`
Branch: `codex/external-agent-lab-isolated`

## Command Verification

Executed commands:

```bash
python3 -m compileall -q external_agent_lab run_lab.py agent_eval.py tests/test_external_agent_lab.py
python3 -m unittest -q tests.test_external_agent_lab
python3 -m unittest -q tests.test_web_ui
python3 -m unittest -q tests.test_ui_shell
python3 -m unittest -q tests.test_cli.CliTests.test_accounts_hold_applies_protective_hold_with_verified_routing_isolation
```

Observed outcomes:

- `compileall`: success
- `tests.test_external_agent_lab`: `Ran 10 tests ... OK`
- `tests.test_web_ui`: `Ran 4 tests ... OK`
- `tests.test_ui_shell`: `Ran 90 tests ... OK`
- `tests.test_cli...verified_routing_isolation`: `Ran 1 test ... OK`

No provider/live commands were required for this acceptance verification.

## Preflight Contract Proof

Proof was captured through patched test path by forcing
`ensure_supported_python` to raise `LabError` in `external_agent_lab.cli.main`.

Observed proof packet:

```json
{
  "exit_code": 1,
  "human_message": "External Agent Lab requires Python >= 3.9.",
  "lab_mode": true,
  "machine_error_code": "invalid_request",
  "return_code": 1,
  "status": "error",
  "stdout_is_single_json_object": true,
  "traceback_present": false,
  "uncaught_exception": false
}
```

## Acceptance Conditions

```text
unsupported_python_returns_json_packet = true
uncaught_laberror_on_preflight = false
traceback_on_preflight = false
verification_report_requires_pytest = false
canonical_acceptance_commands_are_reproducible = true
acceptance_artifact_reissued_after_fix = true
```

## Scope Check

```text
main_runtime_modified = false
wild_boar_proxy_touched = false
external_lab_isolation_preserved = true
```
