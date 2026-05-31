<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Setup Import Server-Owned Discovery Source Foundation Pass Closeout

## Goal

Expose one bounded server-owned discovery source for `setup_discovery` so the
web setup/import branch can emit minimal discovery truth without browser paths,
selection persistence, target/session materialization, or import execution.

## Result

- status: completed
- final verdict: `SETUP_IMPORT_SERVER_OWNED_DISCOVERY_SOURCE_FOUNDATION_PASS`
- next action: reopen `SETUP_IMPORT_SERVER_OWNED_TARGET_SESSION_FOUNDATION_PASS`

## Contour Capsule

- goal: open `setup_discovery` as a zero-write local packet lane backed only by the current server-owned runtime layout, while keeping `legacy_import` parked and metadata-only
- branch: `codex/external-agent-lab-isolated`
- head: `4fdab4939c1a063ae6705ab445c0d969962a2a1e`
- touched files: `wild_boar_proxy/web_design_live_server.py`, `tests/test_web_design_live_server.py`, `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/spec.md`, `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/evidence/action_packets.json`, `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/evidence/verification_summary.json`, `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/evidence/independent_audit_report.json`, `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/closeout.md`
- tests run: `tests.test_web_design_live_server` `103 tests OK`; `tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_screens_are_inert_skeletons` `OK`; `tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_routes_are_static_only` `OK`; `py_compile` OK; `git diff --check` OK; independent read-only audit `PASS`
- blocked risks: target/session token materialization, explicit confirm, cancel semantics, collision handling, and final import execution remain intentionally out of scope
- next exact command: `python3 tools/check_closeout_resilience.py audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/closeout.md`

## Verification

- tests:
  - `python3 -m unittest tests.test_web_design_live_server` via inline launcher with an ephemeral `tkinter` stub
  - `python3 -m unittest tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_screens_are_inert_skeletons tests.test_web_design_ui.WebDesignUiTests.test_setup_select_import_routes_are_static_only` via inline launcher with an ephemeral `PIL.Image` stub
- build:
  - `python3 -m py_compile wild_boar_proxy/web_design_live_server.py tests/test_web_design_live_server.py`
  - `git diff --check`
- manual:
  - not run
- live verification:
  - `setup_discovery` returns factual `none`, `discovered`, and `blocked` packets with `changed_files=[]`
  - `legacy_import` remains unavailable in action metadata

## Artifacts

- spec: `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/spec.md`
- packet: `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/evidence/action_packets.json`
- report: `audit_results/setup_import_server_owned_discovery_source_foundation_pass_2026-05-25/evidence/independent_audit_report.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: local contour work not yet committed at closeout authoring time
- pushed: not yet at closeout authoring time

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; packets expose only server-owned discovery state and marker counts, not raw filesystem paths

## Notes

- blockers encountered: local Python lacks `_tkinter` and Pillow, so verification used ephemeral launch-time stubs rather than repo edits
- follow-up contour: `SETUP_IMPORT_SERVER_OWNED_TARGET_SESSION_FOUNDATION_PASS`
- resume from here: `SETUP_IMPORT_SERVER_OWNED_TARGET_SESSION_FOUNDATION_PASS`
