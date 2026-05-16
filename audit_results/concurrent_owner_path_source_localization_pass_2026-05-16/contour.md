<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# CONCURRENT_OWNER_PATH_SOURCE_LOCALIZATION_PASS Contour

CONTOUR:
CONCURRENT_OWNER_PATH_SOURCE_LOCALIZATION_PASS

Goal:
Localize the evidence-backed active owner-path candidate set for
`wild-boar-proxy.lock` contention during the current selector refresh chain, and
determine whether the blocker is caused by admissible concurrent runtime
activity, missing serialization, or orchestration overlap.

Size:
M

Risk level:
high

Decision owner:
Canon owns disputed truth interpretation. Maintainer owns diagnosis
implementation and evidence collection. Operator owns any later live runtime
step that is not already admitted.

Mode:
runtime diagnosis / owner-path localization

Why this contour:
The prior diagnosis contour already established that repeated `LOCK_HELD` does
not look like a stale-lock cleanup bug, that failed `sync --json` does not
mutate `selected_backend_snapshot`, and that the red
`claim_gate=blocked` / `policy_drift=detected` surface is a truthful fallback
once activation evidence goes stale. The next narrow question is therefore not
"why did status go red?" but "which owner path is actually competing for the
same lock during the active selector/runtime chain?"

In scope:
- Inventory only owner paths that can acquire the same
  `wild-boar-proxy.lock` inside the current active selector/runtime chain.
- Map each relevant owner path to:
  - command surface
  - code entrypoint
  - lock acquisition site
  - mutation scope
  - overlap compatibility with `sync --json`
- Build an evidence-backed ranked candidate set for lock contention source.
- Classify the blocker as one primary category:
  - admissible concurrent runtime activity
  - missing serialization boundary
  - orchestration overlap
  - unresolved localization
- Produce machine-readable localization artifacts and closeout.

Out of scope:
- No new selector retry.
- No `sync --json` just to test.
- No new live runtime commands for confirmation.
- No repair implementation.
- No auth admission.
- No onboarding.
- No route mutation.
- No stage/pilot work.
- No UI work.
- No broad repo-wide lock audit outside the active selector/runtime chain.

Assumptions:
- Active truth is the one fixed in `MASTER_PLAN.md` and the latest diagnosis
  contour, not older intermediate closeouts.
- Repeated `LOCK_HELD` remains retry-forbidden unless this contour yields
  stronger localization than the prior diagnosis contour.
- If owner source cannot be localized from existing evidence plus code/tests,
  truthful output remains `STOP_AND_DIAGNOSE`.

Inputs:
- docs:
  - `CANON.md`
  - `MASTER_PLAN.md`
  - `RUNTIME_CONTRACT.md`
  - `COMMAND_API.md`
  - `DELIVERY_RULES.md`
- prior artifacts:
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/evidence_chain.json`
  - `audit_results/stop_and_diagnose_repeated_selector_lock_and_runtime_regression_2026-05-16/decision_packet.json`
  - `audit_results/selector_refresh_owner_path_pass_2026-05-16_v3/sync_refresh_packet.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/sync_refresh_packet.json`
  - `audit_results/selector_refresh_owner_path_pass_retry_once_2026-05-16/rotation_after_sync.json`
  - `audit_results/runtime_reproof_pass_2026-05-16_v4/decision_packet.json`
- code:
  - `wild_boar_proxy/runtime.py`
- tests:
  - `tests/test_cli.py`

Commands / files:
- Read:
  - `rg -n "serialized_lock\\(|run_sync\\(|run_launch_smoke\\(|run_healthcheck\\(|run_rollout_rotation_inspect\\(" wild_boar_proxy/runtime.py`
  - `sed -n '1180,1265p' wild_boar_proxy/runtime.py`
  - `sed -n '3000,3415p' wild_boar_proxy/runtime.py`
  - `sed -n '5526,5818p' wild_boar_proxy/runtime.py`
  - `sed -n '6200,7055p' wild_boar_proxy/runtime.py`
  - prior packet files listed above
- Write:
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/contour.md`
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/owner_path_matrix.json`
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/decision_packet.json`
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/closeout.md`

Acceptance criteria:
- Owner-path inventory is limited to paths that can acquire the same lock inside
  the current active selector/runtime chain.
- A ranked candidate set exists for lock contention source.
- `most_likely_owner_source` is named with explicit evidence strength.
- The contour clearly distinguishes:
  - code-level serialization issue
  - runtime-procedure overlap
  - admissible concurrent owner activity
  - unresolved localization
- It is explicitly stated whether retry remains forbidden or becomes narrowly
  admissible.
- No repair claim is made.
- No new live retry is performed.
- No auth/onboarding/stage/pilot/UI scope is mixed in.
- The next contour is named narrowly and honestly.

Verification:
- tests:
  - `python3 -m unittest -q tests.test_cli.CliTests.test_sync_blocks_held_lock_without_mutation tests.test_cli.CliTests.test_sync_clears_stale_lock_and_proceeds_past_lock_gate tests.test_cli.CliTests.test_sync_failure_does_not_mutate_selected_backend_snapshot tests.test_cli.CliTests.test_status_reports_stable_policy_drift_without_greenwash tests.test_cli.CliTests.test_status_uses_approved_target_policy_drift_surface_when_live_activation_evidence_is_valid tests.test_cli.CliTests.test_rollout_rotation_inspect_reports_stale_selected_snapshot`
- build:
  - `python3 -m json.tool audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/owner_path_matrix.json`
  - `python3 -m json.tool audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/decision_packet.json`
  - `git diff --check`
- manual:
  - cross-check packet chronology against the ranked candidate set
  - confirm no new live runtime commands were added or executed
  - confirm the next contour remains diagnosis/procedure-localization only
- live packet:
  - none; live retry remains out of scope

Artifacts:
- spec:
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/contour.md`
- packet:
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/owner_path_matrix.json`
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/decision_packet.json`
- closeout note:
  - `audit_results/concurrent_owner_path_source_localization_pass_2026-05-16/closeout.md`

Stop conditions:
- `STOP_AND_DIAGNOSE` if existing evidence cannot distinguish candidates more
  clearly than the prior contour.
- `STOP_AND_DIAGNOSE` if localization would require a fresh live retry.
- `STOP_AND_DIAGNOSE` if work drifts into repair implementation.
- `STOP_AND_DIAGNOSE` if work drifts into UI/auth/onboarding/stage/pilot work.
- `STOP_AND_DIAGNOSE` if the contour expands into a general lock audit outside
  the active chain.

Closeout:
- verification complete:
  - targeted lock and truth tests pass
  - `owner_path_matrix.json` parses
  - `decision_packet.json` parses
  - `git diff --check` passes
  - closeout resilience passes
  - staged-only closeout check passes
- commit:
  - required after staged verification
- push:
  - required by `DELIVERY_RULES.md` before contour is considered closed
- next contour:
  - `RUNTIME_OWNER_PROCEDURE_OVERLAP_DIAGNOSE_PASS`
