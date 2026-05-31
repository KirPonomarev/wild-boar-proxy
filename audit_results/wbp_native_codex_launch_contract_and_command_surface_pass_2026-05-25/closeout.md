# WBP Native Codex Launch Contract And Command Surface Pass Closeout

## Goal

Create a contract-only native Codex launch boundary that separates Codex Custom native app launch from Original Codex via WBP, and rejects process-only, workbench-only, and protected-baseline-only false-green substitutions.

## Result

- status: completed
- final verdict: native launch contract ready; live native app launch remains outside this contour
- closure state: CLOSED

## Contour Capsule

- goal: define and test native Codex launch contract and command/packet schemas without live launch, runtime mutation, or UI wiring
- branch: codex/external-agent-lab-isolated
- head: 1bb37d20
- touched files: NATIVE_LAUNCH_SPEC.md, native_launch_contract.json, native_launch_command_schema.json, native_launch_packet_schema.json, wild_boar_proxy/native_launch_contract.py, tests/test_native_launch_contract.py, audit_results/wbp_native_codex_launch_contract_and_command_surface_pass_2026-05-25/evidence/contract_verification_packet.json, audit_results/wbp_native_codex_launch_contract_and_command_surface_pass_2026-05-25/evidence/independent_audit_packet.json, audit_results/wbp_native_codex_launch_contract_and_command_surface_pass_2026-05-25/closeout.md
- tests run: python3 -m unittest tests.test_native_launch_contract tests.test_codex_launch_modes tests.test_repo_hygiene tests.test_closeout_resilience; python3 -m json.tool native_launch_contract.json native_launch_command_schema.json native_launch_packet_schema.json; python3 -m py_compile wild_boar_proxy/native_launch_contract.py; git diff --check
- blocked risks: live native Codex app launch not attempted by scope; native routing proof not claimed; account/API onboarding not claimed
- closure state: CLOSED

## Verification

- tests: 39 unittest tests passed
- build: py_compile passed for wild_boar_proxy/native_launch_contract.py
- manual: changed files inspected for live launch, runtime mutation, UI mutation, and roadmap leakage
- live verification: not run because this contour is contract-only and forbids live Codex.app launch

## Artifacts

- spec: NATIVE_LAUNCH_SPEC.md
- packet: audit_results/wbp_native_codex_launch_contract_and_command_surface_pass_2026-05-25/evidence/contract_verification_packet.json
- report: audit_results/wbp_native_codex_launch_contract_and_command_surface_pass_2026-05-25/evidence/independent_audit_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: recorded by the repository commit that adds this contract pass
- pushed: recorded by repository history after this contract pass is pushed

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes; no secret values were added and no runtime packets were generated

## Notes

- blockers encountered: pytest is not installed in available Python runtimes, so the passing local verification uses unittest
- resume from here: CLOSED
