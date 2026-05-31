# ROLE_SLOT_PROVIDER_MODEL_IDENTITY_PERSISTENCE_ACROSS_RELAUNCH_R1 Closeout

## Goal

Reprove that saved role-slot bindings survive relaunch with exact provider/model
identity at the admitted proof layer, then show post-relaunch runtime dispatch
and provenance for both lanes without hidden fallback.

## Result

- status: closed honestly with limits
- final verdict: `ROLE_SLOT_PROVIDER_MODEL_IDENTITY_PERSISTENCE_REPROVED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: prove saved slot binding reload, slot-catalog revalidation, post-relaunch runtime identity, and no-hidden-fallback boundary without mixing in thread-history or provider-family claims
- branch: `codex/external-agent-lab-isolated`
- head: `5dec5eba`
- touched files:
  - `wild_boar_proxy/codex_custom_sessions.py`
  - `wild_boar_proxy/web_design_live_server.py`
  - `tools/role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py`
  - `tests/test_codex_custom_sessions.py`
  - `tests/test_role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py`
  - `tests/test_web_design_live_server.py`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_saved_binding_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_relaunch_identity_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_provider_model_persistence_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_post_relaunch_runtime_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_post_relaunch_provenance_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_hidden_fallback_boundary_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/independent_audit_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/closeout.md`
- tests run:
  - `python3 -m pytest -q tests/test_codex_custom_sessions.py -k "reloaded_multi_slot_session or runtime_model_mismatch or provider_collapses_to_cliproxy"`
  - `python3 -m pytest -q tests/test_role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py`
  - `python3 -m pytest -q tests/test_codex_custom_sessions.py tests/test_role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py tests/test_persistent_profile_and_thread_history_r1_probe.py tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py tests/test_final_dual_lane_agent_workflow_e2e_r1_probe.py`
  - `python3 -m py_compile wild_boar_proxy/codex_custom_sessions.py wild_boar_proxy/web_design_live_server.py tools/role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py tests/test_role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py`
  - `python3 tools/role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29`
  - JSON parse sweep over `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/*.json`
- blocked risks:
  - proof is bounded to the server-owned session/reload/runtime packet path and does not separately prove native user-visible relaunch UI recovery for slot dispatch
  - same-provider account continuity is only reproved inside deterministic command packets here and does not upgrade broader live account continuity claims
  - no provider-family compatibility, concurrency, thread-history source, or acceleration claim is upgraded by this contour
  - the optional web-server route was compile-checked but its focused test could not be collected in this environment because `_tkinter` is unavailable
- closure state: CLOSED

## Verification

- tests:
  - `35 passed` across `tests/test_codex_custom_sessions.py`, `tests/test_role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py`, `tests/test_persistent_profile_and_thread_history_r1_probe.py`, `tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py`, and `tests/test_final_dual_lane_agent_workflow_e2e_r1_probe.py`
  - `4 passed` in the focused `test_codex_custom_sessions.py` reload/runtime mismatch/provider collapse slice
  - `2 passed` in `tests/test_role_slot_provider_model_identity_persistence_across_relaunch_r1_probe.py`
- build:
  - `py_compile` passed for `codex_custom_sessions.py`, `web_design_live_server.py`, and the new probe/test file
- manual:
  - `role_slot_saved_binding_packet.json` proves the session root lives under the persistent profile scope and stores both saved slot bindings
  - `role_slot_relaunch_identity_packet.json` proves same profile identity and same session id after reload while keeping `slot_catalog_revalidated_after_reload = false`
  - `role_slot_provider_model_persistence_packet.json` proves explicit revalidation before runtime and keeps runtime truth separate
  - `role_slot_post_relaunch_runtime_packet.json` proves both lanes dispatch with exact runtime model identity after revalidation
  - `role_slot_post_relaunch_provenance_packet.json` proves `backend_proven` for primary and `route_proven` for coding lane after relaunch
  - `role_slot_hidden_fallback_boundary_packet.json` proves no fallback attempt and no observed provider/model remap in the bounded run
- live verification:
  - no live owner prompt or native relaunch interaction was required in this contour
  - runtime proof here is bounded to the server-owned session manager plus packetized prompt runner

## Artifacts

- spec: thread-only contour plan, not stored in repo by policy
- packet:
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_saved_binding_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_relaunch_identity_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_provider_model_persistence_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_post_relaunch_runtime_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_post_relaunch_provenance_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/role_slot_hidden_fallback_boundary_packet.json`
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/independent_audit_packet.json`
- report:
  - `audit_results/role_slot_provider_model_identity_persistence_across_relaunch_r1_2026-05-29/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout write time
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no; pre-existing dirty files outside this contour were left untouched
- private-data risk reviewed: yes; no raw prompt bodies, raw backend ids, or raw secret values were written into the new contour evidence

## Notes

- blockers encountered:
  - persisted slot ids already survived reload, but runtime remained blocked until an explicit revalidation path existed
  - the most important fix was not packet cosmetics; it was adding a real reload-time revalidation surface before prompt admission
  - `test_web_design_live_server.py` focused collection was blocked in this environment by missing `_tkinter`, so that route change was verified by compile plus the manager/runtime packet path instead
- resume from here: CLOSED
