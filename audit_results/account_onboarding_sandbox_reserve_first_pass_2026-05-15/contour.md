# ACCOUNT_ONBOARDING_SANDBOX_RESERVE_FIRST_PASS

## Goal

Attempt the first sandbox onboarding mutation through `accounts onboard --json` on the preserved fresh sandbox root `/Users/kirillponomarev/.codex-custom-sandbox-20260515` and accept success only if reserve-first proof is machine-readable and confirmed by post-refresh truth.

## Result Shape

- owner surface only
- post-refresh proof mandatory
- UI/action-ledger evidence optional only if ambiguity remains
- stop immediately if sandbox-local auth is missing or reserve-first proof is absent
