# HISTORICAL_ITEM_0_RECONCILIATION_R1 Closeout

## Goal

Reconcile the remaining historical item 0 tail by separating historical external-agent-lab seed/reference material from active current runtime truth, mapping what is superseded versus merely historical-only, and closing the ambiguity without upgrading runtime claims.

## Result

- status: ok
- final verdict: HISTORICAL_ITEM_0_RECONCILIATION_CLASSIFIED_AND_CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: close the historical/current inventory gap by building a packet-backed reconciliation ledger that keeps historical seed material non-counted unless explicitly replaced or reconfirmed by current packets.
- branch: codex/external-agent-lab-isolated
- head: dcc09ef2
- touched files: tools/historical_item_0_reconciliation_r1_probe.py; tests/test_historical_item_0_reconciliation_r1_probe.py; audit_results/historical_item_0_reconciliation_r1_2026-05-28/*.json; audit_results/historical_item_0_reconciliation_r1_2026-05-28/closeout.md
- tests run: python3 -m pytest -q tests/test_historical_item_0_reconciliation_r1_probe.py; python3 -m py_compile tools/historical_item_0_reconciliation_r1_probe.py tests/test_historical_item_0_reconciliation_r1_probe.py; python3 tools/historical_item_0_reconciliation_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/historical_item_0_reconciliation_r1_2026-05-28; python3 -m pytest -q tests/test_historical_item_0_reconciliation_r1_probe.py tests/test_final_dual_lane_agent_workflow_e2e_r1_probe.py tests/test_generic_provider_and_model_registry_r1.py; JSON parse sweep; python3 tools/check_closeout_resilience.py --staged-only; git diff --check
- blocked risks: no functional runtime blocker remains inside this contour; historical external-agent-lab materials remain non-counted by design; isolated-lab docs and tests do not become fresh runtime proof; superseded seed-model claims remain superseded rather than reproven
- closure state: CLOSED

## Verification

- tests: 2 passed in the new contour test; 7 passed in the combined focused regression run with final E2E and generic provider/model registry tests
- build: py_compile passed for the new probe and test
- manual: generated 6/6 JSON packets and parsed all packets successfully
- live verification: none required; this contour is read-only evidence lineage reconciliation and does not reopen runtime execution

## Artifacts

- spec: thread-only contour plan
- packet: current_truth_inventory_packet.json; historical_seed_inventory_packet.json; reconfirmed_vs_superseded_matrix.json; historical_item0_counting_boundary_packet.json; false_green_boundary_packet.json; independent_audit_packet.json
- report: closeout.md

## Git

- branch: codex/external-agent-lab-isolated
- commit: dcc09ef2
- pushed: pending at closeout authoring

## Scope Check

- unrelated work mixed in: no; existing dirty worktree entries were left untouched and not staged
- private-data risk reviewed: yes; this contour reads repo-local packets/docs/tests only and records no auth values, prompts, or live runtime secrets

## Notes

- blockers encountered: a first attempt to start a brand-new mini-agent hit the thread agent limit, so the contour proceeded with local packet generation and one reused mini-agent sidecar report; only the local materialized packets count as evidence.
- resume from here: CLOSED
