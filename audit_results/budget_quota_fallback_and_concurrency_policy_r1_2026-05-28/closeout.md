# Budget Quota Fallback And Concurrency Policy R1 Closeout

## Goal

Classify and tighten the current Custom Codex policy truth for budget,
quota, fallback, and concurrency without inventing automatic resilience,
provider-family fallback safety, or acceleration claims that the runtime does
not actually prove.

## Result

- status: `ok`
- final verdict: `BUDGET_QUOTA_FALLBACK_AND_CONCURRENCY_POLICY_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: classify current policy boundaries and add the narrowest real runtime guard where the code already admitted silent concurrent prompt fanout risk
- branch: `codex/external-agent-lab-isolated`
- head: `4e8dd37316dfc960423e0292afd043ec049be3ad`
- touched files: `wild_boar_proxy/codex_custom_sessions.py`, `tools/budget_quota_fallback_and_concurrency_policy_r1_probe.py`, `tests/test_budget_quota_fallback_and_concurrency_policy_r1_probe.py`, `audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/*.json`, `audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile wild_boar_proxy/codex_custom_sessions.py tools/budget_quota_fallback_and_concurrency_policy_r1_probe.py tests/test_budget_quota_fallback_and_concurrency_policy_r1_probe.py`; `python3 -m pytest -q tests/test_budget_quota_fallback_and_concurrency_policy_r1_probe.py`; `python3 -m pytest -q tests/test_codex_custom_sessions.py tests/test_budget_quota_fallback_and_concurrency_policy_r1_probe.py`; `python3 tools/budget_quota_fallback_and_concurrency_policy_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28`; `python3 tools/check_closeout_resilience.py audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/closeout.md`; `git diff --check`
- blocked risks: hard budget enforcement remains unproven in the Custom prompt runtime; `operator_surface.run_prompt()` still executes before a full pre-spend gate is proven; launch surfaces still allow default-model substitution outside this contour’s narrow fix; quota handling remains static classification rather than a live retry policy; concurrency is now guarded per session in `CodexCustomSessionManager`, but broader per-slot or cross-surface parallel paid dispatch policy remains open
- closure state: CLOSED

## Verification

- tests: `3 passed` in `tests/test_budget_quota_fallback_and_concurrency_policy_r1_probe.py`; `26 passed` in the combined focused run with `tests/test_codex_custom_sessions.py`
- build: `py_compile` passed for `wild_boar_proxy/codex_custom_sessions.py`, the contour-local probe, and the contour-local test
- manual: the contour-local probe wrote `9/9` required JSON packets with parseable JSON; `budget_boundary_packet.json` records that external paid-route policy exists only as declared contract truth with `paid_route_default=blocked` while `hard_overspend_prevention_proven=false`; `quota_handling_packet.json` records one launch-capable backend plus separate static `quota_exhausted`, `auth_invalid`, and `cooldown_only` classes without claiming a live retry policy; `fallback_boundary_packet.json` records that invalid slot requests are rejected without primary fallback, blocked provider rows remain blocked, and automatic fallback policy is absent; `concurrency_boundary_packet.json` records an observed blocked concurrent prompt with `CONCURRENT_PROMPT_EXECUTION_NOT_ALLOWED`, one-model-per-run payload shape, and no throughput claim
- live verification: none in this contour; the runtime guard was proven through bounded in-process session-manager execution and contour-local packet capture only

## Artifacts

- spec: thread-only contour plan for `BUDGET_QUOTA_FALLBACK_AND_CONCURRENCY_POLICY_R1`
- packet: `audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/concurrency_boundary_packet.json`
- report: `audit_results/budget_quota_fallback_and_concurrency_policy_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `not_committed_yet`
- pushed: `not_pushed_yet`

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; the new packets use synthetic account identifiers and synthetic prompts only, and the contour keeps probe session roots out of the evidence surface

## Notes

- blockers encountered: the first blocker was honesty about what counts as policy enforcement. The repo already had route-policy defaults and account eligibility classification, but most of that truth was still dry-run or contract truth rather than enforced pre-spend blocking in the Custom prompt path. The second blocker was concurrency: a read-only subagent audit found that `CodexCustomSessionManager` had no per-session prompt lock under the threaded server model, so the contour added a narrow runtime guard and a thread-based regression test instead of merely writing a warning packet. The third blocker was scope integrity. The same audit found additional open risks in `operator_surface.run_prompt()` and the web launch surfaces where execution or default substitution can still happen before a full policy gate is proven. Those risks were kept as explicit open findings in the contour packets and closeout rather than being silently mixed into this narrower fix. A separate high-pass read-only audit agent did not return a materialized verdict before shutdown, so it was not counted as evidence.
- resume from here: CLOSED
