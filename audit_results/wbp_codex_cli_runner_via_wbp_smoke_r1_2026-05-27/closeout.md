# WBP Codex CLI Runner Via WBP Smoke R1 Closeout

## Goal

Prove that the explicit Codex CLI runner command surface can operate through WBP
as a separate non-native consumer lane, with packet-correlated WBP trace,
auth.command boundary proof, bounded response classification, and no substitution
into native Codex.app, UX, direct egress, Original Codex, or final E2E claims.

## Result

- status: `CODEX_CLI_RUNNER_VIA_WBP_WORKS_NOT_NATIVE_APP`
- final verdict: `python3 -m wild_boar_proxy codex-runner smoke --json --prompt <text>` executed through WBP, `auth.command` was invoked, WBP trace correlation was observed on `/v1/responses` with `upstream_status=200`, and the bounded runner response matched the smoke expectation. This proof remains explicitly non-native and does not claim Codex.app UX, direct egress absence, streaming/tool-loop compatibility, Original Codex reversibility, or final E2E.
- closure state: CLOSED

## Contour Capsule

- goal: classify the explicit CLI runner command surface via WBP as one bounded non-native consumer lane without substituting native app proof or widening model/provider claims
- branch: codex/external-agent-lab-isolated
- head: bf00560e852d5649256fbc0079ebeb9f17812011 before this contour commit
- touched files: wild_boar_proxy/cli_runner.py; wild_boar_proxy/cli_runner_via_wbp.py; wild_boar_proxy/codex_custom_sessions.py; tests/test_cli_runner.py; tools/cli_runner_smoke_readiness_probe.py; tools/cli_runner_via_wbp_smoke_probe.py; audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/*
- tests run: python3 -m py_compile wild_boar_proxy/cli_runner.py wild_boar_proxy/cli_runner_via_wbp.py wild_boar_proxy/codex_custom_sessions.py tests/test_cli_runner.py tools/cli_runner_smoke_readiness_probe.py tools/cli_runner_via_wbp_smoke_probe.py; python3 -m pytest -q tests/test_cli_runner.py tests/test_cli_runner_smoke_readiness_probe.py tests/test_codex_custom_sessions.py tests/test_model_availability.py; python3 tools/cli_runner_via_wbp_smoke_probe.py --evidence-dir audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27; top-level JSON status sweep; secret scan; python3 tools/check_closeout_resilience.py audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/closeout.md
- blocked risks: residual limits remain outside this proof: native Codex.app acceptance, native UX, detached native execution, direct api.openai.com egress absence, Responses streaming/tool-loop re-proof, Original Codex reversibility, and final E2E
- closure state: CLOSED

## Verification

- tests: `python3 -m pytest -q tests/test_cli_runner.py tests/test_cli_runner_smoke_readiness_probe.py tests/test_codex_custom_sessions.py tests/test_model_availability.py` passed with `86 passed`.
- build: `python3 -m py_compile wild_boar_proxy/cli_runner.py wild_boar_proxy/cli_runner_via_wbp.py wild_boar_proxy/codex_custom_sessions.py tests/test_cli_runner.py tools/cli_runner_smoke_readiness_probe.py tools/cli_runner_via_wbp_smoke_probe.py` passed.
- manual: top-level JSON status sweep reported `28 passed` status packets in `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27`; secret scan found `0` matches; `independent_cli_runner_audit.json` and `cli_runner_false_green_audit.json` are both `passed`.
- live verification: the explicit CLI runner command surface ran through isolated `HOME` and `CODEX_HOME`, selected `gpt-5.5`, recorded `auth.command` invocation, and correlated a WBP `/v1/responses` trace with `upstream_status=200`. Native Codex.app launch, owner UI, direct egress absence proof, streaming/tool-loop proof, Original profile mutation, and final E2E were not attempted.

## Artifacts

- spec: thread-owned contour instructions; no repo-resident planning artifact added.
- packet: `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/cli_runner_closeout_packet.json`
- report: `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/independent_cli_runner_audit.json`; `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/scanner_agent_fact_report_packet.json`; `audit_results/wbp_codex_cli_runner_via_wbp_smoke_r1_2026-05-27/verification_results_packet.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit created after this closeout
- pushed: contour branch pushed after commit

## Scope Check

- unrelated work mixed in: no; pre-existing historical dirty evidence remained quarantined and unstaged.
- private-data risk reviewed: yes; generated packets do not include auth headers, raw upstream secrets, raw prompt body, or raw response body, and evidence secret scan produced no matches.

## Notes

- blockers encountered: the prior proof path was proving the wrong surface, the runner helper cleaned temp artifacts before reading the auth stamp/output, and the summary packet was initially emitted too late for the independent audit. All three issues were localized, fixed, and re-verified with fresh live evidence.
- resume from here: CLOSED
