# Dual Slot Session Schema And Role Binding R1 Closeout

## Goal

Replace the single-model Custom Codex session truth with a bounded multi-slot
session schema that stores role-slot bindings as packet-backed session state,
keeps selector intent separate from session truth, and does not overclaim
runtime dispatch, simultaneous execution, or API-lane runtime compatibility.

## Result

- status: `ok`
- final verdict: `DUAL_SLOT_SESSION_SCHEMA_AND_ROLE_BINDING_CLASSIFIED_AND_GUARDED`
- closure state: CLOSED

## Contour Capsule

- goal: upgrade Custom Codex session truth from one active `model_id` to bounded role-slot state, add safe legacy migration, add explicit revalidation boundaries on reload, and keep selector/session/runtime truth separated end-to-end
- branch: `codex/external-agent-lab-isolated`
- head: `8d551c72ab2ea49fcf7138e81a3ab3d857bed406`
- touched files: `wild_boar_proxy/codex_custom_sessions.py`, `wild_boar_proxy/web_design_live_server.py`, `wild_boar_proxy/web_design_ui/index.html`, `wild_boar_proxy/web_design_ui/scripts/overview.js`, `tests/test_codex_custom_sessions.py`, `tests/test_web_design_live_server.py`, `tests/test_web_design_ui.py`, `tools/dual_slot_session_schema_and_role_binding_r1_probe.py`, `tests/test_dual_slot_session_schema_and_role_binding_r1_probe.py`, `audit_results/dual_slot_session_schema_and_role_binding_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile wild_boar_proxy/codex_custom_sessions.py wild_boar_proxy/web_design_live_server.py tests/test_codex_custom_sessions.py tests/test_web_design_live_server.py tools/dual_slot_session_schema_and_role_binding_r1_probe.py tests/test_dual_slot_session_schema_and_role_binding_r1_probe.py`; `python3 -m unittest tests.test_codex_custom_sessions tests.test_dual_slot_session_schema_and_role_binding_r1_probe`; `python3 - <<'PY' ... tkinter stub + unittest tests.test_web_design_live_server.WebDesignCodexCustomSessionEndpointTests ... PY`; `python3 - <<'PY' ... PIL stub + unittest tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_accounts_ui_is_selection_not_inference tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_sessions_ui_is_lifecycle_not_inference ... PY`; `python3 tools/dual_slot_session_schema_and_role_binding_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/dual_slot_session_schema_and_role_binding_r1_2026-05-28`; `python3 - <<'PY' ... stubbed local live server at http://127.0.0.1:8788, manual HTTP create/get smoke and forbidden-field boundary capture ... PY`; `git diff --check`
- blocked risks: simultaneous ChatGPT+API execution semantics remain unresolved here; runtime dispatch truth remains unresolved here; non-primary slot compatibility/uniqueness policy remains intentionally broad and is classified as open risk rather than proof; full owner-visible thread-history relaunch continuity remains outside this contour; reloaded sessions now require slot-catalog revalidation before prompt admission
- closure state: CLOSED

## Verification

- tests: `23 passed` across `tests.test_codex_custom_sessions` and `tests.test_dual_slot_session_schema_and_role_binding_r1_probe`; `16 passed` across `tests.test_web_design_live_server.WebDesignCodexCustomSessionEndpointTests` under a local `tkinter` stub; `2 passed` across `tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_accounts_ui_is_selection_not_inference` and `tests.test_web_design_ui.WebDesignUiTests.test_codex_custom_sessions_ui_is_lifecycle_not_inference` under a minimal `PIL` stub
- build: `py_compile` passed for the touched Python modules, focused tests, and contour-local probe
- manual: the contour probe wrote `9/9` JSON packets with `status=ok`; `manual_http_smoke_packet.json` captured a live local `POST /api/codex/custom/sessions` + `GET /api/codex/custom/sessions/{id}` flow with `session_schema_version=2`, `current_execution_slot_id=primary_model_slot`, `role_slot_binding_count=1`, and `slot_catalog_revalidated=true`; `manual_http_boundary_packet.json` captured `FORBIDDEN_BROWSER_FIELD` with `account_id` and `provider` rejected on the live local HTTP surface
- live verification: local live server was launched with a bounded `tkinter` stub at `http://127.0.0.1:8788/`; direct HTTP verification confirmed that the session endpoint accepts bounded slot-backed primary model creation, emits role-slot session packets, and rejects forbidden browser authority fields; no claim is made here about browser-rendered simultaneous execution behavior or runtime dispatch proof

## Artifacts

- spec: thread-only contour plan for `DUAL_SLOT_SESSION_SCHEMA_AND_ROLE_BINDING_R1`
- packet: `audit_results/dual_slot_session_schema_and_role_binding_r1_2026-05-28/dual_slot_session_schema_packet.json`
- report: `audit_results/dual_slot_session_schema_and_role_binding_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; the contour stores only server-issued model ids, digests, bounded session packets, and local audit packets, and the manual HTTP boundary smoke confirmed rejection of raw `account_id` and `provider` browser fields

## Notes

- blockers encountered: the first regression was contract-level: new slot payload keys were still rejected as forbidden browser fields because the create-path filter was still wired to the older single-model dry-run allowlist; this was fixed by adding a contour-specific session-create boundary filter. The next meaningful issue came from live-server integration after session reload support landed: tests began inheriting stale temp-root sessions, so the live-server session endpoint tests were isolated behind a per-test `CodexCustomSessionManager` temp root rather than weakening the loader. The independent read-only audit then found a real false-green risk in `_load_session_state()`: persisted slot bindings could come back as promptable truth after reload. This was fixed by preserving the stored slot state while adding `slot_catalog_revalidated=false` on reload and blocking prompt admission with `SLOT_CATALOG_REVALIDATION_REQUIRED` until later revalidation work exists. The same audit also found UI semantics drift where loaded session rows were wrapped in synthetic `ok` packet truth and `selection_proven` was being treated like dry-run proof; these were fixed by rendering loaded list entries as `loaded` state and requiring actual `selection_dry_run_proven` for dry-run-ready wording. A broader policy question remains intentionally open: all five declared role-slot fields are accepted and now test-covered as explicit contract, but slot/lane compatibility and uniqueness policy are not closed in this contour and remain classified in the gap matrix instead of being silently overclaimed.
- resume from here: CLOSED
