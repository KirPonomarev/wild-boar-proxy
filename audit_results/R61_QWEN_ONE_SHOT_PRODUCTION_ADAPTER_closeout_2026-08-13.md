<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# R61 Qwen One-Shot Production Adapter Closeout

## Goal

Admit a server-owned, fail-closed Qwen Code production one-shot adapter with
sealed argv, isolated auth presence, bounded JSON output, read-only project
access, and an operational-child-only network boundary without claiming live
provider proof.

## Result

- status: implementation and deterministic verification complete
- final verdict: PASS for R61 code admission; B10_LIVE remains explicitly unproven
- closure state: CLOSED

## Contour Capsule

- goal: replace the fake-only Qwen code claim with a sealed production adapter contract
- branch: `codex/r61-qwen-one-shot-production-adapter`
- head: `fb0aa59b56ad9638f3e8fbba334b867d44de88c6`
- touched files: `RUNTIME_CONTRACT.md`; R61 spec and ADR; six focused test modules; `wild_boar_proxy/final_candidate_assurance.py`; `wild_boar_proxy/gate_evidence_bundle_v2.py`; `wild_boar_proxy/one_shot_cli_runtime.py`; `wild_boar_proxy/qwen_one_shot_cli.py`
- tests run: focused 148 passed plus 4 subtests; full 5079 passed plus 989 subtests; repair isolation 153 passed; repaired runtime 28 passed plus 20 consecutive orphan-cleanup stress passes; core 634 passed plus 136 subtests; custom-stability 27 passed plus 5 subtests; targeted hygiene repair 1 passed
- blocked risks: exact Qwen binary admission, operator-managed auth, and real provider positive/negative proof were not authorized or performed and remain B10_LIVE gates
- closure state: CLOSED

## Verification

- tests: `148 passed, 4 subtests passed`; `5079 passed, 1 warning, 989 subtests passed in 1208.47s`; repair isolation `153 passed`; repaired runtime `28 passed` plus 20 consecutive orphan-cleanup stress passes; repaired core `634 passed, 136 subtests passed in 70.83s`; repaired custom stability `27 passed, 5 subtests passed in 2.81s`
- build: repaired `make check` compiled the tree and collected 5080 tests
- manual: staged hygiene and `git diff --check` passed; exact Qwen argv, immutable privacy environment, buffered JSON success envelope, unique R61 evidence stage, and distinct Kimi pending boundary were reviewed
- live verification: not performed; no Qwen binary, login, credential read, admission write, or provider request was used

## Artifacts

- spec: `audit_results/R61_QWEN_ONE_SHOT_PRODUCTION_ADAPTER_SPEC_2026-08-11.md`
- packet: deterministic test packets generated in isolated temporary test homes only
- report: `audit_results/ADR_R61_QWEN_OPERATIONAL_NETWORK_SANDBOX_2026-08-11.md`

## Git

- branch: `codex/r61-qwen-one-shot-production-adapter`
- commit: implementation `5f6e4a0542d96652f90bcbd208b962e3d024fe32`; process cleanup repair `fb0aa59b56ad9638f3e8fbba334b867d44de88c6`
- pushed: implementation and repair commits were each verified at the matching remote branch ref

## Scope Check

- unrelated work mixed in: no; runtime, contract, evidence guard, and direct regressions are one execution-core contour
- private-data risk reviewed: yes; auth content is never read or emitted, secret-shaped prompts fail before spawn, and test fixtures contain no scanner-shaped token literals

## Notes

- blockers encountered: encrypted worktree metadata and local Node/Python test tooling were restored after reboot; a scanner-shaped negative fixture was rewritten without weakening coverage; CI exposed a post-`SIGKILL` process-group exit race, which was repaired with bounded cleanup waiting and deterministic plus stress regressions
- resume from here: CLOSED
