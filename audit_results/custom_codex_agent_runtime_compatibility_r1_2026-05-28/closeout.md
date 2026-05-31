<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Custom Codex Agent Runtime Compatibility Classification R1 Closeout

## Goal

Classify whether the persistent Custom Codex profile has the bounded runtime and plugin surfaces needed for agent-capable workflows while preserving isolated-profile truth and avoiding performance, model-grid, UI, or repair claims.

## Result

- status: ok
- final verdict: CUSTOM_CODEX_AGENT_RUNTIME_COMPATIBILITY_CLASSIFIED_WITH_ISOLATED_PROFILE
- closure state: CLOSED

## Contour Capsule

- goal: classify Custom Codex agent/runtime compatibility with isolated-profile evidence and explicit claim limits
- branch: codex/external-agent-lab-isolated
- head: 2ade4b21434ded15a682f427d238dabf6d4a8113
- touched files: tools/custom_codex_agent_runtime_compatibility_r1_probe.py; tests/test_custom_codex_agent_runtime_compatibility_r1_probe.py; audit_results/custom_codex_agent_runtime_compatibility_r1_2026-05-28
- tests run: python3 -m unittest tests.test_custom_codex_agent_runtime_compatibility_r1_probe; python3 -m py_compile tools/custom_codex_agent_runtime_compatibility_r1_probe.py tests/test_custom_codex_agent_runtime_compatibility_r1_probe.py; python3 tools/custom_codex_agent_runtime_compatibility_r1_probe.py --agent-workflow-observed --agent-workflow-source scanner_agent_spawned_in_current_contour
- blocked risks: false-green sync gate hole found by independent audit and fixed with disclosure fields plus regression tests; performance, parity, model-grid, all-plugin, all-user, auth, and UI claims remain forbidden
- closure state: CLOSED

## Verification

- tests: 13 unit tests passed for the contour probe
- build: py_compile passed for the probe and its test module
- manual: scanner packet and external auditor adjudication packet were reviewed against generated JSON evidence
- live verification: no live runtime repair, cleanup, restore, UI work, model routing, or plugin invocation was performed by this probe

## Artifacts

- spec: thread-only contour plan outside the repository
- packet: audit_results/custom_codex_agent_runtime_compatibility_r1_2026-05-28/agent_runtime_compatibility_summary_packet.json
- report: audit_results/custom_codex_agent_runtime_compatibility_r1_2026-05-28/external_auditor_adjudication_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour evidence commit
- pushed: branch push required by closeout rule

## Scope Check

- unrelated work mixed in: no; pre-existing dirty worktree entries were disclosed as quarantined historical dirt in sync_gate_packet.json and were not staged for this contour
- private-data risk reviewed: yes; protected Original Codex surfaces were recorded as bounded metadata only, with no content capture and no writes

## Notes

- blockers encountered: independent auditor found a false-green weakness in sync-gate accounting; the contour was corrected before closure
- resume from here: CLOSED
