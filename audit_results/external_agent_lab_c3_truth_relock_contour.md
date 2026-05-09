# External Agent Lab C3 Truth Relock Contour

Date: `2026-05-09`
Contour: `external_agent_lab_c3_truth_relock_and_acceptance_docs`
Branch: `codex/external-agent-lab-isolated`

## Scope

In scope:

- `EXTERNAL_AGENT_LAB.md`
- `EXTERNAL_AGENT_LAB_AUDIT.md`
- `external_agent_lab_acceptance_verification.md`
- `external_agent_lab/model_registry_seed.json`
- `tests/test_external_agent_lab.py`

Out of scope:

- `wild_boar_proxy/*`
- provider/live execution
- runtime integration

## Verification Commands And Outcomes

```bash
python3 -m compileall -q external_agent_lab run_lab.py agent_eval.py tests/test_external_agent_lab.py
python3 -m unittest -q tests.test_external_agent_lab
python3 -m unittest -q tests.test_web_ui
python3 -m unittest -q tests.test_ui_shell
python3 -m unittest -q tests.test_cli.CliTests.test_accounts_hold_applies_protective_hold_with_verified_routing_isolation
```

Outcomes:

- compileall: success
- `tests.test_external_agent_lab`: `Ran 10 tests ... OK`
- `tests.test_web_ui`: `Ran 4 tests ... OK`
- `tests.test_ui_shell`: `Ran 90 tests ... OK`
- `tests.test_cli...verified_routing_isolation`: `Ran 1 test ... OK`

## Scope Verification

- `git diff --name-only -- wild_boar_proxy` -> empty
- `git diff --check` -> clean
- no provider/live command required by this contour
