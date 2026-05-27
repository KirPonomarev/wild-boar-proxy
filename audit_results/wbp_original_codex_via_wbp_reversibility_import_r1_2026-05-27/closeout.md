<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Original Codex Via WBP Reversibility Import R1 Closeout

## Goal

Reclassify one bounded Original Codex via WBP reversible intervention from existing packet-backed
live evidence under current claim boundaries, without performing a new Original-profile write and
without promoting the result into general Original usability, broad filesystem innocence, or final E2E.

## Result

- status: ok
- final verdict: ORIGINAL_CODEX_VIA_WBP_PROVEN_REVERSIBLE
- closure state: CLOSED

## Contour Capsule

- goal: import and reclassify packet-backed Original-via-WBP reversibility on declared observed surfaces only
- branch: codex/external-agent-lab-isolated
- head: d9b4221a1912f8f64d77307d35d1e10491d2b21b
- touched files: tools/original_codex_via_wbp_reversibility_import_r1_probe.py; tests/test_original_codex_via_wbp_reversibility_import_r1_probe.py; audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/*
- tests run: python3 -m py_compile tools/original_codex_via_wbp_reversibility_import_r1_probe.py tests/test_original_codex_via_wbp_reversibility_import_r1_probe.py; python3 -m pytest -q tests/test_original_codex_via_wbp_reversibility_import_r1_probe.py tests/test_original_live_reversibility_probe.py; python3 tools/original_codex_via_wbp_reversibility_import_r1_probe.py --evidence-dir audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27 --source-evidence-dir audit_results/original_codex_via_wbp_owner_authorized_live_apply_r5_2026-05-26; top-level JSON status sweep; secret scan; git diff --check; python3 tools/check_closeout_resilience.py audit_results/wbp_original_codex_via_wbp_reversibility_import_r1_2026-05-27/closeout.md
- blocked risks: no new owner action was collected; general Original usability, broad filesystem innocence, direct egress absence, and final E2E intentionally not claimed
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest -q tests/test_original_codex_via_wbp_reversibility_import_r1_probe.py tests/test_original_live_reversibility_probe.py` -> `7 passed`
- build: `python3 -m py_compile tools/original_codex_via_wbp_reversibility_import_r1_probe.py tests/test_original_codex_via_wbp_reversibility_import_r1_probe.py` -> passed
- manual: top-level JSON status sweep reported `15` `ok` packets and `0` blocked packets; secret scan reported `0` matches; explorer audit confirmed no widening from route observation into general Original usability or broad filesystem innocence
- live verification: no new live mutation executed in this contour; bounded reversibility was imported from `original_codex_via_wbp_owner_authorized_live_apply_r5_2026-05-26`, whose source summary remains `ORIGINAL_CODEX_VIA_WBP_TEMP_ROUTE_AND_RESTORE_PROVEN_WITH_LIMITS`

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: original_wbp_reversibility_summary_packet.json
- report: independent_original_wbp_reversibility_audit.json; verification_results_packet.json; scanner_agent_fact_report_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: d9b4221a1912f8f64d77307d35d1e10491d2b21b
- pushed: pending contour push

## Scope Check

- unrelated work mixed in: no; unrelated historical dirt remained quarantined and unstaged from this contour commit
- private-data risk reviewed: yes; imported reversibility packets remained hash-only/no-raw-secret for auth and prompt-adjacent surfaces

## Notes

- blockers encountered: the strongest existing source packet chain already provided bounded reversible route-and-restore truth, so the main risk was overclaim drift between source `...PROVEN_WITH_LIMITS` wording and the current narrower reversibility-only pass
- resume from here: CLOSED
