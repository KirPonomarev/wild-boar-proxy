# DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS Closeout

## Goal

Port the proven web Quick Start continuity flow onto the admitted Tk desktop
shell while keeping sandbox-only packet + refresh semantics intact.

## Result

- status: `closed_success`
- final verdict:
  `DESKTOP_QUICK_START_CONTINUITY_PARITY_PROVEN_ON_ADMITTED_TK_SHELL`
- next action:
  `EXECUTION_CORE_REPAIR_CLOSED_AND_DESIGN_GATE_READY` is still not earned, so stop this line here and only open a narrow follow-up contour if a new blocker appears

## Contour Capsule

- goal:
  prove desktop continuity parity for account truth, API truth, bounded
  `Check All`, and action ledger on the admitted Tk shell without widening
  inputs or truth sources
- branch: `codex/external-agent-lab-isolated`
- head: `d94d6c50802d61ea0753fe79eaa9870fc1e49cee`
- touched files:
  - `wild_boar_proxy/ui_shell.py`
  - `tests/test_ui_shell.py`
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/spec.md`
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/metrics.json`
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/closeout.md`
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/independent_audit.json`
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/evidence/desktop_continuity_smoke.json`
- tests run:
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `git diff --check`
- blocked risks:
  - no medium-or-higher blocker remained after the desktop continuity parity
    path was proved on the admitted Tk shell
- next exact command:
  - `python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests:
  - desktop Quick Start helper tests cover API check refresh order, check-all
    bundle verdict construction, and quick-start summary/bundle state mapping
  - the broader regression suite remained green
- build:
  - `node --check` passed
  - `git diff --check` passed
- manual:
  - real bundled-runtime Tk shell instantiated on a sandbox harness
  - desktop layer applied refresh -> API check -> check-all and rendered ledger
    entries from real command packets
- live verification:
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/evidence/desktop_continuity_smoke.json`
    records `status --json=OK`, `external-models start --json=OK`,
    `api_route_check=OK`, `quick_start_check_all=ready`, and ledger parity on
    the admitted Tk shell

## Artifacts

- spec:
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/evidence/desktop_continuity_smoke.json`
- report:
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/metrics.json`
  - `audit_results/desktop_port_quick_start_real_actions_pass_2026-05-21/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit:
  `closeout drafted before the desktop parity close commit; final commit is recorded after resilience passes`
- pushed:
  `closeout drafted before the desktop parity push; final push is recorded after the closing commit`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; desktop Quick Start surfaces only route id/provider/secret_ref and bounded packet truth, with no raw token/secret/path/auth input`

## Notes

- blockers encountered:
  - initial smoke without `external-models start --json` left desktop API truth
    in the same `missing_secret` lane used by the web flow when local token
    readiness is absent; the parity proof therefore had to use a sandbox root
    with the synthetic adapter started
  - real Tk automation via the standard event loop was awkward inside this
    harness, so the factual smoke uses the admitted Tk shell plus immediate
    `after()` callbacks while still running real command packets
- follow-up contour:
  - none required for this track; only open a narrow repair contour if later
    desktop parity evidence regresses
- resume from here:
  `CLOSED`

> Fill all `Contour Capsule` fields with concrete values before commit.
> Placeholder values are not accepted by resilience checks.
