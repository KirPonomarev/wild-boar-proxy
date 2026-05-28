# Acceleration And Throughput Classification R1 Closeout

## Goal

Classify what timing and throughput truth is actually observable in the current
Custom Codex + WBP stack without inflating bounded measurements into acceleration,
quality, productivity, or concurrency claims.

## Result

- status: `ok`
- final verdict: `ACCELERATION_AND_THROUGHPUT_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: classify bounded timing/throughput surfaces, preserve failed-run measurement truth, and keep cross-surface acceleration comparison narrow and honestly limited
- branch: `codex/external-agent-lab-isolated`
- head: `e03ea571c697c85ef7e23630d2f84cb3a4c54062` before contour-local measurement evidence was added
- touched files: `tools/acceleration_and_throughput_classification_r1_probe.py`, `tests/test_acceleration_and_throughput_classification_r1_probe.py`, `audit_results/acceleration_and_throughput_classification_r1_2026-05-28/*.json`, `audit_results/acceleration_and_throughput_classification_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile tools/acceleration_and_throughput_classification_r1_probe.py tests/test_acceleration_and_throughput_classification_r1_probe.py`; `python3 -m pytest -q tests/test_acceleration_and_throughput_classification_r1_probe.py`; `python3 -m pytest -q tests/test_acceleration_and_throughput_classification_r1_probe.py tests/test_codex_custom_sessions.py`; `python3 tools/acceleration_and_throughput_classification_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/acceleration_and_throughput_classification_r1_2026-05-28`; `python3 tools/check_closeout_resilience.py audit_results/acceleration_and_throughput_classification_r1_2026-05-28/closeout.md`; `git diff --check`
- blocked risks: live-stack acceleration remains unproven beyond the contour-local runner harness; `codex_custom_sessions.py` latency truth still comes from runner-reported `duration_seconds` while `operator_surface.py` and `cli_runner.py` expose wall-clock `duration_seconds`, so clean cross-surface acceleration comparison remains inadmissible; user-visible productivity gain remains unproven; concurrent throughput remains unproven and non-claimed
- closure state: CLOSED

## Verification

- tests: `2 passed` in `tests/test_acceleration_and_throughput_classification_r1_probe.py`; `25 passed` in the combined focused run with `tests/test_codex_custom_sessions.py`
- build: `py_compile` passed for the contour-local probe and focused test
- manual: the contour-local probe wrote `8/8` required JSON packets with parseable JSON; `latency_classification_packet.json` records per-lane packet latency and wall-clock observations from the bounded harness while keeping `live_stack_acceleration_proven=false`; `throughput_classification_packet.json` records sequential-only throughput with one retained failed run and no concurrency claim; `lane_measurement_comparison_packet.json` keeps comparison at `limited_or_not_admitted`; `measurement_integrity_packet.json` records that failed runs are retained and that the repo currently mixes runner-reported and wall-clock timing surfaces
- live verification: none in this contour; the contour stayed at bounded contour-local measurement harness scope and explicitly did not claim live-stack acceleration proof

## Artifacts

- spec: thread-only contour plan for `ACCELERATION_AND_THROUGHPUT_CLASSIFICATION_R1`
- packet: `audit_results/acceleration_and_throughput_classification_r1_2026-05-28/measurement_integrity_packet.json`
- report: `audit_results/acceleration_and_throughput_classification_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: final contour commit recorded in git on `codex/external-agent-lab-isolated`
- pushed: yes, after contour closeout push

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical artifacts outside this contour were left untouched
- private-data risk reviewed: yes; the contour uses synthetic prompts and synthetic account identifiers only, and no probe session roots are written into the evidence surface

## Notes

- blockers encountered: the first blocker was timing-surface integrity. `codex_custom_sessions.py` exposes `latency_ms` only by converting runner-reported `duration_seconds`, while `operator_surface.py` and `cli_runner.py` expose wall-clock `duration_seconds`, so the contour had to separate current timing truth from any clean acceleration comparison. The second blocker was claim pressure: it would have been easy to turn bounded harness measurements into a fake speed story, so the contour deliberately kept `comparison_admitted=false`, `live_stack_acceleration_proven=false`, and all productivity/quality/concurrency claims false. The third blocker was failed-run honesty. The contour therefore included a retained failed API-lane run and checked that the transcript preserves the failed event instead of silently dropping it. A cheap read-only scanner agent was launched early for codebase timing-surface reconnaissance, but it did not return a materialized verdict before shutdown and was not counted as evidence. A later stronger read-only audit pass also failed to return a materialized verdict before shutdown, so it likewise was not counted as evidence.
- resume from here: CLOSED
