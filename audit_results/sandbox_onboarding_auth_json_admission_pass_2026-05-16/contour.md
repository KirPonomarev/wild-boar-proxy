# SANDBOX_ONBOARDING_AUTH_JSON_ADMISSION_PASS

## Goal

Keep the onboarding destination fixed to the sandbox-local `auth.json` path and
choose the narrowest admissible upstream auth source class without reading
secret contents, writing auth material, or rerunning onboarding.

## Scope

- read-only destination-lock confirmation
- read-only classification of upstream auth source classes
- rollback-surface declaration for the next contour
- canon decision about the next exact contour

## Out Of Scope

- writing `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`
- copying any auth payload
- reopening explicit `--auth-ref` as the primary lane
- onboarding rerun
- lifecycle, route, runtime, or UI work

## Decision Rule

Choose the narrowest source class that is both evidenced and canonically
admissible. If all observed candidates sit in forbidden roots, select a
source-specific admission contour rather than jumping to materialization.
