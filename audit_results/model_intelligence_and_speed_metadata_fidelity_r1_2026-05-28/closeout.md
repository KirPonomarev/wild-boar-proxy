# MODEL_INTELLIGENCE_AND_SPEED_METADATA_FIDELITY_R1 Closeout

## Goal

Honestly classify intelligence/speed metadata fidelity for the native ChatGPT /
Codex lane and the API / WBP lane so every exposed label stays source-tagged,
proof-bounded, and non-parity-claiming.

## Result

- status: closed honestly with limits
- final verdict: `MODEL_INTELLIGENCE_AND_SPEED_METADATA_FIDELITY_CLASSIFIED_WITH_LIMITS`
- closure state: CLOSED

## Contour Capsule

- goal: classify source/proof fidelity for native and API lane intelligence/speed metadata without parity overclaim
- branch: `codex/external-agent-lab-isolated`
- head: `ea49c406`
- touched files:
  - `tools/model_intelligence_and_speed_metadata_fidelity_r1_probe.py`
  - `tests/test_model_intelligence_and_speed_metadata_fidelity_r1_probe.py`
  - `tests/test_codex_model_registry.py`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/native_lane_metadata_fidelity_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/api_lane_metadata_fidelity_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/metadata_source_and_proof_level_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/intelligence_parity_non_claims_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/speed_metadata_boundary_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/metadata_gap_matrix.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/false_green_boundary_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/independent_audit_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/closeout.md`
- tests run:
  - `python3 -m pytest -q tests/test_model_intelligence_and_speed_metadata_fidelity_r1_probe.py tests/test_codex_model_registry.py`
  - `python3 -m py_compile tools/model_intelligence_and_speed_metadata_fidelity_r1_probe.py tests/test_model_intelligence_and_speed_metadata_fidelity_r1_probe.py tests/test_codex_model_registry.py`
  - `python3 tools/model_intelligence_and_speed_metadata_fidelity_r1_probe.py --repo-root /Volumes/Work/wild-boar-proxy --evidence-dir /Volumes/Work/wild-boar-proxy/audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28`
  - JSON parse sweep over `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/*.json`
- blocked risks:
  - all currently surfaced native/API intelligence tiers remain `unavailable_unknown` / `unproven`
  - all currently surfaced native/API speed tiers remain `unavailable_unknown` / `unproven`
  - source/proof completeness does not strengthen metadata truth beyond unknown/unproven catalog display
  - historical inventory item 0 remains open and non-counted
  - stronger read-only audit agent was not materialized and was not counted as evidence
- closure state: CLOSED

## Verification

- tests:
  - `22 passed` in combined focused run across `tests/test_model_intelligence_and_speed_metadata_fidelity_r1_probe.py` and `tests/test_codex_model_registry.py`
- build:
  - `python3 -m py_compile` passed for the new probe and focused tests
- manual:
  - probe wrote `8/8` required JSON packets
  - JSON parse sweep reported `json_ok=8`
  - generated packets explicitly mark current metadata truth as `unknown_unproven_only`
- live verification:
  - not attempted
  - contour remains metadata classification only and does not reopen acceleration or live parity proof

## Artifacts

- spec: thread-only contour plan, not stored in repo by policy
- packet:
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/native_lane_metadata_fidelity_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/api_lane_metadata_fidelity_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/metadata_source_and_proof_level_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/intelligence_parity_non_claims_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/speed_metadata_boundary_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/metadata_gap_matrix.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/false_green_boundary_packet.json`
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/independent_audit_packet.json`
- report:
  - `audit_results/model_intelligence_and_speed_metadata_fidelity_r1_2026-05-28/closeout.md`

## Git

- branch: `codex/external-agent-lab-isolated`
- commit: `ea49c406`
- pushed: pending at closeout write time

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes

## Notes

- blockers encountered:
  - cheap read-only scanner materialized a factual report confirming the main metadata surfaces and identifying false-green risks around display wording, provenance wording, and selection-vs-live truth
  - the contour stayed on probe/test/evidence surfaces and did not mutate runtime metadata emitters because current repo truth was already correctly conservative
  - an early parallel JSON sweep raced evidence creation and falsely reported `json_ok=0`; rerun serially and preserved the actual `json_ok=8` result
- resume from here: CLOSED
