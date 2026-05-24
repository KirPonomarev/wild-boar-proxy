# Spec: CONTOUR_07 HONEST_RELEASE_CLAIM_MATRIX

## Objective

Freeze user-facing release claims so they are no wider than the currently
proven review/import surfaces:

- local JSON review packet preview/import
- one exact-text safe apply with receipt and recovery
- the current narrow explicit-confirm import-existing lane
- honest negative wording for unsupported or unclaimed broader surfaces

## In Scope

- user-facing claim wording in `README.md`
- user-facing claim wording in `wild_boar_proxy/web_design_ui/index.html`
- boundary tests in `tests/test_web_design_ui.py`
- one canonical first-useful-release claim matrix

## Out of Scope

- runtime behavior changes
- command surface expansion
- review/apply/import execution changes
- UI redesign
- release tagging or release-cut automation

## Constraints

- no claim may outrun test-proven repo truth
- unsupported surfaces must stay explicitly unsupported or unclaimed
- one canonical claim matrix must remain readable in user-facing surfaces
- this contour must remain text-only

## Acceptance Criteria

- [x] `README.md` narrows the first useful release claim boundary
- [x] the web UI `About` surface exposes the same narrow claim matrix
- [x] review/import/apply claims map to current proof only
- [x] `DOCX review import` stays `not supported yet`
- [x] `Word / Google Docs roundtrip` stays `not claimed`
- [x] no broader structural auto-apply, mass apply, or full sync claim remains
- [x] targeted tests and adjacent UI regressions pass

## Verification

- tests:
  - `tests.test_web_design_ui`
  - targeted proof-binding tests in `tests.test_review_bridge_command_bus`
  - targeted import-confirm proof in `tests.test_web_design_live_server`
- build:
  - `python3 -m py_compile tests/test_web_design_ui.py`
  - `git diff --check`
- live evidence:
  - `audit_results/honest_release_claim_matrix_pass_2026-05-25/evidence/claim_matrix.json`

## Open Questions

- whether a later release contour wants to move the canonical claim matrix from
  README/UI copy into a generated release note surface without widening claims
