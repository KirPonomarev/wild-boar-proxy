# WBP Model Availability Smoke Matrix R1 Closeout

## Goal

Classify model availability one model at a time through direct WBP non-stream `/v1/responses` proof, while separating catalog visibility, route family, admission, default model source, external-route admission, direct WBP response shape, Codex/native acceptance, streaming, tool loop, egress, and UX.

## Result

- status: `WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED`
- final verdict: `gpt-5.5`, `gpt-5.4-mini`, and `gpt-5.4` are classified as direct WBP non-stream response accepted; no Codex/native acceptance, streaming, tool-loop, egress, account-pool, UX, Original reversibility, or final E2E claim is made.
- closure state: CLOSED

## Contour Capsule

- goal: classify direct WBP model availability with explicit candidate partition, route family, default model source, admission, external-route boundary, and false-green audit packets
- branch: codex/external-agent-lab-isolated
- head: d813747d0ab6f6592974e9a28f0ca687f8bac2b3 before this contour commit
- touched files: wild_boar_proxy/model_availability.py; tests/test_model_availability.py; tools/model_availability_direct_only_smoke_probe.py; audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27
- tests run: py_compile; direct-only model availability probe; tests.test_model_availability; tests.test_codex_model_registry; tests.test_wbp_model_catalog_contract; tests.test_cli_external_models; tests.test_repo_hygiene; tests.test_closeout_resilience; contour packet validation; JSON parse; secret scan; git diff --check
- blocked risks: no blocking risk remains for this contour; residual limits record that this proof is direct WBP non-stream only and does not prove Codex/native acceptance, streaming, tool loop, direct egress absence, UX, Original reversibility, or final E2E
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest -q tests.test_model_availability` passed 42 tests; broader model/catalog/external-route subset passed 100 tests.
- build: `python3 -m py_compile wild_boar_proxy/model_availability.py tools/model_availability_direct_only_smoke_probe.py` passed.
- manual: `validate_model_availability_contour_packets` returned no failures for the generated evidence packets; independent audit and false-green audit packets are `ok`.
- live verification: direct WBP HTTP non-stream `/v1/responses` was exercised for the admitted candidate set; native app launch, Codex CLI runner, streaming, tool loop, egress capture, UX, Original profile mutation, and final E2E were not attempted.

## Artifacts

- spec: thread-owned contour instructions; no repo-resident planning artifact added.
- packet: `audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_direct_only_summary_packet.json`
- report: `audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/independent_model_availability_audit.json`; `audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/scanner_agent_fact_report_packet.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit created after this closeout
- pushed: contour branch pushed after commit

## Scope Check

- unrelated work mixed in: no; pre-existing historical dirty evidence remained quarantined and unstaged.
- private-data risk reviewed: yes; generated packets do not include auth headers, raw upstream secrets, or raw prompt body, and evidence secret scan produced no matches.

## Notes

- blockers encountered: no blocking findings; no external WBP/API route candidate was present in the direct `/v1/models` admitted smoke set, so external provider-family compatibility remains unclaimed.
- resume from here: CLOSED
