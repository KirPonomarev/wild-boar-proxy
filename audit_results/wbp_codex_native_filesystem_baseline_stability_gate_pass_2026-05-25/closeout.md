# WBP_CODEX_NATIVE_FILESYSTEM_BASELINE_STABILITY_GATE_PASS_R2 Closeout

## Goal

Classify whether the currently active Codex environment is stable enough to support truthful recursive protected-surface comparison for later native filesystem proof.

## Result

- status: pass
- final verdict: `NATIVE_FILESYSTEM_BASELINE_ADMISSIBILITY_CLASSIFIED`
- closure state: CLOSED

## Contour Capsule

- goal: run repeated idle baseline windows with no custom launch and classify active-baseline admissibility
- branch: `codex/external-agent-lab-isolated`
- head: `90c87bcca1258c527cd79c4ee5eb5b067b1c0daa`
- touched files: `wild_boar_proxy/native_filesystem_probe.py`, `tools/native_baseline_stability_probe.py`, `tests/test_native_filesystem_probe.py`, `audit_results/wbp_codex_native_filesystem_baseline_stability_gate_pass_2026-05-25/evidence/*`, `audit_results/wbp_codex_native_filesystem_baseline_stability_gate_pass_2026-05-25/closeout.md`
- tests run: `python3 -m unittest tests.test_native_filesystem_probe tests.test_repo_hygiene tests.test_closeout_resilience`
- blocked risks: none for this contour; downstream implication is `quiescent_current_codex_precondition_required=true` for the next live filesystem retry
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest tests.test_native_filesystem_probe tests.test_repo_hygiene tests.test_closeout_resilience`
- build: `git diff --check`
- manual: `python3 /Volumes/Work/wild-boar-proxy/tools/native_baseline_stability_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/wbp_codex_native_filesystem_baseline_stability_gate_pass_2026-05-25/evidence --sleep-seconds 3`
- live verification: two idle windows completed with `custom_launch_observed=false`; current Codex root pid stayed `[41266]` before and after both windows; both windows showed recursive protected-surface drift under `~/.codex` and `~/Library/Application Support/Codex`, so the active baseline was classified unstable with repeated drift

## Artifacts

- spec: thread-only contour `WBP_CODEX_NATIVE_FILESYSTEM_BASELINE_STABILITY_GATE_PASS_R2`
- packet: `/Volumes/Work/wild-boar-proxy/audit_results/wbp_codex_native_filesystem_baseline_stability_gate_pass_2026-05-25/evidence/current_codex_baseline_stability_summary.json`
- report: `/Volumes/Work/wild-boar-proxy/audit_results/wbp_codex_native_filesystem_baseline_stability_gate_pass_2026-05-25/evidence/independent_baseline_stability_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: not committed yet at closeout draft time
- pushed: no

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; evidence stores relative paths and packet metadata only, with no secret values recorded

## Notes

- blockers encountered: none inside this contour; the contour resolved the previous Phase 7 blocker by proving `ACTIVE_CURRENT_CODEX_BASELINE_UNSTABLE` with `drift_repeatability=repeated`
- resume from here: CLOSED
