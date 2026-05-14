<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# API Route Builder And Secret Contract Admission Closeout

## Goal

Decide whether API route builder, route create/update, preflight preview, and
secret reference selector surfaces can be admitted into the web UI.

## Result

- status: ready_for_commit
- final verdict: API_ROUTE_BUILDER_AND_SECRET_CONTRACT_NOT_ADMITTED
- next action: keep route builder and secret selector as design inventory only until server-owned route template and safe opaque secret-reference packets are specified and admitted

## Contour Capsule

- goal: decide route builder and secret-reference UI admission
- branch: codex/external-agent-lab-isolated
- head: 2971669
- touched files: audit_results/api_route_builder_and_secret_contract_admission_spec_2026-05-14.md, audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json, audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json, audit_results/api_route_builder_and_secret_contract_admission_closeout_2026-05-14.md
- tests run: python3 -m json.tool audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json; python3 -m json.tool audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json; python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_cli_external_models; python3 tools/check_closeout_resilience.py; python3 -c 'from pathlib import Path; import sys; markers=[bytes.fromhex(x).decode() for x in ("4c617a79776562","7777772e6c617a797765622e636f6d","6d63702d696e7374616c6c","6c617a797765625f6d63705f746f6b656e","42656172657220746f6b656e")]; hits=[str(p) for p in map(Path, sys.argv[1:]) for marker in markers if marker in p.read_text()]; raise SystemExit("\\n".join(hits) if hits else 0)' audit_results/api_route_builder_and_secret_contract_admission_spec_2026-05-14.md audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json audit_results/api_route_builder_and_secret_contract_admission_closeout_2026-05-14.md; git diff --check
- blocked risks: route create/update/draft, preflight-only create/update, and secret-reference selector remain not admitted
- next exact command: git add audit_results/api_route_builder_and_secret_contract_admission_spec_2026-05-14.md audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json audit_results/api_route_builder_and_secret_contract_admission_closeout_2026-05-14.md

## Verification

- tests:
  - `python3 -m json.tool audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json`
  - `python3 -m json.tool audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json`
  - `python3 -m unittest tests.test_web_design_ui tests.test_web_design_live_server tests.test_cli_external_models`
  - `python3 tools/check_closeout_resilience.py`
  - `python3 -c 'from pathlib import Path; import sys; markers=[bytes.fromhex(x).decode() for x in ("4c617a79776562","7777772e6c617a797765622e636f6d","6d63702d696e7374616c6c","6c617a797765625f6d63705f746f6b656e","42656172657220746f6b656e")]; hits=[str(p) for p in map(Path, sys.argv[1:]) for marker in markers if marker in p.read_text()]; raise SystemExit("\\n".join(hits) if hits else 0)' audit_results/api_route_builder_and_secret_contract_admission_spec_2026-05-14.md audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json audit_results/api_route_builder_and_secret_contract_admission_closeout_2026-05-14.md`
  - `git diff --check`
- build: not applicable, spec-only contour
- manual:
  - inspected route parser and command runner
  - inspected route schema and validator
  - inspected web command adapter and live server action allowlists
  - inspected secret permission and validation boundary
  - reconciled previous route config, route builder, and final screen inventory artifacts
- live verification: not applicable, no runtime mutation

## Artifacts

- spec: `audit_results/api_route_builder_and_secret_contract_admission_spec_2026-05-14.md`
- packet: `audit_results/api_route_builder_and_secret_contract_admission_matrix_2026-05-14.json`
- report: `audit_results/api_route_builder_and_secret_contract_admission_independent_audit_2026-05-14.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending until this artifact set is committed
- pushed: pending until this artifact set is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered: none
- follow-up contour: owner-selected; likely server-owned route template packet and safe opaque secret-reference packet if route create/update is still desired
- resume from here: CLOSED
