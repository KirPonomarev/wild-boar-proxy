# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_ADD_REPAIR_PASS Closeout

## Goal

Use the canon-admitted `external-models routes add --json` owner surface to remove the empty sandbox route-registry gap, then re-run owner truth without widening into token/start/validate/materialization work.

## Result

- status: complete
- final verdict: `STOP_AND_DIAGNOSE`
- next action: open `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_PROVIDER_EVIDENCE_SCOPE_ADMISSION_PASS`

## Contour Capsule

- goal: determine whether one bounded route-add mutation against sandbox `routes.json` can shift the owner-level `unknown provider for model claude-sonnet-4-6-thinking` blocker
- branch: `codex/external-agent-lab-isolated`
- head: `94642e2 Audit external-models foundation scope admission`
- touched files: `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/contour.md`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/blocker_confirmation.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/route_payload_plan.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/routes_before_after.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/rollback_snapshot.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/post_add_verification.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/forbidden_drift_check.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/decision_packet.json`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/independent_audit.md`, `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/closeout.md`
- tests run: `python3 -m unittest -q tests.test_cli_external_models`; `python3 -m unittest -q tests.test_ui_shell`; `python3 -m unittest -q tests.test_cli_external_models.ExternalModelsCliTests.test_routes_add_from_stdin_and_models_projection tests.test_cli_external_models.ExternalModelsCliTests.test_routes_add_list_disable_remove_round_trip`
- blocked risks: retrying route variations without owner-proof movement; widening into `validate/check`; widening into token/start or secret admission without a new contour
- next exact command: `python3 -m wild_boar_proxy external-models routes validate --json --route wbp-claude-sonnet-4-6-thinking` only after `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_PROVIDER_EVIDENCE_SCOPE_ADMISSION_PASS` is opened and admits that surface

## Verification

- tests: external-models CLI suite passed; UI shell suite passed; focused route-add round-trip tests passed
- build: `git diff --check`
- manual: baseline sandbox packets captured; one bounded route added through owner surface; post-add packets captured; byte-faithful rollback executed; post-rollback packets captured
- live verification: `routes_count` and `models_count` moved from `0` to `1`, but `healthcheck --json` remained blocked on the same `HTTP 502 unknown provider for model claude-sonnet-4-6-thinking`; rollback restored `routes_count = 0`, `models_count = 0`, and the original owner blocker

## Artifacts

- spec: `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/contour.md`
- packet: `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/decision_packet.json`
- report: `audit_results/sandbox_active_lane_external_models_route_add_repair_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts record packet truth, paths, digests, and counts only; no secret contents were stored

## Notes

- blockers encountered: the empty route registry was real, but eliminating it did not change the owner-level runtime blocker; provider/model-resolution ownership remains unresolved
- follow-up contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_PROVIDER_EVIDENCE_SCOPE_ADMISSION_PASS`
- resume from here: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_PROVIDER_EVIDENCE_SCOPE_ADMISSION_PASS`
