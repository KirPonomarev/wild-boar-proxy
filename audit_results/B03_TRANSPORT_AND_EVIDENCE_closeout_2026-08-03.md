<!-- SPDX-FileCopyrightText: 2026 Kirill Ponomarev -->
<!-- SPDX-License-Identifier: AGPL-3.0-or-later -->

# B03 Normalized Transport And Evidence State Machine Closeout

## Goal

Implement the normalized transport boundary (native/API/one-shot/ACP shared
surface) and the normalized evidence state machine (canonical evidence
taxonomy with non-empty acceptance and claim guards), and update the affected
contract canon with a canon-diff report.

## Result

- status: implemented and verified
- final verdict: normalized transport envelopes/events/errors/receipts are
  live (`transport_normalization.py`); the canonical evidence state machine
  with the plan's exact level taxonomy and false-green negatives is live
  (`evidence_state_machine.py`); `RUNTIME_CONTRACT.md` updated with the
  evidence-level and transport sections; canon digest transition recorded
- closure state: CLOSED

## Contour Capsule

- goal: B03 normalized transport + evidence state machine (contract contour)
- branch: `codex/b03-transport-evidence`
- head: `4d74f15e1b293ffcdf97c7aec6909b6d2f6baae1` (base before contour commit)
- touched files: `wild_boar_proxy/transport_normalization.py` (new),
  `wild_boar_proxy/evidence_state_machine.py` (new), `RUNTIME_CONTRACT.md`,
  `tests/test_transport_normalization.py` (new),
  `tests/test_evidence_state_machine.py` (new),
  `audit_results/B03_TRANSPORT_AND_EVIDENCE_SPEC_2026-08-03.md`,
  `audit_results/B03_TRANSPORT_AND_EVIDENCE_closeout_2026-08-03.md`
- tests run: new suites (29 tests); `make check`; `make test-core`;
  `make test-custom-stability`; `make test-web-e2e`; `make test-full`
- blocked risks: `all([])` acceptance, milestone SHA collision, synthetic
  evidence in live claim slots, credential-presence/bridge-success as live
  proof, stale evidence, ambiguous-delivery retry
- closure state: CLOSED

## Verification

- tests:
  - `tests/test_transport_normalization.py` +
    `tests/test_evidence_state_machine.py` -> `29 passed`
  - `make check` -> green
  - `make test-core` -> green
  - `make test-custom-stability` -> green
  - `make test-web-e2e` -> green
  - `make test-full` -> full local baseline green
- build:
  - `make check` (compileall + collect) green
- manual:
  - `git diff --check` clean
- live verification:
  - no live mutation; pure contract modules

## Artifacts

- spec: `audit_results/B03_TRANSPORT_AND_EVIDENCE_SPEC_2026-08-03.md`
- packet: no live packet artifact required
- report: `CANON_DIFF_REPORT` in PR #117: canon digest transition
  `6975b76f0d11ce1b4d90d23c72fbca6bd08a40571db6ef8e91806389f4eaea6f` ->
  `a2a482975e4f8feb0a224f09ef010bddfb1ede6f041d443c731404fcd065830d`;
  changed file: `RUNTIME_CONTRACT.md` (Evidence levels + Normalized transport
  sections)

## Git

- branch: `codex/b03-transport-evidence`
- commit: contour commit contains modules, tests, spec, closeout, and canon
  update
- pushed: yes, pushed and merged to `main` after required checks

## Scope Check

- unrelated work mixed in: no
- private-data risk reviewed: yes (no credentials in envelopes, receipts, or
  evidence records)
- live-path mutation performed: no
- shared-helper refactor introduced: no
- materialization output drift accepted: no

## Notes

- blockers encountered: none blocking; the B00 closeout note about
  evidence-level taxonomy naming (plan `LIVE_PROVEN`/`PHYSICAL_VISIBLE_PROVEN`
  vs legacy `PHYSICAL_PROVEN`) is resolved here at the canonical model level;
  legacy surface adoption of the canonical names is a B06 regression concern
- resume from here: CLOSED
