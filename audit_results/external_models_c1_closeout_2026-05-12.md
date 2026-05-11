<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C1 Foundation Closeout

## Goal

Build the canon-aligned `external-models` foundation without live provider
integration, real sidecar lifecycle, or engine duplication.

## Result

- status: complete
- final verdict: C1 foundation contract implemented and verified locally
- next action: move to `external_models_c2_lifecycle_and_mocked_status`

## Verification

- tests:
  - `python3 -m unittest -q tests.test_external_models`
  - `python3 -m unittest -q tests.test_cli_external_models`
  - `python3 -m unittest -q tests.test_external_agent_lab`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
- manual:
  - isolated temp-path `external-models routes add --json --stdin`
  - isolated temp-path `external-models status --json`
- live verification:
  - none in C1

## Artifacts

- spec:
  - `EXTERNAL_MODELS_C1_FOUNDATION_SPEC.md`
- packet:
  - `audit_results/external_models_c1_decision_packet_2026-05-12.json`
- report:
  - `audit_results/external_models_c1_independent_audit_2026-05-12.json`

## Git

- branch:
  - `codex/external-agent-lab-isolated`
- commit:
  - `5f264be`
  - `05841c8`
- pushed:
  - yes

## Scope Check

- unrelated work mixed in:
  - no staged contour files from dirty `runtime.py` or external lab mutations
- private-data risk reviewed:
  - yes; isolated temp paths only, no real `~/.wild-boar-proxy/*` writes required

## Notes

- blockers encountered:
  - Python 3.9 compatibility required `timezone.utc` instead of `datetime.UTC`
- follow-up contour:
  - `external_models_c2_lifecycle_and_mocked_status`
