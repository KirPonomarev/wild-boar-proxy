<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# RUNTIME_OWNER_PROCEDURE_OVERLAP_DIAGNOSE_PASS Contour

CONTOUR:
RUNTIME_OWNER_PROCEDURE_OVERLAP_DIAGNOSE_PASS

Goal:
Localize the most likely overlapping admitted runtime procedure inside the
current selector/runtime chain using existing packet and code evidence only, and
determine whether the blocker is best explained by procedure overlap, missing
operational serialization, or unresolved ambiguity.

Size:
M

Risk level:
high

Decision owner:
Canon owns disputed truth interpretation. Maintainer owns diagnosis
implementation and evidence collection. Operator owns any later live runtime
step that is not already admitted.

Mode:
runtime diagnosis / procedure overlap localization

Contour class:
diagnosis-only

Why this contour:
`MASTER_PLAN.md` keeps selector retry and adjacent live-action work parked until
repeated `LOCK_HELD` plus post-retry runtime regression are localized. The
previous contour reduced the problem to a ranked owner-path candidate set and
showed that a launcher-backed runtime owner lane was the strongest class. This
contour narrows one step further: from top-level command family to the shared
runtime procedure that can hold the same serialized lock across a launcher
subprocess.

In scope:
- Use existing packet and code evidence only.
- Reconcile active packet chronology against admitted runtime procedures in the
  active selector/runtime chain.
- Build a bounded procedure overlap matrix:
  - procedure name
  - command surfaces
  - lock site
  - critical-section duration class
  - overlap compatibility with `sync --json`
  - evidence basis in the current chain
  - evidence strength
  - admitted / parked / weaker-candidate status
- Distinguish:
  - legitimate long owner section
  - orchestration overlap
  - missing operational serialization boundary
  - unresolved ambiguity
  - proven code contradiction only if existing evidence proves it
- Emit a machine-readable verdict and closeout.

Out of scope:
- No new `sync --json`.
- No new live runtime retry for confirmation.
- No repair implementation.
- No repair design beyond bounded verdict fields.
- No exact auth admission.
- No sandbox auth materialization.
- No onboarding.
- No route mutation.
- No stage/pilot work.
- No UI work.
- No broad lock-architecture audit outside the active selector/runtime chain.
- No exclusive blame claim unless packet identity actually supports it.

Assumptions:
- Current active truth remains:
  - repeated `LOCK_HELD`
  - no fresh selector progress
  - post-retry runtime regression
- Existing evidence may tighten localization to one shared procedure without
  proving one exclusive top-level command surface.
- If procedure-level localization is not tighter than the prior owner-path
  contour, truthful output remains `STOP_AND_DIAGNOSE`.

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
- prior artifacts:
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/*`
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/*`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/*`
  - `audit_results/runtime_reproof_pass_2026-05-16_v4/*`
- code:
  - `wild_boar_proxy/runtime.py`
- tests:
  - relevant lock / healthcheck / launch / rotation tests in `tests/test_cli.py`

Commands / files:
- Read:
  - `sed -n '3310,3415p' wild_boar_proxy/runtime.py`
  - `sed -n '5168,5182p' wild_boar_proxy/runtime.py`
  - `sed -n '5588,5620p' wild_boar_proxy/runtime.py`
  - `sed -n '6288,6308p' wild_boar_proxy/runtime.py`
  - `sed -n '6885,6945p' wild_boar_proxy/runtime.py`
  - selector retry and runtime reproof packet files
- Write:
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/contour.md`
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/procedure_overlap_matrix.json`
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/decision_packet.json`
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/closeout.md`

Acceptance criteria:
- There is a bounded procedure-level overlap matrix for the active chain.
- One `most_likely_overlapping_procedure` is named with explicit evidence
  strength.
- The contour clearly states whether the blocker is:
  - runtime procedure overlap
  - missing operational serialization
  - unresolved ambiguity
- Retry remains forbidden unless stronger existing evidence truthfully changes
  that.
- No repair claim is made.
- No repair design is mixed in.
- No broader lock-architecture audit is performed.
- No new live retry is performed.
- No auth/onboarding/stage/pilot/UI scope is mixed in.
- No exclusive blame claim is made without packet identity support.
- The next contour is named narrowly and honestly.

Verification:
- tests:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_blocks_held_lock_without_mutation tests.test_cli.CliTests.test_sync_clears_stale_lock_and_proceeds_past_lock_gate tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot tests.test_cli.CliTests.test_status_reports_stable_policy_drift_without_greenwash tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_stale_selected_snapshot`
- build:
  - `python3 -m json.tool audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/procedure_overlap_matrix.json`
  - `python3 -m json.tool audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/decision_packet.json`
  - `git diff --check`
- manual:
  - cross-check the procedure matrix against packet chronology
  - confirm no new live runtime commands were executed
  - confirm localization is tighter than the prior owner-path contour
- live packet:
  - none; live retry remains out of scope

Artifacts:
- spec:
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/procedure_overlap_matrix.json`
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/runtime_owner_procedure_overlap_diagnose_pass_2026-05-16/closeout.md`

Stop conditions:
- `STOP_AND_DIAGNOSE` if tighter localization would require a fresh live retry.
- `STOP_AND_DIAGNOSE` if work drifts into repair implementation.
- `STOP_AND_DIAGNOSE` if work drifts into repair design.
- `STOP_AND_DIAGNOSE` if work drifts into UI/auth/onboarding/stage/pilot.
- `STOP_AND_DIAGNOSE` if no stronger procedure-level localization is possible
  from existing evidence.

Closeout:
- verification complete:
  - targeted tests pass
  - `procedure_overlap_matrix.json` parses
  - `decision_packet.json` parses
  - `git diff --check` passes
  - closeout resilience passes
  - staged-only closeout check passes
- commit:
  - required after staged verification
- push:
  - required by `DELIVERY_RULES.md` before contour is considered closed
- next contour:
  - `RUNTIME_LAUNCHER_OWNER_PROCEDURE_SERIALIZATION_FIX_PASS`
