# SANDBOX_POST_ONBOARD_STATUS_ATTESTATION_REPAIR_PASS

## Goal

Resolve the post-onboard lifecycle-admission blocker without weakening raw
`status --json` truth.

## Scope

- analyze the preserved rerun2 onboarding/status packets
- add a narrow runtime classification for reserve-only post-onboard admission
- keep raw live attestation semantics unchanged
- prove the new classification with focused tests and an independent audit

## Decision Target

- `GO_TO_ACCOUNT_LIFECYCLE_SANDBOX_ACTIONS_PASS`
- or `STOP_AND_DIAGNOSE`
