# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_SCOPE_RESTORATION_ADMISSION_PASS Closeout

## Goal

Determine the next executable contour after provider-evidence admission selected `routes validate`, but the route-add contour had already rolled the route back and left the current sandbox registry empty.

## Result

- status: complete
- final verdict: `GO_TO_EXACT_NEXT_REPAIR_CONTOUR`
- next action: open `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS`

## Contour Capsule

- goal: remove the false `current route exists` precondition and choose the narrowest executable contour that restores validate eligibility honestly
- branch: `codex/external-agent-lab-isolated`
- head: `f4b817f Audit external-models provider evidence scope admission`
- touched files: `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/contour.md`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/rollback_truth_basis.json`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/executable_precondition_check.json`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/scope_split_matrix.json`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/canon_admissibility_matrix.json`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/next_contour_selection.json`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/independent_audit.md`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/decision_packet.json`, `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/closeout.md`
- tests run: `python3 -m unittest -q tests.test_cli_external_models.ExternalModelsCliTests.test_routes_add_list_disable_remove_round_trip tests.test_cli_external_models.ExternalModelsCliTests.test_route_validate_success_writes_network_evidence_and_state`; `python3 -m unittest -q tests.test_ui_shell`
- blocked risks: hidden route rematerialization inside validate contour; fusing registry mutation with validate state/evidence mutation; trusting remembered route shape over current packet truth
- next exact command: `python3 -m wild_boar_proxy external-models routes add --json --stdin` after opening `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS`

## Verification

- tests: focused route add/remove and route validate tests passed; UI shell suite passed
- build: `git diff --check`
- manual: previous route-add and provider-evidence decision packets were re-read against current code paths; no live mutation executed in this admission contour
- live verification: none by design; this contour was executable-scope admission only

## Artifacts

- spec: `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/contour.md`
- packet: `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/decision_packet.json`
- report: `audit_results/sandbox_active_lane_external_models_route_validate_scope_restoration_admission_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts contain only contour decisions, packet truth, paths, and command surfaces

## Notes

- blockers encountered: the previous admission contour selected `routes validate`, but the previous execution contour had already rolled the route back, making validate non-runnable on current truth
- follow-up contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS`
- resume from here: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS`
