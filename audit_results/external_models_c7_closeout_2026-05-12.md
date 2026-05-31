<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C7 Closeout

## Goal

Integrate external-models managed artifact boundaries into the existing
installer/import/reset/uninstall/package owner surfaces without changing runtime
truth or release/pilot state.

## Result

- status: completed
- final verdict:
  - `bounded_external_models_installer_package_integration_completed`
- next action:
  - no immediate external-models runtime contour is opened here
  - future-only v2.4 items remain deferred

## Verification

- tests:
  - `python3 -m unittest -q tests.test_external_models`
  - observed result: `Ran 9 tests ... OK`
  - `python3 -m unittest -q tests.test_cli_external_models`
  - observed result: `Ran 16 tests ... OK`
  - `python3 -m unittest -q tests.test_cli -k installer`
  - observed result: `Ran 2 tests ... OK`
  - `python3 -m unittest -q tests.test_cli -k legacy`
  - observed result: `Ran 5 tests ... OK`
  - `python3 -m unittest -q tests.test_cli -k companion`
  - observed result: `Ran 6 tests ... OK`
  - `python3 -m unittest -q tests.test_cli -k package`
  - observed result: `Ran 9 tests ... OK`
- build:
  - `python3 -m compileall -q wild_boar_proxy tests`
  - observed result: passed
  - `git diff --check`
  - observed result: passed
- manual:
  - isolated `installer init --json` probe
  - isolated `companion reset --json` probe
  - isolated `package experimental build/verify` probe
  - tar listing inspection for package boundary
- live verification:
  - none
  - contour intentionally stayed outside live-path and runtime-claim work

## Artifacts

- spec:
  - `audit_results/external_models_c7_contour_2026-05-12.md`
- packet:
  - `audit_results/external_models_c7_decision_packet_2026-05-12.json`
- report:
  - `audit_results/external_models_c7_independent_audit_2026-05-12.json`

## Git

- branch:
  - `codex/external-agent-lab-isolated`
- commit:
  - pending
- pushed:
  - pending

## Scope Check

- unrelated work mixed in:
  - no new owner surfaces
  - no runtime truth changes
  - no live-path truth changes
- private-data risk reviewed:
  - yes
  - package tests specifically asserted exclusion of external-models secrets/state/evidence artifacts

## Notes

- blockers encountered:
  - none inside contour scope
  - independent audit separately flagged unrelated dirty `run_promote` drift in `wild_boar_proxy/runtime.py` outside C7 scope
- follow-up contour:
  - future-only items from v2.4 remain deferred
