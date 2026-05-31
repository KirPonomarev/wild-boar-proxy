# WORKTREE_TAIL_RESOLUTION_DECISION_GATE Closeout

Date: 2026-05-13

Branch: `codex/external-agent-lab-isolated`

Input commit: `c3346f2 Adjudicate dirty worktree tail before UI freeze`

## Scope

This contour was decision-only by default. It created a resolution decision matrix and did not clean, delete, park, revert, or implement any tail changes.

## Current Tail

- Tracked dirty files: 6.
- Tracked diff stat: 6 files changed, 85 insertions, 17 deletions.
- Untracked baseline excluding this contour's artifacts: 168.
- Current untracked files including this contour's two artifacts before staging: 170.
- Untracked groups: 157 external-lab audit artifacts, 1 other audit artifact, 10 external-agent-lab eval result files.
- Material change since adjudication: none detected.

## Decisions

- `wild_boar_proxy/runtime.py` remains isolated as runtime behavior change and requires owner decision plus a separate runtime contour or explicit revert approval.
- `external_agent_lab` source/test changes are a candidate for a separate external-lab commit only after owner approval and targeted tests.
- Generated audit/eval artifacts remain pending owner decision and must not be auto-committed as ordinary source.

## Verification

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- targeted runtime diff review
- targeted external-agent-lab diff review
- direct secret-value scan over dirty/untracked candidates
- neutral external reference trace scan
- targeted `tests.test_external_agent_lab`
- JSON validation for the decision matrix

## Results

- Direct secret-value scan: no matches.
- External reference trace scan: no matches, reported neutrally.
- Targeted external-agent-lab tests: pass.
- Source/runtime/generated evidence files were not staged by this contour.
- Read-only verifier confirmed the current tail matches the prior adjudication.

## Final State

`WORKTREE_TAIL_RESOLUTION_DECISION_READY_OWNER_APPROVAL_REQUIRED`

The next action is an owner decision on exactly one bucket at a time:

- runtime contour or explicit runtime revert approval;
- separate external-lab commit approval;
- generated evidence park/review/delete/keep-pending decision.
