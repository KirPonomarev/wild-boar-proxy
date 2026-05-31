# NARROWER_SOURCE_TRANSFER_ADMISSION_PASS

## Goal

Attempt to narrow the current forbidden-root auth source family to one
transfer-safe exact source surface for a later sandbox `auth.json`
materialization step, without reading secret contents, writing auth material, or
rerunning onboarding.

## Scope

- read-only confirmation of the fixed sandbox destination and current ambiguity
- read-only inspection of policy-shaped exact source candidates
- rollback-boundary analysis for a later transfer/materialization step
- canon decision about the next exact contour

## Out Of Scope

- writing `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`
- copying any auth payload
- secret-content inspection
- onboarding rerun
- lifecycle, route, runtime, or UI work

## Decision Rule

If one exact transfer-safe source surface can be named honestly, admit it. If
several policy-shaped exact candidates remain and no owner-level selector
narrowly chooses one, do not guess; move to a selector-admission contour rather
than to materialization.
