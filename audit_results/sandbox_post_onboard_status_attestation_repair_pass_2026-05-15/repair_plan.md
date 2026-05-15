# Repair Plan

## Chosen repair

Keep raw `status --json` and `healthcheck --json` semantics untouched.

Add a separate onboarding-only machine-carried classifier that answers a narrower
question:

`does this post-onboard status failure actually block entry into reserve-only lifecycle work?`

## Why this path

- The preserved rerun2 live packet proves reserve-first onboarding success.
- The preserved status packet proves degraded launch readiness.
- The degraded status comes from a reserve-only shape with no active backends,
  not from active-routing drift.
- Promotion/demotion lifecycle owner paths do their own post-mutation proof, so
  launch-readiness failure before promotion must not be silently widened into a
  generic lifecycle block.

## Guardrails

- do not rewrite `status --json`
- do not redefine `ATTESTATION_FAILED`
- do not mark truth drift, listener failure, or proxy drift as lifecycle-ready
- admit only the narrow `reserve_only_launch_gap` case
