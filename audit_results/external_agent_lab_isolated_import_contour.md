# External Agent Lab Isolated Import Contour Index

Date: `2026-05-09`
Scope: canonical naming/index alignment for isolated lab contour history

## Purpose

This document is an index only. It maps the isolated lab contour sequence and
points to source artifacts. It does not supersede C1-C6 artifacts and does not
introduce new technical truth claims.

## Canon Scope

In scope:

- `external_agent_lab/*`
- `run_lab.py`
- `agent_eval.py`
- `tests/test_external_agent_lab.py`
- `EXTERNAL_AGENT_LAB.md`
- `EXTERNAL_AGENT_LAB_AUDIT.md`
- `external_agent_lab_acceptance_verification.md`

Out of scope:

- `wild_boar_proxy/*`
- live Wild Boar runtime
- provider live probes
- paid route execution
- UI work
- production integration

## Contour Map

- C1 quarantine import:
  - `audit_results/external_agent_lab_c1_quarantine_import_contour.md`
- C2 CLI preflight JSON contract:
  - commit `9ca0b05`
- C3 truth relock and acceptance docs:
  - `audit_results/external_agent_lab_c3_truth_relock_contour.md`
- C4 merge-readiness closeout:
  - `audit_results/external_agent_lab_c4_merge_readiness_closeout.md`
- C5 PR review closure:
  - `audit_results/external_agent_lab_c5_review_closure.md`
- C6b read-only post-merge recovery verification:
  - PR comment evidence:
    `https://github.com/KirPonomarev/wild-boar-proxy/pull/47#issuecomment-4412695748`

## Notes

- canonical acceptance verification remains unittest-first
- `pytest` remains optional local convenience only
- isolated lab remains non-integrated into `wild_boar_proxy/*`
