# SANDBOX_ONBOARDING_AUTH_CANDIDATE_DIAGNOSE_PASS

## Goal

Localize why `accounts onboard --json` on the preserved sandbox root cannot
discover an admissible auth candidate, and decide the narrowest canon-supported
next contour without creating, copying, or importing auth material in this
contour.

## Scope

- read-only confirmation of the onboarding stop basis
- read-only mapping of owner-lane auth discovery logic
- read-only inventory of sandbox auth-related paths
- canon admissibility decision for the next auth-related contour

## Out Of Scope

- writing `auth.json`
- copying or importing live auth
- rerunning onboarding
- lifecycle actions
- route or runtime mutations

## Success Criteria

- the missing auth-candidate cause is localized narrowly
- observed discovery behavior is separated from the next-step policy decision
- the next contour class is explicit
- no auth write, onboarding retry, or forbidden-root drift occurs
