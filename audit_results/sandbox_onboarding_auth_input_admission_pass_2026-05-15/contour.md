# SANDBOX_ONBOARDING_AUTH_INPUT_ADMISSION_PASS

## Goal

Choose the narrowest next onboarding auth input lane for
`accounts onboard --json` without writing auth material, rerunning onboarding,
or widening secret-bearing scope beyond what the sandbox boundary already
admits.

## Scope

- read-only comparison of the explicit `--auth-ref` lane and the default
  sandbox-local `auth.json` lane
- sandbox boundary and rollback review for those two lanes only
- supporting review of the stable auth inventory snapshot as secondary evidence
- canon decision about the next exact admission contour

## Out Of Scope

- writing or copying auth payloads
- rerunning `accounts onboard --json`
- lifecycle, route, runtime, or UI work
- treating stable inventory as a third primary onboarding lane

## Decision Rule

Choose the narrower lane already supported by the current owner semantics and
declared sandbox boundary. If neither lane can be narrowed honestly, stop.
