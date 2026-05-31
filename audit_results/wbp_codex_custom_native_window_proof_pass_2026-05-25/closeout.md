# WBP Codex Custom Native Window Proof Closeout

## Goal

Prove that one bounded repo-canonical Custom native launch produces a real
native window bound to the Custom launch with an input-capable UI surface.

## Result

- status: blocked
- final verdict: NATIVE_CUSTOM_WINDOW_NOT_PROVEN

## Contour Capsule

- goal: prove one bounded repo-canonical isolated-home Custom native launch produces a real distinguishable native window with an input-capable UI surface
- branch: codex/external-agent-lab-isolated
- head: 487894f7
- touched files: wild_boar_proxy/native_window_probe.py, audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/evidence/*, audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/spec.md, audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/metrics.json, audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/independent_audit.json, audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_native_launch_dispatch tests.test_native_launch_contract tests.test_native_filesystem_probe -q; python3 -m py_compile wild_boar_proxy/native_window_probe.py tools/native_window_proof_probe.py; live native window proof attempt via tools/native_window_proof_probe.py; independent packet audit; closeout resilience check
- blocked risks: window observed and identity binding proven, but input-capable UI surface not proven because AX/System Events reports zero accessible windows for the Custom Codex process; AX query for text input elements returned System Events error -1719
- closure state: CLOSED
- resume from here: CLOSED

## Verification

- tests: targeted native dispatch/contract/filesystem tests passed
- build: py_compile passed
- manual: owner authorization phrase present; Codex.app remained closed/quiescent; no Keychain reset prompt appeared
- live verification: window observed (Codex, visible=true, 0 windows count), identity binding to Custom launch proven, input-capable UI blocked by AX window accessibility

## Artifacts

- spec: `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/spec.md`
- packet: `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/evidence/window_observation_packet.json`, `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/evidence/window_identity_binding_packet.json`, `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/evidence/native_window_ui_surface_packet.json`, `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/evidence/native_window_proof_summary.json`
- report: `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/metrics.json`, `audit_results/wbp_codex_custom_native_window_proof_pass_2026-05-25/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: 802d06a0
- pushed: yes (origin/codex/external-agent-lab-isolated)

## Scope Check

- unrelated work mixed in: no; this contour stayed at window proof only
- private-data risk reviewed: yes; no provider secrets or local proxy keys were exposed in contour artifacts

## Notes

- blockers encountered: AX/System Events reports the Custom Codex process as having zero windows, preventing input-capable UI surface proof; the same blocker class was observed in historical window proof contours
- resume from here: CLOSED
