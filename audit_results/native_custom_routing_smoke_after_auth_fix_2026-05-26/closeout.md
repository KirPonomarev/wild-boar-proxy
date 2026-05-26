# Native Custom Routing Smoke After Auth Fix Closeout

## Goal

Run a narrow owner-assisted Codex Custom routing smoke after the auth/config fix, without claiming machine UI proof, full native usability, full provider compatibility, or final E2E.

## Result

- status: blocked with route trace evidence
- final verdict: owner-assisted native Custom request reached the trace observer and was forwarded to WBP, but WBP returned 503 and safety gates block a full pass
- closure state: CLOSED

## Contour Capsule

- goal: prove or block one isolated owner-assisted Codex Custom prompt route through WBP after auth/config fix
- branch: codex/external-agent-lab-isolated
- head: 5977c9a70e7e265b7ae387c103e1062bfad0071f
- touched files: audit_results/native_custom_routing_smoke_after_auth_fix_2026-05-26 evidence, metrics, closeout
- tests run: JSON parse for contour packets; raw secret scan; python3 -m unittest -q tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_operator_surface tests.test_closeout_resilience; git diff --check
- blocked risks: Keychain prompt observed; WBP returned 503; direct egress absence unproven; protected-surface guard changed or crashed under active Codex drift
- closure state: CLOSED

## Verification

- tests: python3 -m unittest -q tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_operator_surface tests.test_closeout_resilience
- build: not applicable; no source code changed
- manual: owner reported cancelling the Codex Key prompt, loading Custom Codex, entering the marker prompt, and seeing Custom Codex think then fail
- live verification: owner-assisted request produced POST /v1/responses, forwarded_to_wbp=true, upstream_status=503

## Artifacts

- spec: thread-only contour plan, not stored in repo
- packet: audit_results/native_custom_routing_smoke_after_auth_fix_2026-05-26/evidence
- report: audit_results/native_custom_routing_smoke_after_auth_fix_2026-05-26/evidence/final_contour_summary.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by repository history for this closeout
- pushed: recorded by repository remote state for this branch

## Scope Check

- unrelated work mixed in: false
- private-data risk reviewed: true; raw secret scan reported zero findings after redaction remediation

## Notes

- blockers encountered: macOS UI input remained owner-assisted, Keychain prompt appeared and was cancelled, WBP returned 503, and protected-surface guard was unstable against live current-Codex drift
- resume from here: CLOSED
