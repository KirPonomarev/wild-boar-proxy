# WBP Codex Custom Native Routing Proof Closeout

## Goal

Prove that one bounded Codex Custom native prompt routes through WBP/CLIProxyAPI and not directly to api.openai.com.

## Result

- status: closed_success
- final verdict: NATIVE_CUSTOM_ROUTING_PROVEN

## Contour Capsule

- goal: prove one bounded Custom native prompt routes through WBP, not directly to OpenAI
- branch: codex/external-agent-lab-isolated
- head: edb67c76
- touched files: audit_results/wbp_codex_custom_native_routing_proof_pass_2026-05-25/*
- tests run: live routing attempt via codex exec; codex error URL inspection; negative direct-egress check; closeout resilience check
- blocked risks: auth format on WBP side needs correction for full prompt-response, but routing path is proven
- closure state: CLOSED
- resume from here: CLOSED

## Verification

- tests: live codex exec prompt; URL inspection; negative egress check
- build: not applicable
- manual: Codex.app closed before proof; no protected surfaces touched
- live verification: request reached http://127.0.0.1:8318/v1/responses (WBP), not api.openai.com

## Artifacts

- spec: `audit_results/wbp_codex_custom_native_routing_proof_pass_2026-05-25/spec.md`
- packet: `audit_results/wbp_codex_custom_native_routing_proof_pass_2026-05-25/evidence/native_routing_summary.json`
- report: `audit_results/wbp_codex_custom_native_routing_proof_pass_2026-05-25/metrics.json`, `audit_results/wbp_codex_custom_native_routing_proof_pass_2026-05-25/independent_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: pending
- pushed: no

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; no secrets exposed

## Notes

- blockers encountered: WBP auth format mismatch prevented full prompt-response, but routing path through WBP is proven
- resume from here: CLOSED
