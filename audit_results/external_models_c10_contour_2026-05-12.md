<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# External Models C10 Contour

## Contour

- contour_id: `external_models_c10_sandbox_and_tool_execution_admission_boundary`
- date_utc: `2026-05-12`
- branch: `codex/external-agent-lab-isolated`
- base_head_before_c10: `e11d0a8`
- mode: `audit + decision`

## Goal

Decide whether any bounded sandbox/tool-execution lane is canon-admissible for
external-models without implementing execution capability.

## Verdict

- machine_verdict: `NOT_ADMISSIBLE`

## Evidence Basis

- [ADR-0002-external-models-bounded-compatibility-adapter.md](/Volumes/Work/wild-boar-proxy/ADR-0002-external-models-bounded-compatibility-adapter.md:16)
  keeps external-models as a bounded compatibility adapter and warns that a
  wider merge would create a second hidden engine and a new runtime truth
  surface.
- [MASTER_PLAN.md](/Volumes/Work/wild-boar-proxy/MASTER_PLAN.md:225)
  keeps `CLIProxyAPI` as the engine and [MASTER_PLAN.md](/Volumes/Work/wild-boar-proxy/MASTER_PLAN.md:229)
  assigns upstream execution behavior to engine ownership.
- [MASTER_PLAN.md](/Volumes/Work/wild-boar-proxy/MASTER_PLAN.md:261)
  forbids writing a second proxy server or custom transport executor without a
  concrete blocker.
- [wild_boar_proxy/external_models/routes.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/external_models/routes.py:312)
  still exposes `profile codex-desktop` as a non-mutating packet with
  `writes_external_config=false`, `profile_ready=false`, and
  `runtime_claim_blocked=true`.
- repo scan over `wild_boar_proxy/external_models` found no existing shell,
  filesystem, git, browser, or generic tool-execution surface to extend.
- repo scan found no canon-approved hard blocker or explicit exception
  justifying execution widening.

## Capability Matrix

Permanently forbidden in the current canon:

- shell execution
- arbitrary filesystem writes outside current managed artifact lanes
- git operations
- browser automation
- generic tool execution
- dynamic code loading
- adapter-local task runner semantics

Not admitted in this contour:

- even bounded allowlisted execution helpers
- helper-execution protocol design
- sandbox API shape

Reason:

- no concrete blocker was found that requires widening beyond bounded adapter
  translation
- convenience alone is not a valid blocker basis

## Verification

Executed:

- `python3 -m unittest -q tests.test_external_models`
  - `Ran 11 tests ... OK`
- `python3 -m unittest -q tests.test_cli_external_models`
  - `Ran 17 tests ... OK`
- `python3 -m compileall -q wild_boar_proxy tests`
  - passed
- `git diff --check`
  - passed

## Scope Integrity

- no execution capability implemented
- no command-shape expansion introduced
- no runtime truth semantics changed
- unrelated dirty files in:
  - `external_agent_lab/*`
  - `tests/test_external_agent_lab.py`
  - `wild_boar_proxy/runtime.py`
  remained out of contour scope
