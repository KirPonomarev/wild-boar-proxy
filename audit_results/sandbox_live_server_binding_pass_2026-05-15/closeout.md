# SANDBOX_LIVE_SERVER_BINDING_PASS Closeout

## Goal

Prove that the command runner and live read-only server bind to `/Users/kirillponomarev/.codex-custom-sandbox-20260515` rather than to working/live roots or the quarantined old sandbox root.

## Result

- status: `completed`
- final verdict: `GO_TO_ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
- next action: open the onboarding contour against the preserved fresh sandbox root

## Contour Capsule

- goal: bind the command runner and live read-only server to the declared fresh sandbox root after minimal bootstrap
- branch: `codex/external-agent-lab-isolated`
- head: `877925a Define sandbox boundary and rollback plan`
- touched files:
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/*`
- tests run:
  - `python3 -m unittest -q tests.test_external_models.ExternalModelContractTests.test_paths_from_env_uses_isolated_overrides tests.test_cli.CliTests.test_installer_init_creates_baseline_companion_layout tests.test_web_design_command_adapter tests.test_web_design_live_server`
  - `git diff --check`
  - `python3 tools/check_closeout_resilience.py audit_results/sandbox_live_server_binding_pass_2026-05-15/closeout.md`
  - `python3 tools/check_closeout_resilience.py --staged-only`
- blocked risks:
  - sandbox-local `auth.json` is still absent; this contour proves binding, not onboarding readiness or healthy runtime
- next exact command: `python3 -m wild_boar_proxy accounts onboard --json`

## Verification

- tests:
  - installer bootstrap wrote only inside `/Users/kirillponomarev/.codex-custom-sandbox-20260515`
  - direct `status --json` failed on missing `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`, proving sandbox source ownership rather than live auth fallback
  - `mode get --json` returned `stable/stable` from sandbox-local files
  - `accounts list --json` returned an empty sandbox registry rather than the live 25-account baseline
  - direct external-models packets referenced only `/Users/kirillponomarev/.codex-custom-sandbox-20260515/external-models/*`
- build:
  - `git diff --check`
- manual:
  - `ps eww` on the live server listener showed all `WBP_*` env surfaces bound to `/Users/kirillponomarev/.codex-custom-sandbox-20260515`
  - `/api/live-readonly` returned honest `integration_failure` with the same sandbox `auth.json` path
  - `/api/accounts-readonly` returned empty sandbox registry truth
  - `/api/api-connections-readonly` returned sandbox-local empty external-models truth
  - `/api/actions` stayed in `live_readonly` with only readonly support actions available
- live verification:
  - server listened on `127.0.0.1:8791`
  - server process was terminated after capture
  - sandbox root was preserved explicitly for the next contour

## Artifacts

- spec:
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/contour.md`
- packet:
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/sandbox_env_binding.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/bootstrap_packet.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/status_packet.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/mode_packet.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/accounts_packet.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/external_models_support_packets.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/live_server_binding_packet.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/changed_files_scope.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/persistence_or_teardown_decision.json`
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/decision_packet.json`
- report:
  - `audit_results/sandbox_live_server_binding_pass_2026-05-15/independent_audit.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `pending`
- pushed: `pending`

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes; no live auth contents or raw logs were copied into artifacts`

## Notes

- blockers encountered:
  - none blocking the binding verdict; the only carried-forward caution is missing sandbox auth, which belongs to the next onboarding contour rather than to binding proof
- follow-up contour:
  - `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`
- resume from here: `preserve /Users/kirillponomarev/.codex-custom-sandbox-20260515 and open ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS using the same env binding`
