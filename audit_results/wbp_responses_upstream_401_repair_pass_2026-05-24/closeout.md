# WBP_RESPONSES_UPSTREAM_401_REPAIR_PASS Closeout

## Contour Capsule

- Program: `EXECUTION_CORE_FULL_SYSTEM_TO_ISOLATED_CODEX_APP_PASS`
- Contour: `WBP_RESPONSES_UPSTREAM_401_REPAIR_PASS`
- Status: `passed_guard_repair_and_classified_blocker`
- Branch: `codex/external-agent-lab-isolated`
- goal: classify and narrowly repair the WBP `/v1/responses` upstream 401 boundary without rerunning Codex Custom live prompt.
- head: `9129edb` before this contour; final commit hash is recorded in the operator final note.
- touched files: `wild_boar_proxy/operator_surface.py`; `tests/test_operator_surface.py`; `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/*`
- tests run: `node --check`; operator-surface 9-test gate; 114-test targeted gate; JSON validation; redaction scan; independent audit; `git diff --check`.
- blocked risks: `/v1/responses` live success is still not proven; root cause remains classified as wire API compatibility or GPT account auth stale/invalid; no second live prompt was run.
- next exact command: start either `WBP_RESPONSES_WIRE_API_COMPAT_REPAIR_PASS` or `GPT_ACCOUNT_AUTH_REPAIR_OR_OPERATOR_REAUTH_PASS` before rerunning `CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_RERUN_PASS`.

## Result

The previous 401 was replayed and classified. Local WBP token rejection is unlikely: runtime token and operator token shape matched, `/models` returned 200 with the same token, and an invalid token returned 401. The remaining owner class is downstream `/responses`: wire API compatibility or GPT account/upstream auth stale/invalid.

A repo-owned false-green guard was repaired: `WbpTraceObserver` no longer reports `machine_error_code = OK` for upstream 4xx. It now reports `TRACE_UPSTREAM_HTTP_<status>`, covered by tests for 401, 403, and 429.

No Codex Custom prompt was rerun in this contour.

## Resume From Here

resume from here: choose the next branch. For wire shape, run `WBP_RESPONSES_WIRE_API_COMPAT_REPAIR_PASS`. For account auth, run `GPT_ACCOUNT_AUTH_REPAIR_OR_OPERATOR_REAUTH_PASS`. Only after one of those passes should `CODEX_CUSTOM_SINGLE_TRACED_PROMPT_LIVE_RERUN_PASS` run a new single live prompt.

## Artifacts

- evidence replay: `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/evidence_replay.json`
- token shape: `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/token_shape_check.json`
- models vs responses: `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/models_vs_responses_probe.json`
- classification: `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/auth_boundary_classification.json`
- validation: `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/validation.json`
- independent audit: `audit_results/wbp_responses_upstream_401_repair_pass_2026-05-24/independent_audit.json`

## Git

- Commit hash: recorded in final operator note after commit.
- Push status: recorded in final operator note after remote push completes.
