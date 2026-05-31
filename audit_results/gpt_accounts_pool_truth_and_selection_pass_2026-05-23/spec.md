# GPT_ACCOUNTS_POOL_TRUTH_AND_SELECTION_PASS

Contour capsule: Codex Custom account pool truth and server-side selection surface.

Goal: expose GPT managed account truth for Codex Custom in WBP web UI, prove server-side selection/ranking, and reject browser-supplied account/backend/route fields. This contour is dry-run only and does not claim inference, session manager, prompt execution, or load.

Canonical basis: CANON.md, MASTER_PLAN.md, RUNTIME_CONTRACT.md, STATE_SCHEMA.md, COMMAND_API.md, DELIVERY_RULES.md, README.md, WORKFLOW_OS_V1_2.md, AGENTS.md.

Declared write surfaces:
- wild_boar_proxy/codex_account_selection.py
- wild_boar_proxy/web_design_live_server.py
- wild_boar_proxy/web_design_ui/index.html
- wild_boar_proxy/web_design_ui/scripts/overview.js
- tests/test_codex_account_selection.py
- tests/test_web_design_live_server.py
- tests/test_web_design_ui.py
- audit_results/gpt_accounts_pool_truth_and_selection_pass_2026-05-23/*

Hard boundaries:
- Browser dry-run accepts only server-issued model_id.
- Browser cannot choose account_id, backend_id, route_id, provider, auth, token, secret, path, HOME, or CODEX_HOME.
- Selection proof is not inference proof.
- No account mutation in this contour.
- No prompt/session/load in this contour.
