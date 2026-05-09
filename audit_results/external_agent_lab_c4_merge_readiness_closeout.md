# External Agent Lab C4 Merge Readiness Closeout

Date: `2026-05-09`
Contour: `external_agent_lab_c4_merge_readiness_pr`
Branch: `codex/external-agent-lab-isolated`

## Scope

In scope:

- merge-readiness verification and packaging for isolated lab lane
- consistency re-audit against C3 artifacts
- closeout evidence recording

Out of scope:

- `wild_boar_proxy/*`
- provider/live probes
- runtime integration
- new model-lane promotions

## Canonical Verification Commands

```bash
python3 -m compileall -q external_agent_lab run_lab.py agent_eval.py tests/test_external_agent_lab.py
python3 -m unittest -q tests.test_external_agent_lab
python3 -m unittest -q tests.test_web_ui
python3 -m unittest -q tests.test_ui_shell
python3 -m unittest -q tests.test_cli.CliTests.test_accounts_hold_applies_protective_hold_with_verified_routing_isolation
git diff --check
git diff --name-only -- wild_boar_proxy
```

Observed outcomes:

- compileall: success
- `tests.test_external_agent_lab`: `Ran 10 tests ... OK`
- `tests.test_web_ui`: `Ran 4 tests ... OK`
- `tests.test_ui_shell`: `Ran 90 tests ... OK`
- `tests.test_cli...verified_routing_isolation`: `Ran 1 test ... OK`
- `git diff --check`: clean
- `git diff --name-only -- wild_boar_proxy`: empty

## Merge Readiness Notes

- branch is synced with remote before C4 closeout edits
- C3 artifacts are present:
  - `EXTERNAL_AGENT_LAB.md`
  - `EXTERNAL_AGENT_LAB_AUDIT.md`
  - `external_agent_lab_acceptance_verification.md`
- acceptance path remains unittest-first and provider/live-free

## Independent Audit

Independent consistency audit was executed with factual checks:

- `python3 -m unittest -q tests.test_external_agent_lab` -> `Ran 10 tests ... OK`
- `git diff --name-only -- wild_boar_proxy` and
  `git status --short -- wild_boar_proxy` -> empty
- C3 documents checked for consistency:
  `EXTERNAL_AGENT_LAB.md`, `EXTERNAL_AGENT_LAB_AUDIT.md`,
  `external_agent_lab_acceptance_verification.md`

Audit verdict:

- no direct contradictions found
- overclaim risk is low
- caveat: provider/live behavior was not re-probed in this audit, by design
