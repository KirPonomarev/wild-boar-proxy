# WBP Native Window Alternate Observation Pass Closeout

## Goal

Prove input-capable UI surface using an alternate observation mechanism that
bypasses the AX/System Events front-window limitation.

## Result

- status: blocked
- final verdict: NATIVE_CUSTOM_WINDOW_NOT_PROVEN

## Contour Capsule

- goal: attempt alternate observation mechanism (process-name AX scripting + CGWindowList) to prove input-capable UI surface for the Custom native Codex window
- branch: codex/external-agent-lab-isolated
- head: 52c940e0
- touched files: wild_boar_proxy/native_window_probe.py, audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/evidence/*, audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/spec.md, audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/metrics.json, audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/independent_audit.json, audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_native_launch_dispatch tests.test_native_launch_contract tests.test_native_filesystem_probe -q; python3 -m py_compile wild_boar_proxy/native_window_probe.py tools/native_window_proof_probe.py; live alternate observation attempt; independent audit; closeout resilience check
- blocked risks: Mechanism 1 (process-name AX) blocked with -1728; Mechanism 2 (CGWindowList) unavailable without pyobjc-framework-Quartz; input-capable UI surface remains unproven through currently available observation methods
- closure state: CLOSED
- resume from here: CLOSED

## Verification

- tests: targeted native tests passed
- build: py_compile passed
- manual: Codex.app remained closed; no Keychain prompt appeared; cleanup ok
- live verification: both mechanisms attempted and honestly blocked

## Artifacts

- spec: `audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/spec.md`
- packet: `audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/evidence/native_window_proof_summary.json`, `audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/evidence/native_window_ui_surface_packet.json`, `audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/evidence/window_observation_packet.json`
- report: `audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/metrics.json`, `audit_results/wbp_native_window_alternate_observation_pass_2026-05-25/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending
- pushed: no

## Scope Check

- unrelated work mixed in: no; this contour stayed at alternate observation only
- private-data risk reviewed: yes; no secrets exposed

## Notes

- blockers encountered: both observation mechanisms failed independently; the fundamental limitation is that the isolated-home Codex process does not expose an accessible AX window surface to the available OS-level tooling
- resume from here: CLOSED
