# WORKTREE_TAIL_ADJUDICATION Closeout

Date: 2026-05-13

Branch: `codex/external-agent-lab-isolated`

HEAD: `0acaef1 Harden web action ledger error states`

## Scope

This contour performed read-only dirty-tail adjudication plus repo-safe decision artifacts. It did not implement UI features, visual polish, runtime repair, external-agent-lab changes, cleanup, deletion, staging of dirty tail, or desktop work.

## Findings

- Tracked dirty files: 6.
- Tracked diff size: 85 insertions, 17 deletions.
- Baseline untracked files before this contour's artifacts: 168.
- Current untracked files including this contour's three artifacts: 171.
- Untracked groups: 157 external-lab audit artifacts, 1 other admission artifact, 10 generated eval result files.
- Direct secret-value scan: 0 matches.
- Absolute/private path marker scan: 21 files matched.
- Provider env placeholder marker scan: 17 files matched.
- External reference trace scan: passed with no matches, reported neutrally.

## Decisions

- `wild_boar_proxy/runtime.py` is runtime-behavioral and requires a separate runtime contour. It was not staged, reverted, edited, or committed.
- `external_agent_lab/**` and `tests/test_external_agent_lab.py` are external-agent-lab work and must not be mixed into UI commits.
- Generated audit/eval artifacts are evidence logs, not ordinary source. They require owner decision or a separate evidence review before commit.
- UI render package/passport work remains blocked until the dirty tail is resolved or explicitly parked.

## Verification Commands

- `git status --short`
- `git diff --stat`
- `git diff --name-only`
- targeted `git diff` for runtime and external-agent-lab tracked files
- untracked inventory via `git ls-files -o --exclude-standard`
- direct secret-value scan over dirty and untracked candidates
- absolute/private path marker scan over untracked candidates
- provider env placeholder marker scan over untracked candidates
- neutral external reference trace scan

## Independent Inspection

Read-only inspector `Sartre` independently classified the dirty tail. Its report agreed that:

- external-agent-lab code/test changes are a separate commit candidate;
- `wild_boar_proxy/runtime.py` is runtime-behavioral;
- generated audit/eval artifacts should be treated as evidence logs, not ordinary source.

## Files Intentionally Not Staged

- `external_agent_lab/legacy/agent_eval.py`
- `external_agent_lab/legacy/proxy_server.py`
- `external_agent_lab/legacy/run_lab.py`
- `external_agent_lab/model_registry_seed.json`
- `tests/test_external_agent_lab.py`
- `wild_boar_proxy/runtime.py`
- `audit_results/external_lab_*`
- `audit_results/c02_mini_eval_admission_2026-05-09.json`
- `external_agent_lab/legacy/eval_results/`

## Closeout Status

Classification is complete. Cleanup is not complete by design. The next required decision is whether to park generated evidence, open a runtime contour, and/or commit the external-agent-lab bundle separately after targeted tests.
