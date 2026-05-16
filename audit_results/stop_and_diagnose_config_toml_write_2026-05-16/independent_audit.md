# Independent Audit

## Scope

- contour: `STOP_AND_DIAGNOSE`
- run label: `config_toml_write`
- branch: `codex/external-agent-lab-isolated`
- head: `bbd2d53`

## Local Checks

- `git status --short --untracked-files=no` -> clean
- `python3 -m unittest -q tests.test_cli.CliTests.test_launch_smoke_activates_approved_target_via_generated_config_and_status_reports_effective_target tests.test_cli.CliTests.test_launch_smoke_records_conservative_observed_source_fallback_when_launcher_exits_nonzero_during_approved_target_attempt tests.test_cli.CliTests.test_launch_smoke_wraps_external_launcher_and_reports_fallback` -> `OK`
- code inspection of `wild_boar_proxy/runtime.py`

## Independent Agent Verdicts

- write-origin audit: `PASS`
  - exact CLI trace localized from entrypoint to launcher `smoke` branch
  - primary write occurs in repo-owned default launcher payload
  - secondary fallback write exists in `reconcile_stable_fallback()`
- changed-files audit: `PASS`
  - `runtime_write_surface_candidates()` includes `config_toml`
  - `detect_changed_files()` uses `st_mtime_ns` and `st_mode`, not content diff
  - `write_toml_string_atomic()` rewrites through `write_text_atomic()` without
    unchanged-content short-circuit

## Audit Verdict

- diagnosis localized: `yes`
- contract verdict: `contour contract wrong`
- runtime behavior wrong: `not supported by current evidence`
- live continuation admissible now: `no`
- selector continuation admissible now: `no`

## Follow-Up Recommendation

- open a narrow contract-alignment contour
- update admitted write surfaces and governing runtime contour truth for
  `launch smoke --json`
- only then re-enter runtime/selector live progression
