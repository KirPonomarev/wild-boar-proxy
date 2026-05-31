<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS Closeout

## Goal

Prove the Codex Custom model/API-control layer as server-issued registry plus
OpenAI-compatible shape declaration, without live WBP/API/provider calls.

## Result

- status: passed
- final verdict: `WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_READY`
- next action: `GPT_ACCOUNTS_POOL_TRUTH_AND_SELECTION_PASS`

## Contour Capsule

- goal: server-issued Codex Custom model registry and config-compatible model dry-run with no network or token burn
- branch: codex/external-agent-lab-isolated
- head: f83ec34 before contour commit
- touched files: wild_boar_proxy/codex_model_registry.py; wild_boar_proxy/web_design_ui/scripts/overview.js; tests/test_codex_model_registry.py; tests/test_web_design_live_server.py; tests/test_web_design_ui.py; audit_results/wbp_openai_compat_api_and_model_registry_pass_2026-05-23/*
- tests run: node --check overview.js; project Python targeted 162-test suite; browser fake-server model dry-run proof; git diff --check; closeout resilience; project Python extended 661-test suite
- blocked risks: live API calls, GPT inference, Codex Custom prompt, account mutation, route mutation, and current Codex mutation stayed out of scope
- next exact command: plan `GPT_ACCOUNTS_POOL_TRUTH_AND_SELECTION_PASS`

## Verification

- tests: targeted suite passed with 162 tests; extended CLI/web/Codex suite passed with 661 tests
- build: `node --check wild_boar_proxy/web_design_ui/scripts/overview.js` passed; `git diff --check` passed
- manual: Codex in-app browser clicked model refresh and model dry-run on a fake no-runtime local server
- live verification: not run; live WBP/API/provider calls were intentionally out of scope

## Artifacts

- spec: audit_results/wbp_openai_compat_api_and_model_registry_pass_2026-05-23/spec.md
- packet: audit_results/wbp_openai_compat_api_and_model_registry_pass_2026-05-23/proof.json
- report: audit_results/wbp_openai_compat_api_and_model_registry_pass_2026-05-23/browser_proof.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: contour commit created after this closeout is staged
- pushed: pushed after contour commit

## Scope Check

- unrelated work mixed in: no; unrelated existing untracked files were ignored
- private-data risk reviewed: yes; no auth contents, tokens, provider credentials, account state, or runtime packets captured

## Notes

- blockers encountered: stale test/packet wording implied `/v1/models` was called; fixed to shape declaration and `models_endpoint_called=false`
- follow-up contour: `GPT_ACCOUNTS_POOL_TRUTH_AND_SELECTION_PASS`
- resume from here: CLOSED
