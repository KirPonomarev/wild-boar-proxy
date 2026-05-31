# Original Codex Via WBP Owner-Authorized Live Apply R5 Closeout

## Goal

Execute the owner-authorized Original Codex temporary WBP route contour against `/Users/kirillponomarev/.codex/config.toml`, prove route through WBP with packet truth, and restore the original config byte-for-byte.

## Result

- status: ORIGINAL_CODEX_VIA_WBP_TEMP_ROUTE_AND_RESTORE_PROVEN_WITH_LIMITS
- final verdict: CLOSED
- closure state: CLOSED

## Contour Capsule

- goal: temporarily apply a WBP config to the exact Original Codex config target, launch Original Codex with localhost proxy env sanitized, capture WBP `/v1/responses` request/response packet truth, and restore the original config exactly
- branch: codex/external-agent-lab-isolated
- head: 9512cdf953490eb2109f4849d662fa7663318c04
- touched files: `wild_boar_proxy/native_filesystem_probe.py`, `tools/original_codex_via_wbp_bounded_live_reversibility_probe.py`, `tests/test_original_live_reversibility_probe.py`, `audit_results/original_codex_via_wbp_owner_authorized_live_apply_r3_2026-05-26/*`, `audit_results/original_codex_via_wbp_owner_authorized_live_apply_r4_2026-05-26/*`, `audit_results/original_codex_via_wbp_owner_authorized_live_apply_r5_2026-05-26/*`
- tests run: `python3 -m py_compile tools/original_codex_via_wbp_bounded_live_reversibility_probe.py wild_boar_proxy/native_filesystem_probe.py`; `python3 -m unittest -q tests.test_original_live_reversibility_probe`; `python3 -m unittest -q tests.test_original_live_reversibility_probe tests.test_native_filesystem_probe`; `python3 -m unittest -q tests.test_native_launch_contract tests.test_native_launch_dispatch tests.test_codex_launch_modes tests.test_operator_surface tests.test_closeout_resilience tests.test_repo_hygiene tests.test_provider_auth_strategy tests.test_model_availability`; `git diff --check`; live probe runs R3, R4, and R5; config SHA256 verification after each live run
- blocked risks: direct egress absence, all-model availability, GPT-5.5 availability, full native UX acceptance, normal Original post-cleanup sanity, wire compatibility, and final E2E were not claimed
- closure state: CLOSED

## Verification

- tests: focused Original live tool tests passed with 5 tests; native filesystem plus tool tests passed with 156 tests; core guard suites passed with 137 tests
- build: py_compile passed for the changed live probe and native filesystem module; `git diff --check` passed
- manual: owner entered the nonce prompt manually in the Original Codex window; one earlier duplicate send was observed and treated as diagnostic noise, not a clean UX proof
- live verification: R5 packet truth records `request_observed=true`, `response_observed=true`, `forwarded_to_wbp=true`, `path=/v1/responses`, `upstream_status=200`, request body hash, response body hash, `original_route_proven=true`, `rollback_executed=true`, and `restore_verified=true`

## Artifacts

- spec: thread-only owner-authorized live apply instructions in the active task thread; no repo-resident roadmap was added
- packet: `audit_results/original_codex_via_wbp_owner_authorized_live_apply_r5_2026-05-26/original_via_wbp_summary_packet.json`
- report: `audit_results/original_codex_via_wbp_owner_authorized_live_apply_r5_2026-05-26/independent_original_via_wbp_audit.json`

## Git

- branch: codex/external-agent-lab-isolated
- commit: included in the contour commit that adds this closeout
- pushed: included when the contour commit is pushed

## Scope Check

- unrelated work mixed in: no; pre-existing dirty historical evidence stayed quarantined and unstaged
- private-data risk reviewed: yes; evidence secret-pattern scan returned no matches, prompt body and auth header were not recorded, current `auth.json` was not copied or used as execution input, and config candidate text was not stored

## Notes

- blockers encountered: R3 showed a proxy-env issue when launched via `open`; R4 showed the observer wait loop restored after request observation before response observation; both were preserved as diagnostic evidence and fixed before R5
- resume from here: CLOSED
