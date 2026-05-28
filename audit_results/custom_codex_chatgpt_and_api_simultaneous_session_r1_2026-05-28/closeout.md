# Custom Codex ChatGPT And API Simultaneous Session R1 Closeout

## Goal

Prove that one Custom Codex session identity can call both the ChatGPT/Codex
lane and one API/WBP route lane without silent source collapse, browser
authority widening, or false claims of concurrent execution, provider-family
compatibility, or completed orchestration semantics.

## Result

- status: `ok`
- final verdict: `CUSTOM_CODEX_CHATGPT_AND_API_SIMULTANEOUS_SESSION_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: classify same-session dual-lane runtime callability, slot-dispatch separation, provenance truth, and fallback boundaries without treating same-session observations as concurrent execution proof
- branch: `codex/external-agent-lab-isolated`
- head: `f3a302307af8ece9f29f302e4c8139d9d3b83cd6`
- touched files: `wild_boar_proxy/codex_custom_sessions.py`, `tests/test_codex_custom_sessions.py`, `tests/test_web_design_live_server.py`, `tools/custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py`, `tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py`, `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-28/*.json`, `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-28/closeout.md`
- tests run: `python3 -m py_compile wild_boar_proxy/codex_custom_sessions.py tests/test_codex_custom_sessions.py tests/test_web_design_live_server.py tools/custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py`; `python3 -m pytest tests/test_codex_custom_sessions.py tests/test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py -q`; `python3 - <<'PY' ... pytest.main(['-q','tests/test_web_design_live_server.py','-k','codex_custom_prompt_endpoint_authorized_path_requires_trace_observer or codex_custom_launch_and_prompt_support_route_backed_external_model or codex_custom_same_session_prompt_can_exercise_chatgpt_and_api_lanes or codex_custom_session_create_rejects_free_form_model_and_backend']) ... PY`; `python3 tools/custom_codex_chatgpt_and_api_simultaneous_session_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-28`; `python3 tools/check_closeout_resilience.py audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-28/closeout.md`; `git diff --check`
- blocked risks: concurrent execution was not observed here; only the primary and coding-agent slots are runtime-proven here; provider-family compatibility, tools/streaming semantics, and orchestration policy remain open; contour evidence is packet-backed through focused manager and HTTP-path probes rather than a broad live provider matrix
- closure state: CLOSED

## Verification

- tests: `25 passed` in `tests.test_codex_custom_sessions` plus `tests.test_custom_codex_chatgpt_and_api_simultaneous_session_r1_probe`; `4 passed` in the focused `tests.test_web_design_live_server` HTTP slice under a local `tkinter` stub
- build: `py_compile` passed for the touched session manager, focused tests, and contour-local probe
- manual: the contour-local probe wrote `10/10` JSON artifacts with parseable packet bodies; `simultaneous_session_runtime_packet.json` shows one session id with both lane calls observed, `dual_lane_source_provenance_packet.json` keeps backend and route provenance separated and now includes lane-specific configured providers, `slot_dispatch_separation_packet.json` keeps slot binding distinct from observed dispatch, and `fallback_and_substitution_boundary_packet.json` keeps fallback/substitution false while proving the API lane stayed on `external_route` instead of collapsing into `cliproxy`; a final read-only agent audit reported `no material issues found; residual limits remain correctly classified`
- live verification: the focused live-server slice exercised the HTTP session endpoints with one session containing a ChatGPT primary slot and an API coding-agent slot, then observed separate prompt calls for both lanes without browser-authored backend or route authority

## Artifacts

- spec: thread-only contour plan for `CUSTOM_CODEX_CHATGPT_AND_API_SIMULTANEOUS_SESSION_R1`
- packet: `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-28/simultaneous_session_runtime_packet.json`
- report: `audit_results/custom_codex_chatgpt_and_api_simultaneous_session_r1_2026-05-28/independent_audit_packet.json`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: no; unrelated dirty tracked files and historical audit artifacts outside this contour were left untouched
- private-data risk reviewed: yes; packets keep backend/account/route truth redacted through digests and booleans, raw prompts remain redacted or omitted, and no browser-controlled auth/path/home fields were admitted

## Notes

- blockers encountered: the first real blocker was architectural: the partially applied patch had already introduced per-slot provenance fields, but runtime dispatch still collapsed to the primary slot, so the contour could not honestly prove same-session dual-lane behavior until prompt admission and prompt execution became slot-aware. The second blocker was semantic: once one live prompt completed, the session status became non-runnable, which made a second lane call in the same session impossible; the runnable status set was widened only enough to permit another bounded prompt while still keeping cleaned or unrevalidated sessions blocked. The third blocker was false fallback risk: an invalid `slot_id` would have silently fallen back to the primary slot under the old helper, so the helper now rejects unknown slot ids with `SLOT_ID_NOT_SERVER_ISSUED` instead of collapsing lane truth. A later independent read-only audit found two additional material issues and forced a second tightening pass: route-backed slots were still treating `cliproxy` as an admissible full-success runtime provider, and blocked-after-response packets were still being persisted as completed inference in session state. Those two failures are now covered by focused tests, the route-backed runtime path now requires `external_route` or `wbp`, and blocked-after-response persistence now writes `prompt_blocked_after_response_e2e` with `inference_proven=false` in persisted session truth. The same audit also caught one evidence-hygiene issue: rerunning the probe in the same evidence directory had left older `probe_session_root` sessions beside the newest run, so the probe now clears its owned session root before writing fresh artifacts. Existing route-backed tests also exposed an important contract shift: top-level session provenance is no longer enough to change runtime source truth by itself, because the runtime path now follows per-slot provenance. That migration pressure was absorbed in focused tests rather than by weakening the slot/runtime boundary.
- resume from here: CLOSED
