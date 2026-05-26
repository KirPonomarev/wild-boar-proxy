# WBP_CODEX_MODEL_AVAILABILITY_SMOKE_MATRIX_R1 Closeout

## Goal

Classify direct WBP model availability for a bounded candidate set without treating catalog presence, direct WBP success, or route references as native Codex acceptance.

## Result

- status: WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED
- final verdict: direct WBP non-stream response acceptance is proven for `gpt-5.5`, `gpt-5.4-mini`, and `gpt-5.4`; native/Codex/stream/tool/egress/final claims remain unproven
- closure state: CLOSED

## Contour Capsule

- goal: direct WBP model availability matrix with per-model claim levels and no native/egress/tool overclaim
- branch: codex/external-agent-lab-isolated
- head: 87d69df8 source baseline used for packet generation
- touched files: wild_boar_proxy/model_availability.py; tools/model_availability_direct_only_smoke_probe.py; tests/test_model_availability.py; audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-26/
- tests run: direct-only smoke probe; model/catalog/auth/repo/closeout unittest suite; py_compile; JSON packet audit; strict secret/prompt scan
- blocked risks: Codex/native acceptance, streaming, tool loop, direct egress absence, Original mode, and final E2E are not proven by this contour
- closure state: CLOSED

## Verification

- tests: `verification_results_packet.json` records 64 targeted tests passing
- build: `verification_results_packet.json` records py_compile success for model availability helper, probe, and tests
- manual: no owner/manual UI action was required or used
- live verification: direct WBP HTTP non-stream smoke passed for `gpt-5.5`, `gpt-5.4-mini`, and `gpt-5.4`

## Artifacts

- spec: thread-only contour scope, not written into repository
- packet: `model_availability_direct_only_summary_packet.json` records `WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED`
- report: `model_availability_false_green_audit.json`, `independent_model_availability_direct_only_audit.json`, and `independent_agent_model_availability_audit.json` record no unresolved blocker

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by repository history for this closeout commit
- pushed: recorded by repository remote state after push

## Scope Check

- unrelated work mixed in: historical dirty evidence paths are quarantined in `historical_dirt_quarantine_packet.json` and were not relied on as active truth
- private-data risk reviewed: `secret_redaction_audit.json` and strict local scan found no raw auth, upstream secret, or raw prompt in this contour evidence

## Notes

- blockers encountered: route-policy reference packet required nested `allowed_status` handling because the historical route truth packet does not expose top-level `status`
- resume from here: CLOSED
