<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R58 Delivery Integrity Guard

## Objective

Prevent a repeat of the observed delivery-contract violation in which a contour
branch was force-pushed. Add a fail-closed ancestry check at both the local
pre-push boundary and the GitHub Actions observation boundary.

## In Scope

- A repository-native Python guard for pre-push input and explicit CI SHA
  comparisons.
- A tracked pre-push hook that invokes the guard.
- A portable, worktree-safe relative `core.hooksPath` installation.
- Repo Hygiene workflow enforcement for branch pushes and pull-request
  synchronize events.
- Focused regression tests for fast-forward, divergent, new-branch, deletion,
  missing-object, malformed-input, hook, installer, and workflow behavior.

## Out of Scope

- Runtime, provider, workflow-engine, web UI, or release changes.
- Rewriting or deleting any existing branch history.
- GitHub repository administration or public-release operations.
- Repairing the separately reopened API, CLI, workflow, assurance, and live
  evidence stages.

## Constraints

- The guard has no environment-variable bypass.
- Existing remote branch updates pass only when the remote commit is a proven
  ancestor of the local commit.
- Branch deletions and unprovable ancestry fail closed with typed codes.
- A new remote branch is allowed only when the local object is a commit.
- Non-branch refs are outside this guard and remain unchanged.
- The user-owned dirty canonical checkout is not modified; implementation uses
  the clean encrypted worktree at exact `origin/main` preimage
  `0a36a9b72f9cf612e163cd7e96758c55610a0802`.

## Assumptions

- Git supplies full 40- or 64-character object IDs to the pre-push hook.
- GitHub push and pull-request synchronize payloads supply exact `before` and
  `after` object IDs; the workflow fetches both before asking the guard to
  prove ancestry.

## Acceptance Criteria

- [x] Fast-forward updates to existing remote branches return `OK`.
- [x] Divergent/non-fast-forward updates return
  `PUSH_NON_FAST_FORWARD_BLOCKED` and exit nonzero.
- [x] Branch deletion returns `PUSH_BRANCH_DELETE_BLOCKED` and exits nonzero.
- [x] Missing commit objects return `PUSH_ANCESTRY_UNPROVEN` and exit nonzero.
- [x] Malformed hook input returns `PUSH_INPUT_INVALID` and exits nonzero.
- [x] New branches pass only when the local object resolves to a commit.
- [x] `.githooks/pre-push` invokes the guard without a bypass surface.
- [x] `tools/install_git_hooks.sh` stores relative `.githooks`.
- [x] Repo Hygiene runs the guard for push and pull-request synchronize events.
- [x] Focused tests and affected repository hygiene checks pass.

## Verification

- tests: `python3 -m pytest tests/test_push_ancestry_guard.py tests/test_repo_hygiene.py -q`
- build: `python3 -m compileall -q tools/check_push_ancestry.py tests/test_push_ancestry_guard.py`
- manual: exercise the tracked pre-push hook against temporary repositories and
  verify exact typed packets and exit codes
- live evidence: pull-request CI and post-merge exact remote-main readback

## Open Questions

- None for this contour.
