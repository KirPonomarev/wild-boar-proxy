# LEGACY_CODEX_RUNTIME_SURFACES_RETIREMENT_PASS Closeout

## Result

- status: `closed_success`
- final verdict: repo-owned legacy Codex operator wrappers are retired, risky/external assets are classified and untouched, and the canonical owner session bridge remains green
- next action: continue product work on top of the canonical web/account connect path

## Contour Capsule

- goal: classify legacy Codex runtime/operator surfaces and retire only proven-superseded repo-owned entrypoints
- branch: `codex/external-agent-lab-isolated`
- head: `b13fd43`
- touched files:
  - `wild_boar_proxy/runtime.py`
  - `tests/test_cli.py`
  - `COMMAND_API.md`
  - `UI_READINESS_SPEC.md`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/spec.md`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/legacy_inventory.json`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/replacement_matrix.json`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/not-retired-hold-list.json`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/metrics.json`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/independent_audit.json`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/closeout.md`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/evidence/git-baseline.txt`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/evidence/search-results.txt`
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/evidence/test-results.txt`
- audit package:
  - `audit_results/legacy_codex_runtime_surfaces_retirement_pass_2026-05-22/`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` -> pass
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q` -> `Ran 554 tests in 193.400s OK`
  - `git diff --check` -> pass
  - `python3 tools/check_closeout_resilience.py --staged-only` -> pass
- blocked risks: none; external/local runtime assets were classified but not modified
- next exact command: `git status -sb`

## Verification

- targeted operator wrapper tests: pass
- full required gate: pass, `Ran 554 tests in 193.400s OK`
- `git diff --check`: pass
- closeout resilience: pass

## Scope Check

- `CLIProxyAPI` engine removed: no
- external/local runtime dirs deleted: no
- historical audit artifacts rewritten: no
- web redesign mixed in: no
- promotion to active mixed in: no

## Resume From Here

- resume from here: CLOSED. Resume from the next contour after commit and push.
