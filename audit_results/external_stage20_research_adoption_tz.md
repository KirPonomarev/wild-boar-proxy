<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Stage20 Research Adoption Specification

## Objective

Convert the external stage-20 research bundle into a canon-aligned,
merge-safe, testable set of repository changes and an improved output contract
for future external agent research.

## Inputs

- `/Users/kirillponomarev/Downloads/wbp_execution_core_stage20_fix.patch`
- `/Users/kirillponomarev/Downloads/wbp_agent_integration_notes.md`
- `/Users/kirillponomarev/Downloads/wbp_execution_core_stage20_fix_files.tar.gz`
- `audit_results/external_stage20_research_assessment.md`

## Canon Order

When this specification conflicts with local docs, follow:

1. `CANON.md`
2. `MASTER_PLAN.md`
3. `RUNTIME_CONTRACT.md`
4. `STATE_SCHEMA.md`
5. `COMMAND_API.md`
6. `DELIVERY_RULES.md`
7. `README.md`

## Current Verified Reality

1. The external patch does not apply cleanly to current `HEAD`.
2. The research contains at least two useful execution-core ideas:
   - a read-only posture classifier
   - a stage-advance lock-boundary fix
3. The research also contains one disputed semantic rewrite:
   - reserve posture interpreted as minimum depth instead of exact count
4. That disputed rewrite cannot be merged without ADR and contract review.

## Scope

In scope:

1. manual porting of safe research ideas into current repository state
2. explicit adoption contract for future external agent outputs
3. tests and docs required for the safe repo changes
4. ADR preparation for reserve-semantics review

Out of scope:

1. blind application of the external patch
2. engine-layer changes
3. UI work
4. live mutation based on this research alone
5. wholesale `runtime.py` redesign

## Workstream A: External-Agent Output Contract

### Goal

Make future research bundles directly auditable before they are proposed for
integration.

### Required Output Fields

Every future external research bundle must include:

- `target_branch`
- `target_commit`
- `apply_status`
- `files_changed`
- `ideas`
- `verification`
- `adr_required`

### Required `apply_status` values

- `APPLIES_CLEAN`
- `APPLIES_WITH_MANUAL_PORT`
- `DOES_NOT_APPLY`

### Required idea classification

Each idea must be labeled as one of:

- `safe_to_port`
- `contract_review_required`
- `live_only_guidance`
- `reject_or_rewrite`

### Required verification breakdown

The agent must distinguish:

- `py_compile`
- `targeted_tests`
- `relevant_contour_tests`
- `full_suite`

### Acceptance

This workstream is done when a machine-readable manifest schema is written and
example output exists for the current bundle.

## Workstream B: Adoption Matrix For The Current Bundle

### Goal

Turn the external research into a precise port plan.

### Required classifications

#### Safe To Port Now

1. `rollout posture inspect <15|20> --json`
2. stage-advance precondition reads under `serialized_lock`
3. explicit blocker taxonomy surfaced through JSON

#### ADR Required

1. reserve minimum-depth semantics
2. any proof/postflight behavior change caused by that semantic rewrite

#### Reject Or Rewrite

1. the raw patch
2. any claim that targeted rollout tests imply full merge safety
3. any live claim not re-confirmed against current owner surfaces

### Acceptance

This workstream is done when the current bundle is recorded in a written
adoption matrix and no remaining idea is unlabeled.

## Workstream C: Add `rollout posture inspect`

### Goal

Add a bounded read-only owner surface for pre-advance posture classification.

### Command

```sh
python3 -m wild_boar_proxy rollout posture inspect <15|20> --json
```

### Required behavior

- no writes
- no hidden recovery
- no stage transition
- no policy rewrite
- no registry mutation
- strict JSON output

### Required output fields

- `requested_stage`
- `source_stage`
- `classification`
- `blocker_code`
- `pool_count_summary`
- `candidate_summary`
- `runtime_truth_summary`
- `policy_stage_summary`
- `rotation_summary`
- `normalization_decision_packet`

### Minimum classifications

- `INSUFFICIENT_ELIGIBLE_POOL`
- `RESERVE_CANDIDATE_NOT_IDENTIFIED`
- `LIVE_POSTURE_DRIFT_ONLY`
- `ROTATION_EVIDENCE_INSUFFICIENT`
- `READY_FOR_STAGE_ADVANCE`
- `READY_ALREADY_ON_TARGET`

### Files likely touched

- `wild_boar_proxy/cli.py`
- `wild_boar_proxy/runtime.py`
- `COMMAND_API.md`
- `tests/test_cli.py`

### Test requirements

1. add a step41-shaped fixture for:
   - `24 active`
   - `0 reserve`
   - one live-capable selected backend
2. prove that posture inspect returns the expected classification for that shape
3. prove the command does not mutate registry or state

### Acceptance

- command exists
- command is read-only
- classification is explicit
- tests pass
- docs are updated

## Workstream D: Stage-Advance Serialization Repair

### Goal

Close the precondition-read window in `run_rollout_stage_advance()`.

### Current defect

The current function reads registry/stage/pool/backend preconditions before
entering `serialized_lock(paths)`.

### Required change

These reads must become owner-lock protected:

- registry read
- observed stage read
- pool counts
- target-already-satisfied evaluation
- backend eligibility evaluation

### Test requirements

Add a regression test that proves:

- if the owner lock is already held, stage advance must not leak an optimistic
  stale precondition result
- the command must fail with lock contention instead of pre-lock eligibility
  optimism

### Files likely touched

- `wild_boar_proxy/runtime.py`
- `tests/test_cli.py`

### Acceptance

- preconditions are built under the serialized owner lock
- lock regression test passes
- existing stage-advance tests remain green

## Workstream E: Reserve-Semantics ADR

### Goal

Decide whether reserve posture remains exact-count or changes to minimum depth.

### ADR question

Should staged reserve semantics stay:

```text
reserve_count == reserve_target
```

or move to:

```text
reserve_count >= reserve_target
```

### Current exact-count contract surfaces

- `wild_boar_proxy/runtime.py` around:
  - `7979-7980`
  - `8267`
  - `8362`
- `tests/test_cli.py` around:
  - `9596`
  - `11751`

### Required ADR content

1. context
2. current behavior
3. proposed behavior
4. operational pain caused by exact-count reserve posture
5. benefits and risks of minimum-depth semantics
6. effect on:
   - stage proof
   - stage advance postflight
   - promote/normalize flows
   - docs
   - tests
   - operator expectations

### Acceptance

No reserve-semantics code change merges before ADR acceptance.

## Workstream F: Test Hardening

### Goal

Prevent external research from producing fragile or environment-dependent tests.

### Required improvements

1. use deterministic probe fixtures
2. avoid assumptions about idle localhost ports
3. avoid stale-environment dependencies
4. model candidate classes explicitly:
   - active live-capable
   - reserve live-capable
   - quota-limited
   - auth-invalid
   - unverified

### Acceptance

- targeted tests pass
- relevant rollout contour passes
- full `tests.test_cli` passes before merge

## Workstream G: Documentation And Handoff

### Goal

Make the integration understandable to a team that does not have direct repo
access.

### Required deliverables

1. corrected assessment document
2. adoption matrix
3. machine-readable manifest
4. implementation order
5. test matrix
6. ADR requirement note

### Required doc updates after integration

- `COMMAND_API.md`
- `MASTER_PLAN.md`
- any relevant contour note if workflow changes

### Rules

- do not overclaim that stage-20 is now unblocked
- do not describe `READY_FOR_STAGE_ADVANCE` as equivalent to full 20-account
  production proof
- do not describe the external patch as applied if the work was manually ported

## Recommended Pull Request Sequence

### PR 1

- add `rollout posture inspect`
- add tests
- update command docs

### PR 2

- move stage-advance precondition reads under lock
- add lock regression test

### PR 3

- add external-agent output contract
- add manifest schema / handoff notes
- no behavior change

### PR 4

- reserve-semantics ADR only
- no code behavior change

### PR 5

- optional reserve-semantics implementation
- only after ADR approval

## Detailed Verification Plan

### Mandatory checks for PR 1

```sh
python3 -m py_compile wild_boar_proxy/runtime.py wild_boar_proxy/cli.py tests/test_cli.py
python3 -m pytest -q tests/test_cli.py -k 'rollout_posture'
python3 -m unittest -f tests.test_cli
```

### Mandatory checks for PR 2

```sh
python3 -m py_compile wild_boar_proxy/runtime.py tests/test_cli.py
python3 -m pytest -q tests/test_cli.py -k 'rollout_stage_advance'
python3 -m unittest -f tests.test_cli
```

### Mandatory checks for PR 3

```sh
python3 -m unittest -f tests.test_cli
```

### ADR gate for PR 4 and PR 5

- no PR 5 without accepted ADR
- re-run `tests.test_cli` after any reserve-semantics change

## Definition Of Done

This adoption effort is done only when all of the following are true:

1. the external research bundle is classified by applicability and idea risk
2. `rollout posture inspect` exists and is tested
3. stage-advance precondition reads are lock-bound
4. relevant rollout tests are green
5. full `tests.test_cli` is green
6. docs are updated
7. the external-agent output contract is documented
8. reserve semantics are either:
   - explicitly unchanged, or
   - changed only through an accepted ADR and follow-up implementation

## Practical Summary

Take now:

- posture classifier
- serialized precondition fix
- stricter external-agent manifest contract

Take only after review:

- reserve minimum-depth semantics

Do not take as-is:

- the raw patch
- broad claims that the bundle is already merge-ready
