# Independent Audit

Verdict: `GO_TO_RERUN_ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`.

Grounded facts:
- The sandbox owner helper now normalizes auth kind through `normalize_auth_type(...)` and both the onboarding validator and `accounts validate` use that normalized result at [wild_boar_proxy/sandbox_owner_helpers.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/sandbox_owner_helpers.py:161) and [wild_boar_proxy/sandbox_owner_helpers.py](/Volumes/Work/wild-boar-proxy/wild_boar_proxy/sandbox_owner_helpers.py:314).
- The repair is narrow: it only widens the auth-kind boundary from strict `type` to `type` or legacy `auth_mode`, with a bounded fallback to `apikey` when `OPENAI_API_KEY` is present. Reserve-first onboarding logic in `wild_boar_proxy/runtime.py` is untouched.
- Targeted tests now prove the admitted legacy path and retained honest failure: [tests/test_cli.py](/Volumes/Work/wild-boar-proxy/tests/test_cli.py:442) accepts `auth_mode=apikey` plus `OPENAI_API_KEY`, while [tests/test_cli.py](/Volumes/Work/wild-boar-proxy/tests/test_cli.py:497) still rejects the invalid legacy shape missing `OPENAI_API_KEY`.
- A live read-only proof on `/Users/kirillponomarev/.codex-custom-test/auth.json` now records `normalized_auth_type = apikey` for the current sandbox payload with keys `auth_mode` and `OPENAI_API_KEY` in [compatibility_verification.json](/Volumes/Work/wild-boar-proxy/audit_results/sandbox_auth_payload_compatibility_repair_pass_2026-05-15/compatibility_verification.json).
- Forbidden live-path drift was not observed in the same compatibility verification artifact.

Conclusion:
The auth-shape blocker from the previous onboarding rerun is removed without broad auth refactoring or live fallback. The next honest step is to rerun `ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS`.
