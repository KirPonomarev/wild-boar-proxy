# WBP Codex Model Availability Classification R1 Closeout

## Goal

Classify bounded direct WBP model availability one model at a time through live
non-stream requests, without promoting direct WBP acceptance into native Codex
acceptance, provider-family parity, or final E2E proof.

## Result

- status: ok
- final verdict: WBP_CODEX_MODEL_AVAILABILITY_CLASSIFIED
- closure state: CLOSED

## Contour Capsule

- goal: prove bounded direct WBP model availability for the admitted sample with
  transport-limited per-model claims
- branch: codex/external-agent-lab-isolated
- head: 23016a0d69b5abc92523a86632faf85fe28a6e33 before this contour commit
- touched files: tools/model_availability_direct_only_smoke_probe.py,
  tests/test_model_availability_direct_only_smoke_probe.py,
  audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27
- tests run: python3 -m py_compile
  tools/model_availability_direct_only_smoke_probe.py
  tests/test_model_availability_direct_only_smoke_probe.py; python3 -m pytest
  -q tests/test_model_availability.py
  tests/test_model_availability_direct_only_smoke_probe.py; live direct-only
  model availability probe; JSON status sweep; secret marker scan; closeout
  resilience
- blocked risks: native Codex acceptance, Codex CLI acceptance, provider-family
  compatibility, direct egress absence, streaming, tool loop, Original Codex
  reversibility, and final E2E remain unclaimed
- closure state: CLOSED

## Verification

- tests: python3 -m pytest -q tests/test_model_availability.py
  tests/test_model_availability_direct_only_smoke_probe.py
- build: py_compile passed for the changed probe and test file
- manual: emitted JSON packet statuses all read ok; per-model direct preflight
  packets were inspected directly; independent audit and false-green audit both
  remained ok; secret marker scan returned no matches
- live verification: direct WBP non-stream smoke classified four admitted
  models. gpt-5.5, gpt-5.4-mini, and gpt-5.4 returned 200 with direct WBP
  response acceptance. direct-mistral-devstral-2512 remained classified as
  blocked_with_reason with failure_cause provider_error and http_status 502.

## Artifacts

- spec: thread-only contour definition
- packet: audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_direct_only_summary_packet.json
- report: audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/independent_model_availability_audit.json
- false-green audit: audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_false_green_audit.json
- matrix: audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_matrix.json
- readiness reference: audit_results/wbp_model_availability_smoke_matrix_r1_2026-05-27/model_availability_readiness_reference_packet.json

## Git

- branch: codex/external-agent-lab-isolated
- commit: 209b554fbea9993c97e247de400b5da9ba4565f9 primary contour payload commit before closeout Git finalization
- pushed: yes; origin/codex/external-agent-lab-isolated already contained predecessor contour commit 41ed8966d5550971ee3407a38780232c455bb9f7 before this closeout-only finalization

## Scope Check

- unrelated work mixed in: no; historical dirty evidence remained quarantined
  and unstaged
- private-data risk reviewed: yes; raw prompt text, auth headers, and token
  values were not recorded in emitted evidence

## Notes

- blockers encountered: the first live rerun blocked only on sync-gate hygiene.
  The fix was to admit current-contour evidence mutations and quarantine known
  historical dirt. Model transport truth itself did not need rollback.
- resume from here: CLOSED
