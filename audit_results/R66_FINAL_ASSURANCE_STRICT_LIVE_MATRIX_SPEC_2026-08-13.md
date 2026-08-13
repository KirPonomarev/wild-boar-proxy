<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# Spec: R66 Final Assurance Strict Live Matrix

## Objective

Remove false-green evidence acceptance from `AssuranceEvidenceBundleV2` and
make B18 require subject-specific, candidate-bound proof for repository, CI,
package, migration, privacy, workflow, web, account-isolation, protected-
network, provider API, and provider CLI claims.

## In Scope

- reject generic `{"ok": true}` / `{"passed": true}` blobs as physical
  acceptance;
- require strict schemas for every non-pending assurance check;
- replace the single provider/CLI boolean with provider and workflow-
  combination coverage for DeepSeek, Kimi, GLM, Qwen, API/API, API/CLI, and
  CLI/CLI;
- bind live provider/workflow evidence to exact actor, binding, assignment,
  session, dispatch, candidate, output digest, credential-presence, no-
  fallback, no-substitution, and live-response facts;
- allow typed pending only for explicitly external live checks;
- keep the production verifier read-only and rebuild external evidence only
  after the exact candidate is merged and verified.

## Out of Scope

- live provider dispatch, credential reads, interactive login, or CLI install;
- public release or protected-network mutation;
- UI/product design changes;
- documentation refresh outside the assurance contract.

## Constraints

- no synthetic receipt may close physical acceptance;
- no live dispatch is authorized by this contour;
- one receipt per required check; duplicates and missing checks fail closed;
- pending internal checks are invalid evidence, not an external wait;
- B18 may emit only readiness for independent audit, typed external wait, or a
  typed failure, never `DONE`.

## Acceptance Criteria

- bare booleans fail for every assurance category;
- provider live proof requires all mandatory providers and applicable
  combinations with unique dispatch/session/output identities;
- synthetic, controlled, fallback, substituted, credential-absent, missing-
  output, mismatched-revision, and wrong-candidate evidence fail;
- typed pending provider receipts yield `WAIT_EXTERNAL_PREREQUISITE` without
  readiness;
- current stale production evidence fails honestly until rebuilt;
- focused, affected, repository, and exact-candidate CI gates pass before
  merge.

## Verification

- focused `tests/test_final_candidate_assurance.py` and gate-evidence tests;
- `make check`, core/custom/web gates, and one full suite for the material
  contour;
- exact candidate CI, merge readback, and exact remote-main CI;
- production assurance readback from the external control root.

## Open Questions

- none; live credentials remain a separately gated external prerequisite.
