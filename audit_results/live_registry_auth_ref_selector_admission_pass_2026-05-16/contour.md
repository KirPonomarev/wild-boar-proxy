# LIVE_REGISTRY_AUTH_REF_SELECTOR_ADMISSION_PASS

## Goal

Determine whether any canon-supported selector truth surface can narrow the
current live-registry `auth_ref` candidate family to one exact upstream source
for later sandbox `auth.json` materialization.

## Constraints

- admission only
- no auth payload read
- no auth payload write or copy
- no onboarding rerun
- no registry-count synthesis

## Truth Basis

- fixed destination remains
  `/Users/kirillponomarev/.codex-custom-sandbox-20260515/auth.json`
- prior contour localized the remaining ambiguity to selector truth inside the
  live-registry `auth_ref` family
- current owner-path evidence shows:
  - `rollout rotation inspect --json` reports
    `ROTATION_EVIDENCE_CONTRADICTED`
  - `stable repair --dry-run --json` reports 11 eligible registry
    `auth_ref` copy inputs
  - nested `selected_backend_snapshot` is present but narrows only to 8 current
    eligible exact sources
  - runtime consumer truth remains family-level (`observed_stable_inventory_source`),
    not one exact source file

## Allowed Outcomes

- `GO_TO_EXACT_AUTH_REF_SOURCE_ADMISSION_PASS`
- `GO_TO_SANDBOX_AUTH_JSON_MATERIALIZATION_PASS`
- `STOP_AND_DIAGNOSE`

## Verdict Rule

If no canon-supported selector truth surface narrows the currently eligible
family to one exact source surface, do not guess. Emit `STOP_AND_DIAGNOSE`.
