<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Stage20 Research Assessment

## Purpose

This document evaluates the external stage-20 research bundle for practical
adoption into the current Wild Boar Proxy repository state.

Reviewed artifacts:

- `/Users/kirillponomarev/Downloads/wbp_execution_core_stage20_fix.patch`
- `/Users/kirillponomarev/Downloads/wbp_agent_integration_notes.md`
- `/Users/kirillponomarev/Downloads/wbp_execution_core_stage20_fix_files.tar.gz`

Repository state used for this assessment:

- branch: `codex/wave-1c-prereq-closeout`
- head: `701774c`

## Verified Facts

### 1. The patch does not apply cleanly to the current repository state

Verified command:

```sh
git apply --check /Users/kirillponomarev/Downloads/wbp_execution_core_stage20_fix.patch
```

Observed result:

```text
error: patch failed: wild_boar_proxy/runtime.py:1567
error: wild_boar_proxy/runtime.py: patch does not apply
```

Conclusion:

- the bundle is not drop-in merge material
- the useful parts must be ported manually into current `HEAD`

### 2. The tarball is not an independent proof artifact

Verified command:

```sh
tar -tzf /Users/kirillponomarev/Downloads/wbp_execution_core_stage20_fix_files.tar.gz
```

Contents:

- `wild_boar_proxy/runtime.py`
- `wild_boar_proxy/cli.py`
- `tests/test_cli.py`
- `COMMAND_API.md`
- `MASTER_PLAN.md`

Conclusion:

- the tarball is a convenient reading bundle
- it does not add extra evidence beyond the patch and notes

### 3. The serialization-window diagnosis is materially useful

Current repository facts in `wild_boar_proxy/runtime.py`:

- `run_rollout_stage_advance()` starts at line `8369`
- stage-advance precondition reads happen before the owner lock:
  - stage/policy/pool/backend preconditions are built in the `8561-8666` area
- the composite owner lock is taken later:
  - `with serialized_lock(paths):` at line `8667`

Conclusion:

- the research correctly identified a real execution-core risk
- moving precondition reads under the serialized owner lock is a valid adoption
  candidate

### 4. The posture-classifier idea is materially useful

Current repository facts:

- `ROTATION_EVIDENCE_INSUFFICIENT` already exists in the codebase and tests
- there is no `rollout posture inspect <15|20> --json` surface in the current
  repo
- live classification between:
  - `INSUFFICIENT_ELIGIBLE_POOL`
  - `ROTATION_EVIDENCE_INSUFFICIENT`
  - `LIVE_POSTURE_DRIFT_ONLY`
  - `READY_FOR_STAGE_ADVANCE`
  is currently spread across multiple owner surfaces

Conclusion:

- a dedicated read-only posture-classification command is a strong candidate for
  integration

### 5. The reserve-semantics rewrite is not a safe bugfix

Current repository facts:

- stage-proof currently blocks when:
  `reserve_pool_count_observed != reserve_target`
  at lines `7979-7980`
- stage-advance postflight currently requires:
  `reserve_pool_count_after == reserve_target`
  at line `8267`
- source-stage override logic currently assumes:
  `reserve_pool_count_observed == source_reserve_target + 1`
  at line `8362`
- current tests explicitly encode exact-count posture:
  - `tests/test_cli.py:9596`
  - `tests/test_cli.py:11751`

Conclusion:

- changing reserve semantics from exact-count to minimum-depth changes canon
- this requires contract review and ADR acceptance
- it should not be merged as a casual patch side effect

## Adoption Matrix

### Adopt Now

1. `rollout posture inspect <15|20> --json`
2. stage-advance precondition reads under `serialized_lock`
3. stricter external-agent output contract:
   - apply status
   - target branch / target commit
   - split between safe adoption and ADR-required changes

### Adopt Only After ADR

1. reserve semantics:
   - `reserve_count >= reserve_target`
2. any stage-proof or postflight behavior that turns reserve posture from an
   exact-count gate into a minimum-depth gate

### Reject As-Is

1. blind patch application
2. claims that targeted rollout tests equal full merge readiness
3. live recommendations that are not re-confirmed against current owner
   surfaces

## Corrective Guidance For Integrators

1. Treat the bundle as source material, not as a merge-ready fix.
2. Port ideas one by one into current `HEAD`.
3. Keep the repo repair split into separate pull requests:
   - posture inspect
   - stage-advance serialization fix
   - agent-output contract / manifest
   - reserve-semantics ADR
4. Do not let reserve-semantics changes piggyback on the lock fix.

## Final Verdict

Usefulness score:

- as diagnosis: high
- as direct patch: low
- as source of next repo contours: high

Practical verdict:

- keep the diagnosis
- port the safe execution-core ideas
- isolate the semantic changes behind ADR review
