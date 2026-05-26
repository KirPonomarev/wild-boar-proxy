# WBP Codex CLI Runner Via WBP Smoke R1 Closeout

## Goal

Prove Codex CLI runner as a separate non-native WBP consumer lane with isolated command execution, WBP route trace, response hash, no ambient authority, reference-only model availability, no route/account mutation, and no native/UX/egress/streaming/tool-loop/final claim.

## Result

- status: `CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP`
- final verdict: CLI runner executed through WBP with route trace observed and response hash recorded; this is explicitly non-native and does not prove Codex.app UX, Original reversibility, direct egress absence, streaming, tool loop, expanded model availability, or final E2E.
- closure state: CLOSED

## Contour Capsule

- goal: classify CLI runner via WBP as a non-native consumer lane without substituting native app proof or expanding model availability
- branch: codex/external-agent-lab-isolated
- head: 10e0f7cc7286985f855a2ff3e9694da946089b91 before this contour commit
- touched files: wild_boar_proxy/cli_runner.py; wild_boar_proxy/cli_runner_via_wbp.py; tests/test_cli_runner.py; tools/cli_runner_via_wbp_smoke_probe.py; audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27
- tests run: py_compile; cli runner probe; tests.test_cli_runner; tests.test_model_availability; tests.test_repo_hygiene; tests.test_closeout_resilience; contour packet validation; JSON parse; secret scan; git diff --check
- blocked risks: no blocking risk remains for this contour; residual limits record that native app, UX, egress absence, streaming, tool loop, Original reversibility, and final E2E remain outside this proof
- closure state: CLOSED

## Verification

- tests: `python3 -m unittest -q tests.test_cli_runner` passed 17 tests; broader CLI/model/repo subset passed after this closeout.
- build: `python3 -m py_compile wild_boar_proxy/cli_runner.py wild_boar_proxy/cli_runner_via_wbp.py tools/cli_runner_via_wbp_smoke_probe.py` passed.
- manual: `validate_cli_runner_contour_packets` returned no failures for the generated evidence packets; independent audit and false-green audit packets are `passed`.
- live verification: Codex CLI binary lane was exercised through temp `HOME` and `CODEX_HOME`; native Codex.app launch, owner UI, direct egress absence proof, streaming, tool loop, Original profile mutation, and final E2E were not attempted.

## Artifacts

- spec: thread-owned contour instructions; no repo-resident planning artifact added.
- packet: `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/cli_runner_closeout_packet.json`
- report: `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/independent_cli_runner_audit.json`; `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/scanner_agent_fact_report_packet.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit created after this closeout
- pushed: contour branch pushed after commit

## Scope Check

- unrelated work mixed in: no; pre-existing historical dirty evidence remained quarantined and unstaged.
- private-data risk reviewed: yes; generated packets do not include auth headers, raw upstream secrets, raw prompt body, or raw response body, and evidence secret scan produced no matches.

## Notes

- blockers encountered: one path-normalization bug and one self-validation ordering bug were found before closure; both were localized, fixed, and re-verified.
- resume from here: CLOSED
