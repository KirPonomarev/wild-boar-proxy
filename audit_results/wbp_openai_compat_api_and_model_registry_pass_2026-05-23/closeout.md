# WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS Closeout

## Contour Capsule

- goal: Prove readonly WBP OpenAI-compatible model registry and server-issued model dry-run for Codex Custom without inference or token burn.
- branch: codex/external-agent-lab-isolated
- head: c7619f3 before contour commit; final commit is recorded in git history after this closeout is committed.
- touched files: wild_boar_proxy/codex_model_registry.py, wild_boar_proxy/web_design_live_server.py, wild_boar_proxy/web_design_ui/index.html, wild_boar_proxy/web_design_ui/scripts/overview.js, tests/test_codex_model_registry.py, tests/test_web_design_live_server.py, tests/test_web_design_ui.py, audit_results/wbp_openai_compat_api_and_model_registry_pass_2026-05-23/*
- tests run: node --check overview.js; unittest tests.test_codex_model_registry tests.test_codex_launch_modes tests.test_operator_surface tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter -q; git diff --check
- blocked risks: GPT account inference, API/provider inference, custom session manager, and claim-gate repair are intentionally not claimed in this contour.
- next exact command: /Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest tests.test_cli tests.test_cli_external_models tests.test_external_models tests.test_web_design_live_server tests.test_web_design_ui tests.test_web_design_command_adapter tests.test_codex_model_registry -q
- resume from here: GPT_ACCOUNTS_POOL_TRUTH_AND_SELECTION_PASS

## Outcome

Implemented a bounded Codex Custom model registry and UI panel. Browser can refresh the server-issued model list and run a model selection dry-run, but the packet keeps the state degraded while claim gate is blocked.

The dry-run packet proves the bounded static dry-run path:

- `model_server_issued=true`
- `codex_config_compatible=true`
- `route_or_backend_exposed=false`
- `inference_called=false`
- `provider_called=false`
- `responses_called=false`
- `chat_completions_called=false`
- `token_burn=0`
- `negative_claim_basis=dry_run_static_code_path_no_inference_adapter`
- `independent_runtime_meter_attached=false`

Auditor note: these negative claims are code-path guarded dry-run claims, not independent runtime token-meter claims. The next inference contour must add runtime metering before claiming real token accounting.

## Evidence

- `model_registry_packet.json`
- `api_compat_packet.json`
- `model_dry_run_proof.json`
- `evidence/forbidden_browser_fields_rejection.json`
- `evidence/browser_custom_models.png`
- `redaction_audit.json`
- `independent_audit.json`

## Non-Claims

This closeout does not claim that GPT accounts, external API routes, `/v1/responses`, `/v1/chat/completions`, or Codex Custom sessions work end-to-end.
