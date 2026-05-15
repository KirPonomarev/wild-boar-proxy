CONTOUR:
Goal: Select the exact next repair contour after the active-lane auth/runtime STOP without smuggling mutation into the admission pass.
Size: M
Risk level: high
Decision owner: Codex
Mode: live-proof

In scope:
- blocker basis confirmation from current sandbox packets
- auth-source vs materialization scope split
- canon admissibility check for the next repair contour
- declared write surfaces and rollback expectations for the chosen next contour

Out of scope:
- real auth mutation
- real launcher/materialization execution
- lifecycle rerun
- later lifecycle actions

Assumptions:
- sandbox root remains `/Users/kirillponomarev/.codex-custom-test`
- current blocker truth is owned by `healthcheck --json`
- current contour decides scope only; it does not begin the next repair

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `STATE_SCHEMA.md`
  - `COMMAND_API.md`
- code:
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/cli.py`
  - `wild_boar_proxy/external_models/*`
- runtime evidence:
  - fresh sandbox `healthcheck --json`
  - fresh sandbox `status --json`
  - fresh sandbox `sync --json`
  - `stable target switch --dry-run --json`
  - `stable repair --dry-run --json`
  - fresh sandbox `external-models status/routes/models --json`

Commands / files:
- `python3 -m wild_boar_proxy healthcheck --json`
- `python3 -m wild_boar_proxy status --json`
- `python3 -m wild_boar_proxy sync --json`
- `python3 -m wild_boar_proxy stable target switch --dry-run --json`
- `python3 -m wild_boar_proxy stable repair --dry-run --json`
- `python3 -m wild_boar_proxy external-models status --json`
- `python3 -m wild_boar_proxy external-models routes list --json`
- `python3 -m wild_boar_proxy external-models models --json`
- `python3 -m unittest -q tests.test_cli.CliTests.test_accounts_promote_status_verification_failure_rolls_back tests.test_cli.CliTests.test_status_reports_stable_runtime_consumer_contract_when_approved_target_not_ready tests.test_cli.CliTests.test_stable_target_switch_dry_run_returns_contract_without_mutation tests.test_cli.CliTests.test_stable_repair_dry_run_reports_not_needed_when_target_matches_eligible_registry_auths`

Acceptance criteria:
- exact next repair contour selected or honest STOP preserved
- selected contour has explicit write surfaces
- selected contour has explicit rollback expectations
- auth-source and materialization responsibilities remain separated unless canon requires fusion

Verification:
- tests: targeted unittest quartet passes
- build: `git diff --check`
- manual: artifact review + canon references
- live packet: fresh sandbox packets preserved in blocker basis

Artifacts:
- spec: `contour.md`
- packet: `decision_packet.json`
- closeout note: `closeout.md`

Stop conditions:
- canon does not justify an admissible next mutation scope
- scope selection depends on hidden auth mutation
- scope selection depends on hidden launcher execution
- combined scope is chosen without fused owner-path justification

Closeout:
- verification complete: yes
- commit: pending
- push: pending
- next contour: `SANDBOX_ACTIVE_LANE_AUTH_SOURCE_REPAIR_PASS`
