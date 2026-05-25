# WBP_CODEX_NATIVE_FILESYSTEM_ISOLATION_PROOF_PASS_R2 Closeout

## Goal

Prove filesystem isolation boundaries for the repo-canonical custom native lane `repo_canonical_custom_proxy_auth_isolated_home` without making any native window or routing claim.

## Result

- status: blocked
- final verdict: `NATIVE_CUSTOM_FILESYSTEM_ISOLATION_NOT_PROVEN`
- closure state: CLOSED

## Contour Capsule

- goal: run a bounded live native launch and prove recursive protected surfaces remain isolated to server-owned temp roots
- branch: `codex/external-agent-lab-isolated`
- head: `aade8675187d5e95ba0220356e013c64d03c7ad1`
- touched files: `wild_boar_proxy/native_filesystem_probe.py`, `tools/native_filesystem_isolation_probe.py`, `tests/test_native_filesystem_probe.py`, `audit_results/wbp_codex_native_filesystem_isolation_proof_pass_2026-05-25/evidence/*`, `audit_results/wbp_codex_native_filesystem_isolation_proof_pass_2026-05-25/closeout.md`
- tests run: `python3 -m unittest tests.test_native_filesystem_probe tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_repo_hygiene tests.test_closeout_resilience`
- blocked risks: recursive `~/.codex` stability could not be proven while current Codex remained active; live run and idle baseline both showed protected-surface drift, so default-surface change attribution remained ambiguous
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_native_filesystem_probe tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_repo_hygiene tests.test_closeout_resilience`
- build: `git diff --check`
- manual: bounded live native probe via `python3 tools/native_filesystem_isolation_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/wbp_codex_native_filesystem_isolation_proof_pass_2026-05-25/evidence --endpoint http://127.0.0.1:8318/v1 --model gpt-5.5`
- live verification: custom process observed at isolated `--user-data-dir`, current Codex root pid preserved, `~/Library/Application Support/Codex`, cache, and HTTPStorages unchanged in the live run; recursive `~/.codex` unchanged proof failed, and idle baseline drift packet confirmed ambient protected-surface churn under the active current Codex session, so attribution stayed ambiguous

## Artifacts

- spec: thread-only contour `WBP_CODEX_NATIVE_FILESYSTEM_ISOLATION_PROOF_PASS_R2`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/wbp_codex_native_filesystem_isolation_proof_pass_2026-05-25/evidence/native_filesystem_isolation_summary.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/wbp_codex_native_filesystem_isolation_proof_pass_2026-05-25/evidence/independent_native_filesystem_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: not committed yet at closeout draft time
- pushed: no

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; evidence records paths, counts, and selected changed relative paths, and `secret_value_recorded=false` in the live packet

## Notes

- blockers encountered: live probe initially blocked on `DEFAULT_PROTECTED_SURFACES_CHANGED`; independent audit downgraded the final contour blocker to `WRITE_ATTRIBUTION_AMBIGUOUS_WITH_ACTIVE_CURRENT_CODEX_BASELINE_DRIFT` because idle baseline drift packet showed protected-surface churn even without a custom launch
- resume from here: CLOSED
