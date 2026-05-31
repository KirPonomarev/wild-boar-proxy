# SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_RESTORE_REPAIR_PASS Closeout

## Goal

Restore the already admitted route into the sandbox external-models registry so
that `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`
becomes honestly runnable again, without widening into validate, check,
start, token, or materialization work.

## Result

- status: complete
- final verdict: `GO_TO_SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`
- next action: open `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS` with explicit sandbox env binding

## Contour Capsule

- goal: restore the previously admitted route on the sandbox `routes.json` surface and prove validate preconditions are true again
- branch: `codex/external-agent-lab-isolated`
- head: `1490086 Audit external-models validate scope restoration admission`
- touched files: `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/contour.md`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/rollback_truth_confirmation.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/restore_payload_confirmation.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/rollback_snapshot.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/routes_after_restore.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/models_after_restore.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/forbidden_drift_check.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/decision_packet.json`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/independent_audit.md`, `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/closeout.md`
- tests run: `python3 -m unittest -q tests.test_external_models.ExternalModelContractTests.test_paths_from_env_uses_isolated_overrides tests.test_cli_external_models.ExternalModelsCliTests.test_routes_add_list_disable_remove_round_trip tests.test_cli_external_models.ExternalModelsCliTests.test_routes_add_from_stdin_and_models_projection`; `python3 -m unittest -q tests.test_ui_shell`
- blocked risks: unbound owner command defaulting to `~/.wild-boar-proxy/external-models`; accidental widening into validate/check; registry/projection contradiction after restore
- next exact command: `WBP_EXTERNAL_MODELS_DIR=/Users/kirillponomarev/.codex-custom-test/external-models python3 -m wild_boar_proxy external-models routes validate --json --route wbp-claude-sonnet-4-6-thinking`

## Verification

- tests: focused env-path, route round-trip, and models projection tests passed; UI shell suite passed
- build: `git diff --check`
- manual: sandbox `routes list --json` and `models --json` moved from `count=0` to `count=1`; sandbox `state.json` and `secrets.env` stayed byte-identical
- live verification: not required for contour success; validate intentionally deferred

## Artifacts

- spec: `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/contour.md`
- packet: `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/decision_packet.json`
- report: `audit_results/sandbox_active_lane_external_models_route_restore_repair_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending
- pushed: pending

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; artifacts record only paths, hashes, counts, command packets, and contour decisions

## Notes

- blockers encountered: the first unbound restore attempt targeted the default external-models root `~/.wild-boar-proxy/external-models` instead of the sandbox root; it was localized, disabled, removed, and the default path was re-proven at `count=0`
- follow-up contour: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`
- resume from here: `SANDBOX_ACTIVE_LANE_EXTERNAL_MODELS_ROUTE_VALIDATE_EVIDENCE_PASS`
