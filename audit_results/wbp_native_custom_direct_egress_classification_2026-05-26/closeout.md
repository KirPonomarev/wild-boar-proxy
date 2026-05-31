# Native Custom Direct Egress Classification Closeout

## Goal

Classify bounded direct non-WBP model egress for an isolated native Codex Custom launch without using WBP route success, owner UX, filesystem safety, provider compatibility, or final E2E as substitute proof.

## Result

- status: blocked
- final verdict: `NATIVE_WBP_ROUTE_NETWORK_CLAIM_BLOCKED_BACKGROUND_CODEX_NOISE`
- closure state: CLOSED

## Contour Capsule

- goal: classify native Custom direct egress with process-tree `lsof` sampling and WBP trace reconciliation, while preserving strict layer separation
- branch: `codex/external-agent-lab-isolated`
- head: `b7d6905266cd345e87ae35665d3fb079eab39b8e`
- touched files: `wild_boar_proxy/native_filesystem_probe.py`, `tests/test_native_filesystem_probe.py`, `tools/native_custom_direct_egress_classification_probe.py`, `audit_results/wbp_native_custom_direct_egress_classification_2026-05-26/*`
- tests run: `python3 -m unittest -q tests.test_native_filesystem_probe`; `python3 -m py_compile tools/native_custom_direct_egress_classification_probe.py wild_boar_proxy/native_filesystem_probe.py`; `python3 -m unittest -q tests.test_native_filesystem_probe tests.test_cli_runner tests.test_operator_surface`; `git diff --check`; JSON parse validation for 16 evidence packets; secret-pattern scan; `python3 tools/check_closeout_resilience.py audit_results/wbp_native_custom_direct_egress_classification_2026-05-26/closeout.md`
- blocked risks: direct non-WBP model egress absence is not proven because the live observer saw background Codex noise, default Codex process-count drift, unexpected `node_repl` peer traffic, and non-local Codex peers inside the bounded observation
- closure state: CLOSED

## Verification

- tests: `tests.test_native_filesystem_probe` passed with 99 tests; combined `tests.test_native_filesystem_probe tests.test_cli_runner tests.test_operator_surface` passed with 120 tests; closeout resilience passed
- build: `python3 -m py_compile tools/native_custom_direct_egress_classification_probe.py wild_boar_proxy/native_filesystem_probe.py` passed; `git diff --check` passed
- manual: no owner UX claim recorded; the live probe printed a bounded prompt instruction only as traffic stimulus
- live verification: isolated native Custom launch reached WBP through trace observer with `/v1/responses`, `forwarded_to_wbp=true`, and upstream 200, but process-network observation was contaminated by background Codex noise and therefore blocked the direct-egress absence claim

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: `audit_results/wbp_native_custom_direct_egress_classification_2026-05-26/native_direct_egress_summary_packet.json`
- report: `audit_results/wbp_native_custom_direct_egress_classification_2026-05-26/independent_native_direct_egress_audit.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: contour commit created from head `b7d6905266cd345e87ae35665d3fb079eab39b8e`
- pushed: contour branch push performed after verification

## Scope Check

- unrelated work mixed in: no; pre-existing dirty historical evidence remained quarantined and unstaged
- private-data risk reviewed: yes; packets record hashes, redacted process/network metadata, no raw prompt body, no auth header, and no raw upstream secret

## Notes

- blockers encountered: native route trace was confirmed, but the process observer could not separate isolated Custom traffic from background Codex activity, so absence of direct non-WBP model egress remains unproven for this live native run
- resume from here: CLOSED
