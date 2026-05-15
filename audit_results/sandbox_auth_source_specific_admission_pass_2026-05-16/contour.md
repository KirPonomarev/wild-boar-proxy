# SANDBOX_AUTH_SOURCE_SPECIFIC_ADMISSION_PASS

## Goal

Try to narrow the upstream auth source from a source class to one exact surface
for later sandbox `auth.json` materialization, without reading secret contents,
writing auth material, or rerunning onboarding.

## Scope

- read-only confirmation of the fixed sandbox destination and current blocker
- read-only inspection of exact source path candidates
- policy and rollback analysis for those exact source candidates
- canon decision about the next contour

## Out Of Scope

- writing `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`
- copying any auth payload
- secret-content inspection
- onboarding rerun
- lifecycle, route, runtime, or UI work

## Decision Rule

If one exact source surface can be admitted honestly, choose it. If several
equally plausible exact source surfaces remain under forbidden live roots and no
owner-level selector narrows them, do not guess; open a narrower transfer
admission contour instead.
