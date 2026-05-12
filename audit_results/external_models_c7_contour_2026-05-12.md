<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C7 Installer And Package Integration

```text
CONTOUR:
external_models_c7_installer_and_package_integration

Goal:
Интегрировать external-models data/layout и packaging boundary
в уже существующие installer/import/reset/uninstall/package owner surfaces
без новых truth surfaces, без runtime-claim drift и без release/pilot escalation.

Size: M / L
Risk level: medium
Decision owner: project owner / canon-first
Mode: implementation

In scope:
- external-models layout initialization in installer init
- bounded external-models legacy import support for compatible persisted artifacts only
- external-models managed-state cleanup in companion reset/uninstall with secrets preservation
- package build/verify exclusion checks for external-models runtime-like artifacts
- focused tests and independent audit

Out of scope:
- new installer/package commands
- runtime truth changes
- live provider validation
- Codex config mutation
- release or pilot claim work
- live-path reopening

Assumptions:
- installer/package owner surfaces already exist and remain authoritative
- external-models remains bounded compatibility state, not runtime truth
- tests and manual verification use isolated WBP_* paths only

Inputs:
- docs:
  - CANON.md
  - MASTER_PLAN.md
  - COMMAND_API.md
  - RUNTIME_CONTRACT.md
  - AGENTS.md
  - ADR-0002-external-models-bounded-compatibility-adapter.md
- code:
  - wild_boar_proxy/runtime.py
  - wild_boar_proxy/external_models/paths.py
  - tests/test_cli.py
  - tests/test_external_models.py
- runtime evidence:
  - isolated installer/package owner-surface probes only

Commands / files:
- python3 -m unittest -q tests.test_external_models
- python3 -m unittest -q tests.test_cli_external_models
- python3 -m unittest -q tests.test_cli -k installer
- python3 -m unittest -q tests.test_cli -k legacy
- python3 -m unittest -q tests.test_cli -k companion
- python3 -m unittest -q tests.test_cli -k package
- python3 -m compileall -q wild_boar_proxy tests
- git diff --check

Acceptance criteria:
- external-models layout is integrated through existing installer/package owner surfaces
- secrets.env permission rule is enforced for installer/import surfaces
- package build excludes external-models secrets/state/evidence/private material
- package verify checks package boundary, not checksum only
- reset/uninstall behavior for external-models is explicit and tested
- legacy import stays bounded to compatible source artifacts only
- installer init does not pre-seed observed truth
- no new installer/package commands are introduced
- no runtime truth semantics change
- no pilot/release claim is introduced

Verification:
- tests:
  - python3 -m unittest -q tests.test_external_models
  - python3 -m unittest -q tests.test_cli_external_models
  - python3 -m unittest -q tests.test_cli -k installer
  - python3 -m unittest -q tests.test_cli -k legacy
  - python3 -m unittest -q tests.test_cli -k companion
  - python3 -m unittest -q tests.test_cli -k package
- build:
  - python3 -m compileall -q wild_boar_proxy tests
  - git diff --check
- manual:
  - isolated installer init/reset probe
  - isolated package build/verify probe
  - tar listing inspection for external-models exclusion boundary
- live packet:
  - none

Artifacts:
- spec:
  - audit_results/external_models_c7_contour_2026-05-12.md
- packet:
  - audit_results/external_models_c7_decision_packet_2026-05-12.json
- closeout note:
  - audit_results/external_models_c7_closeout_2026-05-12.md

Stop conditions:
- contour requires new installer/package commands
- runtime truth semantics start drifting
- legacy import requires provider/route reinterpretation
- package boundary cannot exclude private external-models material cleanly

Closeout:
- verification complete:
  - focused tests green
  - compileall green
  - diff check clean
  - isolated owner-surface probes passed
- commit:
  - required
- push:
  - required
- next contour:
  - future-only items from v2.4 remain deferred
```
