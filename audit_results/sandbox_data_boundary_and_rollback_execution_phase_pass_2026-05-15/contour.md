# SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_EXECUTION_PHASE_PASS

CONTOUR:
Goal: Materialize the minimal sandbox-local WBP filesystem scaffold under `/Users/kirillponomarev/.codex-custom-test` without drifting any live work-contour path.
Size: M
Risk level: high
Decision owner: operator
Mode: live-proof

In scope:
- confirm explicit owner authorization for external sandbox-local writes
- classify pre-existing data under `/Users/kirillponomarev/.codex-custom-test`
- snapshot forbidden live paths before and after writes
- create only the allowlisted scaffold paths and baseline files
- prove rollback/residue steps for the created scaffold

Out of scope:
- runtime validation
- live-server binding
- onboarding
- launch readiness
- auth import
- config or state copy from the work contour

Assumptions:
- the operator's explicit full-approval message is valid standing authorization for project-scoped development writes
- existing non-target files under `/Users/kirillponomarev/.codex-custom-test` remain untouched in this contour
- no runnable-sandbox claim is made from the created scaffold

Inputs:
- docs:
  - `/Volumes/Work/wild-boar-proxy/CANON.md`
  - `/Volumes/Work/wild-boar-proxy/MASTER_PLAN.md`
  - `/Volumes/Work/wild-boar-proxy/RUNTIME_CONTRACT.md`
  - `/Volumes/Work/wild-boar-proxy/COMMAND_API.md`
- code:
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/runtime.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/external_models/contracts.py`
  - `/Volumes/Work/wild-boar-proxy/wild_boar_proxy/external_models/integration.py`
  - `/Volumes/Work/wild-boar-proxy/tests/test_cli.py`
- runtime evidence:
  - pre-existing sandbox root inspection at `/Users/kirillponomarev/.codex-custom-test`
  - live work-contour references at `/Users/kirillponomarev/.codex-custom-cli` and `/Users/kirillponomarev/.cli-proxy-api/config.yaml`

Commands / files:
- `git status --short --untracked-files=no`
- `git log --oneline -n 10`
- `bash tools/install_git_hooks.sh`
- repo artifacts under `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_data_boundary_and_rollback_execution_phase_pass_2026-05-15/`
- external scaffold writes under `/Users/kirillponomarev/.codex-custom-test/{managed,stable,external-models,...}`

Acceptance criteria:
- explicit owner gate is preserved in an artifact
- pre-existing sandbox data is classified before the first write
- scaffold writes stay inside the allowlisted sandbox-local paths
- forbidden live work-contour paths remain byte-stable
- rollback/residue steps are concrete for the created scaffold
- no runtime, binding, or launch-readiness claim is made

Verification:
- tests:
  - snapshot diff for forbidden live paths
  - scaffold existence and permission checks
- build: not applicable
- manual:
  - filesystem path inspection for scaffold materialization
  - no-drift verification against prewrite snapshot
- live packet: not applicable

Artifacts:
- spec:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_data_boundary_and_rollback_execution_phase_pass_2026-05-15/contour.md`
- packet:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_data_boundary_and_rollback_execution_phase_pass_2026-05-15/decision_packet.json`
- closeout note:
  - `/Volumes/Work/wild-boar-proxy/audit_results/sandbox_data_boundary_and_rollback_execution_phase_pass_2026-05-15/closeout.md`

Stop conditions:
- owner approval cannot be proven
- target paths already contain data that would be overwritten
- pre-existing sandbox data under a target namespace is ambiguous
- a write outside the allowlist is required
- any forbidden live path drifts

Closeout:
- verification complete: yes
- commit: `9b0e9b1 Materialize sandbox execution-phase scaffold`
- push: yes
- next contour: `SANDBOX_LIVE_SERVER_BINDING_PASS` only if the decision packet says GO
