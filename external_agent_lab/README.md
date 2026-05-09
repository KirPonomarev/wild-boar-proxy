# External Agent Lab Package

`external_agent_lab` is an isolated R&D package imported into the repository as
a non-runtime lane.

## Purpose

- evaluate external model helper/comparison/fallback candidates
- keep command-surface experiments isolated from main runtime control paths
- preserve reproducible acceptance artifacts for the isolated lane

## Boundaries

- no mutation of `wild_boar_proxy/*`
- no runtime integration claims
- no provider/live probes in default acceptance verification
- no reliance on historical result dumps as canonical evidence

## Entry Surfaces

- root wrappers:
  - `run_lab.py`
  - `agent_eval.py`
- shared CLI path:
  - `external_agent_lab/cli.py`
- quarantined legacy implementation:
  - `external_agent_lab/legacy/*`

## Canonical Artifacts

- contour index:
  - `audit_results/external_agent_lab_isolated_import_contour.md`
- lane overview:
  - `EXTERNAL_AGENT_LAB.md`
- lane audit:
  - `EXTERNAL_AGENT_LAB_AUDIT.md`
- acceptance verification:
  - `external_agent_lab_acceptance_verification.md`
