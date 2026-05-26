# Owner Assisted Native Custom Routing Smoke After WBP 200 Closeout

## Goal

Prove one narrow live fact after a successful WBP `/v1/responses` preflight: an isolated owner-assisted Codex Custom launch can send a prompt through WBP and receive a WBP-observed 200 response.

## Result

- status: pass_with_claim_limits
- final verdict: OWNER_ASSISTED_NATIVE_CUSTOM_WBP_200_RESPONSE_PROVEN
- closure state: CLOSED

## Contour Capsule

- goal: isolated Codex Custom owner-assisted prompt routed through WBP with trace observer status 200
- branch: codex/external-agent-lab-isolated
- head: 59499c23 before this closeout commit
- touched files: audit_results/owner_assisted_native_custom_routing_smoke_after_wbp_200_2026-05-26/*
- tests run: JSON parse for 23 packet files; secret redaction scan; git diff --check for this evidence dir; python3 -m unittest -q tests.test_operator_surface tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_codex_custom_sessions
- blocked risks: machine UI input proof not claimed; machine-observed UI response text not claimed; full Phase 7 filesystem isolation not claimed because current_codex_drift_guard_diff is blocked_or_noisy; direct api.openai.com egress absence not proven; final E2E not claimed
- closure state: CLOSED

## Verification

- tests: 88 unittest cases passed; JSON packet parse passed; secret redaction audit passed after remediation; git diff --check passed
- build: not applicable; evidence-only contour
- manual: owner-assisted input was required and inferred from the WBP trace; machine UI typing was not used or claimed
- live verification: wbp_200_preflight_packet recorded HTTP 200 completed/OK; native_custom_launch_packet recorded custom_process_observed=true; wbp_trace_packet recorded POST /v1/responses, forwarded_to_wbp=true, upstream_status=200; cleanup_reversibility_packet recorded tmp_root_removed=true

## Artifacts

- spec: thread-only contour plan OWNER_ASSISTED_NATIVE_CUSTOM_ROUTING_SMOKE_AFTER_WBP_200_R2
- packet: audit_results/owner_assisted_native_custom_routing_smoke_after_wbp_200_2026-05-26/
- report: allowed_claims_matrix.json, verification_packet.json, independent_audit_packet.json, secret_redaction_audit.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending at closeout creation
- pushed: pending at closeout creation

## Scope Check

- unrelated work mixed in: no; historical dirty evidence from 2026-05-25 was not staged or modified by this closeout
- private-data risk reviewed: yes; raw config was not recorded; trace packet does not record prompt body or auth header; a redacted placeholder shaped like `sk-*` was remediated to `REDACTED_LOCAL_PROVIDER_TOKEN`, and the post-remediation secret scan is clean

## Notes

- blockers encountered: current Codex protected-surface drift guard was noisy, so full filesystem safety remains unclaimed in this contour; direct egress absence was not proven in this contour; macOS UI internals were not machine-proven and owner-assisted manual input was used
- resume from here: CLOSED
