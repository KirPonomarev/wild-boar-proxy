# Managed Bridge Lifecycle R14 Closeout

## Goal

Repair managed bridge lifecycle truth so a broken stable proxy path cannot leave
Codex Custom on a false-green runtime, and ensure owner prompt routing consumes
the live managed endpoint once `status --json` proves it.

## Result

- status: `closed_success`
- final verdict: `MANAGED_BRIDGE_LIFECYCLE_AND_OPERATOR_ENDPOINT_TRUTH_REPAIRED`
- closure state: CLOSED

## Contour Capsule

- goal: repair `PROXY_PATH_BROKEN` managed listener startup and stale `8318`
  Codex Custom prompt routing without UI/model-matrix/profile scope
- branch: `codex/managed-bridge-lifecycle-r14`
- head: `7da1b4e4` before closeout commit
- touched files:
  - `COMMAND_API.md`
  - `wild_boar_proxy/runtime.py`
  - `wild_boar_proxy/operator_surface.py`
  - `tests/test_cli.py`
  - `tests/test_operator_surface.py`
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/*`
- tests run:
  - `python3 -m py_compile wild_boar_proxy/operator_surface.py tests/test_operator_surface.py wild_boar_proxy/runtime.py tests/test_cli.py`
  - `python3 -m pytest tests/test_cli.py::CliTests::test_managed_listener_start_retries_proxy_candidate_after_proxy_path_failure tests/test_cli.py::CliTests::test_managed_listener_start_rolls_back_proxy_candidate_when_reproof_fails tests/test_cli.py::CliTests::test_managed_listener_start_starts_engine_and_writes_managed_truth tests/test_cli.py::CliTests::test_managed_listener_start_kills_process_on_wrong_port_failure -q`
  - `python3 -m pytest tests/test_operator_surface.py -q`
  - `python3 -m pytest tests/test_web_design_live_server.py::WebDesignCodexCustomSessionEndpointTests::test_codex_custom_prompt_endpoint_authorized_path_requires_trace_observer tests/test_web_design_live_server.py::WebDesignCodexCustomSessionEndpointTests::test_codex_custom_mixed_role_slot_live_edit_probe_endpoint_proves_coder_file_mutation tests/test_web_design_live_server.py::WebDesignCodexCustomSessionEndpointTests::test_codex_custom_same_session_prompt_can_exercise_chatgpt_and_api_lanes -q`
  - `git diff --check`
- blocked risks:
  - `gpt-5.3-codex` live prompt returned bounded `auth_unavailable`; this was
    packeted as model/auth availability, not as `8318/10808` lifecycle failure
  - process network observation still reports non-local Codex process peers, so
    this closeout does not claim direct-egress absence
- closure state: CLOSED

## Verification

- tests:
  - managed listener retry and rollback regressions passed
  - full operator surface suite passed (`55 passed, 3 subtests passed`)
  - targeted web Codex Custom session tests passed (`3 passed`)
- build:
  - py_compile passed
  - `git diff --check` passed
- manual:
  - pre-fix managed startup retried `18080` and failed honestly with rollback
  - bounded retry using `http://127.0.0.1:12334` started managed listener and
    wrote managed truth only after `/models` and `/responses` passed
  - `status --json` and `healthcheck --json` both reported
    `effective_mode=managed` and `endpoint=http://127.0.0.1:8320/v1`
  - operator prompt routing adopted `status --json` endpoint instead of stale
    config default `http://127.0.0.1:8318/v1`
- live verification:
  - `gpt-5.5` Codex Custom prompt returned `OK` with
    `trace_observer_packet.forwarded_endpoint=http://127.0.0.1:8320/v1`
  - mixed ChatGPT+API live-edit smoke returned
    `CHATGPT_PLUS_API_ROLE_SLOT_LIVE_EDIT_PROVEN_WITH_LIMITS`
  - coding slot was `wbp-deepseek-v4-pro-max`, changed only the expected proof
    file under `.tmp`, and `fallback_used=false`

## Artifacts

- spec:
  - thread-only contour plan, not stored in repo
- packet:
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/health_after_operator_patch.json`
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/status_after_operator_patch.json`
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/gpt53_auth_block_prompt_packet.json`
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/gpt55_managed_endpoint_prompt_packet.json`
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/mixed_role_slot_live_edit_probe_packet.json`
- report:
  - `audit_results/managed_bridge_lifecycle_r14_2026-06-01/closeout.md`

## Git

- branch: `codex/managed-bridge-lifecycle-r14`
- commit: pending at closeout authoring time
- pushed: pending at closeout authoring time

## Scope Check

- unrelated work mixed in: `no`
- private-data risk reviewed: `yes`; committed packets are bounded runtime
  packets and do not expose raw secrets or prompt bodies

## Notes

- blockers encountered:
  - shallow reachable proxy candidate `18080` was not sufficient for live
    `/responses`; retry failure now stays red and rolls back
  - stale operator endpoint `8318` caused Codex Custom prompt forwarding to hit
    old stable proxy truth even after managed listener was healthy
  - `gpt-5.3-codex` model/auth availability remained red while `gpt-5.5` and
    the mixed-role slot smoke proved the repaired managed endpoint path
- resume from here: CLOSED
