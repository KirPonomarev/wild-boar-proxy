# DESKTOP_EXECUTABLE_BRIDGE_ADMISSION_PASS Closeout

## Goal

Admit one real executable desktop bridge path before retrying desktop Quick
Start parity, without widening beyond a minimal packet + refresh proof.

## Result

- status: `closed_success`
- final verdict:
  `DESKTOP_EXECUTABLE_BRIDGE_ADMITTED_WITH_MINIMAL_PROFILE_PACKET_REFRESH_PROOF`
- next action:
  return to `DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS`

## Contour Capsule

- goal:
  prove that the existing Tk desktop shell can execute one bounded
  `codex-desktop` profile packet flow with refresh-confirmed truth and no
  forbidden desktop inputs
- branch: `codex/external-agent-lab-isolated`
- head: `10f66af`
- touched files:
  - `wild_boar_proxy/ui_shell.py`
  - `tests/test_ui_shell.py`
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/spec.md`
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/metrics.json`
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/closeout.md`
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/independent_audit.json`
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/evidence/desktop_bridge_smoke.json`
- tests run:
  - `node --check wild_boar_proxy/web_design_ui/scripts/overview.js`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_ui_shell -q`
  - `/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_ui_shell tests.test_web_ui -q`
  - `PYTHONPATH=/Volumes/Work/wild-boar-proxy /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 /tmp/wbp_desktop_bridge_smoke.py`
  - `git diff --check`
- blocked risks:
  - no medium-or-higher blocker remained after the bounded desktop profile lane
    was added and smoke-proven
  - system `python3` still lacks `_tkinter`; executable proof depends on the
    bundled runtime Python, which is acceptable for this contour and recorded
- next exact command:
  - `python3 tools/check_closeout_resilience.py --staged-only`

## Verification

- tests:
  - new `ui_shell` tests prove route selection, profile packet wiring, profile
    payload rendering, and profile packet + refresh worker order
  - the wider regression suite remained green
- build:
  - `node --check` passed
  - `git diff --check` passed
- manual:
  - real Tk shell instantiated on the bundled runtime
  - desktop bridge smoke selected a route from refreshed truth and rendered a
    `profile_packet_only` state
- live verification:
  - `external-models profile codex-desktop --route wbp-deepseek-v3 --json`
    returned `status=ok`, `profile_kind=codex_desktop_openai_compatible`,
    `writes_external_config=false`
  - desktop layer refreshed `external-models status/models/routes` immediately
    after the packet and kept `runtime_claim_blocked=true`

## Artifacts

- spec:
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/spec.md`
- packet:
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/evidence/desktop_bridge_smoke.json`
- report:
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/metrics.json`
  - `audit_results/desktop_executable_bridge_admission_pass_2026-05-21/independent_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit:
  `closeout drafted before the admission close commit; final closing commit is recorded in git history after resilience passes`
- pushed:
  `closeout drafted before the admission close push; final push is recorded in git history after the closing commit`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed:
  `yes; the new desktop lane surfaces route id, provider, and secret_ref only, and does not accept or reveal raw token/secret/path/auth input`

## Notes

- blockers encountered:
  - earlier desktop-port stop evidence was directionally right about missing
    parity, but the repo already had a real Tk desktop shell; the actual blocker
    was the lack of a bounded desktop-admission lane without forbidden input
  - system `python3` in this environment lacks `_tkinter`; the bundled runtime
    supplied the executable desktop proof
- follow-up contour:
  - `DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS`
- resume from here:
  `return to DESKTOP_PORT_QUICK_START_REAL_ACTIONS_PASS with the admitted Tk desktop shell and bounded profile lane as the new desktop baseline`
