# Custom Codex Dual Lane Model Selection UI R1 Closeout

## Goal

Add a bounded dual-lane model-selection UI surface for Custom Codex that keeps
ChatGPT/Codex-native and API/WBP lanes separate, consumes only server-issued
catalog truth, and does not overclaim session/runtime execution, simultaneous
execution, or role-slot binding.

## Result

- status: `ok`
- final verdict: `CUSTOM_CODEX_DUAL_LANE_MODEL_SELECTION_UI_CLASSIFIED_AND_GUARDED`
- closure state: CLOSED

## Contour Capsule

- goal: wire a bounded dual-lane selector UI and intent-only packet surface on top of the generic registry, keep browser authority bounded, and keep selector truth separate from runtime/session truth
- branch: `codex/external-agent-lab-isolated`
- head: `d6a08d1bb040e362716fab49774e92e118221254`
- touched files: `wild_boar_proxy/codex_model_registry.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `wild_boar_proxy/web_design_ui/styles/overview.css`, `tests/test_web_design_ui.py`, `tests/test_web_design_live_server.py`, `tests/test_custom_codex_dual_lane_model_selection_ui_r1_probe.py`, `tools/custom_codex_dual_lane_model_selection_ui_r1_probe.py`, `audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile wild_boar_proxy/codex_model_registry.py wild_boar_proxy/web_design_live_server.py tests/test_web_design_live_server.py tests/test_web_design_ui.py tests/test_custom_codex_dual_lane_model_selection_ui_r1_probe.py tools/custom_codex_dual_lane_model_selection_ui_r1_probe.py`; `'/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3' -m unittest tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_model_registry_ui_is_dry_run_only tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_accounts_ui_is_selection_not_inference tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_sessions_ui_is_lifecycle_not_inference`; `'/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3' -m unittest tests.test_web_design_live_server.WebDesignCodexCustomModelRegistryEndpointTests tests.test_web_design_live_server.WebDesignCodexCustomDualLaneSelectorEndpointTests`; `'/Users/kirillponomarev/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3' -m unittest tests.test_custom_codex_dual_lane_model_selection_ui_r1_probe tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_model_registry_ui_is_dry_run_only tests.test_web_design_live_server.WebDesignCodexCustomDualLaneSelectorEndpointTests tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_accounts_ui_is_selection_not_inference tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_sessions_ui_is_lifecycle_not_inference`; `python3 tools/custom_codex_dual_lane_model_selection_ui_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28`; `python3 - <<'PY' ... JSON status sweep over audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28 ... PY`; `python3 - <<'PY' ... refined secret-pattern scan over audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28 ... PY`; `git diff --check`
- blocked risks: selector remains intentionally non-runtime; API lane selection is still intent-only until the role-slot/session contour closes; current execution path remains ChatGPT-lane-only in this contour; seed-only visibility policy is display-only and non-selectable; pre-existing dirty worktree entries outside this contour remain quarantined and untouched
- closure state: CLOSED

## Verification

- tests: `8 passed` across `tests.test_custom_codex_dual_lane_model_selection_ui_r1_probe`, `tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_model_registry_ui_is_dry_run_only`, `tests.test_web_design_live_server.WebDesignCodexCustomDualLaneSelectorEndpointTests`, `tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_accounts_ui_is_selection_not_inference`, and `tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_sessions_ui_is_lifecycle_not_inference`, plus the earlier focused UI/server unittest slices for adjacent Custom Codex panels
- build: `py_compile` passed for the touched Python files, the focused live-server/UI tests, and the contour-local probe
- manual: the contour probe wrote `9/9` JSON packets with `status=ok`; the selector packet reports separate `chatgpt_lane`, `api_lane`, and `seed_only_reference` sections; the intent packet reports `selection_intent_only=true`, `session_execution_wired=false`, `simultaneous_execution_proven=false`, `role_slot_binding_proven=false`, and `selected_models_are_server_issued=true`; refined secret-pattern scan over the contour evidence returned zero probable secret hits
- live verification: local server launched at `http://127.0.0.1:8788/`; in-browser verification confirmed that the selector renders separate ChatGPT, API, and historical sections; the boundary note `Selecting both lanes does not prove simultaneous execution semantics.` is visible; forbidden wording (`ready to run`, `active executor`, `attached agent`, `execution ready`, `live now`) is absent from the selector panel text; the selector panel chip renders as `loaded / gate blocked` on load and `intent only` after selector dry-run; browser-triggered selector dry-run returned `status=ok`, `selection_intent_only=true`, `session_execution_wired=false`, `simultaneous_execution_proven=false`, `role_slot_binding_proven=false`, `selected_models_are_server_issued=true`, `current_execution_path_model_id=gpt-5.5`, `current_execution_path_source=operator_reported_configured_model`, and `browser_selected_chatgpt_matches_current_execution_path=false`

## Artifacts

- spec: thread-only contour plan for `CUSTOM_CODEX_DUAL_LANE_MODEL_SELECTION_UI_R1`
- packet: `audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/dual_lane_model_selection_ui_packet.json`
- report: `audit_results/custom_codex_dual_lane_model_selection_ui_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; the contour stores only server-issued model ids, bounded selector metadata, and non-secret evidence packets, and the refined secret-pattern scan over the contour evidence returned zero probable secret hits

## Notes

- blockers encountered: an initial selector-intent packet bug incorrectly derived `selected_models_are_server_issued` from the API lane's `selection_intent_only` flag instead of the API lane's `server_issued` flag; this was fixed before contour evidence was regenerated; an independent audit then surfaced a more serious layer-mixing issue where `current_execution_path_model_id` followed the browser-selected ChatGPT value instead of operator-reported current execution-path truth, plus a too-broad green selector panel state and incomplete forbidden-field coverage in tests; these were fixed by sourcing current execution-path truth from `operator_reported_configured_model`, downgrading the selector panel surface to `loaded`/`intent only` semantics, and extending forbidden-field coverage to `account_id`, `auth_path`, `secret_ref`, and `codex_home`
- resume from here: CLOSED
